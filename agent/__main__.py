"""Run the UnderCover Agent on one claim: uv run -m agent CLM-1001"""

import sys
import uuid

from agent.main import run

print(run(sys.argv[1], str(uuid.uuid4())))
