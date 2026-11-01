"""Static checks on the bundle configuration. No Databricks CLI needed."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_job_installs_the_pinned_dbt_versions():
    # The job's dbt task must run the dbt versions recorded in Phase 04, not whatever is newest.
    bundle = (ROOT / "databricks.yml").read_text()
    for line in (ROOT / "requirements-dbt.txt").read_text().splitlines():
        if line and not line.startswith("#"):
            assert f"- {line}" in bundle, line


def test_python_files_in_the_job_exist():
    # A wrong python_file path is only reported when the task starts in the workspace.
    for line in (ROOT / "databricks.yml").read_text().splitlines():
        if line.strip().startswith("python_file:"):
            assert (ROOT / line.split(":", 1)[1].strip()).is_file(), line
