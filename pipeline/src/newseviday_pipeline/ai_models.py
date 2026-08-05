from pydantic import Field

from newseviday_pipeline.models import ContractModel


class ArticleEnrichment(ContractModel):
    title_zh: str = Field(min_length=2, max_length=160)
    summary_zh: str = Field(min_length=20, max_length=320)
    why_it_matters: str = Field(min_length=10, max_length=180)
    key_points: list[str] = Field(min_length=2, max_length=5)
    topic_ids: list[str] = Field(default_factory=list, max_length=6)


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
