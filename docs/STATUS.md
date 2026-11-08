# Status

The Shoppie pilot and its harness (`docs/HARNESS.md`, `docs/PLAN_HARNESS.md`) are implemented:

- `backend/`: health, SQLite seed and repository, request list/detail, the request context, policies served section by section (`GET /api/policies` and `read_policy_section`, which records each section read on the request), read-only instructions for the queue and for a request, and agent operations to start a waiting request, store its one recommendation, or count a failed attempt. Runs (`POST /api/runs` with a cap, `GET /api/runs/current`) keep a to-do list and a summary, and only one runs at a time. A failed request goes back to waiting once and is left for support after its second failure. No request gets two recommendations or two reviews. At startup, requests left in progress go back to waiting and unfinished runs are marked failed. `npm run seed` rebuilds the database.
- `agent/`: the queue agent (`agent/queue.py`) plans each run as a to-do list, chooses the order, and hands each request to the request agent with `work_request`, then finishes with a summary. Code enforces the cap and ticks the to-do list, and an `after_agent` middleware sends the agent back if it misses a waiting request within the cap. The request agent (`agent/main.py`) works one request on a fresh thread per attempt: it reads the context, looks up only the policy sections it needs, and returns a structured recommendation that cites them, with safety overrides for ambiguous cancellations and food-safety cases. LangChain's retry middleware retries model and network errors. The default model is DeepSeek V4.1 Flash with low reasoning effort; `MODEL_NAME` overrides it. `uv run -m agent --cap 5` starts a capped run, and `uv run -m agent REQ-7001` works one request.
- `dashboard/`: the support queue with a "Requests to work" cap and an Initiate processing button that starts a run. The run panel shows the to-do list (to do, in progress, done, left for support) and the summary. Queue badges show each request's agent decision, its reviewed outcome, or "Left for support". The request detail shows the recommendation, the progress timeline and the policy sections read, with the support review form. The instructions panel shows the queue and request instructions, read only.
- `data/`: synthetic Shoppie customer, order, and support request records, including clearly labeled synthetic follow-ups, photo, packing, delivery and carrier evidence for every request, and a fulfillment timeline (plus shipment tracking once dispatched) on every order. Food and perishable cases are limited to the leafy greens cancellation and the missing bread report; the food-safety guardrail is covered by a unit test fixture.
- `docs/`: Shoppie's sample shopping, cancellation, and returns policies, which the agent reads section by section.
- `data/evals/`: reference decisions kept separate from agent-readable data.

Agent recommendations support review; the product does not execute real customer or order actions. The dashboard displays INR values and IST times for the synthetic records.

## Running it

Run `uv sync` and `npm install` at the repository root, then `npm run dev`. `npm run seed` resets every request to waiting. Start a run from the dashboard, or with `uv run -m agent --cap 5` while `npm run dev` is running. For trials on the real model, reseed first and cap the run at five requests.

## Last live check

On the default model after reseeding, a run capped at five worked REQ-7004, REQ-7001, REQ-7008, REQ-7007 and REQ-7002 in about 85 seconds and left the other three waiting. Two requests failed on their first attempt, went back in the queue and got their recommendation on the second.
