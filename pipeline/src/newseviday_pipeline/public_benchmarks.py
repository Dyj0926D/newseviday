import hashlib
import math
import os
import re
import statistics
import tempfile
import time
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

import httpx
from pydantic import Field

from newseviday_pipeline.embeddings import EmbeddingProvider, cosine_similarity
from newseviday_pipeline.models import ContractModel

HF_DATASET_API = "https://huggingface.co/api/datasets"
HF_DATASET_SERVER = "https://datasets-server.huggingface.co"
MULTIHOP_DATASET_ID = "yixuantt/MultiHopRAG"
RAGBENCH_DATASET_ID = "galileo-ai/ragbench"
RetrievalMode = Literal["article_dense_hashing", "bm25", "hybrid_rrf"]


class BenchmarkManifest(ContractModel):
    benchmark: str
    dataset_id: str
    revision: str
    license: str
    source_url: str
    fetched_at: datetime
    configs: list[str]
    splits: list[str]


class PublicDocument(ContractModel):
    id: str
    url: str
    title: str
    text: str


class PublicQuestion(ContractModel):
    id: str
    query: str
    question_type: str
    answer: str
    expected_document_ids: list[str] = Field(default_factory=list)


class MultiHopArtifact(ContractModel):
    schema_version: str = "1.0.0"
    manifest: BenchmarkManifest
    documents: list[PublicDocument]
    questions: list[PublicQuestion]


class PublicRetrievalMetrics(ContractModel):
    recall_at5: float
    recall_at10: float
    hit_at5: float
    mrr: float
    ndcg_at10: float
    p50_latency_ms: int
    p95_latency_ms: int


class QuestionTypeResult(ContractModel):
    question_type: str
    sample_count: int
    recall_at5: float
    hit_at5: float


class PublicRetrievalReport(ContractModel):
    schema_version: str = "1.0.0"
    run_id: str
    generated_at: datetime
    benchmark: str
    dataset_id: str
    dataset_revision: str
    license: str
    retrieval_mode: str
    embedding_model: str
    corpus_document_count: int
    benchmark_question_count: int
    evaluated_question_count: int
    excluded_null_question_count: int
    seed: str
    metrics: PublicRetrievalMetrics
    by_question_type: list[QuestionTypeResult]
    note: str


class RagBenchReferenceReport(ContractModel):
    schema_version: str = "1.0.0"
    generated_at: datetime
    dataset_id: str
    dataset_revision: str
    license: str
    config: str
    split: str
    sample_count: int
    adherence_positive_rate: float
    average_relevance_score: float
    average_utilization_score: float
    average_completeness_score: float
    sentence_label_coverage: float
    purpose: str


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


def _atomic_json(value: ContractModel, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=output.parent, prefix="benchmark-", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value.model_dump_json(by_alias=True, indent=2) + "\n")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


class HuggingFaceDatasetClient:
    def __init__(self, timeout_seconds: int = 60) -> None:
        self.timeout_seconds = timeout_seconds

    def _get(self, url: str, *, params: dict[str, str | int] | None = None) -> httpx.Response:
        last_error: httpx.RequestError | None = None
        for attempt in range(3):
            try:
                response = httpx.get(
                    url,
                    params=params,
                    timeout=self.timeout_seconds,
                    follow_redirects=True,
                    headers={"User-Agent": "NewsEviday-EvalHarness/1.0"},
                )
                response.raise_for_status()
                return response
            except httpx.RequestError as error:
                last_error = error
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
        if last_error is not None:
            raise last_error
        raise RuntimeError("huggingface_request_failed")

    def revision(self, dataset_id: str) -> str:
        response = self._get(f"{HF_DATASET_API}/{dataset_id}")
        payload = response.json()
        revision = payload.get("sha") if isinstance(payload, dict) else None
        if not isinstance(revision, str) or not revision:
            raise ValueError("huggingface_dataset_revision_missing")
        return revision

    def row_count(self, dataset_id: str, config: str, split: str) -> int:
        response = self._get(
            f"{HF_DATASET_SERVER}/size", params={"dataset": dataset_id}
        )
        payload = response.json()
        entries = payload.get("size", {}).get("splits", [])
        for entry in entries:
            if entry.get("config") == config and entry.get("split") == split:
                count = entry.get("num_rows")
                if isinstance(count, int) and count >= 0:
                    return count
        raise ValueError("huggingface_dataset_split_size_missing")

    def rows(self, dataset_id: str, config: str, split: str) -> list[dict[str, Any]]:
        count = self.row_count(dataset_id, config, split)
        result: list[dict[str, Any]] = []
        for offset in range(0, count, 100):
            response = self._get(
                f"{HF_DATASET_SERVER}/rows",
                params={
                    "dataset": dataset_id,
                    "config": config,
                    "split": split,
                    "offset": offset,
                    "length": min(100, count - offset),
                },
            )
            payload = response.json()
            rows = payload.get("rows") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise ValueError("huggingface_dataset_rows_missing")
            for item in rows:
                row = item.get("row") if isinstance(item, dict) else None
                if not isinstance(row, dict):
                    raise ValueError("huggingface_dataset_row_invalid")
                result.append(row)
        if len(result) != count:
            raise ValueError("huggingface_dataset_row_count_mismatch")
        return result


