import json
import os
import re
import tempfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import Field

from newseviday_pipeline.models import ContentSnapshot, ContractModel
from newseviday_pipeline.stages import chinese_display_ready


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
    high_value_chinese_gap_count: int
    recent_window_days: int
    recent_article_count: int
    recent_chinese_ready_count: int
    recent_chinese_gap_count: int
    trend_brief_count: int
    potential_story_clusters: list[StoryCluster]
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
    terms = re.findall(r"[a-z0-9][a-z0-9-]{2,}|[\u4e00-\u9fff]{2,6}", value.casefold())
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
        high_value_chinese_gap_count=high_value_chinese_gap_count,
        recent_window_days=30,
        recent_article_count=len(recent_articles),
        recent_chinese_ready_count=recent_chinese_ready_count,
        recent_chinese_gap_count=recent_chinese_gap_count,
        trend_brief_count=len(snapshot.briefs),
        potential_story_clusters=detect_story_clusters(snapshot),
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
