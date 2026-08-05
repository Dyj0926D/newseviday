from datetime import UTC, datetime, timedelta

import pytest

from newseviday_pipeline.models import RawFeedItem, TopicConfig
from newseviday_pipeline.stages import (
    apply_content_quotas,
    canonicalize_url,
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
    assert canonicalize_url(
        "https://api-docs.deepseek.com/updates/#deepseek-v4",
        preserve_fragment=True,
    ) == "https://api-docs.deepseek.com/updates#deepseek-v4"


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
