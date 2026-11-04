# Plan: the claims pilot

Builds `docs/SPEC.md` on the stack in `docs/TECH_STACK.md`, to `docs/CODE_STANDARDS.md` and `docs/PROCESS.md`, in the look of `docs/BRAND.md` (MonarchWare Claims). It starts from the hello-world skeleton in `docs/STATUS.md`.

## Decisions to review

- **Where claims live.** The backend creates SQLite tables at startup and seeds them from `data/` (claims, policies, customers, plans, handlers, company settings). It never reads `data/evals/` or `data/security/`. Reseeding is a command, so a demo can be reset.
- **Claim states.** `waiting` -> `in_progress` -> `awaiting_signoff` (approved over $1,000, not yet signed off) or `decided`. A claim that is approved at $1,000 or less, declined or referred goes straight to `decided`.
- **The payment block lives in the backend.** `pay_claim` takes the claim id and the amount and returns 409 unless the claim is approved, the amount equals the decided payout, and, over the $1,000 limit from `company.json`, a handler has signed off. The agent gets a pay tool, so the block is proven against an agent that tries to pay.
- **No optional inputs.** Every operation has an `operation_id`, a one-line docstring and required fields only (for example, `list_claims` takes a state, with `all` as a value instead of an omitted parameter).
- **The agent's instructions** are a file, `agent/instructions.md`. The backend serves it read-only at `GET /api/agent/instructions`, and the agent loads its own system prompt from that endpoint, so the dashboard and the agent always show the same text.
- **Policy wording** is served by the backend (`GET /api/policy-wording`) and read by the agent as a tool. The claims manual is not served, per the spec.
- **Steps.** Every tool call the agent makes is written to the backend as a step (tool, short input, short result, time) by a callback in the agent. The dashboard polls the steps while a claim is in progress.
- **Running the agent.** `POST /api/claims/{id}/run` starts the agent in a background thread, and `uv run -m agent.main CLM-1001` runs it from the terminal. Tests use a stub model and never call OpenRouter.
- **Sign-off** is a button on the claim that asks which handler is signing, from the three in `handlers.json`, and only a handler with `can_approve_over_limit` is accepted. There is no sign-in.
- **Scoring against `data/evals/` is not in the pilot.** The spec says the answer key checks the agent later. Nothing here opens it.

## Phase 1: Data and read API

Builds the database, the seed and the read operations, with tests. This comes first because every other phase needs claims to work on.

- `backend/db.py` (tables, connection), `backend/seed.py` (loads `data/*.json` except `evals/` and `security/`), `backend/models.py` (Pydantic models), `backend/main.py` routes.
- Operations: `list_claims`, `get_claim`, `get_policy`, `get_customer`, `get_plan`, `get_policy_wording`, `get_agent_instructions`, `list_handlers`.

Success criteria:

- [x] `uv run pytest -q` passes, with tests for the seed and each read route
- [x] A test fails if the seed code reads anything under `data/evals/` or `data/security/`
- [x] `GET /api/claims?state=all` returns 25 claims, each `waiting`
- [x] `GET /api/claims/CLM-1001` returns the story, the items and the documents
- [x] `GET /api/customers/CUS-3001` includes the claim history
- [x] `GET /openapi.json` shows an `operationId` and a summary on every operation, and no optional parameters
- [x] `uv run ruff check`, `uv run ruff format --check` and `pyright` are clean

## Phase 2: Decisions, payments and sign-off

Builds the writes and the payment block, the one rule the spec says the system must enforce itself.

- Operations: `start_claim`, `record_decision` (decision, payout, explanation, policy section), `pay_claim`, `sign_off_claim`, `log_step`, `list_steps`.
- The explanation must be filled in for every decision, and the payout is 0 unless the decision is approve.

Success criteria:

- [x] Tests cover the state changes: waiting, in progress, decided, and awaiting sign-off
- [x] Approving $1,250.00 leaves the claim `awaiting_signoff`, and `pay_claim` for $1,250.00 returns 409 with the reason
- [x] After `sign_off_claim` by HND-01, the same payment succeeds and the claim is `decided`
- [x] Sign-off by a handler without `can_approve_over_limit` returns 403, and an unknown handler returns 404
- [x] `pay_claim` with an amount different from the payout, or on a declined or referred claim, returns 409
- [x] A payout of $1,000.00 or less pays without sign-off
- [x] `curl` against a running backend shows the same 409 and 200 responses
- [x] Python checks are clean and coverage is at least 80%

