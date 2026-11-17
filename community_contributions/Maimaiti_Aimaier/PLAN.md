# Plan: the claims pilot

The pilot gives UnderCover's handlers a claims platform with three parts. The backend holds the queue and enforces the rules. The UnderCover Agent decides claims from the policy wording. The dashboard shows the queue, each claim in full, the agent's work step by step, and its instructions.

This plan works from `docs/SPEC.md`, `docs/TECH_STACK.md` and the skeleton described in `docs/STATUS.md`. It adds no new Python or npm dependencies.

## How it fits together

```
data/*.json ──seed──▶ SQLite (backend/undercover.db)
                              ▲
                              │
dashboard (React) ───/api───▶ backend (FastAPI) ◀───/api─── agent (create_agent, OpenRouter)
refreshes every 2 seconds                                   reports each step as it works
```

The main choices, and why:

1. **The backend is the only source of truth.** The agent runs as its own process and reaches claims, policies, claim history and its instructions only through the backend's API, as the tech stack requires. The dashboard reads the same API. Nothing else touches the database.
2. **SQLite through Python's built-in `sqlite3`.** The policies, customers and handlers keep the shape they have in `data/`, stored as JSON, so seeding is simple and the API returns them as they are. A claim's record is stored the same way, and the fields that change as the claim is worked on are proper columns: its state, the run's thread id, the decision, payout, reasons, policy section, sign-off and payment. A small set of tables doesn't need an ORM.
3. **The payment rule is enforced by the backend, not only by the prompt.** The instructions tell the agent that a payout over $1,000 waits for a handler. The `pay_claim` operation refuses a payment over $1,000 that a handler hasn't signed off, whatever the agent does. A test proves this with a stub model that tries to pay anyway.
4. **The agent reports its own steps.** The agent's entry point streams the agent and sends each step to the backend: each tool call, each result and the final reply. The dashboard refreshes every 2 seconds, so a handler can watch a claim being worked on. Refreshing on a timer is the simplest approach and is fast enough for this.
5. **The instructions live in the backend.** `backend/instructions.md` holds the agent's instructions. `GET /api/instructions` returns them with the policy wording added at the end, which is exactly the system prompt the agent works from. The dashboard shows that same text, read only, so handlers see what the agent sees.
6. **Personal data stays in the database.** Customer records hold contact details and dates of birth. The API returns only the customer's name with the claim, and their claim history. Nothing in the pilot needs the rest.
7. **`data/evals/` stays out of reach.** The seed reads only the files it names in `data/` and nothing under `data/evals/` or `data/security/`. A test fails if any code in `backend/` refers to `data/evals`, or if any code in `agent/` refers to `data/` at all.
8. **The agent runs from the command line.** `npm run agent -- CLM-1001` decides one claim and `npm run agent` works through every waiting claim in queue order. The spec asks for the team to watch the agent, not to start it from the screen. See "Choices for you to review".

### Claim states

| State | Label | Color | How a claim gets there |
|---|---|---|---|
| `waiting` | Waiting | Cerulean | Every claim starts here when the queue is seeded |
| `in_progress` | In progress | Marigold | The agent starts on it |
| `waiting_for_sign_off` | Waiting for sign-off | Coral | The agent approves a payout over $1,000 |
| `decided` | Decided | Sea Green | The agent declines, refers, or approves $1,000 or less; or a handler signs off |

The brand asks for Sea Green, Marigold and Coral for three things side by side, with Cerulean as the fourth. A referred claim is shown as Decided with the decision Refer, keeping to the spec's four states.

### The API

Every operation has an `operation_id`, a one-line docstring and no optional inputs. A test walks the OpenAPI schema to check this for every operation, including those added later.

