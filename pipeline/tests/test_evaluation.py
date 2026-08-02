from datetime import UTC, datetime
from pathlib import Path

from newseviday_pipeline.embeddings import HashingEmbedder
from newseviday_pipeline.evaluation import evaluate_rag, load_gold_dataset
from newseviday_pipeline.rag import build_dense_index
from newseviday_pipeline.snapshot import load_snapshot

ROOT = Path(__file__).resolve().parents[2]
DEMO_SNAPSHOT = ROOT / "apps" / "web" / "public" / "data" / "current.json"
DATASET = ROOT / "pipeline" / "eval" / "rag-gold-demo-v1.json"


def test_demo_eval_is_reproducible_and_never_passes_production_gate() -> None:
    snapshot = load_snapshot(DEMO_SNAPSHOT)
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

    assert len(dataset.questions) == 30
    assert report.run.sample_count == 30
    assert report.run.gate == "observe"
    assert report.dataset_kind == "demo"
    assert report.review_status == "engineering_draft_pending_human_review"
    assert report.corpus_health.passed
    assert report.run.metrics.recall_at5 >= 0.75
    assert report.answer_quality.citation_coverage is None
