# Tech stack

- `backend/`: FastAPI and SQLite. Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount. The backend also holds the runs and their to-do lists, the recovery rules (attempts, requeue, left for a handler), the steps and sections read on each claim, and the lookup of the claims manual and policy wording by section. `backend/instructions/` holds the agent's instructions.
- `agent/`: LangChain's `create_agent` on OpenRouter, with no other agent framework. A queue-runner agent plans the to-do list and hands each claim to a fresh claim subagent, one at a time. Its entry point is `run(cap, claim_id)`, started from the command line with `agent.cli`. It reaches claims, the manual and its instructions only through the backend's API. A middleware records every tool call as a step on the claim. It uses `deepseek/deepseek-v4.1-flash` with low reasoning effort by default, or the model in the environment variable `MODEL_NAME` if set, such as `openrouter/free`. Provider calls have a timeout and retries.
- `dashboard/`: React, Vite and TypeScript, with pages for the queue, a claim and the instructions, chosen by the URL hash.
- `e2e/`: Playwright tests. They run against a separate seeded database and never call a model.
- `data/`: the business data the backend starts from. The agent never sees `data/evals/`, which holds the answer key.

Tests never call a model: agent tests use a scripted stub model.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.
