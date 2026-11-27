# Plan: the claims pilot

This plan builds the pilot in `docs/SPEC.md` on the skeleton in `docs/STATUS.md`, using the stack in `docs/TECH_STACK.md`. It has six phases. Each one ends with something that runs and is checked, and the next phase builds on it.

## The shape of the pilot

```
dashboard (React)  ──HTTP──▶  backend (FastAPI + SQLite)  ◀──HTTP──  agent (create_agent on OpenRouter)
                                  │   seeded from data/
                                  └── starts the agent in a background thread when a handler clicks Run
```

- **The backend is the single source of truth.** It holds the claims, policies, customers, plans, the policy wording, the agent's instructions, the agent's steps, its decisions and the payments. The dashboard and the agent both go through its API, so the agent reaches nothing else (the tech stack requires this).
- **The $1,000 rule lives in the backend, not in the prompt.** `pay_claim` refuses a payment over the limit until a handler has signed off. A prompt can be ignored or talked round; an API check can't. This is what "the system must block the payment, even if the agent tries" asks for.
- **The agent never sees `data/evals/`.** The seed loader reads a fixed list of files, and a test proves the eval files are never loaded and that no API response contains eval data. I won't open `data/evals/` while building, as `docs/PROCESS.md` says.
- **The agent works from the policy wording alone.** The claims manual is out of scope for the pilot, so the backend doesn't serve it.

### Claim states

| State | Meaning | Set when |
|---|---|---|
| `waiting` | In the queue, not started | Seeded (the data says `open`; the backend maps it to `waiting`) |
| `in_progress` | The agent is working on it | The agent run starts |
| `awaiting_signoff` | Approved for more than $1,000, payment blocked | The agent records an approval over the limit |
| `decided` | Final: declined, referred, or approved and paid | Decline or refer recorded, a payment made, or a handler signs off |

A failed run (for example the model errors) puts the claim back to `waiting` with an error step, so it can be run again.

### The API

Every operation has an `operation_id`, a one-line docstring and only required inputs, as the tech stack requires.

| Method and path | `operation_id` | Used by |
|---|---|---|
| `GET /api/health` | `health` | both |
| `GET /api/claims` | `list_claims` | dashboard |
| `GET /api/claims/{claim_id}` | `get_claim` | both |
| `GET /api/policies/{policy_id}` | `get_policy` | agent, with the plan's limits and add-on details included |
| `GET /api/customers/{customer_id}` | `get_customer` | agent, the customer and their claim history |
| `GET /api/policy-wording` | `get_policy_wording` | agent, dashboard |
| `GET /api/instructions` | `get_instructions` | agent, dashboard (read only) |
| `GET /api/handlers` | `list_handlers` | dashboard, for sign-off |
| `POST /api/claims/{claim_id}/run` | `run_agent` | dashboard: starts the agent on a waiting claim |
| `POST /api/claims/{claim_id}/start` | `start_claim` | agent: marks it `in_progress` |
| `POST /api/claims/{claim_id}/steps` | `record_step` | agent: one step of its work |
| `GET /api/claims/{claim_id}/steps` | `list_steps` | dashboard |
| `POST /api/claims/{claim_id}/decision` | `record_decision` | agent: decision, payout, calculation, reasons, policy section |
| `POST /api/claims/{claim_id}/payment` | `pay_claim` | agent: takes the amount; blocked over $1,000 without sign-off |
| `POST /api/claims/{claim_id}/sign-off` | `sign_off` | dashboard: a handler signs off, and the payment is made |

`pay_claim` refuses (with a clear error the agent can read) when the claim isn't approved, when the amount isn't the approved payout, when it's already paid, or when the payout is over the limit and nobody has signed off. `sign_off` only accepts a handler whose record says `can_approve_over_limit`. The limit itself comes from `data/company.json`, not a constant in code. No money moves anywhere: a payment is a row in the database.

## Phase 1: The backend's records

Build the SQLite database and the read-only API over UnderCover's records.

- `backend/db.py`: opens the database at the path in `UNDERCOVER_DB` (default `backend/undercover.db`, git-ignored) and creates the tables on first start: claims, policies, customers, plans and add-ons, handlers, company settings, steps, decisions, payments, sign-offs. Claims, policies and customers keep their nested parts (items, documents, trip, previous claims) as JSON columns, since nothing queries inside them.
- `backend/seed.py`: loads `company.json`, `plans.json`, `policies.json`, `customers.json`, `handlers.json` and `claims.json` into an empty database. It names those six files explicitly and never globs `data/`, which keeps `data/evals/` and `data/security/` out.
- Routes: `list_claims`, `get_claim`, `get_policy`, `get_customer`, `get_policy_wording`, `list_handlers`.
- A pytest fixture gives each test a fresh database in a temp folder.

