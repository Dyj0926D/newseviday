import json
from pathlib import Path

from newseviday_pipeline.embeddings import HashingEmbedder
from newseviday_pipeline.rag import (
    assemble_context,
    build_dense_index,
    chunk_snapshot,
    retrieve_dense,
    retrieve_with_article_fallback,
    vectorize_ndjson,
)
from newseviday_pipeline.snapshot import load_snapshot

ROOT = Path(__file__).resolve().parents[2]
CURRENT_SNAPSHOT = ROOT / "apps" / "web" / "public" / "data" / "current.json"
RAG_DATASET = ROOT / "pipeline" / "eval" / "rag-gold-trial-v2.json"
RAG_CORPUS_SNAPSHOT_ID = json.loads(RAG_DATASET.read_text(encoding="utf-8"))["corpusSnapshotId"]
PINNED_RAG_SNAPSHOT = (
    ROOT / "apps" / "web" / "public" / "data" / "versions" / f"{RAG_CORPUS_SNAPSHOT_ID}.json"
)


def test_chunks_are_traceable_and_deterministic() -> None:
    snapshot = load_snapshot(CURRENT_SNAPSHOT)
    first = chunk_snapshot(snapshot, maximum_chars=300, overlap_chars=40)
    second = chunk_snapshot(snapshot, maximum_chars=300, overlap_chars=40)

    assert first
    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]
    assert {chunk.article_id for chunk in first} == {article.id for article in snapshot.articles}
    assert all(chunk.content_hash and chunk.token_estimate > 0 for chunk in first)


def test_dense_retrieval_context_and_article_fallback() -> None:
    snapshot = load_snapshot(PINNED_RAG_SNAPSHOT)
    embedder = HashingEmbedder()
    index = build_dense_index(snapshot, embedder)
    result = retrieve_dense("Video-DeepResearch 发现了哪两个智能体瓶颈？", index, embedder, top_k=5)

    assert len(result.candidates) == 5
    assert result.candidates[0].chunk.article_id == "article-aa9f3addc6b0fbb2a1a0"
    context = assemble_context(result, max_context_chars=2_000, max_chunks_per_article=2)
    assert context.text
    counts: dict[str, int] = {}
    for candidate in context.chunks:
        counts[candidate.chunk.article_id] = counts.get(candidate.chunk.article_id, 0) + 1
    assert max(counts.values()) <= 2

    fallback = retrieve_with_article_fallback(
        "完全无关的火星农业问题",
        snapshot,
        index,
        embedder,
        minimum_score=1.0,
    )
    assert fallback.mode == "article_dense"
    assert fallback.fallback_reason == "chunk_score_below_threshold"


def test_vectorize_export_contains_trace_metadata() -> None:
    snapshot = load_snapshot(CURRENT_SNAPSHOT)
    index = build_dense_index(snapshot, HashingEmbedder(dimensions=64))
    first_line = vectorize_ndjson(index).splitlines()[0]

    assert '"articleId"' in first_line
    assert f'"snapshotId":"{snapshot.snapshot_id}"' in first_line
