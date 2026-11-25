"""Compare evaluation runs: time per claim, model calls and cost.

Read-only. Name each group of runs, such as:

    uv run --env-file .env python scripts/compare_runs.py runtime=12,13 laptop=20,21,22

Times are the app's own: working time is the sum of every segment of work (failed
attempts included, as the dashboard counts it), wall clock is start to finish.
"""

import os
import sys
from datetime import datetime
from statistics import mean

import psycopg

NANOS = 1_000_000_000
NEEDED_ARGUMENTS = 2
RUNS = """
SELECT run_id, kind, status, eval_set, concurrency, model, reasoning_effort,
       started_on, finished_on
FROM undercover.runs WHERE run_id = ANY(%s)
"""
CLAIMS = """
SELECT run_id, count(*) FROM undercover.run_claims
WHERE run_id = ANY(%s) GROUP BY 1
"""
CALLS = """
SELECT run_id, count(*), coalesce(sum(cost_nanos), 0)
FROM undercover.model_calls WHERE run_id = ANY(%s) GROUP BY 1
"""
SEGMENTS = """
SELECT run_id, started_on, finished_on FROM undercover.work_segments
WHERE run_id = ANY(%s)
"""


def parse(arguments: list[str]) -> dict[str, list[int]]:
    """Read `name=1,2,3` arguments into groups of run ids."""
    groups = {}
    for argument in arguments:
        name, _, ids = argument.partition("=")
        groups[name] = [int(i) for i in ids.split(",")]
    return groups


def measure(connection: psycopg.Connection, run_ids: list[int]) -> dict[int, dict]:
    """Return each run's set, settings, claims, times, calls and cost."""
    runs = {}
    for (
        run_id,
        kind,
        status,
        eval_set,
        n,
        model,
        effort,
        started,
        finished,
    ) in connection.execute(RUNS, (run_ids,)):
        wall = (
            (
                datetime.fromisoformat(finished) - datetime.fromisoformat(started)
            ).total_seconds()
            if finished
            else None
        )
        runs[run_id] = {
            "kind": kind,
            "status": status,
            "set": eval_set,
            "n": n,
            "model": f"{model} {effort}",
            "wall": wall,
            "claims": 0,
            "calls": 0,
            "cost": 0.0,
            "work": 0.0,
        }
    for run_id, count in connection.execute(CLAIMS, (run_ids,)):
        runs[run_id]["claims"] = count
    for run_id, count, nanos in connection.execute(CALLS, (run_ids,)):
        runs[run_id]["calls"], runs[run_id]["cost"] = count, int(nanos) / NANOS
    for run_id, started, finished in connection.execute(SEGMENTS, (run_ids,)):
        span = datetime.fromisoformat(finished) - datetime.fromisoformat(started)
        runs[run_id]["work"] += span.total_seconds()
    return runs


def row(run_id: int, run: dict) -> str:
    claims = run["claims"] or 1
    wall = f"{run['wall']:6.0f}" if run["wall"] is not None else "running"
    per_wall = f"{run['wall'] / claims:6.1f}" if run["wall"] is not None else "     -"
    return (
        f"{run_id:>4} {run['status']:<9} {run['set']!s:<9} N={run['n']:<3} "
        f"{run['model']:<28} {run['claims']:>3} {wall:>7} {per_wall} "
        f"{run['work'] / claims:7.1f} {run['calls']:>5} {run['cost']:8.4f} "
        f"{run['cost'] / claims:8.5f}"
    )


def summary(runs: list[dict]) -> str:
    """The group's mean, and its lowest and highest, for each measure."""
    finished = [r for r in runs if r["wall"] is not None and r["claims"]]
    if not finished:
        return "  no finished runs"
    measures = {
        "wall s/claim": [r["wall"] / r["claims"] for r in finished],
        "work s/claim": [r["work"] / r["claims"] for r in finished],
        "cost $/claim": [r["cost"] / r["claims"] for r in finished],
        "calls/claim": [r["calls"] / r["claims"] for r in finished],
    }
    return "\n".join(
        f"  {name:<13} mean {mean(v):9.5f}   low {min(v):9.5f}   high {max(v):9.5f}"
        for name, v in measures.items()
    )


def main() -> None:
    if len(sys.argv) < NEEDED_ARGUMENTS:
        sys.exit(__doc__)
    groups = parse(sys.argv[1:])
    wanted = sorted({i for ids in groups.values() for i in ids})
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        runs = measure(connection, wanted)
    missing = [i for i in wanted if i not in runs]
    if missing:
        sys.exit(f"No such runs: {missing}")
    print(
        f"{'run':>4} {'status':<9} {'set':<9} {'N':<5} {'model, effort':<28} "
        f"{'cl':>3} {'wall s':>7} {'w/cl':>6} {'work/cl':>7} {'calls':>5} "
        f"{'cost $':>8} {'$/claim':>8}"
    )
    for name, ids in groups.items():
        print(f"\n{name}")
        for run_id in ids:
            print(row(run_id, runs[run_id]))
        print(summary([runs[i] for i in ids]))


if __name__ == "__main__":
    main()
