# Week 1 Day 5: the UnderCover harness

My build of the harness from `docs/HARNESS.md`, planned in `docs/PLAN_HARNESS.md` and built in six phases with Claude Code, on top of my pilot.

The code: https://github.com/hvolckaert/undercover/tree/week1day3-hugo

## What it does

- **Two agents on `create_agent`:** a queue agent, `run_queue(run_id, max_claims)`, that lists the waiting claims, keeps a to-do list on the run and hands each claim to a `work_claim` tool; and a fresh claim agent per claim, `run_claim`, that decides it. `work_claim` reports back in one line built from the claim's record, not from the model's reply.
- **Looking things up:** the claim agent no longer gets the whole policy wording. It lists, searches and reads the numbered sections of the wording and the claims manual, and the dashboard shows "What the agent read" on each claim.
- **Middleware:** `ModelRetryMiddleware` retries provider errors and timeouts, and `ModelCallLimitMiddleware` stops a claim agent after 30 model calls. The default model is `deepseek/deepseek-v4.1-flash` at low reasoning effort, or `MODEL_NAME`.
- **Rules in the backend:** a run is capped at `max_claims`, a claim that fails goes back in the queue and is left for a handler after two attempts, no claim is decided or paid twice, `finish_run` refuses while a claim within the cap was missed, and on restart claims left in progress are released.
- **Dashboard:** a run panel on the queue page with the cap, "Start run", the live to-do list and the summary; attempts and sections read on each claim; both sets of instructions.
- **Checks:** `npm run check` runs 61 Python tests (98.7% coverage), 21 Vitest tests (99.4%) and 7 Playwright tests. No test calls a model: the agent tests use a scripted stub model.

## Takeaways

- The same lesson as the pilot, at a bigger scale: the cap, the retries and the missed-claims check live in the backend, so the queue agent can't skip them however it reads its instructions.
- Showing the sections read makes a decision reviewable. On CLM-1011 I could see it read the manual's interpretation notes and count a suit as one item, which explains the payout.
- Instructions need to say what each label means. The agent marked a referred claim as "left for a handler" on its to-do list: a fair reading, but a referral is a decision, not a failure.
- A live run of five claims on DeepSeek V4.1 Flash approved three (one paid, two held for sign-off), declined one and referred one, and left the other 20 claims waiting.
