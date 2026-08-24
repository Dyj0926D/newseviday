import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel

from newseviday_pipeline.ai_models import (
    ArticleEnrichment,
    ProfileEnhancement,
    TrendBriefDraft,
)
from newseviday_pipeline.models import (
    Article,
    Brief,
    BriefSection,
    ContentSnapshot,
    GeneratedText,
    TopicConfig,
)
from newseviday_pipeline.stages import (
    chinese_display_ready,
    high_significance_event_candidate,
    key_signal_assessment,
    key_signal_waiting_for_chinese,
)
from newseviday_pipeline.terminology import TerminologyConfig

PROMPT_VERSION = "article-enrichment-v3"
PROFILE_PROMPT_VERSION = "profile-enhancement-v1"
BRIEF_PROMPT_VERSION = "weekly-trend-brief-v2"
SHANGHAI_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
WEEKLY_BRIEF_CUTOFF = time(hour=9)
MIN_ENRICHMENT_EVIDENCE_CHARS = 120
MIN_TRUSTED_SHORT_EVIDENCE_CHARS = 50
TRANSLATION_PRIORITY_SCORE = 0.60
RECENT_TRANSLATION_SCORE = 0.42
RECENT_TRANSLATION_MAX_AGE = timedelta(days=3)
RECENT_TRANSLATION_MIN_TECHNICAL_VALUE = 0.55
MIN_PAID_TARGET_RELEVANCE = 0.60
SUPPLEMENTAL_TRANSLATION_SCORE = 0.45
SUPPLEMENTAL_TRANSLATION_TARGET_RELEVANCE = 0.50
SUPPLEMENTAL_TRANSLATION_MIN_PRODUCT_OR_ENGINEERING_VALUE = 0.70
ACADEMIC_FOCUS_TRANSLATION_SCORE = 0.35
ACADEMIC_FOCUS_TRANSLATION_MIN_TECHNICAL_VALUE = 0.65
MAX_PAID_ENRICHMENT_AGE_DAYS = 45
MAX_NEW_ENRICHMENTS_PER_SOURCE = 3
FOCUS_TRANSLATION_TOPICS = {
    "data-platform",
    "data-agent",
    "semantic-layer",
    "intelligent-lakehouse",
}
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
    supplemental_translation_calls: int = 0
    priority_topic_translation_calls: int = 0


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
        self._request_count = 0

    @property
    def model(self) -> str:
        return self._model

    @property
    def usage_reported_calls(self) -> int:
        return len(self._usage)

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def usage_totals(self) -> CompletionUsage:
        return CompletionUsage(
            prompt_tokens=sum(item.prompt_tokens for item in self._usage),
            completion_tokens=sum(item.completion_tokens for item in self._usage),
            total_tokens=sum(item.total_tokens for item in self._usage),
        )

    def complete_json(self, *, system: str, user: str) -> Mapping[str, Any]:
        self._request_count += 1
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
        event_translation_bonus = (
            50.0 if needs_chinese and high_significance_event_candidate(article) else 0.0
        )
        focus_topic_translation_bonus = (
            20.0
            if needs_chinese and FOCUS_TRANSLATION_TOPICS.intersection(article.topic_scores)
            else 0.0
        )
        homepage_translation_bonus = 4.0 if needs_chinese and article.id in homepage_ids else 0.0
        cross_language_bonus = (
            0.08 if needs_chinese and not article.language.casefold().startswith("zh") else 0.0
        )
        source_penalty = SOURCE_REPEAT_PENALTY * source_selections.get(article.source_id, 0)
        editorial_priority = 0.25 * (article.key_signal.score if article.key_signal else 0.0)
        return (
            key_translation_bonus
            + event_translation_bonus
            + high_value_translation_bonus
            + focus_topic_translation_bonus
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


def _trusted_fresh_translation_candidate(article: Article, generated_at: datetime) -> bool:
    values = article.content_score_breakdown
    published_at = article.published_at or article.collected_at
    return bool(
        generated_at - published_at <= RECENT_TRANSLATION_MAX_AGE
        and article.source_type in {"official", "research_institute", "professional_media"}
        and (article.content_score or 0.0) >= SUPPLEMENTAL_TRANSLATION_SCORE
        and values is not None
        and values.target_relevance >= SUPPLEMENTAL_TRANSLATION_TARGET_RELEVANCE
        and max(
            values.technical_advancement,
            values.engineering_applicability,
            values.product_industry_impact,
        )
        >= SUPPLEMENTAL_TRANSLATION_MIN_PRODUCT_OR_ENGINEERING_VALUE
    )


def _priority_topic_translation_candidate(
    article: Article,
    generated_at: datetime,
    evidence: str,
) -> bool:
    values = article.content_score_breakdown
    published_at = article.published_at or article.collected_at
    trusted_source = article.source_type in {"official", "research_institute"}
    qualified_academic_source = bool(
        article.source_type == "academic"
        and article.evidence_tier == "primary"
        and (article.content_score or 0.0) >= ACADEMIC_FOCUS_TRANSLATION_SCORE
        and values is not None
        and values.target_relevance >= MIN_PAID_TARGET_RELEVANCE
        and max(values.technical_advancement, values.engineering_applicability)
        >= ACADEMIC_FOCUS_TRANSLATION_MIN_TECHNICAL_VALUE
    )
    return bool(
        generated_at - published_at <= RECENT_TRANSLATION_MAX_AGE
        and (trusted_source or qualified_academic_source)
        and FOCUS_TRANSLATION_TOPICS.intersection(article.topic_scores)
        and (article.content_score or 0.0) >= 0.22
        and values is not None
        and values.target_relevance >= MIN_PAID_TARGET_RELEVANCE
        and len(evidence.strip()) >= MIN_TRUSTED_SHORT_EVIDENCE_CHARS
    )


def _paid_enrichment_skip_reason(article: Article, generated_at: datetime) -> str | None:
    values = article.content_score_breakdown
    published_at = article.published_at or article.collected_at
    recent_relevant_candidate = (
        generated_at - published_at <= RECENT_TRANSLATION_MAX_AGE
        and (article.content_score or 0.0) >= RECENT_TRANSLATION_SCORE
        and values is not None
        and values.target_relevance >= MIN_PAID_TARGET_RELEVANCE
        and max(
            values.technical_advancement,
            values.engineering_applicability,
            values.product_industry_impact,
        )
        >= RECENT_TRANSLATION_MIN_TECHNICAL_VALUE
    )
    trusted_fresh_candidate = _trusted_fresh_translation_candidate(article, generated_at)
    evidence = article.facts.abstract or article.facts.title
    priority_topic_candidate = _priority_topic_translation_candidate(
        article,
        generated_at,
        evidence,
    )
    if not high_significance_event_candidate(article):
        if (
            (article.content_score or 0.0) < TRANSLATION_PRIORITY_SCORE
            and not recent_relevant_candidate
            and not trusted_fresh_candidate
            and not priority_topic_candidate
        ):
            return "below_quality_floor"
        if (
            values is None
            or (
                values.target_relevance < MIN_PAID_TARGET_RELEVANCE
                and not trusted_fresh_candidate
                and not priority_topic_candidate
            )
        ):
            return "below_quality_floor"
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
    if accepted_snapshot is not None and not result.briefs and accepted_snapshot.briefs:
        result.briefs = [accepted_snapshot.briefs[0].model_copy(deep=True)]
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
        priority_topic_candidate = _priority_topic_translation_candidate(
            article,
            generated_at,
            evidence,
        )
        if (
            len(evidence.strip()) < MIN_ENRICHMENT_EVIDENCE_CHARS
            and not priority_topic_candidate
        ):
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
            summary_instruction = (
                "来源只提供了标题和短摘录。summaryZh 控制在 30–80 个中文字符，"
                "只翻译和压缩明确出现的信息；不得推断功能细节、效果、客户或结论。"
                if len(evidence.strip()) < MIN_ENRICHMENT_EVIDENCE_CHARS
                else "summaryZh 控制在 120–220 个中文字符，提炼主要变化，避免复述整段摘要；"
            )
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
                    f"{summary_instruction}"
                    "whyItMatters 控制在 40–100 个中文字符；"
                    "keyPoints 输出 2–4 条，每条不超过 40 个中文字符。"
                ),
            )
            enrichment = ArticleEnrichment.model_validate(payload)
            cache.put(key, enrichment)
            model_calls += 1
            stats.model_calls = model_calls
            if priority_topic_candidate:
                stats.priority_topic_translation_calls += 1
            elif _trusted_fresh_translation_candidate(article, generated_at):
                stats.supplemental_translation_calls += 1
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


