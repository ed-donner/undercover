# Plan: the claims pilot

This plan builds the pilot in `docs/SPEC.md` on top of the hello-world skeleton in `docs/STATUS.md`. It has six phases. Each one builds on the last and ends with a commit through the pre-commit hook.

## The shape of the build

```
dashboard (React)  ──HTTP──▶  backend (FastAPI + SQLite)  ◀──HTTP──  agent (create_agent on OpenRouter)
                               │  seeded from data/ (never data/evals/)
                               └─ starts the agent in the background when a handler presses Run
```

- **The backend is the system of record and the place where the rules live.** Claims, decisions, payments, the agent's steps and its instructions are all in SQLite and all go through the API. The payment block for amounts over $1,000 is enforced here, so it holds whatever the agent does.
- **The agent only sees the API.** Its tools are thin wrappers around backend operations, and it fetches its instructions from the backend at the start of each run. It never reads `data/` directly.
- **The dashboard only sees the API.** It polls the backend, which is simple and is enough to show the steps while the agent works.

### Claim states

| State | Shown as | Set when |
|---|---|---|
| `waiting` | Waiting | Seeded (`open` in `claims.json`), or the agent failed and the claim can be run again |
| `in_progress` | In progress | A run starts |
| `awaiting_sign_off` | Waiting for sign-off | The agent approves a payout over $1,000 |
| `decided` | Decided | The agent declines or refers, approves $1,000 or less, or a handler signs off |

### Choices for you to review

1. **Who starts the agent.** A **Run agent** button on a claim, and **Run the queue** for every waiting claim, one at a time. Both call the backend, which runs the agent in a background task. Without these the dashboard couldn't show the agent at work.
2. **Sign-off pays.** When a handler signs off, the backend makes the payment through the same code path as `pay_claim`. The handler picks their name from a list, since there is no sign-in.
3. **What the agent sees about the customer.** It gets the customer's claim history (`get_claim_history`) but not their contact details or date of birth. It doesn't need them, and they are personal data.
4. **Steps are recorded by the agent's runner, not by the model.** `run()` streams the agent's progress and posts each tool call, result and final reply to the backend. The model can't skip or fake a step.
5. **Not used in the pilot:** `claims_manual.md` (out of scope per the spec), `policy_wording_short.md`, `knowledge.json` and `security/`.
6. **No new dependencies.** Everything needed is already in `pyproject.toml` and `package.json`. SQLite through the standard `sqlite3` module, and hash-based routing in the dashboard instead of a router library.

---

## Phase 1: Records and the read API

**Builds:** the SQLite database seeded from `data/`, and the read operations the agent and dashboard both need.

- `backend/db.py`: opens the database at `UNDERCOVER_DB` (default `backend/undercover.db`), creates the tables, and seeds them on first start from `claims.json`, `policies.json`, `customers.json`, `plans.json`, `company.json`, `handlers.json` and `policy_wording.md`. The seeder reads only these named files, so nothing in `data/evals/` can reach the queue. `uv run -m backend.db --reset` rebuilds the database. `*.db` goes into `.gitignore`.
- `backend/instructions.md`: the agent's instructions, served by the backend. Phase 3 writes the full text; this phase adds a short placeholder.
- Operations, each with an `operation_id`, a one-line docstring and only required inputs:

| Method and path | `operation_id` | Returns |
|---|---|---|
| `GET /api/claims` | `list_claims` | The queue: id, type, summary, amount claimed, submitted date, state, decision and payout |
| `GET /api/claims/{claim_id}` | `get_claim` | The claim in full, with its decision, sign-off and payment |
| `GET /api/policies/{policy_id}` | `get_policy` | The policy, with its plan's limits and add-ons spelled out |
| `GET /api/customers/{customer_id}/claims` | `get_claim_history` | The customer's earlier claims only |
| `GET /api/policy-wording` | `get_policy_wording` | The policy wording as Markdown, with its version |
| `GET /api/instructions` | `get_instructions` | The agent's instructions |
| `GET /api/handlers` | `list_handlers` | The handlers |

**Why this way:** storing each record's original JSON next to a few query columns (id, state) keeps the seeder short and the API faithful to the records, without a schema for every nested field.

**Success criteria**

- [x] `node --version` shows v26, `uv run python --version` shows 3.12, and `uv sync` and `npm install` complete without errors
- [x] pytest: the seeded queue has 25 claims, its ids match `data/claims.json`, and every claim starts as `waiting`
- [x] pytest: seeding twice does not duplicate rows; `--reset` restores the original queue
- [x] pytest: an unknown claim, policy or customer returns 404
- [x] pytest: `get_claim_history` returns earlier claims and no email, phone, address or date of birth
- [x] pytest: every route in `app.openapi()` has an `operation_id`, a docstring summary and no optional parameters or body fields (this test guards the rule for every later phase)
- [x] `curl http://localhost:8000/api/claims/CLM-1001` returns the claim with `"status": "waiting"`
- [x] `npm run check:python` passes with coverage of 80% or more

