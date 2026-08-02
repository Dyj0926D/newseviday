import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from newseviday_pipeline.models import RawFeedItem
from newseviday_pipeline.stages import fuzzy_similarity, normalize_item


class DedupExample(BaseModel):
    id: str
    left_title: str = Field(alias="leftTitle")
    left_summary: str = Field(alias="leftSummary")
    right_title: str = Field(alias="rightTitle")
    right_summary: str = Field(alias="rightSummary")
    duplicate: bool


class DedupDataset(BaseModel):
    version: str
    review_status: str = Field(alias="reviewStatus")
    examples: list[DedupExample]


@dataclass(frozen=True)
class DedupEvalResult:
    dataset_version: str
    review_status: str
    sample_count: int
    precision: float
    recall: float
    f1: float
    threshold: float

    def as_dict(self) -> dict[str, str | int | float]:
        return {
            "datasetVersion": self.dataset_version,
            "reviewStatus": self.review_status,
            "sampleCount": self.sample_count,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "threshold": self.threshold,
        }


def _item(url: str, title: str, summary: str) -> RawFeedItem:
    return RawFeedItem(
        source_id="dedup-eval",
        url=url,
        title=title,
        summary=summary,
        language="mixed",
    )


def evaluate_dedup_dataset(path: Path, *, threshold: float = 0.82) -> DedupEvalResult:
    dataset = DedupDataset.model_validate_json(path.read_text(encoding="utf-8"))
    true_positive = false_positive = false_negative = 0
    for index, example in enumerate(dataset.examples):
        left = normalize_item(
            _item(f"https://example.com/left/{index}", example.left_title, example.left_summary)
        )[0]
        right = normalize_item(
            _item(f"https://example.com/right/{index}", example.right_title, example.right_summary)
        )[0]
        predicted = fuzzy_similarity(left, right) >= threshold
        true_positive += int(predicted and example.duplicate)
        false_positive += int(predicted and not example.duplicate)
        false_negative += int(not predicted and example.duplicate)
    precision = true_positive / (true_positive + false_positive or 1)
    recall = true_positive / (true_positive + false_negative or 1)
    f1 = 2 * precision * recall / (precision + recall or 1)
    return DedupEvalResult(
        dataset_version=dataset.version,
        review_status=dataset.review_status,
        sample_count=len(dataset.examples),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        threshold=threshold,
    )


def write_dedup_report(result: DedupEvalResult, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result.as_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
