# Plan: the claims pilot

The pilot from `docs/SPEC.md`: a backend that holds the claims queue and enforces the payment rule, the
UnderCover Agent that decides one claim at a time, and a dashboard where the handlers watch the queue,
read each decision, watch the agent work and sign off large payouts.

## Approach

- **The backend owns every rule.** The $1,000 sign-off rule lives in the payment route, not in the
  agent's instructions, so a mistaken or misled agent still can't pay. The agent can only ask.
- **One direction of calls.** The dashboard and the agent both call the backend over HTTP. The backend
  never imports the agent. The agent is started from the command line (`npm run agent`), which works
  the queue; the dashboard shows what it does.
- **SQLite through the standard library.** `sqlite3` and JSON columns are enough for 25 claims and need
  no new dependency. On first start the backend copies `data/` into the database; deleting the file
  resets it. `data/evals/`, `data/security/`, `knowledge.json` and `claims_manual.md` are never loaded.
- **The agent's instructions live in the backend** (`backend/instructions.md`, served by
  `GET /api/instructions`), so the agent reads them through the API and the dashboard shows the same
  text read only.
- **Steps are posted by the agent's runner, not by the model.** `run()` streams the agent's updates
  and posts each tool call, tool result and final reply to the backend. The dashboard polls them. Polling
  every two seconds is simpler than websockets and fast enough to watch.
- **The agent sees claim history, not personal details.** It gets the customer's previous claims, not
  their address, phone or date of birth, because it does not need them to decide.
- **End-to-end tests get their own database and ports** (backend on 8001, dashboard on 5174), so
  `npm run e2e` never changes the data you see in `npm run dev`.

### Claim states

| State | Set when |
|---|---|
| `waiting` | seeded from `data/claims.json` (`open` there) |
| `in_progress` | the agent starts the claim |
| `waiting_for_sign_off` | the agent approves a payout over $1,000 |
| `decided` | the agent approves $1,000 or less, declines or refers; or a handler signs off |

Payment is tracked apart from the state: `paid_amount` is empty until a payment goes through.

### API

Every route has an `operation_id`, a one-line docstring and no optional inputs.

