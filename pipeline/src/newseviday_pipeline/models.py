from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
SourceType = Literal[
    "official",
    "academic",
    "research_institute",
    "professional_media",
    "independent_author",
]
EvidenceTier = Literal["primary", "secondary", "opinion"]


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ContractModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class FeatureFlags(ContractModel):
    ingestion_enabled: bool = False
    ai_summary_enabled: bool = False
    rag_enabled: bool = False
    trend_brief_enabled: bool = False


class Limits(ContractModel):
    daily_questions_per_ip: int = Field(default=3, ge=0, le=100)
    monthly_budget_cny: int = Field(default=35, ge=0, le=50)
    hard_budget_cny: int = Field(default=50, ge=0, le=50)


class RuntimeConfig(ContractModel):
    version: int = 1
    mode: Literal["archive", "warmup", "interview"] = "archive"
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    limits: Limits = Field(default_factory=Limits)


class SourceConfig(ContractModel):
    id: str = Field(min_length=2, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1)
    adapter: Literal["atom", "rss", "json", "html"]
    url: HttpUrl
    homepage_url: HttpUrl | None = None
    language: str = Field(min_length=2, max_length=8)
    region: str = Field(min_length=2)
    enabled: bool = False
    usage_scope: str = Field(min_length=2)
    source_type: SourceType = "official"
    evidence_tier: EvidenceTier = "primary"
    note: str | None = None
    max_items: int = Field(default=12, ge=1, le=50)
    max_selected_items: int = Field(default=8, ge=1, le=12)
    max_summary_chars: int = Field(default=2_500, ge=120, le=2_500)
    request_timeout_seconds: int = Field(default=15, ge=3, le=30)
    include_url_patterns: list[str] = Field(default_factory=list, max_length=8)
    exclude_url_patterns: list[str] = Field(default_factory=list, max_length=8)
    title_class_patterns: list[str] = Field(default_factory=list, max_length=8)
    heading_tags: list[Literal["h2", "h3", "h4"]] = Field(default_factory=list, max_length=3)
    html_card_mode: bool = False
    require_published_at: bool = False
    require_summary: bool = False


class SourcesConfig(ContractModel):
    version: int = 1
    sources: list[SourceConfig] = Field(default_factory=list)


class TopicConfig(ContractModel):
    id: str = Field(min_length=2, pattern=r"^[a-z0-9-]+$")
    label: str = Field(min_length=1)
    weight: float = Field(default=1.0, ge=0, le=2)
    keywords: list[str] = Field(min_length=1)


class TopicsConfig(ContractModel):
    version: int = 1
    default_profile: str = "general"
    topics: list[TopicConfig] = Field(default_factory=list)


