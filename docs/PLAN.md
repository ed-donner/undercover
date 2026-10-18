# Plan: the claims pilot

Source: `docs/SPEC.md`. Built to `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`, from the skeleton described in `docs/STATUS.md`.

## What we are building

A backend that holds the claims queue and enforces the payment rule, an agent that works a claim the way a handler does, and a dashboard where the team watches the queue, reads each decision and signs off large payouts.

```
dashboard (React) --/api--> backend (FastAPI + SQLite) <--/api-- agent (create_agent)
                                  |
                                  +-- seeded from data/ (never data/evals/)
```

The agent never touches the database or the files. It reads claims, the policy, the customer's history, the policy wording and its own instructions through the backend's API, and it writes its decision, its payment and its progress back the same way.

## How a claim moves

| Status shown | Meaning | How it gets there |
|---|---|---|
| Waiting | In the queue, nobody has started | Seeded from `data/claims.json` (all 25 start as `open`) |
| In progress | The agent is working it | `start_claim` |
| Waiting for sign-off | Approved for more than $1,000, payment held | `record_decision` with approve and a payout over the limit |
| Decided | Finished | `record_decision` for a decline, a refer or an approve of $1,000 or less; or `sign_off_claim` |

The $1,000 limit comes from `payout_approval_limit` in `data/company.json`, not from a constant in the code.

## The API

Every operation has an `operation_id` in snake_case, a one-line docstring and no optional inputs. Filtering the queue happens in the dashboard, so `list_claims` takes no parameters.

| Method and path | operation_id | Used by |
|---|---|---|
| GET `/api/health` | `health` | exists |
| GET `/api/claims` | `list_claims` | dashboard |
| GET `/api/claims/{claim_id}` | `get_claim` | both: claim, status, decision, payment, sign-off |
| GET `/api/policies/{policy_id}` | `get_policy` | both |
| GET `/api/customers/{customer_id}` | `get_customer` | both: name, customer since, claim history; no contact details |
| GET `/api/policy-wording` | `get_policy_wording` | agent |
| GET `/api/instructions` | `get_instructions` | both |
| GET `/api/handlers` | `list_handlers` | dashboard |
| POST `/api/claims/{claim_id}/start` | `start_claim` | agent |
| POST `/api/claims/{claim_id}/decision` | `record_decision` | agent: decision, payout, explanation, policy section |
| POST `/api/claims/{claim_id}/payment` | `pay_claim` | agent: takes the amount |
| POST `/api/claims/{claim_id}/sign-off` | `sign_off_claim` | dashboard: takes the handler id |
| GET `/api/claims/{claim_id}/steps` | `list_steps` | dashboard |
| POST `/api/claims/{claim_id}/steps` | `add_step` | agent |
| POST `/api/claims/{claim_id}/run` | `run_claim` | dashboard: runs the agent in the background |
| POST `/api/queue/run` | `run_queue` | dashboard: runs the agent on each waiting claim, one at a time |

## Decisions I made

Please change any you disagree with before I build.

