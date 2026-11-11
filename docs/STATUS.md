# Status

The local claims pilot is implemented across all six phases of `docs/PLAN.md`.

## Built

- FastAPI and SQLite: 25 seeded claims, policies, plans, customers/history, handlers, policy wording and backend-owned agent instructions. The seed allowlist excludes evaluation files, held-out claims, the claims manual and manual-only company settings. Monetary values are stored as integer cents.
- Transactional decisions, handler sign-off and separate simulated payments. Payouts above $1,000 cannot be paid before sign-off, including through direct API calls. Payment must match the approved amount; duplicate payments and decision replacement are rejected.
- API-only LangChain agent: `run(claim_id, thread_id)` with four claim-scoped tools. It reads context and wording before deciding, records its calculation, short explanation and policy section references, then requests payment for an approval.
- Background runs with persistent, ordered activity summaries. No hidden reasoning, raw model messages, secrets or tool payloads enter activity history. Failed/interrupted undecided runs become retryable; committed decisions, sign-offs and payments survive failures. Runs are not automatically resumed after restart.
- React dashboard: searchable/filterable queue, all four states, full claim evidence and related records, decisions, live activity, read-only instructions/wording, sign-off and simulated payment controls. Supports narrow screens, keyboard navigation and system light/dark preference.

## Run locally

1. Use Python 3.12, uv and Node 26. Run `uv sync` and `npm install` at the repo root.
2. Add `OPENROUTER_API_KEY` to your existing `.env`; `.env.example` lists the settings. Optional `MODEL_NAME` overrides `openai/gpt-6-luna` (low reasoning by default). Processing a claim makes live model calls and may incur API costs.
3. Run `npm run dev`. Dashboard: `http://localhost:5173`; API reference: `http://localhost:8000/docs`.
4. Select a claim and choose **Process claim**. For above-limit approvals, choose a signing handler, **Sign off payout**, then **Record simulated payment**. All payments are simulated.

5. Optional, from a second terminal while `npm run dev` runs: `uv run -m agent` processes every waiting claim in queue order, one at a time; `uv run -m agent CLM-1001` processes the claims named. It starts runs through the backend (`POST /api/claims/{id}/runs`), polls until each finishes and prints a line such as `CLM-1001: approve, $420.00, paid`. It exits with status 1 if any claim failed or could not start, and says so if the backend is not running.

The git-ignored local database is `undercover.db`; optional `DATABASE_PATH` changes its location. One local backend process owns the database. Optional `BACKEND_URL` changes the agent's API address from `http://127.0.0.1:8000`.

## Verification

- `uv sync`, root `npm install`, hook installation and `npm run dev` succeeded on macOS.
- `npm run check` passed: ruff formatting/lint, pyright, 49 pytest tests with 100% coverage, Prettier, ESLint, strict TypeScript, 19 Vitest tests with 100% statement coverage, and seven Playwright tests.
- `npx vite build dashboard` passed. No coverage thresholds or check rules were lowered.
- Automated tests use scripted models and isolated databases, need no OpenRouter key and make no model-provider calls. End-to-end tests use a dedicated test-only server on port 8011, a temporary database reset between tests and Vite on port 5174. They do not reuse the development app or database. Test reset/release controls are absent from the production application.
- Browser checks covered desktop/mobile, light/dark, expanded evidence, activity, instructions, visible keyboard focus, sign-off/payment, direct API rejection and persistence after reload. Screenshots were visually inspected. Playwright MCP is not exposed in this session, so its specific plan criterion remains blocked; local Playwright/Chromium verification passed instead.
- Each implementation phase was committed with the pre-commit hook; nothing was pushed. Existing notebook edits were left untouched.

## Limits and follow-up

- Policy wording only. No sign-in, real payments or customer messages. Selecting a handler records attribution, not authenticated identity. This is a local pilot, not a production deployment.
- No live-model smoke run or evaluation against handler answers was performed. Workflow correctness is tested; decision accuracy has not been measured. Evaluation files were not opened.
- `npm install` reported 21 dependency vulnerabilities: 15 moderate, four high and two critical. Dependency upgrades were not applied as part of this pilot build.
