# Status

The Shoppie pilot is in progress:

- `backend/`: health, SQLite seed and repository, request list/detail, policy context, read-only instructions, agent-run, and progress APIs
- `agent/`: Shoppie Agent with request-bound context/progress tools and structured recommendations
- `dashboard/`: placeholder page that reports backend health; support queue and request detail screens are next
- `data/`: synthetic Shoppie customer, order, and support request records
- `docs/`: Shoppie's sample shopping, cancellation, and returns policies
- `data/evals/`: reference decisions kept separate from agent-readable data

Agent recommendations and progress persistence are implemented. The support dashboard is still to be built. Run `uv sync` and `npm install` at the repository root, then `npm run dev`.
