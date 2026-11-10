# Status

## Pilot progress

Phases 1–2 complete: SQLite startup seeding and typed read APIs for the 25-claim queue and related records; transactional claim starts, decisions, handler sign-off and separate simulated payments. Seed imports use an explicit allowlist; evaluation records and the claims manual remain excluded. Monetary fields are stored as integer cents.

The backend blocks payouts above $1,000 until sign-off, validates exact approved amounts and prevents duplicate payments. Run history is persisted; agent execution is connected in phase 4.

- Local storage: `undercover.db` (git-ignored); override with `DATABASE_PATH`.
- Install: `uv sync` and root `npm install`.
- Run: `npm run dev` (API at `http://localhost:8000`, dashboard at `http://localhost:5173`). API reference: `/docs`.
- Verified: `npm run check:python`, 33 tests, 99% coverage.
- Agent and dashboard remain the original health-check demonstrations until later phases.
- Installation reported 21 npm dependency vulnerabilities; dependency upgrades have not been applied.
