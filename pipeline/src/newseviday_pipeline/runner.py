from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from newseviday_pipeline.adapters import parse_syndication
from newseviday_pipeline.models import (
    ContentSnapshot,
    PipelineRun,
    PipelineStageName,
    PipelineStageResult,
    RawFeedItem,
    TopicConfig,
)
from newseviday_pipeline.snapshot import SnapshotPublisher
from newseviday_pipeline.stages import (
    exact_deduplicate,
    fuzzy_deduplicate,
    normalize_item,
    select_by_topics,
)


def _stage(
    name: PipelineStageName,
    started: float,
    input_count: int,
    output_count: int,
) -> PipelineStageResult:
    return PipelineStageResult(
        stage=name,
        status="succeeded",
        input_count=input_count,
        output_count=output_count,
        duration_ms=max(0, round((perf_counter() - started) * 1_000)),
    )


def run_fixture_pipeline(
    fixture: Path,
    output_dir: Path,
    *,
    source_id: str,
    language: str,
    topics: list[TopicConfig],
    config_version: int,
    now: datetime | None = None,
) -> tuple[PipelineRun, ContentSnapshot]:
    current_time = now or datetime.now(UTC)
    run = PipelineRun(
        id=f"pipeline-{uuid4().hex}",
        started_at=current_time,
        status="running",
        config_version=config_version,
        source_ids=[source_id],
    )
    try:
        stage_started = perf_counter()
        content = fixture.read_bytes()
        run.stages.append(_stage("fetch", stage_started, 1, 1))

        stage_started = perf_counter()
        raw_items: list[RawFeedItem] = parse_syndication(
            content,
            source_id=source_id,
            language=language,
        )
        run.stages.append(_stage("extract", stage_started, 1, len(raw_items)))

        stage_started = perf_counter()
        normalized = [normalize_item(item, collected_at=current_time) for item in raw_items]
        articles = [article for article, _evidence in normalized]
        evidence_by_article = {evidence.article_id: evidence for _article, evidence in normalized}
        run.stages.append(_stage("normalize", stage_started, len(raw_items), len(articles)))

        stage_started = perf_counter()
        exact = exact_deduplicate(articles)
        run.stages.append(_stage("exact_dedup", stage_started, len(articles), len(exact)))

        stage_started = perf_counter()
        fuzzy = fuzzy_deduplicate(exact)
        run.stages.append(_stage("fuzzy_dedup", stage_started, len(exact), len(fuzzy)))

        stage_started = perf_counter()
        selected = select_by_topics(fuzzy, topics)
        run.stages.append(_stage("select", stage_started, len(fuzzy), len(selected)))

        selected_evidence = [
            evidence_by_article[article.id]
            for article in selected
            if article.id in evidence_by_article
        ]
        snapshot = ContentSnapshot(
            snapshot_id=f"snapshot-{current_time.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}",
            generated_at=current_time,
            pipeline_run_id=run.id,
            state="ready" if selected else "empty",
            source_count=1,
            articles=selected,
            evidence=selected_evidence,
        )

        stage_started = perf_counter()
        SnapshotPublisher(output_dir).publish(snapshot)
        run.stages.append(_stage("snapshot", stage_started, len(selected), len(selected)))
        run.status = "succeeded"
        run.finished_at = datetime.now(UTC)
        return run, snapshot
    except Exception as error:
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.error_code = type(error).__name__
        raise
