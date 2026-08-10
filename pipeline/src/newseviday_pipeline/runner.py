from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4

from newseviday_pipeline.adapters import parse_source, parse_syndication
from newseviday_pipeline.models import (
    ContentSnapshot,
    PipelineRun,
    PipelineStageName,
    PipelineStageResult,
    RawFeedItem,
    SnapshotTopic,
    Source,
    SourceConfig,
    SourceRunOutcome,
    TopicConfig,
)
from newseviday_pipeline.network import fetch_source
from newseviday_pipeline.snapshot import SnapshotPublisher
from newseviday_pipeline.stages import (
    apply_content_quotas,
    exact_deduplicate,
    fuzzy_deduplicate,
    normalize_item,
    select_by_topics,
)
from newseviday_pipeline.tracing import PipelineTraceWriter


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
            topics=[SnapshotTopic(id=topic.id, label=topic.label) for topic in topics],
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


def _source_contract(source: SourceConfig) -> Source:
    parts = urlsplit(str(source.url))
    homepage = f"{parts.scheme}://{parts.netloc}"
    return Source(
        id=source.id,
        name=source.name,
        kind=source.adapter,
        homepage_url=homepage,
        feed_url=str(source.url),
        language=source.language,
        region=source.region,
        active=True,
        usage_scope=source.usage_scope,
        source_type=source.source_type,
        evidence_tier=source.evidence_tier,
    )


def run_network_pipeline(
    sources: list[SourceConfig],
    output_dir: Path,
    *,
    topics: list[TopicConfig],
    config_version: int,
    now: datetime | None = None,
    minimum_successful_sources: int = 3,
) -> tuple[PipelineRun, ContentSnapshot]:
    enabled_sources = [source for source in sources if source.enabled]
    if not enabled_sources:
        raise ValueError("no_enabled_sources")
    current_time = now or datetime.now(UTC)
    run = PipelineRun(
        id=f"pipeline-{uuid4().hex}",
        started_at=current_time,
        status="running",
        config_version=config_version,
        source_ids=[source.id for source in enabled_sources],
    )
    trace_writer = PipelineTraceWriter(output_dir)
    try:
        stage_started = perf_counter()
        with ThreadPoolExecutor(max_workers=min(4, len(enabled_sources))) as executor:
            fetched = list(executor.map(fetch_source, enabled_sources))
        successful = [result for result in fetched if result.ok]
        outcomes = {
            result.source.id: SourceRunOutcome(
                source_id=result.source.id,
                fetch_status="succeeded" if result.ok else "failed",
                parse_status="skipped",
                final_url=result.final_url,
                error_code=result.error_code,
            )
            for result in fetched
        }
        run.source_outcomes = [outcomes[source.id] for source in enabled_sources]
        run.stages.append(_stage("fetch", stage_started, len(enabled_sources), len(successful)))
        if len(successful) < minimum_successful_sources:
            raise RuntimeError("insufficient_successful_sources")

        stage_started = perf_counter()
        raw_items: list[RawFeedItem] = []
        successful_sources: list[SourceConfig] = []
        for result in successful:
            if result.content is None:
                continue
            try:
                parsed_items = parse_source(result.content, result.source)
                raw_items.extend(parsed_items)
                successful_sources.append(result.source)
                outcomes[result.source.id].parse_status = "succeeded"
                outcomes[result.source.id].item_count = len(parsed_items)
            except (ValueError, KeyError) as error:
                outcomes[result.source.id].parse_status = "failed"
                outcomes[result.source.id].error_code = type(error).__name__
                continue
        run.stages.append(_stage("extract", stage_started, len(successful), len(raw_items)))
        if len(successful_sources) < minimum_successful_sources:
            raise RuntimeError("insufficient_parseable_sources")

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
        selected = apply_content_quotas(
            select_by_topics(fuzzy, topics),
            source_limits={source.id: source.max_selected_items for source in enabled_sources},
        )
        selected_counts = Counter(article.source_id for article in selected)
        for source_id, outcome in outcomes.items():
            outcome.selected_count = selected_counts.get(source_id, 0)
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
            snapshot_kind="production",
            source_count=len(successful_sources),
            sources=[_source_contract(source) for source in successful_sources],
            topics=[SnapshotTopic(id=topic.id, label=topic.label) for topic in topics],
            articles=selected,
            evidence=selected_evidence,
        )

        stage_started = perf_counter()
        SnapshotPublisher(output_dir).publish(snapshot)
        run.stages.append(_stage("snapshot", stage_started, len(selected), len(selected)))
        run.status = "succeeded"
        run.finished_at = datetime.now(UTC)
        trace_writer.write(run)
        return run, snapshot
    except Exception as error:
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.error_code = type(error).__name__
        trace_writer.write(run)
        raise
