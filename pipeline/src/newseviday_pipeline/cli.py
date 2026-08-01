import argparse
import json
from collections.abc import Sequence

from newseviday_pipeline import __version__
from newseviday_pipeline.settings import load_project_config

PIPELINE_STAGES = (
    "fetch",
    "extract",
    "normalize",
    "deduplicate",
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


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        return doctor()
    if args.command == "run" and args.dry_run:
        return dry_run()

    print("Actual pipeline execution is not enabled in the engineering skeleton.")
    return 2
