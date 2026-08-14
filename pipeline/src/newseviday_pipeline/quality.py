import json
import math
import os
import re
import tempfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import Field

from newseviday_pipeline.models import ContentSnapshot, ContractModel
from newseviday_pipeline.stages import (
    chinese_display_ready,
    high_significance_event_candidate,
)


class StoryCluster(ContractModel):
    id: str
    article_ids: list[str] = Field(min_length=2)
    source_count: int = Field(ge=2)
    shared_terms: list[str] = Field(default_factory=list)


class SnapshotQualityReport(ContractModel):
    schema_version: str = "1.0.0"
    snapshot_id: str
    generated_at: datetime
    gate: str
    article_count: int
    configured_source_count: int
    contributing_source_count: int
    structured_article_count: int
    ai_article_count: int
    editorial_article_count: int
    missing_abstract_count: int
    missing_abstract_rate: float = Field(ge=0, le=1)
    missing_abstract_by_source: dict[str, int]
    source_counts: dict[str, int]
    zero_contribution_source_ids: list[str]
    topic_counts: dict[str, int]
    topic_gaps: list[str]
    key_signal_eligible_count: int
    high_significance_event_count: int
    high_significance_chinese_gap_count: int
    event_type_counts: dict[str, int]
    high_value_chinese_gap_count: int
    recent_window_days: int
    recent_article_count: int
    recent_chinese_ready_count: int
    recent_chinese_gap_count: int
    trend_brief_count: int
    potential_story_clusters: list[StoryCluster]
    issues: list[str]


class ReleaseGuardReport(ContractModel):
    schema_version: str = "1.0.0"
    generated_at: datetime
    gate: str
    candidate_snapshot_id: str
    baseline_snapshot_id: str
    candidate_quality_gate: str
    candidate_recent_article_count: int
    candidate_recent_chinese_ready_count: int
    baseline_recent_chinese_ready_count: int
    required_recent_chinese_ready_count: int
    candidate_recent_chinese_ready_rate: float = Field(ge=0, le=1)
    minimum_recent_chinese_ready_rate: float = Field(ge=0, le=1)
    candidate_missing_abstract_rate: float = Field(ge=0, le=1)
    maximum_missing_abstract_rate: float = Field(ge=0, le=1)
    candidate_key_signal_count: int
    baseline_key_signal_count: int
    issues: list[str]


STOP_TERMS = {
    "about",
    "after",
    "and",
    "are",
    "can",
    "for",
    "from",
    "has",
    "have",
    "how",
    "into",
    "news",
    "new",
    "our",
    "that",
    "the",
    "their",
    "this",
    "use",
    "using",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "your",
    "发布",
    "推出",
    "更新",
    "模型",
    "人工智能",
}


def _title_terms(value: str) -> set[str]:
    normalized = value.casefold().replace("-", " ")
    terms = re.findall(r"[a-z0-9][a-z0-9]{2,}|[\u4e00-\u9fff]{2,6}", normalized)
    return {term for term in terms if term not in STOP_TERMS}


def detect_story_clusters(snapshot: ContentSnapshot) -> list[StoryCluster]:
    """Find possible multi-source stories for operator review; it does not merge articles."""

    clusters: list[StoryCluster] = []
    used_pairs: set[tuple[str, str]] = set()
    for index, article in enumerate(snapshot.articles):
        left = _title_terms(article.facts.title)
        if not left:
            continue
        for other in snapshot.articles[index + 1 :]:
            if article.source_id == other.source_id:
                continue
            left_id, right_id = sorted((article.id, other.id))
            pair = (left_id, right_id)
            if pair in used_pairs:
                continue
            right = _title_terms(other.facts.title)
            shared = left & right
            similarity = len(shared) / max(1, min(len(left), len(right)))
            if len(shared) < 2 or similarity < 0.45:
                continue
            used_pairs.add(pair)
            clusters.append(
                StoryCluster(
                    id=f"story-{len(clusters) + 1:03d}",
                    article_ids=list(pair),
                    source_count=2,
                    shared_terms=sorted(shared)[:6],
                )
            )
    return clusters[:20]


