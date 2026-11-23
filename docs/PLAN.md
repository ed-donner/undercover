# Plan: the claims pilot

Source brief: `docs/SPEC.md`. This plan builds the pilot in six phases: the backend with its data, the claim rules, the agent, a way to run it, the dashboard, and the end-to-end checks. Each phase ends with something you can run and check.

## Approach

Choices I made where the spec leaves room. Change any of them before we build.

**One place for the rules.** The backend owns every rule, so the dashboard and the agent can't disagree about them. The $1,000 limit is read from `data/company.json` (`payout_approval_limit`), not written into the code. The block on payments over the limit sits inside the one operation that pays, so no route to payment avoids it, whatever the agent sends.

**The agent works only through the API.** Its tools are thin wrappers over backend operations. Its system prompt is fetched from the backend at the start of each run. The dashboard shows the same text, read only, so what the team sees is what the agent got.

**What the agent can see.** One operation returns the claim, its policy, the plan's limits and the customer's claim history. It leaves out contact details and date of birth, which the decision doesn't need. A second operation returns the policy wording. The agent gets no claims manual (the spec rules it out for the pilot), no `knowledge.json`, and nothing from `data/evals/` or `data/security/`. The loader names the files it reads, so a test can prove it never opens those folders.

**State is derived, not stored.** The database holds facts (a run started, a decision recorded, a payment made, a sign-off given) and the state comes from them:
- waiting: no run has started
- in progress: a run has started and there's no decision yet
- waiting for sign-off: an approve over the limit, not yet signed off
- decided: everything else with a decision, including declines and referrals

The seed `status: "open"` on every claim is ignored. Referrals count as decided, because the agent has finished with them. Say if you'd rather they stand apart.

**Sign-off is by a named handler.** There's no sign-in, so the dashboard asks which of the three handlers is signing off. The backend checks that handler's `can_approve_over_limit` flag in `handlers.json` and records who signed.

**Storage.** SQLite through the standard library's `sqlite3`, in `backend/undercover.db`, which `.gitignore` already covers. Built from `data/` on first start, with a reset command. Money is whole cents inside, dollars at the API, so "over $1,000" is an exact comparison.

**Steps while it works.** The agent runs with LangChain's streaming and posts each tool call, tool result and final message to the backend as it happens. The dashboard polls. This gives live progress without websockets.

**Running it.** A dashboard button asks the backend to start the agent on one claim or on the whole queue. The backend runs it in a background thread, one run at a time, which keeps model rate limits simple.

**Not built, to stay inside the spec:** sign-in, real payments, customer messages, the claims manual, a deterministic payout calculator (the agent works out the payout from the wording; the harness comes on Week 1 Day 5), and scoring against `data/evals/` (see the open questions).

## Phase 1: Backend data and read operations

Builds the database, the loader and the read operations.

- `backend/db.py`: schema and connection. `backend/seed.py`: loads `company`, `plans`, `policies`, `customers`, `handlers`, `claims` and `policy_wording.md` from an explicit list of files.
- Operations, all with an `operation_id`, a one-line docstring and required inputs only: `list_claims`, `get_claim`, `get_claim_context`, `get_policy_wording`, `list_handlers`.
- `npm run reset` runs a `uv run` command that deletes the database and rebuilds it.

Success criteria:
- [x] `uv run pytest -q` passes. Tests use a temporary database and a stub-free TestClient.
- [x] A test asserts the seed loads 25 claims, 50 policies, 49 customers, 3 handlers and 3 plans.
- [x] A test asserts the seed's file list contains nothing under `data/evals/` or `data/security/`, and that `claims_manual.md` and `knowledge.json` are not loaded.
- [x] `curl localhost:8000/api/claims` returns 25 claims, all `"state": "waiting"`.
- [x] `curl localhost:8000/api/claims/CLM-1001/context` returns the claim, policy, plan limits and previous claims, and contains no `email`, `phone` or `date_of_birth`.
- [x] `curl localhost:8000/api/policy-wording` starts with `# UnderCover Travel Insurance: Policy Wording`.
- [x] `curl localhost:8000/openapi.json`: every operation has an `operation_id` and no optional parameter or body field.
- [x] `npm run reset` followed by a restart gives the same 25 waiting claims.
- [x] `npm run check:python` passes.

## Phase 2: Decisions, payments and the $1,000 rule

Builds the write side, with the limit enforced in the backend.

