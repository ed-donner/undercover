# Tech stack

- `backend/`: FastAPI and SQLite, which also holds the runs of the queue agent, their to-do lists and each claim's failures. Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount.
- `agent/`: LangChain's `create_agent` on OpenRouter, in two agents of our own, with no other agent framework. The queue agent (`queue_agent.py`) plans a run as a to-do list and hands each claim to a claim agent (`claim_agent.py`), a fresh agent for each claim. Both use LangChain's retry and call-limit middleware, and the queue agent has a hook that stops it finishing while it has missed a waiting claim (`harness.py` holds what they share). They reach claims, the wording and the manual by section, and their instructions only through the backend's API. The default model is `deepseek/deepseek-v4.1-flash` with low reasoning effort, or the model in the environment variable `MODEL_NAME` if set, such as `openrouter/free`.
- `dashboard/`: React, Vite and TypeScript.
- `e2e/`: Playwright tests.
- `data/`: the business data the backend starts from. The agent never sees `data/evals/`, which holds the answer key.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.