def audit_snapshot(
    snapshot: ContentSnapshot,
    *,
    now: datetime | None = None,
) -> SnapshotQualityReport:
    source_counts = Counter(article.source_id for article in snapshot.articles)
    topic_counts = {
        topic.id: sum(topic.id in article.topic_scores for article in snapshot.articles)
        for topic in snapshot.topics
    }
    topic_gaps = sorted(topic_id for topic_id, count in topic_counts.items() if count == 0)
    missing_abstract_count = sum(not article.facts.abstract for article in snapshot.articles)
    missing_abstract_by_source = Counter(
        article.source_id for article in snapshot.articles if not article.facts.abstract
    )
    missing_rate = missing_abstract_count / len(snapshot.articles) if snapshot.articles else 1.0
    configured_source_ids = {source.id for source in snapshot.sources}
    zero_contribution_source_ids = sorted(configured_source_ids - set(source_counts))
    key_signal_eligible_count = sum(
        bool(article.key_signal and article.key_signal.eligible) for article in snapshot.articles
    )
    high_significance_event_count = sum(
        high_significance_event_candidate(article) for article in snapshot.articles
    )
    high_significance_chinese_gap_count = sum(
        high_significance_event_candidate(article) and not chinese_display_ready(article)
        for article in snapshot.articles
    )
    event_type_counts = Counter(
        event_type
        for article in snapshot.articles
        if article.key_signal is not None
        for event_type in article.key_signal.event_types
    )
    high_value_chinese_gap_count = sum(
        (article.content_score or 0) >= 0.6 and not chinese_display_ready(article)
        for article in snapshot.articles
    )
    anchor = now or snapshot.generated_at
    recent_cutoff = anchor - timedelta(days=30)
    recent_articles = [
        article
        for article in snapshot.articles
        if (article.published_at or article.collected_at) >= recent_cutoff
    ]
    recent_chinese_ready_count = sum(chinese_display_ready(article) for article in recent_articles)
    recent_chinese_gap_count = len(recent_articles) - recent_chinese_ready_count
    issues: list[str] = []
    hard_failure = False
    if len(snapshot.articles) < 20:
        issues.append("公开内容少于 20 条")
        hard_failure = True
    if len(source_counts) < 5:
        issues.append("实际贡献来源少于 5 个")
        hard_failure = True
    if missing_rate > 0.5:
        issues.append("缺少来源摘要的内容超过 50%")
        hard_failure = True
    if topic_gaps:
        issues.append(f"{len(topic_gaps)} 个配置主题暂时没有入选内容")
    if recent_chinese_gap_count:
        issues.append(f"近 30 天有 {recent_chinese_gap_count} 条外文内容待中文整理")

    return SnapshotQualityReport(
        snapshot_id=snapshot.snapshot_id,
        generated_at=now or datetime.now(UTC),
        gate="fail" if hard_failure else ("observe" if issues else "pass"),
        article_count=len(snapshot.articles),
        configured_source_count=len(snapshot.sources),
        contributing_source_count=len(source_counts),
        structured_article_count=sum(article.ai is not None for article in snapshot.articles),
        ai_article_count=sum(
            article.ai is not None and article.ai.provider == "deepseek"
            for article in snapshot.articles
        ),
        editorial_article_count=sum(
            article.ai is not None and article.ai.provider == "editorial"
            for article in snapshot.articles
        ),
        missing_abstract_count=missing_abstract_count,
        missing_abstract_rate=round(missing_rate, 4),
        missing_abstract_by_source=dict(sorted(missing_abstract_by_source.items())),
        source_counts=dict(sorted(source_counts.items())),
        zero_contribution_source_ids=zero_contribution_source_ids,
        topic_counts=topic_counts,
        topic_gaps=topic_gaps,
        key_signal_eligible_count=key_signal_eligible_count,
        high_significance_event_count=high_significance_event_count,
        high_significance_chinese_gap_count=high_significance_chinese_gap_count,
        event_type_counts=dict(sorted(event_type_counts.items())),
        high_value_chinese_gap_count=high_value_chinese_gap_count,
        recent_window_days=30,
        recent_article_count=len(recent_articles),
        recent_chinese_ready_count=recent_chinese_ready_count,
        recent_chinese_gap_count=recent_chinese_gap_count,
        trend_brief_count=len(snapshot.briefs),
        potential_story_clusters=detect_story_clusters(snapshot),
        issues=issues,
    )


