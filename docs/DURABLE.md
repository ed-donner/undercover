# Reviews that wait, and work that survives a restart

From Shoppie's head of customer support, with our IT team.

SIDENOTE: For consistency with the course, please read `labs/week2day3.ipynb` and build the solution in the same style as the lab. Where the lab and this brief differ, follow the brief. Include this sidenote in your plan too.

## Where we're heading

Shoppie moves to the cloud next month. Before then we want the agent's recent improvements in the product, our records in a Postgres database, and an agent that can wait for support agents and carry on after a restart.

An experiment by our team showed how to make the agent better: a refund calculation tool, in the style of `labs/week2day1.ipynb`. It isn't in the product yet.

Today, when the agent prepares a recommendation on a support request, its work on the request ends. A support agent reviews it later and the system marks it decided, but the agent never comes back to the request. If the agent is stopped partway through a request, by a crash, a restart or Ctrl-C, the work it has done on that request is lost and the request starts again from scratch.

## What we want

1. **The refund rules in our systems.** Our team found the agent gets refund amounts right far more often with a tool that applies our refund and pickup-fee rules from our shopping, cancellation and returns policies. Make them part of the backend, and give the request agent a tool that uses them.

2. **Tracing in Langfuse.** Trace every request the agent works in Langfuse, as in `labs/week2day1.ipynb`. Everything that happens on one request should be easy to find together, including work that carries on after a pause.

3. **Our records on Postgres.** Move the backend's database to the Postgres database in `DATABASE_URL` in `.env` (running in a local Docker Postgres container, or a hosted Postgres database). Reseeding must work on Postgres. The tests keep running on SQLite and need no network.

4. **A sign-off picks the request back up.** When the agent prepares a recommendation, it stops and waits for a support agent to review and sign off on it, keeping everything it has worked out. As soon as a support agent signs off on the dashboard, the agent picks the request up from where it stopped and completes it. Between the sign-off and completion, the request shows as in progress. If the agent isn't running at that moment, it picks the request up the next time it runs. Completion records who signed off and when. The system never marks an agent-worked request decided without a support agent's sign-off.

5. **Work survives a restart.** If the agent is stopped partway through a request, it carries on with that request from where it got to the next time it runs, and that doesn't count as a new attempt. A request that fails with an error still goes back in the queue and starts afresh, as it does today. A queue run that was stopped is finished by the next run.

6. **Nothing happens twice.** No request is ever recommended or completed twice. A step can run again after a restart, so the backend treats a repeat of a recommendation or completion already recorded for the request as done, and returns the request. A different recommendation or decision on a decided request is still refused.

## Our IT team's choices

- **The request agent** becomes a hand-written LangGraph graph, with its own state, nodes and edges, in place of `create_agent`. The queue agent stays on `create_agent`. The graph keeps what the middleware does today: every step recorded on the request, refusals returned to the model, and at most 30 model calls.
- **Completion** is a step of the graph after the support agent's sign-off. The graph waits for a sign-off with LangGraph's `interrupt()` after saving its recommendation. A sign-off records who signed off, their reviewed outcome and notes, and when, and hands completion back to the agent.
- **Progress** is saved after every step with LangGraph's Postgres checkpointer, in the same Postgres database (`DATABASE_URL`), with `durability="sync"`. The agent stays synchronous, with the synchronous checkpointer, because async Postgres connections don't work with Windows' default event loop.
- **The agent's service** is a small web service of its own, the agent's entry point, which `npm run dev` starts beside the backend and the dashboard. Its address is `UNDERCOVER_AGENT` in the environment, or `http://127.0.0.1:8002`. The backend calls it after each sign-off, and it picks that request back up. `uv run -m agent` still starts runs, and a run first carries on with any request that was stopped or signed off while the agent was away. In the cloud the agent will run as a service like this, separate from the app.
- **A sign-off** reaches the agent only once it is saved. The backend doesn't wait for completion, and the sign-off stands if the agent can't be reached.
- **The database:** the backend uses Postgres only when `DATABASE_URL` is in its environment (pointing at our local Docker Postgres container `postgresql://postgres:postgres@127.0.0.1:5432/postgres` or any Postgres instance). `npm run dev` passes `.env` and the tests never do. Use SQLAlchemy Core, so each query is written once for SQLite and Postgres. Keep all our tables, the checkpointer's included, in a schema of their own, `undercover`, set on the Postgres connection so the queries stay the same on SQLite. Use at most 4 connections in each process so total connections stay under 12.
- **Langfuse:** the keys are in `.env`. Each request's work goes in one Langfuse session, named after the request and its thread.
- **Windows:** everything `npm run dev` starts must work on Windows too (`docs/PROCESS.md`).

## What stays the same

- The rules in `docs/SPEC.md`: recommendations follow Shoppie's policies, a support agent confirms every decision, and no real cancellations, returns, replacements, refunds or customer messages are executed. Update its section on working the queue to match this change, and leave its Rules alone.
- The API rules in `docs/TECH_STACK.md`: every operation has an `operation_id`, a one-line docstring and no optional inputs.
- Tests never call a model, and the code follows `docs/CODE_STANDARDS.md`.
- The dashboard works as it does today, apart from what this change needs.

## What done looks like

- `npm run check` is green with `.env` moved out of the way, so it needs no Postgres container, Langfuse or OpenRouter. It has tests on a stub model for each new behavior: the refund calculation operation; the pause for support sign-off; a sign-off resuming the request and completing it once; a request stopped partway carrying on from its last step with the same attempt and one recommendation; a request that fails with an error starting afresh; and a repeated recommendation or completion counting as done. The end-to-end tests check that a sign-off on the dashboard reaches the agent's service, using a stand-in for it on port 8003, so they never reach the one `npm run dev` starts; the Python tests cover the resume and completion.
- After reseeding the local Postgres container (`npm run seed`), a run capped at five requests on the default model works five requests and waits for support sign-off. Signed off on the dashboard through the Playwright MCP server, a request shows as decided within five seconds, with the support agent's name and the time.
- A run killed after a request's first steps carries on with the same thread the next time, with the attempts unchanged and one recommendation.
- During the live run, Postgres shows no more than 12 connections in `pg_stat_activity` whose user is `postgres`.
- When Langfuse keys are configured, the held request's session has traces from before and after the sign-off.
- `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/PROCESS.md` and `docs/STATUS.md` describe the product as it now is.

## Planning

Follow `docs/PROCESS.md`, but write this plan to `docs/PLAN_DURABLE.md` and tick it off there. Bring in the refund rules and the tracing first. For any live run with the real model, reseed first and cap the run at five requests.
