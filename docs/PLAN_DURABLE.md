# Plan: approvals that wait, and work that survives a restart

Builds `docs/DURABLE.md`: the payout rules in the backend, Langfuse tracing, our records on Supabase, a claim agent that pauses for a sign-off and carries on after a restart, and no decision or payment ever happening twice.

SIDENOTE: For consistency with the course, please read `labs/week2day3.ipynb` and build the solution in the same style as the lab. Where the lab and this brief differ, follow the brief.

## What I found in the code

Three places where the brief's notes on the current build don't match the code. I follow the brief's intent.

- The claim agent has no `pay_claim` tool today. Its tools are `get_claim`, `list_sections`, `read_section` and `decide_claim`, and the instructions say a handler signs off on the payment separately. So there is no tool to remove, only instructions to change.
- There is no middleware in `agent/harness.py`. The steps are recorded inside the tools, a failed backend call raises, and nothing caps the model calls. The graph does these three jobs itself.
- `docs/SPEC.md` still lists signing off from the screens under "Not for now", but the dashboard already has the controls. I fix its working-the-queue section and that line, and leave its Rules alone.

## Design

**Statuses.** `waiting` -> `in progress` -> `decided` for a decline, a referral or an approval at or under the limit. An approval over the limit goes `waiting for sign-off` -> `in progress` (from the sign-off until the payment) -> `decided` (once paid). The dashboard's four badges don't change.

**Payment.** `sign_off_claim` only records who signed off and when, and sets `in progress`. `pay_claim` is called only by the graph. It sets `decided` and records the payment. The dashboard loses its "Release payment" button.

**Threads.** A claim has a `thread` number in the backend, starting at 1. The graph's thread id is `CLM-1001-1`. `requeue_claim` (a failure) adds 1, so a claim that fails starts afresh on a new thread and the old traces stay apart. A claim that is stopped keeps its thread and its status `in progress`, so the next run finds it and carries on. The Langfuse session for a claim's work is its thread id, so the traces from before and after a sign-off sit together.

**Idempotence.** The conditional `UPDATE` in `decide` guards on `decision IS NULL`, not on status, because an `in progress` claim has a decision once it's signed off. A repeat of the same decision or payment returns the claim. A different decision on a decided claim is a 409.

**The sign-off limit** has one home: `payouts.needs_sign_off()` in the backend, reading `data/company.json`. `decide` uses it, the payout operation uses it, and the graph reads the result from the status the backend returns.

**The graph** follows the lab's shape with the brief's changes:

```
START -> agent <-> tools
agent -> settle   (when the model stops calling tools)
settle -> agent   (no decision recorded yet, so send it back)
settle -> END     (decline or referral)
settle -> approval -> pay -> END   (over the limit)
settle -> pay -> END               (approved, under the limit)
```

- `agent` calls the model with `get_claim`, `list_sections`, `read_section`, `calculate_payout` and `decide_claim`, which stay module-level tools reading `ToolRuntime[ClaimContext]`. It counts model calls in the state and fails the claim past 30.
- `tools` is a `ToolNode` with `handle_tool_errors` on, so a refusal from the backend reaches the model as a tool message.
- `settle` reads the claim from the backend and puts the decision, the payout and "needs sign-off" in the state. It applies no limit itself.
- `approval` calls `interrupt()` and records nothing before it, since a resumed node runs again from the top.
- `pay` calls `pay_claim`, which treats a repeat as done.
- Steps are recorded in the tools and in `settle`, `approval` (after the interrupt) and `pay`.

**Connections.** The free pooler allows 15 across every process. The backend's engine is capped at 4 (`pool_size=2, max_overflow=2`). Each agent process uses a pool of at most 2 for the checkpointer. The worst case is four processes: the backend, the agent's service, a CLI run and the dashboard's "Run agent" subprocess. That is 4 + 2 + 2 + 2 = 10, under the 12 the brief allows.

**Tests and `.env`.** The backend uses Supabase only when `DATABASE_URL` is in its environment. The agent's `harness.py` already calls `load_dotenv`, which would put `DATABASE_URL` into the test process. So `agent/tests/conftest.py` removes `DATABASE_URL` and the `LANGFUSE_*` keys. The graph is built from a checkpointer passed in, and the tests pass `InMemorySaver`, shared between two builds to stand for a restart.

## New dependencies

