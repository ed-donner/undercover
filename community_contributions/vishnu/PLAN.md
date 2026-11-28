# Plan: the claims pilot

This plan builds the pilot described in `docs/SPEC.md` on the skeleton in `docs/STATUS.md`: a backend that holds the queue and enforces the rules, the UnderCover Agent that works claims through the backend's API, and a dashboard for the handlers.

## Approach

- **The backend is the system of record and the referee.** It loads `data/` into SQLite and owns every rule that must hold whatever the agent does, the most important being the $1,000 sign-off rule. The agent can ask to pay; the backend says no until a handler has signed off. Putting the rule in the backend, not the prompt, is what makes the block reliable.
- **The agent only sees what the API gives it.** Its tools are thin wrappers over backend operations, and the backend never reads `data/evals/`, so the answer key can't leak. Its instructions also live in the backend, so the dashboard shows exactly what the agent reads.
- **Steps are recorded as the agent works.** `run` streams the agent and posts each step (a tool call, its result, the final answer) to the backend. The dashboard polls the claim while it is in progress, so a handler can watch it step by step. Polling is simpler than websockets and fast enough for a pilot. If a run fails partway, its claim stays in progress; `uv run -m backend.seed` resets the queue, which is enough for a pilot.
- **Small, flat data model.** Each record from `data/` is stored as a JSON document in a table keyed by its id, with the few fields we query or change (status, queue position) as real columns. This keeps the seed code short and the API faithful to the source data.

## Data model

SQLite at `backend/undercover.db` (gitignored); the path can be overridden with the `UNDERCOVER_DB` environment variable so tests and e2e use their own copy. On startup, if the database is empty, the backend seeds it from `data/`: company, plans and add-ons, policies, customers, handlers, claims, and the policy wording. `uv run -m backend.seed` resets it to the seed state. `data/evals/` and `data/security/` are never read.

Claim statuses, shown in the dashboard as:

