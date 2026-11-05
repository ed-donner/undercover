# Plan: the pilot

This plan builds the pilot described in `docs/SPEC.md`: a backend, a dashboard for claims handlers, and a first UnderCover Agent that works the claims queue in `data/claims.json` the way a handler does.

## Approach

**The backend is the single source of truth.** It loads the business data from `data/` into SQLite at startup (the claims queue, customers, policies, plans and handlers — never `data/evals/`), and every read or write, by the agent or the dashboard, goes through its API. Each operation gets an `operation_id`, a one-line docstring and no optional inputs, per `docs/TECH_STACK.md`.

**A claim's status is exactly the four values the spec asks for:** `waiting`, `in_progress`, `waiting_for_sign_off`, `decided`. The transitions:

```
waiting --[run]--> in_progress --[decide: decline/refer]--> decided
                    in_progress --[decide: approve]--> in_progress (still deciding payment)
                                 --[pay: payout <= $1,000]--> decided
                                 --[pay: payout > $1,000, not signed off]--> waiting_for_sign_off
                                                              --[sign off]--> decided
```

Deciding a claim (`decide_claim`) and paying it (`pay_claim`) are separate operations, as `docs/TECH_STACK.md` asks. The agent calls both, in that order, for every claim it approves. `pay_claim` is where the $1,000 rule lives, so it blocks the payment the same way whether the agent calls it or a handler's sign-off releases it afterwards — there is one payment rule, enforced in one place, however it is reached.

**The agent doesn't need to know the $1,000 limit.** The spec says the agent can approve a claim like any other; the limit only holds up the payment. Keeping that number out of the agent's instructions means the business rule stays in one place (the backend, loaded from `data/company.json`) instead of two.

**The plan numbers the agent needs are already in the policy wording.** `data/policy_wording.md` section 1 has the full benefit table by plan, so the agent is given the claim, the policy (plan, add-ons, trip) and the wording text — not a separate numeric plans lookup. The dashboard, though, gets the plan's limits merged into the policy it shows, since a handler reviewing a claim shouldn't have to cross-reference the wording document by hand.

**Every claim-changing call is logged**, so "what the agent is doing on a claim, step by step" is just reading that log back.

**Tests never call a model.** Agent tests use the `GenericFakeChatModel` pattern already in `agent/tests/test_agent.py` — scripted tool calls against the real backend (via `TestClient`), monkeypatching `agent.main.model` so the whole HTTP-triggered run can be tested through `POST /api/claims/{id}/run` without a real LLM. End-to-end (Playwright) tests drive the dashboard against claim states set up directly through the backend's own API (calling `decide_claim`/`pay_claim` as fixtures), so they never click "Run" against a live model either — that would spend real API credits on every `npm run check`. The one exception is a handful of manual runs I do with the Playwright MCP server while building Phase 5, to see the real thing work end to end; that's a deliberate, small, one-off use of API credits, not part of the automated checks.

**The database resets on every backend start.** It's SQLite, seeded from `data/` each time the process starts (an in-memory database is fine for this). A pilot with no real payments doesn't need claim progress to survive a backend restart, and it keeps dev and tests identical: always a fresh, known queue of 25 waiting claims.

## Phase 1: The data layer

Build the backend's SQLite schema and seed it from `data/claims.json`, `customers.json`, `policies.json`, `plans.json` and `handlers.json` (never `data/evals/`). Add the read-only endpoints the rest of the pilot is built on.