| Operation | Method and path | Input | Used by |
|---|---|---|---|
| `health` | `GET /api/health` | | Playwright startup |
| `list_claims` | `GET /api/claims` | | Dashboard |
| `get_claim` | `GET /api/claims/{claim_id}` | | Dashboard, agent |
| `get_policy` | `GET /api/policies/{policy_id}` | | Dashboard, agent |
| `get_claim_history` | `GET /api/customers/{customer_id}/claims` | | Dashboard, agent |
| `list_handlers` | `GET /api/handlers` | | Dashboard |
| `get_instructions` | `GET /api/instructions` | | Dashboard, agent |
| `start_claim` | `POST /api/claims/{claim_id}/start` | `thread_id` | Agent entry point |
| `add_step` | `POST /api/claims/{claim_id}/steps` | `thread_id`, `kind`, `text` | Agent entry point |
| `list_steps` | `GET /api/claims/{claim_id}/steps` | | Dashboard |
| `decide_claim` | `POST /api/claims/{claim_id}/decision` | `decision`, `payout`, `reasons`, `policy_section` | Agent |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` | `amount` | Agent |
| `sign_off_claim` | `POST /api/claims/{claim_id}/sign-off` | `handler_id` | Dashboard |

An unknown id returns 404. Invalid input returns 422. An operation the claim's state doesn't allow returns 409 with a plain message, and changes nothing.

## Phase 1: The records

**What it builds**

- `backend/db.py`: the SQLite database at the path in `UNDERCOVER_DB`, by default `backend/undercover.db` (already ignored by git). It creates the tables and, when the database is empty, seeds it from `data/claims.json`, `policies.json`, `customers.json` and `handlers.json`, with every claim waiting. The backend seeds on startup if needed.
- `npm run reset` (`uv run -m backend.db`): deletes the database and seeds it again, to start the pilot over.
- The read operations: `list_claims`, `get_claim`, `get_policy`, `get_claim_history` and `list_handlers`. The queue is ordered by submission date, then claim id. A claim comes back with its customer's name, and with null decision fields until it's decided.
- A pytest fixture that gives each test its own freshly seeded database in a temporary folder.
- The OpenAPI test and the `data/evals` test described above.

**Success criteria**

- [x] `uv run pytest backend` passes. Tests cover seeding (25 claims, all waiting), each read operation, 404s for unknown ids, the OpenAPI rules and the `data/evals` rule.
- [x] `npm run reset` prints that it seeded 25 claims, 50 policies, 49 customers and 3 handlers.
- [x] With `npm run dev:backend` running, `curl -s localhost:8000/api/claims` returns 25 claims, all `waiting`, CLM-1001 first.
- [x] `curl -s localhost:8000/api/claims/CLM-1001` returns the claim with its story, 3 items, 4 documents, customer name Maya Patel, status `waiting` and decision `null`.
- [x] `curl -s localhost:8000/api/policies/POL-2001` returns the Premium policy for the Rome trip, June 10 to June 18, 2026.
- [x] `curl -s localhost:8000/api/customers/CUS-3001/claims` returns one earlier claim, CLM-0412. No response from any operation contains a customer's email address or phone number, or the email, phone, address or date of birth fields of a customer record. A claim's own documents can still name an address, as CLM-1008's does.
- [x] `curl -s -o /dev/null -w "%{http_code}" localhost:8000/api/claims/CLM-9999` prints `404`.
- [x] `npm run check:python` passes with coverage of at least 80%.

## Phase 2: The claim workflow and the payment rule

**What it builds**

- `start_claim`: moves a waiting claim to in progress and records the run's thread id. It's also allowed on a claim already in progress, so a claim left there by a failed run can be run again. It's refused on any other claim.
- `add_step` and `list_steps`: the agent's steps for a claim, in order, each with its time, thread id, kind (`tool_call`, `tool_result` or `message`) and text.
- `decide_claim`: records approve, decline or refer with the payout, the reasons and the policy section, on a claim in progress. An approval over $1,000 moves the claim to waiting for sign-off. Any other decision moves it to decided. A decline or referral must have a payout of $0.00.
- `pay_claim`: records a payment (there is no real money in the pilot). It pays only an approved claim, only the approved amount and only once. Over $1,000, it pays only after a handler's sign-off. The $1,000 limit comes from `data/company.json`.
- `sign_off_claim`: a handler who may approve over the limit signs off an approved claim that is waiting for sign-off. The waiting payment is made in the same step, and the claim moves to decided.

**Why this way**: Sign-off releases the payment itself, because the spec says the payment waits until a handler signs off. Then a claim can't end up signed off but never paid.

**Success criteria**

- [x] `uv run pytest backend` passes, with tests for every state change above and every refusal, including:
  - [x] Starting a decided claim returns 409.
  - [x] Deciding a claim that isn't in progress returns 409. A decision other than approve, decline or refer returns 422, and so does a decline with a payout above $0.00.
  - [x] Approving $1,000.00 exactly moves the claim to decided. Approving $1,000.01 moves it to waiting for sign-off.
  - [x] Paying a claim approved for $1,250.00 before sign-off returns 409 with a message that the payment needs a handler's sign-off, and no payment is recorded.
  - [x] Paying a different amount from the approved payout, paying twice, and paying a declined or referred claim each return 409.
  - [x] After a sign-off by HND-01, the claim is decided and paid $1,250.00, signed off by HND-01. Signing off a claim that isn't waiting for sign-off returns 409, and an unknown handler returns 404.
- [x] Against the dev backend with curl: start CLM-1002, approve $1,150.00, then try to pay $1,150.00. The payment returns 409 and the claim shows `waiting_for_sign_off` and unpaid. Sign off as HND-01, and the claim shows `decided`, paid $1,150.00. Then `npm run reset`.
- [x] `npm run check:python` passes with coverage of at least 80%.

## Phase 3: The UnderCover Agent

**What it builds**

- `backend/instructions.md` and `get_instructions`, which returns the instructions with the policy wording from `data/policy_wording.md` added at the end. The instructions tell the agent to:
  1. read the claim, the policy and the customer's claim history
  2. check the claim against the wording: the dates of the covered trip, the travelers, the benefit and its waiting period, the documents the benefit's section asks for, the exclusions, the limits and the deductible
  3. approve when the wording covers the claim, decline when it doesn't, and refer when the claim needs a handler's judgment or more information, such as a missing document
  4. work out the payout as section 10 of the wording describes
  5. record the decision with reasons in two or three sentences, and the relevant section, such as "Section 3, Trip Delay"
  6. pay an approved claim for the payout, unless the payout is over $1,000, which waits for a handler's sign-off
- The agent's tools in `agent/main.py`: `get_claim`, `get_policy`, `get_claim_history`, `decide_claim` and `pay_claim`. Each calls one backend operation and returns the backend's response as it is, including refusals. That way the agent reads "needs a handler's sign-off" and can say so.
- The entry point `run(claim_id, thread_id)`. It fetches the instructions, starts the claim and builds the agent with `create_agent`. It streams the agent with `stream_mode="updates"`, sends each tool call, tool result and model reply to `add_step`, and returns the final reply. The model stays as it is: `openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME` if set.
- `agent/__main__.py`: `uv run -m agent CLM-1001` runs the agent on one claim with a new thread id and prints the result.

**Success criteria**

- [x] `uv run pytest agent` passes, using a stub model and the backend's test client, never a real model:
  - [x] A scripted run on CLM-1001 calls `get_claim`, `get_policy` and `get_claim_history`, approves $420.00 and pays. The claim ends decided and paid $420.00, and `list_steps` has a step for each tool call, each result and the final reply.
  - [x] A scripted run that approves $1,250.00 and then calls `pay_claim` anyway leaves the claim waiting for sign-off and unpaid. The tool result the model receives says the payment needs a handler's sign-off.
  - [x] A scripted decline leaves the claim decided with a payout of $0.00 and no payment.
  - [x] The system prompt the agent receives is the text from `get_instructions`.
  - [x] `uv run -m agent CLM-1001` calls `run` with that claim (with `run` replaced in the test).
- [x] `curl -s localhost:8000/api/instructions` returns the instructions, followed by the policy wording, including "How we work out your payment".
- [x] One run with the real model: after `npm run reset`, with the dev backend running, `uv run -m agent CLM-1001` finishes. `GET /api/claims/CLM-1001` shows a decision, a payout, two or three sentences of reasons and a policy section, and `GET /api/claims/CLM-1001/steps` lists the agent's tool calls in order.
- [x] `npm run check:python` passes with coverage of at least 80%.

## Phase 4: The dashboard and the queue

**What it builds**

- The brand: Instrument Sans, Instrument Serif and JetBrains Mono from Google Fonts, and the brand colors as CSS variables. Light and dark mode follow the system setting: a `#F0F4F5` page with white panels, or a `#04232E` page with black panels. Panels are rounded with no outlines. JetBrains Mono is used for claim ids, amounts and dates.
- The page frame: the UnderCover name with a short tagline in Instrument Serif, and links to the Queue and the Instructions. Pages are addressed with the URL hash (`#/`, `#/claims/CLM-1001`, `#/instructions`), which avoids adding a router.
- `dashboard/src/api.ts`, with typed calls for each operation, and a small hook that fetches data and refreshes it every 2 seconds.
- The queue page: four tiles with the number of claims in each state, and a table listing claim, customer, type, submitted date, amount claimed, state, decision and payout. Amounts are shown in US dollars, such as $1,150.00. Each claim id links to its page. If the backend can't be reached, the page says so.
- End-to-end tests on their own servers. Playwright starts a backend on port 8001 with its own database, `e2e/undercover.db`, reset before each run, and a dashboard on port 5174 that sends its API calls to that backend. That way `npm run check` never changes your dev data, and it works while `npm run dev` is running. The health test is replaced by a queue test.

