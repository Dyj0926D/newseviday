from datetime import UTC, datetime
from pathlib import Path

from newseviday_pipeline.embeddings import HashingEmbedder
from newseviday_pipeline.evaluation import evaluate_rag, load_gold_dataset
from newseviday_pipeline.rag import build_dense_index
from newseviday_pipeline.snapshot import load_snapshot

ROOT = Path(__file__).resolve().parents[2]
TRIAL_SNAPSHOT = ROOT / "apps" / "web" / "public" / "data" / "current.json"
DATASET = ROOT / "pipeline" / "eval" / "rag-gold-trial-v2.json"


def test_unreviewed_trial_eval_cannot_pass_production_gate() -> None:
    snapshot = load_snapshot(TRIAL_SNAPSHOT)
    dataset = load_gold_dataset(DATASET)
    embedder = HashingEmbedder()
    index = build_dense_index(snapshot, embedder)
    report = evaluate_rag(
        snapshot,
        index,
        dataset,
        embedder,
        now=datetime(2026, 8, 2, tzinfo=UTC),
    )

    assert len(dataset.questions) == 24
    assert report.run.sample_count == 24
    assert report.run.gate == "fail"
    assert report.dataset_kind == "production"
    assert report.review_status == "trial_draft_pending_human_review"
    assert report.corpus_health.passed
    assert report.run.metrics.recall_at5 >= 0.75
    assert report.answer_quality.citation_coverage is None
    assert report.answer_quality.no_answer_accuracy >= 0.8
    assert (
        report.answer_quality.low_score_refusal_accuracy
        < report.answer_quality.no_answer_accuracy
    )
    assert report.answer_quality.answerable_pass_rate >= 0.9
