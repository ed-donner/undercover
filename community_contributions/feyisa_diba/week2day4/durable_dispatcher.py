"""Stretch challenge: the scoring dispatcher, durable on Supabase with LangGraph's PostgresSaver.

The demo starts the dispatcher in a child process on a new thread and hard-kills that process
(os._exit, no cleanup, like restarting the kernel) after a few claims have finished. It then
reads the thread's checkpoint to see which work_claim tasks were saved, starts a second process
that runs invoke(None, config) on the same thread, and checks from the workers' log which
claims were worked again.

    uv run --env-file ../../../.env python durable_dispatcher.py demo
    uv run --env-file ../../../.env python durable_dispatcher.py cleanup   # drops this demo's schema

The checkpoints go in a schema of their own, w2d4_feyisa_durable, never in the product's
undercover schema. The workers are stand-ins, so the demo makes no model requests.
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import RetryPolicy
from psycopg.rows import dict_row

import score_dispatcher as sd

SCHEMA = "w2d4_feyisa_durable"
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
CRASH_EXIT_CODE = 137


# Postgres


def connect(url: str) -> psycopg.Connection:
    """One connection to Supabase, in this demo's schema, as the product's checkpointer connects."""
    with psycopg.connect(url, autocommit=True, prepare_threshold=0) as setup:
        setup.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    return psycopg.connect(
        url, autocommit=True, prepare_threshold=0, row_factory=dict_row, options=f"-c search_path={SCHEMA}"
    )


def postgres_saver(url: str) -> PostgresSaver:
    saver = PostgresSaver(connect(url))
    saver.setup()
    return saver


def drop_schema(url: str) -> None:
    with psycopg.connect(url, autocommit=True, prepare_threshold=0) as connection:
        connection.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")


# The workers' log: every start and finish, from every process, so we can see what was rerun


LOG_LOCK = threading.Lock()


def log_event(log: Path, event: str, **fields) -> None:
    """Append one event and force it to disk, so it survives the kill.

    The lock matters: on Windows, appends from several threads at once can overwrite each other."""
    line = json.dumps({"event": event, "pid": os.getpid(), "at": datetime.now().isoformat(), **fields})
    with LOG_LOCK, log.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_log(log: Path) -> list[dict]:
    """Every complete event in the log. A line cut short by the kill is skipped."""
    if not log.exists():
        return []
    events = []
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def logged_worker(labels: dict, log: Path, delay: float, stagger: float = 0.0):
    """The lab's stand-in claim agent, logging when it starts and finishes each claim.

    Claim number i takes delay + i * stagger seconds, so the claims finish one by one."""
    order = {claim_id: index for index, claim_id in enumerate(sorted(labels))}

    def work_claim(claim_id: str) -> dict:
        log_event(log, "start", claim_id=claim_id)
        result = sd.make_stand_in(labels, delay=delay + order[claim_id] * stagger)(claim_id)
        log_event(log, "finish", claim_id=claim_id)
        return result

    return work_claim


def build(labels: dict, claim_ids: list[str], log: Path, delay: float, checkpointer, stagger: float = 0.0):
    return sd.build_dispatcher(
        logged_worker(labels, log, delay, stagger),
        claim_ids,
        labels,
        checkpointer=checkpointer,
        retry_policy=RetryPolicy(max_attempts=3),
        on_score=lambda scores: log_event(log, "score_run", claims=scores["claims"]),
    )


def run_config(thread_id: str, concurrency: int, run_name: str) -> tuple[dict, object]:
    """The thread's config, traced in one Langfuse session per thread when the keys are set."""
    config = {"configurable": {"thread_id": thread_id}, "max_concurrency": concurrency, "run_name": run_name}
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        return config, None
    from langfuse.langchain import CallbackHandler

    handler = CallbackHandler()
    config |= {"callbacks": [handler], "metadata": {"langfuse_session_id": f"durable-dispatch {thread_id}"}}
    return config, handler


# What the checkpoint holds


def inspect_thread(graph, config: dict, claim_ids: list[str]) -> dict:
    """Read the thread's latest checkpoint: where it stopped, and which work_claim tasks saved their result.

    Each Send becomes a task whose path is ('__pregel_push', index), in the order fan_out sent them."""
    snapshot = graph.get_state(config)
    saved, unsaved = [], []
    for task in snapshot.tasks:
        if task.name != "work_claim":
            continue
        claim_id = claim_ids[task.path[1]]
        (saved if task.result else unsaved).append(claim_id)
    return {
        "next": list(snapshot.next),
        "checkpoints": sum(1 for _ in graph.get_state_history(config)),
        "saved_tasks": sorted(saved),
        "unsaved_tasks": sorted(unsaved),
        "results_in_state": len(snapshot.values.get("results", [])),
        "scores_in_state": "scores" in snapshot.values,
    }


# The child processes


