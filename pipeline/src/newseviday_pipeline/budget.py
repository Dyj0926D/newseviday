import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import Field

from newseviday_pipeline.models import ContractModel


class AiRolloverLedger(ContractModel):
    schema_version: str = "1.0.0"
    last_settled_date: date
    balance: int = Field(ge=0)
    last_model_calls: int = Field(ge=0)
    updated_at: datetime


@dataclass(frozen=True)
class RolloverBudgetPlan:
    run_date: date
    base_limit: int
    daily_credit: int
    rollover_before: int
    rollover_cap: int
    max_per_run: int
    effective_limit: int


def load_rollover_ledger(path: Path) -> AiRolloverLedger | None:
    if not path.exists():
        return None
    return AiRolloverLedger.model_validate_json(path.read_text(encoding="utf-8"))


def plan_rollover_budget(
    ledger: AiRolloverLedger | None,
    *,
    run_date: date,
    base_limit: int,
    rollover_cap: int,
    max_per_run: int,
    seed_rollover: int = 0,
) -> RolloverBudgetPlan:
    if min(base_limit, rollover_cap, max_per_run, seed_rollover) < 0:
        raise ValueError("rollover_budget_values_must_be_nonnegative")
    if max_per_run > 10:
        raise ValueError("rollover_max_per_run_must_not_exceed_ten")
    if ledger is None:
        rollover_before = min(rollover_cap, seed_rollover)
        daily_credit = base_limit
    elif ledger.last_settled_date < run_date:
        elapsed_days = (run_date - ledger.last_settled_date).days
        missed_daily_credits = max(0, elapsed_days - 1) * base_limit
        rollover_before = min(rollover_cap, ledger.balance + missed_daily_credits)
        daily_credit = base_limit
    else:
        rollover_before = min(rollover_cap, ledger.balance)
        daily_credit = 0
    effective_limit = min(max_per_run, rollover_before + daily_credit)
    return RolloverBudgetPlan(
        run_date=run_date,
        base_limit=base_limit,
        daily_credit=daily_credit,
        rollover_before=rollover_before,
        rollover_cap=rollover_cap,
        max_per_run=max_per_run,
        effective_limit=effective_limit,
    )


def settle_rollover_budget(
    plan: RolloverBudgetPlan,
    *,
    model_calls: int,
    updated_at: datetime | None = None,
) -> AiRolloverLedger:
    if not 0 <= model_calls <= plan.effective_limit:
        raise ValueError("model_calls_outside_effective_rollover_limit")
    balance = min(
        plan.rollover_cap,
        max(0, plan.rollover_before + plan.daily_credit - model_calls),
    )
    return AiRolloverLedger(
        last_settled_date=plan.run_date,
        balance=balance,
        last_model_calls=model_calls,
        updated_at=updated_at or datetime.now(UTC),
    )


def write_rollover_ledger(ledger: AiRolloverLedger, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=path.parent, prefix="ai-budget-", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                ledger.model_dump(mode="json", by_alias=True),
                stream,
                ensure_ascii=False,
                indent=2,
            )
            stream.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
