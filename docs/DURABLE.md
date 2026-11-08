# Approvals that wait, and work that survives a restart

From the head of claims operations, with our IT team.

SIDENOTE: For consistency with the course, please read `labs/week2day3.ipynb` and build the solution in the same style as the lab. Where the lab and this brief differ, follow the brief. Include this sidenote in your plan too.

## Where we're heading

UnderCover moves to the cloud next month. Before then we want the agent's recent improvements in the product, our records in a hosted database, and an agent that can wait for people and carry on after a restart.

An experiment by our team showed how to make the agent better: a payout tool, in `labs/week2day1.ipynb`. It isn't in the product yet.

Today, when the agent approves a payout over $1,000, its work on the claim ends. A handler signs off later and the system pays, but the agent never comes back to the claim. If the agent is stopped partway through a claim, by a crash, a restart or Ctrl-C, the work it has done on that claim is lost and the claim starts again from scratch.

## What we want

1. **The payout rules in our systems.** Our team found the agent gets payouts right far more often with a tool that applies our payout rules. The rules are in `labs/week2day1_payout.py`. Make them part of the backend, and give the claim agent a tool that uses them.

2. **Tracing in Langfuse.** Trace every claim the agent works in Langfuse, as in `labs/week2day1.ipynb`. Everything that happens on one claim should be easy to find together, including work that carries on after a pause.

3. **Our records on Supabase.** Move the backend's database to the Supabase database in `DATABASE_URL` in `.env`, the session pooler connection string from today's lab. Reseeding must work on Supabase. The tests keep running on SQLite and need no network.

4. **A sign-off picks the claim back up.** When the agent approves a payout over the limit, it stops and waits for a handler, keeping everything it has worked out. As soon as a handler signs off on the dashboard, the agent picks the claim up from where it stopped and pays it. Between the sign-off and the payment, the claim shows as in progress. If the agent isn't running at that moment, it picks the claim up the next time it runs. The payment records who signed off and when. A handler can only sign off for now; rejecting a held payout comes later. The system still blocks any payout over the limit without a sign-off, whatever the agent does.

5. **Work survives a restart.** If the agent is stopped partway through a claim, it carries on with that claim from where it got to the next time it runs, and that doesn't count as a new attempt. A claim that fails with an error still goes back in the queue and starts afresh, as it does today. A queue run that was stopped is finished by the next run.

6. **Nothing happens twice.** No claim is ever decided or paid twice. A step can run again after a restart, so the backend treats a repeat of a decision or payment already recorded for the claim as done, and returns the claim. A different decision on a decided claim is still refused.

## Our IT team's choices

- **The claim agent** becomes a hand-written LangGraph graph, with its own state, nodes and edges, in place of `create_agent`. The queue agent stays on `create_agent`. The graph keeps what the middleware does today: every step recorded on the claim, refusals returned to the model, and at most 30 model calls.
- **Paying** is a step of the graph for every approval: straight after the decision when no sign-off is needed, and after the sign-off when it is. The graph waits for a sign-off with LangGraph's `interrupt()` when the backend says a claim needs one, and never applies the limit itself. The claim agent loses its `pay_claim` tool, and its instructions change to match. A sign-off records who signed off and when, and no longer pays.
- **Progress** is saved after every step with LangGraph's Postgres checkpointer, in the same Supabase database, with `durability="sync"`. The agent stays synchronous, with the synchronous checkpointer, because async Postgres connections don't work with Windows' default event loop.
- **The agent's service** is a small web service of its own, the agent's entry point, which `npm run dev` starts beside the backend and the dashboard. Its address is `UNDERCOVER_AGENT` in the environment, or `http://127.0.0.1:8002`. The backend calls it after each sign-off, and it picks that claim back up. `uv run -m agent` still starts runs, and a run first carries on with any claim that was stopped or signed off while the agent was away. In the cloud the agent will run as a service like this, separate from the app. The service is a fourth part of the agent beside the three in `docs/CODE_STANDARDS.md`, and the graph's nodes take the place of the middleware.
- **A sign-off** reaches the agent only once it is saved. The backend doesn't wait for the payment, and the sign-off stands if the agent can't be reached.
- **The database:** the backend uses Supabase only when `DATABASE_URL` is in its environment. `npm run dev` passes `.env` and the tests never do. Use SQLAlchemy Core, so each query is written once for SQLite and Postgres. Keep all our tables, the checkpointer's included, in a schema of their own, `undercover`, set on the Postgres connection so the queries stay the same on SQLite. The free plan allows 15 connections at once through the session pooler, across every process, so use at most 4 connections in each.
- **Langfuse:** the keys are in `.env`. Each claim's work goes in one Langfuse session, named after the claim and its thread.
- **The payout operation** takes the approval limit from our settings in `data/company.json`.
- **Windows:** everything `npm run dev` starts must work on Windows too (`docs/PROCESS.md`).
- **The Supabase MCP server** is set up for Claude Code, read-only and limited to our project, so you can look at the tables as you build.

## What stays the same

- The rules in `docs/SPEC.md`, including the sign-off for payouts over $1,000. Update its section on working the queue to match this change, and leave its Rules alone.
- The API rules in `docs/TECH_STACK.md`: every operation has an `operation_id`, a one-line docstring and no optional inputs.
- Tests never call a model, and the code follows `docs/CODE_STANDARDS.md`.
- The dashboard works as it does today, apart from what this change needs.

## What done looks like

- `npm run check` is green with `.env` moved out of the way, so it needs no Supabase, Langfuse or OpenRouter. It has tests on a stub model for each new behavior: the payout operation; the pause before a payout over the limit; a sign-off resuming the claim and paying it once; a claim stopped partway carrying on from its last step with the same attempt and one decision; a claim that fails with an error starting afresh; and a repeated decision or payment counting as done. The end-to-end tests check that a sign-off on the dashboard reaches the agent's service, using a stand-in for it on port 8003, so they never reach the one `npm run dev` starts; the Python tests cover the resume and the payment.
- After reseeding Supabase, a run capped at five claims on the default model works five claims. A claim over the limit waits for a sign-off. Signed off on the dashboard through the Playwright MCP server, it shows as paid within five seconds, with the handler and the time.
- A run killed after a claim's first steps carries on with the same thread the next time, with the attempts unchanged and one decision.
- During the live run, Supabase shows no more than 12 connections, counting the connections in `pg_stat_activity` whose user is postgres, through the Supabase MCP server.
- Through Langfuse's API, the held claim's session has traces from before and after the sign-off.
- `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/PROCESS.md` and `docs/STATUS.md` describe the product as it now is.

## Planning

Follow `docs/PROCESS.md`, but write this plan to `docs/PLAN_DURABLE.md` and tick it off there. Bring in the payout rules and the tracing first. For any live run with the real model, reseed first and cap the run at five claims.