**Success criteria**

- [x] Vitest tests pass and cover the queue rows, the state counts, money formatting, the message when the backend is down, and the hash addresses for each page. Dashboard coverage is at least 80%.
- [x] `e2e/queue.spec.ts` passes: 25 claims listed, CLM-1001 Waiting, the state tiles add up to 25 and agree with the table, and clicking CLM-1001 opens `#/claims/CLM-1001`. (The plan first said 25 in the Waiting tile, but other e2e tests change claims in the same run.)
- [x] `npm run e2e` passes twice in a row, which shows each run starts from a fresh database.
- [x] `npm run check` passes with `npm run dev` running at the same time.
- [x] In the browser with the Playwright MCP server, at `localhost:5173` and 1280 pixels wide:
  - [x] The queue shows 25 claims, with no page-wide horizontal scroll.
  - [x] The computed styles show Instrument Sans for the body text and JetBrains Mono for claim ids and amounts.
  - [x] The state tiles and labels use Cerulean, Marigold, Coral and Sea Green with the text colors the brand specifies.
  - [x] With dark mode emulated, the page background is `#04232E` and panels are black.
  - [x] I take a screenshot in light mode and one in dark mode, and check them against `docs/BRAND.md`.
- [x] With the queue open, starting CLM-1003 through the API changes its row to In progress within 3 seconds, without reloading the page. This is checked by an e2e test, so it doesn't change the dev data.

