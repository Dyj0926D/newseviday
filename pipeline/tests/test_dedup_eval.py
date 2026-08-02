from pathlib import Path

from newseviday_pipeline.dedup_eval import evaluate_dedup_dataset


def test_dedup_engineering_dataset_is_reproducible() -> None:
    root = Path(__file__).resolve().parents[1]
    result = evaluate_dedup_dataset(root / "eval" / "dedup-gold-v1.json")

    assert result.sample_count == 24
    assert result.review_status == "engineering_draft_pending_human_review"
    assert result.precision >= 0.9
    assert result.recall >= 0.8
