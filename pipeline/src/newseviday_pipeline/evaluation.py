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

from newseviday_pipeline.agentic import retrieve_with_agent
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
    low_score_refusal_accuracy: float
    answerable_pass_rate: float
    agent_mode: str
    average_retrieval_rounds: float
    status: str


class PublishedEvalReport(ContractModel):
    schema_version: str = "1.0.0"
    run: EvalRun
    dataset_kind: str
    review_status: str
    corpus_health: CorpusHealth
    answer_quality: AnswerQualityStatus
    note: str


class RagReviewCandidate(ContractModel):
    article_id: str
    article_title: str
    chunk_id: str
    rank: int = Field(ge=1)
    score: float
    excerpt: str


class RagHumanReviewFields(ContractModel):
    retrieval_evidence_correct: bool | None = None
    answerability_decision_correct: bool | None = None
    citation_supports_answer: bool | None = None
    notes: str | None = None


class RagReviewCase(ContractModel):
    id: str
    question: str
    category: str
    answerable: bool
    expected_article_ids: list[str]
    route: str
    retrieval_rounds: int
    evidence_sufficient: bool
    assessment_reason: str
    stop_reason: str
    candidates: list[RagReviewCandidate]
    human_review: RagHumanReviewFields = Field(default_factory=RagHumanReviewFields)


class RagReviewPacket(ContractModel):
    schema_version: str = "1.0.0"
    dataset_version: str
    corpus_snapshot_id: str
    generated_at: datetime
    minimum_score: float
    review_status: str = "pending_human_review"
    instructions: list[str]
    cases: list[RagReviewCase]


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
    low_score_no_answer_results: list[float] = []
    answerable_gate_results: list[float] = []
    retrieval_rounds: list[int] = []

    for question in dataset.questions:
        started = time.perf_counter()
        result = retrieve_dense(question.question, index, embedder, top_k=10)
        agentic = retrieve_with_agent(
            question.question,
            snapshot,
            index,
            embedder,
            top_k=10,
            minimum_score=minimum_score,
        )
        retrieval_rounds.append(agentic.retrieval_rounds)
        latencies.append((time.perf_counter() - started) * 1_000)
        ranked_articles = list(dict.fromkeys(item.chunk.article_id for item in result.candidates))
        if not question.answerable:
            top_score = result.candidates[0].score if result.candidates else -1.0
            low_score_no_answer_results.append(float(top_score < minimum_score))
            no_answer_results.append(float(not agentic.assessment.sufficient))
            continue

        answerable_gate_results.append(float(agentic.assessment.sufficient))

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


    no_answer_accuracy = (
        round(statistics.fmean(no_answer_results), 4) if no_answer_results else 0.0
    )
    low_score_refusal_accuracy = (
        round(statistics.fmean(low_score_no_answer_results), 4)
        if low_score_no_answer_results
        else 0.0
    )
    answerable_pass_rate = (
        round(statistics.fmean(answerable_gate_results), 4) if answerable_gate_results else 0.0
    )
    production_gate_passed = (
        health.passed
        and metrics.recall_at5 >= 0.75
        and metrics.hit_at5 >= 0.85
        and metrics.p95_latency_ms <= 4_000
        and no_answer_accuracy >= 0.8
        and answerable_pass_rate >= 0.9
        and dataset.review_status == "human_reviewed"
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
            no_answer_accuracy=no_answer_accuracy,
            low_score_refusal_accuracy=low_score_refusal_accuracy,
            answerable_pass_rate=answerable_pass_rate,
            agent_mode="bounded_v1",
            average_retrieval_rounds=round(statistics.fmean(retrieval_rounds), 2),
            status="pending_generated_answer_review",
        ),
        note=(
            "当前结果来自小规模验证集。无答案识别已由单一阈值升级为有限步骤的"
            "证据充分性门禁；黄金题和生成回答仍待人工复核，因此暂不作为正式发布结论。"
        ),
    )


def build_rag_review_packet(
    snapshot: ContentSnapshot,
    index: DenseIndexArtifact,
    dataset: RagGoldDataset,
    embedder: EmbeddingProvider,
    *,
    minimum_score: float = 0.08,
    now: datetime | None = None,
) -> RagReviewPacket:
    """Export per-question evidence and blank human labels without model answers."""

    articles_by_id = {article.id: article for article in snapshot.articles}
    cases: list[RagReviewCase] = []
    for question in dataset.questions:
        agentic = retrieve_with_agent(
            question.question,
            snapshot,
            index,
            embedder,
            top_k=10,
            minimum_score=minimum_score,
        )
        candidates = []
        for item in agentic.candidates[:5]:
            article = articles_by_id.get(item.chunk.article_id)
            candidates.append(
                RagReviewCandidate(
                    article_id=item.chunk.article_id,
                    article_title=(article.facts.title if article is not None else ""),
                    chunk_id=item.chunk.id,
                    rank=item.rank,
                    score=item.score,
                    excerpt=item.chunk.text[:320],
                )
            )
        cases.append(
            RagReviewCase(
                id=question.id,
                question=question.question,
                category=question.category,
                answerable=question.answerable,
                expected_article_ids=question.expected_article_ids,
                route=agentic.plan.route,
                retrieval_rounds=agentic.retrieval_rounds,
                evidence_sufficient=agentic.assessment.sufficient,
                assessment_reason=agentic.assessment.reason,
                stop_reason=agentic.assessment.stop_reason,
                candidates=candidates,
            )
        )
    return RagReviewPacket(
        dataset_version=dataset.version,
        corpus_snapshot_id=snapshot.snapshot_id,
        generated_at=now or datetime.now(UTC),
        minimum_score=minimum_score,
        instructions=[
            "核对 expectedArticleIds 是否完整且确实能够回答问题。",
            "核对前五条候选是否包含正确证据，并填写 retrievalEvidenceCorrect。",
            "核对 evidenceSufficient 的回答或拒答判断，并填写 answerabilityDecisionCorrect。",
            "生成回答开放后再核对逐条引用，并填写 citationSupportsAnswer。",
        ],
        cases=cases,
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


def write_rag_review_packet(packet: RagReviewPacket, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=output.parent, prefix="rag-review-", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                packet.model_dump(mode="json", by_alias=True),
                stream,
                ensure_ascii=False,
                indent=2,
            )
            stream.write("\n")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
