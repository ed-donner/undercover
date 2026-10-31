# Plan: the claims pilot

This plan builds the pilot described in `docs/SPEC.md` on the skeleton in `docs/STATUS.md`. It follows `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`.

## Decisions to review

1. **Claim state is derived from facts the backend stores.** A claim is `waiting` until the agent starts, `in_progress` while it works, `awaiting_sign_off` when it approved a payout over the $1,000 limit that no handler has signed off, and `decided` otherwise. Storing the facts (decision, payout, sign-off, payment) and computing the state avoids states that disagree with the data.
2. **The payment block lives in the backend.** `pay_claim` checks the stored decision and sign-off itself, so it holds even if the agent calls it directly or the agent's prompt is ignored. The limit comes from `data/company.json`, not a hard-coded number.
3. **The agent decides and the backend enforces.** The agent records its decision (`approve`, `decline`, `refer`, payout, explanation, policy section) through the API. It pays under the limit itself, and a payout over the limit waits for a handler.
4. **The agent's instructions live in the backend** (`backend/instructions.md`, served read only at `GET /api/instructions`). The agent loads its system prompt from that route at the start of every run, and the dashboard shows the same text. One source, so what the team reads is what the agent uses.
5. **Steps are recorded by a callback on the agent's tool calls**, not by the model, so the log is complete and cannot be skipped. Each step is a short line, such as "Read the policy POL-2001".
6. **Running the agent**: from the dashboard (a "Run agent" button on a waiting claim, which starts it in the background) and from the command line (`uv run -m agent.main CLAIM_ID`). Tests use a stub model and never call a live one.
7. **Seed data**: the backend loads `claims`, `policies`, `customers`, `plans`, `handlers`, `company` and the policy wording from `data/` into SQLite on first start. It never reads `data/evals/`, and the agent has no tool that could reach those files. The claims manual, `knowledge.json` and `data/security/` are out of scope for the pilot (the spec says the agent works from the wording alone). The database file is git-ignored and `npm run dev` recreates it when missing.
8. **No optional inputs.** Every API operation has an `operation_id`, a one-line docstring and only required parameters, so lists are unfiltered and the dashboard filters in the browser.

## API (planned)

| operation_id | Route | Purpose |
|---|---|---|
| `health` | `GET /api/health` | Existing |
| `list_claims` | `GET /api/claims` | The queue with each claim's state |
| `get_claim` | `GET /api/claims/{claim_id}` | One claim in full, with decision, payment and sign-off |
| `get_policy` | `GET /api/policies/{policy_id}` | A policy |
| `get_plan` | `GET /api/plans/{plan}` | A plan's limits |
| `get_customer` | `GET /api/customers/{customer_id}` | Contact details and claim history |
| `get_policy_wording` | `GET /api/policy-wording` | The wording text |
| `get_instructions` | `GET /api/instructions` | The agent's instructions |
| `start_claim` | `POST /api/claims/{claim_id}/start` | Mark in progress |
| `add_step` | `POST /api/claims/{claim_id}/steps` | Log a step |
| `record_decision` | `POST /api/claims/{claim_id}/decision` | Decision, payout, explanation, policy section |
| `sign_off_claim` | `POST /api/claims/{claim_id}/sign-off` | A handler signs off (takes `handler_id`) |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` | Pay an amount; blocked until sign-off when over the limit |
| `run_agent` | `POST /api/claims/{claim_id}/run` | Start the agent in the background |

## Phase 1: Backend data and read API

Build the SQLite database (SQLAlchemy is not needed; use the standard `sqlite3` module), the seed loader and the read-only routes: claims, policies, plans, customers, handlers, policy wording, instructions. Derived claim state and the claim history appear in the responses. A first draft of `backend/instructions.md` is included.

Success criteria:

- [x] `uv run pytest -q backend` passes, with tests for the seed loader, each read route and the derived state, using a temporary database
- [x] After seeding, the database holds 25 claims, 50 policies, 49 customers, 3 plans and 3 handlers (a test asserts these counts)
- [x] `GET /api/claims` returns 25 claims, all `waiting`
- [x] `GET /api/claims/CLM-1001` returns the story, items, documents and no decision yet
- [x] A test proves no code path in `backend/` or `agent/` opens `data/evals/` (a grep in the test over the sources)
- [x] Every operation in `/openapi.json` has an `operation_id`, a one-line docstring and no optional parameters (a test checks all three)
- [x] `uv run ruff format --check`, `uv run ruff check` and `pyright` are clean

## Phase 2: Backend write API and the payment rule

Add `start_claim`, `add_step`, `record_decision`, `sign_off_claim` and `pay_claim`, with the state rules.

- `record_decision` accepts `approve`, `decline` or `refer`. A payout is required on approve and must be zero otherwise.
- `pay_claim` takes the amount and refuses unless the claim is approved, the amount equals the approved payout and, over the limit, a handler has signed off. It refuses a second payment.
- `sign_off_claim` accepts only a handler with `can_approve_over_limit`, and only on an approved claim over the limit.

Success criteria:

- [x] Tests cover every state transition: waiting, in progress, awaiting sign-off, decided
- [x] A test approves a $1,250 payout and calls `pay_claim`: the response is a 409 and no payment is stored
- [x] The same claim after `sign_off_claim` by `HND-01`: `pay_claim` for $1,250 succeeds and the claim is `decided`
- [x] `pay_claim` refuses a wrong amount, a declined or referred claim, an unknown claim and a second payment
- [x] A payout of exactly $1,000.00 is paid without sign-off; $1,000.01 is not (boundary test)
- [x] Sign-off by an unknown handler is refused
- [x] With the server running, `curl` against a fresh claim shows the whole flow and the responses match the tests
- [x] Format, lint, pyright clean; backend coverage at least 80%

## Phase 3: The agent

Replace the hello-world agent with the UnderCover Agent.

- Tools, each a thin call to one API operation: `get_claim`, `get_policy`, `get_plan`, `get_customer`, `get_policy_wording`, `record_decision`, `pay_claim`.
- `run(claim_id, thread_id, llm=None)` fetches the instructions from the backend, calls `start_claim`, runs the agent and returns the final reply. A callback logs each tool call with `add_step`.
- Instructions (`backend/instructions.md`) cover: read the claim, policy, customer history and wording; decide only from the wording; work out the payout step by step (limits, waiting periods, per-item limits, deductible); refer when judgment or more information is needed; write a two or three sentence explanation with the policy section; pay only when the payout is at or under the limit.
- CLI: `uv run -m agent.main CLAIM_ID`.
- Model stays `openai/gpt-6-luna` at low reasoning effort, or `MODEL_NAME`.

Success criteria:

- [x] Agent tests use a stub chat model that scripts tool calls and make no network call to a model
- [x] Test: a stub run on a small claim records an approve decision, pays it and the claim ends `decided` with steps logged
- [x] Test: a stub run that approves over $1,000 and tries to pay gets the backend's 409 back as a tool error, and the claim ends `awaiting_sign_off`
- [x] Test: a stub run that declines and one that refers record the right decision and no payment
- [x] Test: no agent tool reads files under `data/` and none touches `data/evals/`
- [x] Test: the instructions the agent uses are exactly the text from `GET /api/instructions`
- [x] With a real key, `uv run -m agent.main CLAIM_ID` on one claim finishes and the backend shows a decision, an explanation and logged steps (run once by hand and report the output)
- [x] Format, lint, pyright clean; agent coverage at least 80%

## Phase 4: Dashboard queue and claim page

React, Vite and TypeScript in strict mode with no `any`, styled to `docs/BRAND.md` (Instrument Sans, Instrument Serif for the tagline, JetBrains Mono for ids and numbers; Graphite, Slate, Silver, Steel and Brick; light and dark surfaces; rounded panels without outlines; no one-edge borders).

- **Queue**: a table of claims with id, customer, type, amount claimed and state, plus counts per state. States use Graphite, Slate, Silver and Steel; Brick marks claims awaiting sign-off.
- **Claim page**: the story, items, documents, the policy and customer history, and the agent's decision with payout, explanation and policy section.
- A typed API client in one module; hash routing, no router library.

Success criteria:

- [x] `vitest` tests cover the queue, the claim page, state labels and money formatting ($1,250.00), with API calls mocked
- [x] `npm run check:ts` is clean (Prettier, ESLint, tsc, vitest with 80% coverage)
- [x] Playwright MCP, light mode: the queue shows 25 claims, state counts add up to 25, and a screenshot matches the brand (fonts load, no outlines, no gradients)
- [x] Playwright MCP, dark mode: page background `#18191B`, panels `#0B0B0C` (checked with computed styles)
- [x] Playwright MCP: clicking CLM-1001 opens its page with the story and documents
- [x] Playwright MCP at 390px wide: no horizontal scroll