## Phase 2: Decisions, payments and sign-off

**Builds:** the write operations and the rules from the spec, all in the backend.

| Method and path | `operation_id` | Does |
|---|---|---|
| `POST /api/claims/{claim_id}/steps` | `add_step` | Records one step of the agent's work (kind and text) |
| `GET /api/claims/{claim_id}/steps` | `list_steps` | The steps of the latest run, in order |
| `POST /api/claims/{claim_id}/decision` | `record_decision` | Records `approve`, `decline` or `refer` with payout, reason (two or three sentences) and policy section |
| `POST /api/claims/{claim_id}/payment` | `pay_claim` | Pays the claim the given amount |
| `POST /api/claims/{claim_id}/sign-off` | `sign_off` | A handler signs off an approval over $1,000, which releases the payment |

Rules:

- A decline or a refer has a payout of 0. A claim can be decided once per run.
- Approving a payout over the limit in `company.json` ($1,000) moves the claim to `awaiting_sign_off`. Anything else moves it to `decided`.
- `pay_claim` refuses with 409 and a plain message unless the claim is approved, the amount equals the approved payout, it hasn't been paid already, and, for amounts over $1,000, a handler has signed off.
- `sign_off` needs a known handler with `can_approve_over_limit`, and a claim in `awaiting_sign_off`. It records who signed off and when, pays, and moves the claim to `decided`.
- Payments are records in the database. No money moves.

**Why this way:** putting the limit in the backend, not in the prompt, is what makes the rule hold "even if the agent tries to pay". The prompt will still tell the agent about the limit, but the backend doesn't rely on it.

**Success criteria**

- [x] pytest: approving $420.00 sets `decided`, and `pay_claim` with $420.00 records a payment
- [x] pytest: approving $1,250.00 sets `awaiting_sign_off`, and `pay_claim` with $1,250.00 returns 409 with no payment recorded
- [x] pytest: after `sign_off` by HND-01 that claim is `decided` and paid $1,250.00 once; a second `pay_claim` returns 409
- [x] pytest: paying a declined, referred or undecided claim returns 409, as does paying an amount other than the approved payout
- [x] pytest: a decline with a payout above 0, an unknown decision, an unknown handler and signing off a claim that isn't waiting all return 4xx
- [x] pytest: steps come back in the order they were added
- [x] `curl -X POST .../api/claims/CLM-1001/payment -d '{"amount": 5000}'` on an undecided claim returns 409
- [x] `npm run check:python` passes with coverage of 80% or more

## Phase 3: The UnderCover Agent

**Builds:** the agent that decides a claim, and the backend operations that start it.

- `agent/main.py`, keeping the entry point `run(claim_id, thread_id)`:
  - Tools, each a call to one backend operation: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision` and `pay_claim`. A refused payment comes back to the model as the backend's message rather than an exception, so it can explain the claim is waiting for sign-off.
  - Fetches its instructions from `get_instructions` at the start of each run.
  - Streams the run and posts each step to `add_step`: tool calls with their arguments, a short form of each result, and the final reply. If the run fails, it posts an error step and puts the claim back to `waiting`.
  - Model: `openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME`, as the skeleton already does.
- `backend/instructions.md`: the full instructions. Read the claim, the policy, the claim history and the wording; check dates, cover, exclusions and documents against the wording; work out the payout using section 10; decide; record the decision with a two or three sentence reason and the section; pay approved claims; refer when the wording leaves the decision to judgment or a document is missing.
- Backend operations to start runs:

| Method and path | `operation_id` | Does |
|---|---|---|
| `POST /api/claims/{claim_id}/run` | `run_agent` | Moves a waiting claim to `in_progress`, clears earlier steps and runs the agent in the background with a new thread id |
| `POST /api/queue/run` | `run_queue` | Runs the agent on every waiting claim, one after another, in the background |

**Why this way:** the agent holds no business rules of its own. Everything it knows comes from the backend, so the later builds (harness, durable state, swarm) can change the agent without touching the records or the rules.

**Success criteria** (all pytest with a stub model, which never calls a real one)

- [x] Each tool calls its backend operation and returns its result
- [x] A stub run that reads the claim, approves $420.00 and pays leaves the claim `decided` and paid, with tool-call, result and final steps recorded in order
- [x] A stub run that approves $1,250.00 and then tries to pay leaves the claim `awaiting_sign_off` with no payment, and the agent's step shows the refusal
- [x] A stub run that declines leaves the claim `decided` with a payout of 0 and no payment
- [x] A model that raises an error leaves the claim `waiting` with an error step
- [x] The agent's instructions come from `get_instructions`: changing `instructions.md` changes the system prompt
- [x] `run_agent` on a claim that isn't waiting returns 409; `run_queue` runs only waiting claims
- [x] Nothing under `agent/` refers to `data/`
- [x] Live check (costs a few cents, or free with `MODEL_NAME=openrouter/free`): with `npm run dev:backend` running, `uv run python -c "from agent.main import run; print(run('CLM-1001', 't1'))"` prints a decision, and `GET /api/claims/CLM-1001` shows it with a reason and a policy section
- [x] `npm run check:python` passes with coverage of 80% or more

## Phase 4: Dashboard shell, queue and instructions

**Builds:** the branded dashboard with the queue and the agent's instructions.

- Brand from `docs/BRAND.md`: Instrument Sans, Instrument Serif and JetBrains Mono from Google Fonts; color tokens as CSS variables; light and dark surfaces following the system setting; rounded panels with no outlines. States use Cerulean (waiting), Marigold (in progress), Coral (waiting for sign-off) and Sea Green (decided), darkened for text on light backgrounds and lightened on dark.
- `dashboard/src/api.ts`: typed calls to the backend, with types matching the API.
- Hash routes in a small hook: `#/` the queue, `#/claims/CLM-1001` a claim, `#/instructions` the instructions.
- **Queue:** a count for each state, then a table of claims with id, type, summary, amount claimed, submitted date and state. Rows link to the claim. **Run the queue** button. Refreshes every few seconds while any claim is in progress.
- **Instructions:** the agent's instructions, rendered read only.
- Money as $1,250.00, ids and amounts in JetBrains Mono, US spelling, no exclamation marks.

