# UnderCover pilot plan

Build a local claims workflow from the seeded queue through a recorded decision and, where applicable, a simulated payment. Claims handlers will use the dashboard to follow a claim while the command-line agent works and sign off on approvals over $1,000.

During implementation, verify each phase's checklist, update `docs/STATUS.md`, and commit the phase before starting the next one. Run the applicable Ruff, ty, and runtime checks for phases that change Python.

## 1. Move the dashboard skeleton to Svelte

Port the existing health page to Svelte with Vite and strict TypeScript. Keeping the health page working gives us a small way to verify the new frontend toolchain and the FastAPI proxy before building claims screens. Update formatting, linting, component type checking, and Vitest for `.svelte` files while keeping checks for standalone TypeScript and the existing 80% coverage threshold. Define the dashboard's shared light and dark styles from [the brand guide](BRAND.md), including Ubuntu, Ubuntu Italic, JetBrains Mono, and the four reference colors. [Svelte TypeScript documentation](https://svelte.dev/docs/svelte/typescript)

- [x] `npm install` installs the Svelte dependencies, and `npm run check:ts` passes ESLint, Prettier, strict TypeScript checks for components and supporting files, and Vitest with at least 80% statement coverage.
- [x] `GET /api/health` returns `200` and `{"status":"ok"}`. With `npm run dev` running, open the dashboard in the browser and verify that it displays “Backend: up.” A component test verifies the down state, and `npm run e2e` passes the health check.

## 2. Seed SQLite and expose claims and reference data

Use SQLite so the backend is the source of truth for both the agent and the dashboard. Seed from an explicit list of files in `data/`. Preserve the order of the 25 rows in `claims.json` as the queue order and map the initial `open` status to Waiting. Join claims to their policy, plan and add-ons, and customer with previous claims. Load handler records and the payout limit for sign-off, and serve the full policy wording from the API. Exclude the evaluation files, security fixtures, claims manual, and manual-only settings from the pilot APIs and model inputs.

- [x] On a fresh database, `GET /api/claims` returns `200` with 25 Waiting claims in seed order, from `CLM-1001` through `CLM-1025`. Restarting against the same database preserves order and does not duplicate rows or reset changes.
- [x] `GET /api/claims/CLM-1001` returns `200` with the Rome incident, $420.00 claimed, the original document text, and the associated policy, plan, and customer history. An unknown claim ID returns `404`.
- [x] `GET /api/policy-wording` returns `200` with the contract and its section headings. API tests verify the intended data fields, that seed code reads only the approved inputs, and that no route serves evaluation or manual data.
- [x] API contract tests verify that all operations have unique `operation_id` values, one-line docstrings, and required inputs.

## 3. Enforce decisions, sign-off, and simulated payments in the API

Keep the decision outcome separate from the queue status and payment record. Starting a claim moves it from Waiting to In progress. A decline, referral, or approval at or below $1,000 moves it to Decided. An approval over $1,000 moves it to Waiting for sign-off until an eligible seeded handler signs off. Record the reason, policy citation, and approved amount with the decision. Keep payments behind a separate API operation with a required amount in integer US cents. Check the stored decision, payout amount, and sign-off in SQLite before recording a payment. Use transactions for state changes and a unique payment per claim so concurrent requests and retries are safe.

- [x] Exercise `POST /api/claims/{claim_id}/start` and `POST /api/claims/{claim_id}/decision` with fixtures. A repeated start returns `409`, an invalid decision body returns `422`, and an in-progress claim can finish with each of the three decision outcomes. An approval over the limit retains the Approve outcome while waiting for sign-off.
- [x] `POST /api/claims/{claim_id}/pay` accepts an approved payout of exactly `100000` cents without sign-off. An approval of `100001` cents returns `409` before sign-off and leaves no payment row. After a valid `POST /api/claims/{claim_id}/sign-off`, the same payment request succeeds and records exactly one simulated payment.
- [x] Tests reject payment for declined or referred claims, an amount that differs from the approved amount, and sign-off by an unknown or ineligible handler. Repeating a successful payment returns the existing record, including when duplicate requests arrive together.

