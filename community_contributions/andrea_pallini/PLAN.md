# Plan: the pilot

This plan builds the claims pilot in `docs/SPEC.md` on top of the hello-world skeleton. It has three parts:

- a backend that holds the claims queue and enforces the rules
- the UnderCover Agent, which decides claims through the backend's API
- a dashboard where the handlers watch the queue, read each claim and the agent's decision, follow the agent's work live, read its instructions and sign off large payouts

There are six phases. Phases 1 and 2 build the backend, phase 3 the agent, phases 4 and 5 the dashboard, and phase 6 runs the pilot end to end with a real model.

## Choices to review

**The two additions to the spec.** The spec asks for "a percentage of correctness" with each decision, and for "an estimate of the time remaining" while the agent works.

- *Confidence.* Each decision carries `confidence`, a whole number from 0 to 100: the agent's own estimate that its decision is right. It is self-reported by the model, not measured, so treat it as a hint. Once evaluations arrive in Week 2 we can check how well it matches the handlers' decisions. If you meant the agent's measured accuracy against `data/evals/`, that is an evaluation rather than part of each decision, and it needs the answer key the agent must never see. Tell me and I'll change the plan.
- *Time remaining.* The backend estimates it as the average length of the agent's finished runs, minus the time the current run has taken so far, and never below zero. Before any run has finished, it assumes 30 seconds. The dashboard shows "About 20 seconds left", then "Finishing up" at zero. Every claim takes about the same steps, so an average is a fair guide, and it needs no extra input from the model.

**The backend enforces the rules, not the agent.** The $1,000 sign-off rule lives in the pay operation. A payout over the limit (read from `data/company.json`) is refused until a handler has signed off, whoever calls it. The agent is told about the rule, but the system doesn't rely on that. The pay operation also refuses an amount that differs from the approved payout, a second payment, and payment on a claim that isn't approved.

**The agent's steps are recorded by its harness, not by the model.** `run()` streams the agent's work. For each tool call it records a step in plain English, such as "Reading policy POL-2001" or "Paying $420.00", and for each refusal from the backend it records the reason, such as "Payment blocked: a payout over $1,000.00 needs a handler's sign-off". The model can't forget to report a step, and recording one costs no tokens.

**The agent only sees the backend's API.** Its tools are six thin wrappers over API operations: read the claim, the policy, the customer's claim history and the policy wording, record the decision, and pay. It has no tool for sign-off. The claim history operation returns the customer's name and earlier claims, but no contact details or date of birth, which the agent doesn't need. The agent's instructions live in `backend/instructions.md`, and the agent fetches them from the API at the start of each run. The dashboard shows them read only.

**Starting the agent.** On the dashboard, a "Run the agent" button on a waiting claim starts the agent in the background, so a handler can watch it work. From the terminal, `npm run agent` works through every waiting claim in turn, the way a handler works the queue, and `npm run agent -- CLM-1001` works one claim.

**Storage.** SQLite through Python's built-in `sqlite3`, in `undercover.db` at the repo root (git already ignores `*.db`). The backend creates the database from `data/` the first time it starts, and `npm run reset` rebuilds it. The records from `data/` are stored as JSON in tables keyed by their ids. The things the pilot creates (runs, steps, decisions and payments) get proper columns. The backend never reads `data/evals/` or `data/security/`, and a test proves the first.

**End-to-end tests get their own servers.** Playwright starts its own backend on port 8001 with a fresh database at `e2e/undercover.db`, and its own dashboard on port 5174. `npm run check` then never touches the database you use with `npm run dev`, and it can run while `npm run dev` is up. The tests play the agent's part through the API, so they never call a model.

## A claim's life

```
waiting --(agent starts a run)--> in progress
in progress --(decline or refer)--> decided
in progress --(approve, payout up to $1,000)--> decided; the agent then pays
in progress --(approve, payout over $1,000)--> waiting for sign-off --(a handler signs off; the payment is made)--> decided
in progress --(the run ends without a decision, such as a model error)--> waiting
```

A referral counts as decided: the agent's decision is to refer it.

## The API

Every operation has an `operation_id`, a one-line docstring and no optional inputs.