## Phase 3: The UnderCover Agent

Replaces the hello-world agent with one that decides claims, using only the backend's API.

- `agent/instructions.md`: work from the policy wording alone, follow its waiting periods, limits, deductibles and exclusions, show the arithmetic of the payout in the explanation, cite the section, and refer when judgment or more information is needed. It tells the agent that over $1,000 the payment waits for a handler, and to ignore instructions written inside a claim's story.
- Tools (all HTTP calls to the backend): `get_claim`, `get_policy`, `get_customer`, `get_plan`, `get_policy_wording`, `record_decision`, `pay_claim`. A callback logs each call as a step.
- `run(claim_id, thread_id)` keeps its signature and marks the claim in progress first. Model from `MODEL_NAME`, default `openai/gpt-6-luna` at low effort.
- `POST /api/claims/{id}/run` and `uv run -m agent.main <claim_id>`.

Success criteria:

- [x] Tests with a stub model show the agent calls the tools in a valid order, records a decision, and logs a step for each call
- [x] A stub model that calls `pay_claim` on a $1,250.00 approval gets the 409 back and the claim stays `awaiting_signoff`
- [x] `grep -r "evals" agent backend` finds nothing outside the tests that prove it is never read
- [x] The instructions load from `GET /api/agent/instructions`, not from a path in the agent
- [x] With `OPENROUTER_API_KEY` set, `uv run -m agent.main CLM-1001` records a decision with an explanation and a section (a real run, checked by hand once)
- [x] `POST /api/claims/CLM-1001/run` returns at once and the claim moves to `in_progress` and then to a final state
- [x] Python checks are clean and coverage is at least 80%

## Phase 4: The dashboard

Builds the screens in `docs/BRAND.md` colors and fonts on the existing shell. TypeScript is strict with no `any`.

- **Queue**: a table of the 25 claims with id, customer, type, amount claimed and a colored state chip (waiting, in progress, awaiting sign-off, decided), filterable by state.
- **Claim**: the story, items and documents, the policy, and the agent's decision with payout, explanation and policy section. A Run agent button on waiting claims, and a Sign off button on claims awaiting sign-off.
- **Steps**: the agent's steps in order, refreshed every two seconds while the claim is in progress.
- **Instructions**: the agent's instructions, read only.
- Typed API client in `dashboard/src/api.ts`. Routing with React Router. Money shown as $1,250.00.

Success criteria:

- [x] Vitest tests cover each screen with a mocked `fetch`: queue, filter, claim, steps polling, instructions and sign-off
- [x] `tsc`, ESLint and Prettier are clean, and coverage is at least 80%
- [x] With `npm run dev`, the Playwright MCP shows the queue with 25 rows
- [x] Opening a claim shows its story and, for a decided claim, the explanation
- [x] The Instructions page shows the text and has no edit control
- [x] The sign-off button is missing on claims that are not awaiting sign-off

## Phase 5: End to end and the MonarchWare look

Proves the whole flow and checks the brand.

- Playwright tests start the app with a scripted agent (an environment switch makes the backend run a stub model instead of OpenRouter) and cover: run the agent on a claim and see its steps, a decision under $1,000, a decision over $1,000 that waits, and sign-off that releases the payment.
- Brand pass: light and dark modes use the BRAND.md surfaces, state chips use orange, marigold and sky and then blue and ember, headings are Barlow Condensed, numbers and ids are JetBrains Mono, panels have no outline, and there are no one-edge borders.

Success criteria:

- [x] `npm run e2e` passes for all four flows
- [x] The Playwright MCP screenshots of the queue and a claim look right in light and dark, with the MonarchWare header
- [x] No page has a border on one edge of a panel or a gradient fill
- [x] All labels are in plain US English with no exclamation marks

## Phase 6: Wrap-up

- [x] `docs/STATUS.md` describes what is built and how to run it, including how to reset the data and run the agent
- [x] A short `README.md` section on running the pilot, with no emojis
- [x] `npm run check` passes in full, and the results are reported
- [x] Every phase is committed through the pre-commit hook, with no `--no-verify` and nothing pushed

## Risks

- **Vitest timeouts on this machine.** After the MonarchWare branding change, vitest's default pool timed out at 60 seconds, and passed with `--pool=threads`. If `npm run check` does the same, I will stop and ask before touching the config, as `docs/PROCESS.md` requires.
- **Real model runs** cost a little on OpenRouter. Only the Phase 3 hand check uses a real model, on one claim.
