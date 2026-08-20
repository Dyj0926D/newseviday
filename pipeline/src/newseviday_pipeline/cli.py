import argparse
import json
import os
import shutil
import tempfile
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from newseviday_pipeline import __version__
from newseviday_pipeline.ai import (
    DeepSeekStructuredClient,
    EnrichmentTelemetry,
    FileAiCache,
    enrich_snapshot,
    update_weekly_brief,
)
from newseviday_pipeline.ai_models import AiUsageReport
from newseviday_pipeline.budget import (
    load_rollover_ledger,
    plan_rollover_budget,
    settle_rollover_budget,
    write_rollover_ledger,
)
from newseviday_pipeline.dedup_eval import evaluate_dedup_dataset, write_dedup_report
from newseviday_pipeline.editorial import apply_editorial_package, load_editorial_package
from newseviday_pipeline.embeddings import HashingEmbedder, OpenAICompatibleEmbedder
from newseviday_pipeline.evaluation import (
    build_rag_review_packet,
    evaluate_rag,
    load_gold_dataset,
    write_eval_report,
    write_rag_review_packet,
)
from newseviday_pipeline.inventory import merge_rolling_inventory
from newseviday_pipeline.models import ContentSnapshot
from newseviday_pipeline.quality import (
    audit_snapshot,
    evaluate_release_guard,
    write_quality_report,
    write_release_guard_report,
)
from newseviday_pipeline.rag import build_dense_index, vectorize_ndjson, write_index
from newseviday_pipeline.runner import run_fixture_pipeline, run_network_pipeline
from newseviday_pipeline.settings import load_project_config
from newseviday_pipeline.signal_eval import (
    evaluate_key_signal_dataset,
    write_key_signal_eval_report,
)
from newseviday_pipeline.snapshot import SnapshotPublisher, load_snapshot
from newseviday_pipeline.stages import chinese_display_ready
from newseviday_pipeline.terminology import load_terminology, terminology_consistency

