# Plan: the claims pilot

This plan builds the pilot in `docs/SPEC.md` on the stack in `docs/TECH_STACK.md`. It has six phases. Each one builds on the last and ends with a commit.

## The approach

- **The backend owns the rules.** Claim states, the $1,000 sign-off limit and the payment block all live in the backend, so they hold whatever the agent does. The agent can call `pay_claim` on a $1,500 claim, and the backend refuses it.
- **The agent only sees the API.** The agent's tools are thin wrappers over backend operations, and it fetches its own instructions from the backend too. It never reads `data/`, so it can't reach `data/evals/`. The backend doesn't load `data/evals/` either.
- **SQLite, seeded from `data/`.** On startup the backend creates `backend/undercover.db` (git-ignored) from `data/` if the file isn't there. `uv run -m backend.reset` rebuilds it. The path can be changed with `UNDERCOVER_DB`, so the end-to-end tests run on a database of their own.
- **Steps are stored in the backend.** As the agent works, a callback posts each tool call and its result to the backend as a step. The dashboard polls the steps, so handlers can watch a claim being worked.
- **The pilot works from the policy wording alone.** The claims manual, `knowledge.json` and `policy_wording_short.md` aren't used, as the spec says.

### Claim states

| State | Meaning | Set by |
|---|---|---|
| `waiting` | In the queue, not started | The seed data (`open` in `claims.json`) |
| `in_progress` | The agent is working it | `start_claim` |
| `awaiting_signoff` | Approved with a payout over $1,000. The payment is blocked | `record_decision` |
| `decided` | Approved and paid, declined or referred | `record_decision`, `pay_claim` or `sign_off_claim` |

An approved claim of $1,000 or less goes to `decided` once `pay_claim` succeeds. Over $1,000, `sign_off_claim` by a handler releases the payment and sets `decided`. Declines and referrals go straight to `decided` with no payment.

### API

Every operation has an `operation_id`, a one-line docstring and no optional inputs.

| Method and path | `operation_id` | Used by |
|---|---|---|
| `GET /api/health` | `health` | Dashboard |
| `GET /api/claims` | `list_claims` | Dashboard, agent CLI |
| `GET /api/claims/{claim_id}` | `get_claim` | Both |
| `GET /api/claims/{claim_id}/policy` | `get_policy` | Agent: the policy with its plan's limits and add-ons |
| `GET /api/claims/{claim_id}/history` | `get_claim_history` | Agent: the customer's earlier claims only, with no contact details |
| `GET /api/policy-wording` | `get_policy_wording` | Agent |
| `GET /api/instructions` | `get_instructions` | Agent, dashboard (read only) |
| `GET /api/handlers` | `list_handlers` | Dashboard |
| `POST /api/claims/{claim_id}/start` | `start_claim` | Agent |
| `GET /api/claims/{claim_id}/steps` | `list_steps` | Dashboard |
| `POST /api/claims/{claim_id}/steps` | `add_step` | Agent's callback |
| `POST /api/claims/{claim_id}/decision` | `record_decision` | Agent: `decision`, `payout`, `reason`, `policy_section` |
| `POST /api/claims/{claim_id}/payment` | `pay_claim` | Agent: `amount` |
| `POST /api/claims/{claim_id}/signoff` | `sign_off_claim` | Dashboard: `handler_id` |

