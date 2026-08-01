import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from newseviday_pipeline import __version__
from newseviday_pipeline.runner import run_fixture_pipeline
from newseviday_pipeline.settings import load_project_config
from newseviday_pipeline.snapshot import load_snapshot

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

    validate_parser = subparsers.add_parser("validate-snapshot", help="Validate a snapshot JSON")
    validate_parser.add_argument("path", type=Path)
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


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        return doctor()
    if args.command == "validate-snapshot":
        return validate_snapshot(args.path)
    if args.command == "run" and args.dry_run:
        return dry_run()
    if args.command == "run" and args.fixture:
        return run_fixture(args)

    print("Network collection is disabled. Pass --fixture or --dry-run.")
    return 2
