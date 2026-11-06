# Shoppie pilot plan

Build the pilot in six phases, from the data layer outward. The starter data contains eight synthetic customers, orders, and support requests. Recommendations will follow the sample shopping, cancellation, and returns policies; support agents remain responsible for decisions and actions.

The pilot will not send customer messages or execute cancellations, returns, replacements, or refunds. It will have no sign-in. Reference decisions under `data/evals/` stay out of the queue, agent context, and runtime API.

## Phase 1: Seed the request queue and expose records

Turn `data/customer_orders.json` into the application's source of truth. Add a small SQLite-backed repository, initialize it idempotently from the synthetic records, and expose the request queue and request detail through FastAPI. Map source records to the four queue states in the spec: waiting, in progress, waiting for agent review, and decided. Keep any original source status only for import/mapping; exclude harness annotations such as `intent_summary`, `reason_code`, `required_action`, `policy_checks`, and `prohibited_actions` from agent context so they do not disclose expected behavior. Return only fields handlers need to process the request.

- [x] A backend seed test loads all eight requests and their order/customer links; running initialization a second time does not duplicate records.
- [x] API tests verify `GET /api/requests` returns eight request summaries and `GET /api/requests/REQ-7001` returns its request, order, and limited customer details.
- [x] API tests verify an unknown request ID returns 404 and every route has an `operation_id`, a one-line docstring, and no optional inputs.
- [x] The agent-facing repository and API expose no reference decisions or files from `data/evals/`.
- [x] `uv run pytest -q` passes with the configured 80% coverage threshold.

## Phase 2: Serve policy context and read-only instructions

Add backend operations that return the minimum request context the agent needs: its customer request, order state and item details, relevant request history, and the applicable policy text. Add a read-only operation for the current agent instructions. Select the shopping, cancellation, or returns policy by request type, and avoid returning unrelated customer fields.

- [x] API and policy-selection tests verify cancellation requests receive the cancellation policy, return/refund requests receive the returns policy, and order questions can receive the shopping policy.
- [x] API tests verify context responses omit unrelated contact data and contain no reference decision fields.
- [x] API tests verify the instructions operation returns the configured prompt without allowing edits.
- [x] `uv run pytest -q` passes with the configured 80% coverage threshold.

## Phase 3: Run the Shoppie Agent and record recommendations

Replace the health-check-only agent behavior with a request workflow. Keep `run(request_id, thread_id)` as the entry point, retrieve records and policies through backend API tools, and return a structured recommendation: approve, decline, or request information. Persist the recommendation and policy citations, but leave the request in waiting-for-agent-review after the agent finishes; only a support agent can mark it decided. Start work through a backend operation and record progress steps as the agent works so the dashboard can display them. Use a stub model in tests.

- [ ] Agent tests cover each recommendation outcome, policy citations, missing context, and a tool-call path using a stub model; no test calls a live model.
- [ ] A backend test runs a request and verifies it moves from waiting to in progress and then to waiting for agent review with a stored recommendation.
- [ ] An API test verifies `POST /api/requests/REQ-7001/run` starts work and returns an in-progress response; `GET /api/requests/REQ-7001` then exposes the saved recommendation and ordered progress steps.
- [ ] Tests verify a model or tool error leaves the request available for agent review and does not record an unsupported decision.
- [ ] `uv run pytest -q` passes with the configured 80% coverage threshold.

## Phase 4: Build the support queue and request detail screens

Replace the health placeholder with the handler dashboard. Show all requests, their order reference, request type, time, and queue state. Selecting a row opens the full request, the order details needed to assess it, the recommendation and policy reasons, and the progress timeline. Provide a clear way to start or retry agent work where appropriate, and let a support agent record a reviewed outcome to move the request to decided. Keep agent instructions visible in a read-only view.

- [ ] Vitest tests cover loading, empty, and backend-error states; queue rows; request selection; recommendation display; and read-only instructions.
- [ ] The Playwright browser check opens the queue and shows all eight seeded requests with their states.
- [ ] The Playwright browser check opens `REQ-7001`, shows its order and customer request, starts agent work, and displays progress and the resulting recommendation.
- [ ] The Playwright browser check confirms the instruction text can be read and has no edit control.
- [ ] A support-agent review API test records a reviewed outcome and changes the queue state to decided without recording an external customer action.
- [ ] `npm run check:ts` passes.

## Phase 5: Enforce the support and safety boundaries

Apply the sample policies to the seeded request types and edge cases. Keep customer confirmation, policy exceptions, food-safety concerns, and insufficient information with a support agent. Recommendations must never imply that a real order or payment action was completed. Keep the agent's context restricted to backend operations and the minimum customer/order data needed.

- [ ] Tests verify a request that needs clarification is held for agent review and that a food-safety report is flagged for priority human review.
- [ ] Tests verify no API operation or dashboard action executes a cancellation, return, replacement, refund, or customer message.
- [ ] Tests verify the agent does not claim an action succeeded without a confirming system result and does not guess when request or policy data is missing.
- [ ] API and agent tests verify customer/order context is limited to the fields needed for the request.
- [ ] `uv run pytest -q` passes with the configured 80% coverage threshold.

## Phase 6: Integrate, verify, and document the pilot

Connect the queue, backend, agent, and dashboard; refine loading and error states; and document the data and local run instructions. Confirm the synthetic policies are clearly treated as sample business rules and amounts/times display as INR/IST. Update `docs/STATUS.md` when the pilot is complete.

- [ ] `npm run check` passes Python formatting/lint/type checks and tests, TypeScript formatting/lint/type checks and tests, and Playwright end-to-end tests.
- [ ] The browser workflow covers the queue, request detail, progress timeline, recommendation, and read-only instructions at desktop and mobile widths.
- [ ] A final API check confirms the queue contains eight seeded requests and no reference decisions are available through runtime routes.
- [ ] `git diff --check` passes, and `docs/STATUS.md` describes the implemented Shoppie pilot and its run command.
