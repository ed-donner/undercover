# Tech stack

- `backend/`: FastAPI and SQLite. Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount.
- `agent/`: two agents on LangChain's `create_agent` on OpenRouter. The queue agent's entry point takes a cap and a list of claim ids, either of which can be left out on the command line, and it hands each claim to the claim agent, whose entry point takes a claim id and a thread id. They reach claims and their instructions only through the backend's API. They use DeepSeek V4.1 Flash (`deepseek/deepseek-v4.1-flash`) with low reasoning effort by default, or the model in the environment variable `MODEL_NAME` if set, such as `openrouter/free`. LangChain's middleware retries failed model and tool calls and limits the model calls each agent can make.
- `dashboard/`: React, Vite and TypeScript.
- `e2e/`: Playwright tests.
- `data/`: the business data the backend starts from. The agent never sees `data/evals/`, which holds the answer key.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.
