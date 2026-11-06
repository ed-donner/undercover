# Status

The Shoppie pilot is in progress:

- `backend/`: health route, SQLite seed and repository, and request list/detail API
- `agent/`: Shoppie Agent entry point with a backend health tool
- `dashboard/`: placeholder page that reports backend health
- `data/`: synthetic Shoppie customer, order, and support request records
- `docs/`: Shoppie's sample shopping, cancellation, and returns policies
- `data/evals/`: reference decisions kept separate from agent-readable data

Policy context, agent recommendations, request progress, and the support dashboard are still to be built. Run `uv sync` and `npm install` at the repository root, then `npm run dev`.
