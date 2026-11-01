"""The benchmark collector on a hand-made job run: rows, no URLs or names, no double counting."""
from benchmarks import collect

COMMON = {"scenario": "B3", "preset": "small", "dataset": "anomalous"}
RUN = {
    "run_id": 42, "start_time": 1_000_000, "end_time": 1_160_500, "state": {"result_state": "SUCCESS"},
    "run_page_url": "https://workspace.example.invalid/jobs/1/runs/42", "creator_user_name": "someone@example.invalid",
    "tasks": [
        {"task_key": "gold", "start_time": 1_000_000, "end_time": 1_090_000, "state": {"result_state": "SUCCESS"}},
        {"task_key": "reconciliation", "start_time": 0, "end_time": 0, "state": {"result_state": "UPSTREAM_FAILED"}},
    ],
}


def test_job_run_is_recorded_once_without_urls_or_user_names(tmp_path):
    results = tmp_path / "runs.csv"
    rows = collect.job_rows(RUN, COMMON)
    assert [(r["unit"], r["seconds"], r["result"]) for r in rows] == [("total", 160.5, "SUCCESS"),
                                                                      ("gold", 90.0, "SUCCESS")]
    assert rows[0]["started_at_utc"] == "1970-01-01T00:16:40Z"
    assert collect.append(results, rows) == 2
    assert collect.append(results, rows) == 0
    assert "example.invalid" not in results.read_text()
    assert "| B3 | databricks_job | small | anomalous | total | 1 | 160.5 | 160.5 | 160.5 |" in collect.summary(results)