PIPELINE_STAGES = (
    "fetch",
    "extract",
    "normalize",
    "exact_dedup",
    "fuzzy_dedup",
    "select",
    "snapshot",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="newseviday-pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Validate local configuration and print safe status")

    run_parser = subparsers.add_parser("run", help="Run the deterministic content pipeline")
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned stages without network access or file publication",
    )
    run_parser.add_argument(
        "--fixture",
        type=Path,
        help="Read one local Atom/RSS fixture. Network access remains disabled.",
    )
    run_parser.add_argument("--output", type=Path, default=Path("data/snapshots"))
    run_parser.add_argument("--source-id", default="fixture-source")
    run_parser.add_argument("--language", default="en")
    run_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Explicitly allow configured HTTPS sources for this manual run.",
    )

    validate_parser = subparsers.add_parser("validate-snapshot", help="Validate a snapshot JSON")
    validate_parser.add_argument("path", type=Path)
    dedup_parser = subparsers.add_parser(
        "eval-dedup", help="Evaluate deterministic near-duplicate detection"
    )
    dedup_parser.add_argument("dataset", type=Path)
    dedup_parser.add_argument("--threshold", type=float, default=0.82)
    dedup_parser.add_argument("--output", type=Path)
    enrich_parser = subparsers.add_parser(
        "enrich", help="Add one-call structured AI enrichment to a validated snapshot"
    )
    enrich_parser.add_argument("snapshot", type=Path)
    enrich_parser.add_argument(
        "--accepted-snapshot",
        type=Path,
        help="Reuse only AI fields that have already been published in this snapshot.",
    )
    enrich_parser.add_argument("--output", type=Path, default=Path("data/enriched"))
    enrich_parser.add_argument("--cache", type=Path, default=Path("data/runtime/ai-cache"))
    enrich_parser.add_argument("--terminology", type=Path, default=Path("config/terminology.yaml"))
    enrich_parser.add_argument("--terminology-threshold", type=float, default=0.95)
    enrich_parser.add_argument(
        "--allow-model",
        action="store_true",
        help="Explicitly permit paid model calls for uncached articles.",
    )
    enrich_parser.add_argument(
        "--max-model-calls",
        type=int,
        default=5,
        help="Hard cap for paid calls in one run after rollover (0-10, default: 5).",
    )
    enrich_parser.add_argument(
        "--base-model-calls",
        type=int,
        default=5,
        help="Daily model-call credit before rollover (default: 5).",
    )
    enrich_parser.add_argument(
        "--rollover-ledger",
        type=Path,
        help="Private persisted ledger for bounded unused daily translation credits.",
    )
    enrich_parser.add_argument(
        "--rollover-cap",
        type=int,
        default=10,
        help="Maximum unused credits retained between days (default: 10).",
    )
    enrich_parser.add_argument(
        "--rollover-seed",
        type=int,
        default=0,
        help="One-time bounded starting balance when no ledger exists.",
    )
    enrich_parser.add_argument(
        "--usage-report",
        type=Path,
        help="Write a private per-run token, cache and estimated-cost report.",
    )
    brief_parser = subparsers.add_parser(
        "update-brief",
        help="Generate the last complete weekly brief when due, or carry the last successful brief",
    )
    brief_parser.add_argument("snapshot", type=Path)
    brief_parser.add_argument("--accepted-snapshot", type=Path)
    brief_parser.add_argument("--output", type=Path, default=Path("data/briefed"))
    brief_parser.add_argument("--cache", type=Path, default=Path("data/runtime/ai-cache"))
    brief_parser.add_argument(
        "--allow-model",
        action="store_true",
        help="Permit one paid DeepSeek call when the weekly brief is due.",
    )
    brief_parser.add_argument(
        "--force-generate",
        action="store_true",
        help="Generate the last complete weekly window outside the normal Saturday schedule.",
    )
    editorial_parser = subparsers.add_parser(
        "apply-editorial",
        help="Apply a reviewable editorial package to a validated snapshot",
    )
    editorial_parser.add_argument("snapshot", type=Path)
    editorial_parser.add_argument("package", type=Path)
    editorial_parser.add_argument("--output", type=Path, default=Path("data/editorial-output"))
    inventory_parser = subparsers.add_parser(
        "merge-inventory",
        help="Merge a fresh collection with the accepted rolling public inventory",
    )
    inventory_parser.add_argument("snapshot", type=Path)
    inventory_parser.add_argument("--accepted-snapshot", type=Path, required=True)
    inventory_parser.add_argument("--output", type=Path, default=Path("data/rolling"))
    index_parser = subparsers.add_parser(
        "build-index", help="Build a versioned dense retrieval artifact"
    )
    index_parser.add_argument("snapshot", type=Path)
    index_parser.add_argument("--output", type=Path, default=Path("data/runtime/rag/index.json"))
    index_parser.add_argument("--provider", choices=("hashing", "openai"), default="hashing")
    index_parser.add_argument("--dimensions", type=int, default=384)
    index_parser.add_argument("--vectorize-output", type=Path)
    index_parser.add_argument(
        "--allow-embedding-network",
        action="store_true",
        help="Explicitly allow calls to an OpenAI-compatible embedding endpoint.",
    )
    eval_parser = subparsers.add_parser(
        "eval-rag", help="Run the reproducible retrieval evaluation harness"
    )
    eval_parser.add_argument("snapshot", type=Path)
    eval_parser.add_argument("dataset", type=Path)
    eval_parser.add_argument("--report", type=Path, default=Path("data/runtime/eval/latest.json"))
    eval_parser.add_argument(
        "--review-packet",
        type=Path,
        help="Export per-question candidates and blank human-review fields.",
    )
    eval_parser.add_argument("--minimum-score", type=float, default=0.08)
    signal_eval_parser = subparsers.add_parser(
        "eval-key-signal", help="Evaluate change-event detection and Key Signal eligibility"
    )
    signal_eval_parser.add_argument("dataset", type=Path)
    signal_eval_parser.add_argument(
        "--report", type=Path, default=Path("data/runtime/quality/key-signal-eval.json")
    )
    audit_parser = subparsers.add_parser(
        "audit-snapshot", help="Create a deterministic content operations quality report"
    )
    audit_parser.add_argument("snapshot", type=Path)
    audit_parser.add_argument(
        "--report", type=Path, default=Path("data/runtime/quality/latest.json")
    )
    guard_parser = subparsers.add_parser(
        "compare-quality", help="Compare a candidate with the accepted public snapshot"
    )
    guard_parser.add_argument("snapshot", type=Path)
    guard_parser.add_argument("--accepted-snapshot", type=Path, required=True)
    guard_parser.add_argument(
        "--report", type=Path, default=Path("data/runtime/quality/release-guard.json")
    )
    publish_parser = subparsers.add_parser(
        "publish-web", help="Atomically publish a validated snapshot and optional Eval report"
    )
    publish_parser.add_argument("snapshot", type=Path)
    publish_parser.add_argument("--web-data", type=Path, default=Path("apps/web/public/data"))
    publish_parser.add_argument("--eval-report", type=Path)
    publish_parser.add_argument("--quality-report", type=Path)
    publish_parser.add_argument(
        "--allow-demo",
        action="store_true",
        help="Allow a demo fixture to replace the public snapshot.",
    )
    return parser