- `record_decision(claim_id, decision, payout, explanation, policy_section)`: `decision` is an enum of `approve`, `decline`, `refer`. An approve needs a payout above zero; a decline or refer needs zero. A claim can be decided once.
- `pay_claim(claim_id, amount)`: only for an approved claim, and only for the approved payout. Refused with a clear message when the amount is over the limit and nobody has signed off.
- `sign_off_claim(claim_id, handler_id)`: refused unless the handler's `can_approve_over_limit` is true. A successful sign-off records the payment.
- `record_step(claim_id, kind, text)` and `list_steps(claim_id)`.
- `get_claim` now includes the decision, payment, sign-off and state. `list_claims` now includes each claim's decision and payout, empty until the claim is decided.

Success criteria:
- [x] Test: approve $1,000.00, `pay_claim` for $1,000.00 succeeds with no sign-off (the limit is "over $1,000").
- [x] Test: approve $1,000.01, `pay_claim` is refused (HTTP 409), no payment exists, and the state is `waiting for sign-off`.
- [x] Test: `pay_claim` with an amount different from the approved payout is refused.
- [x] Test: paying a declined, referred or undecided claim is refused.
- [x] Test: `sign_off_claim` with HND-01 on a $1,500.00 approve records a payment of $1,500.00, and the state becomes `decided`.
- [x] Test: sign-off with an unknown handler is refused, and sign-off on a claim under the limit is refused.
- [x] Test: a payment cannot be made twice.
- [x] Test: a decline with a payout above zero and an approve with a payout of zero are both refused.
- [x] Live check with `curl`: record an approve of $1,500.00 on CLM-1001, `POST .../payment` returns 409 and `GET` shows no payment; sign-off returns 200 and `GET` shows the payment.
- [x] `npm run check:python` passes with coverage at or above 80%.

## Phase 3: The agent

Builds the UnderCover Agent in `agent/`, keeping `run(claim_id, thread_id, llm=None)`.

