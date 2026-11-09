# Week 2 Day 4: a swarm of claim agents, with a graceful Stop and a model choice

Darko Martinovic

My build of the swarm brief in `docs/SWARM.md`, on top of my durable-state build ([PR #56](https://github.com/ed-donner/undercover/pull/56)) rather than on Ed's `week2day4-start`. I read Ed's `week2day4-end` before planning and followed his design where it fit my code. The code is in my fork:

- The build as delivered: [week2day4-end](https://github.com/Darko-Martinovic/ai-fde-agentic-engineering/tree/week2day4-end)
- The plan I built it from, in six phases, with what it leaves out: [docs/PLAN_SWARM.md](https://github.com/Darko-Martinovic/ai-fde-agentic-engineering/blob/week2day4-end/docs/PLAN_SWARM.md)
- What is built and every live run: [docs/STATUS.md](https://github.com/Darko-Martinovic/ai-fde-agentic-engineering/blob/week2day4-end/docs/STATUS.md)

![The latest dispatch on the queue page: 22 claims, up to 25 at once, in 77 seconds](https://raw.githubusercontent.com/Darko-Martinovic/ai-fde-agentic-engineering/54d88017c6e7f2ef8a84b9b8806b1891efe803ff/docs/screenshots/swarm-live-dispatch.png)

## What it does

The queue agent is gone. In its place is a dispatcher with no model: a LangGraph graph that lists every claim left in progress and every waiting one, sends each to a claim agent with `Send`, and works up to N of them at once with `max_concurrency`. Each claim agent is the durable graph from Day 3, on its own thread with its own checkpointer, so its pause for a sign-off and its recovery after a restart work as before. A rate limit or a timeout waits and carries the claim on, up to three tries; a claim whose attempt fails gets one more attempt, and one that fails twice is left for a handler. Every model call's tokens and cost and every spell of work on a claim are recorded with their run, so a dispatch shows its wall time against the claim time it saved.

Evaluations work their own copies of a labelled set's claims (`CLM-1104-E7`), which the queue, Insights and dispatches leave out, and the Scoreboard scores them with the lab's measures. The answer key lives in the database, and only seeding reads it from `data/evals/`.

## How it differs from Ed's `week2day4-end`

| | Ed's build | Mine |
|---|---|---|
| Stop | A dispatch can end up stopped, but there is no Stop on the dashboard | A graceful Stop: no more claims start, those working finish, and the dispatch shows Stopped |
| Model | `MODEL_NAME` only | A model picker on the dispatch and evaluation forms, `MODEL_NAME` chosen by default, recorded on each run |
| Cost | OpenRouter's reported cost | The same, or else the prices in `settings/models.toml`, so Anthropic runs have a cost too (a local Ollama model is priced at $0) |
| A held payout | Sign-off only, refused on a copy | Sign-off or rejection with a note, both refused on a copy, and a handler can't decide a copy that was referred |
| The model comparison | None | My `bench/` rebuilt on evaluations: it starts each trial as an evaluation and reads the backend's scores, so the backend is the only scorer |
| The agent limit | 25 written in the agent, the backend and the dashboard | `MAX_AGENTS` once in the settings, which the dashboard reads at build time |

## Live runs

On GPT-6 Luna at low reasoning effort, with the backend, the agent's service and the dashboard running against Supabase. A claim carried on after a review runs on `MODEL_NAME`, which my `.env` sets to Claude Haiku 5.5.

- **A restart.** A dispatch at N=3 decided three claims, then I killed every process on the agent's port with three claims partway through. The next dispatch, at N=25, carried those three on as the same attempts and worked the other 19: all 22 started within 3.6 seconds and the dispatch finished in 77 seconds against 1,221 seconds of claim work, for $0.018. Each claim took about 2.5 times as long as at N=3 (about 60 seconds against 24), though the model calls were no slower, so the time goes in the steps outside the model. I think they wait on the 4 database connections each process keeps, but I inferred that from the timings and didn't measure the pools.
- **The whole queue.** As a last check, after lowering the wait for a database connection to 25 seconds, a dispatch of all 25 claims at once, started through the backend, finished in 1 min 58 s for $0.022, none left or failed.
- **A sign-off and a rejection.** CLM-1008, signed off on its page, was paid 3.9 seconds later. CLM-1011, rejected with a note about the per-item limit and the deductible, came back for a sign-off with the agent's new decision, made on Haiku.
- **Evaluations.** The evaluation set at N=25 scored 84% on decisions and 84% on accuracy (the decision right and the payout within a dollar), with $392 of mistakes; the five tiny held-out claims at N=5 scored 100% on both. The queue's counts were the same before and after.
- **Langfuse.** Each claim's work is its own trace, tagged with its run, so the N=25 dispatch's tag finds 22 traces, one per claim.

Every run of the day, the failed ones included, cost about $0.11 on OpenRouter.

## Takeaways

- **The first dispatch at N=25 stalled the backend, not the model.** Each request waited on a FastAPI threadpool thread for one of the 4 database connections, and its route needed a second thread to run, so 40 requests waiting took every thread and the 4 holding a connection could never finish. Every claim agent's call timed out and 22 claims were left for the next dispatch, none decided or paid twice. The backend now keeps 200 threads, and waits at most 25 seconds for a connection, less than the agent waits for the backend.
- **A request timeout doesn't bound a reply.** One reply in the evaluation ran to 65,536 tokens and took over seven minutes, which set the run's time. The model timeout is a wait between bytes, and the reply kept coming. GPT-6 Luna's replies are now capped at 16,000 tokens in `settings/models.toml`, as the Anthropic models' are; no live run since has hit the cap.
- **The claim graph must not look like a subgraph.** My [Week 2 Day 4 challenge](https://github.com/Darko-Martinovic/ai-fde-agentic-engineering/blob/week2day4-end/community_contributions/Darko-Martinovic/week2day4_challenge.ipynb) showed that a graph invoked inside a node is saved under that node's checkpoint namespace. Running each claim graph in a fresh `contextvars.Context`, as Ed's harness does for Langfuse and mine already did, keeps it a graph of its own: its checkpoints stay under the claim's thread, and its `interrupt()` pauses that claim and not the dispatch. A test checks both.
- **The worker's `error_handler` isn't enough yet.** The brief leaves a claim in progress with the worker's `error_handler` once its retries run out. Ed found that LangGraph 1.2.12 re-raises an error the handler took when the failing worker runs beside another. My test has two failing workers and shows the same: both handlers run, then `invoke` raises anyway. So the worker catches the error on its last try, as Ed's does, and the test keeps watch for a release that fixes it.
- **Langfuse's traces list is going away.** `GET /api/public/traces` answers 410 and stops working on November 16, 2026; a run's traces are found through `GET /api/public/v2/observations` with a filter on the `tags` column. Sending traces through the SDK isn't affected.
