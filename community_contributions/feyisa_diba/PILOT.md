# The UnderCover claims pilot

This is my Week 1 Day 3 build for Ed Donner's course, AI FDE: The Forward Deployed Engineer & Agentic AI Architect. I'm UnderCover's forward deployed engineer, and I directed Claude Code (Opus 5.5 at extra high effort) through the course's process. First "Please plan the pilot" wrote a plan in six phases, each with success criteria. Then "Please implement the plan for the pilot" built it phase by phase, with tests and a commit for each phase.

My build: https://github.com/Feyisa-Diba/undercover/tree/week1day3-feyisa

The plan it followed: https://github.com/Feyisa-Diba/undercover/blob/week1day3-feyisa/docs/PLAN.md

## What I built

UnderCover is a fictional travel insurer whose three claims handlers work a queue of 25 claims by hand. The pilot gives them the UnderCover Agent, which decides claims, and a dashboard to watch it work.

```
dashboard (React, :5173) ──/api──▶ backend (FastAPI, :8000) ──▶ SQLite (undercover.db)
                                        ▲                       seeded from data/
UnderCover Agent (uv run -m agent) ─────┘ HTTP only
LangChain create_agent on OpenRouter
```

- **Backend:** FastAPI and SQLite with 14 operations. Each has an `operation_id`, a one-line docstring and no optional inputs, and a test checks this. The backend owns each claim's status, its decision, its payment and the agent's steps.
- **Agent:** LangChain's `create_agent` on GPT-6 Luna at low effort, or the model in `MODEL_NAME`. Its system prompt is its instructions plus the policy wording, both fetched from the API. It has five tools: `get_claim`, `get_policy`, `get_claim_history`, `record_decision` and `pay_claim`. Every tool call, result and final message is posted to the backend as a step. `uv run -m agent` works the queue, and `uv run -m agent CLM-1001` works one claim.
- **Dashboard:** React, Vite and TypeScript in UnderCover's brand, in light and dark mode. It has three pages:
  - the queue, with a count for each status
  - each claim in full, with the agent's decision, its steps as they happen, and a sign-off form when a payout waits for a handler
  - the agent's instructions, read only

## Key features

- **The $1,000 rule is enforced by the backend, not the prompt.** `pay_claim` refuses a payment while its claim waits for sign-off, whatever the agent tries. The refusal comes back to the agent as the tool's result, so it reads "Payment of $1,500.00 needs a handler's sign-off." and finishes instead of crashing.
- **One decision per claim, paid once, to the cent.** The agent can't approve $1,500, re-record $900 to get under the limit, and then pay. A payout can't exceed the amount claimed.
- **Sign-off releases the payment.** When a handler signs off, the backend pays the approved payout. There's no second step, and no way to pay a different amount.
- **The agent's tools only work on the claim it's deciding.** No tool takes a claim, policy or customer id. The agent can't act on another claim or browse other customers, and a small model has no ids to copy wrong.
- **Customers' contact details stay in the database.** The API serves a customer's name and claim history, never their email, phone, address or date of birth. Nothing serves `data/evals/`.
- **The end-to-end tests have their own backend and database.** Playwright starts a freshly seeded backend on port 8100 and Vite on port 5174, so `npm run check` never touches the queue I'm working with `npm run dev`.
- **No new dependencies.** It uses `sqlite3` from Python's standard library, hash routing, one CSS file, and polling every two seconds instead of websockets.

## How it was built

Each phase was built with tests, checked against its success criteria, and committed through the pre-commit hook.

| Phase | What it built | Criteria |
| --- | --- | --- |
| 1. The database and the seed | SQLite tables and `uv run -m backend.seed` | 6 |
| 2. The read API | The queue, claims, policies, claim history, policy wording and handlers | 9 |
| 3. Decisions, payments and sign-off | The status rules and the $1,000 block, built and tested before any agent existed | 5 |
| 4. The UnderCover Agent | The instructions, five tools bound to the claim, and steps posted as it works | 10 |
| 5. The dashboard's pages | The queue, the claim and the instructions in the brand look, with isolated end-to-end tests | 5 |
| 6. Live steps, sign-off and a full run | The steps timeline, the sign-off form, and the real model over the whole queue | 8 |

All 43 criteria were checked and ticked. The code is about 2,400 lines, with about 1,500 lines of tests.

## Test results

The final `npm run check` passed:

