from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from newseviday_pipeline.models import RuntimeConfig, SourcesConfig, TopicsConfig

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"Configuration must be a mapping: {path}")
    return data


def load_config[ConfigModel: BaseModel](path: Path, model: type[ConfigModel]) -> ConfigModel:
    return model.model_validate(_read_yaml(path))


def load_project_config(
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> tuple[RuntimeConfig, SourcesConfig, TopicsConfig]:
    runtime = load_config(config_dir / "runtime.yaml", RuntimeConfig)
    sources = load_config(config_dir / "sources.yaml", SourcesConfig)
    topics = load_config(config_dir / "topics.yaml", TopicsConfig)
    return runtime, sources, topics
