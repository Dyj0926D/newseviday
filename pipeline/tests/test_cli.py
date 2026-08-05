import json
from pathlib import Path

from pytest import CaptureFixture

from newseviday_pipeline.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "arxiv-feed.xml"


def test_doctor_reports_safe_local_state(capsys: CaptureFixture[str]) -> None:
    assert main(["doctor"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["ok"] is True
    assert payload["mode"] == "archive"
    assert payload["enabledSources"] == 9
    assert payload["aiEnabled"] is False


def test_dry_run_does_not_use_network_or_models(capsys: CaptureFixture[str]) -> None:
    assert main(["run", "--dry-run"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["dryRun"] is True
    assert payload["networkAccess"] is False
    assert payload["modelCalls"] is False


def test_fixture_run_remains_offline_and_model_free(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    assert main(["run", "--fixture", str(FIXTURE), "--output", str(tmp_path)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["networkAccess"] is False
    assert payload["modelCalls"] is False
    assert (tmp_path / "current.json").exists()


def test_enrich_rejects_call_cap_above_ten(capsys: CaptureFixture[str]) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = root / "apps" / "web" / "public" / "data" / "current.json"

    assert (
        main(
            [
                "enrich",
                str(snapshot),
                "--allow-model",
                "--max-model-calls",
                "11",
            ]
        )
        == 2
    )
    assert "between 0 and 10" in capsys.readouterr().out


def test_publish_web_keeps_an_immutable_snapshot_version(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = root / "apps" / "web" / "public" / "data" / "current.json"
    snapshot_id = json.loads(snapshot.read_text(encoding="utf-8"))["snapshotId"]
    web_data = tmp_path / "web-data"

    assert main(["publish-web", str(snapshot), "--web-data", str(web_data)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert (web_data / "current.json").read_bytes() == snapshot.read_bytes()
    assert (web_data / "versions" / f"{snapshot_id}.json").read_bytes() == snapshot.read_bytes()
    assert Path(payload["versionPath"]).name == f"{snapshot_id}.json"