Why SQLite with JSON columns: the tech stack names SQLite, and the pilot only ever looks claims up by id, so a full relational model for documents and items would be work with no payoff.

Success criteria:

- [x] `uv run pytest backend` passes, with tests for every route and for seeding
- [x] A test seeds the database and asserts that no claim, policy or customer id from outside the six seed files is present, and that the seed loader opens no path under `data/evals/` (checked by patching `open`)
- [x] `GET /api/claims` returns 25 claims, each with `claim_id`, `summary`, `claim_type`, `amount_claimed` and `status` `waiting`
- [x] `GET /api/claims/CLM-1001` returns the full claim with its story, items and documents
- [x] `GET /api/policies/POL-2001` returns the policy with the Premium plan's limits and deductible included
- [x] `GET /api/customers/CUS-3001` returns Maya Patel with her previous claim CLM-0412
- [x] `GET /api/claims/CLM-9999` returns 404
- [x] Every route in `/openapi.json` has an `operation_id` and a summary, and no parameter is optional (a test walks the schema)
- [x] `npm run check:python` passes with coverage at or above 80%

## Phase 2: Decisions, payments and sign-off

Add the operations the agent and the handlers use to change a claim, with the $1,000 rule enforced.

- `backend/instructions.md`: the agent's instructions, served by `get_instructions`. Keeping them in the backend means the agent and the dashboard read the same text, and the dashboard shows exactly what the agent was told.
- `start_claim`, `record_step`, `list_steps`, `record_decision`, `pay_claim`, `sign_off`, with the state changes in the table above.
- `record_decision` takes `decision` (`approve`, `decline` or `refer`), `payout`, `calculation`, `reasons` and `policy_section`. Decline and refer must have a payout of 0. An approval over the limit moves the claim to `awaiting_signoff`.
- `get_claim` now includes the decision, the payment and the sign-off, if any.

Success criteria:

- [x] `uv run pytest backend` passes, with tests for each rule below
- [x] Approving CLM-1001 for $420.00, then `pay_claim` with 420.00, gives 200 and the claim is `decided` and paid
- [x] Approving a claim for $1,500.00 leaves it `awaiting_signoff`; `pay_claim` with 1500.00 gives 403 with a message that a handler must sign off, and no payment row exists
- [x] `sign_off` on that claim with HND-01 gives 200, the payment of $1,500.00 is recorded with the handler's id, and the claim is `decided`
- [x] `sign_off` with a handler who lacks `can_approve_over_limit` gives 403
- [x] `pay_claim` with the wrong amount, twice, or on a declined claim gives 409
- [x] Recording a decline with a payout above 0 gives 422
- [x] Steps posted with `record_step` come back in order from `list_steps`
- [x] `GET /api/instructions` returns the instructions text
- [x] `npm run check:python` passes with coverage at or above 80%

## Phase 3: The UnderCover Agent

Replace the hello-world agent with one that decides a claim through the backend's API.

- `agent/main.py`: `run(claim_id, thread_id)` stays the one entry point. It reads its instructions from `get_instructions`, calls `start_claim`, then runs `create_agent` with these tools, each a thin wrapper over one API operation: `get_claim`, `get_policy`, `get_customer`, `get_policy_wording`, `record_decision`, `pay_claim`.
- Steps: `run` streams the agent and posts each tool call, tool result and model reply to `record_step` as it happens. That gives the dashboard the step-by-step view without the agent having to remember to report.
- The instructions tell the agent to read the claim, the policy, the customer's history and the wording; decide; work out the payout by the method in section 10 of the wording; explain the decision in two or three sentences with the section it rests on; record the decision; and, when it approves, pay the payout. If `pay_claim` says sign-off is needed, it stops there.
- A failed run records an error step and puts the claim back to `waiting`.
- Model: `openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME` if set, as the skeleton already does.
- `uv run -m agent CLM-1001` runs it from the command line.

Why the agent pays through a tool rather than the backend paying on approval: the spec wants the block to hold "even if the agent tries to pay", so the agent does try, and the backend's check is what stops it.

Success criteria:

- [x] `uv run pytest agent` passes, using the stub model (no test calls a real model), with tests that:
  - [x] a scripted run on CLM-1001 reads the claim, records an approval, pays it, and leaves the claim `decided` with steps recorded
  - [x] a scripted run that approves over $1,000 and then calls `pay_claim` gets the refusal back as a tool result, and the claim ends `awaiting_signoff` with no payment
  - [x] a run whose model raises an error leaves the claim `waiting` with an error step
  - [x] the agent's tools only call URLs under the backend (`/api/...`)
- [x] With the backend running, `uv run -m agent CLM-1001` on the real model (one live call, a few cents, or free with `MODEL_NAME=openrouter/free`) records a decision with a payout, reasons and a policy section, and the claim leaves `waiting`
- [x] `npm run check:python` passes with coverage at or above 80%

