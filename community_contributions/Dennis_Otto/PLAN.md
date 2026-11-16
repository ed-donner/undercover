# Plan: the claims pilot

Builds what `docs/SPEC.md` asks for: a backend that holds UnderCover's records, the UnderCover Agent that works the queue, and a dashboard for the handlers.

## Starting point

- The hello-world skeleton passes `npm run check` on branch `week1day3-DennisOtto`.
- `data/claims.json` has 25 claims, all `open`. On the amount claimed, 10 are over $1,000 and 15 are not. The final payout can be lower than the amount claimed.
- `data/` already has every record the pilot needs.
- I have not opened `data/evals/`, and this plan never does.

## Approach

### How the pieces fit

```
dashboard  --->  backend (FastAPI + SQLite)  <---  agent (LangChain)
                   holds every record              reads and acts only
                   enforces every rule             through the API
```

The backend owns the rules. The agent can ask for anything its tools allow, and the backend decides what actually happens. That is how the spec's rule holds "even if the agent tries to pay".

This protects against the agent, not against every caller. With no sign-in, the API cannot tell who is calling, so a person or program with access to the backend could call `sign_off_claim` directly. See "What this plan leaves open".

### Decisions and why

| Decision | Why |
|---|---|
| Use Python's built-in `sqlite3`, with no ORM | The tech stack says SQLite and the pilot has a few simple tables. Week 2 moves to Supabase, so a heavier layer buys little. |
| One SQLite connection per request, with every write in a `BEGIN IMMEDIATE` transaction | Checks and writes happen as one step. A second request at the same moment waits, sees the result of the first and gets a normal 409, not a database error. |
| Keep SQLite's default journal, with no WAL mode, and its default 5 second wait for a lock | Transactions are short, so nothing more is needed. The data stays in one file, which `*.db` ignores and a reset can delete. A wait past 5 seconds surfaces as a 500, which is acceptable for a pilot. |
| No new Python or npm packages | Everything needed is already installed. |
| The agent runs in a single background worker inside the backend, one claim at a time | The handlers can start it from the dashboard, nothing extra needs running, and running in order avoids hitting model rate limits. The agent still reaches the backend only over HTTP. |
| The dashboard polls every 2 seconds | Handlers see the steps while the agent works, with far less code than a live stream. |
| The agent writes its own steps through the API, as plain-English lines | Only the agent knows what it is doing, and this keeps to "only through the backend's API". |
| Instructions live in `backend/instructions.md`, served by a read-only operation | One source for both the agent and the dashboard. With no write operation, read only is enforced rather than just hidden in the screen. |
| The customer API returns name, customer-since date and claim history only | The agent needs the history and the name to compare with documents. Nothing in the pilot needs addresses, emails, phone numbers or dates of birth, so they stay out of the API and out of the model's context. |
| The dashboard uses the URL hash for pages, with no router library | Three pages do not justify a dependency. Links to a claim still work and survive a refresh. |
| Colors are CSS variables in one theme file, with light and dark from `prefers-color-scheme` | `docs/BRAND.md` defines both modes. |

### The claim lifecycle

| Status | Label | Reached when |
|---|---|---|
| `waiting` | Waiting | Seeded from `open`, or a run failed |
| `in_progress` | In progress | The agent starts the claim |
| `waiting_for_sign_off` | Waiting for sign-off | The agent approves a payout over the limit |
| `decided` | Decided | Declined, referred, approved with a $0 payout, or paid |

Only the backend changes statuses. A failed run is reset after `run` has returned or raised, so nothing from that run is still writing. The reset touches `in_progress` claims only, and those can never have a payment. The worker lives in the backend process, so a restart ends any run with it, and a claim still queued at that moment simply stays `waiting`. That is why runs need no id on each write to guard against a stale run: with one worker, a stale run cannot exist.

### The payment rule

`pay_claim` succeeds only when all of these are true:

1. The claim has an approve decision.
2. The amount equals the approved payout to the cent. This stops the agent recording $900 and paying $1,500.
3. The payout is within the limit, or a handler has signed off.
4. The claim has not been paid. `payments.claim_id` is a primary key, so a second payment is impossible at the database level and a claim cannot be paid in parts.

The checks and the payment run in one transaction, so two payments at the same moment give one success and one 409.

A decision can only be recorded while a claim is `in_progress`, so the agent cannot lower an approved payout after the fact to get under the limit. The limit is read from `company.json`, never hard-coded. Exactly $1,000.00 does not need a sign-off, because the rule says "over $1,000".

