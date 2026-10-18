# Status

Built from `docs/PLAN.md`, phase by phase.

## Done

- Phase 1, backend data and read operations: `backend/` serves the claims queue, policies, customer history, policy wording, instructions and handlers from SQLite, seeded from `data/` on first start. The agent sees no contact details for customers.

## Still to build

The claim workflow and payment rule, the agent, the dashboard and the end-to-end tests. The `agent/` and `dashboard/` folders are still the hello-world skeleton.

## Run it

- `uv sync` and `npm install` once.
- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173.
- `npm run check` runs every check.
- The database is `backend/undercover.db`, created on first start. Delete it to reset the queue.
