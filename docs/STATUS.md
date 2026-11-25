# Status

The pilot from `docs/PLAN.md` and the harness from `docs/PLAN_HARNESS.md` are built.

- `backend/`: FastAPI on SQLite. The database is seeded from `data/` (never `data/evals/`) and serves the claims queue, policies with their plan limits, customers' claim history (without personal details), the policy wording, the claims manual, the numbered sections of both, the agent's two sets of instructions (`backend/instructions/queue.md` and `claim.md`) and the handlers. It records runs with their to-do list and summary, decisions, payments, sign-offs and the agent's steps, and enforces the rules: one run at a time, one decision per claim, a payment only for the approved payout, an approval over $1,000 waits for a handler's sign-off, and a claim that fails twice is left for a handler. On startup it closes any run a restart cut short and puts its claim back.
- `agent/`: the UnderCover Agent. A run (`agent/queue.py`) is a queue agent that lists the waiting claims in its scope, writes a to-do list, hands each claim to `work_claim` and finishes with a summary. `work_claim` (`agent/claim.py`) starts a fresh claim agent that reads the claim, policy and history, looks up the sections it needs, decides and pays approvals up to $1,000, posting every step (including each section read) to the claim; it returns one line and never raises. Code holds the rules the model can't talk around: the cap, a claim outside a one-claim run, finishing while a claim within the cap or a retry is still waiting, and releasing a claim that failed. Middleware retries model and tool errors twice and ends a claim after 25 model calls. The default model is `deepseek/deepseek-v4.1-flash` with low reasoning effort, or `MODEL_NAME`.
- `dashboard/`: React in the UnderCover brand, light and dark, refreshing on its own. The queue with a count per state and, above it, the current run: its status, scope, times, to-do list with a chip per item, summary or problem, and Run the queue with the number of claims to work. Each claim in full with its policy, history, decision and reasons, the wording of the policy section, what the agent read, and its steps live while it works, with retries marked (Run agent starts a one-claim run); sign-off and payment for payouts over $1,000; both sets of instructions read only. Views are hash links: `#/`, `#/claims/<id>`, `#/instructions`.
- `e2e/`: Playwright tests of the queue, a decision, the sign-off, the instructions, a run's to-do list and summary, a claim left for a handler and the sections read. They run their own backend on port 8001 with a fresh database (`e2e/e2e.db`) and `UNDERCOVER_AGENT=off`, and the dashboard on port 5174, and play the agents' part through the API, so they never call a model.

Live trial (November 24, 2026): after a reseed, Run the queue with a cap of 5 on DeepSeek V4.1 Flash worked CLM-1004, CLM-1013, CLM-1023, CLM-1025 and CLM-1001 in about 13 minutes with no failures: three approved and paid ($677.00), one declined, one referred. Each claim read 8 to 13 sections; the other 20 claims stayed waiting. The decisions have not been scored against `data/evals/`.

Not built, as the spec says: sign-in, real payments and messages to customers. A claim left for a handler can't yet be worked by hand in the dashboard. There is no tool yet for scoring the agent against `data/evals/`.

## Running it

- `uv sync` and `npm install` once
- `npm run seed` rebuilds the database at `backend/undercover.db` (or the path in `UNDERCOVER_DB`). The backend seeds it on startup if it is missing. Run it again to put every claim back to waiting.
- `npm run dev` starts the backend on port 8000 and the dashboard on http://localhost:5173
- Start a run with Run the queue on the queue page, or Run agent on a waiting claim. From the command line, with the backend running: `uv run -m agent --cap 5` or `uv run -m agent CLM-1001`. Both start the run in the backend and print the to-do list as it changes, then the summary. The agent runs inside the backend, so a restart of the backend ends the run.
- `UNDERCOVER_AGENT=off` starts the backend without the agent, so runs can be played through the API.
- `npm run check` runs every check