- **Payment on sign-off.** A handler's sign-off releases the held payment: `sign_off_claim` records the sign-off and then records the payment of the approved payout. The agent has finished by then, so nobody else is there to pay. `pay_claim` stays a separate operation, takes the amount and is the one the agent calls for payouts of $1,000 or less. Both go through the same check.
- **The payment rule is in `pay_claim`, not in the prompt.** It refuses with a 409 unless the claim has an approve decision, the amount equals the approved payout, the claim has not been paid, and, over $1,000, a handler has signed off. The agent's instructions also say not to pay over the limit, but the rule does not depend on the agent obeying.
- **Instructions live in `backend/instructions.md`.** The agent fetches them at the start of each run as its system prompt, and the dashboard shows the same text read only. This replaces the hello-world prompt in `agent/main.py`.
- **The agent gets the policy wording from a tool**, so its reading shows up as a step in the trace. It uses `data/policy_wording.md` (the full wording), not the short one and not the claims manual.
- **The agent sees a customer's name and claim history, not their address, phone or date of birth.** `data/README.md` marks `customers.json` as personal data and the agent does not need the contact details to decide a claim.
- **Money is floats rounded to cents**, compared with a cent of tolerance. Fine for a pilot.
- **Steps are recorded by the agent's entry point, not by the model.** `run` streams the agent and posts each tool call, tool result and message to `add_step`. The model cannot skip or edit its own trace.
- **A refer is a decided claim** whose decision reads "Referred". What a handler then does with it happens outside this system.
- **No router library.** The dashboard has three views, so it uses a small hash router instead of a new dependency.
- **`data/knowledge.json` is not used.** The spec lists it nowhere in the pilot. I'd only look at it if the agent needs it for the "publicly known before you bought" exclusion.
- **The database is `backend/undercover.db`**, created and seeded on first start, and gitignored. Delete it to reset the queue. Tests and Playwright use their own temporary databases.
- **The agent runs from the dashboard or the command line**: `uv run -m agent.main CLM-1001`.
- **Accuracy is not measured in the pilot.** I won't open `data/evals/`. The pilot builds the machinery; scoring against the handlers' decisions comes later, on your instruction.

## Phase 1: Backend data and read operations

Builds the SQLite database, seeds it from `data/`, and serves everything the agent and dashboard read. First because every later phase depends on it, and it has no model or UI in it to confuse a failure.

Files: `backend/db.py` (connection, schema, seeding), `backend/models.py` (Pydantic models), `backend/main.py` (routes), `backend/instructions.md` (first draft, finished in phase 3), tests in `backend/tests/`.

Tables: `claims` (with `status`), `policies`, `customers`, `handlers`, then `decisions`, `payments`, `sign_offs` and `steps` which later phases fill. Claims, policies and customers keep their original JSON in a `data` column next to the columns we query on. Seeding runs once, when the database is empty, and reads only `claims.json`, `policies.json`, `customers.json`, `handlers.json`, `company.json` and `policy_wording.md`.

Success criteria:

- [x] `uv run pytest -q backend` passes, with tests that use a temporary database and need no network
- [x] A fresh start creates `backend/undercover.db` with 25 claims, all `waiting`, 50 policies and the 3 handlers; a second start does not duplicate them
- [x] `GET /api/claims` returns 25 summaries, each with claim id, customer name, claim type, summary, amount claimed, submitted date and status
- [x] `GET /api/claims/CLM-1001` returns the story, items and documents, and `decision`, `payment` and `sign_off` are null
- [x] `GET /api/claims/CLM-9999` returns 404
- [x] `GET /api/policies/POL-2001` returns the plan, add-ons, trip and travelers
- [x] `GET /api/customers/CUS-3001` returns the name and previous claims, and the response has no `email`, `phone`, `address` or `date_of_birth`
- [x] `GET /api/policy-wording` returns the text of `data/policy_wording.md`; `GET /api/instructions` returns the text of `backend/instructions.md`
- [x] The OpenAPI document at `/openapi.json` shows an `operation_id` and a summary on every operation, and no optional parameters
- [x] No backend code refers to `data/evals/` (a test greps the `backend/` and `agent/` sources for `evals`), and the database holds no decisions after seeding
- [x] `uv run ruff format --check`, `uv run ruff check` and `npx pyright` are clean; coverage is at least 80%
- [x] Committed, with the pre-commit hook passing

## Phase 2: Claim workflow and the payment rule

Adds everything that changes a claim. This is the heart of the pilot's rules, so it is built and proven before the agent exists, by calling the API directly.

Operations: `start_claim`, `record_decision`, `pay_claim`, `sign_off_claim`, `add_step`, `list_steps`.

Rules in the code:

