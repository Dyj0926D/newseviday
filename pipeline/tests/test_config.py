from newseviday_pipeline.settings import load_project_config


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
