from newseviday_pipeline.settings import load_project_config


def test_project_config_defaults_to_cost_safe_archive_mode() -> None:
    runtime, sources, topics = load_project_config()

    assert runtime.mode == "archive"
    assert runtime.features.ingestion_enabled is False
    assert runtime.features.ai_summary_enabled is False
    assert len([source for source in sources.sources if source.enabled]) == 9
    assert len(topics.topics) >= 8
