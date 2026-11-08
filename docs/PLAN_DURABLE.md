# Shoppie durable state plan

SIDENOTE: For consistency with the course, please read `labs/week2day3.ipynb` and build the solution in the same style as the lab. Where the lab and this brief differ, follow the brief.

This plan builds `docs/DURABLE.md` for Shoppie using a local Docker Postgres container (`DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/postgres` in `.env`) in place of hosted Supabase, while keeping full compatibility with any Postgres connection string. In line with `docs/SPEC.md`, recommendations and confirmed reviews never execute real external customer or payment actions.

Today, the request agent (`agent/main.py`) uses `create_agent`, stores its recommendation, and stops forever. A support agent's review marks the request `decided` directly in the backend, and if the process crashes mid-request, all progress on that attempt is lost and the backend resets `in_progress` requests to `waiting` on startup.

After this build:

- **Refund rules live in the backend (`backend/refunds.py`).** A backend operation applies Shoppie's cancellation, return, delivery-fee, and ₹75 return-pickup-fee rules to an order's items and gives the request agent a tool (`calculate_refund`) to compute exact INR amounts.
- **Every request is traced in Langfuse.** All steps on a request share a single Langfuse session named after the request and its thread, so work before and after a pause or restart appears together.
- **Records live in local Docker Postgres when `DATABASE_URL` is set, and SQLite in tests.** `backend/store.py` uses SQLAlchemy Core so each query is written once. On Postgres, all application and LangGraph checkpointer tables live in the `undercover` schema (`search_path=undercover`), and each process caps its pool at 4 connections so total connections stay under 12.
- **The request agent becomes a hand-written synchronous LangGraph `StateGraph`.** Built in the style of `labs/week2day3.ipynb` with `durability="sync"` and `PostgresSaver` (or an offline checkpointer in tests), it loops between `agent` and `tools` (at most 30 model calls), turns its work into a structured `Recommendation` in `decide`, pauses at `approval` with `interrupt()` while waiting for support review, and finishes in `complete` once the support agent signs off. The queue agent (`agent/queue.py`) stays on `create_agent`.
- **A separate agent service (`agent/service.py` on `http://127.0.0.1:8002` or `UNDERCOVER_AGENT`) handles runs and resumes.** When a support agent signs off on the dashboard, the backend saves the review, marks the request `in_progress`, and notifies the agent service in the background to resume the paused thread and complete the request. Starting a run also resumes any request that was stopped mid-flight or signed off while the agent service was offline, without counting a new attempt.

## Phase 1: Refund calculation rules and Langfuse tracing

Bring in the deterministic calculation rules and Langfuse tracing first, before changing the database layer or replacing `create_agent`.

Add `backend/refunds.py` and `POST /api/requests/{request_id}/refund` (`operation_id="calculate_refund"`), which computes a step-by-step INR refund breakdown from the request's order record and Shoppie's policies (`docs/shopping-policy.md`, `docs/cancellation-policy.md`, `docs/returns-policy.md`) and records a `calculated_refund` progress step on the request:

- Sum the covered line items (capped at ordered quantities and line totals).
- Include the order's `delivery_fee` (₹49 on orders under ₹499) when cancelling a whole order before dispatch or when the issue is attributable to Shoppie for the whole order; leave delivery fees out of partial-order or change-of-mind item refunds.
- Deduct the sample `₹75` return pickup / handling fee (`75.0`) on eligible non-perishable change-of-mind returns or customer-attributable failed non-perishable deliveries, while keeping pickup free (`0.0`) for damaged, defective, missing, or incorrect items.
- Floor the total at `0.0` and return `{"calculation": [...], "refund": ..., "needs_sign_off": True}`.

Give the request agent a `calculate_refund` tool that calls this endpoint, and update `REQUEST_INSTRUCTIONS` in `agent/instructions.py` to use it when working out a refund. Add Langfuse tracing (`CallbackHandler` with `propagate_attributes(session_id=thread_id)`) to `agent/main.py` whenever `LANGFUSE_SECRET_KEY` and `LANGFUSE_PUBLIC_KEY` are set in the environment, and skip tracing cleanly when they are absent.