## Phase 5: The claim, the agent's steps, sign-off and the instructions

**What it builds**

- The claim page:
  - a header with the claim id, state, customer, claim type, incident date and place, and amount claimed
  - the customer's story, the items claimed and each document's full text
  - the policy: plan, add-ons, purchase date, trip dates, destination, trip cost and travelers
  - the customer's claim history
  - the agent's decision: Approve, Decline or Refer, with the payout, the reasons and the policy section, and the payment, which is either paid (with the amount and date), waiting for sign-off, or not paid
  - the agent's steps, numbered, with each step's time and text. Long tool results fold away. The list grows while the agent works.
- Sign-off: on a claim waiting for sign-off, a handler chooses their name and presses "Sign off and pay $1,150.00". The page then shows who signed off and the payment.
- The instructions page: the exact text the agent receives, read only, with no controls to edit it.

**Success criteria**

- [x] Vitest tests pass for the claim page sections, the steps list, sign-off (which sends the chosen handler and shows the result), and the instructions page (which has no editable fields). Dashboard coverage stays at least 80%.
- [x] `e2e/claim.spec.ts` passes. The test drives CLM-1002 through the API the way the agent does: start, two steps, then approve $1,150.00. With the page open, the steps appear without a reload, and the claim shows Waiting for sign-off with a payout of $1,150.00. A payment through the API returns 409. Signing off in the page as Dana Whitfield changes the claim to Decided, paid $1,150.00, signed off by Dana Whitfield.
- [x] `e2e/instructions.spec.ts` passes: the instructions and the policy wording are shown, and the page has no input or text area.
- [x] In the browser with the Playwright MCP server, after the agent's real run on CLM-1001 from phase 3:
  - [x] The CLM-1001 page shows the story, items, documents, policy, claim history, decision and steps, in light and dark mode.
  - [x] The longest document and the longest tool result are readable without breaking the layout.
