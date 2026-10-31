# Plan: the pilot

Builds the UnderCover Agent, the backend it works through, and the dashboard the claims team watches it on, from `docs/SPEC.md`.

## Design

- **Reference data** (plans, policies, customers, handlers, company settings, policy wording) loads from `data/*.json` at backend startup into read-only in-memory dicts — it never changes, so it doesn't need a table.
- **Claim state** (status, decision, payout, reason, sign-off, payment) is the only mutable data, and lives in SQLite (`backend/undercover.db`, already gitignored) via the stdlib `sqlite3` module — no ORM. The table seeds from `data/claims.json` on first startup, with every claim `waiting`.
- **Statuses**: `waiting` → `in progress` (the agent's first tool call on a claim) → either `decided` or `waiting for sign-off` (a decided claim over the $1,000 payout limit in `data/company.json`) → `decided` once a handler signs off.
- **Agent tools** are thin wrappers over the backend API. Each one also calls the backend's `record_step` operation with a plain-English line, so the step-by-step log is driven by what actually happened, not by asking the model to narrate itself.
- `data/evals/` is never loaded, served, or referenced by any backend operation or agent tool.
- Brand fonts, colors, and surfaces from `docs/BRAND.md` apply globally in the dashboard from Phase 4 onward.

## Phase 1: Backend — reference data and the queue

Load the seed data, persist claim status in SQLite, and serve the read-only views the agent and dashboard both need.

- `list_claims`: every claim's id, type, summary, amount claimed, and status.
- `get_claim`: one claim in full, with its policy, its customer's previous claims, and its decision fields.
- `get_policy_wording`: the full text of `data/policy_wording.md`.

**Success criteria**

- [x] `uv run pytest backend -q` passes.
- [x] `GET /api/claims` returns 25 claims, each `"status": "waiting"`.
- [x] `GET /api/claims/CLM-1001` returns the claim merged with its policy (`POL-2001`) and customer `CUS-3001`'s previous claims.
- [x] `GET /api/claims/CLM-9999` (unknown id) returns 404.
- [x] `GET /api/policy-wording` returns text containing `"Trip Delay"`.
- [x] `grep -ri evals backend` returns nothing.
- [x] Restarting the backend (`uv run -m uvicorn backend.main:app`) twice does not duplicate or reset claims — the SQLite file persists state across restarts.

## Phase 2: Backend — deciding, signing off, and paying

The status machine and the rule that a payout over $1,000 blocks payment until a handler signs off.

- `decide_claim(claim_id, decision, payout, reason, policy_reference)`: records the decision; sets `waiting for sign-off` if `decision == "approve"` and `payout` is over the company's approval limit, else `decided`.
- `record_step(claim_id, text)`: appends a timestamped step; moves a `waiting` claim to `in progress` on its first call.
- `list_claim_steps(claim_id)`: a claim's steps in order.
- `sign_off_claim(claim_id, handler_id)`: only valid on a `waiting for sign-off` claim, by a handler with `can_approve_over_limit`; moves it to `decided`.
- `pay_claim(claim_id, amount)`: blocked unless the claim is `decided`, its decision is `approve`, and — if it was over the limit — it has been signed off.

**Success criteria**

- [x] `uv run pytest backend -q` passes, including:
  - [x] approving CLM-1001 at $420 moves it straight to `decided`.
  - [x] approving a claim at $1,200 moves it to `waiting for sign-off`, and `pay_claim` on it returns 409.
  - [x] `sign_off_claim` on that claim moves it to `decided`, after which `pay_claim` succeeds.
  - [x] `sign_off_claim` on a claim that isn't `waiting for sign-off` returns 409.
  - [x] `record_step` on a `waiting` claim moves it to `in progress` and appears in `list_claim_steps` in order.
- [x] Coverage for `backend/` stays at 80% or above (`uv run pytest --cov`).

## Phase 3: The UnderCover Agent decides claims

Replace the hello-world tool with the three tools the agent needs, and a system prompt from the SPEC's rules.

- Tools: `get_claim`, `get_policy_wording`, `decide_claim` (each also logs a step).
- System prompt: read the claim, its policy, its customer's history, and the policy wording; decide approve, decline, or refer; work out the payout; explain in two or three sentences with the policy section; call `decide_claim` exactly once.
- `run(claim_id, thread_id, llm=None)` keeps its shape, with the new tools.

**Success criteria**

- [x] `uv run pytest agent -q` passes, using the existing `StubModel` pattern (no real model calls in tests):
  - [x] a scripted `get_claim` → `get_policy_wording` → `decide_claim` run against the real backend (`TestClient`) leaves the claim `decided` with the scripted decision.
  - [x] the three steps appear in `list_claim_steps` in that order.
- [x] Coverage for `agent/` stays at 80% or above.
- [x] Manual check (not in the automated suite): ran the real agent (`MODEL_NAME=openrouter/free`) against the 5 `tiny` sample claims and compared each decision by eye against `data/evals/decisions.json` (read only by the check script, never by the agent). 3 of 5 matched the handler's decision and payout exactly; CLM-1020 (`manual` difficulty, needs the claims manual, out of scope for the pilot) came back `refer` instead of `approve`; CLM-1021 (`hard`) was approved correctly but with the wrong payout. Both misses are expected for a small model working from the policy wording alone.

## Phase 4: Dashboard — the queue and a claim's page

- Routes with React Router: `/` (queue), `/claims/:id` (a claim).
- Queue: a table of all 25 claims with a status badge (Sea Green/Marigold/Coral/Cerulean for the four statuses per `docs/BRAND.md`), linking to each claim.
- Claim page: the story, the items claimed, the policy and customer history, and — once decided — the decision, payout, reason, and policy reference.
- Brand fonts (Instrument Sans, Instrument Serif, JetBrains Mono from Google Fonts) and colors applied globally.

**Success criteria**

- [x] `npx vitest run --root dashboard --coverage` passes at 80% or above.
- [x] Queue page renders 25 rows with status badges (component test with mocked `fetch`).
- [x] Claim page renders a decided claim's decision, payout, and reason (component test with mocked `fetch`).
- [x] Checked in the browser (Playwright MCP): the queue and a claim page load, use the brand fonts and colors, and work in both light and dark mode.

## Phase 5: Dashboard — instructions, and running the agent

- `/instructions`: the agent's system prompt, read only.
- `run_agent(claim_id)` backend operation: schedules `agent.main.run` on a `FastAPI` `BackgroundTasks`, returns immediately.
- Claim page: a "Run agent" button when `waiting`; while `in progress`, polls `get_claim` and `list_claim_steps` every two seconds and shows the step log live; stops polling once the status leaves `in progress`.

**Success criteria**

- [x] `uv run pytest backend -q` passes: `run_agent` schedules the agent run (monkeypatched) with the right claim id and returns before it finishes.
- [x] `npx vitest run --root dashboard --coverage` passes at 80% or above, including a polling test with mocked timers and `fetch`.
- [x] Instructions page renders the system prompt text (component test).
- [x] Checked in the browser (Playwright MCP): clicking "Run agent" on a real claim (CLM-1004) showed steps appearing live, then the decision (approved, $186.00). Caught and fixed a real bug along the way: `run_agent`'s response is a bare DB row, not the full merged claim, so the button handler now re-fetches via `get_claim` instead of using the `run_agent` response directly.

## Phase 6: Sign-off, end-to-end tests, and the final check

- Claim page: when `waiting for sign-off`, show the handlers who `can_approve_over_limit` and a "Sign off" button calling `sign_off_claim`; once signed off, a "Release payment" button calling `pay_claim` (no real money, per the SPEC).
- `docs/STATUS.md` updated to describe the finished pilot.
- Playwright e2e tests that never call a model: each test sets up its own fixture state by calling `decide_claim` directly over the API before visiting the page, so results don't depend on what ran before.

**Success criteria**

- [x] `npm run e2e` passes, covering:
  - [x] the queue shows a claim's status badge after that claim is set to each of the four statuses in turn.
  - [x] a decided claim's page shows its decision, payout, and reason.
  - [x] the instructions page shows the system prompt.
  - [x] an over-limit approved claim blocks "Release payment" until "Sign off" is used, then allows it.
- [x] `npm run check` passes in full (ruff, pyright, pytest ≥80%, Prettier, ESLint, tsc, vitest ≥80%, Playwright) with no thresholds lowered and no rules disabled.
- [x] `docs/STATUS.md` matches what's built.

Along the way: the e2e tests weren't repeatable on a second run (a claim moved to `decided` by one run started the next run's "moves through the four states" test from the wrong state, since nothing in the app resets a claim backwards). Fixed with `e2e/globalSetup.ts`, which deletes the SQLite file before each `npm run e2e`/`npm run check` so every run starts from the same seeded queue. Also found and fixed that redeciding a claim left its old sign-off and payment on the row; `decide_claim` now clears `signed_off_by`, `signed_off_on`, `paid_amount`, and `paid_on` whenever a new decision is recorded.

## Known gap: a crash in the single-claim button path

"Run agent" marks the claim `in progress` and starts `python -m agent.cli --claim <id>` as a separate process (`backend/agent_process.py`). If that process crashes before it records a decision, nothing notices: the claim stays `in progress` and the step log just stops. The queue run's retry logic (`agent/work.py`) covers queue runs only. Fixing it would mean the backend watching the process and either returning the claim to `waiting` or retrying it.
