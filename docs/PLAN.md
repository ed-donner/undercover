# Plan: the claims pilot

This plan builds the pilot in `docs/SPEC.md` on top of the hello-world skeleton, following `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`. It has six phases, each building on the last. Every phase ends with its checks green, `docs/STATUS.md` updated and a commit.

## What we're building

- **The backend** (`backend/`): FastAPI on SQLite. It loads UnderCover's records from `data/`, serves them through the API and enforces the rules. The agent and the dashboard both go through it, and neither touches the database or `data/` directly.
- **The UnderCover Agent** (`agent/`): LangChain's `create_agent` on OpenRouter. For one claim it reads the claim, the policy, the customer's claim history and the policy wording through tools that call the API. Then it records a decision with a payout, a two or three sentence reason and the policy section, and pays approvals of up to $1,000. Each step it takes is posted to the backend as it happens.
- **The dashboard** (`dashboard/`): React, Vite and TypeScript. It has three pages: the queue, a claim in full with the agent's live steps and a sign-off form, and the agent's instructions (read only).

```
data/ --seed--> SQLite <-- backend: FastAPI, /api <-- dashboard: polls every 2 seconds
                               ^
                               +-- agent: uv run -m agent --> OpenRouter
```

## Key decisions, and why

1. **Storage: SQLite through Python's built-in `sqlite3`, with no ORM.** Each record from `data/` (claim, policy, customer, handler) is stored as the JSON it arrived in, in a table keyed by its id. Everything the platform changes gets real columns: a claim's status, decision, payout, reason, policy section, sign-off and payment, plus a `steps` table. The records are deeply nested (items, documents, trips, claim history), and flattening them into a dozen tables would add a lot of code and buy the pilot nothing. Reference documents that never change (`plans.json`, `company.json`, `policy_wording.md`) are read straight from `data/`. The database file is `backend/undercover.db`, which `*.db` in `.gitignore` already keeps out of git, or the path in `UNDERCOVER_DB`, which the tests use.
2. **Claim states.** These are the four the spec names. Each move happens in one `UPDATE ... WHERE status = ...` statement, so two processes can't both start the same claim.

   | Status | How a claim gets there |
   |---|---|
   | `waiting` | The seed puts every claim here (the data says `open`) |
   | `in_progress` | The agent starts work on it. An approval of $1,000 or less stays here until the agent pays it |
   | `waiting_for_sign_off` | The agent approves a payout over $1,000 |
   | `decided` | The agent declines or refers, or the approved payout has been paid |

   So `decided` always means there's nothing left to do. If the agent approved a claim and then failed to pay it, the claim stays visibly in progress instead of looking finished but unpaid. A referral is a decision the agent makes, so a referred claim is `decided` with the decision `refer`, and a handler picks it up from there.
3. **The $1,000 rule is enforced in the backend, not in the prompt.** The instructions tell the agent not to pay over $1,000. The pay operation refuses anyway with `403`, whatever the agent does. Payment also has to match the approved payout exactly, and a claim can be paid only once, so the agent can't get round the limit by paying a lower amount or splitting the payout. A handler's sign-off records who signed off and makes the payment itself, in the backend. The limit comes from `payout_approval_limit` in `data/company.json`.
4. **The agent's tools match the API operations one to one** (`get_claim`, `get_policy`, `get_customer`, `get_policy_wording`, `record_decision`, `pay_claim`). In LangChain 1.4, an exception in a tool ends the whole run (I checked this against the installed version). So when the backend refuses something, the tool hands the refusal back to the model as text, for example `{"detail": "A payout over $1,000.00 waits for a handler's sign-off."}`, and the agent can carry on and explain.
5. **Live steps come from streaming and polling.** `run(claim_id, thread_id)` streams the agent's updates and posts each one to the backend: tool calls with their arguments, tool results and the model's replies. The dashboard re-reads every 2 seconds. Polling is the simplest way to get live updates; WebSockets or server-sent events would need more code on both sides and give nothing the team would notice. Each step carries the thread id, which tells one run of a claim apart from another.
6. **The agent runs from the command line, and the dashboard watches.** `uv run -m agent` works every waiting claim in turn, and `uv run -m agent CLM-1001 CLM-1004` works just those claims, which is a cheap way to try a single claim. The spec asks the team to see the agent's work, not to start it, and a Run button would make the backend depend on the agent. These are the same commands the course videos use (from `guides/for_agents/`), and `uv run -m backend.seed` resets the queue.
7. **The agent's instructions live in the backend** as `backend/instructions.md`, served by `GET /api/instructions`. The agent fetches them as its system prompt, and the dashboard shows the same text. The instructions are short and say what to achieve rather than listing every step: decide against the wording, work out the payout under section 10, refer when a document the wording asks for is missing or the claim needs a person's judgment, write the reason for a handler, record the decision, and pay approvals of $1,000 or less.
8. **Personal data stays out of the model.** The `get_customer` tool gives the model the customer's name, how long they've been a customer and their earlier claims. It leaves out the email, phone, date of birth and address, which a decision doesn't need and which would otherwise go to OpenRouter. The dashboard still shows everything to the handlers.
9. **The dashboard adds no dependencies.** Routing is a small hash router (`#/claims/CLM-1001`), so deep links and the back button work on any static host. Styling is one CSS file of brand variables, with light and dark mode following the system setting.
10. **The end-to-end tests get their own servers and database.** Playwright starts the backend on port 8001, freshly seeded into a database under `e2e/test-results/`, and the dashboard on port 5174. The dashboard proxies to whichever backend `BACKEND_URL` names, which defaults to port 8000. So `npm run check` never touches the queue you're looking at in `npm run dev`. Tests set up the states they need, such as a claim waiting for sign-off, through the same API operations the agent uses. Each test uses its own claim, so the tests can run in parallel.

