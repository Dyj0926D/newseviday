from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from newseviday_pipeline.ai import (
    DeepSeekStructuredClient,
    EnrichmentTelemetry,
    FileAiCache,
    enhance_profile,
    enrich_snapshot,
)
from newseviday_pipeline.ai_models import ArticleEnrichment
from newseviday_pipeline.models import TopicConfig
from newseviday_pipeline.snapshot import load_snapshot
from newseviday_pipeline.stages import apply_article_scoring
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
                "统一语义层集中治理指标口径和访问权限，为 Data Agent 提供可以追溯的数据查询基础。"
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
            return {
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 30,
                    "total_tokens": 150,
                },
            }

    def fake_post(*_args: Any, **kwargs: Any) -> FakeResponse:
        captured.update(kwargs["json"])
        return FakeResponse()

    monkeypatch.setattr("newseviday_pipeline.ai.httpx.post", fake_post)
    client = DeepSeekStructuredClient(api_key="test-key", model="deepseek-v4-flash")

    assert client.complete_json(system="system", user="user") == {"ok": True}
    assert captured["thinking"] == {"type": "disabled"}
    assert captured["temperature"] == 0.1
    assert client.usage_reported_calls == 1
    assert client.usage_totals.prompt_tokens == 120
    assert client.usage_totals.completion_tokens == 30
    assert client.usage_totals.total_tokens == 150


