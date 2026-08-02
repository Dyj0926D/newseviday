from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from newseviday_pipeline.ai import FileAiCache, enhance_profile, enrich_snapshot
from newseviday_pipeline.ai_models import ArticleEnrichment
from newseviday_pipeline.models import TopicConfig
from newseviday_pipeline.snapshot import load_snapshot
from newseviday_pipeline.terminology import TerminologyConfig, TermRule, terminology_consistency


class FakeStructuredClient:
    model = "deepseek-test"

    def __init__(self) -> None:
        self.calls = 0

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        self.calls += 1
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
