from datetime import UTC, datetime
from pathlib import Path

from newseviday_pipeline.embeddings import HashingEmbedder
from newseviday_pipeline.evaluation import (
    build_rag_review_packet,
    evaluate_rag,
    load_gold_dataset,
)
from newseviday_pipeline.rag import build_dense_index
from newseviday_pipeline.snapshot import load_snapshot

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "pipeline" / "eval" / "rag-gold-trial-v3.json"


def test_unreviewed_trial_eval_cannot_pass_production_gate() -> None:
    dataset = load_gold_dataset(DATASET)
    trial_snapshot = (
        ROOT
        / "apps"
        / "web"
        / "public"
        / "data"
        / "versions"
        / f"{dataset.corpus_snapshot_id}.json"
    )
    snapshot = load_snapshot(trial_snapshot)
    assert snapshot.snapshot_id == dataset.corpus_snapshot_id
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
    assert report.run.metrics.recall_at5 == 1.0
    assert report.run.metrics.hit_at5 == 1.0
    assert report.answer_quality.citation_coverage is None
    assert report.answer_quality.no_answer_accuracy >= 0.8
    assert (
        report.answer_quality.low_score_refusal_accuracy
        < report.answer_quality.no_answer_accuracy
    )
    assert report.answer_quality.answerable_pass_rate >= 0.9


def test_rag_review_packet_exposes_candidates_and_blank_human_labels() -> None:
    dataset = load_gold_dataset(DATASET)
    trial_snapshot = (
        ROOT
        / "apps"
        / "web"
        / "public"
        / "data"
        / "versions"
        / f"{dataset.corpus_snapshot_id}.json"
    )
    snapshot = load_snapshot(trial_snapshot)
    embedder = HashingEmbedder()
    index = build_dense_index(snapshot, embedder)

    packet = build_rag_review_packet(
        snapshot,
        index,
        dataset,
        embedder,
        now=datetime(2026, 8, 20, tzinfo=UTC),
    )

    assert len(packet.cases) == 24
    assert packet.review_status == "pending_human_review"
    assert packet.cases[0].candidates
    assert packet.cases[0].human_review.retrieval_evidence_correct is None
    assert packet.cases[12].answerable is False