- [x] Unit and API tests verify `POST /api/requests/{request_id}/refund` for whole-order cancellation before dispatch, damaged-item partial refund (`REQ-7002`, ₹90 with free pickup), change-of-mind return with the ₹75 pickup fee (`REQ-7003`, ₹624 net), and missing perishable item (`REQ-7007`, ₹99), plus 404/409 guards when the request is missing or not `in_progress`.
- [x] Route tests confirm `calculate_refund` has an `operation_id`, a one-line docstring, and no optional query inputs.
- [x] Stub-model agent tests verify the request agent calls `calculate_refund` and records the `calculated_refund` step on the request.
- [x] Tracing unit tests verify that `CallbackHandler` and the request's `session_id` are attached when Langfuse keys are set, and that no network or Langfuse client call happens when `.env` / Langfuse keys are absent.
- [x] `npm run check:python` passes with at least 80% coverage.

## Phase 2: SQLAlchemy Core storage for SQLite and local Docker Postgres

Rewrite `backend/store.py` using SQLAlchemy Core (`MetaData`, `Table`, `Column`, `create_engine`, and Core `select`/`insert`/`update`/`delete` queries) so every query is written once and runs on both SQLite and Postgres:

- When `DATABASE_URL` is set in the environment (pointing to the local Docker Postgres container `postgresql://postgres:postgres@127.0.0.1:5432/postgres`), connect via `postgresql+psycopg://...`, ensure `CREATE SCHEMA IF NOT EXISTS undercover`, set `options="-c search_path=undercover"`, and limit the engine to at most 4 connections (`pool_size=2, max_overflow=2`).
- When `DATABASE_URL` is not set (including all automated unit/API/e2e tests), use the SQLite file at `SHOPPIE_DATABASE_PATH` or `data/shoppie.sqlite3`.
- Update `backend/seed.py` (`npm run seed`) to reset and reseed all tables (and clear checkpointer tables when on Postgres) idempotently on both backends.
- Make recommendation and completion operations idempotent ("Nothing happens twice"): repeating the same recommendation on a request that already has that recommendation succeeds and returns the request without adding a second recommendation or step, while a different recommendation on an already-recommended request is refused with 409. Repeating an identical completion/decision is treated as done, while a conflicting decision is refused with 409.

- [x] Store and API tests pass on SQLite with `DATABASE_URL` unset, verifying table creation, seeding, `reseed()`, queue listing, request context, steps, runs, and to-do lists.
- [x] Tests verify idempotency: sending the same recommendation twice returns 200 and stores only one recommendation; sending a different recommendation on a decided or already-recommended request returns 409.
- [x] Engine configuration tests verify that `DATABASE_URL` configures the `undercover` schema search path and caps total pooled connections per process at 4 or fewer.
- [x] `npm run check:python` passes with at least 80% coverage.

## Phase 3: The request agent as a hand-written LangGraph graph

Replace `create_agent` in `agent/main.py` with a synchronous hand-written `StateGraph` built in the style of `labs/week2day3.ipynb`, while keeping `agent/queue.py` on `create_agent`:

- Define `RequestState(TypedDict)` holding `messages` (with `add_messages`), `request_id`, `attempt`, `recommendation`, and `review`.
- Build five nodes and two conditional edges:
  - `agent`: invokes the model bound with `get_request_context`, `list_policy_sections`, `read_policy_section`, `calculate_refund`, and `record_progress` (with retry handling and a cap of 30 model calls).
  - `tools`: executes tool calls and returns any 4xx backend refusal messages to the model so it can recover.
  - `decide`: invokes `model.with_structured_output(Recommendation)` to produce the structured decision, checks that request context was retrieved and no unsupported execution claim was made, applies `apply_context_overrides`, and posts the recommendation to `POST /api/requests/{request_id}/recommendation` (which moves the request to `waiting_for_agent_review`).
  - `approval`: calls `interrupt({"request_id": state["request_id"], "recommendation": state["recommendation"]})` to pause the graph for support agent sign-off, and returns `{"review": answer}` when resumed with `Command(resume=...)`.
  - `complete`: calls `POST /api/requests/{request_id}/complete` (`operation_id="complete_request"`) to record the final confirmed resolution step (with who signed off and when) and transition the request from `in_progress` to `decided`.
