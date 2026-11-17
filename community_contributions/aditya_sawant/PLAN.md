# Plan: the claims pilot

This plan builds the pilot in `docs/SPEC.md`, starting from the skeleton on `main`. It has three parts. The backend holds the claims queue and enforces the rules. The UnderCover Agent decides claims through the backend's API. The dashboard lets handlers watch the queue, read each claim and its decision, follow the agent step by step, read its instructions and sign off large payouts. The dashboard uses the brand in `docs/BRAND.md`, and the unit tests live in `tests/`, as `docs/TECH_STACK.md` now asks.

It is built in six phases. Each phase adds to the backend and the dashboard together, so there is something to look at from Phase 1, starting with the new brand. Each phase leaves `npm run check` green.

## Starting again

This branch already holds an earlier build of the pilot (commits `0d5831d` to `1672de4`). This plan replaces that build rather than editing it:

- Phase 1 starts by resetting `backend/`, `agent/`, `dashboard/`, `e2e/`, `playwright.config.ts` and `docs/STATUS.md` to the skeleton on `main`, and by deleting the local `backend/undercover.db`. The earlier build stays in this branch's history for comparison.
- The updated `docs/BRAND.md`, the updated `docs/TECH_STACK.md` and this plan go into Phase 1's commit.
- Your changes to `labs/week1day2.ipynb` and `labs/week1day4.ipynb` stay out of every commit.

## Key decisions

- **The backend is the only door, and it enforces the rules.** The agent never reads `data/` or the database. It reaches claims, policies, claim history, the policy wording and its own instructions only through the API, as the tech stack asks. Every rule then lives in one place and holds whatever the model does.
- **The backend enforces the $1,000 rule; the prompt doesn't.** The limit comes from `payout_approval_limit` in `data/company.json`. An approval over the limit moves the claim to `awaiting_signoff`, and `pay_claim` refuses it with 403 until a handler signs off. The sign-off makes the payment itself, so nobody has a second step to forget. Only a handler with `can_approve_over_limit` can sign off; all three can today. The agent has no sign-off tool.
- **A refused call goes back to the model; it doesn't crash the run.** When the backend refuses a tool call with 403, 409 or 422, the tool returns the status and the backend's reason as its result. The model can then read "the payment waits for a handler's sign-off" and stop, or shorten a reason that was too long and try again.
- **The runner records the steps, not the model.** `run()` streams the agent and posts each tool call, each tool result and the final message to the backend as a step, tagged with the run's thread id. The model can't skip or invent a step, and the dashboard polls the steps to show the run live. Every run ends with the agent's final message or an error step, so the dashboard keeps following a run until it has really finished, even after the payment has already moved the claim to `decided`. A refused call is recorded as the tool's result, and the dashboard marks it in Alert Orange.
- **A run never leaves a claim half done.** A run can fail, or end with the claim still in progress, for example when the model approves but never pays. Either way, the runner records an error step and releases the claim back to `waiting`, dropping any unpaid decision. A release names its thread id, so a run can only release its own claim.
- **Each decision cites a section of the policy wording by number.** `record_decision` takes `policy_section` as a number, such as 3, and the backend rejects a number that isn't a section of `data/policy_wording.md`. The claim page shows that section's title and text under the reasons, so a handler can check the decision against the clause it rests on. The backend also requires the reason to be two or three sentences, as the spec asks.
- **The agent sees only what it needs, and never the answer key.** The seed reads only the queue's records, never `data/evals/` or `data/security/`, so no route can serve them. Claim history has its own route, which leaves out the customer's email, phone, address and date of birth.
- **The policy wording is the reference, and the claims manual is left out**, as the spec says for the pilot. The agent's instructions live in `backend/instructions.md`, so the agent and the dashboard read the same text.
- **Tests never call a model.** `MODEL_NAME=stub` swaps in a scripted model, in `agent/stub.py`, that approves the claim in full and tries to pay it. The end-to-end tests run the backend with it. `.env` is loaded without overriding the environment, so the tests' `MODEL_NAME=stub` takes precedence over any `MODEL_NAME` in your `.env`.
- **`BACKEND_URL` says where the backend is.** It defaults to `http://127.0.0.1:8000`. The agent calls it and the dashboard's dev proxy points at it, so the end-to-end tests can run a second backend on port 8001 with its own database and never touch yours.
- **Unit tests live in `tests/`**: `tests/backend/`, `tests/agent/` and `tests/dashboard/`, with the Playwright tests staying in `e2e/`. This needs the checks pointed at the new folder in `pyproject.toml`, `lefthook.yml`, `package.json`, `dashboard/vite.config.ts`, `eslint.config.js` and `tsconfig.json`. Nothing is loosened:
  - The 80% thresholds stay.
  - Coverage is still measured on `backend/`, `agent/` and `dashboard/src/`.
  - The tests are still linted and type-checked.
  - The two test-only ruff ignores (`S101` for asserts and `PLR2004` for literal numbers) move with the tests.
