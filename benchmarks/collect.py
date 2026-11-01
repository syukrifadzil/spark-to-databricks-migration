"""Benchmark results collector. It turns what a run reports about itself into rows of
benchmarks/results/runs.csv, and summarises that file. It never starts a run, and it records
nothing the run did not report. Method and scenarios: benchmarks/README.md.

Run from the repository root:

    python -m benchmarks.collect legacy --scenario B1 --preset small --dataset anomalous \\
        --metrics output/benchmarks/B1_1/baseline_metrics.json
    databricks jobs get-run <run_id> -o json > output/benchmarks/run_<run_id>.json
    python -m benchmarks.collect job --scenario B3 --preset small --dataset anomalous \\
        --run-json output/benchmarks/run_<run_id>.json
    python -m benchmarks.collect manual --scenario B5 --preset small --dataset anomalous \\
        --system pipeline_update --run-ref <update_id> --started-at 2026-11-02T01:00:00Z --seconds 138
    python -m benchmarks.collect summary
"""
import argparse
import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results" / "runs.csv"
COLUMNS = ["scenario", "system", "preset", "dataset", "run_ref", "started_at_utc", "unit", "seconds", "result"]
PASSED = ("ok", "SUCCESS")


def utc(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def legacy_rows(metrics, common):
    """One row from the legacy job's baseline_metrics.json, which records its own duration."""
    return [dict(common, system="legacy_local", run_ref=metrics["started_at_utc"],
                 started_at_utc=metrics["started_at_utc"], unit="total",
                 seconds=metrics["duration_seconds"], result="ok")]


def job_rows(run, common):
    """One row for the whole run and one per task, from `databricks jobs get-run -o json`.
    Only ids, times and states are kept: the JSON also holds the workspace URL and the user's
    name, which must not reach git."""
    if not run.get("end_time"):
        raise ValueError(f"run {run.get('run_id')} has not finished")

    def row(unit, item):
        return dict(common, system="databricks_job", run_ref=str(run["run_id"]),
                    started_at_utc=utc(item["start_time"]), unit=unit,
                    seconds=round((item["end_time"] - item["start_time"]) / 1000, 1),
                    result=item.get("state", {}).get("result_state", "UNKNOWN"))
    # A task that never started (skipped after a failure) has no times to measure.
    return [row("total", run)] + [row(t["task_key"], t) for t in run.get("tasks", [])
                                  if t.get("start_time") and t.get("end_time")]


def append(path, rows):
    """Appends rows not already in the file, keyed by scenario, run and unit, so collecting the
    same run twice cannot weight the median. Returns the number added."""
    existing = set()
    if path.exists() and path.stat().st_size:
        with path.open(newline="") as f:
            existing = {(r["scenario"], r["run_ref"], r["unit"]) for r in csv.DictReader(f)}
    new = [r for r in rows if (r["scenario"], r["run_ref"], r["unit"]) not in existing]
    write_header = not path.exists() or not path.stat().st_size
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerows(new)
    return len(new)


def summary(path):
    """Markdown table: runs, median, min and max seconds per scenario and unit, passed runs only."""
    groups = {}
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            if r["result"] in PASSED:
                key = (r["scenario"], r["system"], r["preset"], r["dataset"], r["unit"])
                groups.setdefault(key, []).append(float(r["seconds"]))
    lines = ["| Scenario | System | Preset | Dataset | Unit | Runs | Median s | Min s | Max s |",
             "|---|---|---|---|---|---|---|---|---|"]
    for key, values in sorted(groups.items()):
        lines.append("| " + " | ".join(key) + f" | {len(values)} | {statistics.median(values):.1f}"
                     f" | {min(values):.1f} | {max(values):.1f} |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Record and summarise benchmark runs.")
    parser.add_argument("--results", type=Path, default=RESULTS, help="CSV file to append to")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, source in (("legacy", "--metrics"), ("job", "--run-json"), ("manual", None)):
        command = commands.add_parser(name)
        command.add_argument("--scenario", required=True, help="benchmark id, for example B3")
        command.add_argument("--preset", required=True, help="generator preset: small or medium")
        command.add_argument("--dataset", required=True, help="clean or anomalous")
        if source:
            command.add_argument(source, dest="source", type=Path, required=True)
    manual = commands.choices["manual"]
    manual.add_argument("--system", required=True, help="for example pipeline_update or sql_editor")
    manual.add_argument("--run-ref", required=True, help="update id, run id or statement label")
    manual.add_argument("--started-at", required=True, help="UTC, for example 2026-11-02T01:00:00Z")
    manual.add_argument("--seconds", type=float, required=True)
    manual.add_argument("--unit", default="total")
    manual.add_argument("--result", default="ok")
    commands.add_parser("summary")
    args = parser.parse_args(argv)

    if args.command == "summary":
        print(summary(args.results))
        return 0
    common = {"scenario": args.scenario, "preset": args.preset, "dataset": args.dataset}
    if args.command == "manual":
        rows = [dict(common, system=args.system, run_ref=args.run_ref, started_at_utc=args.started_at,
                     unit=args.unit, seconds=args.seconds, result=args.result)]
    else:
        data = json.loads(args.source.read_text())
        rows = legacy_rows(data, common) if args.command == "legacy" else job_rows(data, common)
    added = append(args.results, rows)
    print(f"{added} of {len(rows)} rows added to {args.results}")
    for r in rows:
        print(f"  {r['scenario']} {r['system']} {r['unit']}: {r['seconds']} s, {r['result']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
