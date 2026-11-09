"""Start the UnderCover Agent from the command line.

uv run -m agent              # work every waiting claim
uv run -m agent --cap 5      # work up to 5 waiting claims
uv run -m agent --claim CLM-1001   # work one named claim
"""

import argparse

from dotenv import load_dotenv

from agent.agents import decide_claim, run_queue


def main() -> None:
    load_dotenv()
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
