from datetime import UTC, datetime
from pathlib import Path

from newseviday_pipeline.models import TopicConfig
from newseviday_pipeline.runner import run_fixture_pipeline
from newseviday_pipeline.snapshot import load_snapshot

FIXTURE = Path(__file__).parent / "fixtures" / "arxiv-feed.xml"


def test_offline_fixture_pipeline_publishes_only_relevant_unique_articles(tmp_path: Path) -> None:
    topic = TopicConfig(
        id="semantic-layer",
        label="Semantic Layer",
        keywords=["semantic layer", "data agent"],
    )
    run, snapshot = run_fixture_pipeline(
        FIXTURE,
        tmp_path,
        source_id="arxiv-cs-ai",
        language="en",
        topics=[topic],
        config_version=1,
        now=datetime(2026, 8, 1, tzinfo=UTC),
    )

    assert run.status == "succeeded"
    assert [stage.stage for stage in run.stages] == [
        "fetch",
        "extract",
        "normalize",
        "exact_dedup",
        "fuzzy_dedup",
        "select",
        "snapshot",
    ]
    assert len(snapshot.articles) == 1
    assert snapshot.articles[0].ai is None
    assert load_snapshot(tmp_path / "current.json").snapshot_id == snapshot.snapshot_id
