# Shoppie harness plan

This plan builds `docs/HARNESS.md`. The course's brief was written for UnderCover's insurance claims; `docs/HARNESS.md` is its Shoppie version, with requests in place of claims, support agents in place of handlers, Shoppie's three policies in place of a claims manual, and a support agent's review of every recommendation in place of sign-off on large payouts.

Today, code runs the agent on one request at a time (`run_queue_in_background`), and each run gets the whole policy for that request type. A request that fails is moved to support review and isn't retried. After this build, a **queue agent** plans the run as a to-do list and chooses the order of requests. It hands each request to a **request agent**, a subagent with a clean thread, which looks up only the policy sections it needs and reports back in one line. Code applies the rules that must not depend on a model: the cap, the attempt count, the one-recommendation guarantee and the check for missed requests.

Approach and why:

- **The subagent is a tool.** The queue agent's `work_request` tool calls `agent.main.run_request(...)` with a new thread id for each attempt and returns a one-line report. The queue agent's context grows by one line per request, not by every step taken on that request, so later steps cost no more than earlier ones. This is LangChain's `create_agent` called from a tool. The brief asks for no other agent framework, so none is added.
- **Retries happen at two levels.** LangChain's `ModelRetryMiddleware` and `ToolRetryMiddleware` handle short glitches such as timeouts and provider errors. When a request still fails, the backend counts the attempt. After the first failure the request goes back to waiting. After the second it's left for a support agent. These counts live in the database, so they don't depend on the model remembering them.
- **The cap and the missed-request check are in code.** `work_request` refuses to work more requests than the run's cap. An `after_agent` middleware hook checks for waiting requests the run could still take within its cap and sends the queue agent back to work on them. The agent can't finish early by mistake.

The pilot's rules stay as they are: no real cancellations, returns, refunds or customer messages, and a support agent confirms every decision. Tests never call a model.

## Phase 1: Runs, attempts and the to-do list in the backend

Add the records the harness needs. A `runs` table holds each run's id, cap, status (`running`, `finished`, `failed`), start and finish times, and summary. A `run_todos` table holds the run's to-do items: request id, title, and a status of `to_do`, `in_progress`, `done` or `left_for_support`. Add an `attempts` count to `support_requests`. `fail_run` changes: on the first failure the request goes back to `waiting` with an `error` step and `attempts = 1`. On the second it moves to `waiting_for_agent_review` with no recommendation and a `left_for_support` step. `save_recommendation` keeps its `in_progress` guard and refuses a request that already has a recommendation, and `record_review` refuses a second review, so a request is never recommended or reviewed twice. When the backend starts, any request left in progress goes back to waiting and any run left running is marked failed, so a restart never leaves a request stuck. Add `npm run seed` (`uv run -m backend.seed`), which rebuilds the database from `data/customer_orders.json`.

New operations, each with an `operation_id`, a one-line docstring and no optional inputs:

- `POST /api/runs` with `{"cap": n}` (`start_run`) creates a run and starts the queue agent in the background. It refuses with 409 while another run is running.
- `GET /api/runs/current` (`get_current_run`) returns the latest run with its to-do list.
- `PUT /api/runs/{run_id}/todos` (`write_run_todos`) replaces the run's to-do list.
- `POST /api/runs/{run_id}/todos/{request_id}` (`update_run_todo`) sets one item's status, so code can tick off an item whatever the model does.
- `GET /api/requests/waiting` (`list_waiting_requests`) returns the ids, types and creation times of waiting requests, and nothing else.
- `POST /api/requests/{request_id}/start` (`start_request`), `POST /api/requests/{request_id}/recommendation` (`save_recommendation`) and `POST /api/requests/{request_id}/failure` (`record_failure`) let the agent start a waiting request, store its one recommendation, or count a failed attempt, all through the API.

The run's summary is the queue agent's final message, which the backend stores when the run ends, so no finish operation is needed. `POST /api/requests/run`, `POST /api/requests/{request_id}/run` and `run_queue_in_background` go, replaced by `start_run`; one named request is worked from the terminal (Phase 4). Until the queue agent arrives in Phase 4, `start_run` works waiting requests in order up to the cap.

