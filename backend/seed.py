"""Reset the local database to the seeded queue: uv run -m backend.seed."""

import os
from pathlib import Path

from dotenv import load_dotenv

from backend.store import Store


def main() -> None:
    load_dotenv()
    path = Path(os.getenv("DATABASE_PATH", "undercover.db"))
    path.unlink(missing_ok=True)
    store = Store(path)
    store.initialize()
    print(f"Reset {path} with {len(store.queue())} waiting claims.")


if __name__ == "__main__":
    main()
