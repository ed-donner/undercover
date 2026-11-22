# Week 2 Day 5: policy wording as an improvement lever

Assignment from `labs/week2day5.ipynb`.

[The notebook](week2day5_policy_choice.ipynb) adds a versioned `full` / `short` policy wording choice. The improver proposes changes, a human approves them, and the lab's held-out scoring rules keep or roll back each candidate. Its recipe can also improve between rounds.

The first proposed experiment changes only the wording. Both versions use the same instructions and judge, accepting equivalent section titles and numbers. The summary reports actual API costs and quality; shorter text does not guarantee savings. `TINY = True` is a smoke test, not evidence of improvement. The $0.50 evaluation budget is an estimate-based guard and excludes improver calls. No live results are claimed.
