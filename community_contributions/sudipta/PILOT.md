# The claims pilot: what we built and what we learned

The pilot is the first build of UnderCover's claims platform, from `docs/SPEC.md`. It was planned in `docs/PLAN.md`, built in six phases, and checked against 43 success criteria, all of which pass. `docs/STATUS.md` says how to run it.

## What we built

UnderCover's three handlers work a queue of 25 claims by hand. The pilot gives them an AI agent that works the queue the way a handler does, and a dashboard to watch it.

```
Dashboard (React)  --HTTP-->  Backend (FastAPI + SQLite)  <--HTTP--  UnderCover Agent (LangChain)
  queue, claim,                 the records and the                    reads, decides, pays,
  activity, sign-off            business rules                         records each step
```

- **The backend** holds the claims, policies, customers' claim history and handlers, seeded from `data/`. It is the only source of truth, and it enforces the rules: a claim moves through `waiting`, `in_progress`, `awaiting_sign_off` and `decided`, and a payout over $1,000.00 cannot be paid until a handler signs off, whatever the agent does.
- **The UnderCover Agent** reaches everything through the backend's API, including its own instructions (`backend/instructions.md`). For each claim it reads the claim, the policy, the claim history and the policy wording; approves, declines or refers; works out the payout; explains the decision in two or three sentences with the policy section; and pays when the payout is $1,000.00 or less. Each tool call, result and its final reply is recorded as a step.
- **The dashboard** shows the queue with a count in each state; each claim in full with the agent's decision and reasons; the agent's activity, step by step, while it works; a "Sign off and pay" control for large payouts; and the agent's instructions, read only. It follows UnderCover's brand in light and dark mode.

### The build in numbers

| | |
|---|---|
| Commits | 7: one per phase, and one fix after handover |
| Change | 43 files, about 3,900 lines |
| Python tests | 56, 99% coverage |
| Dashboard tests | 31, 100% statement coverage |
| End-to-end tests | 5, on their own backend, dashboard and database |
| API operations | 16, each with an `operation_id`, a one-line docstring and no optional inputs |

### The phases

1. **The backend's records and read API.** SQLite seeded from `data/`, with routes to read claims, policies, claim history, the policy wording, the instructions and the handlers.
2. **Decisions, payments and the sign-off rule.** The state changes and the payment guard, proven with no model involved.
3. **The UnderCover Agent.** Tools over the API, step recording, a command line and a way for the backend to start the agent.
4. **The dashboard's queue and claim pages.** Read-only pages in the brand.
5. **The agent at work.** The run button, live activity, sign-off and the instructions page.
6. **End-to-end tests and handover.** Playwright tests and the documents.

## Decisions that shaped it

- **Every rule lives in the backend.** The agent is a client of the API like the dashboard. The $1,000 sign-off holds even when the agent tries to pay: the backend answers 403 and records no payment. A rule enforced only in a prompt is a request, not a rule.
- **The agent can only change the claim it is working on.** The tools that write, `record_decision` and `pay_claim`, are bound to that claim, so the model cannot pay a different one, whatever a claim's story says.
- **The agent sees only what it needs.** No route returns a customer's phone, email, date of birth or address, and the database never stores them. The handlers' answer key in `data/evals/` and the security claim in `data/security/` are never loaded, and a test guards this.
- **Simple over clever.** Python's built-in `sqlite3` with no ORM, hash routing with no router library, and polling with no websockets. Each was enough for the pilot and easy to read.
- **One tool per API call.** This keeps the agent's activity readable for a handler and keeps the logic in one place.

## What we learned

Most of these were found by running the real system, not by the tests. Each fix came with a test that fails without it.

### About agents

