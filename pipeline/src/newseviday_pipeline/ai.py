import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel

from newseviday_pipeline.ai_models import ArticleEnrichment, ProfileEnhancement
from newseviday_pipeline.models import Article, ContentSnapshot, GeneratedText, TopicConfig
from newseviday_pipeline.stages import (
    chinese_display_ready,
    key_signal_assessment,
    key_signal_waiting_for_chinese,
)
from newseviday_pipeline.terminology import TerminologyConfig

PROMPT_VERSION = "article-enrichment-v3"
PROFILE_PROMPT_VERSION = "profile-enhancement-v1"
MIN_ENRICHMENT_EVIDENCE_CHARS = 120
TRANSLATION_PRIORITY_SCORE = 0.60
MIN_PAID_TARGET_RELEVANCE = 0.60
MAX_PAID_ENRICHMENT_AGE_DAYS = 45
MAX_NEW_ENRICHMENTS_PER_SOURCE = 3
HOME_PRIORITY_WINDOW = 8
SOURCE_REPEAT_PENALTY = 1.0
SchemaModel = TypeVar("SchemaModel", bound=BaseModel)


@dataclass(frozen=True)
class CompletionUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class EnrichmentTelemetry:
    model_calls: int = 0
    cache_hits: int = 0
    accepted_enrichment_reuses: int = 0
    enriched_articles: int = 0
    skipped_thin_evidence: int = 0
    skipped_below_quality_floor: int = 0
    skipped_stale: int = 0
    skipped_source_cap: int = 0
    skipped_after_call_limit: int = 0


class StructuredCompletionClient(Protocol):
    @property
    def model(self) -> str: ...

    def complete_json(self, *, system: str, user: str) -> Mapping[str, Any]: ...


def _json_object(value: str) -> Mapping[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", value.strip(), flags=re.IGNORECASE)
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("model_output_must_be_json_object")
    return payload


class DeepSeekStructuredClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: int = 30,
        thinking_enabled: bool = False,
    ) -> None:
        if not api_key or not model:
            raise ValueError("deepseek_configuration_incomplete")
        if not base_url.startswith("https://"):
            raise ValueError("deepseek_base_url_must_be_https")
        self.api_key = api_key
        self._model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.thinking_enabled = thinking_enabled
        self._usage: list[CompletionUsage] = []

    @property
    def model(self) -> str:
        return self._model

    @property
    def usage_reported_calls(self) -> int:
        return len(self._usage)

    @property
    def usage_totals(self) -> CompletionUsage:
        return CompletionUsage(
            prompt_tokens=sum(item.prompt_tokens for item in self._usage),
            completion_tokens=sum(item.completion_tokens for item in self._usage),
            total_tokens=sum(item.total_tokens for item in self._usage),
        )

    def complete_json(self, *, system: str, user: str) -> Mapping[str, Any]:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "thinking": {"type": "enabled" if self.thinking_enabled else "disabled"},
                "response_format": {"type": "json_object"},
                **({} if self.thinking_enabled else {"temperature": 0.1}),
                "max_tokens": 1_200,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("invalid_deepseek_completion") from error
        usage = payload.get("usage") if isinstance(payload, Mapping) else None
        if isinstance(usage, Mapping):
            prompt_tokens = _nonnegative_int(usage.get("prompt_tokens"))
            completion_tokens = _nonnegative_int(usage.get("completion_tokens"))
            total_tokens = _nonnegative_int(usage.get("total_tokens"))
            self._usage.append(
                CompletionUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens or prompt_tokens + completion_tokens,
                )
            )
        return _json_object(str(content))

    @classmethod
    def from_environment(cls) -> "DeepSeekStructuredClient":
        return cls(
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            model=os.environ.get("DEEPSEEK_MODEL", ""),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            thinking_enabled=os.environ.get("DEEPSEEK_THINKING_ENABLED", "false").lower() == "true",
        )


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


class FileAiCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str, schema: type[SchemaModel]) -> SchemaModel | None:
        path = self._path(key)
        if not path.exists():
            return None
        return schema.model_validate_json(path.read_text(encoding="utf-8"))

    def put(self, key: str, value: BaseModel) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        content = json.dumps(
            value.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            indent=2,
        )
        handle, name = tempfile.mkstemp(dir=self.directory, prefix="ai-", suffix=".tmp")
        temporary = Path(name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content + "\n")
            temporary.replace(self._path(key))
        finally:
            temporary.unlink(missing_ok=True)


