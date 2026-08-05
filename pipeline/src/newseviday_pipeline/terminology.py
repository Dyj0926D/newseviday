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
        generated = f"{article.ai.title_zh or ''} {article.ai.summary_zh or ''}".casefold()
        for rule in config.terms:
            if rule.source.casefold() not in source_text:
                continue
            accepted = [
                rule.preferred_zh.casefold(),
                *[item.casefold() for item in rule.allowed_aliases],
            ]
            if any(value in generated for value in accepted):
                checked += 1
                matched += 1
            elif rule.source.casefold() in generated:
                # The generated text retained the source term but did not use an
                # approved representation. Omitted concepts are not translation errors.
                checked += 1
    return matched / checked if checked else 1.0
