"""Work the queue: uv run -m agent, or one claim: uv run -m agent CLM-1001"""

import sys

from agent.main import main

main(sys.argv[1:])