def adapt_multihop_rows(
    corpus_rows: list[dict[str, Any]],
    question_rows: list[dict[str, Any]],
    *,
    revision: str,
    fetched_at: datetime | None = None,
) -> MultiHopArtifact:
    documents: list[PublicDocument] = []
    document_ids_by_url: dict[str, str] = {}
    for row in corpus_rows:
        url = str(row.get("url") or "").strip()
        title = str(row.get("title") or "").strip()
        body = str(row.get("body") or "").strip()
        if not url or not title or not body or url in document_ids_by_url:
            continue
        document_id = _stable_id("multihop-doc", url)
        document_ids_by_url[url] = document_id
        metadata = " | ".join(
            str(row.get(key) or "").strip()
            for key in ("source", "category", "published_at")
            if str(row.get(key) or "").strip()
        )
        documents.append(
            PublicDocument(
                id=document_id,
                url=url,
                title=title,
                text=f"{title}\n{metadata}\n{body}",
            )
        )
    questions: list[PublicQuestion] = []
    for index, row in enumerate(question_rows):
        query = str(row.get("query") or "").strip()
        if not query:
            continue
        evidence = row.get("evidence_list")
        evidence_rows = evidence if isinstance(evidence, list) else []
        expected = list(
            dict.fromkeys(
                document_ids_by_url[url]
                for item in evidence_rows
                if isinstance(item, dict)
                and (url := str(item.get("url") or "").strip()) in document_ids_by_url
            )
        )
        questions.append(
            PublicQuestion(
                id=f"multihop-q{index:04d}-{hashlib.sha256(query.encode()).hexdigest()[:8]}",
                query=query,
                question_type=str(row.get("question_type") or "unknown"),
                answer=str(row.get("answer") or ""),
                expected_document_ids=expected,
            )
        )
    return MultiHopArtifact(
        manifest=BenchmarkManifest(
            benchmark="MultiHop-RAG",
            dataset_id=MULTIHOP_DATASET_ID,
            revision=revision,
            license="ODC-BY-1.0",
            source_url=f"https://huggingface.co/datasets/{quote(MULTIHOP_DATASET_ID, safe='/')}",
            fetched_at=fetched_at or datetime.now(UTC),
            configs=["corpus", "MultiHopRAG"],
            splits=["train"],
        ),
        documents=documents,
        questions=questions,
    )


def download_multihop_artifact(client: HuggingFaceDatasetClient) -> MultiHopArtifact:
    revision = client.revision(MULTIHOP_DATASET_ID)
    corpus = client.rows(MULTIHOP_DATASET_ID, "corpus", "train")
    questions = client.rows(MULTIHOP_DATASET_ID, "MultiHopRAG", "train")
    if client.revision(MULTIHOP_DATASET_ID) != revision:
        raise ValueError("multihop_dataset_changed_during_download")
    return adapt_multihop_rows(corpus, questions, revision=revision)


def load_or_download_multihop(
    cache_path: Path,
    *,
    allow_network: bool,
    client: HuggingFaceDatasetClient | None = None,
) -> MultiHopArtifact:
    if cache_path.exists():
        return MultiHopArtifact.model_validate_json(cache_path.read_text(encoding="utf-8"))
    if not allow_network:
        raise ValueError("public_benchmark_download_requires_allow_network")
    artifact = download_multihop_artifact(client or HuggingFaceDatasetClient())
    _atomic_json(artifact, cache_path)
    return artifact


def _select_questions(
    questions: list[PublicQuestion], sample_size: int, seed: str
) -> list[PublicQuestion]:
    answerable = [question for question in questions if question.expected_document_ids]
    if sample_size <= 0 or sample_size >= len(answerable):
        return answerable
    groups: dict[str, list[PublicQuestion]] = defaultdict(list)
    for question in answerable:
        groups[question.question_type].append(question)
    for group in groups.values():
        group.sort(
            key=lambda item: hashlib.sha256(f"{seed}:{item.id}".encode()).hexdigest()
        )
    selected: list[PublicQuestion] = []
    ordered_types = sorted(groups)
    while len(selected) < sample_size and any(groups.values()):
        for question_type in ordered_types:
            if groups[question_type] and len(selected) < sample_size:
                selected.append(groups[question_type].pop(0))
    return selected


def _percentile(values: list[float], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1)
    return max(1, round(ordered[index]))


