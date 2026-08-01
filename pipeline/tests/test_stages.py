from datetime import UTC, datetime

import pytest

from newseviday_pipeline.models import RawFeedItem, TopicConfig
from newseviday_pipeline.stages import (
    canonicalize_url,
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
