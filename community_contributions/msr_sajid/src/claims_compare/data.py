"""Load the demo claims, policies, policy wording and the answer key."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _load(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def load_claims() -> list[dict]:
    return _load("claims.json")


def load_labels() -> dict[str, dict]:
    return _load("labels.json")


def load_policies() -> dict[str, dict]:
    return {policy["policy_id"]: policy for policy in _load("policies.json")}


def load_wording() -> str:
    return (DATA_DIR / "policy.md").read_text(encoding="utf-8")