- Backend: `backend/instructions.md` (the agent's instructions) and `get_instructions`. The instructions tell it to work only from the policy and the wording, to follow the wording over the story, to approve, decline or refer (refer when judgment or more information is needed), to explain in two or three sentences naming the section, and to pay only after it has recorded an approval.
- Agent tools: `get_claim_context`, `get_policy_wording`, `record_decision`, `pay_claim`. Each surfaces backend refusals to the model as text, so the agent can see that a payment is waiting for sign-off.
- `run` fetches the instructions, streams the agent, and calls `record_step` for each tool call, tool result and final message. The health tool from the skeleton goes.
- `model()` is unchanged: `openai/gpt-6-luna` with low reasoning, or `MODEL_NAME` if set.

Success criteria:
- [x] Test: a stub model scripted to read the context, read the wording, record an approve for $420.00 and pay it leaves the claim decided with a payment of $420.00.
- [x] Test: a stub model that approves $1,500.00 and tries to pay leaves the claim `waiting for sign-off` with no payment, and the refusal text appears in the steps.
- [x] Test: the system prompt passed to the model equals the text from `get_instructions`.
- [x] Test: steps are recorded in order, one per tool call and result plus the final message.
- [x] Test: the agent package makes no request except to the backend, and no file under `data/` is read by `agent/`. Check with a grep in the test.
- [x] Existing `model()` tests still pass.
- [x] `curl localhost:8000/api/instructions` returns the instructions.
- [x] `npm run check:python` passes.

## Phase 4: Running the agent from the backend

Builds the way to start the agent, and the "in progress" state.

- `start_claim_run(claim_id)`, `start_queue_run()` and `get_run_status()`. A run is a background thread calling `agent.main.run` with a new thread id.
- One run at a time. A second start returns 409. A claim that already has a decision can't be run again.
- On start the backend records the run, so the claim is `in progress` until a decision is recorded. A run that ends without a decision records a final step that says so, and the claim returns to `waiting` rather than staying stuck in progress.
- Tests inject the stub model through a single backend setting, not an environment variable, so production code has no test switch.

Success criteria:
- [x] Test: with a stub model, the claim is `in progress` during the run and `decided` after it.
- [x] Test: starting a second run during a run returns 409; starting a run on a decided claim returns 409.
- [x] Test: a queue run over three waiting claims decides them one after another, never two at once.
- [x] Test: a run whose model fails ends with a recorded step, and the claim returns to `waiting`.
- [x] `curl -X POST localhost:8000/api/claims/CLM-1002/run` returns 202. Polling `curl .../api/claims/CLM-1002` shows steps appearing. With no `OPENROUTER_API_KEY` the failure shows as a step.
- [x] `npm run check:python` passes.

## Phase 5: The dashboard

Builds the screens in React, TypeScript strict, styled to `docs/BRAND.md`. Hash routes, no router library.

- **Queue** (`#/`): table of claims with id, customer, claim type, amount claimed, a state badge, the agent's decision and its payout. A claim with no decision shows a dash in both new columns. Buttons: run the queue. Refreshes every two seconds while a run is active.
- **Claim** (`#/claims/CLM-1001`): the story, items, documents, the policy, the customer's earlier claims. The agent's decision, payout, explanation and policy section. The payment: paid, or waiting for sign-off with a handler picker and a sign-off button. The steps, live. A run button.
- **Instructions** (`#/instructions`): the agent's instructions, read only.
- States use the brand's colors: Cerulean for waiting, Coral for in progress, Marigold for waiting for sign-off and Sea Green for decided, with the specified text colors. Raspberry marks a refused payment. Light and dark modes. Instrument Sans, JetBrains Mono for ids and amounts. Money as `$1,250.00`. No borders on one edge, no thin lines across the top.
- The API calls live in one small typed module, so components stay simple and tests can fake it.

Success criteria:
- [x] `npm run check:ts` passes: ESLint, Prettier, tsc strict with no `any`, vitest at or above 80% coverage.
- [x] vitest: the queue shows every claim with its state badge and formats amounts as dollars.
- [x] vitest: the queue shows each claim's decision and payout, and a dash for both when there is no decision yet.
- [x] Playwright: after a decision is recorded through the API, the claim's queue row shows the decision and the payout.
- [x] vitest: a decided claim shows decision, payout, explanation and policy section; an approve over the limit shows the sign-off control and the picker lists the three handlers.
- [x] vitest: the instructions page shows text and has no input or textarea.
- [x] Playwright MCP browser at `http://localhost:5173/#/`: the queue shows 25 rows. Screenshot in light and dark mode and compare with the brand (page `#F0F4F5` or `#04232E`, panels white or black, rounded, no outlines).
- [x] Playwright MCP browser: open CLM-1001, record a decision through the API, and the page shows it within three seconds.
- [x] Playwright MCP browser: `#/instructions` has no way to edit the text.
- [x] A grep of `dashboard/src` finds no customer email or phone field.

## Phase 6: End-to-end checks, status and a live run

Builds the Playwright tests, `docs/STATUS.md` and one live run.

End-to-end tests (no model calls; they set up state through the API, which Phase 2 makes possible):
- The queue loads 25 claims.
- A claim with a recorded decision shows the decision, reasons and payout.
- A $1,500.00 approval shows "waiting for sign-off"; signing off as a handler turns it to decided and shows the payment.
- A $1,000.00 approval pays without sign-off.
- The instructions page loads with no edit control.

The end-to-end tests reset the database before each test through the reset command.

Live run, which I will ask you about first because it uses your OpenRouter key: with `MODEL_NAME` unset, start the queue run and let it finish. I'll report each claim's decision and payout, which payments were blocked, any claim stuck or failed, and the cost if OpenRouter reports it. I won't compare against `data/evals/`.

Success criteria:
- [x] `npx playwright test` passes the five tests above.
- [x] `npm run check` passes: Python, TypeScript and Playwright.
- [x] `docs/STATUS.md` says what's built, how to run it, how to reset it and how to run the queue.
- [x] The run instructions are in `docs/STATUS.md`. The root `README.md` is the course's, so I left it alone.
- [x] Live run (once you approve): no claim is left in progress; every approve over $1,000.00 is `waiting for sign-off` with no payment recorded; every other approve has a payment equal to its payout.
- [x] Every `package.json` script is a `uv run` command or an `.mjs` file, and paths in Python use `pathlib`.

## Open questions

1. Referrals count as decided here. Do you want them in their own state, or under waiting for sign-off?
2. Should I score the agent against `data/evals/decisions.json` after the live run? The docs say not to open that folder unless you ask, so the plan doesn't.
3. The Playwright MCP server isn't among my tools in this session. If it isn't there when we build, I'll do the Phase 5 browser checks with Playwright tests and screenshots and say so.
