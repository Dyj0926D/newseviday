import re
from typing import Literal

from pydantic import Field

from newseviday_pipeline.embeddings import EmbeddingProvider
from newseviday_pipeline.models import ContentSnapshot, ContractModel
from newseviday_pipeline.rag import DenseIndexArtifact, RetrievalMode, RetrievedChunk, retrieve

AgentRoute = Literal["single_fact", "comparison", "timeline", "policy_scope"]


class QueryPlan(ContractModel):
    agent_mode: Literal["bounded_v1"] = "bounded_v1"
    route: AgentRoute
    subqueries: list[str] = Field(min_length=1, max_length=2)
    requirements: list[str] = Field(default_factory=list)
    preflight_reason: str | None = None
    max_retrieval_rounds: int = Field(default=2, ge=1, le=2)


class EvidenceAssessment(ContractModel):
    sufficient: bool
    reason: str
    stop_reason: Literal[
        "evidence_sufficient", "evidence_insufficient", "policy_scope", "round_limit"
    ]


class AgenticRetrieval(ContractModel):
    plan: QueryPlan
    candidates: list[RetrievedChunk] = Field(default_factory=list)
    retrieval_rounds: int = Field(ge=0, le=2)
    assessment: EvidenceAssessment


POLICY_PATTERNS = (
    "处方",
    "诊断",
    "治疗方案",
    "legal advice",
    "法律意见",
    "保证.*股票",
    "股票.*保证",
    "保证.*上涨",
    "guarantee.*stock",
)

OUTSIDE_PRODUCT_PATTERNS = (
    "天气",
    "下雨",
    "weather",
    "世界杯",
    "比分",
    "赛季",
    "sports score",
)

EXPANSIONS = {
    "价格": "price pricing cost subscription",
    "订阅": "subscription pricing monthly price",
    "收购": "acquisition acquire buyer",
    "评测": "evaluation benchmark eval harness",
    "第三方": "third-party",
    "网络安全": "cybersecurity cyber evaluation incidents",
    "总体改进": "new safeguards strengthen AI model testing evaluation",
    "推理": "reasoning inference test-time scaling",
    "运行条件": "protocol reproducibility context window reasoning effort tools",
    "语义": "semantic layer semantics",
    "智能体": "agent agentic",
    "agentic harness": (
        "performance efficiency models tasks controlled variables same model same benchmark "
        "tool selection MCP servers real-world metrics online experiments"
    ),
    "agentic": "agent agentic",
    "多模态": "multimodal video vision",
    "安全": "safety guardrail moderation prompt response",
    "实时": "real-time streaming",
    "数据湖": "data lake lakehouse",
}

COMPARISON_TAIL_PATTERNS = (
    "为什么",
    "如何",
    "分别",
    "共同",
    "在解决",
    "解决",
    "有哪些",
    "是什么",
    "有什么",
)


def _expand_query(query: str) -> str:
    normalized = query.casefold()
    expansion = " ".join(value for key, value in EXPANSIONS.items() if key in normalized)
    return f"{query} {expansion}" if expansion else query


def _comparison_subqueries(question: str) -> list[str]:
    """Split explicit two-subject comparisons while retaining the shared predicate."""

    for connector in ("和", "与"):
        if connector not in question:
            continue
        left, right = question.split(connector, 1)
        tail_positions = [
            right.find(pattern) for pattern in COMPARISON_TAIL_PATTERNS if pattern in right
        ]
        if not tail_positions:
            continue
        tail_start = min(position for position in tail_positions if position >= 0)
        right_subject = right[:tail_start].strip()
        shared_tail = right[tail_start:].strip()
        if left.strip() and right_subject and shared_tail:
            return [
                _expand_query(f"{left.strip()}{shared_tail}"),
                _expand_query(f"{right_subject}{shared_tail}"),
            ]
    return []