## Phase 4: The dashboard

Build the screens the team asked for, in the brand, against the API.

- **Queue**: every claim with its id, customer, type, amount claimed, submitted date and a state badge. States use Sea Green, Marigold, Coral and Cerulean, per `docs/BRAND.md`.
- **Claim**: the claim in full (story, items, documents, policy summary), and the agent's decision with the payout, calculation, reasons and policy section, the payment, and any sign-off.
- **Instructions**: the agent's instructions, read only.
- Hash-based navigation (`#/`, `#/claims/CLM-1001`, `#/instructions`) in a few lines of code, rather than adding a router library for three screens.
- Fonts from Google Fonts (Instrument Sans, Instrument Serif, JetBrains Mono for ids and amounts), light and dark mode following the system setting, rounded panels with no outlines, money shown as `$1,250.00`.
- A typed API client in `dashboard/src/api.ts`, strict TypeScript, no `any`.

Success criteria:

- [x] `npx vitest run --root dashboard --coverage` passes at or above 80%, with tests for the queue, the claim page, the instructions page, navigation and money formatting
- [x] `npm run check:ts` passes
- [x] Playwright tests: the queue shows 25 claims all `Waiting`; clicking CLM-1001 shows its story and its three items; the instructions page shows the instructions
- [x] Checked in the browser with the Playwright MCP server: the queue, a claim and the instructions match the brand in light and dark mode, and the layout holds at a narrow width

## Phase 5: Running the agent from the dashboard

Connect the two: a handler starts the agent, watches it work and signs off big payouts.

- `run_agent` starts `agent.run` in a background thread with a new thread id and returns at once. It refuses a claim that isn't `waiting`.
- On the claim page: a **Run agent** button on waiting claims; the steps appear as the agent works (the page polls `list_steps` every second while the claim is `in_progress`, which is simpler than streaming and fast enough for a person watching); the decision appears when it's recorded.
- On a claim waiting for sign-off: the blocked payout, a handler picker limited to handlers who can approve over the limit, and a **Sign off and pay** button.
- The queue refreshes so states change as claims move.
- The end-to-end tests run their own backend on a fresh database, so they don't touch the development data, and drive the agent's side through the API (`start_claim`, `record_step`, `record_decision`, `pay_claim`) so no test calls a model.

Success criteria:

- [ ] Backend tests: `run_agent` starts the run (with `agent.run` stubbed) and returns at once; on a claim that isn't waiting it gives 409
- [ ] Vitest tests for the Run button, the step list, the sign-off form and polling
- [ ] Playwright: after steps are posted through the API, the claim page shows them in order while `In progress`
- [ ] Playwright: a claim approved for $1,500.00 shows `Waiting for sign-off` in the queue; the claim page says the payment is blocked; choosing Dana Whitfield and clicking Sign off and pay shows it paid and `Decided`
- [ ] Checked in the browser with the Playwright MCP server, with the real model: clicking Run agent on a waiting claim shows the steps arriving one by one, then the decision with its reasons and policy section
- [ ] `npm run check` passes

## Phase 6: A pilot run and handover

Run the agent on part of the real queue, fix what that shows, and hand over.

- Run the agent live on five claims of different types, including one that should pay over $1,000, and read each decision against the wording. Fix bugs in the code and clear problems in the instructions. Accuracy against the handlers' decisions is checked later with `data/evals/`, which this build doesn't open.
- Update `docs/STATUS.md` with what's built and how to run it, and keep the README short.

Success criteria:

- [ ] Five live runs complete, each with a decision, a payout, two or three sentences of reasons and a policy section, and none with an error
- [ ] Any approval over $1,000 in those runs is `awaiting_signoff` with no payment until signed off in the dashboard
- [ ] `docs/STATUS.md` describes the backend, the agent, the dashboard, how to start them (`npm run dev`), how to run the agent, and the `UNDERCOVER_DB` setting
- [ ] `npm run check` passes: ruff, pyright, pytest at 80%, ESLint, Prettier, tsc, vitest at 80% and Playwright

## Choices for you to review

1. **Who pays.** The agent calls `pay_claim` itself and the backend blocks it over $1,000. The alternative is that the backend pays on approval. I chose the first because it tests the block the way the spec describes.
2. **Starting the agent.** One claim at a time from the dashboard, plus `uv run -m agent <claim id>`. There's no "work the whole queue" button. Live runs cost money, and the spec doesn't ask for batch runs. It's easy to add if you want one.
3. **Live model calls.** Phases 3, 5 and 6 each make a few real model calls, about 10 claims in all. Set `MODEL_NAME=openrouter/free` in `.env` if you'd rather these be free.
4. **Checking against the handlers' decisions.** The spec says the evals are for checking the agent "later", and the process says not to open `data/evals/` unless asked. So this plan builds no scoring. Tell me if you want a scoring script in the pilot.
