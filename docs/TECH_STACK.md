# Tech stack

- `backend/`: FastAPI and SQLite, which holds all state: claims, steps, runs, to-do lists and attempts. The rules (one decision, one payment, sign-off over $1,000, retries) are enforced here, not in the agent. Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount.
- `agent/`: LangChain's `create_agent` on OpenRouter, our own code and no other agent framework. A queue agent plans a to-do list and hands each claim to a fresh claim agent (a subagent with a clean start); both reach claims, the claims manual, the policy wording and their instructions only through the backend's API. It uses `deepseek/deepseek-v4.1-flash` with low reasoning effort by default, or the model in the environment variable `MODEL_NAME` if set, such as `openrouter/free`. Entry points: `run(claim_id, thread_id)` for one claim and `run_queue(limit, thread_id)` for a run; `uv run -m agent --limit 5` or `--claim CLM-1001`.
- `dashboard/`: React, Vite and TypeScript.
- `e2e/`: Playwright tests.
- `data/`: the business data the backend starts from. The agent never sees `data/evals/`, which holds the answer key.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.
