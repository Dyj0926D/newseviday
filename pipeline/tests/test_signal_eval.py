from pathlib import Path

from newseviday_pipeline.signal_eval import (
    evaluate_key_signal_dataset,
    write_key_signal_eval_report,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "pipeline" / "eval" / "key-signal-gold-v1.json"


def test_key_signal_eval_harness_passes_cross_event_gold_set(tmp_path: Path) -> None:
    report = evaluate_key_signal_dataset(DATASET)
    output = tmp_path / "key-signal-eval.json"
    write_key_signal_eval_report(report, output)

    assert report.gate == "pass"
    assert report.case_count == 12
    assert report.eligibility.precision == 1.0
    assert report.eligibility.recall == 1.0
    assert report.high_significance.precision == 1.0
    assert report.high_significance.recall == 1.0
    assert report.event_type_exact_accuracy == 1.0
    assert output.exists()