## The API

Every operation has an `operation_id` equal to its function name, a one-line docstring and only required inputs. A test checks all three against the OpenAPI schema.

| Operation | Route | Inputs | What it does |
|---|---|---|---|
| `health` | `GET /api/health` | | Already there |
| `list_claims` | `GET /api/claims` | | The queue: id, customer name, type, submitted date, amount claimed, status, decision, payout, paid amount |
| `get_claim` | `GET /api/claims/{claim_id}` | | The claim in full: story, items, documents, decision, reason, policy section, sign-off and payment |
| `get_policy` | `GET /api/policies/{policy_id}` | | The policy, with its plan's limits and the details of its add-ons |
| `get_customer` | `GET /api/customers/{customer_id}` | | The customer, with their claim history |
| `list_handlers` | `GET /api/handlers` | | The three handlers |
| `get_policy_wording` | `GET /api/policy-wording` | | The wording's version and text |
| `get_instructions` | `GET /api/instructions` | | The agent's instructions |
| `start_claim` | `POST /api/claims/{claim_id}/start` | | `waiting` to `in_progress`, otherwise `409` |
| `list_steps` | `GET /api/claims/{claim_id}/steps` | | The agent's steps on the claim, in order |
| `add_step` | `POST /api/claims/{claim_id}/steps` | `thread_id`, `kind`, `name`, `content` | Records one step: `kind` is `tool_call`, `tool_result` or `reply` |
| `record_decision` | `POST /api/claims/{claim_id}/decision` | `decision`, `payout`, `reason`, `policy_section` | Only on a claim in progress. Approve needs a payout above $0, and decline and refer need $0 |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` | `amount` | Only an approved, unpaid claim, and only its exact payout. Over $1,000 it needs a sign-off first, otherwise `403` |
| `sign_off` | `POST /api/claims/{claim_id}/sign-off` | `handler_id` | Only on a claim waiting for sign-off, by a handler who `can_approve_over_limit`. Records the sign-off and pays |

An unknown id returns `404`, the wrong state returns `409` and invalid input returns `422`.

## Phase 1: The backend's records

Builds `backend/db.py` (the connection and the tables), `backend/seed.py` (`uv run -m backend.seed` resets the database from `data/`, and the backend seeds it at startup if the file is missing) and the read operations: `list_claims`, `get_claim`, `get_policy`, `get_customer`, `list_handlers` and `get_policy_wording`. The seed reads only the files it names at the top of `data/`, never `data/evals/` or `data/security/`. This phase comes first because everything else reads these records.

- [x] `uv run -m backend.seed` reports 25 claims, 50 policies, 49 customers and 3 handlers.
- [x] `GET /api/claims` returns 25 claims, CLM-1001 to CLM-1025 in order, all `waiting`, with their customer names. A test checks the set of ids exactly, so nothing from the evaluation or security sets can slip into the queue.
- [x] `GET /api/claims/CLM-1001` returns Maya Patel's story, 3 items, 4 documents, `amount_claimed` 420.0, status `waiting` and decision `null`.
- [x] `GET /api/policies/POL-2001` returns the Premium plan with its limits (deductible 50.0, per-item limit 300.0, trip delay maximum 800.0) and no add-ons. A test on a policy with Electronics Plus shows the add-on's details and its $1,200 electronics limit.
- [x] `GET /api/customers/CUS-3001` returns Maya Patel with one earlier claim, CLM-0412.
- [x] `GET /api/handlers` returns Dana Whitfield, Marcus Oyelaran and Priya Raman.
- [x] `GET /api/policy-wording` returns version `2026.1` and the text of `data/policy_wording.md`.
- [x] `GET /api/claims/CLM-9999`, `/api/policies/POL-9999` and `/api/customers/CUS-9999` return `404`.
- [x] Deleting the database file and starting the backend creates and seeds it again.
- [x] A test checks that every operation in the OpenAPI schema has an operation id, a one-line docstring and only required inputs.
- [x] `npm run check:python` passes: ruff, pyright and pytest with at least 80% coverage.

## Phase 2: The claim workflow and the payment rule

Builds `start_claim`, `add_step`, `list_steps`, `record_decision`, `pay_claim`, `sign_off` and `get_instructions`, with a first version of `backend/instructions.md`. This is where the business rules live, so it's built and tested before the agent that relies on them.

- [x] Within the limit: `POST /api/claims/CLM-1001/start` returns `in_progress`, and a second start returns `409`. Recording `approve` with payout 420 leaves it `in_progress`. Paying 420 makes it `decided` with `paid_amount` 420.0 and a `paid_at` time, and paying again returns `409`.
- [x] Over the limit: start CLM-1003 and record `approve` with payout 1500, and the claim is `waiting_for_sign_off`. `POST /api/claims/CLM-1003/payment` with 1500 returns `403` with "A payout over $1,000.00 waits for a handler's sign-off.", and the claim is still unpaid. A sign-off by `HND-01` makes it `decided`, with `signed_off_by` `HND-01` and `paid_amount` 1500.0.
- [x] The rule holds against workarounds. Tests show that paying an amount other than the payout returns `409`, paying 1000 against an approved 1500 returns `409`, a second payment returns `409`, and paying a declined or referred claim returns `409`.
- [x] Decisions are checked. Tests show that a decline or referral with a payout above $0 returns `422`, an approval of $0 returns `422`, a decision other than approve, decline or refer returns `422`, a decision on a claim that isn't in progress returns `409`, and a decline or referral makes the claim `decided`.
- [x] Sign-off is checked. Tests show that signing off a claim that isn't waiting for sign-off returns `409`, an unknown handler returns `404`, and a handler without `can_approve_over_limit` returns `403`.
- [x] Steps posted to a claim come back from `list_steps` in the order they were posted, with their thread id, kind, name, content and time.
- [x] `GET /api/instructions` returns the text of `backend/instructions.md`.
- [x] The OpenAPI test from Phase 1 passes with the new operations.
- [x] `npm run check:python` passes, and `uv run -m backend.seed` resets the queue after the manual checks.

## Phase 3: The UnderCover Agent

Builds the agent's six tools, `run(claim_id, thread_id)` and `agent/__main__.py`. `run` fetches the instructions, starts the claim, streams the agent and posts each step to the backend, then returns the agent's final reply. The command line works the queue one claim at a time and prints a line for each. Tests use a stub model that plays out a script of tool calls, as the skeleton's test does, so no test calls a real model.

- [ ] A stub run that approves CLM-1001 for $420 and pays it leaves the claim `decided`, with the decision, reason, policy section and `paid_amount` 420.0. Its steps (the tool calls, the tool results and the reply) are recorded in order under the run's thread id.
- [ ] A stub run that approves CLM-1003 for $1,500 and then tries to pay finishes normally. The pay tool hands the backend's `403` refusal back to the model, and the claim is `waiting_for_sign_off` and unpaid.
- [ ] A stub run that declines a claim leaves it `decided` and unpaid.
- [ ] Running a claim that isn't waiting raises an error, so a decided claim is final.
- [ ] The agent's system prompt is the text from `GET /api/instructions`.
- [ ] The `get_customer` tool returns the name, the customer-since date and the earlier claims, with no email, phone, date of birth or address.
- [ ] `uv run -m agent` with no arguments works only the waiting claims, and with claim ids works only those (tested with the stub).
- [ ] Outside its tests, `agent/` opens no files and imports nothing from `backend/`, so it reaches everything through the API: `grep -rnE "open\(|from backend|import backend" agent --include=*.py` finds matches only in `agent/tests/`.
- [ ] `npm run check:python` passes.

## Phase 4: The dashboard and the queue

Builds the dashboard's frame: `styles.css` with the brand's fonts, colors and light and dark surfaces, a typed API client, the hash router, a header with links to the queue and the instructions, and a `usePolling` hook. Then the queue page: a count for each status, and a table of claims (id, customer, type, submitted, claimed, status, decision, payout) that links to each claim and refreshes every 2 seconds. Status badges use Cerulean for waiting, Marigold for in progress, Coral for waiting for sign-off and Sea Green for decided, per `docs/BRAND.md`. It also sets up the end-to-end tests' own servers and database (decision 10), and a queue test replaces the health test.

- [ ] Vitest tests cover the queue rendering from a stubbed API, the status labels and counts, money shown as `$1,250.00`, the table updating on the next poll, routing to a claim, and a clear message when the backend can't be reached.
- [ ] `npm run check:ts` passes: Prettier, ESLint, tsc and vitest with at least 80% coverage.
- [ ] `npm run e2e` passes on ports 8001 and 5174. The queue test sees 25 claims, with CLM-1025 waiting.
- [ ] Running `npm run e2e` while `npm run dev` is up leaves the dev queue untouched: the claims' statuses at `localhost:8000/api/claims` are the same before and after.
- [ ] In the browser with the Playwright MCP server, `http://localhost:5173` shows the four status counts and 25 claims. In light and dark mode, the page and panels use the brand's surfaces and text colors, headings and body are in Instrument Sans, and ids and money are in JetBrains Mono. Panels are rounded with no outline, there are no one-edge borders or lines across the top, and the console shows no errors.

