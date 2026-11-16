"""Compare a change against repeated baseline runs, claim by claim.

Input: a CSV with a claim_id column and one 0/1 column per run (1 = right).
The last column is the changed run; every other column is an unchanged baseline run.

    uv run python claim_stability.py claim_results.csv
"""

import csv
import sys


def main(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        runs = reader.fieldnames[1:]
        rows = {r["claim_id"]: {k: r[k] == "1" for k in runs} for r in reader}
    baseline, changed = runs[:-1], runs[-1]
    if len(baseline) < 2:
        sys.exit("Need at least two baseline runs to tell noise from change.")

    print("Scores:", ", ".join(f"{k} {sum(r[k] for r in rows.values())}/{len(rows)}" for k in runs))

    stable_right = [c for c, r in rows.items() if all(r[k] for k in baseline)]
    stable_wrong = [c for c, r in rows.items() if not any(r[k] for k in baseline)]
    flips = [c for c in rows if c not in stable_right and c not in stable_wrong]
    print(
        f"Across {len(baseline)} baseline runs: {len(stable_right)} always right, "
        f"{len(stable_wrong)} always wrong, {len(flips)} flip"
    )

    broke = [c for c in stable_right if not rows[c][changed]]
    fixed = [c for c in stable_wrong if rows[c][changed]]
    print("Always right, now wrong (inspect these):", ", ".join(broke) or "none")
    print("Always wrong, now right (inspect these):", ", ".join(fixed) or "none")
    print(
        "Flipping claims, where a result says nothing about the change:", ", ".join(flips) or "none"
    )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "claim_results.csv")
