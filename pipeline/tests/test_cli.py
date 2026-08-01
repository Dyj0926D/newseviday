import json

from pytest import CaptureFixture

from newseviday_pipeline.cli import main


def test_doctor_reports_safe_local_state(capsys: CaptureFixture[str]) -> None:
    assert main(["doctor"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["ok"] is True
    assert payload["mode"] == "archive"
    assert payload["enabledSources"] == 0
    assert payload["aiEnabled"] is False


def test_dry_run_does_not_use_network_or_models(capsys: CaptureFixture[str]) -> None:
    assert main(["run", "--dry-run"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["dryRun"] is True
    assert payload["networkAccess"] is False
    assert payload["modelCalls"] is False