Signing off records the handler and makes the payment in one transaction, so a handler has one click and the claim cannot end up signed off but unpaid. The agent has no sign-off tool.

### API operations

Every operation has an `operation_id`, a one-line docstring and no optional inputs. For example, `record_decision` always takes a payout, which must be 0 for a decline or a referral.

| `operation_id` | Route | Used by |
|---|---|---|
| `health` | `GET /api/health` | Playwright |
| `list_claims` | `GET /api/claims` | Dashboard |
| `get_claim` | `GET /api/claims/{claim_id}` | Dashboard, agent |
| `get_policy` | `GET /api/policies/{policy_id}` | Dashboard, agent |
| `get_customer` | `GET /api/customers/{customer_id}` | Dashboard, agent |
| `get_policy_wording` | `GET /api/policy-wording` | Agent |
| `get_instructions` | `GET /api/instructions` | Dashboard, agent |
| `list_handlers` | `GET /api/handlers` | Dashboard |
| `start_claim` | `POST /api/claims/{claim_id}/start` | Agent |
| `record_decision` | `POST /api/claims/{claim_id}/decision` | Agent |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` | Agent |
| `sign_off_claim` | `POST /api/claims/{claim_id}/sign-off` | Dashboard |
| `record_step` | `POST /api/claims/{claim_id}/steps` | Agent |
| `list_steps` | `GET /api/claims/{claim_id}/steps` | Dashboard |
| `run_agent_on_claim` | `POST /api/claims/{claim_id}/agent-run` | Dashboard |
| `work_queue` | `POST /api/queue/agent-run` | Dashboard |

### How tests avoid the model

- pytest uses a stub model through the `llm` argument `run` already has.
- Playwright starts `backend/tests/e2e_app.py`: the real app and the real agent over real HTTP, with a stub model and a temporary database. No test flag goes into the production code.
- Playwright runs the backend on port 8001 and the dashboard on port 5174, with `reuseExistingServer: false`. Otherwise `npm run check` could attach to a running `npm run dev`, change the real data and spend money on the real model. On their own ports, the two can run side by side.

### Browser checks

`docs/PROCESS.md` names the Playwright MCP server, which is not connected in this session. The page checks below use `playwright-cli`, which drives the same Chromium through Playwright. This applies only to my own page checks. The repo's Playwright tests still run through `npm run e2e`, unchanged.

## Phase 1: Records and the read API

Builds `backend/db.py` and the read operations. This comes first because everything else depends on the records. The seed names each file it loads, so `data/evals/` and `data/security/` cannot get in by accident. `data/knowledge.json` is not in `data/README.md` and the spec does not ask for it, so it stays out too.

- [x] Starting the backend creates `undercover.db` and seeds it once. A restart keeps existing data and does not seed again.
- [x] `GET /api/claims` returns 25 claims, each with status `waiting` and with its customer's name, type, amount claimed and submitted date.
- [x] `GET /api/claims/CLM-1001` returns the full claim: story, 3 items and 4 documents, with `amount_claimed` of 420.0.
- [x] `GET /api/claims/CLM-9999` returns 404.
- [x] `GET /api/policies/POL-2001` returns plan `premium` with its limits, including a per-item limit of 300.0 and a deductible of 50.0.
- [x] `GET /api/customers/CUS-3001` returns Maya Patel and claim history with CLM-0412. A test asserts that email, phone, address and date of birth are absent.
- [x] `GET /api/policy-wording` returns text starting with `# UnderCover Travel Insurance: Policy Wording`.
- [x] `GET /api/handlers` returns 3 handlers.
- [x] `/openapi.json` shows every operation with an `operation_id`, a summary and no optional parameters. A test checks this and applies to every later phase.
- [x] The queue holds exactly the 25 ids in `data/claims.json`, and `GET /api/claims/CLM-1901` returns 404, so the security claim is out.
- [x] The seed's files are one explicit list, and a test asserts that list. Another test asserts that no API response carries the fields `data/README.md` names for the answer key: `difficulty`, `failure_class`, `tone`, `tiny`, `needs` and `over_approval_limit`.
- [x] `git grep -n "evals" backend agent` finds nothing.
- [x] `npm run check:python` passes with at least 80% coverage.

## Phase 2: Decisions, payment and sign-off

Builds the rule the spec cares about most, as backend code with no agent involved, so it is proven before anything can try to break it.

