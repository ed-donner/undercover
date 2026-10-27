# Plan: the harness

The brief in `docs/HARNESS.md`, built on our own pilot: one run works the queue under a cap, with a to-do list the team can watch; each claim goes to a fresh claim agent; the agent looks up the claims manual and the wording section by section; failures are put right on their own; and the instructions say what to achieve, not how. On top of the brief, at the student's request: every host, port, URL and model moves into configuration, the agent can run on OpenRouter, Anthropic or a local Ollama model, the dashboard shows and picks the model, every model call's tokens, cost and time are recorded, and an experiment compares models on accuracy, tokens and speed.

## Approach

- **Clean code first.** `docs/CODE_STANDARDS.md` gains Ed's rules from his Day 5 review and stricter ones of ours, and tests enforce what can be enforced: one owner for each service's address, operations named the same everywhere, page links in one place, short modules, and no configuration written in code. Phase 1 brings the pilot up to them before anything is added, and a fresh reviewer checks every phase.
- **The agent in three parts and its settings.** `agent/api.py` is the backend's API, `agent/tools.py` holds every tool and the contexts they read, `agent/harness.py` builds and runs the agents, and `agent/config.py` reads the settings and `models.toml`. A claim agent's tools take the claim from `ToolRuntime`, so the model can't act on another claim. LangChain middleware records each reply, tool call and tool result, and gives the backend's refusals back to the model as text.
- **Configuration.** `.env.defaults` (committed) holds every setting that isn't secret; `.env` holds the keys and personal overrides and wins over it; the environment wins over both. `models.toml` lists the models allowed, with their prices and the options for their LangChain class. Tests and the end-to-end run read `.env.defaults` alone.
- **Models.** `MODEL_NAME` is `provider:model`: `openrouter:` through `ChatOpenAI` at OpenRouter, `anthropic:` through `ChatAnthropic`, `ollama:` through `ChatOllama` with a context window from the settings, all built by `init_chat_model`. The brief's default, DeepSeek V4.1 Flash, is the default in `.env.defaults`. The student's `.env` uses Claude Haiku 5.5 for live runs, paid from Anthropic credit; OpenRouter stays on free models.
- **What the code guarantees, not the instructions.** The cap, failures going back to the queue, a claim left for a handler after two failures, never deciding or paying twice, and the check for missed claims are code, in the backend where they are rules.
- **Our own to-do list.** LangChain's `TodoListMiddleware` keeps the list in the agent's state, with three statuses, where the dashboard can't see it. The brief needs a fourth status, left for a handler, and the list stored in the backend, so `write_todos` is a small tool of ours that calls the backend.
- **Not now.** Parallel claims are Week 2 Day 4's dispatcher, and accuracy in the product is its Scoreboard; here accuracy is measured only by the experiment in Phase 7, which reads `data/evals/` and is kept apart from the agent and the backend.

---

## Phase 1: Configuration, standards and a clean base

**Builds:** `.env.defaults`, `.env.example` and `models.toml`; `backend/config.py`, `agent/config.py` and the TypeScript `settings.config.ts`; `uv run -m backend`, which runs the backend on the configured host and port; the guards in `tests/test_standards.py` and `dashboard/src/standards.test.ts`; tighter ESLint and ruff limits; the agent split into `api.py`, `tools.py`, `harness.py` and `config.py`, with `main.py` gone; the model factory for the three providers; the backend's routes split by resource (`claims.py`, `records.py`, `documents.py`), with `main.py` only putting the app together; `dashboard/src/paths.ts`; and the model shown in the agent bar. No change in what the product does.

**Success criteria**

- [x] Every existing test passes, rewritten only where an import moved or a tool lost its `claim_id` argument
- [x] Each guard fails on a planted violation (a URL, an `httpx` import and an `/api/` path in the agent; a `fetch`, a URL and a `#/` link in the dashboard) and passes on the tree
- [x] A stub test builds a `ChatOpenAI`, a `ChatAnthropic` and a `ChatOllama` from their specs, and a model not in `models.toml` is refused
- [x] A test shows a claim agent's tools work only on the claim it was given
- [x] `npm run check` passes with `.env` moved out of the way
- [x] `npm run dev` serves the backend and dashboard on the ports in `.env.defaults`; the agent bar shows the model
- [x] One claim worked live on Ollama (`qwen3.5:4b`), for nothing

## Phase 2: The claims manual, looked up

**Builds:** the manual seeded with the wording; both split into their numbered sections; `search_documents` and `read_section`; the claim tools that use them, recording each section read as a step; "Sections read" on the claim page, each opening in place; the claim agent's instructions rewritten as goals, from the wording and the manual; and `docs/SPEC.md` updated so the manual is no longer "Not for now".

**Success criteria**

- [x] A search for a third claim within 12 months finds manual section 9 first; a search for meals without receipts finds manual section 10
- [x] `read_section` returns one section's text, and a 404 for one that doesn't exist
- [x] A stub run that searches and reads a section shows it in "Sections read" on the claim page
- [x] The claim agent's prompt no longer holds the whole wording
- [x] A seeding test allows the manual and still never opens `data/evals/` or `data/security/`