def plan_question(question: str, snapshot: ContentSnapshot) -> QueryPlan:
    normalized = " ".join(question.casefold().split())
    if any(re.search(pattern, normalized) for pattern in POLICY_PATTERNS):
        return QueryPlan(
            route="policy_scope",
            subqueries=[question],
            preflight_reason="policy_scope",
        )
    if any(pattern in normalized for pattern in OUTSIDE_PRODUCT_PATTERNS):
        return QueryPlan(
            route="policy_scope",
            subqueries=[question],
            preflight_reason="outside_product_scope",
        )

    requirements: list[str] = []
    years = [int(value) for value in re.findall(r"\b(20\d{2})\b", normalized)]
    snapshot_year = snapshot.generated_at.year
    if years and max(years) > snapshot_year:
        requirements.append(f"future_year:{max(years)}")
    if any(term in normalized for term in ("价格", "订阅", "price", "pricing", "cost")):
        requirements.append("price")
    if any(term in normalized for term in ("收购", "acquire", "acquisition")):
        requirements.append("acquisition")
    if any(term in normalized for term in ("多少", "how many", "数量")):
        requirements.append("numeric")

    if any(term in normalized for term in ("分别", "对比", "比较", "共同", "和", "与")):
        route: AgentRoute = "comparison"
    elif any(item.startswith("future_year:") for item in requirements) or any(
        term in normalized for term in ("何时", "时间线", "最新", "when")
    ):
        route = "timeline"
    else:
        route = "single_fact"

    comparison_subqueries = _comparison_subqueries(question) if route == "comparison" else []
    if comparison_subqueries:
        subqueries = comparison_subqueries
        requirements.append(f"comparison_coverage:{len(comparison_subqueries)}")
    else:
        expanded = _expand_query(question)
        subqueries = [question]
        if expanded != question:
            subqueries.append(expanded)
    return QueryPlan(route=route, subqueries=subqueries[:2], requirements=requirements)


def assess_evidence(
    plan: QueryPlan,
    candidates: list[RetrievedChunk],
    *,
    minimum_score: float,
    round_leader_article_ids: list[str] | None = None,
) -> EvidenceAssessment:
    if plan.preflight_reason == "policy_scope":
        return EvidenceAssessment(
            sufficient=False,
            reason="policy_scope",
            stop_reason="policy_scope",
        )
    if plan.preflight_reason == "outside_product_scope":
        return EvidenceAssessment(
            sufficient=False,
            reason="outside_product_scope",
            stop_reason="evidence_insufficient",
        )
    if not candidates or candidates[0].score < minimum_score * 0.75:
        return EvidenceAssessment(
            sufficient=False,
            reason="retrieval_score_below_floor",
            stop_reason="evidence_insufficient",
        )

    evidence_text = "\n".join(item.chunk.text for item in candidates[:5]).casefold()
    future_year = next(
        (item.split(":", 1)[1] for item in plan.requirements if item.startswith("future_year:")),
        None,
    )
    if future_year and future_year not in evidence_text:
        return EvidenceAssessment(
            sufficient=False,
            reason="required_future_date_evidence_missing",
            stop_reason="evidence_insufficient",
        )
    if "price" in plan.requirements:
        has_price_language = any(
            term in evidence_text
            for term in ("price", "pricing", "cost", "subscription", "价格", "订阅", "费用")
        )
        has_price_value = bool(
            re.search(r"(?:[$¥￥]\s?\d|\d+(?:\.\d+)?\s?(?:元|美元|usd|cny))", evidence_text)
        )
        if not (has_price_language and has_price_value):
            return EvidenceAssessment(
                sufficient=False,
                reason="required_price_evidence_missing",
                stop_reason="evidence_insufficient",
            )
    if "acquisition" in plan.requirements and not any(
        term in evidence_text for term in ("acquire", "acquisition", "收购")
    ):
        return EvidenceAssessment(
            sufficient=False,
            reason="required_acquisition_evidence_missing",
            stop_reason="evidence_insufficient",
        )
    if "numeric" in plan.requirements and not re.search(r"\d", evidence_text):
        return EvidenceAssessment(
            sufficient=False,
            reason="required_numeric_evidence_missing",
            stop_reason="evidence_insufficient",
        )
    comparison_coverage = next(
        (
            int(item.split(":", 1)[1])
            for item in plan.requirements
            if item.startswith("comparison_coverage:")
        ),
        None,
    )
    if comparison_coverage is not None:
        leader_ids = round_leader_article_ids or []
        top_article_ids = {item.chunk.article_id for item in candidates[:5]}
        if len(leader_ids) < comparison_coverage or len(set(leader_ids)) < comparison_coverage:
            return EvidenceAssessment(
                sufficient=False,
                reason="comparison_subquery_coverage_missing",
                stop_reason="evidence_insufficient",
            )
        if not set(leader_ids).issubset(top_article_ids):
            return EvidenceAssessment(
                sufficient=False,
                reason="comparison_source_missing_from_context",
                stop_reason="evidence_insufficient",
            )
    return EvidenceAssessment(
        sufficient=True,
        reason="evidence_requirements_satisfied",
        stop_reason="evidence_sufficient",
    )


