# Plan: the pilot

This plan builds what `docs/SPEC.md` asks for: a backend that holds the claims and enforces the rules, the UnderCover Agent that works a claim from reading it to deciding it, and a dashboard where the team watches the queue, reads a decision and signs off a large payout.

The repo already has a hello-world skeleton in `backend/`, `agent/`, `dashboard/` and `e2e/`, with every check and the pre-commit hook in place. Each phase below grows that skeleton and leaves it green: six phases, each one a working product that does more than the last.

I have written no code. Please review the decisions below first, then ask me to implement the plan.

## Decisions to review

The spec leaves these open. I picked the simplest option that meets it, and I can change any of them before I build.

1. **A handler starts the agent from the dashboard, and the command line also works.** "Run agent" on a claim calls the backend, which runs the agent in a background task, so the handler watches the steps appear on the page they are already on. `uv run -m agent.main CLM-1001` does the same from the terminal, and with no claim id it works through every waiting claim. The cost: the backend imports the agent. The alternative is the command line alone, with the dashboard only watching.
2. **A referred claim is `decided` with the outcome `refer`.** The spec's four stages have no stage for "a person has it now", and what a handler does next is outside the pilot. The dashboard shows the outcome beside the stage, so a referral is easy to spot in the queue.
3. **Sign-off and payment stay two operations.** `docs/TECH_STACK.md` asks for paying to be its own operation that takes the amount, so a handler signs off and then pays. Two buttons also make the guard visible, which is the point of the rule.
4. **The payment must equal the approved payout, to the cent.** Otherwise an agent could approve $900 and pay $9,000 without ever passing the limit. The limit is "over $1,000", so $1,000.00 pays without sign-off and $1,000.01 does not.
5. **The agent gets a payment tool, so we can show the block working.** The spec says the system must block the payment "even if the agent tries to pay". The agent is told to pay what it approves; the backend refuses anything over the limit, and the agent reports that the claim waits for a handler. This is the pilot's clearest demonstration of the guardrail.
6. **The agent reads a customer's earlier claims and nothing else about them.** The backend's customer record holds contact details, date of birth and address, which the dashboard shows and the decision never needs. The agent's tool returns the claim history alone, so that personal data never reaches a prompt.
7. **A policy comes back with its plan's limits attached.** `get_policy` returns the per-item limit, the deductible and the rest beside the add-ons, so a small model does not have to pull them out of a table in the wording. They are the same numbers as the wording, which the agent reads too.
8. **The agent's instructions live in `backend/instructions.md`.** The backend serves them read only, the agent fetches them at the start of every run as its system prompt, and the dashboard shows them. To change the agent, edit that file.
9. **The steps reach the dashboard by polling.** Each of the agent's tools records a one-line step through the backend, and the claim page refreshes every two seconds while a claim is in progress. No websockets in the pilot.
10. **A run that fails puts the claim back in the queue.** Free and rate-limited models do fail mid-run. The runner records "the run stopped" as a step and returns the claim to `waiting`, instead of leaving it stuck at "in progress" with no way back.
11. **The end-to-end tests get their own ports and their own database** (backend 8100, dashboard 5273, `e2e/e2e.db`, rebuilt each run) and never call a model. They drive the real screens; where a test needs the agent's steps or a decision, it posts them through the API. That keeps `npm run check` free of API spend and of a model's wandering.
12. **Not used by the pilot:** `data/claims_manual.md` (the spec says not for now), `policy_wording_short.md`, `knowledge.json`, `context/` and `data/security/`, which belong to later days. I have not opened `data/evals/` and will not unless you ask; the pilot does not score the agent against the handlers' decisions.

## How the parts fit

```
dashboard (React + Vite)  --/api-->  backend (FastAPI + SQLite)  <--/api--  agent (create_agent)
  queue, claim, instructions           claims, stages, money rules,          run(claim_id, thread_id)
  run, sign off, pay                   steps, wording, instructions          six tools, no file access
```

The agent never opens a file and never touches the database. Every read and every write goes through the backend's API, so the rules live in one place and hold however the agent behaves.

### The stages of a claim

| Stage | What it means | It gets there by |
|---|---|---|
| `waiting` | In the queue, nobody has started it | Seeding (`status: open` in `data/claims.json`), or a run that stopped |
| `in_progress` | The agent is working it | `start_claim` |
| `awaiting_signoff` | Approved over $1,000, payment on hold | `decide_claim` with an approve above the limit |
| `decided` | Finished: approved, declined or referred | `decide_claim` otherwise, or `sign_off_claim` |

