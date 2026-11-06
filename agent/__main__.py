"""Work the claims queue: uv run -m agent [--cap N] [claim ids]"""

import argparse
import sys

from agent import queue_agent


def main(arguments: list[str]) -> None:
    """Run the queue agent once, then print its summary for the handlers."""
    parser = argparse.ArgumentParser(
        prog="uv run -m agent", description="Work the waiting claims in the queue."
    )
    parser.add_argument("--cap", type=int, help="the most claims the run may start")
    parser.add_argument("claim_ids", nargs="*", help="work only these claims")
    options = parser.parse_args(arguments)
    print(queue_agent.run(options.cap, options.claim_ids), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