def _rank_with_round_leaders(
    rounds: list[list[RetrievedChunk]],
    *,
    top_k: int,
    preserve_round_leaders: bool,
) -> tuple[list[RetrievedChunk], list[str]]:
    by_chunk: dict[str, RetrievedChunk] = {}
    for candidates in rounds:
        for item in candidates:
            current = by_chunk.get(item.chunk.id)
            if current is None or item.score > current.score:
                by_chunk[item.chunk.id] = item
    ordered = sorted(by_chunk.values(), key=lambda item: (-item.score, item.chunk.id))

    leaders: list[RetrievedChunk] = []
    used_articles: set[str] = set()
    if preserve_round_leaders:
        for candidates in rounds:
            leader = next(
                (
                    item
                    for item in candidates
                    if item.chunk.article_id not in used_articles
                ),
                candidates[0] if candidates else None,
            )
            if leader is not None:
                leaders.append(leader)
                used_articles.add(leader.chunk.article_id)

    leader_ids = {item.chunk.id for item in leaders}
    fused = sorted(leaders, key=lambda item: (-item.score, item.chunk.id)) + [
        item for item in ordered if item.chunk.id not in leader_ids
    ]
    ranked = [
        item.model_copy(update={"rank": rank})
        for rank, item in enumerate(fused[:top_k], start=1)
    ]
    return ranked, [item.chunk.article_id for item in leaders]


def retrieve_with_agent(
    question: str,
    snapshot: ContentSnapshot,
    index: DenseIndexArtifact,
    embedder: EmbeddingProvider,
    *,
    top_k: int = 10,
    minimum_score: float = 0.08,
    retrieval_mode: RetrievalMode = "chunk_dense",
) -> AgenticRetrieval:
    plan = plan_question(question, snapshot)
    if plan.preflight_reason:
        assessment = assess_evidence(plan, [], minimum_score=minimum_score)
        return AgenticRetrieval(
            plan=plan,
            candidates=[],
            retrieval_rounds=0,
            assessment=assessment,
        )

    round_count = 0
    rounds: list[list[RetrievedChunk]] = []
    for subquery in plan.subqueries:
        round_count += 1
        result = retrieve(
            subquery,
            index,
            embedder,
            top_k=top_k,
            retrieval_mode=retrieval_mode,
        )
        rounds.append(result.candidates)
    ranked, round_leader_article_ids = _rank_with_round_leaders(
        rounds,
        top_k=top_k,
        preserve_round_leaders=(plan.route == "comparison" and len(plan.subqueries) > 1),
    )
    assessment = assess_evidence(
        plan,
        ranked,
        minimum_score=minimum_score,
        round_leader_article_ids=round_leader_article_ids,
    )
    return AgenticRetrieval(
        plan=plan,
        candidates=ranked,
        retrieval_rounds=round_count,
        assessment=assessment,
    )
