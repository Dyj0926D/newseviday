import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from newseviday_pipeline.inventory import merge_rolling_inventory
from newseviday_pipeline.quality import evaluate_release_guard
from newseviday_pipeline.snapshot import load_snapshot
from newseviday_pipeline.stages import chinese_display_ready

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "apps" / "web" / "public" / "data" / "current.json"


def _fresh_candidate(*, chinese_ready_count: int):
    accepted = load_snapshot(SNAPSHOT)
    incoming = accepted.model_copy(deep=True)
    incoming.snapshot_id = "snapshot-fresh"
    incoming.generated_at = datetime(2026, 8, 13, 4, tzinfo=UTC)
    incoming.briefs = []
    incoming.evidence = []
    source_ids = [source.id for source in accepted.sources if source.id != "arxiv-cs-ai"]
    template_ai = next(article.ai for article in accepted.articles if article.ai is not None)
    incoming.articles = []
    for index in range(30):
        article = accepted.articles[index % len(accepted.articles)].model_copy(deep=True)
        article.id = f"article-fresh-{index:02d}"
        article.source_id = source_ids[index % len(source_ids)]
        article.canonical_url = f"https://example.com/fresh/{index}"
        article.content_hash = hashlib.sha256(f"fresh-{index}".encode()).hexdigest()
        article.facts.title = f"Fresh engineering item {index}"
        article.facts.abstract = "A complete engineering source abstract. " * 8
        article.language = "en"
        article.published_at = incoming.generated_at - timedelta(hours=index)
        article.collected_at = incoming.generated_at
        article.evidence_ids = []
        article.ai = template_ai.model_copy(deep=True) if index < chinese_ready_count else None
        incoming.articles.append(article)
    return accepted, incoming


def test_rolling_inventory_preserves_published_chinese_content() -> None:
    accepted, incoming = _fresh_candidate(chinese_ready_count=0)

    result = merge_rolling_inventory(incoming, accepted)

    assert len(result.articles) == 40
    assert sum(chinese_display_ready(article) for article in result.articles) >= 20
    assert any(
        article.content_hash in {item.content_hash for item in accepted.articles}
        for article in result.articles
    )
    assert result.articles == sorted(
        result.articles,
        key=lambda article: (
            chinese_display_ready(article),
            article.published_at or article.collected_at,
            article.content_score or 0,
        ),
        reverse=True,
    )


def test_rolling_inventory_reserves_a_fresh_focus_topic_candidate() -> None:
    accepted, incoming = _fresh_candidate(chinese_ready_count=0)
    candidate = incoming.articles[0]
    candidate.id = "article-fresh-data-agent"
    candidate.content_hash = hashlib.sha256(b"fresh-data-agent").hexdigest()
    candidate.canonical_url = "https://example.com/fresh-data-agent"
    candidate.source_id = "databricks-blog"
    candidate.source_type = "official"
    candidate.topic_scores = {"data-agent": 0.65}
    assert candidate.content_score_breakdown is not None
    candidate.content_score_breakdown.target_relevance = 0.65
    candidate.facts.title = "Designing effective Genie Agents from a single prompt"
    candidate.facts.abstract = (
        "Ask a governed data agent about revenue and route it to the approved metric."
    )

    result = merge_rolling_inventory(incoming, accepted)

    assert any(article.id == candidate.id for article in result.articles)


def test_release_guard_passes_after_five_new_chinese_items() -> None:
    accepted, incoming = _fresh_candidate(chinese_ready_count=5)
    candidate = merge_rolling_inventory(incoming, accepted)

    report = evaluate_release_guard(
        candidate,
        accepted,
        now=incoming.generated_at,
    )

    assert sum(chinese_display_ready(article) for article in candidate.articles) >= 25
    assert report.gate == "pass"


def test_release_guard_blocks_an_untranslated_inventory_regression() -> None:
    accepted, incoming = _fresh_candidate(chinese_ready_count=0)

    report = evaluate_release_guard(
        incoming,
        accepted,
        now=incoming.generated_at,
    )

    assert report.gate == "fail"
    assert "近 30 天中文可读内容占比下降过多" in report.issues


def test_release_guard_warns_without_blocking_when_inventory_has_no_fresh_change() -> None:
    accepted = load_snapshot(SNAPSHOT)
    candidate = accepted.model_copy(deep=True)
    candidate.snapshot_id = "snapshot-metadata-refresh"
    now = datetime(2026, 8, 20, 3, tzinfo=UTC)
    candidate.generated_at = now

    report = evaluate_release_guard(candidate, accepted, now=now)

    assert report.gate == "pass"
    assert report.new_article_count == 0
    assert "候选与线上库存没有新增文章" in report.warnings
