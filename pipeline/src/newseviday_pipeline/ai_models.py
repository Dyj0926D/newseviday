from datetime import datetime

from pydantic import Field

from newseviday_pipeline.models import ContractModel


class ArticleEnrichment(ContractModel):
    title_zh: str = Field(min_length=2, max_length=160)
    summary_zh: str = Field(min_length=20, max_length=320)
    why_it_matters: str = Field(min_length=10, max_length=180)
    key_points: list[str] = Field(min_length=2, max_length=5)
    topic_ids: list[str] = Field(default_factory=list, max_length=6)


class AiUsageReport(ContractModel):
    schema_version: str = "1.0.0"
    snapshot_id: str
    generated_at: datetime
    provider: str = "deepseek"
    model: str
    model_calls: int = Field(ge=0)
    model_call_limit: int = Field(ge=0)
    usage_reported_calls: int = Field(ge=0)
    usage_complete: bool
    cache_hits: int = Field(ge=0)
    accepted_enrichment_reuses: int = Field(ge=0)
    enriched_article_count: int = Field(ge=0)
    skipped_thin_evidence: int = Field(ge=0)
    skipped_below_quality_floor: int = Field(ge=0)
    skipped_stale: int = Field(ge=0)
    skipped_source_cap: int = Field(ge=0)
    skipped_after_call_limit: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    input_cny_per_million: float | None = Field(default=None, ge=0)
    output_cny_per_million: float | None = Field(default=None, ge=0)
    estimated_cost_cny: float | None = Field(default=None, ge=0)


class ProfileInterest(ContractModel):
    topic_id: str = Field(min_length=2, max_length=80)
    weight: int = Field(ge=1, le=5)
    reason: str = Field(min_length=2, max_length=120)


class ProfileEnhancement(ContractModel):
    role: str = Field(default="", max_length=80)
    work: str = Field(default="", max_length=200)
    goal: str = Field(default="", max_length=240)
    description: str = Field(default="", max_length=500)
    interests: list[ProfileInterest] = Field(default_factory=list, max_length=8)
    inferred_terms: list[str] = Field(default_factory=list, max_length=12)
    warnings: list[str] = Field(default_factory=list, max_length=5)
