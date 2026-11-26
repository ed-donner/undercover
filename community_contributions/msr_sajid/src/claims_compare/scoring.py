"""Score results against the answer key."""


def is_right(answer: dict, label: dict) -> bool:
    """Right means the same decision and a payout within a dollar."""
    return answer["decision"] == label["decision"] and abs(answer["payout"] - label["payout"]) <= 1


def summarize(name: str, results: list[dict], labels: dict[str, dict]) -> dict:
    right = sum(is_right(r, labels[r["claim_id"]]) for r in results)
    return {
        "approach": name,
        "accuracy": f"{right} / {len(results)}",
        "calls": sum(r["calls"] for r in results),
        "seconds_per_claim": round(sum(r["seconds"] for r in results) / len(results), 1),
    }
