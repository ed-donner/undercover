# Status

The pilot and harness are implemented. The harness plan and verification evidence are in `docs/PLAN_HARNESS.md`; `docs/PLAN.md` remains the pilot's historical plan.

## Built

- FastAPI and SQLite with 25 seeded claims, policies, customers/history, plans, handlers, backend-owned instructions and allowlisted wording/manual sections. Additive migrations preserve existing decisions, sign-offs, payments and history. Money is stored as integer cents. Evaluation, held-out and security files are not loaded.
- One queue agent chooses claim order, persists its to-do list and delegates sequentially to fresh claim helpers. Whole-queue, distinct-claim caps and named-claim runs share backend ownership/cap guards. Retries consume the same cap slot. Only one top-level run is active.
- Each claim helper reads context and selected wording/manual sections through the API, records its decision/calculation/explanation and source provenance, then separately requests simulated payment. The default is `deepseek/deepseek-v4.1-flash` with low reasoning effort; `MODEL_NAME` overrides it.
- First pre-decision failure returns a claim to waiting for an automatic retry. Two failures persist a handler hold without a coverage decision; later runs cannot reset the budget. Committed decisions/payments are reconciled after ambiguous responses rather than duplicated. An unresolved payment is visible handler work, not a successful payment.
- Backend-enforced payment rules: approval required, exact approved amount, no duplicate payment, and handler sign-off above $1,000. An above-limit claim stays approved while payment waits. Agent payment calls are also fenced to an active attempt.
- Persisted runs, ordered task states, activity and exact source-read text/version/attempt. Model requests have a 60-second timeout and one transient middleware retry; helpers have an 80-step limit and an eight-minute write deadline. A 490-second delegation deadline fences late children. A failed supervisor gets one fresh invocation using recorded work. Completion is checked transactionally for missed claims within the cap.
- React dashboard with queue/capped/named starts, live tasks and summaries, claim evidence/decisions/activity/sources, separate read-only queue/claim instructions and a source library. Handler sign-off and simulated payment remain separate controls. Supports narrow screens, keyboard focus and system light/dark preference.

## Run locally

1. Use Python 3.12, uv and Node 26. Run `uv sync` and root `npm install`.
2. Add `OPENROUTER_API_KEY` to the existing `.env`; `.env.example` lists settings. A nonempty `MODEL_NAME` overrides the default. Starting a run makes paid model calls.
3. Run `npm run dev`. Dashboard: `http://localhost:5173`; API: `http://localhost:8000/docs`. Those ports must be available; do not start a second backend against the same database.
4. Use **Start capped run** with cap five for trials, **Start queue** for all eligible claims, or **Process claim** for one named claim. Review the run's to-do list and the claim's evidence/activity/sources. For above-limit approvals, select a handler, **Sign off payout**, then **Record simulated payment**.
5. From a second terminal: `uv run -m agent --max-claims 5`, `uv run -m agent`, or `uv run -m agent CLM-1001`. Multiple explicit claim IDs start separate named runs. Queue mode starts once and polls; it does not iterate claims in the CLI. Technical failures yield exit status 1; normal referrals and sign-off waits do not.
6. `uv run -m backend.seed` deletes the configured database and all its decisions, payments, task/run/activity history, then creates 25 waiting claims. Stop that database's backend first. For every live-model trial, reseed first and cap at five; use a dedicated `DATABASE_PATH` to preserve existing work.

The default git-ignored database is `undercover.db`; `DATABASE_PATH` changes it. `BACKEND_URL` changes the agent's API address. `VITE_BACKEND_URL` changes the dashboard development proxy when using another API port. One local backend process owns a database. On restart, interrupted runs are marked failed, undecided claims are released or held after their second failure, and committed financial records survive. Runs do not resume automatically.

## Verification

- `uv sync`, root `npm install` and hook/browser installation succeeded. `npm run dev` served a healthy API and dashboard using a separate database, a free `UVICORN_PORT` and Vite's next available port. The live preview also used isolated ports. Existing services and the developer database were not stopped or reseeded; temporary preview services were stopped afterward. Restarting the smoke database preserved its completed run without resuming any work.
- `npm run check` passes: ruff formatting/lint, pyright, 114 pytest tests (99.19% coverage), Prettier, ESLint, strict TypeScript, 26 Vitest tests (100% statement coverage) and 11 Playwright tests. `npx vite build dashboard` passes. No rules, thresholds or coverage scope were weakened.
- Automated tests use stub models and isolated databases, require no model key and make no provider calls. End-to-end tests use ports 8011/5174 and test-only reset/release/failure controls absent from production. They cover cap five, a missed task repaired before completion, fresh helpers, automatic retry, a two-failure hold, source reads, all decision outcomes, sign-off/payment enforcement and persistence after reload.
- Local Playwright inspection covered desktop and 390px narrow screens, light/dark, live and completed tasks, source text, both instruction sets, USD formatting and visible keyboard focus. Dark task-link contrast measured 9.68:1. No horizontal overflow or page errors were observed. Screenshots were inspected. A Playwright MCP server is not exposed, so the specific MCP criterion remains blocked, not marked verified.
- Live trial on a freshly reseeded, separate temporary database: `deepseek/deepseek-v4.1-flash`, low reasoning effort, cap five; run `a1164190-db88-494b-a1d8-14a8e75442c1` completed its check and processed five claims in five attempts with 76 source reads. It recorded five approvals, four simulated payments and one $3,750 approval waiting for sign-off, with zero technical issues. All other 20 claims remained waiting with no attempts. There were exactly five decision records and four payment records; a direct attempt to pay the unsigned above-limit approval returned `409`.
- The live dashboard showed tasks filling and progressing, recorded source sections and the completed summary after reload. All real calls were confined to this cap-five run. Workflow operation is verified; decisions were not scored against handler answers, and evaluation files were not opened.
- Each implementation phase is committed with the pre-commit hook. Nothing is pushed.

## Limits

- Local pilot only: no sign-in, authenticated handler identity, real money, customer messages, external document requests or automatic restart resumption. Technical holds are visible for review; no new handler adjudication/release workflow is included.
- `npm install` reports 21 existing dependency vulnerabilities: 15 moderate, four high and two critical. Dependency upgrades were not part of this build.