@dataclass(frozen=True)
class BriefUpdateResult:
    snapshot: ContentSnapshot
    status: str
    model_calls: int
    period_start: datetime
    period_end: datetime


def _last_complete_seven_day_window(now: datetime) -> tuple[datetime, datetime]:
    local_now = now.astimezone(SHANGHAI_TIMEZONE)
    days_since_saturday = (local_now.weekday() - 5) % 7
    current_or_previous_saturday = local_now.date() - timedelta(days=days_since_saturday)
    period_end_exclusive = datetime.combine(
        current_or_previous_saturday,
        WEEKLY_BRIEF_CUTOFF,
        tzinfo=SHANGHAI_TIMEZONE,
    )
    if local_now < period_end_exclusive:
        period_end_exclusive -= timedelta(days=7)
    period_start = period_end_exclusive - timedelta(days=7)
    return period_start.astimezone(UTC), period_end_exclusive.astimezone(UTC)


def _brief_period_matches(brief: Brief, start: datetime, end_exclusive: datetime) -> bool:
    inclusive_end = end_exclusive - timedelta(microseconds=1)
    return brief.period_start == start and brief.period_end == inclusive_end


def _with_brief_suffix(snapshot: ContentSnapshot, signature_value: str) -> ContentSnapshot:
    result = snapshot.model_copy(deep=True)
    signature = hashlib.sha256(signature_value.encode("utf-8")).hexdigest()[:8]
    result.snapshot_id = f"{snapshot.snapshot_id}-brief-{signature}"
    return result