def _cache_key(content_hash: str, model: str, prompt_version: str) -> str:
    value = f"{content_hash}:{model}:{prompt_version}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _terminology_instruction(evidence: str, config: TerminologyConfig | None) -> str:
    if config is None:
        return ""
    source_text = evidence.casefold()
    relevant = [rule for rule in config.terms if rule.source.casefold() in source_text]
    if not relevant:
        return ""
    mappings = "\n".join(f"- {rule.source} -> {rule.preferred_zh}" for rule in relevant)
    return (
        "\n术语规范：原文已经出现下列术语。titleZh 或 summaryZh 必须保留该概念，"
        "并使用指定中文写法：\n"
        f"{mappings}\n"
    )


def _enrichment_priority_order(articles: list[Article]) -> list[Article]:
    """Prioritize valuable untranslated items while preserving source diversity."""

    topic_counts: dict[str, int] = {}
    for article in articles:
        for topic_id in article.topic_scores:
            topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1
    homepage_ids = {
        article.id
        for article in sorted(
            articles,
            key=lambda item: item.content_score or 0.0,
            reverse=True,
        )[:HOME_PRIORITY_WINDOW]
    }
    source_selections: dict[str, int] = {}
    recent_sources: list[str] = []
    remaining = list(articles)
    result: list[Article] = []

    def priority(article: Article) -> float:
        score = article.content_score or 0.0
        underrepresented_bonus = max(
            (1 / max(1, topic_counts.get(topic_id, 1)) for topic_id in article.topic_scores),
            default=0.0,
        )
        needs_chinese = not chinese_display_ready(article)
        key_translation_bonus = (
            100.0
            if needs_chinese
            and article.content_score_breakdown is not None
            and key_signal_waiting_for_chinese(article)
            else 0.0
        )
        high_value_translation_bonus = (
            10.0 if needs_chinese and score >= TRANSLATION_PRIORITY_SCORE else 0.0
        )
        homepage_translation_bonus = 4.0 if needs_chinese and article.id in homepage_ids else 0.0
        cross_language_bonus = (
            0.08 if needs_chinese and not article.language.casefold().startswith("zh") else 0.0
        )
        source_penalty = SOURCE_REPEAT_PENALTY * source_selections.get(article.source_id, 0)
        editorial_priority = 0.25 * (article.key_signal.score if article.key_signal else 0.0)
        return (
            key_translation_bonus
            + high_value_translation_bonus
            + homepage_translation_bonus
            + score
            + editorial_priority
            + 0.12 * underrepresented_bonus
            + cross_language_bonus
            - source_penalty
        )

    while remaining:
        candidates = [
            article
            for article in remaining
            if not (
                len(recent_sources) >= 2
                and recent_sources[-1] == recent_sources[-2] == article.source_id
            )
        ]
        if not candidates:
            candidates = remaining
        selected = max(candidates, key=priority)
        remaining.remove(selected)
        result.append(selected)
        source_selections[selected.source_id] = source_selections.get(selected.source_id, 0) + 1
        recent_sources.append(selected.source_id)
        if len(recent_sources) > 2:
            recent_sources.pop(0)
    return result


def _paid_enrichment_skip_reason(article: Article, generated_at: datetime) -> str | None:
    if (article.content_score or 0.0) < TRANSLATION_PRIORITY_SCORE:
        return "below_quality_floor"
    if (
        article.content_score_breakdown is None
        or article.content_score_breakdown.target_relevance < MIN_PAID_TARGET_RELEVANCE
    ):
        return "below_quality_floor"
    published_at = article.published_at or article.collected_at
    if generated_at - published_at > timedelta(days=MAX_PAID_ENRICHMENT_AGE_DAYS):
        return "stale"
    return None