## Phase 5: A claim in full, the live steps, sign-off and the instructions

Builds the claim page: the agent's decision (decision, payout, reason, policy section, and payment or sign-off state), the claim (summary, story, items with their total, documents), the policy (plan, add-ons, trip, travelers, purchase date), the customer and their earlier claims, and the agent's steps. The steps refresh every 2 seconds, and long tool results fold away. A claim waiting for sign-off shows a form to choose a handler and "Sign off and pay $1,500.00". The instructions page shows the agent's instructions with no way to edit them.

- [ ] Vitest tests cover each section of the claim page, the steps list and its labels, the sign-off form appearing only when a claim is waiting for sign-off, the form posting the chosen handler and showing the payment, and the instructions page.
- [ ] End-to-end: CLM-1001's page shows Maya Patel's story, its 3 items totaling $420.00, its 4 documents, the Premium plan and the earlier claim CLM-0412.
- [ ] End-to-end: with CLM-1013's page open, a step posted through the API appears without a reload.
- [ ] End-to-end: after CLM-1003 is started and approved for $1,500 through the API, its page shows "Waiting for sign-off", and a payment through the API is refused with `403`. Signing off as Dana Whitfield in the page then shows "Paid $1,500.00" and "Signed off by Dana Whitfield", and the queue shows CLM-1003 as decided.
- [ ] End-to-end: the instructions page shows the text of `backend/instructions.md`, with no text box or button that could change it.
- [ ] In the browser with the Playwright MCP server, a claim page reads clearly in light and dark mode, with the decision first, and the console shows no errors.
- [ ] `npm run check` passes.