def test_article_enrichment_uses_one_call_and_content_hash_cache(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    snapshot.articles = snapshot.articles[:1]
    snapshot.articles[0].topic_scores = {"semantic-layer": 0.6}
    snapshot.articles[0].ai = None
    client = FakeStructuredClient()
    cache = FileAiCache(tmp_path)
    first_telemetry = EnrichmentTelemetry()

    first, first_calls = enrich_snapshot(
        snapshot,
        client=client,
        cache=cache,
        topics=[topic()],
        now=datetime(2026, 8, 2, tzinfo=UTC),
        telemetry=first_telemetry,
    )
    second_client = FakeStructuredClient()
    second_telemetry = EnrichmentTelemetry()
    second, second_calls = enrich_snapshot(
        snapshot,
        client=second_client,
        cache=cache,
        topics=[topic()],
        now=datetime(2026, 8, 2, tzinfo=UTC),
        telemetry=second_telemetry,
    )

    assert first_calls == 1
    assert second_calls == 0
    assert first.articles[0].ai is not None
    assert second.articles[0].ai == first.articles[0].ai
    assert first.articles[0].topic_scores == {"semantic-layer": 0.6}
    assert first_telemetry.model_calls == 1
    assert first_telemetry.cache_hits == 0
    assert second_telemetry.model_calls == 0
    assert second_telemetry.cache_hits == 1


def test_article_enrichment_never_exceeds_hard_call_cap(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    snapshot.articles = snapshot.articles[:3]
    for article in snapshot.articles:
        article.ai = None
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
    assert sum(article.ai is not None for article in result.articles) == 2
    assert (
        sum(
            article.ai is not None and article.ai.model == "deepseek-test"
            for article in result.articles
        )
        == 2
    )


def test_article_enrichment_skips_thin_source_evidence(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    snapshot.articles = snapshot.articles[:2]
    thin, supported = snapshot.articles
    thin.source_id = "source-thin"
    thin.content_score = 1.0
    thin.facts.abstract = "Only a short announcement is available."
    thin.ai = None
    supported.source_id = "source-supported"
    supported.content_score = 0.9
    supported.facts.abstract = "A sufficiently detailed source excerpt. " * 8
    supported.ai = None
    client = FakeStructuredClient()

    result, model_calls = enrich_snapshot(
        snapshot,
        client=client,
        cache=FileAiCache(tmp_path),
        topics=[topic()],
        max_model_calls=1,
    )

    assert model_calls == 1
    assert result.articles[0].ai is None
    assert result.articles[1].ai is not None


def test_article_enrichment_rotates_across_sources(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    snapshot.articles = snapshot.articles[:4]
    snapshot.articles[0].source_id = "source-a"
    snapshot.articles[1].source_id = "source-a"
    snapshot.articles[2].source_id = "source-b"
    snapshot.articles[3].source_id = "source-c"
    for article in snapshot.articles:
        article.ai = None
        article.key_signal = None
        article.content_score = 0.8
        article.published_at = datetime(2026, 8, 5, tzinfo=UTC)
        assert article.content_score_breakdown is not None
        article.content_score_breakdown.target_relevance = 0.8

    result, model_calls = enrich_snapshot(
        snapshot,
        client=FakeStructuredClient(),
        cache=FileAiCache(tmp_path),
        topics=[topic()],
        max_model_calls=3,
    )

    assert model_calls == 3
    assert result.articles[0].ai is not None
    assert result.articles[0].ai.model == "deepseek-test"
    assert result.articles[1].ai is None
    assert result.articles[2].ai is not None
    assert result.articles[2].ai.model == "deepseek-test"
    assert result.articles[3].ai is not None
    assert result.articles[3].ai.model == "deepseek-test"


def test_article_enrichment_translates_key_candidate_before_a_higher_raw_score(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    snapshot.articles = snapshot.articles[:2]
    key_candidate, other = snapshot.articles
    key_candidate.source_id = "official-platform"
    key_candidate.language = "en"
    key_candidate.facts.title = (
        "Open-source data agent platform benchmark improves production latency by 35%"
    )
    key_candidate.facts.abstract = (
        "We introduce a general-purpose framework, API, deployment workflow and dataset. "
        "Evaluation across models shows higher throughput and lower cost than baseline. "
    ) * 3
    key_candidate.topic_scores = {"data-agent": 1.0, "semantic-layer": 0.8}
    key_candidate.ai = None
    apply_article_scoring(key_candidate, anchor=key_candidate.collected_at)

    other.source_id = "other-source"
    other.language = "en"
    other.facts.title = "Modern Greek specialist dataset"
    other.facts.abstract = "A narrow specialist language dataset and benchmark. " * 5
    other.topic_scores = {"foundation-models": 0.8}
    other.ai = None
    apply_article_scoring(other, anchor=other.collected_at)
    other.content_score = 0.99

    result, model_calls = enrich_snapshot(
        snapshot,
        client=FakeStructuredClient(),
        cache=FileAiCache(tmp_path),
        topics=[topic()],
        max_model_calls=1,
    )

    assert model_calls == 1
    assert result.articles[0].ai is not None
    assert result.articles[0].ai.model == "deepseek-test"
    assert result.articles[1].ai is None


def test_article_enrichment_allows_a_major_event_below_profile_relevance_floor(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    snapshot.articles = snapshot.articles[:1]
    article = snapshot.articles[0]
    now = datetime(2026, 8, 14, 3, 30, tzinfo=UTC)
    article.source_id = "official-model-updates"
    article.source_type = "official"
    article.evidence_tier = "primary"
    article.language = "en"
    article.published_at = datetime(2026, 8, 13, tzinfo=UTC)
    article.collected_at = now
    article.facts.title = "DeepSeek-V4-Pro Update"
    article.facts.abstract = (
        "The GA release has been rolled out on the APP, Web, and API. The model "
        "significantly enhances agent capabilities in production environments and reports "
        "multiple benchmark results. The API now natively supports the Responses API, "
        "thinking effort levels, and peak or off-peak pricing that takes effect this week. "
    ) * 2
    article.topic_scores = {"rag-eval": 0.55, "foundation-models": 0.425}
    article.ai = None
    apply_article_scoring(article, anchor=now)
    assert article.content_score_breakdown is not None
    assert article.content_score_breakdown.target_relevance < 0.6
    assert article.content_score_breakdown.event_significance >= 0.7

    result, model_calls = enrich_snapshot(
        snapshot,
        client=FakeStructuredClient(),
        cache=FileAiCache(tmp_path),
        topics=[topic()],
        max_model_calls=1,
        now=now,
    )

    assert model_calls == 1
    assert result.articles[0].ai is not None
    assert result.articles[0].key_signal is not None
    assert result.articles[0].key_signal.eligible


def test_article_enrichment_injects_relevant_terminology(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    snapshot.articles = snapshot.articles[:1]
    snapshot.articles[0].facts.title = "RAG evaluation update"
    snapshot.articles[0].facts.abstract = (
        "RAG systems need reproducible evaluation across retrieval, ranking, citation, "
        "latency, and refusal cases. The source describes a complete repeatable protocol."
    )
    snapshot.articles[0].ai = None
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


def test_article_enrichment_reuses_published_ai_below_new_call_floor(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    accepted = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    accepted.articles = accepted.articles[:1]
    assert accepted.articles[0].ai is not None
    incoming = accepted.model_copy(deep=True)
    incoming.articles[0].ai = None
    incoming.articles[0].content_score = 0.2
    telemetry = EnrichmentTelemetry()

    result, model_calls = enrich_snapshot(
        incoming,
        client=FakeStructuredClient(),
        cache=FileAiCache(tmp_path),
        topics=[topic()],
        accepted_snapshot=accepted,
        telemetry=telemetry,
        now=datetime(2026, 8, 10, tzinfo=UTC),
    )

    assert model_calls == 0
    assert result.articles[0].ai == accepted.articles[0].ai
    assert telemetry.accepted_enrichment_reuses == 1
    assert telemetry.skipped_below_quality_floor == 0


def test_article_enrichment_does_not_pay_for_low_value_backlog(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    snapshot.articles = snapshot.articles[:1]
    article = snapshot.articles[0]
    article.ai = None
    article.content_score = 0.59
    article.facts.abstract = "Detailed but low-priority source evidence. " * 8
    telemetry = EnrichmentTelemetry()
    client = FakeStructuredClient()

    result, model_calls = enrich_snapshot(
        snapshot,
        client=client,
        cache=FileAiCache(tmp_path),
        topics=[topic()],
        telemetry=telemetry,
        now=datetime(2026, 8, 10, tzinfo=UTC),
    )

    assert model_calls == 0
    assert client.calls == 0
    assert result.articles[0].ai is None
    assert telemetry.skipped_below_quality_floor == 1


def test_article_enrichment_does_not_pay_for_stale_backlog(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    snapshot.articles = snapshot.articles[:1]
    article = snapshot.articles[0]
    article.ai = None
    article.content_score = 0.9
    article.published_at = datetime(2026, 5, 1, tzinfo=UTC)
    article.facts.abstract = "High-quality but stale source evidence. " * 8
    telemetry = EnrichmentTelemetry()

    _result, model_calls = enrich_snapshot(
        snapshot,
        client=FakeStructuredClient(),
        cache=FileAiCache(tmp_path),
        topics=[topic()],
        telemetry=telemetry,
        now=datetime(2026, 8, 10, tzinfo=UTC),
    )

    assert model_calls == 0
    assert telemetry.skipped_stale == 1


def test_article_enrichment_requires_target_relevance_for_new_calls(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    snapshot.articles = snapshot.articles[:1]
    article = snapshot.articles[0]
    article.ai = None
    article.content_score = 0.9
    article.published_at = datetime(2026, 8, 9, tzinfo=UTC)
    article.facts.abstract = "Complete but weakly relevant evidence. " * 8
    assert article.content_score_breakdown is not None
    article.content_score_breakdown.target_relevance = 0.59
    telemetry = EnrichmentTelemetry()

    _result, model_calls = enrich_snapshot(
        snapshot,
        client=FakeStructuredClient(),
        cache=FileAiCache(tmp_path),
        topics=[topic()],
        telemetry=telemetry,
        now=datetime(2026, 8, 10, tzinfo=UTC),
    )

    assert model_calls == 0
    assert telemetry.skipped_below_quality_floor == 1


def test_article_enrichment_caps_new_items_per_source(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    snapshot = load_snapshot(root / "apps" / "web" / "public" / "data" / "current.json")
    snapshot.articles = snapshot.articles[:4]
    for article in snapshot.articles:
        article.source_id = "same-source"
        article.ai = None
        article.content_score = 0.8
        article.published_at = datetime(2026, 8, 9, tzinfo=UTC)
        assert article.content_score_breakdown is not None
        article.content_score_breakdown.target_relevance = 0.8
    telemetry = EnrichmentTelemetry()

    result, model_calls = enrich_snapshot(
        snapshot,
        client=FakeStructuredClient(),
        cache=FileAiCache(tmp_path),
        topics=[topic()],
        telemetry=telemetry,
        max_model_calls=5,
        now=datetime(2026, 8, 10, tzinfo=UTC),
    )

    assert model_calls == 3
    assert sum(article.ai is not None for article in result.articles) == 3
    assert telemetry.skipped_source_cap == 1


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


def test_article_enrichment_schema_rejects_overlong_summary() -> None:
    payload = {
        "titleZh": "结构化标题",
        "summaryZh": "测" * 321,
        "whyItMatters": "这会影响模型评测结果的可比性和复现成本。",
        "keyPoints": ["统一评测口径", "记录推理协议"],
        "topicIds": ["data-agent"],
    }

    try:
        ArticleEnrichment.model_validate(payload)
    except ValueError:
        pass
    else:
        raise AssertionError("overlong summary must be rejected")


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