- [x] `start_claim` moves a `waiting` claim to `in_progress`, and returns 409 for any other status.
- [x] `record_decision` with a decline or a referral moves the claim to `decided`. A nonzero payout on either returns 422.
- [x] `record_decision` with an approve of $1,000.00 leaves the claim `in_progress`, and paying $1,000.00 moves it to `decided`.
- [x] `record_decision` with an approve of $1,000.01 moves the claim to `waiting_for_sign_off`.
- [x] `record_decision` with an approve of $0 moves the claim straight to `decided` with no payment.
- [x] `record_decision` on a claim that is not `in_progress` returns 409, so a $1,500 approval cannot be lowered to $900.
- [x] `pay_claim` without a sign-off on a $1,500 approval returns 403, the reason names the sign-off, and no payment row exists.
- [x] `pay_claim` with an amount other than the approved payout returns 409, and no payment row exists. This is tested with $900 against a $1,500 approval.
- [x] `pay_claim` a second time returns 409, and exactly one payment row exists.
- [x] `pay_claim` on a claim with no decision, or with a decline, returns 409.
- [x] Two `pay_claim` calls at the same moment on a real database file give one 200 and one 409, with one payment row. Two `sign_off_claim` calls at the same moment do the same.
- [x] `sign_off_claim` with a valid handler on a `waiting_for_sign_off` claim records the handler, makes the payment and moves the claim to `decided`.
- [x] `sign_off_claim` returns 404 for an unknown handler, 403 for a handler whose `can_approve_over_limit` is false, and 409 for a claim not waiting for sign-off.
- [x] `get_claim` includes the decision, the sign-off and the payment once they exist.
- [x] Changing the limit in the seed data changes where the block applies, which proves it is not hard-coded. This is covered by a test.
- [x] `npm run check:python` passes.

## Phase 3: The UnderCover Agent

Builds the instructions, the tools, the step log, the `run` entry point and the worker. The health-check tool is removed. `run` fetches its instructions from the API, then the agent reads the claim, policy, history and wording through its tools.

- [x] `backend/instructions.md` covers what to read, when to approve, decline or refer, how to work out the payout from section 10 of the wording, the two or three sentence reason and the policy section. It does not mention the claims manual.
- [x] The agent's tools are exactly `get_claim`, `get_policy`, `get_customer`, `get_policy_wording`, `record_decision` and `pay_claim`. A test asserts the list, which proves it has no sign-off tool.
- [x] A `4xx` from the API reaches the model as the tool's result, so the model can read why, and does not crash the run.
- [x] A stub-model test runs a claim to the end: it moves to `decided`, a payment exists and the steps are recorded in order.
- [x] A stub-model test scripts the agent to approve $1,500 and then try to pay anyway. The claim ends `waiting_for_sign_off`, no payment exists and the blocked attempt shows in the steps.
- [x] `record_decision` tells the agent the resulting status, so the instructions need no dollar limit.
- [x] `run_agent_on_claim` returns 202 for a `waiting` claim and 409 otherwise. `work_queue` starts every `waiting` claim and returns how many it started.
- [x] Runs happen one at a time, in claim order. This is tested with a stub runner.
- [x] A stub runner that records a $400 approval and then raises leaves the claim `waiting`. `get_claim` shows no decision and no payment, and the last step reads `The agent stopped before finishing:` followed by the error.
- [x] A stub-model run that ends with no decision, and one whose $400 approval is followed by a refused payment, both end the same way.
- [x] A run that fails after the claim reached `waiting_for_sign_off` or `decided` leaves the claim, its decision and its payment unchanged.
- [x] `model()` sets a 120 second request timeout, so a hung model call fails the run and does not hold up the queue.
- [x] A backend restart moves any `in_progress` claim back to `waiting` and clears its decision. This is tested with a claim set up that way before startup.
- [x] Real model, one claim, on a separate port and scratch database: `run("CLM-1001", "plan-check")` ends with CLM-1001 no longer `in_progress`, a decision with a two or three sentence reason and a policy section, and steps listed by `GET /api/claims/CLM-1001/steps`.
- [x] `npm run check:python` passes, with no test calling a model.

## Phase 4: The dashboard, reading

Builds the look and the three pages with live data but no actions, and sets up the Playwright test server. Layout and brand are checked here, before behavior is added on top.

