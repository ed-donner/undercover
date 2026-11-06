# Status

The Shoppie pilot is in progress:

- `backend/`: health, SQLite seed and repository, request list/detail, policy context, and read-only instructions APIs
- `agent/`: Shoppie Agent entry point and shared read-only instructions
- `dashboard/`: placeholder page that reports backend health
- `data/`: synthetic Shoppie customer, order, and support request records
- `docs/`: Shoppie's sample shopping, cancellation, and returns policies
- `data/evals/`: reference decisions kept separate from agent-readable data

Agent recommendations, request progress, and the support dashboard are still to be built. Run `uv sync` and `npm install` at the repository root, then `npm run dev`.