- **Nothing new to install.** FastAPI, SQLite from the standard library, LangChain, httpx, React, Vite, Testing Library and Playwright are already in `pyproject.toml` and `package.json`. The dashboard uses hash routes (`#/`, `#/claims/CLM-1001`, `#/instructions`) and polling, not a router library or websockets.

## Reading the brand

`docs/BRAND.md` leaves a few points open, so the dashboard reads it like this:

- **Fonts.** Montserrat Bold for headings, labels and buttons. Lato Regular for running text, such as the customer's story. Playfair Display Italic for the tagline only. Montserrat SemiBold for claim ids and amounts, with tabular figures so the columns line up. All from Google Fonts.
- **The four claim states** take the first four colors in the order the brand gives: decided is Sky Blue, in progress is Ocean Cyan, awaiting sign-off is Travel Purple and waiting is Info Blue.
- **Text on color.** The color list names a font for each color but no text color, so each badge uses whichever ink reaches at least 4.5:1 contrast on it. That means white on Sky Blue, and Deep Ink on Ocean Cyan, Info Blue and Alert Orange. Travel Purple reaches only about 4.2:1 with either white or Deep Ink, so its badge uses a deeper shade of the purple, such as `#7C3AED`, with white text.
- **Alert Orange** marks what needs someone's attention: a payout waiting for sign-off, a refused payment and a failed run.
- **Light and dark mode** follow the system setting. Light mode is `#F8FAFC` with white panels, and dark mode is `#0B1220` with black panels. Panels are rounded with no outline. Sky Blue and Ocean Cyan are darkened for text on light backgrounds and lightened on dark ones. The dashboard has no one-sided borders, no lines across the top of the page and no gradients.

## The claim states

```
waiting --start--> in_progress --decline or refer---------------------------------> decided
                       |-- approve $1,000 or less, then pay ----------------------> decided
                       |-- approve over $1,000 --> awaiting_signoff --sign-off pays--> decided
                       '-- the run fails or ends unfinished --> waiting
```

The data's `open` becomes `waiting` when the database is seeded.

## The API

Every operation has an `operation_id`, a one-line docstring and no optional inputs, and a test checks every route for all three.

| Operation | Route | Body | Used by | Phase |
|---|---|---|---|---|
| `health` | `GET /api/health` | | end-to-end tests | skeleton |
| `list_claims` | `GET /api/claims` | | dashboard, `agent queue` | 1 |
| `get_claim` | `GET /api/claims/{claim_id}` | | agent, dashboard | 1 |
| `get_policy` | `GET /api/policies/{policy_id}` | | agent, dashboard | 2 |
| `get_plan` | `GET /api/plans/{plan}` | | agent | 2 |
| `get_claim_history` | `GET /api/customers/{customer_id}/claims` | | agent, dashboard | 2 |
| `get_policy_wording` | `GET /api/policy-wording` | | agent | 2 |
| `get_instructions` | `GET /api/instructions` | | agent, dashboard | 2 |
| `list_handlers` | `GET /api/handlers` | | dashboard | 2 |
| `start_claim` | `POST /api/claims/{claim_id}/start` | `thread_id` | runner | 3 |
| `add_step` | `POST /api/claims/{claim_id}/steps` | `thread_id`, `kind`, `text` | runner | 3 |
| `list_steps` | `GET /api/claims/{claim_id}/steps` | | dashboard | 3 |
| `record_decision` | `POST /api/claims/{claim_id}/decision` | `decision`, `payout`, `reason`, `policy_section` | agent | 3 |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` | `amount` | agent | 3 |
| `sign_off` | `POST /api/claims/{claim_id}/sign-off` | `handler_id` | dashboard | 3 |
| `release_claim` | `POST /api/claims/{claim_id}/release` | `thread_id` | runner | 3 |
| `run_agent` | `POST /api/claims/{claim_id}/run` | | dashboard | 5 |

`decision` is `approve`, `decline` or `refer`. A decline or a referral has a payout of 0. The amount passed to `pay_claim` must match the approved payout.

## Where the code goes

```
backend/    main.py (the routes), models.py (request and response shapes), db.py (the database),
            seed.py (builds it from data/), claims.py (the claim rules), instructions.md
