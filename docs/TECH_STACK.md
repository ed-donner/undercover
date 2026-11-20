# Tech stack

- `backend/`: FastAPI and SQLite. Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount.
- `agent/`: LangChain's `create_agent` on OpenRouter, with `run_queue(run_id, thread_id)` for planning/delegation and `run(claim_id, thread_id)` for a fresh claim helper. Both reach business data, instructions, tasks and activity only through the backend's API. The default is `deepseek/deepseek-v4.1-flash` with low reasoning effort; `MODEL_NAME` overrides it, such as `openrouter/free`. Small middleware handles bounded retries, public activity and queue ownership; no additional agent framework.
- The backend stores parent runs, ordered tasks, child attempts and source reads in SQLite with additive migrations. It enforces caps, attempt budgets, write deadlines, completion checks and financial rules. Document lookup uses a section catalog and deterministic keyword search over allowlisted wording/manual files, without a vector database. Agent payments carry an active attempt ID; handler sign-off and payment remain separate operations.
- `dashboard/`: React, Vite and TypeScript.
- `e2e/`: Playwright tests.
- `data/`: the business data the backend starts from. The agent never sees `data/evals/`, which holds the answer key.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.
