import json
from datetime import UTC, datetime
from pathlib import Path

from newseviday_pipeline.quality import audit_snapshot, write_quality_report
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
    assert "potentialStoryClusters" in payload
