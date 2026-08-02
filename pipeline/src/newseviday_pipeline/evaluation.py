import json
import math
import os
import statistics
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from newseviday_pipeline.embeddings import EmbeddingProvider
from newseviday_pipeline.models import ContentSnapshot, ContractModel, EvalMetrics, EvalRun
from newseviday_pipeline.rag import DenseIndexArtifact, retrieve_dense


class GoldQuestion(ContractModel):
    id: str
    question: str = Field(min_length=2, max_length=300)
    category: str
    answerable: bool = True
    expected_article_ids: list[str] = Field(default_factory=list)


class RagGoldDataset(ContractModel):
    version: str
    dataset_kind: str
    review_status: str
    corpus_snapshot_id: str
    questions: list[GoldQuestion] = Field(min_length=1)


class CorpusHealth(ContractModel):
    passed: bool
    article_count: int
    chunk_count: int
    chunk_coverage: float
    missing_expected_article_ids: list[str] = Field(default_factory=list)


class AnswerQualityStatus(ContractModel):
    citation_coverage: float | None = None
    no_answer_accuracy: float
    status: str


class PublishedEvalReport(ContractModel):
    schema_version: str = "1.0.0"
    run: EvalRun
    dataset_kind: str
    review_status: str
    corpus_health: CorpusHealth
    answer_quality: AnswerQualityStatus
    note: str


def load_gold_dataset(path: Path) -> RagGoldDataset:
    return RagGoldDataset.model_validate_json(path.read_text(encoding="utf-8"))


def corpus_health(
    snapshot: ContentSnapshot,
    index: DenseIndexArtifact,
    dataset: RagGoldDataset,
) -> CorpusHealth:
    article_ids = {article.id for article in snapshot.articles}
    chunked_ids = {record.chunk.article_id for record in index.records}
    expected_ids = {
        article_id
        for question in dataset.questions
        for article_id in question.expected_article_ids
    }
    missing = sorted(expected_ids - article_ids)
    coverage = len(article_ids & chunked_ids) / len(article_ids) if article_ids else 0.0
    return CorpusHealth(
        passed=(
            dataset.corpus_snapshot_id == snapshot.snapshot_id
            and not missing
            and coverage >= 0.95
        ),
        article_count=len(article_ids),
        chunk_count=len(index.records),
        chunk_coverage=round(coverage, 4),
        missing_expected_article_ids=missing,
    )


def _percentile(values: list[float], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1)
    return max(1, round(ordered[index]))


def _ndcg(retrieved: list[str], relevant: set[str], limit: int = 10) -> float:
    if not relevant:
        return 0.0
    dcg = sum(
        1 / math.log2(rank + 1)
        for rank, article_id in enumerate(retrieved[:limit], start=1)
        if article_id in relevant
    )
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(len(relevant), limit) + 1))
    return dcg / ideal if ideal else 0.0


def evaluate_rag(
    snapshot: ContentSnapshot,
    index: DenseIndexArtifact,
    dataset: RagGoldDataset,
    embedder: EmbeddingProvider,
    *,
    minimum_score: float = 0.08,
    now: datetime | None = None,
) -> PublishedEvalReport:
    health = corpus_health(snapshot, index, dataset)
    recalls5: list[float] = []
    recalls10: list[float] = []
    reciprocal_ranks: list[float] = []
    ndcgs: list[float] = []
    hits5: list[float] = []
    latencies: list[float] = []
    no_answer_results: list[float] = []

    for question in dataset.questions:
        started = time.perf_counter()
        result = retrieve_dense(question.question, index, embedder, top_k=10)
        latencies.append((time.perf_counter() - started) * 1_000)
        ranked_articles = list(dict.fromkeys(item.chunk.article_id for item in result.candidates))
        if not question.answerable:
            top_score = result.candidates[0].score if result.candidates else -1.0
            no_answer_results.append(float(top_score < minimum_score))
            continue

        relevant = set(question.expected_article_ids)
        hits_at5 = relevant & set(ranked_articles[:5])
        hits_at10 = relevant & set(ranked_articles[:10])
        recalls5.append(len(hits_at5) / len(relevant) if relevant else 0.0)
        recalls10.append(len(hits_at10) / len(relevant) if relevant else 0.0)
        hits5.append(float(bool(hits_at5)))
        first_rank = next(
            (
                rank
                for rank, article_id in enumerate(ranked_articles, start=1)
                if article_id in relevant
            ),
            None,
        )
        reciprocal_ranks.append(1 / first_rank if first_rank else 0.0)
        ndcgs.append(_ndcg(ranked_articles, relevant))

    metrics = EvalMetrics(
        recall_at5=round(statistics.fmean(recalls5), 4),
        recall_at10=round(statistics.fmean(recalls10), 4),
        mrr=round(statistics.fmean(reciprocal_ranks), 4),
        ndcg_at10=round(statistics.fmean(ndcgs), 4),
        hit_at5=round(statistics.fmean(hits5), 4),
        p50_latency_ms=_percentile(latencies, 0.5),
        p95_latency_ms=_percentile(latencies, 0.95),
    )
    production_gate_passed = (
        health.passed
        and metrics.recall_at5 >= 0.75
        and metrics.hit_at5 >= 0.85
        and metrics.p95_latency_ms <= 4_000
    )
    gate: Literal["pass", "fail", "observe"] = (
        "observe"
        if dataset.dataset_kind == "demo"
        else ("pass" if production_gate_passed else "fail")
    )
    created_at = now or datetime.now(UTC)
    run = EvalRun(
        id=f"eval-{created_at.strftime('%Y%m%d%H%M%S')}",
        created_at=created_at,
        dataset_version=dataset.version,
        retrieval_mode="chunk_dense",
        sample_count=len(dataset.questions),
        metrics=metrics,
        gate=gate,
        dataset_kind="demo" if dataset.dataset_kind == "demo" else "production",
        corpus_snapshot_id=snapshot.snapshot_id,
        embedding_model=embedder.model,
    )
    return PublishedEvalReport(
        run=run,
        dataset_kind=dataset.dataset_kind,
        review_status=dataset.review_status,
        corpus_health=health,
        answer_quality=AnswerQualityStatus(
            citation_coverage=None,
            no_answer_accuracy=round(statistics.fmean(no_answer_results), 4)
            if no_answer_results
            else 0.0,
            status="pending_generated_answer_review",
        ),
        note=(
            "Demo 快照上的工程基线，仅用于验证评测链路。黄金题尚待人工复核，"
            "回答引用覆盖率尚未评测，不构成生产发布结论。"
        ),
    )


def write_eval_report(report: PublishedEvalReport, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=output.parent, prefix="eval-", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                report.model_dump(mode="json", by_alias=True),
                stream,
                ensure_ascii=False,
                indent=2,
            )
            stream.write("\n")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
