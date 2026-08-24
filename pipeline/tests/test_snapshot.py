from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from newseviday_pipeline.models import ContentSnapshot
from newseviday_pipeline.snapshot import SnapshotPublisher, load_snapshot


def empty_snapshot(snapshot_id: str) -> ContentSnapshot:
    return ContentSnapshot(
        snapshot_id=snapshot_id,
        generated_at=datetime(2026, 8, 1, tzinfo=UTC),
        pipeline_run_id="pipeline-test",
        state="empty",
        source_count=0,
    )


def test_snapshot_publisher_keeps_versions_and_updates_current_atomically(tmp_path: Path) -> None:
    publisher = SnapshotPublisher(tmp_path)
    publisher.publish(empty_snapshot("snapshot-1"))
    publisher.publish(empty_snapshot("snapshot-2"))

    assert load_snapshot(tmp_path / "current.json").snapshot_id == "snapshot-2"
    assert (tmp_path / "versions" / "snapshot-1.json").exists()
    assert (tmp_path / "versions" / "snapshot-2.json").exists()


def test_invalid_snapshot_never_replaces_current(tmp_path: Path) -> None:
    publisher = SnapshotPublisher(tmp_path)
    publisher.publish(empty_snapshot("snapshot-safe"))
    before = (tmp_path / "current.json").read_text(encoding="utf-8")

    with pytest.raises(ValidationError):
        publisher.publish_payload({"schemaVersion": "1.0.0", "snapshotId": "broken"})

    assert (tmp_path / "current.json").read_text(encoding="utf-8") == before


def test_published_web_snapshot_conforms_to_python_contract() -> None:
    project_root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(project_root / "apps" / "web" / "public" / "data" / "current.json")

    assert snapshot.snapshot_kind == "production"
    assert snapshot.source_count == len(snapshot.sources)
    assert 1 <= len(snapshot.articles) <= 40
    assert any(article.ai and article.ai.why_it_matters for article in snapshot.articles)