def enrich_snapshot(
    snapshot: ContentSnapshot,
    *,
    client: StructuredCompletionClient,
    cache: FileAiCache,
    topics: list[TopicConfig],
    terminology: TerminologyConfig | None = None,
    accepted_snapshot: ContentSnapshot | None = None,
    max_model_calls: int = 5,
    now: datetime | None = None,
    telemetry: EnrichmentTelemetry | None = None,
) -> tuple[ContentSnapshot, int]:
    if not 0 <= max_model_calls <= 10:
        raise ValueError("max_model_calls_must_be_between_0_and_10")
    generated_at = now or datetime.now(UTC)
    result = snapshot.model_copy(deep=True)
    stats = telemetry or EnrichmentTelemetry()
    model_calls = 0
    topic_description = ", ".join(f"{topic.id}={topic.label}" for topic in topics)
    accepted_ai = {
        article.content_hash: article.ai
        for article in (accepted_snapshot.articles if accepted_snapshot else [])
        if article.ai is not None
    }
    new_enrichments_by_source: dict[str, int] = {}
    for article in _enrichment_priority_order(result.articles):
        published_enrichment = article.ai or accepted_ai.get(article.content_hash)
        if published_enrichment is not None:
            article.ai = published_enrichment.model_copy(deep=True)
            stats.accepted_enrichment_reuses += 1
            stats.enriched_articles += 1
            continue
        evidence = article.facts.abstract or article.facts.title
        if len(evidence.strip()) < MIN_ENRICHMENT_EVIDENCE_CHARS:
            stats.skipped_thin_evidence += 1
            continue
        skip_reason = _paid_enrichment_skip_reason(article, generated_at)
        if skip_reason == "below_quality_floor":
            stats.skipped_below_quality_floor += 1
            continue
        if skip_reason == "stale":
            stats.skipped_stale += 1
            continue
        if new_enrichments_by_source.get(article.source_id, 0) >= MAX_NEW_ENRICHMENTS_PER_SOURCE:
            stats.skipped_source_cap += 1
            continue
        terminology_instruction = _terminology_instruction(evidence, terminology)
        terminology_signature = hashlib.sha256(terminology_instruction.encode("utf-8")).hexdigest()[
            :12
        ]
        key = _cache_key(
            article.content_hash,
            client.model,
            f"{PROMPT_VERSION}:{terminology_signature}",
        )
        enrichment = cache.get(key, ArticleEnrichment)
        if enrichment is None:
            if model_calls >= max_model_calls:
                stats.skipped_after_call_limit += 1
                continue
            payload = client.complete_json(
                system=(
                    "你是 NewsEviday 的结构化情报编辑。只根据给定资料输出 JSON。"
                    "不得补充资料外的发布日期、数字、客户或因果结论。"
                ),
                user=(
                    f"允许的 topicIds：{topic_description}\n"
                    f"原始语言：{article.language}\n原始标题：{article.facts.title}\n"
                    "<untrusted-evidence>\n"
                    f"{evidence[:8_000]}\n"
                    "</untrusted-evidence>\n"
                    f"{terminology_instruction}"
                    "输出 titleZh、summaryZh、whyItMatters、keyPoints、topicIds。"
                    "summaryZh 控制在 120–220 个中文字符，提炼主要变化，避免复述整段摘要；"
                    "whyItMatters 控制在 40–100 个中文字符；"
                    "keyPoints 输出 2–4 条，每条不超过 40 个中文字符。"
                ),
            )
            enrichment = ArticleEnrichment.model_validate(payload)
            cache.put(key, enrichment)
            model_calls += 1
            stats.model_calls = model_calls
        else:
            stats.cache_hits += 1
        new_enrichments_by_source[article.source_id] = (
            new_enrichments_by_source.get(article.source_id, 0) + 1
        )
        article.ai = GeneratedText(
            title_zh=enrichment.title_zh,
            summary_zh=enrichment.summary_zh,
            why_it_matters=enrichment.why_it_matters,
            key_points=enrichment.key_points,
            model=client.model,
            prompt_version=PROMPT_VERSION,
            generated_at=generated_at,
        )
        stats.enriched_articles += 1
        # Topic labels remain deterministic pipeline data. Model topicIds are
        # validated for observability but never change filters or recommendations.
    suffix = hashlib.sha256(
        f"{snapshot.snapshot_id}:{client.model}:{PROMPT_VERSION}".encode()
    ).hexdigest()[:8]
    for article in result.articles:
        if article.content_score_breakdown is not None:
            article.key_signal = key_signal_assessment(article)
    result.snapshot_id = f"{snapshot.snapshot_id}-ai-{suffix}"
    result.generated_at = generated_at
    return result, model_calls


def enhance_profile(
    value: Mapping[str, str],
    *,
    client: StructuredCompletionClient,
    topics: list[TopicConfig],
) -> ProfileEnhancement:
    safe_input = {key: str(item)[:500] for key, item in value.items()}
    allowed = ", ".join(f"{topic.id}={topic.label}" for topic in topics)
    payload = client.complete_json(
        system=(
            "你只负责整理用户主动输入的职业与兴趣，不推断年龄、性别、公司、地点、健康、"
            "政治或其他敏感属性。只输出 JSON。"
        ),
        user=(
            f"可选主题：{allowed}\n用户输入：{json.dumps(safe_input, ensure_ascii=False)}\n"
            "输出 role、work、goal、description、interests、inferredTerms、warnings。"
        ),
    )
    result = ProfileEnhancement.model_validate(payload)
    allowed_ids = {topic.id for topic in topics}
    result.interests = [item for item in result.interests if item.topic_id in allowed_ids]
    return result
