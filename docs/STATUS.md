# Status

## Pilot progress

Phases 1–3 complete: SQLite records and typed APIs, transactional financial rules and an API-only LangChain claim agent. Seed imports use an explicit allowlist; evaluation records and the claims manual remain excluded. Monetary fields are stored as integer cents.

The backend blocks payouts above $1,000 until sign-off, validates exact approved amounts and prevents duplicate payments. Run history is persisted; agent execution is connected in phase 4.

- Local storage: `undercover.db` (git-ignored); override with `DATABASE_PATH`.
- Install: `uv sync` and root `npm install`.
- Run: `npm run dev` (API at `http://localhost:8000`, dashboard at `http://localhost:5173`). API reference: `/docs`.
- Agent: `run(claim_id, thread_id)` uses backend instructions and four claim-scoped tools. It must read context and wording before deciding. Configure `OPENROUTER_API_KEY` in `.env`; optional `MODEL_NAME` overrides `openai/gpt-6-luna` (low reasoning). Optional `BACKEND_URL` overrides `http://127.0.0.1:8000`.
- Verified: `npm run check:python`, 40 tests, 100% coverage, scripted models only.
- The dashboard remains the original health-check demonstration until phase 5.
- Installation reported 21 npm dependency vulnerabilities; dependency upgrades have not been applied.