**Success criteria**

- [x] vitest: the queue lists claims from a mocked API with their states and amounts formatted as $420.00
- [x] vitest: the state counts match the claims; a claim in progress turns on refreshing
- [x] vitest: the instructions page shows the text and has no editing controls
- [x] vitest: the routes show the right page for `#/`, `#/claims/<id>` and `#/instructions`
- [x] Playwright MCP: the queue shows 25 claims, all Waiting, in the brand fonts and colors, in light and dark mode, with no horizontal scroll at phone width
- [x] Playwright MCP: the instructions page shows the text from `backend/instructions.md`
- [x] `npm run check:ts` passes with coverage of 80% or more

## Phase 5: The claim page

**Builds:** each claim in full, the agent at work and the handler's sign-off.

- **The claim:** summary, story, items claimed, documents, and the policy (plan, add-ons, trip dates, travelers).
- **The decision:** approve, decline or refer, the payout, the reason and the policy section. The payment state: paid, waiting for sign-off, or none.
- **The agent at work:** a **Run agent** button on waiting claims. While the claim is in progress, the steps appear one by one as the page polls `list_steps`.
- **Sign-off:** on a claim waiting for sign-off, choose a handler and press **Sign off and pay**. A refusal from the backend shows its message in Raspberry.

**Success criteria**

- [ ] vitest: a waiting claim shows its story, items, documents and policy, and a Run agent button that calls `run_agent`
- [ ] vitest: an in-progress claim shows its steps in order and adds new ones as they arrive
- [ ] vitest: a decided claim shows the decision, payout, reason and section, and no Run agent button
- [ ] vitest: a claim waiting for sign-off shows the handler list; signing off calls `sign_off` and shows the claim as paid
- [ ] vitest: a backend error on sign-off shows its message
- [ ] Playwright MCP: CLM-1001 shows the full claim, and its page works at phone width in both modes
- [ ] `npm run check:ts` passes with coverage of 80% or more

## Phase 6: End to end, a live run and the handover

**Builds:** Playwright tests of the whole flow, a check with a real model, and the docs.

- The e2e servers run on their own ports (backend 8001, dashboard 5174) with their own database, rebuilt fresh at the start, so tests never touch the development data. The dashboard's proxy target comes from an environment variable, defaulting to port 8000.
- The e2e tests stand in for the agent by calling the API directly (`add_step`, `record_decision`, `pay_claim`), so they never call a model.
- Specs replace `e2e/health.spec.ts`:
  - The queue shows 25 waiting claims and opens a claim
  - Steps posted for a claim appear on its page, and a recorded decision shows with its reason and section
  - An approval over $1,000 shows Waiting for sign-off, a direct payment is refused, and signing off as a handler shows the claim as paid and decided
  - The instructions page shows the instructions read only
- `docs/STATUS.md` describes what's built and how to run it; a short `README` section on running the pilot.

**Success criteria**

- [ ] `npm run e2e` passes all specs
- [ ] Live check with a real model: run the agent from the dashboard on three claims (a trip delay, a baggage claim and an emergency medical claim). Each moves through In progress to a decision, with steps showing as it works and a reason that cites a section of the wording. An approval over $1,000, if one comes up, waits for sign-off.
- [ ] Playwright MCP: the same flow in the browser, including signing off a claim over $1,000
- [ ] `docs/STATUS.md` is up to date
- [ ] `npm run check` passes: ruff, pyright, pytest at 80% or more, Prettier, ESLint, tsc, vitest at 80% or more, and Playwright
