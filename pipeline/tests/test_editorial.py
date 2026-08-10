from datetime import timedelta
from pathlib import Path

from newseviday_pipeline.editorial import apply_editorial_package, load_editorial_package
from newseviday_pipeline.snapshot import load_snapshot
from newseviday_pipeline.stages import chinese_display_ready

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "apps" / "web" / "public" / "data" / "current.json"
PACKAGE = ROOT / "data" / "editorial" / "近期中文与首期周报-2026-08-10.json"


def test_editorial_package_fills_the_recent_chinese_feed_and_first_brief() -> None:
    snapshot = load_snapshot(SNAPSHOT)
    package = load_editorial_package(PACKAGE)

    result = apply_editorial_package(snapshot, package)
    cutoff = result.generated_at - timedelta(days=30)
    recent = [
        article
        for article in result.articles
        if (article.published_at or article.collected_at) >= cutoff
    ]

    assert len(package.articles) == 14
    assert len(recent) == 20
    assert all(chinese_display_ready(article) for article in recent)
    editorial_count = sum(
        article.ai is not None and article.ai.provider == "editorial"
        for article in result.articles
    )
    assert editorial_count == 14
    assert len(result.briefs) == 1
    evidence_sources = {evidence.id: evidence.source_id for evidence in result.evidence}
    assert all(
        len({evidence_sources[item] for item in section.evidence_ids}) >= 2
        for section in result.briefs[0].sections
    )