| Operation | Route | Called by | What it does |
|---|---|---|---|
| `health` | `GET /api/health` | | Already built |
| `list_claims` | `GET /api/claims` | dashboard, CLI | The queue: id, customer name, type, summary, amount claimed, date submitted, status, and the decision and payout once there is one |
| `get_claim` | `GET /api/claims/{claim_id}` | agent, dashboard | The claim in full, with its story, items, documents and status |
| `get_policy` | `GET /api/policies/{policy_id}` | agent, dashboard | The policy: plan, add-ons, purchase date, trip and travelers |
| `get_claim_history` | `GET /api/customers/{customer_id}/history` | agent, dashboard | The customer's name, customer-since date and earlier claims |
| `get_policy_wording` | `GET /api/policy-wording` | agent | The version and text of `data/policy_wording.md` |
| `get_instructions` | `GET /api/instructions` | agent, dashboard | The text of `backend/instructions.md` |
| `list_handlers` | `GET /api/handlers` | dashboard | The three handlers, for sign-off |
| `start_run` | `POST /api/claims/{claim_id}/runs` | agent harness | Takes a `thread_id`. Moves a waiting claim to in progress and opens a run |
| `record_step` | `POST /api/runs/{thread_id}/steps` | agent harness | Takes a `description` and adds a timed step to the run |
| `finish_run` | `POST /api/runs/{thread_id}/finish` | agent harness | Closes the run. A claim still in progress goes back to waiting |
| `get_progress` | `GET /api/claims/{claim_id}/progress` | dashboard | The latest run: start, finish, steps and `seconds_remaining` (null once finished) |
| `record_decision` | `POST /api/claims/{claim_id}/decision` | agent | Takes `decision` (approve, decline or refer), `payout`, `reasons`, `policy_section` and `confidence` |
| `get_decision` | `GET /api/claims/{claim_id}/decision` | dashboard | The decision, with its sign-off and payment |
| `pay_claim` | `POST /api/claims/{claim_id}/payments` | agent | Takes the `amount`. Records a payment, or refuses it with the reason |
| `sign_off_claim` | `POST /api/claims/{claim_id}/sign-off` | dashboard | Takes a `handler_id`. Records the sign-off, makes the payment and marks the claim decided |
| `start_agent` | `POST /api/claims/{claim_id}/agent` | dashboard | Starts the agent on a waiting claim in the background and returns the thread id |

Refusals return 409 with a plain-English `detail`, such as "A payout over $1,000.00 needs a handler's sign-off." Unknown ids return 404, and invalid inputs return 422.

## Phase 1: the backend's records

Builds the database, loads it from `data/` and serves the read-only operations: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording` and `list_handlers`.

- `backend/db.py`: connects to the database at `DATABASE_PATH` (default `undercover.db`) and creates the tables.
- `backend/seed.py`: loads claims, policies, customers, handlers and the company settings from `data/`. Each claim starts as waiting. `uv run -m backend.seed` rebuilds the database, and `npm run reset` runs it. On startup the backend seeds the database if the file doesn't exist yet.
- `backend/main.py`: the routes, with Pydantic models for every response.
- A root `conftest.py` gives each test a fresh database in a temporary folder.

Success criteria:

- [x] `npm run check:python` passes: ruff, pyright and pytest with at least 80% coverage
- [x] `npm run reset` prints that it loaded 25 claims, 50 policies, 49 customers and 3 handlers, and creates `undercover.db`
- [x] `GET /api/claims` returns 25 claims, each with `"status": "waiting"` and a customer name, and CLM-1001 shows Maya Patel, trip delay and 420.0
- [x] `GET /api/claims/CLM-1001` returns the story, 3 items, 4 documents and status `waiting`
- [x] `GET /api/claims/CLM-9999` returns 404
- [x] `GET /api/policies/POL-2001` returns the Premium plan and the Rome trip from 2026-06-10 to 2026-06-18
- [x] `GET /api/customers/CUS-3001/history` returns Maya Patel with one earlier claim, CLM-0412, and has no `email`, `phone`, `address` or `date_of_birth`
- [x] `GET /api/policy-wording` returns version `2026.1` and text that starts with `# UnderCover Travel Insurance: Policy Wording`
- [x] `GET /api/handlers` returns HND-01, HND-02 and HND-03
- [x] A test records every file the seed opens and confirms none is under `data/evals/`
- [x] A test reads `/openapi.json` and confirms every operation has an `operationId` and a description, and every parameter and request field is required
- [x] After restarting the backend, the database is still there and isn't seeded again

## Phase 2: the claim workflow and the payment rule

Adds the operations that change a claim: `start_run`, `record_step`, `finish_run`, `get_progress`, `record_decision`, `get_decision`, `pay_claim` and `sign_off_claim`, with the state changes in "A claim's life" and the time estimate.

- `record_decision` checks its inputs. An approval needs a payout above zero, and a decline or referral a payout of zero. Confidence is from 0 to 100, and the decision is one of approve, decline or refer.
- `pay_claim` checks, in order: the claim is approved, the amount matches the payout, it hasn't been paid, and if the payout is over the limit, a handler has signed off.
- The time estimate takes the clock as an input, so tests can fix the time.

Success criteria:

