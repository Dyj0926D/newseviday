from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from newseviday_pipeline.ai import (
    DeepSeekStructuredClient,
    FileAiCache,
    enhance_profile,
    enrich_snapshot,
)
from newseviday_pipeline.ai_models import ArticleEnrichment
from newseviday_pipeline.models import TopicConfig
from newseviday_pipeline.snapshot import load_snapshot
from newseviday_pipeline.terminology import TerminologyConfig, TermRule, terminology_consistency


class FakeStructuredClient:
    model = "deepseek-test"

    def __init__(self) -> None:
        self.calls = 0
        self.users: list[str] = []

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        self.calls += 1
        self.users.append(user)
        if "用户输入" in user:
            return {
                "role": "AI 产品经理",
                "work": "数据中台与 Data Agent",
                "goal": "跟踪统一语义",
                "description": "关注可信数据产品",
                "interests": [
                    {"topicId": "data-agent", "weight": 5, "reason": "当前工作"},
                    {"topicId": "unknown", "weight": 5, "reason": "不应保留"},
                ],
                "inferredTerms": ["Data Agent"],
                "warnings": [],
            }
        return {
            "titleZh": "语义层成为可信 Data Agent 的指标入口",
            "summaryZh": (
                "统一语义层集中治理指标口径和访问权限，"
                "为 Data Agent 提供可以追溯的数据查询基础。"
            ),
            "whyItMatters": "这会影响企业数据产品的准确率、权限边界和可解释性。",
            "keyPoints": ["指标口径集中治理", "查询结果可以追溯"],
            "topicIds": ["data-agent"],
        }


def topic() -> TopicConfig:
    return TopicConfig(id="data-agent", label="Data Agent", keywords=["data agent"])


def test_deepseek_v4_request_explicitly_disables_thinking(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

    def fake_post(*_args: Any, **kwargs: Any) -> FakeResponse:
        captured.update(kwargs["json"])
        return FakeResponse()

    monkeypatch.setattr("newseviday_pipeline.ai.httpx.post", fake_post)
    client = DeepSeekStructuredClient(api_key="test-key", model="deepseek-v4-flash")

    assert client.complete_json(system="system", user="user") == {"ok": True}
    assert captured["thinking"] == {"type": "disabled"}
    assert captured["temperature"] == 0.1


def test_article_enrichment_uses_one_call_and_content_hash_cache(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    snapshot.articles = snapshot.articles[:1]
    client = FakeStructuredClient()
    cache = FileAiCache(tmp_path)

    first, first_calls = enrich_snapshot(
        snapshot,
        client=client,
        cache=cache,
        topics=[topic()],
        now=datetime(2026, 8, 2, tzinfo=UTC),
    )
    second_client = FakeStructuredClient()
    second, second_calls = enrich_snapshot(
        snapshot,
        client=second_client,
        cache=cache,
        topics=[topic()],
        now=datetime(2026, 8, 2, tzinfo=UTC),
    )

    assert first_calls == 1
    assert second_calls == 0
    assert first.articles[0].ai is not None
    assert second.articles[0].ai == first.articles[0].ai
    assert first.articles[0].topic_scores["data-agent"] == 1.0


def test_article_enrichment_never_exceeds_hard_call_cap(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    snapshot.articles = snapshot.articles[:3]
    original_third_model = snapshot.articles[2].ai.model if snapshot.articles[2].ai else None
    client = FakeStructuredClient()

    result, model_calls = enrich_snapshot(
        snapshot,
        client=client,
        cache=FileAiCache(tmp_path),
        topics=[topic()],
        max_model_calls=2,
        now=datetime(2026, 8, 5, tzinfo=UTC),
    )

    assert model_calls == 2
    assert client.calls == 2
    assert result.articles[0].ai is not None
    assert result.articles[0].ai.model == "deepseek-test"
    assert result.articles[2].ai is not None
    assert result.articles[2].ai.model == original_third_model


def test_article_enrichment_injects_relevant_terminology(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    snapshot.articles = snapshot.articles[:1]
    snapshot.articles[0].facts.title = "RAG evaluation update"
    snapshot.articles[0].facts.abstract = "RAG systems need reproducible evaluation."
    client = FakeStructuredClient()
    terminology = TerminologyConfig(
        version=1,
        terms=[TermRule(source="RAG", preferredZh="RAG", allowedAliases=[])],
    )

    enrich_snapshot(
        snapshot,
        client=client,
        cache=FileAiCache(tmp_path),
        topics=[topic()],
        terminology=terminology,
    )

    assert "RAG -> RAG" in client.users[0]
    assert "titleZh 或 summaryZh 必须保留该概念" in client.users[0]


def test_article_enrichment_rejects_call_cap_above_ten(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")

    try:
        enrich_snapshot(
            snapshot,
            client=FakeStructuredClient(),
            cache=FileAiCache(tmp_path),
            topics=[topic()],
            max_model_calls=11,
        )
    except ValueError as error:
        assert str(error) == "max_model_calls_must_be_between_0_and_10"
    else:
        raise AssertionError("call cap above ten must be rejected")


def test_profile_enhancement_drops_topics_outside_public_configuration() -> None:
    result = enhance_profile(
        {"role": "AI 产品经理", "work": "Data Agent"},
        client=FakeStructuredClient(),
        topics=[topic()],
    )

    assert [item.topic_id for item in result.interests] == ["data-agent"]


def test_article_enrichment_schema_rejects_incomplete_payload() -> None:
    try:
        ArticleEnrichment.model_validate({"titleZh": "只有标题"})
    except ValueError:
        pass
    else:
        raise AssertionError("incomplete model output must be rejected")


def test_terminology_consistency_is_measurable(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    config = TerminologyConfig(
        version=1,
        terms=[TermRule(source="Semantic", preferredZh="语义层", allowedAliases=[])],
    )
    assert terminology_consistency(snapshot.articles, config) == 1.0


def test_terminology_consistency_does_not_penalize_omitted_concepts() -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    article = snapshot.articles[0]
    assert article.ai is not None
    article.facts.title = "Metadata platform update"
    article.facts.abstract = "A new metadata catalog is available."
    article.ai.title_zh = "平台目录更新"
    article.ai.summary_zh = "新版本调整了目录体验。"
    config = TerminologyConfig(
        version=1,
        terms=[TermRule(source="Metadata", preferredZh="元数据", allowedAliases=[])],
    )

    assert terminology_consistency([article], config) == 1.0


def test_terminology_consistency_rejects_unapproved_retained_terms() -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    article = snapshot.articles[0]
    assert article.ai is not None
    article.facts.title = "Metadata platform update"
    article.ai.title_zh = "Metadata 平台更新"
    article.ai.summary_zh = "新版本调整了目录体验。"
    config = TerminologyConfig(
        version=1,
        terms=[TermRule(source="Metadata", preferredZh="元数据", allowedAliases=[])],
    )

    assert terminology_consistency([article], config) == 0.0
