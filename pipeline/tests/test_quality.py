import json
from datetime import UTC, datetime
from pathlib import Path

from newseviday_pipeline.quality import (
    STOP_TERMS,
    audit_snapshot,
    detect_story_clusters,
    write_quality_report,
)
from newseviday_pipeline.snapshot import load_snapshot

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "apps" / "web" / "public" / "data" / "current.json"


def test_quality_report_exposes_content_gaps_without_model_calls(tmp_path: Path) -> None:
    snapshot = load_snapshot(SNAPSHOT)
    report = audit_snapshot(snapshot, now=datetime(2026, 8, 6, tzinfo=UTC))
    output = tmp_path / "quality.json"
    write_quality_report(report, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert report.article_count == 40
    assert report.contributing_source_count >= 5
    assert report.gate in {"pass", "observe"}
    assert payload["snapshotId"] == snapshot.snapshot_id
    assert "topicCounts" in payload
    assert "visibleTopicCounts" in payload
    assert "visibleTopicGaps" in payload
    assert "potentialStoryClusters" in payload
    assert "highValueChineseGapCount" in payload
    assert "structuredArticleCount" in payload
    assert "editorialArticleCount" in payload
    assert "recentChineseGapCount" in payload
    assert "visibleRecent24hCount" in payload
    assert "visibleRecent48hCount" in payload
    assert "latestVisiblePublishedAt" in payload
    assert "trendBriefCount" in payload
    assert "keySignalEligibleCount" in payload
    assert "highSignificanceEventCount" in payload
    assert "highSignificanceChineseGapCount" in payload
    assert "eventTypeCounts" in payload
    assert "zeroContributionSourceIds" in payload
    assert "missingAbstractBySource" in payload
    assert all(
        not (set(cluster["sharedTerms"]) & STOP_TERMS)
        for cluster in payload["potentialStoryClusters"]
    )


def test_story_clusters_ignore_generic_question_words() -> None:
    snapshot = load_snapshot(SNAPSHOT)
    left = snapshot.articles[0].model_copy(deep=True)
    right = snapshot.articles[1].model_copy(deep=True)
    left.id = "article-generic-left"
    left.source_id = "source-left"
    left.facts.title = "What are agentic workflows?"
    right.id = "article-generic-right"
    right.source_id = "source-right"
    right.facts.title = "What are data platforms?"
    snapshot.articles = [left, right]

    assert detect_story_clusters(snapshot) == []


def test_story_clusters_group_hyphenated_and_spaced_product_names() -> None:
    snapshot = load_snapshot(SNAPSHOT)
    left = snapshot.articles[0].model_copy(deep=True)
    right = snapshot.articles[1].model_copy(deep=True)
    left.id = "article-deepseek-official"
    left.source_id = "deepseek-updates"
    left.facts.title = "DeepSeek-V4-Pro Update"
    right.id = "article-deepseek-analysis"
    right.source_id = "independent-analysis"
    right.facts.title = "DeepSeek V4 Pro 0813 on OpenRouter"
    snapshot.articles = [left, right]

    clusters = detect_story_clusters(snapshot)

    assert len(clusters) == 1
    assert set(clusters[0].shared_terms) == {"deepseek", "pro"}


def test_quality_report_counts_source_and_chinese_readiness_gaps() -> None:
    snapshot = load_snapshot(SNAPSHOT)
    snapshot.sources = snapshot.sources[:3]
    left = snapshot.articles[0].model_copy(deep=True)
    right = snapshot.articles[1].model_copy(deep=True)
    left.id = "article-quality-left"
    left.source_id = snapshot.sources[0].id
    left.language = "en"
    left.ai = None
    left.facts.abstract = None
    left.content_score = 0.8
    assert left.key_signal is not None
    left.key_signal.eligible = True
    right.id = "article-quality-right"
    right.source_id = snapshot.sources[1].id
    right.facts.abstract = "A sufficiently detailed source abstract. " * 4
    snapshot.articles = [left, right]

    report = audit_snapshot(snapshot, now=datetime(2026, 8, 8, tzinfo=UTC))

    assert report.missing_abstract_by_source == {left.source_id: 1}
    assert report.zero_contribution_source_ids == [snapshot.sources[2].id]
    assert report.high_value_chinese_gap_count == 1
    assert report.key_signal_eligible_count == 1