The outcome (`approve`, `decline`, `refer`), the payout, the reason, the policy section, the sign-off and the payment are fields on the claim. A claim approved up to the limit is `decided` straight away and shows "payment due" until `pay_claim` runs.

### The payment rule

`pay_claim` refuses unless all of these hold, and says which one failed:

1. The claim's outcome is `approve`.
2. The amount equals the payout on the claim.
3. The payout is $1,000.00 or less, or a handler has signed off.
4. The claim has not been paid already.

### The API

Every operation has an `operation_id`, a one-line docstring and no optional inputs. There are no filters or search parameters; the dashboard filters the queue in the browser.

| Operation | Route | Input | What it does |
|---|---|---|---|
| `health` | `GET /api/health` | none | Already built |
| `list_claims` | `GET /api/claims` | none | The queue: id, type, customer, summary, amount claimed, stage, outcome, payout |
| `get_claim` | `GET /api/claims/{claim_id}` | none | One claim in full, with its decision, sign-off and payment |
| `list_steps` | `GET /api/claims/{claim_id}/steps` | none | What the agent did on the claim, oldest first |
| `get_policy` | `GET /api/policies/{policy_id}` | none | The policy, its plan's limits and its add-ons |
| `get_customer` | `GET /api/customers/{customer_id}` | none | Contact details and earlier claims |
| `get_policy_wording` | `GET /api/policy-wording` | none | `data/policy_wording.md` as text |
| `get_instructions` | `GET /api/instructions` | none | `backend/instructions.md` as text |
| `list_handlers` | `GET /api/handlers` | none | The three handlers |
| `start_claim` | `POST /api/claims/{claim_id}/start` | `thread_id` | Takes the claim to `in_progress` |
| `add_step` | `POST /api/claims/{claim_id}/steps` | `step` | Records one line of what the agent is doing |
| `decide_claim` | `POST /api/claims/{claim_id}/decision` | `outcome`, `payout`, `reason`, `policy_section` | Records the decision and sets the stage |
| `stop_claim` | `POST /api/claims/{claim_id}/stop` | none | Puts a claim that is in progress back in the queue |
| `sign_off_claim` | `POST /api/claims/{claim_id}/sign-off` | `handler_id` | Records a handler's sign-off |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` | `amount` | Pays, under the rule above |
| `run_claim` | `POST /api/claims/{claim_id}/run` | none | Starts the agent on the claim in the background |

### The agent's tools

`get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `decide_claim` and `pay_claim`. Each one calls the matching API operation and records a step as it goes, so the dashboard shows the run without the model having to narrate it.

### The data

`uv run -m backend.seed` builds `backend/undercover.db` from `data/`: the 25 claims, 50 policies, 49 customers, the three plans and their add-ons, the three handlers and the company settings, including the $1,000 limit. The backend seeds itself on startup when the database is missing. Running the seed again rebuilds it, which is how we reset the queue after a demo.

---

## Phase 1: the claims store and the read API

The backend holds UnderCover's records and serves them. No decisions yet.

**Build:** `backend/schema.sql`, `backend/db.py` (one connection helper, the database path from `UNDERCOVER_DB`), `backend/seed.py`, `backend/models.py` (the Pydantic responses), and the read operations in `backend/main.py`. Lists and documents are stored as JSON columns. Tests get a temporary database through a fixture in `backend/tests/conftest.py`.

**Success criteria**

- [x] `uv run -m backend.seed` prints one line: `Seeded 25 claims, 50 policies, 49 customers, 3 plans, 3 handlers`
- [x] `curl -s localhost:8000/api/claims | jq 'length, (map(select(.stage == "waiting")) | length)'` returns `25` and `25`
- [x] `curl -s localhost:8000/api/claims/CLM-1001 | jq '[.amount_claimed, (.items | length), (.documents | length)]'` returns `[420, 3, 4]`
- [x] `curl -s localhost:8000/api/policies/POL-2001 | jq '[.plan, .plan_limits.per_item_limit, .plan_limits.deductible]'` returns `["premium", 300, 50]`
- [x] `curl -s localhost:8000/api/customers/CUS-3001 | jq '[.name, (.previous_claims | length)]'` returns `["Maya Patel", 1]`
- [x] `curl -s localhost:8000/api/policy-wording | jq -r '.text' | head -1` returns `# UnderCover Travel Insurance: Policy Wording`
- [x] `curl -s -o /dev/null -w '%{http_code}' localhost:8000/api/claims/CLM-9999` returns `404`
- [x] A test walks `app.routes` and asserts every operation has an `operation_id`, a one-line docstring and no optional inputs
- [x] `uv run pytest -q` passes with coverage at or above 80%
- [x] `http://localhost:8000/docs` in the Playwright MCP browser lists every operation above with its summary