- [x] Instrument Sans, Instrument Serif and JetBrains Mono load from Google Fonts. Claim ids and amounts use JetBrains Mono.
- [x] Light mode uses page `#F1F5F9` with white panels, and dark mode uses page `#0F172A` with `#1E293B` panels. Panels are rounded with no outline, and no panel has a border on one edge.
- [x] The queue page shows 25 rows with claim id, customer, type, amount, submitted date, status and decision.
- [x] Status chips use Royal Blue, Ice Blue, Silver Grey and Deep Blue with a text label, so status never relies on color alone. Ice Blue and Silver Grey are not used as fills in dark mode.
- [x] Money displays like `$1,250.00`, in a test.
- [x] Clicking a claim opens its page, and `#/claims/CLM-1001` opens it directly and survives a refresh.
- [x] The claim page shows the story, items, documents, policy, plan limits and claim history, then the decision, reason, policy section and payout once they exist.
- [x] The instructions page shows the text from the API with no editing controls.
- [x] Browser, both modes: open the queue, click CLM-1001, read the page, go to instructions and go back, with a screenshot of each and no console errors.
- [x] `backend/tests/e2e_app.py` and the Playwright config are in place, and `e2e/health.spec.ts` is replaced by a test of the same three pages.
- [x] TypeScript strict mode passes with no `any`, and `npm run check:ts` and `npm run e2e` pass.

## Phase 5: The dashboard, acting

Adds the handler's actions and the live view. These go in once the read pages are stable, since each one changes what those pages show.

- [x] A Run agent button appears on a `waiting` claim and starts the agent. It shows the claim has been queued and cannot be clicked twice.
- [x] A Work the queue button on the queue page starts every waiting claim and shows how many.
- [x] Steps appear on the claim page one by one while the agent works, with no refresh, in an `aria-live="polite"` region.
- [x] The queue updates its statuses with no refresh.
- [x] A claim `waiting_for_sign_off` shows a handler picker and a Sign off and pay button. After clicking, it shows the handler, the payment and `Decided`.
- [x] The sign-off controls appear on no other status.
- [x] A failed API call shows a plain message on the page, using the alert color.
- [x] Playwright with the stub model: run a claim, watch the steps arrive, and see `Decided` with a payment.
- [x] Playwright with the stub model: run a claim that approves over the limit and tries to pay, see `Waiting for sign-off` with no payment, sign off, and see `Decided` with the handler's name and the payment.
- [x] Browser: click through both of those journeys by hand and re-check the page after each click.
- [x] `npm run check:ts` and `npm run e2e` pass.

## Phase 6: The real thing

Smoke-checks the whole product on the real model, then finishes the documents. This shows the path works, not that the decisions are right.

- [x] Real model, through the dashboard, on separate ports and a scratch database: Run agent on CLM-1002 (baggage), CLM-1003 (emergency medical), CLM-1004 (baggage delay) and CLM-1008 (trip cancellation). For each one, steps appear live, the claim ends `Waiting for sign-off` or `Decided`, and the decision has a payout, a reason of two or three sentences and a policy section.
- [x] Any claim that approves over the limit shows `Waiting for sign-off` with no payment until a handler signs off in the browser. If none does, I report that, and the stub-model Playwright test from Phase 5 stands as the proof for that path.
- [x] Instructions are adjusted if those runs show a clear gap, such as a reason that runs past three sentences or a missing policy section.
- [x] The real-model checks leave `undercover.db` untouched, so the student starts with a clean queue of 25.
- [x] `docs/STATUS.md` says what is built, how to run it and how to reset the data: stop the backend, delete `undercover.db` and start it again.
- [x] `git grep -n "evals" backend agent` still finds nothing, and no secret is committed.
- [x] `npm run check` passes in full: ruff, pyright, pytest, ESLint, Prettier, tsc, vitest and Playwright.

## What this plan leaves open

- **Accuracy is not measured.** The goal is to match the handlers, but the answer key stays closed until we are asked to open it. Evaluations arrive on Week 2 Day 4. The checks here prove the product works, not that the decisions are right.
- **The agent will miss some claims.** `data/README.md` says some claims need the claims manual, which the spec leaves out for now.
- **Sign-off is on trust.** There is no sign-in, so the API cannot tell a handler from any other caller. Anyone at the screen can pick any handler's name, and anything that can reach the backend could record an approval and call `sign_off_claim`. The agent cannot, because it has no tool for it. The spec rules out sign-in for the pilot, and it arrives on Week 2 Day 5.
- **Referred claims end as `Decided`.** The spec gives four statuses and no handler screen for finishing a referral. The queue shows the decision, so handlers can pick these out.
- **A full queue run costs real money.** Phase 6 runs 4 claims. Running all 25 with Work the queue is the student's call.
