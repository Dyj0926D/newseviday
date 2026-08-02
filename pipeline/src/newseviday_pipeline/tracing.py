import json
from pathlib import Path

from newseviday_pipeline.models import PipelineRun


class PipelineTraceWriter:
    def __init__(self, output_dir: Path) -> None:
        self.run_dir = output_dir / "runs"

    def write(self, run: PipelineRun) -> Path:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        path = self.run_dir / f"{run.id}.json"
        payload = run.model_dump(mode="json", by_alias=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path