## Phase 2: the stages, the decisions and the money rules

The backend becomes the system of record for a claim's life, and the limit becomes something no caller can get around.

**Build:** `start_claim`, `add_step`, `list_steps`, `decide_claim`, `stop_claim`, `sign_off_claim` and `pay_claim`, with the stage transitions and the payment rule. A refused call returns 409 with a plain sentence. `decide_claim` rejects a payout on a decline or a refer, and a negative payout.

**Success criteria**

Each of these is a test as well as a command I run against a seeded database.

- [x] `POST /api/claims/CLM-1001/start` with `{"thread_id": "t1"}` leaves the claim `in_progress`; a second `start` returns 409
- [x] Two `add_step` calls then `GET /api/claims/CLM-1001/steps` returns both, oldest first, with timestamps
- [x] `POST /api/claims/CLM-1001/decision` with `approve`, `420`, a reason and `Section 3: Trip Delay` leaves the claim `decided` with `payout: 420`
- [x] `POST /api/claims/CLM-1001/payment` with `{"amount": 420}` sets `paid_amount` and `paid_at`; a second payment returns 409
- [x] `POST /api/claims/CLM-1002/payment` with an amount that is not the payout returns 409 and the claim stays unpaid
- [x] A decision of `approve` for `3750` on CLM-1003 leaves the claim `awaiting_signoff`; payment returns 409 saying it waits for a handler's sign-off
- [x] `POST /api/claims/CLM-1003/sign-off` with `{"handler_id": "HND-01"}` leaves it `decided`, and the payment of `3750` then succeeds
- [x] A payout of exactly `1000` pays without sign-off; `1000.01` does not
- [x] A decision of `decline` with a payout above zero returns 422, and paying a declined or referred claim returns 409
- [x] `stop_claim` on an `in_progress` claim returns it to `waiting`; on a decided claim it returns 409
- [x] `uv run pytest -q` passes with coverage at or above 80%

## Phase 3: the UnderCover Agent

The agent works a claim end to end, through the API alone.

**Build:** `backend/instructions.md` (its role, the benefits and the limits it must apply, how to work out a payout, the three outcomes, the two or three sentence reason with the policy section, and that it pays what it approves) and `get_instructions`. In `agent/main.py`: the six tools, step recording, and `run(claim_id, thread_id)`, which fetches the instructions, starts the claim, decides it and returns the agent's final reply. A `__main__` entry runs one claim id or every waiting claim. In the backend, `run_claim` starts a run in the background and returns the thread id.

**Success criteria**

- [x] Tests with a stub model cover a full run: the claim starts, steps are recorded, the decision is saved, and the final reply comes back. No test calls a model
- [x] A stub-model test of the block: the agent approves 2,340 and tries to pay it; the payment is refused, the claim is `awaiting_signoff` and unpaid, and the refusal reaches the agent
- [x] A test asserts the agent only reads through the API: `grep -rn "data/\|open(" agent/*.py` finds nothing
- [x] `uv run -m agent.main CLM-1001` against the real model decides the claim; `curl -s localhost:8000/api/claims/CLM-1001 | jq '{stage, outcome, payout, reason, policy_section}'` shows an outcome, a payout, a reason of two or three sentences and a section of the wording
- [x] `curl -s localhost:8000/api/claims/CLM-1001/steps | jq -r '.[].step'` lists the reads and the decision in the order the agent did them
- [x] A real run on a claim the agent approves above $1,000 ends `awaiting_signoff` and unpaid, and the agent's reply says the payment waits for a handler
- [x] `POST /api/claims/CLM-1013/run` returns 202 with a thread id, and the claim reaches a decision while I poll `get_claim`
- [x] A run whose model call fails leaves the claim `waiting` with a step that says the run stopped (tested with a stub that raises)
- [x] `MODEL_NAME=openrouter/free uv run -m agent.main CLM-1023` decides the claim, so the free route works
- [x] `uv run pytest -q` passes with coverage at or above 80%

## Phase 4: the dashboard shell and the queue

