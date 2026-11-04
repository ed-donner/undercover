"""Command line for the agent: `uv run -m agent.cli --limit 5` or `--claim CLM-1001`."""

import argparse
import sys

from dotenv import load_dotenv

from agent.runner import run


def main(argv: list[str] | None = None) -> str:
    """Run the agent on the queue, up to a limit, or on one named claim."""
    parser = argparse.ArgumentParser(description="Run the UnderCover Agent.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--limit", "--cap", type=int, help="work at most this many claims"
    )
    group.add_argument("--claim", help="work only this claim")
    args = parser.parse_args(argv)
    load_dotenv(override=True)
    summary = run(cap=args.limit, claim_id=args.claim or "")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print(summary)  # noqa: T201
    return summary


if __name__ == "__main__":
    main()
