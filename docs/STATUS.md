# Status

The Shoppie adaptation is at the pilot skeleton stage:

- `backend/`: health route only (`GET /api/health`)
- `agent/`: Shoppie Agent entry point with a backend health tool
- `dashboard/`: placeholder page that reports backend health
- `data/`: synthetic Shoppie customer, order, and support request records
- `docs/`: Shoppie's sample shopping, cancellation, and returns policies
- `data/evals/`: reference decisions kept separate from agent-readable data

The support queue, policy-based recommendations, and request detail screens are not implemented yet. Run `uv sync` and `npm install` at the repository root, then `npm run dev`.
