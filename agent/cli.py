"""Command line for the agent: `uv run -m agent.cli --limit 5` or `--claim CLM-1001`."""

import argparse

from agent.runner import run


def main(argv: list[str] | None = None) -> str:
    """Run the agent on the queue, up to a limit, or on one named claim."""
    parser = argparse.ArgumentParser(description="Run the UnderCover Agent.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--limit", type=int, help="work at most this many claims")
    group.add_argument("--claim", help="work only this claim")
    args = parser.parse_args(argv)
    summary = run(cap=args.limit, claim_id=args.claim or "")
    print(summary)  # noqa: T201
    return summary


if __name__ == "__main__":
    main()
