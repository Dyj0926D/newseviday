from datetime import UTC, datetime, timedelta

import pytest

from newseviday_pipeline.models import GeneratedText, RawFeedItem, TopicConfig
from newseviday_pipeline.stages import (
    CHINESE_READINESS_FAILURE,
    apply_article_scoring,
    apply_content_quotas,
    canonicalize_url,
    chinese_display_ready,
    content_score_breakdown,
    content_value_score,
    exact_deduplicate,
    fuzzy_deduplicate,
    normalize_item,
    select_by_topics,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)


def item(url: str, title: str, summary: str) -> RawFeedItem:
    return RawFeedItem(
        source_id="test-source",
        url=url,
        title=title,
        summary=summary,
        language="en",
    )


def test_canonical_url_removes_tracking_and_fragment() -> None:
    assert canonicalize_url("HTTPS://Example.com/news/?utm_source=x&id=2#part") == (
        "https://example.com/news?id=2"
    )


def test_canonical_url_can_preserve_a_meaningful_section_fragment() -> None:
    assert (
        canonicalize_url(
            "https://api-docs.deepseek.com/updates/#deepseek-v4",
            preserve_fragment=True,
        )
        == "https://api-docs.deepseek.com/updates#deepseek-v4"
    )


def test_exact_and_fuzzy_deduplication_are_deterministic() -> None:
    raw = [
        item("https://example.com/a?utm_source=x", "Semantic Layer for Data Agents", "Traceable"),
        item("https://example.com/a", "Semantic Layer for Data Agents", "Traceable"),
        item("https://example.com/b", "Semantic Layer for Reliable Data Agents", "Traceable"),
    ]
    articles = [normalize_item(value, collected_at=NOW)[0] for value in raw]

    exact = exact_deduplicate(articles)
    fuzzy = fuzzy_deduplicate(exact, similarity_threshold=0.75)

    assert len(exact) == 2
    assert len(fuzzy) == 1


def test_fuzzy_dedup_rejects_unbounded_daily_batch() -> None:
    article = normalize_item(item("https://example.com/a", "A", "B"), collected_at=NOW)[0]
    with pytest.raises(ValueError, match="batch_exceeds"):
        fuzzy_deduplicate([article, article], max_batch_size=1)


def test_topic_selection_sets_explainable_scores() -> None:
    article = normalize_item(
        item("https://example.com/a", "A semantic layer for data agents", "metrics layer"),
        collected_at=NOW,
    )[0]
    topic = TopicConfig(
        id="semantic-layer",
        label="Semantic Layer",
        weight=1.0,
        keywords=["semantic layer", "metrics layer"],
    )

    selected = select_by_topics([article], [topic])

    assert len(selected) == 1
    assert selected[0].topic_scores == {"semantic-layer": 1.0}


def test_topic_selection_does_not_penalize_topics_with_a_larger_vocabulary() -> None:
    article = normalize_item(
        item("https://example.com/deepseek", "DeepSeek-V4 release", "Model update"),
        collected_at=NOW,
    )[0]
    topic = TopicConfig(
        id="foundation-models",
        label="Foundation Models",
        weight=1.0,
        keywords=["foundation model", "llm", "gpt", "claude", "qwen", "deepseek"],
    )

    selected = select_by_topics([article], [topic])

    assert len(selected) == 1
    assert selected[0].topic_scores == {"foundation-models": 0.5}


def test_content_value_score_balances_relevance_freshness_and_completeness() -> None:
    recent = normalize_item(
        item("https://example.com/recent", "Fresh semantic layer", "x" * 300),
        collected_at=NOW,
    )[0]
    recent.published_at = NOW
    recent.topic_scores = {"semantic-layer": 0.8}
    stale = normalize_item(
        item("https://example.com/stale", "Old semantic layer", "x" * 300),
        collected_at=NOW,
    )[0]
    stale.published_at = NOW - timedelta(days=14)
    stale.topic_scores = {"semantic-layer": 0.8}

    assert content_value_score(recent, anchor=NOW) > content_value_score(stale, anchor=NOW)
    assert apply_content_quotas([stale, recent])[0].id == recent.id


def test_content_score_assigns_twenty_five_percent_to_engineering_signals() -> None:
    engineering = normalize_item(
        item(
            "https://example.com/engineering",
            "Open-source semantic platform benchmark improves production latency by 35%",
            (
                "We introduce a general-purpose framework with an API and deployment workflow. "
                "Evaluation across datasets shows lower cost and higher throughput than baseline. "
            )
            * 3,
        ),
        collected_at=NOW,
    )[0]
    engineering.published_at = NOW
    engineering.topic_scores = {"semantic-layer": 1.0, "data-agent": 0.8}
    plain = normalize_item(
        item("https://example.com/plain", "Semantic layer research", "x" * 300),
        collected_at=NOW,
    )[0]
    plain.published_at = NOW
    plain.topic_scores = {"semantic-layer": 1.0, "data-agent": 0.8}

    breakdown = content_score_breakdown(engineering, anchor=NOW)

    assert breakdown.technical_advancement >= 0.7
    assert breakdown.engineering_applicability >= 0.7
    assert breakdown.technical_generality >= 0.65
    assert content_value_score(engineering, anchor=NOW) > content_value_score(plain, anchor=NOW)