Errors use plain HTTP codes: 404 for an unknown claim, 409 for a step out of order (paying before approving, paying a claim that needs sign-off, paying the wrong amount, deciding twice, signing off a claim that isn't waiting for it) and 422 for bad input.

---

## Phase 1: Backend data and read API

**Builds:** `backend/db.py` (schema, seeding from `data/`, connection), `backend/reset.py`, and the read routes: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions` and `list_handlers`. The agent's instructions are written into `backend/instructions.md` here, so the backend serves them from the start. Pydantic models for every response.

**Why first:** everything else reads from this. Getting the data model right early keeps the later phases small.

Success criteria:

- [x] `uv run pytest backend` passes, with tests for each read route on a temporary database
- [x] `GET /api/claims` returns 25 claims in queue order (`CLM-1001` first), all `waiting`
- [x] `GET /api/claims/CLM-1001` returns the story, items, documents, `amount_claimed: 420.0`, the customer's name, and an empty decision and payment
- [x] `GET /api/claims/CLM-1001/policy` returns `POL-2001` with the Premium plan's limits (`deductible: 50.0`) and its add-ons
- [x] `GET /api/claims/CLM-1001/history` returns `CLM-0412` with no email, phone, address or date of birth
- [x] `GET /api/policy-wording` returns the text of `data/policy_wording.md`
- [x] `GET /api/claims/CLM-9999` returns 404
- [x] A test asserts that nothing under `backend/` reads `data/evals/`
- [x] `uv run -m backend.reset` rebuilds the database, and every `operation_id` in `/openapi.json` matches the table above
- [x] `npm run check:python` passes

## Phase 2: Backend workflow and the payment rule

**Builds:** `start_claim`, `add_step`, `list_steps`, `record_decision`, `pay_claim` and `sign_off_claim`, with the state rules above. The approval limit comes from `data/company.json`.

**Why here:** the business rules are the riskiest part of the spec, so they're built and tested on their own before any agent or screen depends on them.

Success criteria:

- [x] Tests cover every state change in the table and every 409 case
- [x] A $420 approval on `CLM-1001` goes `waiting` → `in_progress` → `decided` once `pay_claim` is called with 420
- [x] An approval over $1,000 goes to `awaiting_signoff`, and `pay_claim` with the full amount returns 409 with no payment recorded
- [x] `sign_off_claim` with `HND-01` on that claim records the payment and the handler, and the claim becomes `decided`
- [x] `pay_claim` with an amount different from the approved payout returns 409
- [x] Decline and refer go straight to `decided`, and `pay_claim` on them returns 409
- [x] `record_decision` rejects a decision other than `approve`, `decline` or `refer`, a negative payout, and a non-zero payout on a decline or referral (422)
- [x] Steps come back from `list_steps` in the order they were added
- [x] `npm run check:python` passes with coverage at or above 80%

## Phase 3: The UnderCover Agent

**Builds:** `agent/main.py`, rewritten around `create_agent` with one tool per agent operation (`get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `start_claim`, `record_decision`, `pay_claim`). Its instructions come from `get_instructions`. A callback handler posts each tool call and result to `add_step`. The entry point stays `run(claim_id, thread_id)`. `agent/__main__.py` adds `uv run -m agent` (every waiting claim in queue order) and `uv run -m agent CLM-1001` (one claim), printing each claim's outcome.

The instructions tell the agent to start the claim, read the claim, policy, history and wording, decide, work out the payout from the wording (limits, per-item limits and the deductible where it applies), record the decision with two or three sentences and the policy section, then pay if approved. They also say the backend may hold a payment for sign-off.

**Why this way:** keeping the tools thin means every rule is enforced in one place, the backend. Fetching instructions over the API lets the dashboard show exactly what the agent was given.

Success criteria:

- [x] Agent tests with a stub model and the backend's `TestClient` work a claim end to end: steps recorded, decision recorded, claim `decided`
- [x] A stub test where the model calls `pay_claim` on a $1,500 approval shows the tool returning the backend's refusal, and the claim staying `awaiting_signoff`
- [x] A test of the CLI picks only `waiting` claims, in queue order
- [x] `MODEL_NAME` still selects the model, and the default stays `openai/gpt-6-luna` with low reasoning effort
- [x] With the backend running, `uv run -m agent CLM-1001` (one real model call chain, a few cents) leaves `CLM-1001` `decided` with a reason and a policy section, and `GET /api/claims/CLM-1001/steps` lists its tool calls
- [x] `npm run check:python` passes

## Phase 4: Dashboard: queue, claim and instructions pages

**Builds:** a small hash router (no new dependency), an API client with typed responses, and three pages:

- **Queue:** every claim with its id, customer, type, amount claimed and a state badge, counts by state at the top
- **Claim:** the story, items, documents, policy summary, and the decision with its payout, reasons and policy section
- **Instructions:** the agent's instructions, read only

Styling follows `docs/BRAND.md`: Instrument Sans, Instrument Serif and JetBrains Mono from Google Fonts. The badges are Sea Green for decided, Marigold for in progress, Coral for waiting for sign-off and Cerulean for waiting. There are light and dark modes from `prefers-color-scheme`, rounded panels with no outlines, and amounts shown as `$1,250.00`. This replaces the current health-check page and its heading.

**Why no router library:** three pages don't need one, and the code standards ask for simple.

Success criteria:

- [x] Vitest tests cover each page with a mocked `fetch`, plus the money formatter and the router
- [x] `npm run check:ts` passes, with coverage at or above 80% and no `any`
- [x] With `npm run dev`, Playwright MCP shows the queue with 25 claims and the right badge colors, in light and dark mode
- [x] Clicking `CLM-1001` opens its claim page with the story, three items and four documents
- [x] The instructions page shows the agent's instructions with no way to edit them

## Phase 5: Live steps and sign-off in the dashboard

**Builds:** the claim page polls the claim every two seconds until it is decided, and polls `list_steps` while the page is open so the agent's last step still shows, and shows each step as it lands. Claims in `awaiting_signoff` get a sign-off panel: choose a handler from `list_handlers` and sign off, which releases the payment. The queue page refreshes on the same interval. Playwright tests run against their own backend on port 8001, using `UNDERCOVER_DB` and Playwright's `webServer.env` so they work on Windows. They drive the backend API the way the agent would, so no model is called.

Success criteria:

- [x] Vitest tests cover polling (the claim stops polling once decided) and the sign-off panel
- [x] Playwright: steps posted through the API appear on the claim page without a reload
- [x] Playwright: a claim approved at $1,500 shows "Waiting for sign-off", signing off as Dana Whitfield moves it to decided with the payment shown, and the queue badge updates
- [x] Playwright: a declined claim shows its reasons and policy section and has no sign-off panel
- [x] `npm run e2e` passes, and the end-to-end tests leave the dev database untouched

## Phase 6: Working the queue

**Builds:** the full run. `uv run -m agent` works the queue while the dashboard is open, and the docs are brought up to date. Any problems the run turns up are fixed here, such as a tool description the model misreads or a step that's hard to read on screen.

What the first run turned up, and the fixes:

- Steps showed raw JSON. They now say what the agent is doing in plain words, and show refusals in full.
- OpenRouter limits new accounts to 20 requests a minute on this model, and the run stopped at the eighth claim. The model client now retries with backoff long enough to wait out the limit.
- The crash left a claim stuck in progress. `start_claim` now also resumes a claim that is in progress with no decision, so `uv run -m agent CLM-1008` finishes it.
- On the second run the model wrote one decision (CLM-1020) in its reply without calling `record_decision`. The instructions now say every claim must end with `record_decision`, and resuming the claim recorded it.

Success criteria:

- [x] After `uv run -m backend.reset`, `uv run -m agent` works all 25 claims: none left `waiting` or `in_progress`, and every claim over $1,000 that was approved is `awaiting_signoff` with no payment
- [x] Playwright MCP shows a claim's steps arriving live during the run, and the queue counts change as claims are decided
- [x] Signing off one `awaiting_signoff` claim in the dashboard pays it
- [x] `docs/STATUS.md` lists what's built and every command: `npm run dev`, `uv run -m agent`, `uv run -m agent CLM-1001`, `uv run -m backend.reset` and `npm run check`
- [x] `npm run check` passes in full

The full run calls the model 25 times. With `openai/gpt-6-luna` on low effort that should cost well under a dollar. Setting `MODEL_NAME=openrouter/free` keeps it free, with lower accuracy and a daily limit. Scoring the agent against `data/evals/` isn't part of this plan. The spec keeps that for later.
