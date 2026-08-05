import argparse
import json
import os
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path

from newseviday_pipeline import __version__
from newseviday_pipeline.ai import DeepSeekStructuredClient, FileAiCache, enrich_snapshot
from newseviday_pipeline.dedup_eval import evaluate_dedup_dataset, write_dedup_report
from newseviday_pipeline.embeddings import HashingEmbedder, OpenAICompatibleEmbedder
from newseviday_pipeline.evaluation import evaluate_rag, load_gold_dataset, write_eval_report
from newseviday_pipeline.rag import build_dense_index, vectorize_ndjson, write_index
from newseviday_pipeline.runner import run_fixture_pipeline, run_network_pipeline
from newseviday_pipeline.settings import load_project_config
from newseviday_pipeline.snapshot import SnapshotPublisher, load_snapshot
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
    enrich_parser.add_argument("--output", type=Path, default=Path("data/enriched"))
    enrich_parser.add_argument("--cache", type=Path, default=Path("data/runtime/ai-cache"))
    enrich_parser.add_argument(
        "--terminology", type=Path, default=Path("config/terminology.yaml")
    )
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
        help="Hard cap for paid calls in one run (0-10, default: 5).",
    )
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
    eval_parser.add_argument(
        "--report", type=Path, default=Path("data/runtime/eval/latest.json")
    )
    eval_parser.add_argument("--minimum-score", type=float, default=0.08)
    publish_parser = subparsers.add_parser(
        "publish-web", help="Atomically publish a validated snapshot and optional Eval report"
    )
    publish_parser.add_argument("snapshot", type=Path)
    publish_parser.add_argument("--web-data", type=Path, default=Path("apps/web/public/data"))
    publish_parser.add_argument("--eval-report", type=Path)
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
    _runtime, _sources, topics = load_project_config()
    snapshot = load_snapshot(args.snapshot)
    result, model_calls = enrich_snapshot(
        snapshot,
        client=DeepSeekStructuredClient.from_environment(),
        cache=FileAiCache(args.cache),
        topics=topics.topics,
        max_model_calls=args.max_model_calls,
    )
    terminology_score = terminology_consistency(
        result.articles,
        load_terminology(args.terminology),
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
                "modelCallLimit": args.max_model_calls,
                "terminologyConsistency": round(terminology_score, 4),
                "output": str(args.output / "current.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


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
    print(report.model_dump_json(by_alias=True, indent=2))
    return 0


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


def publish_web(args: argparse.Namespace) -> int:
    snapshot = load_snapshot(args.snapshot)
    if snapshot.snapshot_kind == "demo" and not args.allow_demo:
        print("Refusing to publish a demo snapshot without --allow-demo.")
        return 2
    _atomic_copy(args.snapshot, args.web_data / "current.json")
    if args.eval_report:
        _atomic_copy(args.eval_report, args.web_data / "eval" / "latest.json")
    print(
        json.dumps(
            {
                "ok": True,
                "snapshotId": snapshot.snapshot_id,
                "webData": str(args.web_data),
                "evalReport": bool(args.eval_report),
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
    if args.command == "build-index":
        return build_index(args)
    if args.command == "eval-rag":
        return eval_rag(args)
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