def _mean(values: list[float]) -> float:
    return round(statistics.fmean(values), 4) if values else 0.0


def _lexical_tokens(value: str) -> list[str]:
    normalized = value.casefold()
    latin = re.findall(r"[a-z0-9][a-z0-9._+-]*", normalized)
    cjk_runs = re.findall(r"[\u3400-\u9fff]+", normalized)
    cjk = [
        run[index : index + 2]
        for run in cjk_runs
        for index in range(max(1, len(run) - 1))
    ]
    return latin + cjk


class Bm25Index:
    def __init__(self, documents: Sequence[str]) -> None:
        self.term_frequencies: list[dict[str, int]] = []
        self.document_lengths: list[int] = []
        document_frequency: dict[str, int] = defaultdict(int)
        for document in documents:
            frequencies: dict[str, int] = defaultdict(int)
            for token in _lexical_tokens(document):
                frequencies[token] += 1
            self.term_frequencies.append(dict(frequencies))
            length = sum(frequencies.values())
            self.document_lengths.append(length)
            for token in frequencies:
                document_frequency[token] += 1
        self.document_frequency = dict(document_frequency)
        self.average_document_length = (
            statistics.fmean(self.document_lengths) if self.document_lengths else 0.0
        )

    def scores(self, query: str, *, k1: float = 1.5, b: float = 0.75) -> list[float]:
        query_tokens = set(_lexical_tokens(query))
        document_count = len(self.term_frequencies)
        scores = [0.0] * document_count
        if not query_tokens or not document_count or not self.average_document_length:
            return scores
        for document_index, frequencies in enumerate(self.term_frequencies):
            length_ratio = self.document_lengths[document_index] / self.average_document_length
            score = 0.0
            for token in query_tokens:
                frequency = frequencies.get(token, 0)
                if not frequency:
                    continue
                document_frequency = self.document_frequency[token]
                inverse_frequency = math.log(
                    1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5)
                )
                score += inverse_frequency * (
                    frequency * (k1 + 1)
                    / (frequency + k1 * (1 - b + b * length_ratio))
                )
            scores[document_index] = score
        return scores


def _rank_indexes(scores: Sequence[float]) -> list[int]:
    return sorted(range(len(scores)), key=lambda index: (-scores[index], index))


def _hybrid_rrf(dense_scores: Sequence[float], lexical_scores: Sequence[float]) -> list[int]:
    dense_rank = {index: rank for rank, index in enumerate(_rank_indexes(dense_scores), start=1)}
    lexical_rank = {
        index: rank for rank, index in enumerate(_rank_indexes(lexical_scores), start=1)
    }
    return sorted(
        range(len(dense_scores)),
        key=lambda index: (
            -(1 / (60 + dense_rank[index]) + 1 / (60 + lexical_rank[index])),
            index,
        ),
    )


