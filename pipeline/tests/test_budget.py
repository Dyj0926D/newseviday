from datetime import UTC, date, datetime

from newseviday_pipeline.budget import (
    AiRolloverLedger,
    plan_rollover_budget,
    settle_rollover_budget,
)


def test_rollover_budget_accrues_missed_days_but_caps_the_bank_and_run() -> None:
    ledger = AiRolloverLedger(
        lastSettledDate=date(2026, 8, 18),
        balance=5,
        lastModelCalls=0,
        updatedAt=datetime(2026, 8, 18, tzinfo=UTC),
    )

    plan = plan_rollover_budget(
        ledger,
        run_date=date(2026, 8, 20),
        base_limit=5,
        rollover_cap=10,
        max_per_run=10,
    )

    assert plan.rollover_before == 10
    assert plan.daily_credit == 5
    assert plan.effective_limit == 10
    settled = settle_rollover_budget(
        plan,
        model_calls=8,
        updated_at=datetime(2026, 8, 20, tzinfo=UTC),
    )
    assert settled.balance == 7


def test_rollover_budget_does_not_grant_the_daily_credit_twice() -> None:
    ledger = AiRolloverLedger(
        lastSettledDate=date(2026, 8, 20),
        balance=4,
        lastModelCalls=6,
        updatedAt=datetime(2026, 8, 20, tzinfo=UTC),
    )

    plan = plan_rollover_budget(
        ledger,
        run_date=date(2026, 8, 20),
        base_limit=5,
        rollover_cap=10,
        max_per_run=10,
    )

    assert plan.daily_credit == 0
    assert plan.effective_limit == 4


def test_rollover_budget_uses_a_bounded_seed_for_the_first_run() -> None:
    plan = plan_rollover_budget(
        None,
        run_date=date(2026, 8, 21),
        base_limit=5,
        rollover_cap=10,
        max_per_run=10,
        seed_rollover=20,
    )

    assert plan.rollover_before == 10
    assert plan.effective_limit == 10
