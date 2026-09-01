from pathlib import Path

from newseviday_pipeline.ai import FileAiCache
from newseviday_pipeline.answer_evaluation import (
    analyze_answer_claims,
    build_answer_review_packet,
    summarize_answer_review,
)
from newseviday_pipeline.embeddings import HashingEmbedder
from newseviday_pipeline.evaluation import load_gold_dataset
from newseviday_pipeline.rag import build_dense_index
from newseviday_pipeline.snapshot import load_snapshot

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "pipeline" / "eval" / "rag-gold-trial-v3.json"


class FakeTextClient:
    model = "fake-rag-model"

    def __init__(self) -> None:
        self.calls = 0

    def complete_text(self, *, system: str, user: str) -> str:
        assert "只使用提供的证据" in system
        assert "untrusted-evidence" in user
        self.calls += 1
        return "第一项事实来自证据。[1]\n第二项事实也有证据。[2]"


def _fixture() -> tuple[object, object, object, HashingEmbedder]:
    dataset = load_gold_dataset(DATASET)
    snapshot = load_snapshot(
        ROOT
        / "apps"
        / "web"
        / "public"
        / "data"
        / "versions"
        / f"{dataset.corpus_snapshot_id}.json"
    )
    embedder = HashingEmbedder()
    return snapshot, build_dense_index(snapshot, embedder), dataset, embedder


def test_claim_parser_detects_missing_and_invalid_citations() -> None:
    claims, invalid = analyze_answer_claims(
        "有证据的事实。[1]\n没有引用的事实。\n错误引用。[9]",
        citation_count=2,
    )

    assert len(claims) == 3
    assert claims[0].citation_valid
    assert not claims[1].citation_present
    assert not claims[2].citation_valid
    assert invalid == [9]


def test_answer_harness_is_bounded_cached_and_human_gated(tmp_path: Path) -> None:
    snapshot, index, dataset, embedder = _fixture()
    client = FakeTextClient()
    packet = build_answer_review_packet(
        snapshot,
        index,
        dataset,
        embedder,
        client=client,
        cache=FileAiCache(tmp_path / "cache"),
        maximum_model_calls=2,
    )

    assert client.calls == 2
    assert packet.model_calls == 2
    assert packet.summary.generated_case_count == 2
    assert packet.summary.pending_model_call_count == 10
    assert packet.summary.citation_coverage == 1.0
    assert packet.summary.gate == "pending"
    assert packet.cases[0].retriever_input
    assert packet.cases[0].ranked_candidates
    assert packet.cases[0].injected_context

    generated_cases = [case for case in packet.cases if case.answer]
    for case in generated_cases:
        case.human_review.answer_correct = True
        case.human_review.answer_complete = True
        for claim in case.claims:
            claim.human_citation_support = True
    summary = summarize_answer_review(packet.cases)
    assert summary.citation_faithfulness == 1.0
    assert not summary.human_review_complete or summary.pending_model_call_count > 0

    cached_client = FakeTextClient()
    cached_packet = build_answer_review_packet(
        snapshot,
        index,
        dataset,
        embedder,
        client=cached_client,
        cache=FileAiCache(tmp_path / "cache"),
        maximum_model_calls=0,
    )
    assert cached_client.calls == 0
    assert cached_packet.summary.generated_case_count == 2