The team gets the queue, in UnderCover's brand.

**Build:** `dashboard/src/styles.css` with the brand's fonts and colors as variables, light and dark through `prefers-color-scheme`, rounded panels and no outlines; a small hash router (`#/`, `#/claims/{id}`, `#/instructions`) so pages can be linked and tested without adding a dependency; `api.ts` for the typed calls; the queue page: every claim with its id, customer, type, amount, stage chip, outcome and payout, a filter by stage in the browser, a "Run agent" button on a waiting claim, and a refresh every two seconds while anything is in progress.

**Success criteria**

- [x] `npx vitest run --root dashboard --coverage` passes with statements at or above 80%
- [x] In the Playwright MCP browser at `http://localhost:5173`: 25 rows, every stage chip in its brand color (waiting Cerulean, in progress Marigold, waiting for sign-off Coral, decided Sea Green), money as `$420.00`
- [x] Filtering to "Waiting for sign-off" shows only the claims awaiting a sign-off, and clearing the filter brings all 25 back
- [x] "Run agent" on a waiting claim turns it to "In progress" in the queue without a reload
- [x] `document.fonts.check('16px "Instrument Sans"')` is true in the browser, and headings use it
- [x] The page in dark mode (`browser_emulate_media` with `colorScheme: dark`) has the `#04232E` background and readable text, checked by screenshot
- [x] No borders on one edge of a panel and no line across the top of the page, checked by screenshot against `docs/BRAND.md`

## Phase 5: the claim page, the live steps and the sign-off

Everything the spec asks the team to see, on one page.

**Build:** the claim page: the customer's story, the items, the documents, the policy with its plan and add-ons, the customer's earlier claims, and the decision panel with the outcome, the payout, the reason and the policy section. The steps appear as they happen while the claim is in progress. A sign-off panel appears on a claim awaiting sign-off, with the handler chosen from `list_handlers`; the pay button is enabled only when the payment rule allows it and says why when it does not. The instructions page shows `get_instructions` read only.

**Success criteria**

- [x] `npx vitest run --root dashboard --coverage` passes with statements at or above 80%
- [x] In the Playwright MCP browser, `#/claims/CLM-1001` shows the story, the three items with amounts, the four documents, the Premium plan with its limits and the customer's one earlier claim
- [x] With the page open, `add_step` through the API appears on the page within three seconds without a reload
- [x] A claim the agent decided shows the outcome, the payout as `$420.00`, the reason and the policy section
- [x] On a claim awaiting sign-off: the pay button is disabled and says it needs a handler's sign-off; signing off as Dana Whitfield enables it; paying shows the claim paid, with the amount and the time
- [x] `#/instructions` shows the instructions and has no input, textarea or save button on the page
- [x] A claim id that does not exist shows a plain "claim not found" page, not a blank screen

## Phase 6: end to end, and the hand-over

The whole product checked the way the team will use it.

**Build:** `playwright.config.ts` gets its own ports and `UNDERCOVER_DB`, and reseeds before the run; `dashboard/vite.config.ts` takes the backend's URL from the environment. End-to-end specs: the queue, a claim in full, the live steps, the sign-off then the payment, the blocked payment, and the instructions page. `docs/STATUS.md` is rewritten to describe the pilot and how to run it.

**Success criteria**

- [x] `npm run e2e` passes, and the specs above all appear in the output
- [x] The end-to-end run leaves `backend/undercover.db` untouched: the queue in `npm run dev` is as it was
- [x] `npm run check` is green end to end, with the output pasted into my report
- [x] A real run over five claims, including CLM-1003 and CLM-1012, from the command line: every claim ends `decided` or `awaiting_signoff`, each with a payout, a reason and a section, reported as a table
- [x] A handler's path in the browser once more: queue, open an approved claim over the limit, sign off, pay, see it paid
- [x] `docs/STATUS.md` describes the pilot, the API, the seed command and how to run the agent
- [x] Every box in this plan is ticked, with one commit per phase

## What the pilot does not build

The claims manual, sign-in, real payments, messages to customers, scoring against `data/evals/`, editing a claim or a policy, and more than one agent at a time. The agent's harness, durable state and the swarm come on later days, and I will not build ahead of the briefs.

## What this costs

Phases 3 and 6 make real model calls: around forty claim runs at low reasoning effort on `openai/gpt-6-luna`, well under a dollar. `MODEL_NAME=openrouter/free` runs the same work on a free model. The tests and the checks never call a model.