def _carry_brief(snapshot: ContentSnapshot, brief: Brief) -> ContentSnapshot:
    if snapshot.briefs and snapshot.briefs[0].id == brief.id:
        return snapshot
    result = _with_brief_suffix(snapshot, f"{brief.id}:{snapshot.snapshot_id}")
    result.briefs = [brief.model_copy(deep=True)]
    return result


def update_weekly_brief(
    snapshot: ContentSnapshot,
    *,
    accepted_snapshot: ContentSnapshot | None,
    client: StructuredCompletionClient | None,
    cache: FileAiCache,
    now: datetime | None = None,
    generate_if_due: bool = True,
    force_generate: bool = False,
) -> BriefUpdateResult:
    generated_at = now or datetime.now(UTC)
    period_start, period_end_exclusive = _last_complete_seven_day_window(generated_at)
    accepted_brief = (
        accepted_snapshot.briefs[0]
        if accepted_snapshot is not None and accepted_snapshot.briefs
        else None
    )

    if accepted_brief and _brief_period_matches(
        accepted_brief,
        period_start,
        period_end_exclusive,
    ):
        result = _carry_brief(snapshot, accepted_brief)
        return BriefUpdateResult(result, "current", 0, period_start, period_end_exclusive)

    local_generated_at = generated_at.astimezone(SHANGHAI_TIMEZONE)
    is_due = force_generate or (
        local_generated_at.weekday() == 5
        and local_generated_at.time() >= WEEKLY_BRIEF_CUTOFF
    )
    if not generate_if_due or not is_due or client is None:
        if accepted_brief is None:
            return BriefUpdateResult(snapshot, "not_due", 0, period_start, period_end_exclusive)
        result = _carry_brief(snapshot, accepted_brief)
        return BriefUpdateResult(result, "carried", 0, period_start, period_end_exclusive)

    candidates = [
        article
        for article in snapshot.articles
        if article.published_at is not None
        and period_start <= article.published_at < period_end_exclusive
        and article.evidence_ids
        and chinese_display_ready(article)
    ]
    source_ids = {article.source_id for article in candidates}
    if len(candidates) < 4 or len(source_ids) < 2:
        if accepted_brief is None:
            return BriefUpdateResult(
                snapshot,
                "insufficient_evidence",
                0,
                period_start,
                period_end_exclusive,
            )
        result = _carry_brief(snapshot, accepted_brief)
        return BriefUpdateResult(
            result,
            "insufficient_evidence_carried",
            0,
            period_start,
            period_end_exclusive,
        )

    candidate_signature = ":".join(sorted(article.content_hash for article in candidates))
    cache_key = _cache_key(candidate_signature, client.model, BRIEF_PROMPT_VERSION)
    draft = cache.get(cache_key, TrendBriefDraft)
    model_calls = 0
    if draft is None:
        evidence_rows = [
            {
                "evidenceId": article.evidence_ids[0],
                "sourceId": article.source_id,
                "sourceType": article.source_type,
                "evidenceTier": article.evidence_tier,
                "publishedAt": (
                    article.published_at.isoformat() if article.published_at is not None else None
                ),
                "title": article.ai.title_zh if article.ai else article.facts.title,
                "summary": article.ai.summary_zh if article.ai else article.facts.abstract,
            }
            for article in sorted(
                candidates,
                key=lambda item: item.published_at or item.collected_at,
                reverse=True,
            )
        ]
        payload = client.complete_json(
            system=(
                "你是 NewsEviday 的趋势情报编辑。只能根据给定证据归纳共同变化，并输出 JSON。"
                "不得引入证据外的数字、因果关系、公司计划或市场结论。"
            ),
            user=(
                f"覆盖周期：{period_start.date().isoformat()} 至 "
                f"{(period_end_exclusive - timedelta(days=1)).date().isoformat()}。\n"
                "输出 title 和 1 至 3 个 sections。每个 section 包含 heading、body、evidenceIds；"
                "每节必须引用 2 至 5 条证据，并覆盖至少 2 个不同 sourceId。"
                "事实结论优先使用 evidenceTier=primary 的一手来源；"
                "professional_media 与 independent_author 只作为观察、解释或交叉验证，"
                "不能单独支撑趋势结论。"
                "body 用中文说明共同变化和判断边界，避免把单篇文章写成行业趋势。\n"
                f"<untrusted-evidence>\n{json.dumps(evidence_rows, ensure_ascii=False)}\n"
                "</untrusted-evidence>"
            ),
        )
        draft = TrendBriefDraft.model_validate(payload)
        cache.put(cache_key, draft)
        model_calls = 1

    evidence_to_source = {
        evidence_id: article.source_id
        for article in candidates
        for evidence_id in article.evidence_ids
    }
    evidence_to_tier = {
        evidence_id: article.evidence_tier
        for article in candidates
        for evidence_id in article.evidence_ids
    }
    sections: list[BriefSection] = []
    for section in draft.sections:
        evidence_ids = list(dict.fromkeys(section.evidence_ids))
        if any(item not in evidence_to_source for item in evidence_ids):
            raise ValueError("weekly_brief_contains_unknown_evidence")
        if len({evidence_to_source[item] for item in evidence_ids}) < 2:
            raise ValueError("weekly_brief_section_requires_two_sources")
        section_tiers = [evidence_to_tier[item] for item in evidence_ids]
        secondary_sources = {
            evidence_to_source[item]
            for item in evidence_ids
            if evidence_to_tier[item] == "secondary"
        }
        if "primary" not in section_tiers and len(secondary_sources) < 2:
            raise ValueError("weekly_brief_requires_primary_or_two_secondary_sources")
        sections.append(
            BriefSection(
                heading=section.heading,
                body=section.body,
                evidence_ids=evidence_ids,
            )
        )

    inclusive_end = period_end_exclusive - timedelta(microseconds=1)
    brief_signature = hashlib.sha256(
        f"{candidate_signature}:{client.model}:{BRIEF_PROMPT_VERSION}".encode()
    ).hexdigest()[:12]
    brief = Brief(
        id=f"brief-{period_start.date().isoformat()}-{brief_signature}",
        title=draft.title,
        period_start=period_start,
        period_end=inclusive_end,
        sections=sections,
        generated_by=GeneratedText(
            provider="deepseek",
            model=client.model,
            prompt_version=BRIEF_PROMPT_VERSION,
            generated_at=generated_at,
        ),
        published_at=generated_at,
    )
    result = _with_brief_suffix(snapshot, f"{brief.id}:{snapshot.snapshot_id}")
    result.briefs = [brief]
    return BriefUpdateResult(result, "generated", model_calls, period_start, period_end_exclusive)


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