class Source(ContractModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    id: str
    name: str
    kind: Literal["atom", "rss", "json", "html", "manual"]
    homepage_url: str
    feed_url: str | None = None
    language: str
    region: str
    active: bool
    usage_scope: str
    source_type: SourceType = "official"
    evidence_tier: EvidenceTier = "primary"


class RawFeedItem(ContractModel):
    source_id: str
    url: str
    title: str
    summary: str | None = None
    authors: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    language: str
    content_html: str | None = None
    preserve_fragment: bool = False
    source_type: SourceType = "official"
    evidence_tier: EvidenceTier = "primary"


class ArticleFacts(ContractModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None


class GeneratedText(ContractModel):
    title_zh: str | None = None
    summary_zh: str | None = None
    why_it_matters: str | None = None
    key_points: list[str] = Field(default_factory=list)
    provider: Literal["deepseek", "editorial"] = "deepseek"
    model: str
    prompt_version: str
    generated_at: datetime


class ContentScoreBreakdown(ContractModel):
    target_relevance: float = Field(ge=0, le=1)
    technical_advancement: float = Field(ge=0, le=1)
    engineering_applicability: float = Field(ge=0, le=1)
    technical_generality: float = Field(ge=0, le=1)
    product_industry_impact: float = Field(ge=0, le=1)
    freshness: float = Field(ge=0, le=1)
    evidence_maturity: float = Field(ge=0, le=1)
    completeness: float = Field(ge=0, le=1)


class KeySignalAssessment(ContractModel):
    eligible: bool
    score: float = Field(ge=0, le=1)
    user_value: float = Field(ge=0, le=1)
    change_magnitude: float = Field(ge=0, le=1)
    actionability: float = Field(ge=0, le=1)
    generality: float = Field(ge=0, le=1)
    freshness: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list, max_length=5)
    gate_failures: list[str] = Field(default_factory=list, max_length=8)


class Article(ContractModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    id: str
    source_id: str
    source_type: SourceType = "official"
    evidence_tier: EvidenceTier = "primary"
    canonical_url: str
    language: str
    published_at: datetime | None = None
    collected_at: datetime
    facts: ArticleFacts
    ai: GeneratedText | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    topic_scores: dict[str, float] = Field(default_factory=dict)
    content_score: float | None = Field(default=None, ge=0, le=1)
    content_score_breakdown: ContentScoreBreakdown | None = None
    selection_reasons: list[str] = Field(default_factory=list, max_length=5)
    key_signal: KeySignalAssessment | None = None
    content_hash: str


class Evidence(ContractModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    id: str
    article_id: str
    source_id: str
    url: str
    excerpt: str
    retrieved_at: datetime


class Chunk(ContractModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    id: str
    article_id: str
    position: int = Field(ge=0)
    text: str
    language: str
    token_estimate: int = Field(ge=0)
    content_hash: str


class BriefSection(ContractModel):
    heading: str
    body: str
    evidence_ids: list[str] = Field(default_factory=list)


class Brief(ContractModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    id: str
    title: str
    period_start: datetime
    period_end: datetime
    sections: list[BriefSection] = Field(default_factory=list)
    generated_by: GeneratedText | None = None
    published_at: datetime


PipelineStageName = Literal[
    "fetch",
    "extract",
    "normalize",
    "exact_dedup",
    "fuzzy_dedup",
    "select",
    "ai_enrich",
    "chunk",
    "index",
    "eval",
    "snapshot",
]


class PipelineStageResult(ContractModel):
    stage: PipelineStageName
    status: Literal["succeeded", "skipped", "failed"]
    input_count: int = Field(ge=0)
    output_count: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    reason: str | None = None


class SourceRunOutcome(ContractModel):
    source_id: str
    fetch_status: Literal["succeeded", "failed"]
    parse_status: Literal["succeeded", "failed", "skipped"]
    item_count: int = Field(default=0, ge=0)
    selected_count: int = Field(default=0, ge=0)
    final_url: str | None = None
    error_code: str | None = None


class PipelineRun(ContractModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: Literal["running", "succeeded", "failed"]
    config_version: int
    source_ids: list[str] = Field(default_factory=list)
    source_outcomes: list[SourceRunOutcome] = Field(default_factory=list)
    stages: list[PipelineStageResult] = Field(default_factory=list)
    error_code: str | None = None


class RagCandidate(ContractModel):
    chunk_id: str
    rank: int = Field(ge=1)
    score: float


class RagTrace(ContractModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    id: str
    created_at: datetime
    query_fingerprint: str
    retrieval_mode: Literal["chunk_dense", "article_dense", "hybrid_rerank"]
    ranked_candidates: list[RagCandidate] = Field(default_factory=list)
    injected_chunk_ids: list[str] = Field(default_factory=list)
    answer_id: str | None = None
    fallback_reason: str | None = None
    agent_mode: Literal["bounded_v1"] | None = None
    route: Literal["single_fact", "comparison", "timeline", "policy_scope"] | None = None
    retrieval_rounds: int | None = Field(default=None, ge=0, le=2)
    sufficiency_reason: str | None = None
    stop_reason: (
        Literal["evidence_sufficient", "evidence_insufficient", "policy_scope", "round_limit"]
        | None
    ) = None
    latency_ms: int = Field(ge=0)


class EvalMetrics(ContractModel):
    recall_at5: float = Field(ge=0, le=1)
    recall_at10: float = Field(ge=0, le=1)
    mrr: float = Field(ge=0, le=1)
    ndcg_at10: float = Field(ge=0, le=1)
    hit_at5: float = Field(ge=0, le=1)
    p50_latency_ms: int = Field(ge=0)
    p95_latency_ms: int = Field(ge=0)


class EvalRun(ContractModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    id: str
    created_at: datetime
    dataset_version: str
    retrieval_mode: Literal["chunk_dense", "article_dense", "hybrid_rerank"]
    sample_count: int = Field(ge=1)
    metrics: EvalMetrics
    gate: Literal["pass", "fail", "observe"]
    dataset_kind: Literal["demo", "production"] = "production"
    corpus_snapshot_id: str | None = None
    embedding_model: str | None = None


class RuntimeContractFeatures(ContractModel):
    ingestion: bool = False
    ai_summary: bool = False
    rag: bool = False
    trend_brief: bool = False


class RuntimeContractLimits(ContractModel):
    daily_questions_per_ip: int = Field(default=3, ge=0, le=100)
    monthly_budget_cny: int = Field(default=35, ge=0, le=50)
    hard_budget_cny: int = Field(default=50, ge=0, le=50)
    request_body_bytes: int = Field(default=32768, ge=1024, le=131072)
    upstream_timeout_ms: int = Field(default=20000, ge=1000, le=60000)


class RuntimeContractAi(ContractModel):
    enabled: bool = False
    provider: Literal["deepseek"] = "deepseek"
    model: str | None = None


class RuntimeContract(ContractModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    version: int = Field(default=1, ge=1)
    mode: Literal["archive", "warmup", "interview"] = "archive"
    features: RuntimeContractFeatures = Field(default_factory=RuntimeContractFeatures)
    limits: RuntimeContractLimits = Field(default_factory=RuntimeContractLimits)
    ai: RuntimeContractAi = Field(default_factory=RuntimeContractAi)


class SnapshotTopic(ContractModel):
    id: str
    label: str


class ContentSnapshot(ContractModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    snapshot_id: str
    generated_at: datetime
    pipeline_run_id: str
    state: Literal["empty", "ready", "stale"]
    snapshot_kind: Literal["demo", "production"] = "production"
    source_count: int = Field(ge=0)
    sources: list[Source] = Field(default_factory=list)
    topics: list[SnapshotTopic] = Field(default_factory=list)
    articles: list[Article] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    briefs: list[Brief] = Field(default_factory=list)
