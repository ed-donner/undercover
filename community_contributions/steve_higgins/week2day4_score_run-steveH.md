# Week 2 Day 4 challenge: scoring the whole swarm run

## The challenge

The Day 4 dispatcher fans out to the claim agents with `Send`, but it never comes back together. Each branch goes straight to `END`, so nothing in the graph sees the whole run. The lab scores a run in cells after the graph has finished.

The challenge was to add a `score_run` node after `work_claim` that scores the whole run and puts the scores in the state.

## What I built

- `ScoredDispatch`, the dispatcher's state with a `scores` field. Only `score_run` writes it, so it needs no reducer.
- `score_run`, which scores `state["results"]` with the lab's own `score_table` and `run_scores` and returns each score as a plain `float`.
- A plain edge from `work_claim` to `score_run`. No other wiring makes it wait: all the `Send`s run in one step, and a node after them starts in the next, once the `results` reducer has joined every claim's result.
- A stand-in claim agent that answers like the handler on every claim except one, so the right scores are known in advance.

## How I tested it

- **With the stand-in (free).** `score_run` ran once, on all 25 results, with 1, 5 and 25 claim agents at once. Accuracy was 24/25, which is 0.96, as expected. It still ran once when one claim failed and was retried.
- **With the real claim agent.** On the 5 `tiny` claims with 5 at once, the scores in the state matched the lab's scoring done outside the graph, key for key. The run took about 28 seconds and cost about $0.003. Accuracy was 0.8: one of the five answers differed from the handler's.
- The scores also went to the run's trace in Langfuse with the same values.

## Takeaways

- **The join is free.** A node after a fan-out is a join. I didn't have to count branches or wait for them.
- **A stand-in with a known answer makes the check exact.** Knowing the accuracy should be 0.96 made it easy to see that `score_run` had every result, and that it had run only once.
- **Make the notebook stand alone.** My first version added cells to the lab, and they depended on earlier cells that I hadn't run. That is how I hit a `NameError`, and it was hard to know which cells to run without paying for Part 2. The notebook now holds only what it needs, and its free cells run with no keys.
- **Reading scores back from Langfuse.** For a Langfuse project created on or after 16 September 2026, the older trace and score endpoints return a 410 error. `langfuse.api.scores_v3.get_many_v3` works. Sending scores with `create_score` is not affected.
- **Not how the product will work.** As the lab's note says, in the product each claim keeps its own thread and the dispatcher only starts them. The single graph state that `score_run` joins is how the lab works, not how the product will.

## The work

The notebook, `week2day4_score_run-steveH.ipynb`, is in this folder. Copy it into `labs/` before running it. Its Part 1 costs nothing, and Part 2 costs a few cents.

My fork has it on the branch `steve_higgins-week2day4-score-run`:
https://github.com/stevehome/undercover/blob/steve_higgins-week2day4-score-run/community_contributions/steve_higgins/week2day4_score_run-steveH.ipynb
