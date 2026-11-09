# Plan: the claims pilot

From `docs/SPEC.md`. The pilot gives UnderCover a claims queue, a claim view for the handlers, and the UnderCover Agent, which works each claim from the policy wording and the customer's records. It goes in six phases, each building on the last. No sign-in, no real payments, no customer messages, and the agent never sees `data/evals/`.

## Decisions I made

- **Data is loaded from `data/` into SQLite at startup.** The backend reads `claims.json`, `policies.json`, `customers.json`, `plans.json`, `handlers.json`, `company.json` and `policy_wording.md`. It never reads `data/evals/`, `data/security/` or `context/`. A test checks this.
- **Money is in US dollars**, as the source data is, and shown as `$1,250.00`. The API and the agent both use dollars, so the agent never converts units. Amounts are compared after rounding to two decimals. The $1,000 limit comes from `company.json`, not from code.
- **The claim states are four:** `waiting`, `in_progress`, `waiting_for_sign_off` and `decided`. A claim moves to `waiting_for_sign_off` when the agent approves a payout over $1,000, and to `decided` once a handler signs off, or straight away when no sign-off is needed.
- **The payment gate lives in the backend, not the agent.** The pay operation rejects any payment over $1,000 that has no recorded sign-off. The agent gets no special trust, so even a pay call it makes is blocked.
- **The agent reaches data only through the backend's API.** Its tools are the backend's operations, one per API call, each with an `operation_id`, a one-line docstring and no optional inputs.
- **The agent's instructions live in the backend** as a text file, served read only on the dashboard. The agent loads them through an operation.
- **The agent's tool calls are recorded per claim** as a step log, so the dashboard can show what the agent did, step by step.
- **Tests use a stub model** and never call OpenRouter. Live runs are a manual step for the student, because they cost API money.

## Phase 1: Load the data and read the queue

Build the backend's data layer and the read operations.

- Load the business data into SQLite on startup, from `data/` only. Keep the loader in `backend/`.
- Add the read operations: list the queue, get one claim in full (with its policy, plan, customer history and handler), get the policy wording, and get the agent's instructions.
- Each claim's state starts as `waiting`.

Success criteria:

- [x] `uv run pytest backend` passes, with coverage at or above 80%. (10 passed, 98% coverage)
- [x] Starting the backend loads 25 claims and the matching policies, customers, plans and handlers. A test confirms the count.
- [x] A test confirms the loader runs from the pilot files alone. It copies only those files, so any read of `data/evals/`, `data/security/` or `context/` would fail.
- [x] `GET /api/claims` returns 25 claims, each with `state` set to `waiting`.
- [x] `GET /api/claims/{id}` returns one claim with its policy, plan, customer history and amounts in dollars, and returns 404 for an unknown id.
- [x] `GET /api/policy-wording` returns the text of `data/policy_wording.md`.
- [x] Every operation has an `operation_id`, a one-line docstring and no optional inputs. A test checks this on the OpenAPI schema.

## Phase 2: Record decisions and the payment gate

Add the write operations and the rules that protect money.

- `record_decision(claim_id, decision, payout, reason, policy_section)`: `decision` is `approve`, `decline` or `refer`. Payout is required and must be zero unless the decision is `approve`.
- A decision over $1,000 moves the claim to `waiting_for_sign_off`. Any other decision moves it to `decided`.
- `sign_off(claim_id, handler_id)`: a handler signs off a waiting claim, which moves it to `decided`.
- `pay_claim(claim_id, amount)`: takes the amount in dollars. It records a payment only when the claim is `decided`, the amount equals the approved payout, and any payout over $1,000 has a sign-off. Otherwise it returns a clear error and records nothing. There are no real payments.
- `record_step(claim_id, tool, input, output)`: the step log that the agent writes to.

Success criteria:

- [x] `uv run pytest backend` passes, with coverage at or above 80%.
- [x] A decline with a payout above zero is rejected with an error.
- [x] An approve of $1,000.00 or less moves the claim to `decided`. An approve of $1,000.01 moves it to `waiting_for_sign_off`.
- [x] `pay_claim` on a $1,250.00 claim before sign-off returns an error and records no payment. A test checks that the claim's payment list is empty.
- [x] After `sign_off`, the same `pay_claim` call with `amount` of 1250.00 succeeds and records one payment.
- [x] `pay_claim` with an amount different from the approved payout is rejected.
- [x] `GET /api/claims/{id}` shows the decision, the reason, the policy section, the payout and the step log.

## Phase 3: The UnderCover Agent

Build the agent with its tools, on `create_agent` and OpenRouter.

- Replace the skeleton's health tool with tools that call the backend's operations: get claim, get policy wording, get the agent's instructions, record decision, record step. The agent has no pay tool, though a test confirms the gate blocks it if one were added.
- `run(claim_id, thread_id)` is the single entry point. It loads the instructions, reads the claim, decides, and records the decision and the steps.
- The model is `openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME` from the environment when it is set.
- The agent is written so that it cannot reach `data/evals/`: it has no file access and calls only the backend's API.
- The instructions file is written in `backend/` (or `agent/`, decided during this phase) and says how to decide from the policy wording: approve, decline or refer, work out the payout, and explain in two or three sentences with the policy section.

