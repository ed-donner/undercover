# Status

## Pilot progress

Phases 1–5 built: SQLite records and typed APIs, transactional financial rules, an API-only LangChain claim agent, background execution with persisted activity and the handler dashboard. Seed imports use an explicit allowlist; evaluation records and the claims manual remain excluded. Monetary fields are stored as integer cents.

The backend blocks payouts above $1,000 until sign-off, validates exact approved amounts and prevents duplicate payments. Starting a claim returns immediately while its agent runs in a worker thread. Run history and allowlisted activity summaries are persisted; neither raw model reasoning nor tool payloads are recorded. Interrupted/failed undecided claims can be retried; committed decisions and payments survive failures.

- Local storage: `undercover.db` (git-ignored); override with `DATABASE_PATH`.
- Install: `uv sync` and root `npm install`.
- Run: `npm run dev` (API at `http://localhost:8000`, dashboard at `http://localhost:5173`). API reference: `/docs`.
- Agent: `run(claim_id, thread_id)` uses backend instructions and four claim-scoped tools. It must read context and wording before deciding. Configure `OPENROUTER_API_KEY` in `.env`; optional `MODEL_NAME` overrides `openai/gpt-6-luna` (low reasoning). Optional `BACKEND_URL` overrides `http://127.0.0.1:8000`.
- Verified: `npm run check:python`, 47 tests, 100% coverage, scripted models only.
- Dashboard: searchable/filterable queue, full evidence and related records, agent decisions and activity, read-only instructions/wording, handler sign-off and separate simulated payment. Supports narrow screens and system light/dark preference.
- Verified: `npm run check:ts`, 19 UI tests, 100% statement coverage. Local Playwright browser inspection passed at desktop/mobile sizes, including sign-off, payment and direct API bypass rejection. The specifically requested Playwright MCP check remains unavailable because that server is not exposed in this session.
- Installation reported 21 npm dependency vulnerabilities; dependency upgrades have not been applied.
