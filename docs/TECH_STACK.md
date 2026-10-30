# Tech stack

- `backend/`: FastAPI and SQLite. Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount. The policy wording and the claims manual are split into their headed sections at load time, read by section rather than handed over whole. A run's to-do list (one row per claim it works, with its status and attempts) lives in SQLite alongside claim status.
- `agent/`: two LangChain `create_agent`s on OpenRouter, both reaching claims, documents and instructions only through the backend's API. `agent/main.py`'s `run(claim_id, thread_id)` decides one claim from a clean start. `agent/queue.py`'s `run_queue(cap=None)` is the orchestrator: it starts a run over the waiting claims (capped if asked), then works through the to-do list, handing each claim to a fresh `run()` subagent. Retries, giving up after two failed attempts, and the check that a run can't finish early are deterministic Python, not left to the model. `agent/cli.py` starts either from the command line. The default model is `deepseek/deepseek-v4.1-flash` at low reasoning effort, or the model in the environment variable `MODEL_NAME` if set, such as `openrouter/free`.
- `dashboard/`: React, Vite and TypeScript.
- `e2e/`: Playwright tests.
- `data/`: the business data the backend starts from. The agent never sees `data/evals/`, which holds the answer key.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.