## Phase 3: Runs, to-do lists, failures and usage

**Builds:** a `runs` table (mode, cap, model, status, times, summary and to-do list) with `start_run`, `get_latest_run`, `write_todos` and `finish_run`; a claim's attempts; `fail_claim`, which puts a claim back in the queue or, on its second failure, leaves it for a handler (`left_for_handler`); `start_claim` taking the run and refusing claims past its cap; `resolve_referral` renamed `decide_as_handler`, for referred claims and claims left for a handler; and a usage middleware that records each model call's tokens, cost and time against the claim and the run, with the cost worked out from the prices in `models.toml` (the free models cost nothing, so OpenRouter's own cost report isn't needed). The claim agent also gets `ModelRetryMiddleware` (provider errors are retried twice) and `ModelCallLimitMiddleware` (30 calls a claim), and `work_claim` turns any failure, or a claim left undecided, into `fail_claim`, reporting in a line.

**Success criteria**

- [x] Tests for a run's cap, a first failure going back to `waiting`, a second leaving the claim for a handler, a claim never decided or paid twice, and Stop marking the run stopped
- [x] A stub run records its model calls' tokens and cost, and a run's totals are its own
- [x] Postman covers every new and changed operation, and newman passes

## Phase 4: The queue agent

**Builds:** `run_queue(cap, model)` with the queue agent's tools (`list_waiting_claims`, `write_todos` and `work_claim`, which hands a claim to a fresh claim agent and reports back in a line); the check for missed claims within the cap before the run finishes; the summary for the handlers; the command line's `--cap` and `--model`; the runner starting a capped run on a chosen model (`run_queue` and `run_claim` take a model, checked against `models.toml`, and `list_models` lists them); the queue agent's instructions as goals; and, brought forward from Phase 5, the run controls in the agent bar (model picker, claims field, Run, Run all, Stop) and the Instructions page showing both agents' instructions. `work_claim` calls go one at a time through a lock, so a model that calls the tool for several claims at once can't work them in parallel.

**Success criteria**

- [x] Stub-model tests for the to-do list stored, the cap, a failed claim that doesn't stop the run, a failed claim tried again, a claim that fails twice left for a handler, and the check for missed claims
- [x] Every claim's steps land on that claim, and the queue agent's to-do list, usage and summary land on the run

## Phase 5: The live run view

**Builds:** the run panel on the queue page (the to-do list, the claim being worked with its steps arriving live, progress and time left, tokens and cost, and the summary), with the run's model. The run controls, failed attempts, the Instructions page and "Left for a handler" came in earlier phases. Insights stays as it is.

**Success criteria**

- [x] Vitest tests for each part of the run panel and each state
- [x] An end-to-end test of a run set up through the API: its to-do list, the claim being worked and its summary
- [x] Checked in the browser in light, dark and at phone width

## Phase 6: A live trial and the docs

**Builds:** after reseeding, a run of five claims from the dashboard on Claude Haiku 5.5 (the brief asks for the default model, DeepSeek, which needs OpenRouter credit we don't spend), screenshots, and `STATUS.md`, `TECH_STACK.md` and `SPEC.md` describing the product as it now is; then a review of the whole branch.

**Success criteria**

- [x] Five claims worked on their own, the other 20 still waiting; the to-do list filled in and ticked off; each claim's steps with the sections read
- [x] `npm run check` passes

## Phase 7: The model comparison

**Builds:** `bench/`, run as `uv run -m bench`, kept apart from the agent and the backend: for each model asked for, it reseeds, runs the claims chosen through the harness, reads decisions, payouts, tokens, cost and time through the API, scores them against `data/evals/decisions.json` (the decision, and the payout within a dollar), repeats, and writes `bench/results.md` and a chart. It refuses to start when its estimate is over `BENCH_BUDGET_USD`.

**Success criteria**

- [x] Scoring tested on a stub model and hand-made answers
- [x] The comparison run, within the budget: Claude Haiku 5.5 on 25 claims three times, Claude Opus 5.5 on the five `tiny` claims three times, one free OpenRouter model (Gemma 4 31B) on the five `tiny` claims, and Ollama `qwen3.5:4b` twice on 25 claims. (A measured Haiku claim used 10 model calls, 63,000 input and 3,400 output tokens; at Opus prices that is about $0.32 a claim, so Opus on all 25 would cost about $8 and is left out. The plan had three runs of each Qwen model; on this machine a 4B run took 25 to 30 minutes and `qwen3.5:9b` three to four minutes a claim, so the 4B ran twice and the 9B was left out. OpenRouter refused every call to the free model, rate-limited upstream, so that trial has no score.)
- [x] A write-up of the results, for a community contribution: `bench/results.md`, and `community_contributions/Darko-Martinovic/HARNESS.md` in Ed's repo