def child(args) -> None:
    """Run (and maybe crash) or resume the dispatcher on a thread. Runs in its own process."""
    labels = sd.load_labels()
    claim_ids = sorted(labels)[: args.claims]
    log = Path(args.log)
    graph = build(labels, claim_ids, log, args.delay, postgres_saver(os.environ["DATABASE_URL"]), args.stagger)

    if args.mode == "run":
        config, handler = run_config(args.thread, args.concurrency, "Durable dispatch: first run (killed)")
        if args.crash_after:
            watchdog(log, args.crash_after, handler)
        graph.invoke({}, config, durability="sync")
        return

    config, handler = run_config(args.thread, args.concurrency, "Durable dispatch: resume")
    state = graph.invoke(None, config, durability="sync")
    if handler:
        from langfuse import get_client

        langfuse = get_client()
        sd.send_scores(langfuse, handler.last_trace_id, state["scores"])
        langfuse.flush()
        log_event(log, "trace", trace_id=handler.last_trace_id)


def watchdog(log: Path, crash_after: int, handler) -> None:
    """Kill this process, with no cleanup, once crash_after claims have finished in it."""
    pid = os.getpid()

    def watch() -> None:
        while sum(1 for e in read_log(log) if e["event"] == "finish" and e["pid"] == pid) < crash_after:
            time.sleep(0.02)
        if handler:  # let Langfuse see what had happened before the crash, as a real exporter would have sent it
            from langfuse import get_client

            get_client().flush()
            log_event(log, "trace", trace_id=handler.last_trace_id)
        log_event(log, "crash")
        os._exit(CRASH_EXIT_CODE)

    threading.Thread(target=watch, daemon=True).start()


def spawn(mode: str, thread_id: str, log: Path, scenario: dict, crash_after: int = 0) -> int:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "child",
        mode,
        "--thread",
        thread_id,
        "--log",
        str(log),
        "--claims",
        str(scenario["claims"]),
        "--concurrency",
        str(scenario["concurrency"]),
        "--delay",
        str(scenario["delay"]),
        "--stagger",
        str(scenario["stagger"]),
        "--crash-after",
        str(crash_after),
    ]
    return subprocess.run(command, cwd=HERE, check=False).returncode  # noqa: S603


# The demo


def analyse(events: list[dict], first_pid: int | None, before_resume: dict, claim_ids: list[str], final: dict) -> dict:
    """Compare what the log says each process did with what the checkpoint saved."""

    def claims(event: str, pid_filter) -> list[str]:
        return sorted(e["claim_id"] for e in events if e["event"] == event and pid_filter(e["pid"]))

    first = lambda pid: pid == first_pid  # noqa: E731
    second = lambda pid: pid != first_pid  # noqa: E731
    finished_first = claims("finish", first)
    started_first = claims("start", first)
    rerun = claims("start", second)
    result_ids = [r["claim_id"] for r in final["results"]]
    return {
        "finished_before_crash": finished_first,
        "in_flight_at_crash": sorted(set(started_first) - set(finished_first)),
        "never_started_before_crash": sorted(set(claim_ids) - set(started_first)),
        "saved_in_checkpoint": before_resume["saved_tasks"],
        "worked_on_resume": rerun,
        "checks": {
            "only_unsaved_tasks_rerun": rerun == before_resume["unsaved_tasks"],
            "no_saved_task_rerun": not set(rerun) & set(before_resume["saved_tasks"]),
            "every_claim_has_a_result": sorted(result_ids) == sorted(claim_ids),
            "no_duplicate_results": len(result_ids) == len(set(result_ids)),
            "score_run_ran_once": sum(1 for e in events if e["event"] == "score_run") == 1,
            "scores_cover_every_claim": final["scores"]["claims"] == len(claim_ids),
        },
    }


def run_scenario(name: str, scenario: dict) -> dict:
    """Kill a run partway, inspect the checkpoint, resume on the same thread and check the recovery."""
    url = os.environ["DATABASE_URL"]
    labels = sd.load_labels()
    claim_ids = sorted(labels)[: scenario["claims"]]
    thread_id = f"w2d4-durable-{name}-{uuid.uuid4()}"
    RESULTS.mkdir(exist_ok=True)
    log = RESULTS / f"durable_log_{name}.jsonl"
    log.unlink(missing_ok=True)
    print(f"\n== {name}: {scenario['description']}\nThread {thread_id}")

    code = spawn("run", thread_id, log, scenario, scenario["crash_after"])
    print(f"First process exited with code {code} ({'killed' if code == CRASH_EXIT_CODE else 'NOT killed'})")
    first_pid = next((e["pid"] for e in read_log(log) if e["event"] == "crash"), None)

    saver = postgres_saver(url)
    graph = build(labels, claim_ids, log, scenario["delay"], saver, scenario["stagger"])
    config = {"configurable": {"thread_id": thread_id}}
    before = inspect_thread(graph, config, claim_ids)
    print(f"Checkpoint after the kill: next={sorted(set(before['next']))}, saved {before['saved_tasks']}")

    resume_code = spawn("resume", thread_id, log, scenario)
    print(f"Resume process exited with code {resume_code}")
    final = graph.get_state(config).values
    after = inspect_thread(graph, config, claim_ids)
    saver.conn.close()

    events = read_log(log)
    analysis = analyse(events, first_pid, before, claim_ids, final)
    analysis["finished_but_lost"] = sorted(set(analysis["finished_before_crash"]) - set(before["saved_tasks"]))
    report = {
        "scenario": name,
        "thread_id": thread_id,
        "settings": scenario,
        "first_exit_code": code,
        "resume_exit_code": resume_code,
        "checkpoint_before_resume": before,
        "checkpoint_after_resume": after,
        **analysis,
        "scores": final.get("scores"),
        "langfuse": {
            "session_id": f"durable-dispatch {thread_id}" if os.getenv("LANGFUSE_PUBLIC_KEY") else None,
            "trace_ids": [e["trace_id"] for e in events if e["event"] == "trace"],
        },
    }
    keys = (
        "finished_before_crash",
        "in_flight_at_crash",
        "never_started_before_crash",
        "saved_in_checkpoint",
        "finished_but_lost",
        "worked_on_resume",
        "checks",
    )
    print(json.dumps({key: report[key] for key in keys}, indent=2))
    return report