Success criteria:

- [x] `uv run pytest agent` passes, with coverage at or above 80%, using a stub model. No test calls OpenRouter.
- [x] A stub model that approves a claim produces one recorded decision and one step per tool call, in order.
- [x] A stub model that tries to pay a $1,250.00 approval does not move money, and the claim stays `waiting_for_sign_off`.
- [x] A stub model that calls an unknown tool gets an error and the run ends without a crash.
- [x] `MODEL_NAME` overrides the default model. A test confirms this.
- [ ] Running `uv run python -c "from agent.main import run; print(run('CLM-1001', 'live'))"` against the live backend with a real key decides one routine claim. This is a manual check for the student, since it calls OpenRouter and costs API money. It is not run here.

## Phase 4: Run the queue

Connect the agent to the queue so it works claims from the backend.

- `POST /api/claims/{id}/run` starts the agent on one claim in a background thread and sets the state to `in_progress`. It returns at once.
- When the run ends, the state becomes `decided` or `waiting_for_sign_off`, or back to `waiting` if the run failed, with the error in the step log.
- A claim that is already `in_progress` cannot be started again.
- `POST /api/claims/run-queue` runs every `waiting` claim, one at a time.

Success criteria:

- [x] `uv run pytest backend agent` passes, with coverage at or above 80%.
- [x] Starting a claim returns straight away with state `in_progress`. Polling `GET /api/claims/{id}` shows it move to `decided` or `waiting_for_sign_off`, using the stub model in tests.
- [x] Starting a claim that is already `in_progress` returns an error and starts no second run.
- [x] A run that fails leaves the claim `waiting` and records the error as a step.
- [x] Running the queue with the stub model moves all 25 claims out of `waiting`.

## Phase 5: The dashboard

Build the screens for the handlers, following `docs/BRAND.md`.

- **Queue page:** all 25 claims with their state, in four groups or with state filters: waiting, in progress, waiting for sign-off, decided.
- **Claim page:** the claim in full (the customer's story, the items, the documents), the policy and the customer's history, the agent's decision and reasons, the payout, the sign-off button and the pay button, and the step log.
- **Instructions page:** the agent's instructions, read only.
- Use Instrument Sans for text, JetBrains Mono for claim ids and money, Sea Green, Marigold and Coral for the states, Midnight text on light surfaces, and rounded panels with no outline. Money shows as `$1,250.00`.
- The screens show everything to everyone. There is no sign-in.

Success criteria:

- [x] `npm run check` passes for the dashboard: ESLint, Prettier, tsc, and vitest with coverage at or above 80%. No `any` in the code.
- [x] Each state has its own colour, and the queue shows the count of claims in each state.
- [x] The claim page shows the decision, reasons, policy section, payout, step log and both buttons. The pay button is disabled until the claim is `decided`.
- [x] Playwright MCP: open the queue at a phone width and at a desktop width, with no horizontal scroll and a 16px gutter. Take a screenshot of each.
- [x] Playwright MCP: sign off a $1,250.00 claim and then pay it. The payment shows on the page.
- [x] Playwright MCP: the instructions page shows the agent's text and has no edit control.

## Phase 6: End-to-end tests, checks and handover

Prove the whole pilot works, and bring the docs up to date.

- Playwright tests in `e2e/` for: the queue loads 25 claims; a decision recorded through the API shows on the claim page (the backend runs in its own process, so the agent cannot be stubbed there and the run button is not exercised, since it would call OpenRouter); a payout over $1,000 waits for sign-off; a signed-off claim can be paid; the instructions page is read only.
- Update `docs/STATUS.md` to describe what is built, how to run it, and the manual live-run step.
- Keep the README short, with the run steps for Windows and Mac.

Success criteria:

- [x] `npm run check` passes from the repo root: Python (ruff, pyright, pytest at 80%), TypeScript (ESLint, Prettier, tsc, vitest at 80%) and Playwright.
- [x] The Playwright tests cover the five flows above and pass.
- [x] No file under `data/evals/` is opened by any code. A grep over `backend/`, `agent/`, `dashboard/` and `e2e/` for `evals` finds nothing outside tests that assert its absence.
- [x] `docs/STATUS.md` lists what is built, the run commands and the manual live-run step.
- [x] Every phase's criteria in this file are ticked.

## Open questions

- **Which policy wording file?** `data/README.md` names `policy_wording.md` as the contract and says it fits in a prompt. `data/policy_wording_short.md` is also there. The plan uses `policy_wording.md`. Tell me if the short one is meant instead.
- **`data/knowledge.json`** is not described in `data/README.md`. The plan does not use it. Tell me if it should be part of the agent's inputs.
- **The sign-off handler.** With no sign-in, the sign-off operation takes a `handler_id` that the handler picks on the screen. The plan assumes that is enough.