| Operation | Route | Used by |
|---|---|---|
| `list_claims` | `GET /api/claims` | dashboard |
| `get_claim` | `GET /api/claims/{claim_id}` | agent, dashboard |
| `get_policy` | `GET /api/policies/{policy_id}` | agent, dashboard |
| `get_claim_history` | `GET /api/customers/{customer_id}/claims` | agent, dashboard |
| `get_policy_wording` | `GET /api/policy-wording` | agent |
| `get_instructions` | `GET /api/instructions` | agent, dashboard |
| `list_handlers` | `GET /api/handlers` | dashboard |
| `start_claim` | `POST /api/claims/{claim_id}/start` | agent runner |
| `add_step` / `list_steps` | `POST` / `GET /api/claims/{claim_id}/steps` | agent runner / dashboard |
| `record_decision` | `POST /api/claims/{claim_id}/decision` | agent |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` (takes `amount`) | agent |
| `sign_off` | `POST /api/claims/{claim_id}/sign-off` (takes `handler_id`) | dashboard |

The agent's tools are the six operations marked "agent" that a handler would use: `get_claim`,
`get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision` and `pay_claim`. It has no
`sign_off` tool.

## Phase 1: the store and the read API

Build `backend/store.py` (connect, create tables, seed from `data/` when empty) and the read routes.
The database path is `UNDERCOVER_DB`, defaulting to `backend/undercover.db` (already ignored by
`*.db` in `.gitignore`). Tests use a fresh database in `tmp_path`.

- [x] `uv run pytest backend -q --no-cov` passes, with tests for every route below
- [x] A fresh database has 25 claims, all `waiting`, and no claim from `data/evals/` or `data/security/`
      (test checks the ids against `data/claims.json` only, without opening `data/evals/`)
- [x] `GET /api/claims` returns 25 items with `claim_id`, `summary`, `claim_type`, `amount_claimed`,
      `status`, and customer name
- [x] `GET /api/claims/CLM-1001` returns the story, the three items and the four documents
- [x] `GET /api/policies/POL-2001` returns the Premium policy for the Rome trip
- [x] `GET /api/customers/CUS-3001/claims` returns CLM-0412 and no email, phone, address or date of birth
- [x] `GET /api/policy-wording` returns `data/policy_wording.md` in full
- [x] `GET /api/handlers` returns the three handlers
- [x] An unknown claim, policy or customer returns 404
- [x] Restarting the backend does not reseed or duplicate rows (test opens the store twice)
- [x] `npm run check:python` passes

## Phase 2: decisions, payment and sign-off

Add `start_claim`, the steps routes, `record_decision`, `pay_claim` and `sign_off`. The limit comes from
`payout_approval_limit` in `data/company.json`.

- [x] `start_claim` moves `waiting` or `in_progress` to `in_progress` and clears old steps; a `decided`
      claim returns 409
- [x] `record_decision` takes `decision` (`approve`, `decline` or `refer`), `payout`, `reason` and
      `policy_section`; a payout above zero on a decline or refer returns 422
- [x] Approve with payout $420.00 sets `decided`; approve with $1,250.00 sets `waiting_for_sign_off`
- [x] `pay_claim` with the approved payout of $420.00 succeeds and sets `paid_amount`
- [x] **The rule:** `pay_claim` on the $1,250.00 claim before sign-off returns 403 and nothing is paid.
      Tests also try $1,000.00 and $250.00 on that claim (splitting the payment) and both return 403
- [x] `pay_claim` with an amount that is not the approved payout returns 422; paying twice returns 409;
      paying a declined or referred claim returns 409
- [x] `sign_off` with HND-01 on the $1,250.00 claim records the handler, pays $1,250.00 and sets
      `decided`; signing off a claim that is not waiting for sign-off returns 409; an unknown handler
      returns 404
- [x] `add_step` then `list_steps` returns the steps in order
- [x] `curl -X POST localhost:8000/api/claims/CLM-1001/payment -H "Content-Type: application/json" -d "{\"amount\": 420}"`
      against a running backend gives 409 while the claim has no decision
- [x] `npm run check:python` passes, coverage at or above 80%

## Phase 3: the UnderCover Agent

Write `backend/instructions.md` and serve it. Replace the hello-world agent with the six tools, each
named after its operation and calling the backend over HTTP. `run(claim_id, thread_id, llm=None)`
starts the claim, reads its instructions from the API, streams the agent and posts each step. Add
`agent/__main__.py` so `uv run -m agent` works every waiting claim in turn (or the ids given), and an
`agent` script in `package.json`.

The instructions tell the agent to read the claim, the policy, the claim history and the policy wording;
decide by the wording alone; work out the payout by section 10; record the decision with two or three
sentences of reasons and the section; then pay if it approved.

- [x] `GET /api/instructions` returns the text of `backend/instructions.md`
- [x] Each tool test calls the real app through `TestClient` and gets the right data back
- [x] A stub-model test of `run` on CLM-1001 (scripted: read claim, policy, history, wording; approve
      $420.00; pay) ends with the claim `decided`, `paid_amount` 420.0, and at least six steps recorded
- [x] A stub-model test where the agent approves $1,250.00 and then calls `pay_claim` ends with the claim
      `waiting_for_sign_off` and nothing paid; the tool returns the backend's refusal to the model as text
      rather than crashing the run
- [x] A test of the runner with a stub `run` works only the waiting claims, in queue order
- [x] `test_model_name` still passes: `openai/gpt-6-luna` by default, `MODEL_NAME` when set
- [x] No file in `agent/` reads `data/` (test greps `agent/*.py` for `data/`)
- [x] With the backend running and the key in `.env`, `uv run -m agent CLM-1001` decides the claim and
      `GET /api/claims/CLM-1001` shows the decision, reasons and section (one real model call, a few cents
      or free with `MODEL_NAME=openrouter/free`)
- [x] `npm run check:python` passes

## Phase 4: the dashboard, read only

Three views with hash routes and no router library: the queue (`#/`), a claim (`#/claims/CLM-1001`) and
the instructions (`#/instructions`). `dashboard/src/api.ts` holds the types and fetch calls. Brand from
`docs/BRAND.md`: the three fonts from Google Fonts, light and dark surfaces by `prefers-color-scheme`,
rounded panels with no outlines, states in Sea Green, Marigold, Coral and Cerulean, money as $1,250.00.

Move the e2e servers to ports 8001 and 5174 with `UNDERCOVER_DB=e2e/e2e.db` (deleted before each run by
an `.mjs` global setup), and read the dashboard's proxy target from an environment variable defaulting to
8000.

- [x] Vitest tests with a mocked `fetch` cover the queue, the claim view and the instructions view
- [x] The queue shows 25 claims with id, customer, type, amount and state, and a count per state
- [x] The claim view shows the story, items, documents, policy, claim history and, once decided, the
      decision, payout, reasons and policy section
- [x] The instructions view shows the text from `GET /api/instructions` with no way to edit it
- [x] In the browser (Playwright MCP) at `localhost:5173`: the queue loads, clicking CLM-1001 opens it,
      (checked with the Chrome DevTools MCP server, as the Playwright MCP server is not connected)
      the back link returns to the queue; checked in light and dark mode
- [x] An e2e test opens the queue, sees 25 claims and opens CLM-1001
- [x] `npm run check:ts` and `npm run e2e` pass, coverage at or above 80%

## Phase 5: live steps and sign-off

While a claim is `waiting` or `in_progress`, the claim view polls the claim and its steps every two seconds and shows
each step as it arrives. The queue polls every five seconds so states change on their own. A claim
`waiting_for_sign_off` shows the payout, the agent's reasons and a sign-off form with a handler picker.

- [x] Vitest tests: steps appear as polling returns more of them; polling stops once the claim is decided
      or waiting for sign-off (it also polls while `waiting`, so a page opened before the agent starts
      still updates); signing off posts the chosen handler and shows the claim as decided and paid
- [x] An e2e test drives the backend through the API (no model): starts a claim, adds steps, and sees them
      appear on the claim view without a reload
- [x] An e2e test records an approve over $1,000 through the API, sees the claim waiting for sign-off,
      signs off as Dana Whitfield and sees "Paid $..."
- [x] In the browser (Playwright MCP), running `uv run -m agent CLM-1001` while the claim view is open shows
      the steps arrive one by one and then the decision
      (checked with the Chrome DevTools MCP server on CLM-1002, as CLM-1001 was already decided)
- [x] `npm run check:ts` and `npm run e2e` pass

## Phase 6: the whole queue and hand-over

- [ ] Delete `backend/undercover.db`, start `npm run dev`, run `npm run agent`, and watch the queue move from
      waiting to decided or waiting for sign-off in the browser
- [ ] Every claim ends `decided` or `waiting_for_sign_off`; every approved claim over $1,000 is unpaid
      until signed off (checked with `GET /api/claims`)
- [x] `docs/STATUS.md` says what is built, how to run it, how to reset the data and how to run the agent
- [x] `npm run check` passes in full

## Not in the pilot

- Scoring the agent against `data/evals/`. The spec keeps the answer key for checking later, and the
  evaluations come in a later build.
- The claims manual, sign-in, real payments and messages to customers, as the spec says.
- Starting the agent from the dashboard.