- [x] `npm run check:python` passes with at least 80% coverage, with a test for every state change and every refusal below
- [x] On CLM-1001, `start_run` moves the claim to `in_progress`, and a second `start_run` returns 409
- [x] `record_step` adds a step, and `get_progress` returns it with its time and a `seconds_remaining` from 0 to 30
- [x] Recording approve with a payout of 420.00 on CLM-1001 makes it `decided`. `pay_claim` with 420.00 returns 201, and paying again returns 409
- [x] On CLM-1002, recording approve with a payout of 1,100.00 makes it `waiting_for_sign_off`. `pay_claim` with 1,100.00 returns 409 with "A payout over $1,000.00 needs a handler's sign-off.", and `get_decision` shows no payment
- [x] `sign_off_claim` on CLM-1002 with HND-01 records Dana Whitfield's sign-off and a payment of 1,100.00, and the claim becomes `decided`
- [x] `sign_off_claim` on a claim that isn't waiting for sign-off returns 409, and an unknown handler returns 404
- [x] `pay_claim` with an amount that differs from the payout returns 409, and so does paying a declined claim
- [x] `record_decision` on a waiting claim returns 409. A decline with a payout of 50.00 returns 422, and so does a confidence of 120
- [x] `finish_run` on a run with no decision puts its claim back to `waiting`, and `start_run` on a decided claim returns 409
- [x] With the clock fixed, two finished runs of 20 and 40 seconds and a current run 10 seconds old give `seconds_remaining` of 20. A finished run gives null

## Phase 3: the UnderCover Agent

Replaces the hello-world agent with one that decides claims.

- `backend/instructions.md`: the agent's instructions, served by `get_instructions`. They cover reading the claim, the policy, the claim history and the policy wording; checking the trip dates, cover, exclusions, waiting periods and documents; working out the payout as section 10 of the wording describes; and referring a claim when it needs judgment or a missing document. They also say to give two or three sentences of reasons with the key figures, the policy section and a confidence; to pay after approving; and to stop if the payment is refused.
- `agent/main.py`: the six tools, each a thin wrapper that returns the backend's response, including a refusal's reason, so the model can respond to it. `run(claim_id, thread_id)` fetches the instructions, starts the run, streams the agent and records a step for each tool call and each refusal, then finishes the run even if the agent fails.
- `agent/__main__.py`: the CLI. `uv run -m agent` works every waiting claim in turn, and `uv run -m agent CLM-1001` works the claims named. `npm run agent` runs it.
- `start_agent` in the backend runs `run()` in the background with a new thread id.
- `npm run dev:backend` also reloads when `agent/` changes.

Success criteria:

- [x] `npm run check:python` passes with at least 80% coverage, and no test calls a model
- [x] `GET /api/instructions` returns the text of `backend/instructions.md`
- [x] A test of the tools confirms the agent has exactly these: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision` and `pay_claim`
- [x] A scripted run with a stub model on CLM-1001 reads the claim, the policy, the history and the wording, then approves 420.00 and pays. The claim is `decided` and paid, and its steps are in order: "Reading claim CLM-1001", "Reading policy POL-2001", "Reading the customer's claim history", "Reading the policy wording", "Recording the decision: approve, $420.00", "Paying $420.00"
- [x] A scripted run that approves 1,100.00 and tries to pay leaves the claim `waiting_for_sign_off` with no payment, and records the step "Payment blocked: A payout over $1,000.00 needs a handler's sign-off."
- [x] A scripted run whose model fails partway finishes its run and puts the claim back to `waiting`
- [x] `start_agent` on a waiting claim returns 202 with a thread id and calls `run()` with the claim id and that thread id. On a decided claim it returns 409
- [x] Tests of the CLI confirm that `uv run -m agent CLM-1001` runs one claim, and that `uv run -m agent` runs each waiting claim
- [x] Live, with `npm run dev` running: `npm run agent -- CLM-1001` prints the agent's reply. `GET /api/claims/CLM-1001/decision` shows a decision with two or three sentences of reasons, a policy section and a confidence from 0 to 100, and `get_progress` shows at least five steps
- [x] Live: `npm run agent -- CLM-1003` (a $3,800 medical claim) ends in a valid state. If it approves over $1,000, the claim is waiting for sign-off, there's no payment, and the steps show the blocked payment

The live checks call the model in `MODEL_NAME`. It isn't set in `.env` now, so they would use `openai/gpt-6-luna`, which is a paid model. To spend nothing, set `MODEL_NAME=openrouter/free` in `.env` first.

## Phase 4: the dashboard's queue, claims and instructions

Builds the dashboard's pages in the UnderCover brand, reading from the API.

- `dashboard/src/api.ts`: types for every response and a function for every operation the dashboard calls.
- Pages, chosen by the address (`#/`, `#/claims/CLM-1001`, `#/instructions`) without a routing library:
  - **Claims queue**: a count of claims in each status, and a table of claims showing id, customer, type, summary, amount claimed, date submitted, status and decision. A row opens the claim. The page refreshes every 5 seconds.
  - **Claim**: the claim in full (story, incident, items with their total, documents), the policy, and the customer's earlier claims.
  - **Agent instructions**: the instructions as plain text, read only.
