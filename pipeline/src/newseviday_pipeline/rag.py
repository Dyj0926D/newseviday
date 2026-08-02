import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from newseviday_pipeline.embeddings import EmbeddingProvider, cosine_similarity
from newseviday_pipeline.models import Article, Chunk, ContentSnapshot, ContractModel

CHUNKING_VERSION = "article-readable-v1"


class IndexedVector(ContractModel):
    chunk: Chunk
    vector: list[float]


class DenseIndexArtifact(ContractModel):
    schema_version: str = "1.0.0"
    snapshot_id: str
    chunking_version: str = CHUNKING_VERSION
    embedding_model: str
    dimensions: int = Field(ge=1)
    records: list[IndexedVector] = Field(default_factory=list)


class RetrievedChunk(ContractModel):
    chunk: Chunk
    rank: int = Field(ge=1)
    score: float


class RetrievalResult(ContractModel):
    mode: str
    candidates: list[RetrievedChunk] = Field(default_factory=list)
    fallback_reason: str | None = None


@dataclass(frozen=True)
class ContextAssembly:
    text: str
    chunks: list[RetrievedChunk]


def article_readable_text(article: Article) -> str:
    sections = [article.ai.title_zh if article.ai and article.ai.title_zh else article.facts.title]
    if article.facts.title not in sections:
        sections.append(article.facts.title)
    if article.facts.abstract:
        sections.append(article.facts.abstract)
    if article.ai:
        if article.ai.summary_zh:
            sections.append(article.ai.summary_zh)
        if article.ai.why_it_matters:
            sections.append(article.ai.why_it_matters)
        sections.extend(article.ai.key_points)
    return "\n\n".join(section.strip() for section in sections if section and section.strip())