- Compile the graph with `PostgresSaver` (connected with `autocommit=True, prepare_threshold=0, row_factory=dict_row, options="-c search_path=undercover"`) when `DATABASE_URL` is set, or an in-memory/SQLite checkpointer when `DATABASE_URL` is unset, and run every `.invoke(...)` with `durability="sync"`.

- [x] Stub-model tests verify the graph runs `agent -> tools -> decide -> approval`, saves the recommendation, moves the request to `waiting_for_agent_review`, and pauses at `interrupt()` with `state.next == ("approval",)`.
- [x] Stub-model tests verify resuming the paused thread with `Command(resume={"outcome": "approve", "notes": "...", "reviewed_by": "Priya Nair", "reviewed_at": "..."})` runs `complete`, transitions the request to `decided`, and records who signed off and when.
- [x] Stub-model tests verify that a second resume or duplicate `complete` call does not record a second decision or duplicate step.
- [x] Stub-model tests verify tool refusal messages are returned to the model and a runaway loop stops after 30 model calls.
- [x] `npm run check:python` passes with at least 80% coverage.

## Phase 4: Crash recovery, sign-off resume, and the agent service

Add the agent web service (`agent/service.py`) and wire up restart survival and sign-off resumption across the backend and agent:

- **Sign-off handoff (`POST /api/requests/{request_id}/review`):**
  - `ReviewInput` takes `outcome`, `notes`, and `reviewed_by` (all required, no optional inputs).
  - Recording a review on a `waiting_for_agent_review` request stores `review_json` (`outcome`, `notes`, `reviewed_by`, `reviewed_at`), records a `signed_off` step, and moves `queue_status` to `in_progress` while the agent finishes the request. (If the request was `left_for_support` with no agent recommendation thread to resume, recording the review completes it immediately to `decided`.)
  - After saving the review, the backend schedules a background call to `POST {UNDERCOVER_AGENT}/requests/{request_id}/resume` (where `UNDERCOVER_AGENT` defaults to `http://127.0.0.1:8002`). If the agent service is unreachable, the saved review stands and the request stays `in_progress` with its saved review until the next agent run picks it up.
- **Work survives a restart:**
  - Startup no longer resets `in_progress` requests to `waiting`.
  - If a request was stopped partway through an attempt (its status is `in_progress` and its checkpoint exists in the checkpointer), `work_request` resumes the existing thread (`request-{request_id}-attempt-{attempt}`) with `graph.invoke(None, config, durability="sync")` from its last checkpoint instead of starting a new attempt.
  - If a request fails with an unhandled error, `work_request` clears the failed checkpoint and calls `POST /api/requests/{request_id}/failure` so the next attempt starts afresh on a new attempt number, or leaves the request for support on its second failure.
  - Before working new `waiting` requests, a queue run (`run_queue` / `uv run -m agent`) first resumes any `in_progress` requests (both those signed off while the agent was away and those interrupted partway through) and finishes any stopped run.
- **Agent service (`agent/service.py`) and `npm run dev`:**
  - FastAPI app in `agent/service.py` exposing `GET /health`, `POST /requests/{request_id}/resume`, and `POST /runs`.
  - Update `package.json` so `npm run dev` starts `backend`, `agent` (`uv run -m uvicorn agent.service:app --port 8002`), and `dashboard` using Windows-compatible commands.