def evaluate_multihop_retrieval(
    artifact: MultiHopArtifact,
    embedder: EmbeddingProvider,
    *,
    sample_size: int = 120,
    seed: str = "newseviday-public-v1",
    maximum_document_chars: int = 12_000,
    retrieval_mode: RetrievalMode = "article_dense_hashing",
    now: datetime | None = None,
) -> PublicRetrievalReport:
    if maximum_document_chars < 1_000:
        raise ValueError("maximum_document_chars_must_be_at_least_1000")
    selected = _select_questions(artifact.questions, sample_size, seed)
    document_texts = [document.text[:maximum_document_chars] for document in artifact.documents]
    document_vectors = (
        embedder.embed(document_texts) if retrieval_mode != "bm25" else []
    )
    lexical_index = Bm25Index(document_texts) if retrieval_mode != "article_dense_hashing" else None
    recalls5: list[float] = []
    recalls10: list[float] = []
    hits5: list[float] = []
    reciprocal_ranks: list[float] = []
    ndcgs: list[float] = []
    latencies: list[float] = []
    type_recalls: dict[str, list[float]] = defaultdict(list)
    type_hits: dict[str, list[float]] = defaultdict(list)
    for question in selected:
        started = time.perf_counter()
        query_vector = (
            embedder.embed([question.query])[0] if retrieval_mode != "bm25" else []
        )
        dense_scores = [
            cosine_similarity(query_vector, vector) for vector in document_vectors
        ]
        lexical_scores = lexical_index.scores(question.query) if lexical_index else []
        if retrieval_mode == "article_dense_hashing":
            ranked_indexes = _rank_indexes(dense_scores)
        elif retrieval_mode == "bm25":
            ranked_indexes = _rank_indexes(lexical_scores)
        else:
            ranked_indexes = _hybrid_rrf(dense_scores, lexical_scores)
        ranked_ids = [artifact.documents[index].id for index in ranked_indexes[:10]]
        latencies.append((time.perf_counter() - started) * 1_000)
        relevant = set(question.expected_document_ids)
        hit5 = relevant & set(ranked_ids[:5])
        hit10 = relevant & set(ranked_ids[:10])
        recall5 = len(hit5) / len(relevant)
        recall10 = len(hit10) / len(relevant)
        hit = float(bool(hit5))
        recalls5.append(recall5)
        recalls10.append(recall10)
        hits5.append(hit)
        type_recalls[question.question_type].append(recall5)
        type_hits[question.question_type].append(hit)
        first_rank = next(
            (rank for rank, item_id in enumerate(ranked_ids, start=1) if item_id in relevant),
            None,
        )
        reciprocal_ranks.append(1 / first_rank if first_rank else 0.0)
        dcg = sum(
            1 / math.log2(rank + 1)
            for rank, item_id in enumerate(ranked_ids, start=1)
            if item_id in relevant
        )
        ideal = sum(
            1 / math.log2(rank + 1) for rank in range(1, min(len(relevant), 10) + 1)
        )
        ndcgs.append(dcg / ideal if ideal else 0.0)
    generated_at = now or datetime.now(UTC)
    null_count = sum(not question.expected_document_ids for question in artifact.questions)
    return PublicRetrievalReport(
        run_id=f"public-eval-{generated_at.strftime('%Y%m%d%H%M%S')}",
        generated_at=generated_at,
        benchmark=artifact.manifest.benchmark,
        dataset_id=artifact.manifest.dataset_id,
        dataset_revision=artifact.manifest.revision,
        license=artifact.manifest.license,
        retrieval_mode=retrieval_mode,
        embedding_model=embedder.model if retrieval_mode != "bm25" else "none",
        corpus_document_count=len(artifact.documents),
        benchmark_question_count=len(artifact.questions),
        evaluated_question_count=len(selected),
        excluded_null_question_count=null_count,
        seed=seed,
        metrics=PublicRetrievalMetrics(
            recall_at5=_mean(recalls5),
            recall_at10=_mean(recalls10),
            hit_at5=_mean(hits5),
            mrr=_mean(reciprocal_ranks),
            ndcg_at10=_mean(ndcgs),
            p50_latency_ms=_percentile(latencies, 0.5),
            p95_latency_ms=_percentile(latencies, 0.95),
        ),
        by_question_type=[
            QuestionTypeResult(
                question_type=question_type,
                sample_count=len(type_recalls[question_type]),
                recall_at5=_mean(type_recalls[question_type]),
                hit_at5=_mean(type_hits[question_type]),
            )
            for question_type in sorted(type_recalls)
        ],
        note=(
            "MultiHop-RAG 用于检验跨文档检索迁移能力；本报告是 NewsEviday 当前"
            f"{retrieval_mode} 检索结果，不等同于内部中文生产集，也不作为上线的唯一 Gate。"
        ),
    )


def fetch_ragbench_reference(
    client: HuggingFaceDatasetClient,
    *,
    config: str = "techqa",
    split: str = "test",
    sample_size: int = 100,
) -> RagBenchReferenceReport:
    revision = client.revision(RAGBENCH_DATASET_ID)
    rows = client.rows(RAGBENCH_DATASET_ID, config, split)
    if client.revision(RAGBENCH_DATASET_ID) != revision:
        raise ValueError("ragbench_dataset_changed_during_download")
    selected = sorted(
        rows,
        key=lambda row: hashlib.sha256(str(row.get("id") or "").encode()).hexdigest(),
    )[:sample_size]
    adherence = [float(bool(row.get("adherence_score"))) for row in selected]
    relevance = [float(row.get("relevance_score") or 0.0) for row in selected]
    utilization = [float(row.get("utilization_score") or 0.0) for row in selected]
    completeness = [float(row.get("completeness_score") or 0.0) for row in selected]
    sentence_labeled = sum(
        isinstance(row.get("sentence_support_information"), list)
        and bool(row.get("response_sentences"))
        for row in selected
    )
    return RagBenchReferenceReport(
        generated_at=datetime.now(UTC),
        dataset_id=RAGBENCH_DATASET_ID,
        dataset_revision=revision,
        license="CC-BY-4.0",
        config=config,
        split=split,
        sample_count=len(selected),
        adherence_positive_rate=_mean(adherence),
        average_relevance_score=_mean(relevance),
        average_utilization_score=_mean(utilization),
        average_completeness_score=_mean(completeness),
        sentence_label_coverage=round(sentence_labeled / len(selected), 4) if selected else 0.0,
        purpose=(
            "用于校准回答忠实度、相关性、证据利用率和完整性评测字段；"
            "这些标签不是 NewsEviday 模型成绩。"
        ),
    )


def write_public_report(report: ContractModel, output: Path) -> None:
    _atomic_json(report, output)