agent/      main.py (the model, the tools and run), stub.py (the scripted model),
            __main__.py (the command line)
dashboard/  src/: api.ts, format.ts, router.ts, styles.css, and a component for each page and panel
tests/      conftest.py, backend/, agent/, dashboard/
e2e/        Playwright tests of the whole pilot
```

## Phase 1: A fresh start, the records and the queue

**Builds:**

- **The skeleton, back in place** as described above. Its three unit tests move to `tests/`, and the checks point there.
- **A SQLite database seeded from `data/`.** It lives at `backend/undercover.db`, or at the path in `UNDERCOVER_DB`, is created on startup when missing, and is ignored by git. `uv run -m backend.seed` rebuilds it, and each test gets a fresh one in a temporary folder.
- **`list_claims` and `get_claim`.**
- **The dashboard's brand:** the fonts, the color and surface tokens for light and dark mode, and a header with the UnderCover name, a tagline and links to the queue and the instructions.
- **The queue page:** a count for each state, and a row per claim with its id, customer, type, amount claimed, submitted date and a state badge. At phone width the rows become cards.
- **End-to-end servers of their own.** The end-to-end tests start their own backend on port 8001 with a freshly seeded database, and their own dashboard on port 5174, which `BACKEND_URL` points at that backend. The skeleton's health test becomes a test of the queue.

**Why first:** everything else reads these records, so their shape gets fixed first. The new brand is also the biggest change from the last build, so it's on screen for you to review before the other pages are built on it.

**Success criteria:**

- [x] Before any new code is written, `git diff --stat main -- backend agent dashboard e2e playwright.config.ts` prints nothing
- [x] `uv run pytest` collects tests only from `tests/`, and vitest runs the tests in `tests/dashboard/`. Coverage is reported on `backend/`, `agent/` and `dashboard/src/` against the unchanged 80% thresholds
- [x] `uv run -m backend.seed` creates `backend/undercover.db` with 25 claims, all `waiting`
- [x] `GET /api/claims` returns the 25 claims, and CLM-1001 is Maya Patel's trip delay for 420.0, submitted 2026-06-24 and `waiting`
- [x] `GET /api/claims/CLM-1001` returns the story, the three items, the four documents and the amount claimed, and `GET /api/claims/CLM-9999` returns 404
- [x] A test confirms the seed opens nothing in `data/evals/` or `data/security/`
- [x] A test confirms every route has an `operation_id`, a one-line docstring and no optional inputs
- [x] Vitest tests cover the queue page and the formatting of money, dates and claim types, using stubbed fetches
- [x] With `npm run dev` running, the Playwright MCP server shows the queue with 25 claims and a count of 25 waiting. In light mode the page is `#F8FAFC` with white panels, and in dark mode it is `#0B1220` with black panels
- [x] In the browser, `document.fonts.check` confirms Montserrat, Lato and Playfair Display have loaded. The computed styles show headings in Montserrat 700, body text in Lato, the tagline in Playfair Display italic, and ids and amounts in Montserrat 600 with tabular figures
- [x] At 375 pixels wide, the queue has no horizontal scroll
- [x] `npm run check` passes

## Phase 2: Each claim in full, and the instructions

**Builds:**