## 4. Run the UnderCover Agent from the command line

Keep `run(claim_id, thread_id)` as the single-claim entry point. Fetch claim context, policy wording, and the exact system instructions through the backend. Use LangChain `create_agent` on OpenRouter with `openai/gpt-6-luna` and low reasoning effort by default, or the chosen `MODEL_NAME`. Give the model a structured decision to return, with the outcome, payout for an approval, relevant policy section, and a two- or three-sentence explanation. Have the runner submit the validated decision and request the payment when it is eligible. Keep these writes in the runner so a model reply cannot bypass the backend's workflow. Persist timestamped progress as each step happens, using short activity labels such as “Read policy wording” and “Recorded decision.” [LangChain structured output documentation](https://docs.langchain.com/oss/python/langchain/structured-output)

- [x] Stub-model tests verify the claim, supporting documents, policy, customer history, and wording reach the agent. The API records the stub's structured outcome, payout, explanation, and policy citation. `GET /api/agent/instructions` returns the exact system instructions used by the runner.
- [x] With an injected stub, the no-argument CLI processes Waiting claims in API queue order, and the CLI with `CLM-1001` processes just that claim. An unknown ID produces a clear error, and a completed claim is not decided again.
- [x] Verify that `GET /api/claims/{claim_id}/activity` shows new steps in order while a stub run is still active. It contains application activity labels and timestamps. A handled model failure before a decision leaves the claim available for retry, while a payment failure after an approval leaves the decision intact so payment can be retried separately.
- [x] Unit tests verify `OPENROUTER_API_KEY`, the default model and low effort, and a `MODEL_NAME` override such as `openrouter/free` through model construction with test values. All automated tests use a stub model.

## 5. Build the handler dashboard

Build the queue, a claim detail view, and a read-only instructions view in Svelte. Use a short polling interval for queue status and the visible claim's activity so the independent CLI can update the browser through the API. In the detail view, show the full claim and documents, the decision and cited policy section, payment state, and the activity timeline. For an approval waiting for sign-off, let the handler select their name from eligible seeded records. Submit sign-off and request simulated payment through their separate operations. If payment fails after sign-off, keep the sign-off visible and allow payment to be retried without another sign-off.

- [x] Open the queue and `CLM-1001` in the browser. The queue shows all four status labels as claims move through the workflow. Claim detail shows the original story, itemized costs, document text, policy and history, plus the decision and reason when available. Amounts display in US dollars, including `$420.00`.
- [x] With a paused stub run, the browser displays In progress and an early activity step. On resuming it, the detail view adds the decision and the queue updates without reloading the page. The instructions view shows the backend prompt as read-only text.
- [x] In the browser, sign off on an over-limit approval and verify that it becomes Decided with one simulated payment. Component tests cover loading and API errors, a failed payment after sign-off, and a successful retry.
- [x] Inspect the queue and claim detail at desktop and narrow widths in light and dark mode with Playwright. Verify Ubuntu loads, the interface uses the [brand palette](BRAND.md), status remains readable as text, and keyboard navigation reaches the claim and sign-off controls.

## 6. Verify the workflow and document how to run it

Run the full workflow using a disposable SQLite database and stub models so tests are repeatable and leave the local pilot queue intact. Add startup, configuration, database location, and usage instructions to `docs/STATUS.md`. Document `uv run -m agent` for the waiting queue and `uv run -m agent CLM-1001` for one claim, including the need for a running backend and an OpenRouter key for real runs.

- [x] Playwright covers a standard approval and an over-limit approval. Verify a direct pre-sign-off payment attempt fails, the handler can sign off in the browser, and the recorded payout matches the approved amount. Use the Playwright MCP server for visual inspection when available, or the repository's Playwright runner with Chromium.
- [x] `npm run check` passes Ruff formatting and lint, ty over the first-party Python packages and tests, pytest with at least 80% coverage, the frontend checks, and Playwright. Record the result in `docs/STATUS.md`.
- [x] Follow the documented startup steps against a fresh database and verify the 25-claim queue appears. Verify both CLI forms in the automated suite and report the final check results.
