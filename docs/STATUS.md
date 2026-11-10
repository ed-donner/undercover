# Status

## Pilot progress

Phase 1 complete: SQLite startup seeding and typed read APIs for the 25-claim queue, full claims, policies, plans, customers/history, handlers, company settings, wording and read-only agent instructions. Seed imports use an explicit allowlist; evaluation records and the claims manual remain excluded. Monetary fields are stored as integer cents.

- Local storage: `undercover.db` (git-ignored); override with `DATABASE_PATH`.
- Install: `uv sync` and root `npm install`.
- Run: `npm run dev` (API at `http://localhost:8000`, dashboard at `http://localhost:5173`). API reference: `/docs`.
- Verified: `npm run check:python`, 11 tests, 98% coverage.
- Agent and dashboard remain the original health-check demonstrations until later phases.
- Installation reported 21 npm dependency vulnerabilities; dependency upgrades have not been applied.
