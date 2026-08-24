from pathlib import Path

from newseviday_pipeline.agentic import plan_question, retrieve_with_agent
from newseviday_pipeline.embeddings import HashingEmbedder
from newseviday_pipeline.rag import build_dense_index
from newseviday_pipeline.snapshot import load_snapshot

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "apps" / "web" / "public" / "data" / "current.json"
PINNED_SNAPSHOT = (
    ROOT
    / "apps"
    / "web"
    / "public"
    / "data"
    / "versions"
    / "snapshot-20260805T035314Z-a2c2f64d-ai-07822422.json"
)


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


def test_comparison_planner_builds_two_anchored_subqueries() -> None:
    snapshot = load_snapshot(PINNED_SNAPSHOT)

    evaluation = plan_question(
        "推理系统评测和 agentic harness 评测为什么都要记录完整运行条件？",
        snapshot,
    )
    reliability = plan_question(
        "多模态智能体研究和实时安全模型分别在解决什么可靠性问题？",
        snapshot,
    )

    assert evaluation.route == "comparison"
    assert len(evaluation.subqueries) == 2
    assert "reasoning inference test-time scaling" in evaluation.subqueries[0]
    assert "agentic harness" in evaluation.subqueries[1]
    assert "comparison_coverage:2" in evaluation.requirements
    assert "multimodal video vision" in reliability.subqueries[0]
    assert "real-time streaming" in reliability.subqueries[1]
    assert "safety guardrail moderation" in reliability.subqueries[1]


def test_agentic_comparison_retrieval_preserves_both_required_sources() -> None:
    snapshot = load_snapshot(PINNED_SNAPSHOT)
    embedder = HashingEmbedder()
    index = build_dense_index(snapshot, embedder)
    cases = [
        (
            "推理系统评测和 agentic harness 评测为什么都要记录完整运行条件？",
            {
                "article-0a5a098d6f2d01ba23d0",
                "article-2e0b2f76a5b7e197d60e",
            },
        ),
        (
            "多模态智能体研究和实时安全模型分别在解决什么可靠性问题？",
            {
                "article-aa9f3addc6b0fbb2a1a0",
                "article-9173cc726336dababfa0",
            },
        ),
    ]

    for question, expected_ids in cases:
        result = retrieve_with_agent(question, snapshot, index, embedder)
        top_ids = {item.chunk.article_id for item in result.candidates[:5]}

        assert result.assessment.sufficient
        assert result.retrieval_rounds == 2
        assert expected_ids.issubset(top_ids)
        assert expected_ids == {
            item.chunk.article_id for item in result.candidates[:2]
        }


def test_revised_openai_question_ranks_supported_evidence_first() -> None:
    snapshot = load_snapshot(PINNED_SNAPSHOT)
    embedder = HashingEmbedder()
    index = build_dense_index(snapshot, embedder)

    result = retrieve_with_agent(
        "OpenAI 针对第三方网络安全评测事件提出的总体改进方向是什么？",
        snapshot,
        index,
        embedder,
    )

    assert result.assessment.sufficient
    assert result.candidates[0].chunk.article_id == "article-c99ec862b4e71599bc42"
