from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class FeatureFlags(BaseModel):
    ingestion_enabled: bool = False
    ai_summary_enabled: bool = False
    rag_enabled: bool = False
    trend_brief_enabled: bool = False


class Limits(BaseModel):
    daily_questions_per_ip: int = Field(default=3, ge=0, le=100)
    monthly_budget_cny: int = Field(default=35, ge=0, le=50)
    hard_budget_cny: int = Field(default=50, ge=0, le=50)


class RuntimeConfig(BaseModel):
    version: int = 1
    mode: Literal["archive", "warmup", "interview"] = "archive"
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    limits: Limits = Field(default_factory=Limits)


class SourceConfig(BaseModel):
    id: str = Field(min_length=2, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1)
    adapter: Literal["atom", "rss", "json", "html"]
    url: HttpUrl
    language: str = Field(min_length=2, max_length=8)
    region: str = Field(min_length=2)
    enabled: bool = False
    usage_scope: str = Field(min_length=2)
    note: str | None = None


class SourcesConfig(BaseModel):
    version: int = 1
    sources: list[SourceConfig] = Field(default_factory=list)


class TopicConfig(BaseModel):
    id: str = Field(min_length=2, pattern=r"^[a-z0-9-]+$")
    label: str = Field(min_length=1)
    weight: float = Field(default=1.0, ge=0, le=2)
    keywords: list[str] = Field(min_length=1)


class TopicsConfig(BaseModel):
    version: int = 1
    default_profile: str = "general"
    topics: list[TopicConfig] = Field(default_factory=list)