## Phase 5: Live progress, agent control and instructions

- **Steps**: the claim page shows the steps log and refreshes every two seconds while the claim is `in_progress`.
- **Run agent**: a button on a waiting claim calls `run_agent`; the claim moves to in progress and then to its final state.
- **Sign-off**: on an `awaiting_sign_off` claim, a handler picker and a "Sign off and pay" button. The button signs off and pays the approved amount.
- **Instructions page**: the agent's instructions shown read only, with no edit control.

Success criteria:

- [x] `vitest` tests cover polling start and stop, the run button, the sign-off flow and the instructions page
- [x] Playwright MCP: the instructions page shows the text from `GET /api/instructions` and has no input or textarea
- [x] Playwright MCP with a stub model (the backend started with a test flag that swaps in the stub): Run agent on a waiting claim shows steps appearing, then a decision
- [x] Playwright MCP: a claim over $1,000 shows `awaiting_sign_off` in Brick, and after sign-off shows `decided` with the payment
- [x] No console errors on any page (checked with the Playwright MCP console messages)
- [x] `npm run check:ts` clean

## Phase 6: End-to-end tests, docs and final check

- Playwright tests in `e2e/` run against a backend with a temporary database and the stub model: queue, claim detail, run agent, over-limit sign-off, instructions.
- `npm run dev` starts both servers; the database is created on first start.
- Update `docs/STATUS.md` (what is built and how to run it), add a short `README.md` section if needed, and `.gitignore` the database.

Success criteria:

- [x] `npm run e2e` passes, covering the five flows above
- [x] `npm run check` passes from a clean checkout state (`uv sync`, `npm install`)
- [x] `docs/STATUS.md` lists what is built, the API, how to run the stack and how to run the agent on a claim
- [x] `git status` shows no database file, no `.env` and nothing from `data/evals/` was changed
- [x] All phases ticked in this file and each phase committed (hook passing, no `--no-verify`)

## Out of scope for the pilot

The claims manual, sign-in, real payments, messages to customers, checking the agent against `data/evals/` (a later step; the agent must not see those files), `knowledge.json` and `data/security/`.

## Open questions for you

- Should the "Run agent" button be in the pilot dashboard, or should running stay a command-line action? The plan includes the button because the spec asks the team to watch the agent work.
- A sign-off currently pays the claim in the same click. Say if you want sign-off and payment as two separate steps.