def _split_text(text: str, maximum_chars: int, overlap_chars: int) -> list[str]:
    if maximum_chars < 200 or overlap_chars < 0 or overlap_chars >= maximum_chars:
        raise ValueError("invalid_chunking_configuration")
    normalized = "\n\n".join(part.strip() for part in text.split("\n\n") if part.strip())
    if not normalized:
        return []
    result: list[str] = []
    start = 0
    while start < len(normalized):
        proposed_end = min(start + maximum_chars, len(normalized))
        end = proposed_end
        if proposed_end < len(normalized):
            boundary = normalized.rfind("\n\n", start + maximum_chars // 2, proposed_end)
            if boundary > start:
                end = boundary
        chunk = normalized[start:end].strip()
        if chunk:
            result.append(chunk)
        if end >= len(normalized):
            break
        start = max(start + 1, end - overlap_chars)
    return result


def chunk_snapshot(
    snapshot: ContentSnapshot,
    *,
    maximum_chars: int = 900,
    overlap_chars: int = 120,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for article in snapshot.articles:
        for position, text in enumerate(
            _split_text(article_readable_text(article), maximum_chars, overlap_chars)
        ):
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            chunk_key = f"{CHUNKING_VERSION}:{article.id}:{position}:{content_hash}"
            chunks.append(
                Chunk(
                    id=f"chunk-{hashlib.sha256(chunk_key.encode()).hexdigest()[:20]}",
                    article_id=article.id,
                    position=position,
                    text=text,
                    language=article.language,
                    token_estimate=max(1, math.ceil(len(text) / 3)),
                    content_hash=content_hash,
                )
            )
    return chunks


def build_dense_index(
    snapshot: ContentSnapshot,
    embedder: EmbeddingProvider,
) -> DenseIndexArtifact:
    chunks = chunk_snapshot(snapshot)
    vectors = embedder.embed([chunk.text for chunk in chunks])
    if len(vectors) != len(chunks):
        raise ValueError("embedding_count_mismatch")
    return DenseIndexArtifact(
        snapshot_id=snapshot.snapshot_id,
        embedding_model=embedder.model,
        dimensions=embedder.dimensions,
        records=[
            IndexedVector(chunk=chunk, vector=vector)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ],
    )


def retrieve_dense(
    query: str,
    index: DenseIndexArtifact,
    embedder: EmbeddingProvider,
    *,
    top_k: int = 10,
    article_id: str | None = None,
) -> RetrievalResult:
    if not query.strip():
        raise ValueError("query_required")
    if embedder.model != index.embedding_model or embedder.dimensions != index.dimensions:
        raise ValueError("embedding_index_mismatch")
    query_vector = embedder.embed([query])[0]
    scored = [
        (record.chunk, cosine_similarity(query_vector, record.vector))
        for record in index.records
        if article_id is None or record.chunk.article_id == article_id
    ]
    scored.sort(key=lambda item: (-item[1], item[0].id))
    return RetrievalResult(
        mode="chunk_dense",
        candidates=[
            RetrievedChunk(chunk=chunk, rank=rank, score=round(score, 8))
            for rank, (chunk, score) in enumerate(scored[:top_k], start=1)
        ],
    )


def retrieve_with_article_fallback(
    query: str,
    snapshot: ContentSnapshot,
    index: DenseIndexArtifact,
    embedder: EmbeddingProvider,
    *,
    top_k: int = 10,
    minimum_score: float = 0.08,
) -> RetrievalResult:
    result = retrieve_dense(query, index, embedder, top_k=top_k)
    if result.candidates and result.candidates[0].score >= minimum_score:
        return result

    article_vectors = embedder.embed(
        [article_readable_text(article) for article in snapshot.articles]
    )
    query_vector = embedder.embed([query])[0]
    ranked_articles = sorted(
        zip(snapshot.articles, article_vectors, strict=True),
        key=lambda item: -cosine_similarity(query_vector, item[1]),
    )
    if not ranked_articles:
        return RetrievalResult(
            mode="article_dense",
            candidates=[],
            fallback_reason="empty_corpus",
        )
    best_article = ranked_articles[0][0]
    fallback = retrieve_dense(
        query,
        index,
        embedder,
        top_k=top_k,
        article_id=best_article.id,
    )
    fallback.mode = "article_dense"
    fallback.fallback_reason = "chunk_score_below_threshold"
    return fallback


def assemble_context(
    result: RetrievalResult,
    *,
    max_context_chars: int = 8_000,
    max_chunks_per_article: int = 2,
) -> ContextAssembly:
    selected: list[RetrievedChunk] = []
    article_counts: dict[str, int] = {}
    blocks: list[str] = []
    used = 0
    for candidate in result.candidates:
        article_id = candidate.chunk.article_id
        if article_counts.get(article_id, 0) >= max_chunks_per_article:
            continue
        block = (
            f"[chunkId={candidate.chunk.id};articleId={article_id};score={candidate.score:.4f}]\n"
            f"{candidate.chunk.text}"
        )
        separator = 2 if blocks else 0
        if used + separator + len(block) > max_context_chars:
            continue
        blocks.append(block)
        selected.append(candidate)
        article_counts[article_id] = article_counts.get(article_id, 0) + 1
        used += separator + len(block)
    return ContextAssembly(text="\n\n".join(blocks), chunks=selected)


def write_index(index: DenseIndexArtifact, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=output.parent, prefix="index-", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(index.model_dump_json(by_alias=True, indent=2) + "\n")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def load_index(path: Path) -> DenseIndexArtifact:
    return DenseIndexArtifact.model_validate_json(path.read_text(encoding="utf-8"))


def vectorize_ndjson(index: DenseIndexArtifact) -> str:
    lines = []
    for record in index.records:
        lines.append(
            json.dumps(
                {
                    "id": record.chunk.id,
                    "values": record.vector,
                    "metadata": {
                        "articleId": record.chunk.article_id,
                        "position": record.chunk.position,
                        "contentHash": record.chunk.content_hash,
                        "snapshotId": index.snapshot_id,
                    },
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    return "\n".join(lines) + ("\n" if lines else "")
