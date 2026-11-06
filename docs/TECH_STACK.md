# Tech stack

- `backend/`: FastAPI and SQLite. Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount.
- `agent/`: LangChain's `create_agent` on OpenRouter, with one entry point that takes a claim id and a thread id. It reaches claims and its instructions only through the backend's API. It uses DeepSeek V4.1 Flash (`deepseek/deepseek-v4.1-flash`) with low reasoning effort by default, or the model in the environment variable `MODEL_NAME` if set, such as `openrouter/free`. LangChain's middleware retries failed model and tool calls and limits the model calls an agent can make.
- `dashboard/`: React, Vite and TypeScript.
- `e2e/`: Playwright tests.
- `data/`: the business data the backend starts from. The agent never sees `data/evals/`, which holds the answer key.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.
