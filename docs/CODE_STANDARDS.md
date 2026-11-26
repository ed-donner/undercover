# Code standards

1. Keep it simple, do not overcomplicate.
2. Comments only when necessary.
3. Be concise: a short README and no emojis.
4. IMPORTANT: avoid overly defensive code. Handle exceptions only when necessary.
5. Use uv: ALWAYS `uv run`, NEVER `python3`.
6. TypeScript: strict mode, never `any`.

## Module boundaries

- Entry points compose dependencies and invoke services; other agent modules must not import `main.py` or `queue.py`.
- `agent/api.py` owns backend URLs, client creation and HTTP calls. Expose named operations, encode path identifiers and propagate unexpected errors. No backend imports, direct database access or arbitrary HTTP/file tools in the agent.
- `agent/harness.py` owns `create_agent` and invocation configuration, not claim assessment, delegation or financial rules. Keep those in domain services and compose tools/middleware at entry points.
- Define every model-visible tool in `agent/tools.py`. Inject dependencies and trusted scope through `context_schema=RunContext` and `ToolRuntime`; never bind tools to mutable closures or accept trusted run/attempt IDs from the model. Invocation state belongs in the graph state schema, updated through `Command`, not global/shared flags.
- Keep FastAPI handlers thin in `backend/routes/`, SQL and workflow rules in services, and app/lifecycle composition in `backend/main.py`. Shared contracts must not depend on an unrelated domain. Name SQL insert columns; never rely on model-field order matching table order.
- `dashboard/src/api.ts` owns transport, route strings and named endpoint operations. Components use those operations and typed callbacks, not endpoint suffixes. Keep polling hooks separate from transport and split components by responsibility, not merely to satisfy a lint limit.
- Use structured fields for program decisions; never parse human-readable summaries or reasons for failure status.

## Agent instructions

- State the goal, authoritative sources, expected result and authority/privacy boundaries. Let the agent choose the investigation and work order; do not turn the prompt into a numbered tool-call script or duplicate source-document rules.
- Enforce caps, ownership, financial constraints and completion in backend code. Prompts and disabled UI controls are not safeguards.
- Check observable behavior with stub models, and record real-model smoke tests separately. Stub tests cannot establish prompt effectiveness or decision accuracy.