- [x] Store tests: a first failure returns a request to `waiting` with `attempts = 1`. A second failure leaves it in `waiting_for_agent_review` with a `left_for_support` step and no recommendation.
- [x] A store test shows `save_recommendation` on a request that already has a recommendation, or is decided, changes nothing.
- [x] API tests: `POST /api/runs` returns a run id. A second start while one is running returns 409. The to-do list round-trips through `PUT /api/runs/{id}/todos` and `GET /api/runs/current`.
- [x] An API test confirms `list_waiting_requests` returns only waiting requests, with no customer or order fields.
- [x] `npm run seed` rebuilds the database with all eight requests waiting.
- [x] The existing route test confirms every operation has an `operation_id`, a one-line docstring and no optional inputs (the review's notes become required).
- [x] `npm run check:python` passes with 80% coverage.

## Phase 2: Policies looked up by section

The context operation stops including the whole policy. Two new operations let the request agent look up what it needs:

- `GET /api/policies` (`list_policy_sections`) returns each policy's name and its section headings, parsed from the `##` and `###` headings in `docs/*-policy.md`.
- `GET /api/requests/{request_id}/policies/{policy}/sections/{section}` (`read_policy_section`) returns one section's text and records a `read_section` step on the request, for example "Read Cancellation Policy, 2. Customer-requested cancellations". This is the only way the agent reads policy text, so the request page lists exactly what it read.

`backend/policies.py` becomes a small section parser: a section's id is its heading in lower case with dashes, such as `2-customer-requested-cancellations`, and a `##` section includes its `###` subsections. `policy_for_request_type` goes. Phases 2 and 3 are committed together, because the request agent depends on the context it loses here.

- [x] Parser tests: each of the three policies yields the headings in its file. An unknown policy or section returns 404.
- [x] An API test reads one section for `REQ-7001` and the request's steps then include that section's name.
- [x] An API test confirms `GET /api/requests/{id}/context` no longer contains policy text.
- [x] A test confirms `read_policy_section` on a request that isn't in progress is refused with 409 and records no step.
- [x] `npm run check:python` passes with 80% coverage.

## Phase 3: The request agent as a subagent

Refactor `agent/main.py` so that `run_request(request_id, thread_id, llm)` is the request agent: its tools are `get_request_context`, `list_policy_sections`, `read_policy_section` and `record_progress`, and its output is the same structured `Recommendation`, with the existing safety checks in `agent/safety.py`. It gets `ModelRetryMiddleware` and `ToolRetryMiddleware` for timeouts and provider errors. `work_request(request_id)` wraps it: it starts the request in the backend, calls `run_request` on the thread `request-<id>-attempt-<n>`, saves the recommendation or records the failure, and returns one line, such as `REQ-7003: request_information (needs the customer to confirm scope)` or `REQ-7005: failed, back in the queue (attempt 1 of 2)`.

The default model becomes `deepseek/deepseek-v4.1-flash` with low reasoning effort. `MODEL_NAME` still overrides it and runs with no reasoning effort set. The request agent's instructions move to `agent/instructions.py` as `REQUEST_INSTRUCTIONS`, rewritten from the policies to tell the agent to look up only the sections it needs. They're never written from `data/evals/`.

- [x] Stub-model tests: the request agent lists sections, reads at least one and returns each outcome (approve, decline, request information), with citations that match sections it read.
- [x] A stub-model test: a model error on the first try that succeeds on retry gives one recommendation, through `ModelRetryMiddleware`.
- [x] `work_request` tests: a success returns the one-line report and stores the recommendation. A failure returns the request to waiting. A second failure leaves it for support. No test calls a live model.
- [x] The existing safety tests still pass: the food-safety flag, ambiguous cancellation scope, and the check that the agent never claims an action happened.
- [x] A test confirms the default model is `deepseek/deepseek-v4.1-flash` with low reasoning effort, and that `MODEL_NAME` overrides it with none.
- [x] `npm run check:python` passes with 80% coverage.

## Phase 4: The queue agent

Add `agent/queue.py`, the queue agent: `create_agent` with the tools `list_waiting_requests`, `write_todos` (which stores the run's to-do list through the backend) and `work_request`. Its final message is the run's summary, which the backend stores. `work_request` also ticks the request's to-do item itself (in progress, then done, left for support, or back to do), so the list on the dashboard is right even if the model forgets to update it. Its instructions, `QUEUE_INSTRUCTIONS`, tell it to plan the run as a to-do list, choose an order, hand each request to `work_request`, keep the list up to date, and finish with a short summary for support agents.

Code enforces the rules:

- `work_request` refuses a new request once the run has worked `cap` requests, and refuses a request that isn't waiting without using up the cap. A retry of a request already in the run doesn't count again.
- An `after_agent` middleware checks `list_waiting_requests` against what's left of the cap. If the run missed a request, it sends the agent back with a message naming the request. If the run is still short after three returns, the run is marked failed.
- An exception from one request never escapes `work_request`, so one bad request can't stop the run.

The backend's `start_run` runs the queue agent in the background. `uv run -m agent --cap 5` starts a capped run from the terminal, and `uv run -m agent REQ-7001` works one named request with the request agent alone. `GET /api/agent/instructions` returns both sets of instructions.

- [x] Stub-model tests: a run capped at 2 of 8 works exactly 2 requests and leaves 6 waiting. A third `work_request` call is refused.
- [x] A stub-model test: a request that raises does not stop the run, and the next request is worked.
- [x] A stub-model test: a request that fails once goes back to waiting, is worked again in the same run, and gets one recommendation.
- [x] A stub-model test: a request that fails twice is left for support, its to-do item shows `left_for_support`, and the run still finishes.
- [x] A stub-model test: a queue agent that tries to finish with a waiting request within its cap is sent back and works it.
- [x] A stub-model test: the to-do list is stored and updated as items are worked.
- [x] An API test: `GET /api/agent/instructions` returns the queue and request instructions, with no edit operation.
- [x] `npm run check:python` passes with 80% coverage.

## Phase 5: The dashboard

On the queue page, Initiate processing gets a number input for the cap, 1 to 8 with 5 to start with, and calls `POST /api/runs`. A to-do panel beside the queue polls `GET /api/runs/current` while a run is going. It shows each item with its status (to do, in progress, done, left for support), using the brand's three-state colors, then the run summary when the run finishes. The request page shows the policy sections the agent read, from its `read_section` steps. The instructions view shows the queue agent's and the request agent's instructions under separate headings, read only. Requests left for support show a "Left for support" badge in the queue.

- [ ] Vitest tests cover the cap input, starting a run, the to-do panel in each item state and the summary, a 409 when a run is already going, the sections-read list, and both instruction sets.
- [ ] Playwright, with the queue agent stubbed: start a capped run, see the to-do list fill in and get ticked off, and open a request to see the sections it read. Checked at desktop and mobile widths.
- [ ] Playwright confirms the instructions view has no edit control.
- [ ] `npm run check:ts` and `npm run e2e` pass.

## Phase 6: Live check and documents

Update `docs/SPEC.md` ("What the team needs to see": the to-do list and the sections read; working the queue in one capped run), `docs/TECH_STACK.md` (the queue agent and request subagent, the middleware, the default model) and `docs/STATUS.md`. Leave the Rules in `docs/SPEC.md` alone. Then run the product on the default model.

- [ ] `npm run seed`, then a run capped at 5 from the dashboard works 5 requests on its own. The to-do list fills in and gets ticked off, each request's page shows its steps and the sections it read, and 3 requests stay waiting.
- [ ] No request in that run has more than one recommendation, and none is marked decided without a support review.
- [ ] `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` describe the product as it now is.
- [ ] `npm run check` is green, and `git diff --check` passes.