SCENARIOS = {
    "capped": {
        "description": "max_concurrency=2 below the 8 claims sent, the lab's setting",
        "claims": 8,
        "concurrency": 2,
        "delay": 1.5,
        "stagger": 0.0,
        "crash_after": 3,
    },
    "uncapped": {
        "description": "max_concurrency=8, every claim running at once, finishing one by one",
        "claims": 8,
        "concurrency": 8,
        "delay": 1.0,
        "stagger": 0.75,
        "crash_after": 3,
    },
}


def demo(names: list[str]) -> list[dict]:
    reports = [run_scenario(name, SCENARIOS[name]) for name in names]
    (RESULTS / "durable_run.json").write_text(json.dumps(reports, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved {RESULTS / 'durable_run.json'}")
    return reports


def langfuse_traces() -> list[dict]:
    """Read each demo session back from Langfuse and count the spans in each trace by name.

    Run it a minute after the demo: Langfuse ingests traces in the background."""
    from collections import Counter

    from langfuse import get_client

    langfuse = get_client()
    sessions = []
    for report in json.loads((RESULTS / "durable_run.json").read_text(encoding="utf-8")):
        session_id = report["langfuse"]["session_id"]
        if not session_id:
            continue
        for attempt in range(3):
            try:
                observations = langfuse.api.observations.get_many(session_id=session_id, limit=1000).data
                break
            except Exception:  # Langfuse's API sometimes times out; try again
                if attempt == 2:
                    raise
                time.sleep(5)
        spans: dict[str, Counter] = {}
        for observation in observations:
            spans.setdefault(observation.trace_id, Counter())[observation.name] += 1
        traces = [{"trace_id": trace_id, "spans": dict(counts)} for trace_id, counts in spans.items()]
        sessions.append({"scenario": report["scenario"], "session_id": session_id, "traces": traces})
        print(f"{report['scenario']}: session {session_id!r}")
        for trace in traces:
            print(f"  {trace['trace_id']}: {trace['spans']}")
    (RESULTS / "langfuse_traces.json").write_text(json.dumps(sessions, indent=2), encoding="utf-8")
    return sessions


def main() -> None:
    parser = argparse.ArgumentParser(description="Durable dispatcher demo on Supabase")
    commands = parser.add_subparsers(dest="command", required=True)
    run_demo = commands.add_parser("demo")
    run_demo.add_argument("scenarios", nargs="*", default=list(SCENARIOS), help=f"any of {', '.join(SCENARIOS)}")
    commands.add_parser("cleanup")
    commands.add_parser("traces")
    run_child = commands.add_parser("child")
    run_child.add_argument("mode", choices=["run", "resume"])
    for name, kind in (
        ("--thread", str),
        ("--log", str),
        ("--claims", int),
        ("--concurrency", int),
        ("--delay", float),
        ("--stagger", float),
        ("--crash-after", int),
    ):
        run_child.add_argument(name, type=kind, required=True)
    args = parser.parse_args()

    if not os.getenv("DATABASE_URL"):
        sys.exit("DATABASE_URL is not set. Run with: uv run --env-file ../../../.env python durable_dispatcher.py demo")
    if args.command == "demo":
        unknown = set(args.scenarios) - set(SCENARIOS)
        if unknown:
            parser.error(f"unknown scenarios {sorted(unknown)}; choose from {list(SCENARIOS)}")
        reports = demo(args.scenarios)
        sys.exit(0 if all(all(r["checks"].values()) for r in reports) else 1)
    elif args.command == "traces":
        langfuse_traces()
    elif args.command == "cleanup":
        drop_schema(os.environ["DATABASE_URL"])
        print(f"Dropped schema {SCHEMA}")
    else:
        child(args)


if __name__ == "__main__":
    main()