- `start_claim` works on a waiting or in-progress claim (so a failed run can be retried) and returns 409 on a claim waiting for sign-off or decided
- `record_decision` takes `decision` (approve, decline or refer), `payout`, `explanation` and `policy_section`, all required, and only on an in-progress claim. A decline or refer must have a payout of 0 and an approve a payout above 0, else 422
- An approve over the limit sets the status to waiting for sign-off; every other decision sets it to decided
- `pay_claim` and `sign_off_claim` follow the payment rule in "Decisions I made"
- `sign_off_claim` needs a claim waiting for sign-off and a handler with `can_approve_over_limit`

Success criteria:

- [x] `uv run pytest -q backend` passes with tests for every rule below
- [x] Starting a waiting claim makes it `in_progress`; starting it again is allowed; starting a decided claim returns 409
- [x] Recording a decline for CLM-1001 sets it `decided`, stores the explanation and policy section, and a later `pay_claim` on it returns 409
- [x] Recording an approve of $200.00 sets `decided`; `pay_claim` for $200.00 returns 200 and the claim shows the payment; `pay_claim` again returns 409; `pay_claim` for $199.00 on another approved claim returns 409
- [x] Recording an approve of $1,250.00 sets `waiting_for_sign_off`
- [x] **`pay_claim` for $1,250.00 on that claim returns 409 and no payment exists**, checked with a test and with `curl` against the running backend
- [x] `sign_off_claim` with an unknown handler returns 404; with HND-01 it sets `decided` and records one payment of $1,250.00 and one sign-off by HND-01; calling it again returns 409
- [x] An approve of exactly $1,000.00 does not wait for sign-off (the limit is "over $1,000"), and $1,000.01 does
- [x] A decline with a payout of 50 returns 422; a request with a missing field returns 422
- [x] `add_step` and `list_steps` return steps in the order they were added, each with a time
- [x] Ruff, pyright and 80% coverage pass
- [x] Committed, with the pre-commit hook passing

## Phase 3: The agent

Replaces the hello-world agent with one that decides claims, and adds the backend endpoints that run it. The agent comes after the workflow because its tools are thin wrappers over operations that already work and are tested.

Agent (`agent/main.py`, with `agent/tools.py` if the file gets long):