- [x] Stub-model test: stopping a request partway through (after tool calls, before `decide`) and running `work_request` again carries on from the last checkpoint on the same thread, keeps `attempts == 1`, does not re-run earlier steps, and produces a single recommendation.
- [x] Stub-model test: a request that raises an error goes back to `waiting` with `attempts == 1` and starts afresh on attempt 2.
- [x] API and service tests: signing off on a held request saves the review, sets status to `in_progress`, notifies the agent service, and transitions the request to `decided` with `reviewed_by` and `reviewed_at` recorded.
- [x] API and service tests: when the agent service is unreachable at sign-off time, the review still succeeds (200) and the next agent run picks up the signed-off request and finishes it.
- [x] `npm run check:python` passes with at least 80% coverage.

## Phase 5: Dashboard sign-off updates and end-to-end tests

Update the React dashboard (`dashboard/src/`) and Playwright end-to-end suite (`e2e/`) for the durable review workflow:

- Add a required `Reviewed by` input to `ActionPanel` (`dashboard/src/components.tsx`) so the support agent records their name alongside the reviewed outcome and notes when signing off.
- Show who signed off (`reviewed_by`) and when (`reviewed_at`) in `ReviewRecord`, and display the `in_progress` state between sign-off and agent completion while polling continues until the request reaches `decided`.
- Update `e2e/dashboard.spec.ts` and `playwright.config.ts` so the end-to-end suite runs a stand-in agent service on port `8003` (`UNDERCOVER_AGENT=http://127.0.0.1:8003`) and verifies that signing off on the dashboard reaches the stand-in service on port 8003 without touching port 8002.

- [x] Vitest tests (`dashboard/src/App.test.tsx`) verify the `Reviewed by` field, submitting a sign-off, polling while `in_progress` after sign-off, and displaying the reviewer's name and time once `decided`.
- [x] Playwright tests (`e2e/dashboard.spec.ts`) verify that signing off on a held request on the dashboard sends the review to the backend, which calls the stand-in agent service on port 8003, and that the UI updates to show the completed review.
- [x] `npm run check` passes with `.env` moved out of the way (no Postgres container, Langfuse, or OpenRouter needed).

## Phase 6: Local Docker Postgres container, live verification, and documentation

Start the local Docker Postgres container, set `DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/postgres` in `.env`, reseed Postgres, run the live verification checks with a 5-request cap, and update the documentation to match the finished build:

- Start the local `shoppie-postgres` Docker container (`postgres:17-alpine` on `127.0.0.1:5432`) and run `npm run seed` with `DATABASE_URL` set so the `undercover` schema in Postgres is freshly seeded.
- Start `npm run dev` and run a queue run capped at 5 requests on the default model.
- Sign off on a held request in the dashboard via the Playwright MCP server and verify it completes within 5 seconds.
- Verify crash recovery by stopping a run after a request's first steps and confirming the next run resumes the same thread with `attempts` unchanged and one decision.
- Check `pg_stat_activity` in the local Postgres container (`usename = 'postgres'`) and the request's session traces in Langfuse (when Langfuse keys are configured).
- Update `docs/SPEC.md` (working the queue), `docs/TECH_STACK.md`, `docs/PROCESS.md`, and `docs/STATUS.md`.

- [x] With `.env` moved aside, `npm run check` passes Python, TypeScript, and Playwright checks offline.
- [x] After starting the local Docker Postgres container and running `npm run seed`, a live run capped at 5 requests works 5 requests; signing off on a held request in the browser via Playwright completes it within 5 seconds with the reviewer and timestamp shown.
- [x] A live run stopped after a request's first steps resumes the same thread on the next run with `attempts` unchanged and one recommendation.
- [x] During the live run, querying `pg_stat_activity` (`usename = 'postgres'`) in the local Postgres container shows no more than 12 connections.
- [x] When Langfuse keys are configured, the signed-off request's session contains traces from both before and after the sign-off.
- [x] `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/PROCESS.md`, and `docs/STATUS.md` describe the product as built, and `git diff --check` passes.
