# Tech stack

- `backend/`: FastAPI and SQLite. Every API operation has an `operation_id`, a one-line docstring and no optional inputs. The pilot recommends support outcomes; it does not execute cancellations, returns, or refunds.
- `agent/`: LangChain's `create_agent` on OpenRouter, with one entry point that takes a support request id and a thread id. It reaches customer/order/request data and its instructions only through the backend's API. It uses `openai/gpt-6-luna` with low reasoning effort by default, or the model in the environment variable `MODEL_NAME` if set, such as `openrouter/free`.
- `dashboard/`: React, Vite and TypeScript.
- `e2e/`: Playwright tests.
- `data/`: Shoppie's synthetic customer, order, and support request data. The agent never sees `data/evals/`, which holds reference decisions for evaluation.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.