1. **Models skip steps, so the tool result should say what comes next.** In one live run the agent approved $186.00 and never paid, although its instructions said to. `record_decision` now replies with the next step: "Now call pay_claim with 186.00", "do not pay it", or "There is nothing to pay". Later runs paid every time.
2. **Parallel tool calls can guess at data.** The model called `get_claim_history` at the same time as `get_claim`, before it knew the customer, and passed `customer_id=TBD`. It recovered from the refusal, but the instructions now say to read the claim first, on its own.
3. **A claim's state is not the same as the agent being done.** The claim turns Decided when the agent records its decision, but the agent still has to pay and reply. The dashboard stopped watching too early and showed "Not paid yet". Every run now ends with exactly one `reply` or `error` step, and the dashboard follows the run until that step arrives.
4. **Error handling has to respect state.** When OpenRouter's free-tier limit hit the agent's last call, after its decision, the run tried to put a decided claim back in the queue. The backend rightly refused, and the command crashed. The run now returns a claim to the queue only while it is still in progress, and otherwise the decision stands.
5. **Rules in the backend make model mistakes safe.** None of the problems above could pay a large claim without sign-off, because that rule never depended on the model.

### About the stack

6. **FastAPI may finish a request in a different thread from the one that started it.** SQLite connections are tied to their thread by default, so concurrent requests, such as the model's parallel tool calls, failed with a 500. The fix is `check_same_thread=False`, which is safe because each connection serves one request at a time.
7. **FastAPI commits a `yield` dependency after the response by default.** A client that records a decision and pays straight away could read the old state. `Depends(get_db, scope="function")` commits before the response is sent.
8. **Starlette's `TestClient` here is built on `httpx2`**, so it raises `httpx2.HTTPStatusError`, not `httpx.HTTPStatusError`. The test matches the message instead.
9. **Dates in tests depend on the time zone.** A test that assumed a whole-hour offset from UTC failed in India (UTC+5:30), and some ICU versions put a narrow no-break space before AM and PM.
10. **The dev server reloads only the folders it watches.** Once the backend ran the agent, `agent/` had to be watched too.

### About models and cost

11. **Check the model and the balance before any live run.** The default model, `openai/gpt-6-luna`, is paid, and the first live runs used it on a key with no credit. They cost $0.0056, which OpenRouter accepted and recorded against an account with no credit. A key's "limit" is a daily spending cap, not money in the account.
12. **The free tier is 6 to 10 claims a day.** `MODEL_NAME=openrouter/free` uses free models, with 50 requests a day, and a claim takes 5 to 8 model calls. Adding $10 of credit raises the limit to 1,000 requests a day.

### About working with a coding agent

13. **Verify in the real app, not just in tests.** The thread bug, the commit timing, the skipped payment and the dashboard stopping early all passed their unit tests at first. Live runs and checks in the browser found them.
14. **Prove a test catches the bug.** For each fix, the new test was run against the old code to show it fails.
15. **Be precise with shell commands.** `pkill -f concurrently` matched the agent's own shell and killed it instead of the dev servers. Stopping processes by their ID is safer.

## Live results

These came from live runs during the build. They show the system works end to end. They do not measure accuracy.

| Claim | Decision | Payout | Outcome |
|---|---|---|---|
| CLM-1001, flight canceled | Approve | $420.00 | Paid |
| CLM-1003, hospital visit | Approve | $3,750.00 | Waiting for sign-off, then signed off and paid |
| CLM-1004, bag delayed | Approve | $74.00 | Paid. An earlier run approved $186.00 and did not pay, which led to learning 1 |
| CLM-1013, seven-hour delay | Decline | $0.00 | The delay was under the Economy plan's 12-hour waiting period |
| CLM-1008, trip canceled | Approve | $2,240.00 | Waiting for sign-off. The run hit the free-tier limit after deciding, which led to learning 4 |

## What's next

- **Measure accuracy.** The spec's goal is to decide claims as accurately as the handlers do. The handlers' decisions in `data/evals/` are kept for scoring the agent, and that has not been done yet. CLM-1004 shows why it matters: two runs gave two different payouts.
- **Choose a model.** Free models vary in how well they use tools. The scoring above would show whether a free model is good enough or a paid one is needed.
- **The claims manual.** The spec leaves it out for now. Some claims need its rules, such as a third claim in 12 months or meals without receipts.
