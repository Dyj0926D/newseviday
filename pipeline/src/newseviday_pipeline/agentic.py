import re
from typing import Literal

from pydantic import Field

from newseviday_pipeline.embeddings import EmbeddingProvider
from newseviday_pipeline.models import ContentSnapshot, ContractModel
from newseviday_pipeline.rag import DenseIndexArtifact, RetrievedChunk, retrieve_dense

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
    "语义": "semantic layer semantics",
    "智能体": "agent agentic",
    "数据湖": "data lake lakehouse",
}


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

    expansion = " ".join(value for key, value in EXPANSIONS.items() if key in normalized)
    subqueries = [question]
    if expansion:
        subqueries.append(f"{question} {expansion}")
    return QueryPlan(route=route, subqueries=subqueries[:2], requirements=requirements)


def assess_evidence(
    plan: QueryPlan,
    candidates: list[RetrievedChunk],
    *,
    minimum_score: float,
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
    return EvidenceAssessment(
        sufficient=True,
        reason="evidence_requirements_satisfied",
        stop_reason="evidence_sufficient",
    )


def retrieve_with_agent(
    question: str,
    snapshot: ContentSnapshot,
    index: DenseIndexArtifact,
    embedder: EmbeddingProvider,
    *,
    top_k: int = 10,
    minimum_score: float = 0.08,
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

    by_chunk: dict[str, RetrievedChunk] = {}
    round_count = 0
    for subquery in plan.subqueries:
        round_count += 1
        result = retrieve_dense(subquery, index, embedder, top_k=top_k)
        for item in result.candidates:
            current = by_chunk.get(item.chunk.id)
            if current is None or item.score > current.score:
                by_chunk[item.chunk.id] = item
    ordered = sorted(by_chunk.values(), key=lambda item: (-item.score, item.chunk.id))[:top_k]
    ranked = [item.model_copy(update={"rank": rank}) for rank, item in enumerate(ordered, start=1)]
    assessment = assess_evidence(plan, ranked, minimum_score=minimum_score)
    return AgenticRetrieval(
        plan=plan,
        candidates=ranked,
        retrieval_rounds=round_count,
        assessment=assessment,
    )
