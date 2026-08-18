from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("workflow_path", "variable_name"),
    [
        (".github/workflows/content-refresh.yml", "DAILY_REFRESH_AUTO_MERGE"),
        (".github/workflows/weekly-brief.yml", "WEEKLY_REFRESH_AUTO_MERGE"),
    ],
)
def test_automatic_content_publication_is_opt_in_and_schedule_only(
    workflow_path: str,
    variable_name: str,
) -> None:
    workflow = (REPOSITORY_ROOT / workflow_path).read_text(encoding="utf-8")

    assert f"{variable_name}: ${{{{ vars.{variable_name} || 'false' }}}}" in workflow
    assert (
        f'"$GITHUB_EVENT_NAME" == "schedule" && "${variable_name}" == "true"'
        in workflow
    )
    assert "gh pr merge" in workflow