- The brand: Instrument Sans, Instrument Serif and JetBrains Mono from Google Fonts, the colors as CSS variables, light and dark modes, and rounded panels with no outlines. The statuses use Marigold for waiting, Cerulean for in progress, Coral for waiting for sign-off and Sea Green for decided. Money shows as $1,250.00.
- If the backend doesn't answer, the page says "The backend is not responding."
- The end-to-end tests move to their own backend and dashboard, as described in "Choices to review". `npm run e2e` reseeds `e2e/undercover.db` before it starts the backend. The vite proxy reads the backend's address from `BACKEND_URL`, with port 8000 by default.

Success criteria:

- [x] `npm run check:ts` passes: Prettier, ESLint, tsc in strict mode with no `any`, and vitest with at least 80% coverage
- [x] `npm run e2e` passes while `npm run dev` is running, and the decisions in `undercover.db` are unchanged afterwards
- [x] End-to-end: the queue shows 25 claims and "Waiting 25". Opening CLM-1001 shows its story, 3 items totaling $420.00, 4 documents, the Premium plan and the earlier claim CLM-0412
- [x] End-to-end: the instructions page shows the start of `backend/instructions.md` and has no input fields
- [x] Unit test: with the backend down, the queue says "The backend is not responding."
- [x] In the browser with the Playwright MCP server, at `http://localhost:5173`: the queue and a claim page use the brand's fonts and colors in light mode and in dark mode (checked with media emulation), with no outlines on panels, and the screenshots look right

## Phase 5: the agent's work on the dashboard

Adds the agent's live work, its decision and the sign-off to the claim page.

- **Run the agent**: a button on waiting claims that calls `start_agent`.
- **Agent activity**: the steps of the latest run with their times, and while the run is going, the time left. The claim page refreshes every 2 seconds while the claim is in progress.
- **Decision**: approve, decline or refer (in Sea Green, Coral and Marigold), the payout, the confidence as a percentage, the policy section and the reasons. Below it, the payment: "Paid $420.00", "Not paid yet" or "Waiting for a handler's sign-off".
- **Sign-off**: on a claim waiting for sign-off, a choice of handler and a "Sign off and pay $1,100.00" button. Afterwards it shows who signed off and when.

Success criteria:

- [x] `npm run check:ts` passes with at least 80% coverage, with unit tests for each panel and for the button calling `start_agent`
- [x] End-to-end, playing the agent through the API on CLM-1004: after `start_run` and a step, the claim page shows "In progress", the step and "About N seconds left" without a reload. After an approval of 186.00 and a payment, it shows "Decided", "Approve", "$186.00", the confidence, the reasons and "Paid $186.00"
- [x] End-to-end on CLM-1002: after an approval of 1,100.00, the page shows "Waiting for sign-off", and a payment through the API returns 409. Choosing Dana Whitfield and pressing "Sign off and pay $1,100.00" changes the page to "Decided", "Paid $1,100.00" and "Signed off by Dana Whitfield"
- [x] End-to-end on CLM-1005: after a decline, the page shows "Decline", the reasons and no payment or sign-off
- [x] End-to-end: the queue shows the new statuses and decisions without a reload
- [x] "Run the agent" shows only on waiting claims

## Phase 6: the pilot end to end

Runs the real agent from the dashboard and brings the docs up to date.

- `docs/STATUS.md` says what's built and how to run it: `npm run dev`, `npm run agent`, `npm run reset` and `npm run check`.

Success criteria:

- [x] Live, in the browser with the Playwright MCP server: on a waiting claim, pressing "Run the agent" shows "In progress", the steps arrive one by one with a falling time estimate, and the decision appears with its reasons, policy section and confidence
- [x] Live: if any claim run so far is waiting for sign-off, signing it off in the browser pays it and marks it decided
- [x] The queue page shows the claims the agent has decided, with their decisions and payouts
- [x] `docs/STATUS.md` is up to date
- [x] `npm run check` passes in full

Running the whole queue with `npm run agent` is up to you, since it makes 25 model runs. It's the closest the pilot comes to the spec's goal of handling claims straight through.

## Not in this plan

- Scoring the agent against the handlers' decisions in `data/evals/`, which comes with evaluations in Week 2
- The claims manual, sign-in, real payments and messages to customers, as the spec says
- A handler overturning the agent's decision. Sign-off approves the payout as decided
- Durable agent state: the thread id names a run, but nothing is saved between runs
