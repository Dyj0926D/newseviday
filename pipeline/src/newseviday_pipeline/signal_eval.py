import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from newseviday_pipeline.models import (
    ContractModel,
    GeneratedText,
    RawFeedItem,
)
from newseviday_pipeline.stages import (
    apply_article_scoring,
    high_significance_event_candidate,
    normalize_item,
)


class BinarySignalMetrics(ContractModel):
    precision: float
    recall: float
    f1: float
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int


class KeySignalEvalReport(ContractModel):
    schema_version: str = "1.0.0"
    dataset: str
    generated_at: datetime
    case_count: int
    gate: str
    eligibility: BinarySignalMetrics
    high_significance: BinarySignalMetrics
    event_type_exact_accuracy: float
    failures: list[str]


def _binary_metrics(expected: list[bool], predicted: list[bool]) -> BinarySignalMetrics:
    pairs = list(zip(expected, predicted, strict=True))
    true_positive = sum(wanted and actual for wanted, actual in pairs)
    false_positive = sum(not wanted and actual for wanted, actual in pairs)
    false_negative = sum(wanted and not actual for wanted, actual in pairs)
    true_negative = sum(not wanted and not actual for wanted, actual in pairs)
    precision = true_positive / (true_positive + false_positive) if true_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return BinarySignalMetrics(
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        true_negative=true_negative,
    )


def evaluate_key_signal_dataset(path: Path) -> KeySignalEvalReport:
    payload = json.loads(path.read_text(encoding="utf-8"))
    generated_at = datetime.fromisoformat(payload["generatedAt"].replace("Z", "+00:00"))
    expected_eligible: list[bool] = []
    predicted_eligible: list[bool] = []
    expected_significant: list[bool] = []
    predicted_significant: list[bool] = []
    exact_event_types = 0
    failures: list[str] = []

    for index, case in enumerate(payload["cases"]):
        article = normalize_item(
            RawFeedItem(
                source_id=f"key-signal-eval-{index}",
                source_type=case["sourceType"],
                evidence_tier=case["evidenceTier"],
                url=f"https://eval.newseviday.dev/key-signal/{case['id']}",
                title=case["title"],
                summary=case["abstract"],
                language="en",
            ),
            collected_at=generated_at,
        )[0]
        published_at = datetime.fromisoformat(
            case.get("publishedAt", payload["generatedAt"]).replace("Z", "+00:00")
        )
        article.published_at = published_at
        article.topic_scores = case["topicScores"]
        article.ai = GeneratedText(
            title_zh=f"评测样例 {index + 1} 的中文标题",
            summary_zh="该中文导读只用于隔离并验证变化事件、证据质量与重点情报门禁。",
            why_it_matters="验证指标体系对不同变化类型的识别能力。",
            key_points=["验证事件类型", "验证发布门禁"],
            model="eval-fixture",
            prompt_version="key-signal-gold-v1",
            generated_at=generated_at,
        )
        apply_article_scoring(article, anchor=generated_at)
        if article.key_signal is None:
            raise ValueError(f"key_signal_missing:{case['id']}")

        wanted_eligible = bool(case["expectedEligible"])
        actual_eligible = article.key_signal.eligible
        wanted_significant = bool(case["expectedHighSignificance"])
        actual_significant = high_significance_event_candidate(article)
        wanted_types = case["expectedEventTypes"]
        actual_types = article.key_signal.event_types
        expected_eligible.append(wanted_eligible)
        predicted_eligible.append(actual_eligible)
        expected_significant.append(wanted_significant)
        predicted_significant.append(actual_significant)
        if actual_types == wanted_types:
            exact_event_types += 1
        if (
            wanted_eligible != actual_eligible
            or wanted_significant != actual_significant
            or wanted_types != actual_types
        ):
            failures.append(case["id"])

    case_count = len(payload["cases"])
    event_type_accuracy = exact_event_types / case_count if case_count else 0.0
    return KeySignalEvalReport(
        dataset=path.name,
        generated_at=generated_at,
        case_count=case_count,
        gate="pass" if not failures else "fail",
        eligibility=_binary_metrics(expected_eligible, predicted_eligible),
        high_significance=_binary_metrics(expected_significant, predicted_significant),
        event_type_exact_accuracy=round(event_type_accuracy, 4),
        failures=failures,
    )


def write_key_signal_eval_report(report: KeySignalEvalReport, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=output.parent, prefix="key-signal-", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                report.model_dump(mode="json", by_alias=True),
                stream,
                ensure_ascii=False,
                indent=2,
            )
            stream.write("\n")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
