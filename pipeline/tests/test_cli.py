import json
from pathlib import Path

import pytest
from pytest import CaptureFixture, MonkeyPatch

from newseviday_pipeline.cli import _token_prices_from_environment, main

FIXTURE = Path(__file__).parent / "fixtures" / "arxiv-feed.xml"


def test_doctor_reports_safe_local_state(capsys: CaptureFixture[str]) -> None:
    assert main(["doctor"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["ok"] is True
    assert payload["mode"] == "archive"
    assert payload["enabledSources"] == 15
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


def test_key_signal_eval_cli_writes_a_gate_report(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    root = Path(__file__).resolve().parents[2]
    dataset = root / "pipeline" / "eval" / "key-signal-gold-v1.json"
    report = tmp_path / "key-signal-eval.json"

    assert main(["eval-key-signal", str(dataset), "--report", str(report)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["gate"] == "pass"
    assert payload["eligibility"]["f1"] == 1.0
    assert payload["eventTypeExactAccuracy"] == 1.0
    assert report.exists()


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


def test_token_prices_are_optional_but_must_be_configured_together(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_INPUT_CNY_PER_MILLION", raising=False)
    monkeypatch.delenv("DEEPSEEK_OUTPUT_CNY_PER_MILLION", raising=False)
    assert _token_prices_from_environment() == (None, None)

    monkeypatch.setenv("DEEPSEEK_INPUT_CNY_PER_MILLION", "2")
    monkeypatch.setenv("DEEPSEEK_OUTPUT_CNY_PER_MILLION", "4")
    assert _token_prices_from_environment() == (2.0, 4.0)

    monkeypatch.delenv("DEEPSEEK_OUTPUT_CNY_PER_MILLION")
    with pytest.raises(ValueError, match="configured_together"):
        _token_prices_from_environment()


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
    manifest = json.loads((web_data / "archive" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["snapshots"][0]["snapshotId"] == snapshot_id
    assert len(manifest["articles"]) == 40
    assert manifest["articles"][0]["snapshotPath"] == f"versions/{snapshot_id}.json"