- **The read routes for the rest of a claim:** `get_policy`, `get_plan`, `get_claim_history`, `get_policy_wording`, `get_instructions` and `list_handlers`.
- **`backend/instructions.md`, the agent's instructions.** They tell the agent to:
  - read the claim, the policy, the plan, the claim history and the policy wording
  - check that the incident fell within the covered trip, that the claim was filed within 90 days, that any waiting period was met and that no exclusion applies
  - refer the claim when a document the wording asks for is missing, or when the wording doesn't settle it
  - work out the payout the way section 10 does: per-item limits, then what a carrier has already paid, then the deductible where it applies, then the benefit's maximum
  - record the decision with two or three sentences and the section number
  - pay an approval only when it is $1,000 or less
- **The claim page at `#/claims/{id}`.** It shows a summary (the id, state, type, customer, submitted date and amount claimed), the customer's story, the items, the documents, the policy (its plan, add-ons, purchase date, trip, travelers and trip cost) and the claim history. Each queue row links to its claim page, and an unknown claim gets a plain not-found message.
- **The instructions page at `#/instructions`**, read only.

**Why here:** this is everything a handler reads before deciding, and everything the agent will read through its tools. Building the pages first lets you check that the agent will see what a handler sees, before the agent exists.

**Success criteria:**

- [x] `GET /api/policies/POL-2001` returns the Premium plan with no add-ons, bought 2026-04-22, for the trip to Rome, Italy, from 2026-06-10 to 2026-06-18 costing 3100.0, with the traveler Maya Patel
- [x] `GET /api/plans/premium` returns the Premium limits and waiting periods, the 50.0 deductible and the benefits it applies to (baggage and emergency medical)
- [x] `GET /api/customers/CUS-3001/claims` returns CLM-0412, an approved baggage delay paid at 140.0, and nothing in the response holds an email, phone number, address or date of birth
- [x] `GET /api/policy-wording` returns the text of `data/policy_wording.md`, and `GET /api/instructions` returns the text of `backend/instructions.md`
- [x] `GET /api/handlers` returns Dana Whitfield, Marcus Oyelaran and Priya Raman
- [x] An unknown policy, plan or customer returns 404
- [x] Vitest tests cover the claim page, the not-found message, the instructions page and the routes
- [x] In the Playwright MCP server, clicking CLM-1001 in the queue opens `#/claims/CLM-1001`. The page shows the story, the items at $245.00, $95.00 and $80.00, the total of $420.00, the four documents, the Premium policy for Rome, Italy, from Jun 10 to Jun 18, 2026, and CLM-0412 in the claim history
- [x] The Playwright MCP server shows `#/claims/CLM-9999` as not found, and shows `#/instructions` with the instructions and no text field, editable area or save button
- [x] At 375 pixels wide, the claim page has no horizontal scroll in either light or dark mode
- [x] An end-to-end test opens a claim from the queue, then the instructions page
- [x] `npm run check` passes

## Phase 3: The claim workflow and the $1,000 rule

**Builds:**

