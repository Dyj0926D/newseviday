import json
import os
import tempfile
from pathlib import Path
from typing import Any

from newseviday_pipeline.models import ContentSnapshot


def snapshot_json(snapshot: ContentSnapshot) -> str:
    payload = snapshot.model_dump(mode="json", by_alias=True)
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


class SnapshotPublisher:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.versions_dir = output_dir / "versions"

    def publish_payload(self, payload: dict[str, Any]) -> Path:
        snapshot = ContentSnapshot.model_validate(payload)
        return self.publish(snapshot)

    def publish(self, snapshot: ContentSnapshot) -> Path:
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        current_path = self.output_dir / "current.json"
        version_path = self.versions_dir / f"{snapshot.snapshot_id}.json"
        content = snapshot_json(snapshot)

        if version_path.exists():
            existing = version_path.read_text(encoding="utf-8")
            if existing != content:
                raise FileExistsError(f"snapshot_id_already_exists: {snapshot.snapshot_id}")
        else:
            version_path.write_text(content, encoding="utf-8", newline="\n")

        handle, temporary_name = tempfile.mkstemp(
            dir=self.output_dir,
            prefix="current-",
            suffix=".json.tmp",
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            temporary_path.replace(current_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return current_path


def load_snapshot(path: Path) -> ContentSnapshot:
    return ContentSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