| Status | Label | Meaning |
|---|---|---|
| `waiting` | Waiting | In the queue (the seed's `open`) |
| `in_progress` | In progress | The agent is working on it |
| `awaiting_sign_off` | Waiting for sign-off | Approved for over $1,000; payment held |
| `decided` | Decided | Approved, declined or referred, with nothing pending |

A claim's decision: `approve`, `decline` or `refer`, the payout (0 unless approved), a two-or-three-sentence reason, and the policy section it rests on (such as "5. Baggage and Personal Effects"). A payment record holds the amount, when it was made, and the handler who signed off, if any.

## API

Every operation has an `operation_id`, a one-line docstring and no optional inputs.

| Method and path | `operation_id` | Used by |
|---|---|---|
| `GET /api/health` | `health` | dashboard |
| `GET /api/claims` | `list_claims` | dashboard, agent CLI |
| `GET /api/claims/{claim_id}` | `get_claim` | dashboard, agent |
| `GET /api/policies/{policy_id}` | `get_policy` | dashboard, agent (includes the plan's limits and the add-ons' effects) |
| `GET /api/customers/{customer_id}/claim-history` | `get_claim_history` | dashboard, agent (earlier claims only, no contact details) |
| `GET /api/policy-wording` | `get_policy_wording` | agent |
| `GET /api/instructions` | `get_instructions` | dashboard, agent |
| `GET /api/handlers` | `list_handlers` | dashboard |
| `POST /api/claims/{claim_id}/start` | `start_claim` | agent `run` |
| `POST /api/claims/{claim_id}/steps` | `record_step` | agent `run` |
| `POST /api/claims/{claim_id}/decision` | `record_decision` | agent |
| `POST /api/claims/{claim_id}/payment` | `pay_claim` | agent; takes the amount |
| `POST /api/claims/{claim_id}/sign-off` | `sign_off_claim` | dashboard; takes the handler id |

Rules the backend enforces:

- `record_decision` needs the claim in progress. An approval over the company's `payout_approval_limit` ($1,000) moves the claim to `awaiting_sign_off`; anything else moves it to `decided`. A decline or referral must have a payout of 0.
- `pay_claim` is refused with 409 unless the claim is approved, the amount equals the approved payout, it hasn't been paid, and either the payout is within the limit or a handler has signed off. Payments are records only; no money moves.
- `sign_off_claim` needs the claim in `awaiting_sign_off` and a handler with `can_approve_over_limit`. It records the sign-off, makes the payment and moves the claim to `decided`.

## Phases

### Phase 1: The backend's data and read API

Builds the SQLite store, the seed from `data/`, and the read operations: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions` and `list_handlers`. Writes the agent's first instructions to `backend/instructions.md`: work from the policy wording alone; read the claim, policy, plan and history; check cover, waiting periods, limits, per-item limits, add-ons, deductibles and exclusions; approve, decline or refer (refer when it needs judgment or information the agent doesn't have); work out the payout as section 10 of the wording describes; give a two-or-three-sentence reason and the section; record the decision, then pay an approval.

- [x] `uv run pytest backend` passes, with tests for every read operation and for 404 on an unknown id
- [x] A test seeds a fresh database and finds 25 claims, all `waiting`, in the order of `data/claims.json`
- [x] A test confirms nothing from `data/evals/` or `data/security/` is in the database (no `CLM-1901`, no held-out claim ids, no eval fields such as `failure_class`)
- [x] With `npm run dev:backend` running, `curl http://localhost:8000/api/claims` returns 25 claims, the first `CLM-1001` with status `waiting`
- [x] `curl http://localhost:8000/api/policies/POL-2001` includes the Premium plan's limits and deductible
- [x] `curl http://localhost:8000/api/customers/CUS-3001/claim-history` returns `CLM-0412` and no email, phone or address
- [x] Every route in `/openapi.json` has an `operation_id` and a summary, and no optional parameters (checked by a test)
- [x] `npm run check:python` passes with coverage at or above 80%

### Phase 2: The backend's workflow and the sign-off rule

Adds `start_claim`, `record_step`, `record_decision`, `pay_claim` and `sign_off_claim`, with the rules above. `get_claim` now returns the decision, the payment and the recorded steps.

- [x] Tests cover each status change: waiting to in progress; in progress to decided (decline, refer, approve at or under $1,000); in progress to waiting for sign-off (approve over $1,000); waiting for sign-off to decided on sign-off
- [x] A test approves a claim for $1,000.00 and pays it: 200, claim decided and paid
- [x] A test approves a claim for $1,250.00 and calls `pay_claim` for $1,250.00: 409, and no payment is recorded
- [x] A test signs off that claim as `HND-01`: the payment of $1,250.00 is recorded with the handler, and a second `pay_claim` returns 409
- [x] Tests reject: paying a declined or referred claim, paying an amount other than the payout, a decline with a payout above 0, a decision on a claim not in progress, sign-off by an unknown handler, sign-off of a claim not waiting for it
- [x] A test records three steps and `get_claim` returns them in order
- [x] `curl -X POST .../api/claims/CLM-1001/payment` with an amount on a waiting claim returns 409 against the running backend
- [x] `npm run check:python` passes

### Phase 3: The UnderCover Agent

Replaces the hello-world agent. Tools, each a call to one backend operation: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision`, `pay_claim`. `run(claim_id, thread_id)` calls `start_claim`, fetches the instructions from `get_instructions`, builds the agent with `create_agent` on OpenRouter (`openai/gpt-6-luna`, low reasoning effort, or `MODEL_NAME`), streams it, posts each step with `record_step`, and returns the final reply. `agent/__main__.py` adds the command line: `uv run -m agent` works every waiting claim in queue order, and `uv run -m agent CLM-1001` works one claim, printing each claim's decision and payout.

- [x] Tests, with a stub model and the backend through `TestClient`, cover: a run that approves under the limit and pays (claim decided, paid); a run that approves over the limit and tries to pay (the tool reports the refusal, the claim waits for sign-off, no payment); a decline; and the steps recorded for each run
- [x] A test confirms the system prompt comes from `get_instructions`
- [x] A test of the command line works only the waiting claims, in queue order, and works a single claim when given its id
- [x] No file under `agent/` refers to `data/` (checked by a test)
- [x] The existing `MODEL_NAME` test still passes
- [x] With the backend running and `OPENROUTER_API_KEY` set, `uv run -m agent CLM-1001` prints a decision, a payout and a reason, and `curl .../api/claims/CLM-1001` shows the decision and its steps (one live run, a cent or two of spend)
- [x] `npm run check:python` passes

### Phase 4: The dashboard: queue, claim and instructions

Replaces the health page with three pages, using React Router (added as a dependency): the queue (`/`), a claim (`/claims/:claimId`) and the agent's instructions (`/instructions`). Styled to `docs/BRAND.md`: Instrument Sans, Instrument Serif and JetBrains Mono from Google Fonts; light and dark modes from the system setting; rounded panels with no outlines; status chips in Sea Green, Marigold, Coral and Cerulean with Midnight or white text as the brand says; money as $1,250.00. Types for the API's responses live in one file, with no `any`.

- The queue: a table of claims in queue order with id, customer, claim type, amount claimed, status, decision and payout, plus a count per status. Each row links to its claim.
- A claim: the story, the items, the documents, the policy and plan, the claim history, the decision with its reason, section and payout, and the payment.
- Instructions: the agent's instructions, read only.

- [x] Vitest tests cover each page with a mocked `fetch`: the queue lists claims with the right labels; a claim shows its decision, reason, section and payout; the instructions page has no editable fields
- [x] A test of the money formatter: `1250` shows as `$1,250.00`
- [x] `npm run check:ts` passes with coverage at or above 80%
- [x] With `npm run dev` running, the Playwright MCP server shows the queue at `http://localhost:5173` with 25 claims, and clicking `CLM-1001` opens its page with the story and the Meridian Air notice
- [x] Screenshots in light and dark mode match the brand: correct fonts and colors, no edge borders, no thin line across the top

### Phase 5: Live steps, sign-off, and end-to-end tests

The claim page polls every two seconds while the claim is in progress and shows the agent's steps as a timeline. A claim waiting for sign-off shows a panel explaining that the payout is over $1,000, a choice of handler and a Sign off button. Playwright tests run against their own database, set with Playwright's `webServer.env` so it works on Windows, and on their own ports (backend 8001, dashboard 5174, with the Vite proxy target read from an environment variable) so they never reuse or change the database behind `npm run dev`.

- [x] Vitest tests: the steps timeline renders steps in order; polling stops once the claim leaves in progress; the sign-off panel appears only for claims waiting for sign-off and calls `sign_off_claim` with the chosen handler
- [x] Playwright: the queue shows 25 claims and the four status labels render
- [x] Playwright: a claim set up through the API (started, steps recorded, approved for $1,250.00) shows its steps and Waiting for sign-off; signing off as Dana Whitfield shows Decided and a payment of $1,250.00
- [x] Playwright: the instructions page shows the instructions
- [x] With `npm run dev` running, `uv run -m agent CLM-1002` is visible step by step on its claim page through the Playwright MCP server, ending with its decision
- [x] `npm run check` passes

### Phase 6: Hand-over

Brings the documents up to date and runs the full queue once.

- [x] `docs/STATUS.md` describes what's built and how to run it: `uv sync`, `npm install`, `npm run dev`, `uv run -m agent`, `uv run -m agent CLM-1001`, `uv run -m backend.seed`, `npm run check`
- [x] With the user's go-ahead on the spend, `uv run -m backend.seed` then `uv run -m agent` works all 25 claims; every claim ends decided or waiting for sign-off, and no claim over $1,000 has a payment without a sign-off
- [x] `npm run check` passes and the results are reported

## Not in this plan

As the spec says: the claims manual, sign-in, real payments and messages to customers. Scoring the agent against `data/evals/` is how UnderCover checks its work, but the build doesn't open those files; evaluations come in a later build.
