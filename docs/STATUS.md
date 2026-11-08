# Status

The Shoppie pilot is implemented:

- `backend/`: health, SQLite seed and repository, request list/detail, policy context, read-only instructions, agent-run/progress APIs, a run-all API that clears earlier agent work and reviews and runs the agent on every request in turn, and support review API. Every request starts as waiting, with no pre-recorded action results or request history.
- `agent/`: Shoppie Agent with request-bound context/progress tools, structured recommendations, and safety overrides for ambiguous cancellation and food-safety cases. Its instructions require it to consider customer messages, supplied evidence, relevant history, order facts, and policy; distinguish reported claims from recorded facts; and request missing information rather than guess.
- `dashboard/`: responsive support queue and request detail screens, an Initiate processing button that runs the agent on the whole queue, queue badges showing each request's agent decision (Approve, Decline, Needs info) or reviewed outcome, agent progress/recommendations, support review, and read-only instructions
- `data/`: synthetic Shoppie customer, order, and support request records, including clearly labeled synthetic follow-ups, photo, packing, delivery and carrier evidence for every request, and a fulfillment timeline (plus shipment tracking once dispatched) on every order. Food and perishable cases are limited to the leafy greens cancellation and the missing bread report; the food-safety guardrail is covered by a unit test fixture. Existing local databases refresh request and order records from the source data at startup.
- `docs/`: Shoppie's sample shopping, cancellation, and returns policies
- `data/evals/`: reference decisions kept separate from agent-readable data

The backend, Shoppie Agent workflow, and support dashboard are implemented. The dashboard displays INR values and IST times for the synthetic records. Agent recommendations support review; the pilot does not execute real customer or order actions. Run `uv sync` and `npm install` at the repository root, then `npm run dev`.

## Harness build (in progress, `docs/PLAN_HARNESS.md`)

- Phase 1: runs with a cap and a to-do list, attempt counting (a failed request goes back to the queue once, then is left for support), one recommendation and one review per request, recovery at startup, and `npm run seed`. The dashboard's Initiate processing button is rewired in Phase 5.
- Phases 2 and 3: the request agent is a subagent with a clean thread per attempt. It looks up policy sections (`GET /api/policies`, `read_policy_section`), and each section it reads is recorded on the request. It retries model and network errors with LangChain's retry middleware and reports back in one line. The default model is DeepSeek V4.1 Flash.
