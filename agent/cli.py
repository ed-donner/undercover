"""Start the UnderCover Agent from the command line.

uv run python -m agent.cli              # work every waiting claim
uv run python -m agent.cli --cap 5      # work up to 5 waiting claims
uv run python -m agent.cli --claim CLM-1001   # work one named claim
"""

import argparse

from agent.agents import decide_claim, run_queue


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--cap", type=int, help="work at most this many claims")
    group.add_argument("--claim", help="work one named claim")
    args = parser.parse_args()

    if args.claim:
        print(decide_claim(args.claim))
    else:
        print(run_queue(cap=args.cap))


if __name__ == "__main__":
    main()
