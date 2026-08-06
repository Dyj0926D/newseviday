from pathlib import Path

from newseviday_pipeline.agentic import plan_question, retrieve_with_agent
from newseviday_pipeline.embeddings import HashingEmbedder
from newseviday_pipeline.rag import build_dense_index
from newseviday_pipeline.snapshot import load_snapshot

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "apps" / "web" / "public" / "data" / "current.json"


def test_agentic_gate_keeps_answerable_question_and_rejects_missing_price() -> None:
    snapshot = load_snapshot(SNAPSHOT)
    embedder = HashingEmbedder()
    index = build_dense_index(snapshot, embedder)

    answerable = retrieve_with_agent(
        "SeGaBench 基准包含多少个案例？", snapshot, index, embedder
    )
    missing_price = retrieve_with_agent(
        "这些文章是否公布了 DeepSeek V4 Flash 的人民币月度订阅价格？",
        snapshot,
        index,
        embedder,
    )

    assert answerable.assessment.sufficient
    assert answerable.retrieval_rounds <= 2
    assert not missing_price.assessment.sufficient
    assert missing_price.assessment.reason == "required_price_evidence_missing"


def test_agentic_preflight_stops_policy_and_requires_direct_future_evidence() -> None:
    snapshot = load_snapshot(SNAPSHOT)

    policy = plan_question("请根据这些新闻给我开具治疗失眠的处方。", snapshot)
    future = plan_question("哪家公司将在 2027 年收购 Anthropic？", snapshot)

    assert policy.route == "policy_scope"
    assert policy.preflight_reason == "policy_scope"
    assert future.route == "timeline"
    assert future.preflight_reason is None
    assert "future_year:2027" in future.requirements