- [x] `npm run check` passes.

## Phase 6: Working the queue

**What it builds**

- `uv run -m agent` with no claim id works through every waiting claim in queue order, each with a new thread id, and prints one line per claim with its decision, payout and state. `npm run agent` runs it. If a run fails, the claim stays in progress and can be run again by its id.
- `docs/STATUS.md` brought up to date, saying what's built and how to run it: `npm run dev`, `npm run agent`, `npm run reset` and `npm run check`.

**Success criteria**

- [x] A test of the queue run (with `run` replaced) shows that it runs every waiting claim in order and skips decided ones.
- [x] With the real model, after `npm run reset`, `npm run agent` works through all 25 claims. The queue is open in the browser with the Playwright MCP server throughout.
  - [x] Claims move from Waiting to In progress to Decided or Waiting for sign-off without a reload. Opening a claim while it's being worked on shows its steps as they're added.
  - [x] When the run ends, `GET /api/claims` shows every claim decided or waiting for sign-off, each with a decision, reasons and a policy section.
  - [x] No claim has a payment over $1,000 without a sign-off.
- [x] Signing off one claim that is waiting for sign-off, in the browser, pays it and moves it to Decided.
- [x] `npm run check` passes, and I report the results.

The agent's accuracy against the handlers' decisions isn't measured in this plan, because that needs `data/evals/`, which stays closed unless you ask. The run shows the system working end to end, not how often the agent is right.

## Not in this plan

- The claims manual, sign-in, real payments and messages to customers, as the spec says.
- Changing or rejecting the agent's decision from the dashboard. The spec asks for sign-off only.
- Editing the instructions. They're read only.
- Scoring the agent against `data/evals/`.

## Choices for you to review

1. **Running the agent from the command line, not from the dashboard.** The spec asks the team to watch the agent work, not to start it from the screen. Keeping the agent in its own process keeps the rule that it reaches everything through the API. The alternative is a "Run the agent" button that asks the backend to start the agent in the background. It's a small addition, but the backend would then depend on the agent.
2. **A referred claim counts as Decided.** This keeps to the spec's four states, and the decision column shows Refer. The alternative is a fifth state, Referred.
3. **Spending on the model.** Only two steps call a real model: one claim in phase 3 and the full queue of 25 claims in phase 6. Your `.env` doesn't set `MODEL_NAME`, so these use `openai/gpt-6-luna` and spend a little on OpenRouter. If you'd rather not spend on it, I can run phase 6 on three claims, or you can set `MODEL_NAME=openrouter/free`, which is free but slower and less dependable with tools.
