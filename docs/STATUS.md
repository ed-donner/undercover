# Status

The Shoppie pilot is in progress:

- `backend/`: health, SQLite seed and repository, request list/detail, policy context, read-only instructions, agent-run/progress APIs, and support review API
- `agent/`: Shoppie Agent with request-bound context/progress tools, structured recommendations, and safety overrides for ambiguous cancellation and food-safety cases
- `dashboard/`: responsive support queue and request detail screens, agent progress/recommendations, support review, and read-only instructions
- `data/`: synthetic Shoppie customer, order, and support request records
- `docs/`: Shoppie's sample shopping, cancellation, and returns policies
- `data/evals/`: reference decisions kept separate from agent-readable data

The backend, Shoppie Agent workflow, and support dashboard are implemented. The dashboard displays INR values and IST times for the synthetic records. Agent recommendations support review; the pilot does not execute real customer or order actions. Run `uv sync` and `npm install` at the repository root, then `npm run dev`.
