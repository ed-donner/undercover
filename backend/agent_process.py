"""Starting the UnderCover Agent: its own process, never imported by the backend."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def start(claim_id: str) -> None:
    """Start the agent on one claim, and leave it to work on its own."""
    subprocess.Popen(  # noqa: S603 - fixed command, claim_id is a known claim
        [sys.executable, "-m", "agent", "--claim", claim_id], cwd=ROOT
    )