- **Tools** call the backend through `httpx` and return JSON text: `get_claim`, `get_policy`, `get_customer`, `get_policy_wording`, `record_decision`, `pay_claim`. Each tool returns the backend's error message instead of raising, so the agent sees why a call was refused, such as a payment held for sign-off, and can carry on. That is the one place the tools handle an error.
- **Instructions** are fetched with `get_instructions` at the start of `run`. `backend/instructions.md` is finished here. It tells the agent to: read the claim, then its policy, the customer's history and the wording; check the dates, the benefit, the exclusions and the limits section by section; work out the payout by the wording's section 10, showing each step; approve, decline or refer (refer when it needs someone's judgment or more information, such as a missing document); give two or three sentences and the section of the wording; record the decision; pay an approve of $1,000 or less; and not pay anything over $1,000. It says amounts are in US dollars and that the claims manual does not exist for this agent.
- **`run(claim_id, thread_id, llm=None)`** keeps its signature. It calls `start_claim`, streams the agent with `stream_mode="updates"`, posts a step for each tool call, tool result and model message, and returns the final reply. If the run raises, it posts an error step and re-raises.
- **Model**: unchanged, `openai/gpt-6-luna` with low reasoning, or `MODEL_NAME`.
- **Command line**: `uv run -m agent.main CLM-1001` runs one claim and prints the reply.

Backend additions: `run_claim` and `run_queue` start the agent with FastAPI background tasks (a new thread id each time). `run_claim` returns 409 for a claim that is not waiting. `run_queue` starts a single background loop over the waiting claims, one at a time, and returns the count.

Success criteria:

- [x] `uv run pytest -q` passes; tests use a scripted stub model and never call a model
- [x] A stub run that calls `get_claim`, `get_policy`, `get_customer`, `get_policy_wording`, `record_decision`, `pay_claim` and then replies ends with CLM-1001 `decided`, one payment, and a step for every call and result in order
- [x] A stub run that tries `pay_claim` for $1,250.00 before sign-off gets the refusal back as a tool result, no payment exists, and the claim is still `waiting_for_sign_off`
- [x] A stub run whose model raises leaves an error step, and `start_claim` can start the claim again
- [x] A test confirms the agent has no tool that reads `data/evals/`, and the tool list has exactly the six above
- [x] `run_claim` on a decided claim returns 409; on a waiting claim it returns 202 and, with a stub agent, the claim ends decided; `run_queue` with a stub agent decides every waiting claim
- [x] `backend/instructions.md` is under about 60 lines and mentions the $1,000 limit, the three outcomes, the payout steps and the explanation format
- [x] Live check, after you say it is fine to spend the tokens: `uv run -m agent.main CLM-1001` with the dev backend running ends with CLM-1001 decided, or waiting for sign-off, with an explanation of two or three sentences naming a section of the wording, and `GET /api/claims/CLM-1001/steps` lists what it did. I repeat this on one claim whose payout should be over $1,000, if the queue has one, and check that its payment is held
- [x] Ruff, pyright and 80% coverage pass
- [x] Committed, with the pre-commit hook passing

## Phase 4: Dashboard foundation and the queue

Builds the look, the data layer and the first screen. The queue comes first because it is the screen the team lives in, and everything else links from it.

- **Brand** (`dashboard/src/styles.css`): Instrument Sans for text, Instrument Serif for the tagline, JetBrains Mono for claim ids and amounts, loaded from Google Fonts in `index.html`. Colors as CSS variables with light and dark values following the system setting: page `#F0F4F5` / `#04232E`, panels white / black, rounded and with no outline, Midnight `#073B4C` / Sea Mist `#CDD8DB` ink. No one-edge borders, no gradients. Plain US business English, money as $1,250.00.
- **Status colors**: Waiting is Marigold, In progress Cerulean, Waiting for sign-off Coral, Decided Sea Green. Chip text is Midnight on Marigold, Coral and Sea Green and white on Cerulean. Raspberry is kept for errors. The brand lists Sea Green, Marigold, Coral then Cerulean for four things side by side; I assigned them by meaning instead, so the sign-off state, which needs a person, stands out in Coral.
- **Data layer** (`dashboard/src/api.ts`, `types.ts`): typed `fetch` wrappers for the operations the dashboard uses. Strict TypeScript, no `any`.
- **Shell** (`App.tsx`): a header with the UnderCover name and links to Queue and Instructions, and a hash router for `#/`, `#/claims/CLM-1001` and `#/instructions`.
- **Queue view**: counts for each status; a filter by status; a table of claims with id, customer, type, summary, amount claimed, status and, once decided, the decision and payout; a "Run agent on all waiting claims" button; a "Run agent" button on each waiting row; polling every 3 seconds. Rows link to the claim.

Success criteria:

- [x] `npm run check:ts` passes: Prettier, ESLint, tsc and vitest with 80% coverage
- [x] Vitest tests with a mocked `fetch` cover: rendering 25 rows, the status counts, the status filter, the status chips, the run buttons calling the right endpoints, and an empty and an error state
- [x] `npm run dev` starts; with the Playwright MCP server I open `http://localhost:5173/` and see 25 claims, four status counts that add up to 25 with Waiting at 25, and a screenshot in light mode that uses the brand colors and fonts
- [x] Switching the browser to dark mode gives the `#04232E` page with black panels and readable text (screenshot checked)
- [x] Filtering to Decided shows an empty state; the filter and counts update when a claim's status changes (checked by starting one with `curl` and watching the page poll)
- [x] The page has no horizontal scroll at 1280 and 390 pixels wide
- [x] The browser console has no errors
- [x] Committed, with the pre-commit hook passing

## Phase 5: Claim detail, sign-off and instructions

Builds the other two screens and the sign-off action. This is where the team reads the agent's work, so it comes after the queue and after the agent exists to fill it.

- **Claim view** (`#/claims/:id`): the status chip; the customer's story, items and documents; the policy (plan, add-ons, trip, travelers) and the customer's claim history; the decision, with the payout, the explanation and the policy section; the payment if there is one; and the agent's steps as a timeline, newest at the bottom, polled every 2 seconds while the claim is in progress and shown with times. A waiting claim has a "Run agent" button.
- **Sign-off panel**: shown only when the claim is waiting for sign-off. It names the payout, lists the three handlers in a select, and has a "Sign off and pay" button. After it, the claim shows Decided and the payment.
- **Instructions view** (`#/instructions`): the agent's instructions as read-only text, with no edit control.

Success criteria:

- [x] `npm run check:ts` passes with 80% coverage
- [x] Vitest tests cover: each section of the claim view, the steps timeline and its polling stop when the claim is decided, the sign-off panel appearing only for the held status, a successful sign-off, a failed sign-off, and the instructions view
- [x] With the dev servers running and claims put in each state with `curl` (start, decision, payment, steps), the Playwright MCP server shows the claim view in the four states: Waiting with a Run button, In progress with steps arriving, Waiting for sign-off with the panel, and Decided with the decision and payment
- [x] I sign off a held $1,250.00 claim as Dana Whitfield in the browser; the claim then shows Decided, a $1,250.00 payment and Dana's name, and the queue shows the same
- [x] The instructions page shows the text of `backend/instructions.md`, with nothing to edit
- [x] No screen shows a customer's email, phone, address or date of birth
- [x] The claim view has no horizontal scroll at 1280 and 390 pixels wide, and no console errors
- [x] Committed, with the pre-commit hook passing

## Phase 6: End-to-end tests, docs and final check

Proves the whole thing together without a model, and brings the documents up to date.

- **Playwright setup**: `playwright.config.ts` starts the backend and dashboard on their own ports (8100 and 5273) with a fresh temporary database, so a test run never touches the dev queue. `vite.config.ts` reads the backend address from an environment variable for the proxy. The variables are set from the Playwright config in Node, so it works on Windows.
- **Tests** (`e2e/`): they stand in for the agent by calling the API with Playwright's `request` fixture, then check what the browser shows.
  - the queue lists 25 claims, all waiting
  - a decline: start, record, and the claim page shows Decided, the explanation and the policy section
  - a small approve: the claim shows Decided, with a payment
  - **a large approve: the claim shows Waiting for sign-off, a direct payment call is refused with 409, the sign-off in the browser releases the payment, and the claim shows Decided with the payment**
  - the instructions page shows the instructions and no edit control
  - the existing health test keeps passing
- **Docs**: a short `README.md` section for how to run it and reset the queue; `docs/STATUS.md` rewritten to say what is built, how to run it and how to reset it.

Success criteria:

- [x] `npm run e2e` passes, using the ports and database above, and does not change `backend/undercover.db`
- [x] The large-approve test fails if I temporarily remove the over-limit check from `pay_claim` (checked once, then restored; not committed)
- [x] `docs/STATUS.md` matches what is built; every phase's boxes in this file are ticked
- [x] `npm run check` passes, including ruff, pyright, pytest at 80% or better, Prettier, ESLint, tsc, vitest at 80% or better and Playwright, and I report the output
- [x] `git status` shows no stray files (no database, no `test-results`)
- [x] Committed, with the pre-commit hook passing. Nothing is pushed

## Not in the pilot

The claims manual, sign-in, real payments, messages to customers, scoring against `data/evals/`, tools that calculate for the agent, and any change to the agent's instructions from the dashboard. Each is either in the spec's "Not for now" or belongs to a later brief.

## Risks

- **Payout arithmetic.** The agent does its own sums, and the wording's rules (per-item limits, deductible once per claim, carrier payments taken off first) are easy to get wrong for a small model. The pilot's instructions make it show each step and the explanation records it, so a handler can check. Fixing it with tools or a calculator is later work.
- **The free model.** `MODEL_NAME=openrouter/free` may ignore the tool-call format or run out of allowance part way through a queue. Errors leave a step and the claim can be started again.
- **Pre-commit time.** The hook runs every Python or TypeScript check on each commit. Phases that touch both take a minute or two.