## Phase 6: The pilot on real claims

Runs the real agent on GPT-6 Luna through OpenRouter for the first time, with `npm run dev` up and the dashboard open through the Playwright MCP server. It fixes whatever the run turns up, then brings `docs/STATUS.md` up to date. This is the only phase that calls a model.

- [ ] After `uv run -m backend.seed`, `uv run -m agent CLM-1001` prints one line for the claim. While it runs, the claim page in the browser moves from waiting to in progress to its final state, with steps appearing as they happen.
- [ ] CLM-1001 ends with a decision, a payout if approved, a reason of two or three sentences and a policy section, and if it's approved for $1,000 or less it shows as paid.
- [ ] `uv run -m agent` works the other 24 claims. Afterwards no claim is waiting or in progress, and every claim has a decision, a reason and a policy section.
- [ ] Every approval over $1,000 is waiting for sign-off and unpaid, and every approval of $1,000 or less is paid.
- [ ] Signing off one held claim in the browser pays it.
- [ ] `docs/STATUS.md` says what's built and how to run it: `npm run dev`, `uv run -m agent`, `uv run -m agent <claim ids>`, `uv run -m backend.seed` and `npm run check`.
- [ ] `npm run check` passes, and the results are reported.

## Not in the pilot

- The claims manual. The agent works from the policy wording alone, as the spec says.
- Sign-in, real payments and messages to customers.
- Scoring the agent against the handlers' decisions in `data/evals/`. `docs/PROCESS.md` says not to open that folder unless asked, so I'll do it only if you ask.
- Retrying a failed run, or running a decided claim again. Reseed with `uv run -m backend.seed` instead.
- Screens for a handler to work a referred claim, or to turn down an approval at sign-off. The spec asks for neither.
- A button on the dashboard that starts the agent.