def test_arxiv_source_has_a_six_article_daily_cap() -> None:
    candidates = []
    for index in range(8):
        article = normalize_item(
            item(
                f"https://arxiv.org/abs/2608.{index:05d}",
                f"RAG evaluation benchmark {index}",
                "We propose an evaluation dataset for retrieval systems. " * 5,
            ),
            collected_at=NOW,
        )[0]
        article.source_id = "arxiv-cs-ai"
        article.published_at = NOW - timedelta(minutes=index)
        article.topic_scores = {"rag-eval": 0.9}
        candidates.append(article)
    official = normalize_item(
        item(
            "https://example.com/release",
            "Data agent platform release",
            "A production platform API and workflow for enterprise data agents. " * 4,
        ),
        collected_at=NOW,
    )[0]
    official.topic_scores = {"data-agent": 1.0}
    candidates.append(official)

    selected = apply_content_quotas(candidates, max_total=20)

    assert sum(article.source_id == "arxiv-cs-ai" for article in selected) == 6
    assert official in selected


def test_arxiv_requires_strong_target_relevance_before_entering_the_feed() -> None:
    specialist = normalize_item(
        item(
            "https://arxiv.org/abs/2608.12345",
            "Synthetic clinical benchmark for enterprise AI agents",
            "We introduce a healthcare benchmark with quantitative evaluation. " * 6,
        ),
        collected_at=NOW,
    )[0]
    specialist.source_id = "arxiv-cs-ai"
    specialist.published_at = NOW
    specialist.topic_scores = {"ai-products-agents": 0.45}
    official = normalize_item(
        item(
            "https://example.com/official-agent-update",
            "Enterprise AI agent product update",
            "The product adds a production workflow and evaluation API. " * 6,
        ),
        collected_at=NOW,
    )[0]
    official.published_at = NOW
    official.topic_scores = {"ai-products-agents": 0.45}

    selected = apply_content_quotas([specialist, official], max_total=10)

    assert specialist not in selected
    assert official in selected


def test_arxiv_rejects_fresh_complete_paper_with_only_weak_topic_overlap() -> None:
    candidate = normalize_item(
        item(
            "https://arxiv.org/abs/2608.54321",
            "Strategy-first synthesis planning for complex natural products",
            "We introduce an LLM framework and dataset for molecular synthesis planning. " * 6,
        ),
        collected_at=NOW,
    )[0]
    candidate.source_id = "arxiv-cs-ai"
    candidate.published_at = NOW
    candidate.topic_scores = {
        "metadata-governance": 0.55,
        "foundation-models": 0.425,
        "ai-products-agents": 0.45,
    }

    selected = apply_content_quotas([candidate], max_total=10)

    assert candidate not in selected


def test_key_signal_uses_a_separate_editorial_gate() -> None:
    candidate = normalize_item(
        item(
            "https://example.com/key-signal",
            "Open-source data agent platform benchmark improves production latency by 35%",
            (
                "We introduce a general-purpose framework, API, deployment workflow and dataset. "
                "Evaluation across models shows higher throughput and lower cost than baseline. "
            )
            * 3,
        ),
        collected_at=NOW,
    )[0]
    candidate.published_at = NOW
    candidate.topic_scores = {"data-agent": 1.0, "semantic-layer": 0.8}
    candidate.ai = GeneratedText(
        title_zh="开源数据智能体平台将生产延迟降低 35%",
        summary_zh="该平台提供通用框架、API 与可复现评测，并给出跨模型生产部署结果。",
        why_it_matters="可用于判断数据智能体的落地成本。",
        key_points=["生产延迟降低", "提供开源框架"],
        model="deepseek-test",
        prompt_version="test",
        generated_at=NOW,
    )

    apply_article_scoring(candidate, anchor=NOW)

    assert candidate.content_score is not None and candidate.content_score >= 0.75
    assert candidate.key_signal is not None and candidate.key_signal.eligible


def test_key_signal_rejects_a_narrow_low_relevance_paper() -> None:
    candidate = normalize_item(
        item(
            "https://arxiv.org/abs/2608.99999",
            "Modern Greek police language processing benchmark",
            "We propose a new benchmark and dataset for Modern Greek police language. " * 4,
        ),
        collected_at=NOW,
    )[0]
    candidate.source_id = "arxiv-cs-ai"
    candidate.published_at = NOW
    candidate.topic_scores = {"foundation-models": 0.8}
    candidate.ai = GeneratedText(
        title_zh="现代希腊语警务语言处理评测",
        summary_zh="论文整理了现代希腊语警务语言数据集和评测方法。",
        why_it_matters="适用于特定语种研究。",
        key_points=["建立数据集", "限定特定语种"],
        model="deepseek-test",
        prompt_version="test",
        generated_at=NOW,
    )

    apply_article_scoring(candidate, anchor=NOW)

    assert candidate.key_signal is not None
    assert not candidate.key_signal.eligible
    assert "目标用户相关性低于 65" in candidate.key_signal.gate_failures


def test_chinese_source_satisfies_display_gate_without_model_output() -> None:
    candidate = normalize_item(
        RawFeedItem(
            source_id="official-cn",
            url="https://example.cn/release",
            title="数据智能体平台发布统一语义能力",
            summary=(
                "该平台发布统一指标口径、权限治理和可追溯查询能力，"
                "面向企业生产环境提供接口与评测结果。"
            )
            * 3,
            language="zh-CN",
        ),
        collected_at=NOW,
    )[0]
    candidate.published_at = NOW
    candidate.topic_scores = {"data-agent": 1.0, "semantic-layer": 0.8}

    apply_article_scoring(candidate, anchor=NOW)

    assert chinese_display_ready(candidate)
    assert candidate.ai is None
    assert candidate.key_signal is not None
    assert CHINESE_READINESS_FAILURE not in candidate.key_signal.gate_failures
