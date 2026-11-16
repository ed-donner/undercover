"""A handler's view of the claims waiting for review, from any computer with the repo and the same DATABASE_URL.

uv run community_contributions/arthur_jzl/approve_claim.py
    Lists the claims waiting for a handler.

uv run community_contributions/arthur_jzl/approve_claim.py CLM-1011 --approve --handler "Dana Whitfield"
uv run community_contributions/arthur_jzl/approve_claim.py CLM-1011 --reject --handler "Dana Whitfield" --note "..."
    Approves or rejects a claim's decision, and runs the claim until it pauses again or finishes.
"""

import argparse
import sys

from claim_graph import build_graph, connect, review, waiting_for_review


def show(waiting):
    """Print what a paused claim is waiting on, with the calculation behind its payout."""
    print(
        f"{waiting['claim_id']}, round {waiting['round']}: {waiting['decision']} ${waiting['payout']:,.2f}"
    )
    print(f"  {waiting['rationale']}")
    for step in waiting["calculation"]:
        print(f"  {step['step']:<60} {step['amount']:>10,.2f}")


def main():
    parser = argparse.ArgumentParser(
        description="Review the claims waiting for a handler"
    )
    parser.add_argument("claim_id", nargs="?", help="The claim to approve or reject")
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--approve", action="store_true")
    choice.add_argument("--reject", action="store_true")
    parser.add_argument("--handler", default="A handler")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    connection = connect()
    graph = build_graph(connection)
    waiting = {item["claim_id"]: item for item in waiting_for_review(connection, graph)}

    if not args.claim_id:
        if not waiting:
            print("No claims are waiting for a handler")
        for item in waiting.values():
            show(item)
        return

    if args.claim_id not in waiting:
        sys.exit(f"{args.claim_id} isn't waiting for a handler")
    if not (args.approve or args.reject):
        sys.exit("Choose --approve or --reject")

    result = review(graph, args.claim_id, args.handler, args.approve, args.note)
    if result.get("__interrupt__"):
        print("The agent looked again, and the claim is back with a handler:")
        show(result["__interrupt__"][0].value)
    else:
        print(
            f"Finished: {result['decision']} ${result['payout']:,.2f}. {result['rationale']}"
        )


if __name__ == "__main__":
    main()