- Tables: `claims` (seeded with `status = "waiting"`, overriding the seed file's own `"open"`), `customers`, `policies`, `plans`, `handlers`. `data/company.json`'s `payout_approval_limit` is loaded as a constant, not a table — it's backend-internal, used in Phase 2.
- `GET /api/claims` (`list_claims`) — every claim in the queue, with its status.
- `GET /api/claims/{claim_id}` (`get_claim`) — one claim in full: its story, items and documents, its customer (with claim history), and its policy with that plan's limits merged in.
- `GET /api/policy-wording` (`get_policy_wording`) — the contents of `data/policy_wording.md`.
- `GET /api/handlers` (`list_handlers`) — the three handlers.
- A `reset_database()` function that drops and reseeds everything, used at startup and by a pytest fixture so every test starts from the same 25 waiting claims.

**Success criteria**

- [x] `uv run pytest backend -q` passes, including new tests for seeding and each endpoint above.
- [x] `GET /api/claims` returns 25 claims, every one with `status: "waiting"`.
- [x] `GET /api/claims/CLM-1003` returns a policy whose plan is `"premium"` with that plan's limits merged in (`emergency_medical_max: 100000.0`, `deductible: 50.0`), and a customer with a `previous_claims` array.
- [x] `GET /api/policy-wording` returns text containing "Emergency Medical".
- [x] `GET /api/handlers` returns the 3 handlers from `data/handlers.json`, each with `can_approve_over_limit`.
- [x] `uv run ruff format --check`, `uv run ruff check` and `pyright` are clean on `backend/`.
- [x] Coverage stays at or above 80%.

## Phase 2: Deciding and paying a claim

Add the operations that move a claim through the rest of its lifecycle, and the event log that records every one of them.

- `claim_events` table: claim id, operation id, a short message, a timestamp.
- `POST /api/claims/{claim_id}/decide` (`decide_claim`) — body: `decision` (`approve`/`decline`/`refer`), `payout`, `reason`, `reference`. Rejected with 409 if the claim is already `decided` or `waiting_for_sign_off`. For `decline`/`refer`, status becomes `decided`. For `approve`, status is unchanged (payment is still to come).
- `POST /api/claims/{claim_id}/pay` (`pay_claim`) — body: `amount`. Rejected with 400 if the claim's decision isn't `approve`, or it's already paid. If `amount` is over the $1,000 limit and the claim isn't signed off, status becomes `waiting_for_sign_off` and nothing is paid. Otherwise the claim is marked paid and status becomes `decided`.
- `POST /api/claims/{claim_id}/sign-off` (`sign_off_claim`) — body: `handler_id`. Rejected with 409 if the claim isn't `waiting_for_sign_off`, 400 if the handler can't approve over the limit. Records the sign-off, then runs the same payment logic as `pay_claim` with the claim's own payout.
- `GET /api/claims/{claim_id}/events` (`list_claim_events`) — the log for one claim, in order.

**Success criteria**

- [x] `uv run pytest backend -q` passes, including:
  - [x] `decide_claim(CLM-1001, "approve", 420.0, ..., "Policy wording, section 3")` then `pay_claim(CLM-1001, 420.0)` leaves the claim `decided` with `paid_amount: 420.0`.
  - [x] `decide_claim(CLM-1003, "approve", 3750.0, ..., "Policy wording, section 7")` then `pay_claim(CLM-1003, 3750.0)` leaves the claim `waiting_for_sign_off` with no `paid_amount`, and its events include one about needing sign-off. (3750.0 is the $3,800 claimed on CLM-1003 less the Premium plan's $50 deductible, both straight from `data/claims.json` and `data/plans.json`.)
  - [x] `sign_off_claim(CLM-1003, "HND-01")` leaves that claim `decided`, `paid_amount: 3750.0`, `signed_off_by: "HND-01"`, and its events show the sign-off followed by the payment.
  - [x] `decide_claim` on an already-decided claim returns 409; `pay_claim` on a declined claim returns 400; `sign_off_claim` on a claim that isn't waiting for sign-off returns 409.
- [x] `uv run ruff format --check`, `uv run ruff check` and `pyright` are clean; coverage stays at or above 80%.

## Phase 3: The UnderCover Agent

Replace the hello-world agent with the real one: it reads a claim, the policy, the customer's history and the policy wording, then decides and tries to pay.

- `backend/agent_instructions.md` — the agent's instructions: its role, what to read before deciding, the three possible decisions, when to decline or refer, how to compute a payout from the wording, and that it must call `decide_claim` then (if it approved) `pay_claim`, and close with two or three sentences naming the decision, its reason and the policy wording section behind it.
- `GET /api/agent-instructions` (`get_agent_instructions`) — serves that file's text. The agent and the dashboard's Instructions page both read it from here, so they can never drift apart.
- `POST /api/claims/{claim_id}/run` (`run_claim`) — rejected with 409 if the claim isn't `waiting`. Moves it to `in_progress`, logs a "Started" event, calls `agent.main.run(claim_id, thread_id=claim_id)`, and returns the agent's final reply.
- `agent/main.py` gets four tools in place of `check_backend`: `get_claim`, `get_policy_wording`, `decide_claim`, `pay_claim`, each a thin wrapper over the matching backend call. `run()` fetches the instructions from the backend to use as the system prompt.

**Success criteria**

- [x] `uv run pytest agent -q` passes, with a test per tool (mirroring the existing `test_check_backend`) checking it calls the right route and returns the right shape.
- [x] An integration test scripts a `GenericFakeChatModel` to call `get_claim`, `get_policy_wording`, `decide_claim("approve", 420.0, ..., "Policy wording, section 3")`, `pay_claim(420.0)`, then reply; with `agent.main.model` monkeypatched to return it, `POST /api/claims/CLM-1001/run` returns 200 and `GET /api/claims/CLM-1001` shows `status: "decided"`, `paid_amount: 420.0`.
- [x] A second scripted run for CLM-1003 (`approve`, `3750.0`) leaves it `waiting_for_sign_off`; a follow-up call to `sign_off_claim` completes it, as in Phase 2.
- [x] `run_claim` on a claim that isn't `waiting` returns 409.
- [x] `GET /api/agent-instructions` returns text containing "policy wording".
- [x] `uv run ruff format --check`, `uv run ruff check` and `pyright` are clean; coverage stays at or above 80% for both `backend/` and `agent/`.

## Phase 4: The dashboard

Build the three screens the spec asks for, styled to `docs/BRAND.md`.

- Add `react-router-dom` and a small `src/api.ts` with typed fetch helpers matching the backend's response shapes.
- **Queue** (`/`) — every claim: id, summary, type, submitted date, status, and its decision and payout once it has one. A "Run" button on each `waiting` claim.
- **Claim detail** (`/claims/:id`) — the story, items claimed, documents, the customer (with claim history), the policy (with its plan's limits), the decision once made (decision, payout, reason, reference), the step-by-step event log, and — only when `waiting_for_sign_off` — a handler picker and a "Sign off" button.
- **Instructions** (`/instructions`) — the agent's instructions, read only.
- Brand styling: Instrument Sans for headings and body, Instrument Serif for any accent text, JetBrains Mono for ids and amounts, the seven brand colors as CSS custom properties, light and dark surfaces via `prefers-color-scheme`, rounded panels with no outline, money formatted as `$1,250.00`.

**Success criteria**

- [ ] `npx vitest run --root dashboard --coverage` passes, with new tests for the Queue, Claim detail and Instructions components against mocked `fetch`, in the style of the existing `App.test.tsx`.
- [ ] `npx prettier --check -u dashboard e2e *.config.*`, `npx eslint dashboard e2e *.config.*` and `npx tsc` are clean.
- [ ] With `npm run dev` running, checked with the Playwright MCP server:
  - [ ] `/` lists all 25 seeded claims with status "waiting".
  - [ ] A claim's detail page shows its story, items, customer and policy.
  - [ ] `/instructions` renders the instructions text.
  - [ ] Headings use Instrument Sans, the palette matches `docs/BRAND.md`, and the page is legible in both light and dark mode.

## Phase 5: Wiring it end to end

Connect the dashboard's buttons to the backend, add polling so the queue and a claim's events update while the agent is working, and prove the whole path with end-to-end tests and a manual run.

- "Run" calls `run_claim`; the Queue and Claim detail pages poll while a claim is `in_progress` so its events and status update live.
- "Sign off" calls `sign_off_claim` with the picked handler, then refreshes the claim.
- Playwright tests set up claim state directly through the backend's API (never through the agent or a model) and then drive the dashboard: a claim pushed to `waiting_for_sign_off` can be signed off and ends up `decided` and paid; the queue and a claim's detail page render seeded data correctly.

**Success criteria**

- [ ] `npm run e2e` passes, including a test that seeds a claim to `waiting_for_sign_off` via direct API calls, loads its page, clicks "Sign off", and confirms it becomes `decided` with the payout shown as paid.
- [ ] Manual check with the Playwright MCP server against `npm run dev` (not an automated test, and the one place in this plan that spends real API credits): click "Run" on CLM-1001 and watch its events appear, ending `decided` with a reason naming the trip delay and a policy wording reference; click "Run" on CLM-1003, confirm it ends `waiting_for_sign_off`, then sign it off and confirm it becomes `decided`. Screenshot each state.
- [ ] `npm run check` passes in full.

## Phase 6: Docs and final check

- Rewrite `docs/STATUS.md` to describe the finished pilot — what's built in each of `backend/`, `agent/`, `dashboard/`, `e2e/`, and how to run it.
- Run `npm run check` fresh and record the result.
- Walk back through `docs/SPEC.md` line by line: the queue view, claim detail with decision and reasons, the step-by-step log, read-only instructions, the $1,000 sign-off block, decisions following the policy wording, and that `data/evals/` was never opened by the agent — and confirm the "Not for now" items (the claims manual, sign-in, real payments, customer messages) are genuinely absent, not just unmentioned.

**Success criteria**

- [ ] `docs/STATUS.md` accurately describes the built pilot and how to run it.
- [ ] `npm run check` passes in full, output recorded.
- [ ] Every bullet in `docs/SPEC.md`'s "What the team needs to see" and "Rules" sections is met, and every item in "Not for now" is confirmed absent.
