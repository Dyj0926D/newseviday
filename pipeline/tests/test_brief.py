from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from newseviday_pipeline.ai import (
    FileAiCache,
    _last_complete_seven_day_window,
    update_weekly_brief,
)
from newseviday_pipeline.editorial import apply_editorial_package, load_editorial_package
from newseviday_pipeline.snapshot import load_snapshot

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = (
    ROOT
    / "apps"
    / "web"
    / "public"
    / "data"
    / "versions"
    / "snapshot-20260810T031024Z-e3340841-ai-12c83ca0.json"
)
PACKAGE = ROOT / "data" / "editorial" / "近期中文与首期周报-2026-08-10.json"


class FakeBriefClient:
    model = "deepseek-test"

    def __init__(self) -> None:
        self.calls = 0

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        self.calls += 1
        return {
            "title": "一周 Agent 产品与工程趋势",
            "sections": [
                {
                    "heading": "Agent 工作流开始同时关注任务编排与检索效率",
                    "body": (
                        "两家不同来源同时讨论 Agent 工作流、实际任务使用与检索效率，"
                        "说明工程关注点正在从单次问答扩展到任务过程与运行成本。"
                    ),
                    "evidenceIds": [
                        "evidence-aaeaa892ea6a66d00483",
                        "evidence-565f07e8223aea328340",
                    ],
                }
            ],
        }


def test_weekly_brief_generates_once_and_reuses_the_published_period(tmp_path: Path) -> None:
    source = load_snapshot(SNAPSHOT)
    prepared = apply_editorial_package(source, load_editorial_package(PACKAGE))
    prepared.briefs = []
    client = FakeBriefClient()
    generated = update_weekly_brief(
        prepared,
        accepted_snapshot=None,
        client=client,
        cache=FileAiCache(tmp_path),
        now=datetime(2026, 8, 8, 2, tzinfo=UTC),
    )

    assert generated.status == "generated"
    assert generated.model_calls == 1
    assert client.calls == 1
    assert len(generated.snapshot.briefs) == 1
    assert generated.snapshot.briefs[0].generated_by is not None
    assert generated.snapshot.briefs[0].generated_by.provider == "deepseek"
    assert generated.period_start == datetime(2026, 8, 1, 1, tzinfo=UTC)
    assert generated.period_end == datetime(2026, 8, 8, 1, tzinfo=UTC)

    reused = update_weekly_brief(
        generated.snapshot,
        accepted_snapshot=generated.snapshot,
        client=FakeBriefClient(),
        cache=FileAiCache(tmp_path),
        now=datetime(2026, 8, 8, 3, tzinfo=UTC),
    )
    assert reused.status == "current"
    assert reused.model_calls == 0
    assert reused.snapshot.briefs[0].id == generated.snapshot.briefs[0].id
    assert reused.snapshot.snapshot_id == generated.snapshot.snapshot_id


def test_weekly_brief_is_carried_on_non_saturday_refresh(tmp_path: Path) -> None:
    source = load_snapshot(SNAPSHOT)
    accepted = apply_editorial_package(source, load_editorial_package(PACKAGE))
    incoming = source.model_copy(deep=True)
    incoming.briefs = []

    carried = update_weekly_brief(
        incoming,
        accepted_snapshot=accepted,
        client=None,
        cache=FileAiCache(tmp_path),
        now=datetime(2026, 8, 11, 2, tzinfo=UTC),
    )

    assert carried.status == "carried"
    assert carried.model_calls == 0
    assert carried.snapshot.briefs[0].id == accepted.briefs[0].id


def test_weekly_brief_can_force_last_complete_window_after_saturday(tmp_path: Path) -> None:
    source = load_snapshot(SNAPSHOT)
    prepared = apply_editorial_package(source, load_editorial_package(PACKAGE))
    prepared.briefs = []
    client = FakeBriefClient()

    generated = update_weekly_brief(
        prepared,
        accepted_snapshot=None,
        client=client,
        cache=FileAiCache(tmp_path),
        now=datetime(2026, 8, 10, 2, tzinfo=UTC),
        force_generate=True,
    )

    assert generated.status == "generated"
    assert generated.model_calls == 1
    assert client.calls == 1
    assert generated.period_start == datetime(2026, 8, 1, 1, tzinfo=UTC)
    assert generated.period_end == datetime(2026, 8, 8, 1, tzinfo=UTC)


def test_weekly_window_uses_previous_cutoff_before_saturday_nine() -> None:
    period_start, period_end = _last_complete_seven_day_window(
        datetime(2026, 8, 8, 0, 30, tzinfo=UTC)
    )

    assert period_start == datetime(2026, 7, 25, 1, tzinfo=UTC)
    assert period_end == datetime(2026, 8, 1, 1, tzinfo=UTC)


def test_weekly_brief_rejects_opinion_only_support(tmp_path: Path) -> None:
    source = load_snapshot(SNAPSHOT)
    prepared = apply_editorial_package(source, load_editorial_package(PACKAGE))
    prepared.briefs = []
    for article in prepared.articles:
        article.source_type = "independent_author"
        article.evidence_tier = "opinion"

    with pytest.raises(
        ValueError,
        match="weekly_brief_requires_primary_or_two_secondary_sources",
    ):
        update_weekly_brief(
            prepared,
            accepted_snapshot=None,
            client=FakeBriefClient(),
            cache=FileAiCache(tmp_path),
            now=datetime(2026, 8, 8, 2, tzinfo=UTC),
        )