def doctor() -> int:
    runtime, sources, topics = load_project_config()
    payload = {
        "ok": True,
        "pipelineVersion": __version__,
        "mode": runtime.mode,
        "enabledSources": sum(source.enabled for source in sources.sources),
        "topicCount": len(topics.topics),
        "aiEnabled": runtime.features.ai_summary_enabled,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def dry_run() -> int:
    runtime, sources, topics = load_project_config()
    payload = {
        "dryRun": True,
        "mode": runtime.mode,
        "stages": PIPELINE_STAGES,
        "enabledSources": [source.id for source in sources.sources if source.enabled],
        "topics": [topic.id for topic in topics.topics],
        "networkAccess": False,
        "modelCalls": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def run_fixture(args: argparse.Namespace) -> int:
    runtime, _sources, topics = load_project_config()
    run, snapshot = run_fixture_pipeline(
        args.fixture,
        args.output,
        source_id=args.source_id,
        language=args.language,
        topics=topics.topics,
        config_version=runtime.version,
    )
    payload = {
        "ok": True,
        "runId": run.id,
        "snapshotId": snapshot.snapshot_id,
        "articleCount": len(snapshot.articles),
        "output": str(args.output / "current.json"),
        "networkAccess": False,
        "modelCalls": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def run_network(args: argparse.Namespace) -> int:
    runtime, sources, topics = load_project_config()
    run, snapshot = run_network_pipeline(
        sources.sources,
        args.output,
        topics=topics.topics,
        config_version=runtime.version,
    )
    payload = {
        "ok": True,
        "runId": run.id,
        "snapshotId": snapshot.snapshot_id,
        "articleCount": len(snapshot.articles),
        "sourceCount": snapshot.source_count,
        "output": str(args.output / "current.json"),
        "networkAccess": True,
        "modelCalls": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def validate_snapshot(path: Path) -> int:
    snapshot = load_snapshot(path)
    print(
        json.dumps(
            {
                "ok": True,
                "schemaVersion": snapshot.schema_version,
                "snapshotId": snapshot.snapshot_id,
                "articleCount": len(snapshot.articles),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def eval_dedup(args: argparse.Namespace) -> int:
    result = evaluate_dedup_dataset(args.dataset, threshold=args.threshold)
    if args.output:
        write_dedup_report(result, args.output)
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    return 0


def enrich(args: argparse.Namespace) -> int:
    if not args.allow_model:
        print("AI enrichment requires an explicit --allow-model flag.")
        return 2
    if not 0 <= args.max_model_calls <= 10:
        print("--max-model-calls must be between 0 and 10.")
        return 2
    if min(args.base_model_calls, args.rollover_cap, args.rollover_seed) < 0:
        print("Rollover budget values must be nonnegative.")
        return 2
    budget_plan = None
    effective_model_call_limit = args.max_model_calls
    if args.rollover_ledger:
        budget_plan = plan_rollover_budget(
            load_rollover_ledger(args.rollover_ledger),
            run_date=datetime.now(ZoneInfo("Asia/Shanghai")).date(),
            base_limit=args.base_model_calls,
            rollover_cap=args.rollover_cap,
            max_per_run=args.max_model_calls,
            seed_rollover=args.rollover_seed,
        )
        effective_model_call_limit = budget_plan.effective_limit
    _runtime, _sources, topics = load_project_config()
    snapshot = load_snapshot(args.snapshot)
    accepted_snapshot = load_snapshot(args.accepted_snapshot) if args.accepted_snapshot else None
    terminology = load_terminology(args.terminology)
    client = DeepSeekStructuredClient.from_environment()
    telemetry = EnrichmentTelemetry()
    result, model_calls = enrich_snapshot(
        snapshot,
        client=client,
        cache=FileAiCache(args.cache),
        topics=topics.topics,
        terminology=terminology,
        accepted_snapshot=accepted_snapshot,
        max_model_calls=effective_model_call_limit,
        telemetry=telemetry,
    )
    input_price, output_price = _token_prices_from_environment()
    usage = client.usage_totals
    usage_complete = client.usage_reported_calls == model_calls
    estimated_cost = (
        round(
            (usage.prompt_tokens * input_price + usage.completion_tokens * output_price)
            / 1_000_000,
            6,
        )
        if usage_complete and input_price is not None and output_price is not None
        else None
    )
    rollover_after = None
    if budget_plan is not None:
        settled_budget = settle_rollover_budget(
            budget_plan,
            model_calls=model_calls,
            updated_at=result.generated_at,
        )
        write_rollover_ledger(settled_budget, args.rollover_ledger)
        rollover_after = settled_budget.balance
    usage_report = AiUsageReport(
        snapshot_id=result.snapshot_id,
        generated_at=result.generated_at,
        model=client.model,
        model_calls=model_calls,
        model_call_limit=effective_model_call_limit,
        base_model_call_limit=(budget_plan.base_limit if budget_plan else None),
        rollover_daily_credit=(budget_plan.daily_credit if budget_plan else None),
        rollover_before=(budget_plan.rollover_before if budget_plan else None),
        rollover_after=rollover_after,
        rollover_cap=(budget_plan.rollover_cap if budget_plan else None),
        usage_reported_calls=client.usage_reported_calls,
        usage_complete=usage_complete,
        cache_hits=telemetry.cache_hits,
        accepted_enrichment_reuses=telemetry.accepted_enrichment_reuses,
        enriched_article_count=telemetry.enriched_articles,
        skipped_thin_evidence=telemetry.skipped_thin_evidence,
        skipped_below_quality_floor=telemetry.skipped_below_quality_floor,
        skipped_stale=telemetry.skipped_stale,
        skipped_source_cap=telemetry.skipped_source_cap,
        skipped_after_call_limit=telemetry.skipped_after_call_limit,
        supplemental_translation_calls=telemetry.supplemental_translation_calls,
        priority_topic_translation_calls=telemetry.priority_topic_translation_calls,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        input_cny_per_million=input_price,
        output_cny_per_million=output_price,
        estimated_cost_cny=estimated_cost,
    )
    if args.usage_report:
        _atomic_json(
            usage_report.model_dump(mode="json", by_alias=True),
            args.usage_report,
        )
    terminology_score = terminology_consistency(
        result.articles,
        terminology,
    )
    if terminology_score < args.terminology_threshold:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "terminology_consistency_below_threshold",
                    "score": round(terminology_score, 4),
                    "threshold": args.terminology_threshold,
                    "modelCalls": model_calls,
                    "usage": usage_report.model_dump(mode="json", by_alias=True),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    SnapshotPublisher(args.output).publish(result)
    print(
        json.dumps(
            {
                "ok": True,
                "snapshotId": result.snapshot_id,
                "articleCount": len(result.articles),
                "modelCalls": model_calls,
                "modelCallLimit": effective_model_call_limit,
                "terminologyConsistency": round(terminology_score, 4),
                "usage": usage_report.model_dump(mode="json", by_alias=True),
                "output": str(args.output / "current.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def update_brief(args: argparse.Namespace) -> int:
    snapshot = load_snapshot(args.snapshot)
    accepted_snapshot = load_snapshot(args.accepted_snapshot) if args.accepted_snapshot else None
    client = DeepSeekStructuredClient.from_environment() if args.allow_model else None
    try:
        update = update_weekly_brief(
            snapshot,
            accepted_snapshot=accepted_snapshot,
            client=client,
            cache=FileAiCache(args.cache),
            force_generate=args.force_generate,
        )
    except (httpx.HTTPError, ValueError) as error:
        update = update_weekly_brief(
            snapshot,
            accepted_snapshot=accepted_snapshot,
            client=None,
            cache=FileAiCache(args.cache),
            generate_if_due=False,
        )
        print(f"Weekly brief generation fell back to the last successful brief: {error}")
    SnapshotPublisher(args.output).publish(update.snapshot)
    print(
        json.dumps(
            {
                "ok": True,
                "snapshotId": update.snapshot.snapshot_id,
                "status": update.status,
                "briefCount": len(update.snapshot.briefs),
                "modelCalls": update.model_calls,
                "periodStart": update.period_start.isoformat(),
                "periodEndExclusive": update.period_end.isoformat(),
                "output": str(args.output / "current.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def apply_editorial(args: argparse.Namespace) -> int:
    snapshot = load_snapshot(args.snapshot)
    package = load_editorial_package(args.package)
    result = apply_editorial_package(snapshot, package)
    SnapshotPublisher(args.output).publish(result)
    print(
        json.dumps(
            {
                "ok": True,
                "snapshotId": result.snapshot_id,
                "articleCount": len(result.articles),
                "editorialArticleCount": len(package.articles),
                "briefCount": len(result.briefs),
                "output": str(args.output / "current.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def merge_inventory(args: argparse.Namespace) -> int:
    incoming = load_snapshot(args.snapshot)
    accepted = load_snapshot(args.accepted_snapshot)
    result = merge_rolling_inventory(incoming, accepted)
    SnapshotPublisher(args.output).publish(result)
    print(
        json.dumps(
            {
                "ok": True,
                "snapshotId": result.snapshot_id,
                "articleCount": len(result.articles),
                "chineseReadyCount": sum(
                    chinese_display_ready(article) for article in result.articles
                ),
                "output": str(args.output / "current.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _optional_nonnegative_float(name: str) -> float | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{name}_must_be_nonnegative_number") from error
    if parsed < 0:
        raise ValueError(f"{name}_must_be_nonnegative_number")
    return parsed


def _token_prices_from_environment() -> tuple[float | None, float | None]:
    input_price = _optional_nonnegative_float("DEEPSEEK_INPUT_CNY_PER_MILLION")
    output_price = _optional_nonnegative_float("DEEPSEEK_OUTPUT_CNY_PER_MILLION")
    if (input_price is None) != (output_price is None):
        raise ValueError("deepseek_token_prices_must_be_configured_together")
    return input_price, output_price


def _embedding_provider(args: argparse.Namespace) -> HashingEmbedder | OpenAICompatibleEmbedder:
    if args.provider == "hashing":
        return HashingEmbedder(dimensions=args.dimensions)
    if not args.allow_embedding_network:
        raise ValueError("OpenAI-compatible embeddings require --allow-embedding-network")
    return OpenAICompatibleEmbedder(
        base_url=os.environ.get("EMBEDDING_BASE_URL", ""),
        model=os.environ.get("EMBEDDING_MODEL", ""),
        dimensions=args.dimensions,
        api_key=os.environ.get("EMBEDDING_API_KEY"),
    )


def build_index(args: argparse.Namespace) -> int:
    snapshot = load_snapshot(args.snapshot)
    provider = _embedding_provider(args)
    index = build_dense_index(snapshot, provider)
    write_index(index, args.output)
    if args.vectorize_output:
        args.vectorize_output.parent.mkdir(parents=True, exist_ok=True)
        args.vectorize_output.write_text(vectorize_ndjson(index), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "ok": True,
                "snapshotId": snapshot.snapshot_id,
                "chunkCount": len(index.records),
                "embeddingModel": index.embedding_model,
                "dimensions": index.dimensions,
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def eval_rag(args: argparse.Namespace) -> int:
    snapshot = load_snapshot(args.snapshot)
    dataset = load_gold_dataset(args.dataset)
    provider = HashingEmbedder()
    index = build_dense_index(snapshot, provider)
    report = evaluate_rag(
        snapshot,
        index,
        dataset,
        provider,
        minimum_score=args.minimum_score,
    )
    write_eval_report(report, args.report)
    if args.review_packet:
        packet = build_rag_review_packet(
            snapshot,
            index,
            dataset,
            provider,
            minimum_score=args.minimum_score,
        )
        write_rag_review_packet(packet, args.review_packet)
    print(report.model_dump_json(by_alias=True, indent=2))
    return 0


def eval_key_signal(args: argparse.Namespace) -> int:
    report = evaluate_key_signal_dataset(args.dataset)
    write_key_signal_eval_report(report, args.report)
    print(report.model_dump_json(by_alias=True, indent=2))
    return 0 if report.gate == "pass" else 1


def audit(args: argparse.Namespace) -> int:
    report = audit_snapshot(load_snapshot(args.snapshot))
    write_quality_report(report, args.report)
    print(report.model_dump_json(by_alias=True, indent=2))
    return 1 if report.gate == "fail" else 0


def compare_quality(args: argparse.Namespace) -> int:
    report = evaluate_release_guard(
        load_snapshot(args.snapshot),
        load_snapshot(args.accepted_snapshot),
    )
    write_release_guard_report(report, args.report)
    print(report.model_dump_json(by_alias=True, indent=2))
    return 1 if report.gate == "fail" else 0


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=target.parent, prefix="publish-", suffix=".tmp")
    os.close(handle)
    temporary = Path(name)
    try:
        shutil.copyfile(source, temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(value: object, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=target.parent, prefix="publish-", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def _update_archive_manifest(snapshot: ContentSnapshot, web_data: Path) -> Path:
    manifest_path = web_data / "archive" / "manifest.json"
    existing: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                existing = parsed
        except (json.JSONDecodeError, OSError):
            existing = {}
    snapshot_id = snapshot.snapshot_id
    snapshots = [
        item
        for item in existing.get("snapshots", [])
        if isinstance(item, dict) and item.get("snapshotId") != snapshot_id
    ]
    snapshots.append(
        {
            "snapshotId": snapshot_id,
            "generatedAt": snapshot.generated_at.isoformat().replace("+00:00", "Z"),
            "path": f"versions/{snapshot_id}.json",
            "articleCount": len(snapshot.articles),
        }
    )
    snapshots.sort(key=lambda item: str(item.get("generatedAt", "")), reverse=True)
    article_entries = {
        str(item.get("id")): item
        for item in existing.get("articles", [])
        if isinstance(item, dict) and item.get("id")
    }
    for article in snapshot.articles:
        article_entries[article.id] = {
            "id": article.id,
            "title": (
                article.ai.title_zh if article.ai and article.ai.title_zh else article.facts.title
            ),
            "originalTitle": article.facts.title,
            "sourceId": article.source_id,
            "publishedAt": (
                article.published_at.isoformat().replace("+00:00", "Z")
                if article.published_at
                else None
            ),
            "snapshotPath": f"versions/{snapshot_id}.json",
        }
    manifest = {
        "schemaVersion": "1.0.0",
        "updatedAt": snapshot.generated_at.isoformat().replace("+00:00", "Z"),
        "snapshots": snapshots,
        "articles": sorted(
            article_entries.values(),
            key=lambda item: str(item.get("publishedAt") or ""),
            reverse=True,
        ),
    }
    _atomic_json(manifest, manifest_path)
    return manifest_path


def publish_web(args: argparse.Namespace) -> int:
    snapshot = load_snapshot(args.snapshot)
    if snapshot.snapshot_kind == "demo" and not args.allow_demo:
        print("Refusing to publish a demo snapshot without --allow-demo.")
        return 2
    version_path = args.web_data / "versions" / f"{snapshot.snapshot_id}.json"
    if version_path.exists() and version_path.read_bytes() != args.snapshot.read_bytes():
        print(f"Refusing to overwrite immutable snapshot version: {version_path}")
        return 2
    if not version_path.exists():
        _atomic_copy(args.snapshot, version_path)
    _atomic_copy(args.snapshot, args.web_data / "current.json")
    manifest_path = _update_archive_manifest(snapshot, args.web_data)
    if args.eval_report:
        _atomic_copy(args.eval_report, args.web_data / "eval" / "latest.json")
    if args.quality_report:
        _atomic_copy(args.quality_report, args.web_data / "quality" / "latest.json")
    print(
        json.dumps(
            {
                "ok": True,
                "snapshotId": snapshot.snapshot_id,
                "webData": str(args.web_data),
                "versionPath": str(version_path),
                "archiveManifest": str(manifest_path),
                "evalReport": bool(args.eval_report),
                "qualityReport": bool(args.quality_report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        return doctor()
    if args.command == "validate-snapshot":
        return validate_snapshot(args.path)
    if args.command == "eval-dedup":
        return eval_dedup(args)
    if args.command == "enrich":
        return enrich(args)
    if args.command == "update-brief":
        return update_brief(args)
    if args.command == "apply-editorial":
        return apply_editorial(args)
    if args.command == "merge-inventory":
        return merge_inventory(args)
    if args.command == "build-index":
        return build_index(args)
    if args.command == "eval-rag":
        return eval_rag(args)
    if args.command == "eval-key-signal":
        return eval_key_signal(args)
    if args.command == "audit-snapshot":
        return audit(args)
    if args.command == "compare-quality":
        return compare_quality(args)
    if args.command == "publish-web":
        return publish_web(args)
    if args.command == "run" and args.dry_run:
        return dry_run()
    if args.command == "run" and args.fixture:
        return run_fixture(args)
    if args.command == "run" and args.allow_network:
        return run_network(args)

    print("Network collection requires an explicit --allow-network flag.")
    return 2