- **The routes that change a claim:** `start_claim`, `add_step`, `list_steps`, `record_decision`, `pay_claim`, `sign_off` and `release_claim`, with the state rules in `backend/claims.py`.
- **More on each claim.** `get_claim` adds the thread id, the decision (with the cited section's title and text), the payment and the sign-off. `list_claims` adds the decision and the payout.
- **The decision on the claim page.** The page shows the decision (the outcome, the payout, the reasons and the section of the wording it cites), the payment, the sign-off, an Alert Orange note when a payout is waiting for sign-off, and the agent's steps grouped by run. The queue shows each claim's decision.

**Why here:** the $1,000 rule is the one hard rule in the spec, and it has to hold whatever the agent does. Building and testing it before the agent exists proves the rule doesn't depend on the agent behaving. You can also drive a claim through every state by hand and see each state in the dashboard.

**Success criteria:**

- [x] `start_claim` moves a `waiting` claim to `in_progress` and records the thread id, and returns 409 for a claim in any other state
- [x] `add_step` stores the time, the thread id, the kind (`tool_call`, `tool_result`, `message` or `error`) and the text, and `list_steps` returns the steps in order. Any other kind returns 422
- [x] `record_decision` returns 409 for a claim that isn't `in_progress`
- [x] A decline or a referral with a payout of 0 moves the claim to `decided`. A decline or referral with a payout returns 422, and so does an approval with no payout
- [x] A reason of one sentence, or of four, returns 422 with a message saying it must be two or three sentences. A `policy_section` of 13 also returns 422
- [x] An approval of $420 leaves the claim `in_progress`. `pay_claim` with 420.0 records the payment and moves the claim to `decided`, and `pay_claim` with 400.0 returns 409
- [x] An approval of exactly $1,000 can be paid without a sign-off, and an approval of $1,150 moves the claim to `awaiting_signoff`
- [x] `pay_claim` on that $1,150 approval returns 403, records no payment and leaves the claim `awaiting_signoff`
- [x] A test with the limit set to $500 shows a $600 approval waiting for sign-off, which confirms the limit comes from `data/company.json` and not from the code
- [x] `sign_off` with HND-01 records Dana Whitfield and the time, pays the $1,150 and moves the claim to `decided`. It returns 404 for an unknown handler, 403 for a handler without `can_approve_over_limit` and 409 for a claim that isn't awaiting sign-off
- [x] `release_claim` with the claim's own thread id moves an `in_progress` claim back to `waiting`, drops the unpaid decision and keeps the steps. It returns 409 for a different thread id or for a claim that isn't in progress
- [x] `GET /api/claims/{id}` includes the payment, the sign-off and the decision with its section (3, "Trip Delay" and the section's text)
- [x] Vitest tests cover the decision for each outcome, the payment, the sign-off, the sign-off note and the steps
- [x] With `npm run dev` running, use curl with made-up decisions to take CLM-1001 to paid, CLM-1002 to awaiting sign-off, CLM-1003 to declined and CLM-1004 to in progress. The Playwright MCP server then shows the queue with all four states, their counts and their badges. In both light and dark mode, each badge's text has at least 4.5:1 contrast with its fill
- [x] The Playwright MCP server shows CLM-1001 approved at $420.00, with its reasons, Section 3 (Trip Delay) with its text, and the payment. It shows CLM-1002 with the Alert Orange note that $1,150.00 is waiting for a handler's sign-off
- [x] `uv run -m backend.seed` then puts every claim back to `waiting`
- [x] `npm run check` passes

## Phase 4: The UnderCover Agent

**Builds:**

- **`agent/main.py`:** `model()`, seven tools and `run(claim_id, thread_id)`.
  - The tools are thin wrappers on the API, named after its operations: `get_claim`, `get_policy`, `get_plan`, `get_claim_history`, `get_policy_wording`, `record_decision` and `pay_claim`.
  - `run()` loads the instructions from `get_instructions` as the system prompt and calls `start_claim`. It then streams the agent and posts each step. When the stream ends, it checks how the claim ended and releases the claim if the run didn't finish.
- **`agent/stub.py`:** the scripted model behind `MODEL_NAME=stub`. It reads the claim, approves it in full citing section 10, and tries to pay.
- **The command line.** `uv run -m agent CLM-1001` runs the agent on one claim and prints the decision.
- **`.env` loading** that no longer overrides the environment.

**Why here:** with the backend's rules in place, the agent is the only new moving part. The stub-model tests drive it against the real API, running in the same process.

**Success criteria:**

- [x] With a stub model, a test runs CLM-1001 through the seven tools in turn. The claim ends `decided` with a payment of 420.0, and its steps are the tool calls, the tool results and a final message, all with the run's thread id
- [x] A stub model approves CLM-1002 at $1,150 and then tries to pay. The 403 and the backend's reason come back to the model as the tool's result and are recorded as a step, and the claim ends `awaiting_signoff` with no payment
- [x] A model that stops without deciding leaves an error step and the claim `waiting`, and so does a model that raises an error partway through
- [x] Running the agent on a claim that isn't `waiting` fails without changing the claim
- [x] A test confirms the agent's tools are exactly the seven above, with no tool for sign-off, release or steps
- [x] A test confirms the system prompt is the text that `get_instructions` returns
- [x] A test confirms no module in `agent/` imports from `backend/`, so the agent reaches everything through the API
- [x] `model()` returns `openai/gpt-6-luna` at low reasoning effort by default, the model in `MODEL_NAME` when it's set, and the stub when `MODEL_NAME=stub`. A `MODEL_NAME` already set in the environment takes precedence over one in `.env`
- [x] With `npm run dev` running, `uv run -m agent CLM-1001` on the real model prints a decision. `GET /api/claims/CLM-1001` then shows the claim `decided`, with a reason of two or three sentences and a section of the wording (one real run, a few cents)
- [x] `npm run check` passes

## Phase 5: Running the agent from the dashboard, live

**Builds:**

- **`run_agent`,** which starts the agent on a waiting claim in the background with a new thread id and returns at once.
- **`uv run -m agent queue`,** which works every waiting claim in turn and prints a line for each.
- **A Run the agent button** on a waiting claim's page.
- **Live steps.** While the claim is in progress, the page polls the claim and its steps every second and shows each step as it arrives:
  - tool calls in plain words, such as "Read the policy POL-2001"
  - tool results folded, so a long one like the policy wording doesn't fill the page
  - refusals and errors in Alert Orange
- **A live queue** that refreshes every two seconds.
- **The end-to-end backend** runs with `MODEL_NAME=stub` and with `BACKEND_URL` set to port 8001.

**Why here:** this joins the agent to the dashboard, which is how the team sees what the agent does step by step. The queue command is how the whole queue gets worked straight through.

**Success criteria:**

- [x] With a stub model, `POST /api/claims/CLM-1001/run` returns 202 with a thread id, and the claim reaches `decided` with its steps under that thread id
- [x] `run_agent` returns 409 for a claim that isn't `waiting`
- [x] With a stub model, the queue command decides every waiting claim: claims of $1,000 or less end paid, and claims over $1,000 end awaiting sign-off. It leaves a claim that is already in progress alone
- [x] Vitest tests cover the button, each kind of step, and the polling stopping when the claim leaves `in_progress`
- [x] With `npm run dev` running, the Playwright MCP server clicks Run the agent on CLM-1001. It sees the claim go to in progress, its steps appear one by one, and its decision and reasons at the end, and the queue's counts change without a reload (one real run, a few cents)
- [x] An end-to-end test runs CLM-1001 from the dashboard and sees its steps, then sees the claim decided and paid at $420.00
- [x] `npm run check` passes

## Phase 6: Sign-off in the dashboard, and the whole pilot end to end

**Builds:**

- **Sign-off on the claim page.** A claim awaiting sign-off gets a handler picker and a button that names the amount, such as "Sign off and pay $1,150.00". Once the claim is signed off, the page shows who signed off, when, and the payment.
- **End-to-end tests of the whole pilot** on the stub model: the queue, a run that is paid, a run that waits for sign-off and is then signed off, and the instructions.
- **`docs/STATUS.md`,** saying what's built and how to run it.

**Why last:** the sign-off closes the loop on the $1,000 rule, and the end-to-end tests check the backend, the agent and the dashboard working together.

**Success criteria:**

- [x] Vitest tests cover the sign-off: the three handlers in the picker, the button disabled until a handler is chosen, the handler id posted, and a refusal shown as a message
- [x] An end-to-end test runs CLM-1002 and sees the refused payment as a step and the claim awaiting sign-off. It then signs off as Dana Whitfield and sees the claim decided, with $1,150.00 paid and her name
- [x] The end-to-end tests leave the dev database alone: `GET /api/claims` on port 8000 returns the same before and after `npm run e2e`
- [x] With `MODEL_NAME=stub npm run dev` running, the Playwright MCP server runs CLM-1002 and signs off as Priya Raman. It sees the claim decided with her name, the time and the payment, in light and dark mode and at 375 pixels wide. `uv run -m backend.seed` resets the database afterwards
- [x] `docs/STATUS.md` says what's built and how to run it
- [x] `npm run check` passes: ruff, pyright, pytest with 80% coverage, ESLint, Prettier, tsc, vitest with 80% coverage, and Playwright

## What the build costs

Only two runs use a real model: the command-line run in Phase 4 and the dashboard run in Phase 5. Each costs a few cents on `openai/gpt-6-luna`, or nothing if your `.env` sets `MODEL_NAME` to a free model such as `openrouter/free`. Every test uses the stub.

## Not in this plan

- Scoring the agent against `data/evals/`. The spec keeps the handlers' decisions for checking the agent's work later, and nothing in the pilot reads them.
- The claims manual, sign-in, real payments and messages to customers, as the spec says.
- A handler changing the agent's decision, or editing the instructions, which stay read only.
