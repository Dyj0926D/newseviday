from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from newseviday_pipeline.models import Article


class TermRule(BaseModel):
    source: str
    preferred_zh: str = Field(alias="preferredZh")
    allowed_aliases: list[str] = Field(default_factory=list, alias="allowedAliases")


class TerminologyConfig(BaseModel):
    version: int
    terms: list[TermRule]


def load_terminology(path: Path) -> TerminologyConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return TerminologyConfig.model_validate(payload)


def terminology_consistency(articles: list[Article], config: TerminologyConfig) -> float:
    checked = matched = 0
    for article in articles:
        if not article.ai:
            continue
        source_text = f"{article.facts.title} {article.facts.abstract or ''}".casefold()
        generated = f"{article.ai.title_zh or ''} {article.ai.summary_zh or ''}"
        for rule in config.terms:
            if rule.source.casefold() not in source_text:
                continue
            checked += 1
            accepted = [rule.preferred_zh, *rule.allowed_aliases]
            matched += int(any(value in generated for value in accepted))
    return matched / checked if checked else 1.0
