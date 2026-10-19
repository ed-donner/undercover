"""The UnderCover Agent from the command line: uv run -m agent.main CLM-1001."""

import sys
import uuid

from agent.claim_agent import work
from agent.harness import request


def main(claim_id: str) -> str:
    """Start a waiting claim, work it and return the claim agent's report."""
    request("POST", f"/api/claims/{claim_id}/start").raise_for_status()
    return work(claim_id, uuid.uuid4().hex)


if __name__ == "__main__":
    print(main(sys.argv[1]))