def evaluate_release_guard(
    candidate: ContentSnapshot,
    baseline: ContentSnapshot,
    *,
    now: datetime | None = None,
) -> ReleaseGuardReport:
    """Block public inventory regressions while still allowing artifacts to be reviewed."""

    anchor = now or datetime.now(UTC)
    candidate_quality = audit_snapshot(candidate, now=anchor)
    baseline_quality = audit_snapshot(baseline, now=anchor)
    baseline_ready = baseline_quality.recent_chinese_ready_count
    required_ready = (
        min(baseline_ready, max(12, math.ceil(baseline_ready * 0.8)))
        if baseline_ready
        else 0
    )
    candidate_ready_rate = (
        candidate_quality.recent_chinese_ready_count / candidate_quality.recent_article_count
        if candidate_quality.recent_article_count
        else 0.0
    )
    baseline_ready_rate = (
        baseline_ready / baseline_quality.recent_article_count
        if baseline_quality.recent_article_count
        else 0.0
    )
    minimum_ready_rate = min(0.8, max(0.55, baseline_ready_rate - 0.4))
    maximum_missing_rate = min(0.5, max(0.2, baseline_quality.missing_abstract_rate + 0.1))
    issues: list[str] = []
    if candidate_quality.gate == "fail":
        issues.append("候选快照未通过基础质量门禁")
    if candidate_quality.recent_chinese_ready_count < required_ready:
        issues.append("近 30 天中文可读内容低于已发布库存的保底要求")
    if candidate_ready_rate < minimum_ready_rate:
        issues.append("近 30 天中文可读内容占比下降过多")
    if candidate_quality.missing_abstract_rate > maximum_missing_rate:
        issues.append("来源摘要缺失率相对已发布版本上升过多")
    return ReleaseGuardReport(
        generated_at=anchor,
        gate="fail" if issues else "pass",
        candidate_snapshot_id=candidate.snapshot_id,
        baseline_snapshot_id=baseline.snapshot_id,
        candidate_quality_gate=candidate_quality.gate,
        candidate_recent_article_count=candidate_quality.recent_article_count,
        candidate_recent_chinese_ready_count=candidate_quality.recent_chinese_ready_count,
        baseline_recent_chinese_ready_count=baseline_ready,
        required_recent_chinese_ready_count=required_ready,
        candidate_recent_chinese_ready_rate=round(candidate_ready_rate, 4),
        minimum_recent_chinese_ready_rate=round(minimum_ready_rate, 4),
        candidate_missing_abstract_rate=candidate_quality.missing_abstract_rate,
        maximum_missing_abstract_rate=round(maximum_missing_rate, 4),
        candidate_key_signal_count=candidate_quality.key_signal_eligible_count,
        baseline_key_signal_count=baseline_quality.key_signal_eligible_count,
        issues=issues,
    )


def write_quality_report(report: SnapshotQualityReport, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=output.parent, prefix="quality-", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                report.model_dump(mode="json", by_alias=True),
                stream,
                ensure_ascii=False,
                indent=2,
            )
            stream.write("\n")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def write_release_guard_report(report: ReleaseGuardReport, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=output.parent, prefix="release-guard-", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                report.model_dump(mode="json", by_alias=True),
                stream,
                ensure_ascii=False,
                indent=2,
            )
            stream.write("\n")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
