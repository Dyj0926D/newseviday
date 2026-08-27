import hashlib
import json
from datetime import datetime
from pathlib import Path

from pydantic import Field, model_validator

from newseviday_pipeline.models import (
    Brief,
    BriefSection,
    ContentSnapshot,
    ContractModel,
    GeneratedText,
)
from newseviday_pipeline.stages import key_signal_assessment

EDITORIAL_PROMPT_VERSION = "editorial-bootstrap-v1"


class EditorialArticle(ContractModel):
    content_hash: str = Field(min_length=64, max_length=64)
    title_zh: str = Field(min_length=2, max_length=160)
    summary_zh: str = Field(min_length=20, max_length=320)
    why_it_matters: str = Field(min_length=10, max_length=180)
    key_points: list[str] = Field(min_length=2, max_length=5)


class EditorialBrief(ContractModel):
    id: str = Field(min_length=3, max_length=160)
    title: str = Field(min_length=6, max_length=80)
    period_start: datetime
    period_end: datetime
    published_at: datetime
    sections: list[BriefSection] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def validate_period(self) -> "EditorialBrief":
        if self.period_start >= self.period_end:
            raise ValueError("editorial_brief_period_must_increase")
        return self


class EditorialPackage(ContractModel):
    version: int = 1
    generated_at: datetime
    articles: list[EditorialArticle] = Field(default_factory=list)
    brief: EditorialBrief | None = None


def load_editorial_package(path: Path) -> EditorialPackage:
    return EditorialPackage.model_validate_json(path.read_text(encoding="utf-8"))


def apply_editorial_package(
    snapshot: ContentSnapshot,
    package: EditorialPackage,
) -> ContentSnapshot:
    result = snapshot.model_copy(deep=True)
    by_hash = {article.content_hash: article for article in result.articles}
    requested_hashes = {item.content_hash for item in package.articles}
    missing_hashes = sorted(requested_hashes - set(by_hash))
    if missing_hashes:
        raise ValueError(f"editorial_articles_not_found:{','.join(missing_hashes)}")

    for item in package.articles:
        article = by_hash[item.content_hash]
        article.ai = GeneratedText(
            title_zh=item.title_zh,
            summary_zh=item.summary_zh,
            why_it_matters=item.why_it_matters,
            key_points=item.key_points,
            provider="editorial",
            model="编辑整理",
            prompt_version=EDITORIAL_PROMPT_VERSION,
            generated_at=package.generated_at,
        )
        if article.content_score_breakdown is not None:
            article.key_signal = key_signal_assessment(article, anchor=package.generated_at)

    if package.brief is not None:
        evidence_by_id = {evidence.id: evidence for evidence in result.evidence}
        for section in package.brief.sections:
            if len(set(section.evidence_ids)) != len(section.evidence_ids):
                raise ValueError("editorial_brief_duplicate_evidence")
            unknown = sorted(set(section.evidence_ids) - set(evidence_by_id))
            if unknown:
                raise ValueError(f"editorial_brief_evidence_not_found:{','.join(unknown)}")
            source_ids = {evidence_by_id[item].source_id for item in section.evidence_ids}
            if len(source_ids) < 2:
                raise ValueError("editorial_brief_section_requires_two_sources")
        result.briefs = [
            Brief(
                id=package.brief.id,
                title=package.brief.title,
                period_start=package.brief.period_start,
                period_end=package.brief.period_end,
                sections=package.brief.sections,
                generated_by=GeneratedText(
                    provider="editorial",
                    model="编辑整理",
                    prompt_version=EDITORIAL_PROMPT_VERSION,
                    generated_at=package.generated_at,
                ),
                published_at=package.brief.published_at,
            )
        ]

    signature = hashlib.sha256(
        json.dumps(
            package.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:8]
    result.snapshot_id = f"{snapshot.snapshot_id}-editorial-{signature}"
    result.generated_at = package.generated_at
    return result