- **Python:** 54 pytest tests with 99% coverage, plus ruff (lint and format) and pyright, all clean.
- **TypeScript:** 26 vitest tests with 99% statement coverage, plus ESLint, Prettier and strict tsc, all clean.
- **End to end:** 5 Playwright tests: the queue, a claim, the instructions, steps appearing live, and a handler signing off a $1,500.00 payout.

The tests never call a model. A stub model drives the agent through the real API, including a test where it tries to pay $1,500.00 and the backend refuses.

I ran the whole queue on the real model twice:

| | First run | Second run |
| --- | --- | --- |
| Approved | 15 | 15 |
| Declined | 5 | 4 |
| Referred | 5 | 6 |
| Held for a handler's sign-off | 4 | 3 |
| Paid straight through | 11 claims, $3,938.00 | 11 claims, $4,933.00 |

In both runs, every claim ended decided or waiting for sign-off. No held payout was paid before a handler signed off. In the first run, I signed off CLM-1003 ($3,750.00, an emergency medical claim) in the dashboard, and it showed as paid.

Four claims got a different decision in the second run:

| Claim | Claimed | First run | Second run |
| --- | --- | --- | --- |
| CLM-1004, baggage delay | $186.00 | Approved $74.00 | Approved $186.00 |
| CLM-1021, baggage | $1,103.00 | Approved $1,053.00, held for sign-off | Approved $954.00, paid straight through |
| CLM-1024, baggage | $899.00 | Declined | Approved at $0.00 |
| CLM-1025, trip delay | $71.00 | Approved $71.00 | Referred, asking for the carrier's confirmation of the cause |

I haven't scored the decisions against the handlers' own, which are in `data/evals/`. The course keeps that folder closed until evaluations in Week 2.

## Challenges

- **Every backend call took about 2 seconds on Windows.** The agent used `localhost`, which tries IPv6 first and waits about two seconds to be refused before it falls back. Switching to `127.0.0.1` took the first claim from 50 seconds to about 8.
- **OpenRouter rate-limited the first full run.** New accounts get 20 requests a minute on GPT-6 Luna, and the run stopped with a 429 at claim 9. The model client now retries with backoff (`max_retries=10`), so a run waits instead of failing. The backend held up well here. Claim 9 had already been decided and paid before the 429, which only cut off the agent's closing sentence. When I reran it, the backend refused to start it again with a 409, so it couldn't be decided or paid twice.
- **A flaky test.** The agent reads the claim, the policy and the history in parallel, so their results arrive in any order. The test now checks those three as a set.
- **Tests that change data.** End-to-end tests against the development server would have changed my queue, and a sign-off test could change the counts that another test checks. The fix was a separate backend and database for Playwright, and a second Playwright project so the tests that change claims run after the ones that read the fresh queue.
- **Strict lint.** ESLint flagged props that weren't read-only, non-null assertions, and React 19's deprecated `FormEvent`. Each was fixed in the code; the process forbids turning off a rule to get a green run.
- **A false alarm.** An explanation looked garbled in the terminal, with three odd characters where a curly apostrophe should be. Checking the raw bytes showed the data was correct and only the terminal display was wrong, so nothing needed changing.

## Lessons learned

- **Put a hard rule where the agent can't argue with it.** The prompt tells the agent about the $1,000 limit, but the backend enforces it. The tests prove that a payment is refused even when the agent tries.
- **A sign-off threshold is only as good as the payout the agent computes.** CLM-1021 needed a handler in one run and was paid straight through in the other, because the agent worked out a different payout. An approval limit on agent-computed amounts needs evaluations behind it, and maybe a check against the amount claimed.
- **The same claim can get a different decision.** Four of 25 decisions changed between runs, so accuracy has to be measured over many runs against the handlers' decisions, not judged from one good run.
- **Stub-model tests and real runs find different problems.** The stub tests proved the rules and the wiring. Only real runs found the Windows `localhost` delay, the rate limit and the variation between runs.
- **Success criteria you can check make an agent's work reviewable.** The 43 criteria are tests, commands, API calls and pages in the browser, so each phase could be verified rather than trusted.
- **Give the agent only what it needs.** Binding the tools to one claim and keeping contact details out of the API kept the agent's reach small without making it any less capable.

## What's next

- **Fix the $0 approval.** The second run approved CLM-1024 with a $0.00 payout. A payment must be more than $0, so that claim can never be paid, and the dashboard shows "Not paid yet". The backend should refuse an approval of $0.
- **Score the agent against the handlers' decisions**, once evaluations come in Week 2.
- **The claims manual and a retry for failed claims**, which come with the harness in Week 1 Day 5.