- `uv add sqlalchemy`, moved from the `server` group into the main dependencies.
- `uv add "psycopg[pool]"` for the checkpointer's connection pool.
- `langgraph`, `langgraph-checkpoint-postgres`, `psycopg` and `langfuse` are already in `pyproject.toml`.

## Phase 1: The payout rules in the backend, and a payout tool

Brings in `labs/week2day1_payout.py` first, as the brief asks.

- `backend/payouts.py`: works out a payout from the plan's limits and the wording's section 10. It is `labs/week2day1_payout.py` in `Decimal` rather than floats (`agent/tests/test_structure.py` bans floats), rounding to the cent when it works the payout out. It reads `data.PLANS`, and `needs_sign_off(payout)` reads `data.PAYOUT_APPROVAL_LIMIT`.
- `backend/main.py`: the route `calculate_payout` (a POST with an `operation_id`, a one-line docstring and no optional inputs, so `paid_by_others` and each line's `quantity`, `nights` and `hours` are required). It calls `payouts.py` and nothing else.
- `agent/api.py`: `calculate_payout(...)`, with the `Line` and `Benefit` types the model fills in.
- `agent/tools.py`: the `calculate_payout` tool, with the lab's descriptions of the lines.
- `backend/instructions.py`: one line that tells the agent it has a payout tool and to record the payout it returns. The instructions stay a goal, not steps.
- `claims.decide` uses `payouts.needs_sign_off` in place of its own comparison.

**Success criteria**

- [x] `uv run pytest backend -q` passes, including: a payout with a per-item limit, a deductible, a benefit maximum and a payment from others; cash capped at $100; hotel nights and meals without receipts; a payout of 0 when nothing is left; `needs_sign_off` true at $1,000.01 and false at $1,000.00; and the route returns two-decimal strings.
- [x] `grep -rn "float" backend/payouts.py` returns nothing, and `test_structure.py` passes.
- [x] `uv run pytest agent -q` passes, including a scripted run where the stub model calls `calculate_payout` and then `decide_claim`.
- [x] `POST /api/payouts` with the lab's baggage example (policy `POL-2201`, a $239.99 suitcase and three T-shirts for $74.97, $100 paid by others) returns the same payout as `labs/week2day1_payout.py` run with those inputs.
- [x] The instructions page shows the new line.
- [x] `npm run check` is green.

## Phase 2: Tracing in Langfuse

- `agent/tracing.py`: the one module that knows Langfuse. It gives the callbacks and metadata for a claim's work: a `CallbackHandler`, and `langfuse_session_id` set to the claim id (this becomes the thread id in Phase 6). It returns nothing when `LANGFUSE_SECRET_KEY` isn't set, so tests make no network calls. It flushes the client at the end of a process, because the CLI is short-lived.
- `agent/harness.py`: `run_agent` takes the config for the run and hands it to `invoke`. It still knows nothing about claims.
- `agent/agents.py`: `decide_claim` and `run_queue` pass the tracing config. The queue's trace and each claim's trace are in separate sessions.
- A structure test: only `tracing.py` imports `langfuse`.

**Success criteria**

- [x] `uv run pytest agent -q` passes with no `LANGFUSE_*` keys set, and a test shows `tracing.py` returns no callbacks without them.
- [x] Run once with the real model on one reseeded claim, `MODEL_NAME=openrouter/free uv run -m agent.cli --claim CLM-1001`, then check through Langfuse's API (`langfuse.api.trace.list(session_id="CLM-1001")`) that the claim's traces are all in one session.
- [x] `npm run check` is green with `.env` moved out of the way.

## Phase 3: SQLAlchemy Core on SQLite, nothing else changes

Moves every query to Core while the tests still pass, so Phase 4 changes the database only.

- `backend/db.py`: the engine and the table definitions for `claims`, `claim_steps`, `runs` and `run_items`, with no schema in the table names. `connection()` keeps its name and its job (commit, roll back, close) but yields a Core connection. The engine, `create_all` and the first seeding happen once per URL (an `lru_cache`), not on every call, since each call will be a network round trip on Supabase.
- `backend/claims.py`, `backend/runs.py`: each query written once with Core (`update().where()`, `select()`, `insert().returning()`). The `attempts + (?1 = 'in progress')` in SQL becomes a `case()`.
- `claims` gets a `thread` column (integer, default 1) and the `requeue` operation adds 1 to it.
- The tests are unchanged apart from the connection fixture.

**Success criteria**

- [x] `uv run pytest -q` passes at the same coverage, with the existing tests unchanged (no behavior change).
- [x] `grep -rn "sqlite3" backend` returns only `db.py`'s SQLite URL, and `grep -rn "execute(\"" backend` returns nothing.
- [x] A new test: `requeue_claim` adds 1 to a claim's `thread`, and `get_claim` shows it.
- [x] `npm run check` is green.

## Phase 4: Our records on Supabase

- `backend/db.py`: with `DATABASE_URL` set, the engine uses Postgres (the `postgresql+psycopg://` form) with `pool_size=2, max_overflow=2` and `connect_args={"options": "-c search_path=undercover"}`, after `CREATE SCHEMA IF NOT EXISTS undercover`. With no `DATABASE_URL` it uses SQLite as before.
- `backend/seed.py`: `uv run --env-file .env -m backend.seed` resets the database to the seeded queue. On Postgres it drops and recreates the `undercover` schema, so the checkpointer's tables go too. If it only cleared the claims, the old threads would come back to life under the same ids. On SQLite it deletes the file. It is run with `npm run seed`, and it needs the agent's service stopped.
- `package.json`: `dev:backend` runs with `--env-file .env`, plus `seed`. I'll check what `uv run --env-file` does when `.env` is missing, since `npm run check` runs without it. If it fails, I'll use a small `.mjs` script that passes `.env` only when it exists (this works on Windows too).

**Success criteria**

- [x] `uv run pytest -q` passes with no network and `.env` moved out of the way.
- [x] Through the Supabase MCP server, `list_tables` shows the four tables in the `undercover` schema and none in `public`.
- [x] `npm run seed`, then `GET /api/claims` returns 25 claims, all `waiting`. Run it twice to show reseeding works on a database that already has data.
- [x] Restart the backend and the claims keep their state (Postgres persists it).
- [x] The Supabase MCP server's `get_advisors` reports nothing new that this change caused. If it reports tables without row level security, I'll tell you rather than change it, since the backend is the only client.
- [x] `npm run check` is green with `.env` moved out of the way.

## Phase 5: The backend's rules for sign-off, decision and payment

- `claims.sign_off`: records the handler and time, sets `in progress` and does not pay. A repeat sign-off by the same handler returns the claim.
- `claims.decide`: guards on `decision IS NULL`. The same decision again returns the claim, and a different decision on a decided claim is a 409.
- `claims.pay`: a repeat payment of the same amount returns the claim. The first payment sets `decided`. The existing blocks stay: no payment without the sign-off, only the approved payout.
- `claims.list_unfinished()` and the route `list_unfinished_claims`: the claims the agent must carry on with. These are the `in progress` claims, and the approved claims that are payable (under the limit, or signed off) but unpaid.
- `backend/agent_service.py`: tells the agent's service about a sign-off. It is the only place the agent's address is known: `UNDERCOVER_AGENT`, or `http://127.0.0.1:8002`. The route schedules it as a background task, so it runs after the sign-off is saved and the response doesn't wait for the payment. It catches `httpx.HTTPError` and nothing else, since an unreachable agent must not undo the sign-off.
- `backend/agent_process.py`: runs `python -m agent` in place of `agent.cli`.
- `agent/api.py`: `decide_claim` returns the claim, `pay_claim` and `list_unfinished_claims` are added.

**Success criteria**

- [x] `uv run pytest backend -q` passes, including:
  - [x] a $1,200 approval -> `waiting for sign-off` -> `pay_claim` is 409 -> `sign_off_claim` -> status `in progress`, with the handler and time recorded, and no payment -> `pay_claim` -> `decided`, paid.
  - [x] the same decision twice returns the claim, one row, one `decided_on`; a different decision is 409, even on an `in progress` signed-off claim.
  - [x] the same payment twice returns the claim with one `paid_on`; a payment of a different amount is 409.
  - [x] a sign-off with the agent unreachable (the notifier pointed at a closed port) still returns 200 and the sign-off stands.
  - [x] a sign-off calls the notifier once, after the commit, with the claim id.
  - [x] `list_unfinished_claims` lists an `in progress` claim and a signed-off unpaid claim, and not a `waiting for sign-off` or a paid one.
- [x] `npm run check` is green. The e2e tests that used "Release payment" are updated in Phase 8, so until then the pre-commit hook runs the unit checks and `npm run e2e` waits for Phase 8. I'll say so in the commit message.

## Phase 6: The claim agent as a LangGraph graph

- `agent/claim_state.py`: `ClaimState` (messages, decision, payout, needs_sign_off, model_calls) and the state a claim starts with. `agent/claim_graph.py`: the edges and `build_graph(checkpointer, model, instructions)`. This module only wires the graph.
- `agent/claim_nodes.py`: the nodes (`agent`, `settle`, `approval`, `pay`). Each is short and calls the backend through `api.py`.
- `agent/tools.py`: `CLAIM_TOOLS` gains `calculate_payout` (Phase 1). `decide_claim` stays, and now uses the repeat-safe backend.
- `agent/checkpoint.py`: the one module that touches Postgres. It makes the pool (at most 2 connections, with the lab's settings `autocommit=True`, `prepare_threshold=0`, `row_factory=dict_row` and `search_path=undercover`), runs `setup()` once, and gives the `PostgresSaver`.
- `agent/agents.py`: `decide_claim(claim_id)` builds the graph and runs the claim on thread `claim-thread`, or carries on if that thread has saved state. It invokes with `durability="sync"`, the tracing config (session = the thread id) and `ClaimContext`. `resume_claim(claim_id)` answers a sign-off. `carry_on()` calls `list_unfinished_claims` and carries on with each.
- `backend/instructions.py`: the claim instructions drop the line about a separate sign-off and say that a payout over the limit waits for a handler, and that the agent does not pay.
- `agent/harness.py`: `run_agent` stays for the queue agent only.

**Success criteria**

- [x] `uv run pytest agent -q` passes, on a stub model and an in-memory checkpointer, including:
  - [x] under the limit: the claim ends `decided`, paid, with the steps in order.
  - [x] over the limit: the run returns with the graph paused (`state.next == ("approval",)`), the claim `waiting for sign-off`, nothing paid. After `sign_off_claim`, resuming the thread pays it once and the claim is `decided` with the handler recorded. Resuming it a second time pays nothing more.
  - [x] the agent trying `decide_claim` twice: the second is a repeat, not a second decision.
  - [x] a decline and a referral end without a payment.
  - [x] a refusal from the backend (a payout of 0 on an approval) reaches the model as a tool message, and the model corrects it.
  - [x] a model that keeps calling tools stops with an error on the 31st model call.
- [x] `agent/claim_graph.py` has the lab's graph picture: `build_graph(...).get_graph().draw_mermaid()` shows the five nodes (checked by eye, not a test).
- [x] `test_structure.py` gains: only `checkpoint.py` imports `psycopg` or `langgraph.checkpoint`, and `grep -n "1000\|APPROVAL_LIMIT" agent` returns nothing (the graph applies no limit).
- [x] `npm run check:python` is green.

## Phase 7: Work that survives a restart, and the agent's service

- `agent/work.py`: the retry policy keeps its rules, and learns about a stopped claim. If a claim's run item is `in progress` and the claim has saved state, the item is carried on and `update_run_item` doesn't add an attempt. A failure (any `Exception`) still calls `requeue_claim` and the claim starts afresh on its new thread. Ctrl-C and a kill are not `Exception`, so they leave the claim `in progress` for the next run.
- `agent/agents.py`: `run_queue` first calls `carry_on()`. If the latest run hasn't finished, it continues that run instead of starting another. In that case `--cap` doesn't apply, since the run's list is already fixed.
- `agent/__main__.py` replaces `cli.py`, so `uv run -m agent` works as the brief says, with the same `--cap` and `--claim` options.
- `agent/service.py`: the agent's service, a small FastAPI app. `POST /api/claims/{claim_id}/resume` (an `operation_id`, a one-line docstring, no optional inputs) answers 202 and carries on with that claim in the background. It builds the graph once at startup. It calls the same `resume_claim` as the CLI, so there is one way to resume.
- `package.json`: `dev:agent` runs `uv run -m uvicorn agent.service:app --port 8002`, and `dev` runs the backend, the agent and the dashboard.

**Success criteria**

- [x] `uv run pytest agent -q` passes, including:
  - [x] a claim stopped partway (the stub raises `KeyboardInterrupt` after the first tool call), then a new graph on the same checkpointer: it carries on from the last step, the run item's attempts are unchanged, the thread is the same and there is one decision.
  - [x] a claim that fails with an error is requeued, starts on thread 2 and is decided there; the run item's attempts become 2.
  - [x] a stopped queue run: the next `run_queue` finishes that run's items and finishes the run, and doesn't start a second run.
  - [x] a signed-off claim whose agent was away is paid by `carry_on()`.
  - [x] the service: `POST /api/claims/CLM-1003/resume` returns 202, and the claim ends paid (the test client, a stub model).
- [x] `uv run -m agent --help` works. `npm run dev` starts three processes and `GET http://127.0.0.1:8002/api/health` answers.
- [x] `npm run check:python` is green.

## Phase 8: The dashboard and the end-to-end tests

- `dashboard/src/pages/ClaimPage.tsx`: removes "Release payment". After a sign-off, the page shows `in progress` and polls (it already polls while a claim is in progress), then shows the payment with who signed off and when.
- `dashboard/src/api.ts`, `types.ts`: drop the payment call the page no longer makes (the types keep the paid fields).
- `e2e/agentStandIn.mjs`: a tiny HTTP server on port 8003 that records the calls it receives and lets a test read them.
- `playwright.config.ts`: the backend for the tests runs with `UNDERCOVER_AGENT=http://127.0.0.1:8003` and no `DATABASE_URL`. `reuseExistingServer` is off for the backend so a dev server (pointing at the real agent) can't be picked up by mistake.
- `e2e/claim.spec.ts`: updated for the new flow, plus a test that signing off on the dashboard calls the stand-in once with that claim.

**Success criteria**

- [x] `npx vitest run --root dashboard --coverage` passes at 80% or above, with a test for the page after a sign-off (in progress, then paid with the handler and time).
- [x] `npm run e2e` passes: an over-limit claim shows `waiting for sign-off`; signing off shows the sign-off was received by the stand-in on 8003, once; no test reaches port 8002.
- [x] The e2e run touches no Supabase, Langfuse or OpenRouter (with `.env` moved out of the way).
- [x] `npm run check` is green with `.env` moved out of the way.

## Phase 9: Documents, the live runs and the final review

- `docs/SPEC.md`: the working-the-queue section describes the wait for a sign-off and the carry-on; the Rules are untouched, and I remove the stale "Signing off from the screens" line from "Not for now".
- `docs/TECH_STACK.md`: Supabase and SQLAlchemy Core, the graph, the checkpointer, the agent's service as a fourth part, Langfuse, and the payout operation.
- `docs/PROCESS.md`: `npm run dev` starts three parts, `npm run seed`, and the `.env` rule for the checks.
- `docs/STATUS.md`: what is built and how to run it.
- Review the whole change once more against the checklist in `docs/CODE_STANDARDS.md`.

**Success criteria (the live run, with the real model; reseed first and cap the run at five claims)**

- [ ] `npm run seed`, then `npm run dev`, then `uv run -m agent --cap 5` on the default model works five claims. A claim over the limit waits for a sign-off.
- [ ] Through the Playwright MCP server, I sign off the held claim on the dashboard and it shows as paid within five seconds, with the handler and the time.
- [ ] I kill a run (`Ctrl-C`) after a claim's first steps. The next `uv run -m agent` carries on with the same thread: the database shows the same `thread`, the run item's attempts unchanged and one decision.
- [ ] I stop the agent's service, sign off a held claim (it succeeds), then run `uv run -m agent`: the claim is paid.
- [ ] Through the Supabase MCP server, `SELECT count(*) FROM pg_stat_activity WHERE usename = 'postgres'` (the brief's user) is 12 or fewer during the run.
- [ ] Through Langfuse's API, the held claim's session has traces from before and after the sign-off.
- [ ] `npm run check` is green with `.env` moved out of the way, with a test for each behavior the brief lists (the payout operation; the pause; a sign-off resuming and paying once; a claim stopped partway; a claim that fails; a repeated decision or payment).
- [ ] `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/PROCESS.md` and `docs/STATUS.md` describe the product as it now is.

## Things I'd like you to check

- **Thread numbers on the claim.** I keep the thread number in the backend (`claims.thread`) so a restart can always find the thread, and a failure moves to a new one. The alternative is deleting the old thread on failure, which loses the old traces' names.
- **Decide stays a tool.** The lab has a separate `decide` node that asks the model for a structured decision. I keep the `decide_claim` tool, because the brief keeps the tools and it saves a model call. The `settle` node reads the result back from the backend.
- **`--cap` on a continued run.** When the next run continues an unfinished one, the cap is ignored. That seems right to me, but it is a choice.
- **Reseeding needs the agent stopped,** because it drops the checkpointer's tables.
