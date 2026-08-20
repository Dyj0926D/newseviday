from datetime import UTC, datetime

from newseviday_pipeline.models import RawFeedItem
from newseviday_pipeline.settings import load_project_config
from newseviday_pipeline.stages import normalize_item, select_by_topics


def test_project_config_defaults_to_cost_safe_archive_mode() -> None:
    runtime, sources, topics = load_project_config()

    assert runtime.mode == "archive"
    assert runtime.features.ingestion_enabled is False
    assert runtime.features.ai_summary_enabled is False
    enabled_sources = [source for source in sources.sources if source.enabled]
    assert len(enabled_sources) == 15
    assert {source.source_type for source in enabled_sources} == {
        "official",
        "academic",
        "research_institute",
        "professional_media",
        "independent_author",
    }
    assert {source.evidence_tier for source in enabled_sources} == {
        "primary",
        "secondary",
        "opinion",
    }
    assert len(topics.topics) >= 8


def test_project_topics_recognize_current_data_agent_and_semantic_layer_language() -> None:
    _runtime, _sources, topics = load_project_config()
    article, _evidence = normalize_item(
        RawFeedItem(
            sourceId="databricks-blog",
            url="https://example.com/genie-agent",
            title="Designing effective Genie Agents from a single prompt",
            summary="Route business questions through governed metrics and semantic metadata.",
            language="en",
        ),
        collected_at=datetime(2026, 8, 20, tzinfo=UTC),
    )

    selected = select_by_topics([article], topics.topics)

    assert selected
    assert "data-agent" in selected[0].topic_scores
    assert "semantic-layer" in selected[0].topic_scores
