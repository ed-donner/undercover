"""Work the claims queue: uv run -m agent, or uv run -m agent CLM-1001 CLM-1004"""

import sys
import uuid

from agent import main


def work(claim_ids: list[str]) -> None:
    """Work the claims given, or else every waiting claim, one at a time."""
    if not claim_ids:
        with main.backend() as client:
            claims = client.get("/api/claims").raise_for_status().json()
        claim_ids = [
            claim["claim_id"] for claim in claims if claim["status"] == "waiting"
        ]
    if not claim_ids:
        print("No claims are waiting.")
    for claim_id in claim_ids:
        print(f"{claim_id}: {main.run(claim_id, str(uuid.uuid4()))}", flush=True)


if __name__ == "__main__":
    work(sys.argv[1:])
