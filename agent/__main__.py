"""Run the UnderCover Agent on one claim: uv run -m agent CLM-1001."""

import sys
from uuid import uuid4

from agent.main import run

claim_id = sys.argv[1]
print(run(claim_id, f"{claim_id}-{uuid4().hex[:8]}"))
