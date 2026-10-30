# Plan: the harness

Builds the agent's harness from `docs/HARNESS.md`: one run that works the whole queue, a to-do list the team can watch, a fresh subagent per claim, lookups into the claims manual as well as the policy wording, and automatic recovery from a bad claim. Builds on the pilot (`docs/STATUS.md`, `docs/PLAN.md`), which stays as it is.

## Design

- **Two system prompts, two agents.** The existing per-claim agent (`agent/main.py`, `run(claim_id, thread_id)`) stays as the "subagent" that decides one claim from a clean start — unchanged in shape, with new tools (below). A new orchestrator, `run_queue()` in `agent/queue.py`, is a second `create_agent` whose tools plan and track a run and call the subagent once per claim. `backend/instructions.py` holds two prompts, `CLAIM_INSTRUCTIONS` and `QUEUE_INSTRUCTIONS`, served by two operations and shown as two sections on `/instructions`.
- **Hard guarantees live in code, not in the model's judgment.** Which claims are in scope for a run (the cap), when a claim is retried, when it's given up on, and whether a run is allowed to finish are all decided by plain Python in a backend operation or an agent tool — never left to the orchestrator to remember to do. The orchestrator's actual freedom is just the order it works a fixed to-do list in, and the summary it writes at the end.
- **The cap is applied before the model sees anything.** `run_queue(cap)` reads the waiting claims (oldest submitted first, as the queue already orders them) and takes the first `cap` of them — or all of them, uncapped — before starting the run. The orchestrator is handed that fixed list; it never sees or chooses which claims are in scope, only the order it works them in.
- **One run, one to-do list, stored in SQLite.** Two new tables alongside `claims` and `claim_steps` in `backend/db.py`: `runs` (one row per run, with its summary once finished) and `run_items` (one row per claim in that run, with its status — `to do`, `in progress`, `done`, or `left for a handler` — and how many attempts it took). The run-state logic (starting a run, moving an item, finishing a run) is plain functions in a new `backend/runs.py`, the same split `data.py`/`db.py` already use, called from thin routes in `backend/main.py`.
- **Retries and give-up are inside one tool call, not spread across the orchestrator's turns.** The orchestrator's `work_claim(claim_id)` tool tries the per-claim subagent, catches any failure (an exception, or a timeout from a wall-clock limit the tool itself imposes), and on failure resets the claim to `waiting` and tries once more before giving up — all inside that one tool call. The orchestrator always gets back exactly one line per claim it asks about: decided, or left for a handler. This also means a test can call `work_claim` directly with a monkeypatched subagent and never touch a model.
- **Before re-trying a claim, check it isn't already decided.** A subagent can fail after it has already called `decide_claim` (for example, the network drops on the way back). `work_claim` re-reads the claim before a retry and skips straight to reporting success if it's already decided or waiting for sign-off, so a claim is never decided twice.
- **`finish_run` is a backend rule, not an honor system.** `finish_run(run_id, summary)` returns 409 if any `run_item` is still `to do` or `in progress`. This is what satisfies "the agent checks it hasn't missed a claim" — the orchestrator doesn't have to remember to check; it simply can't finish until the backend agrees every item is settled.
- **The claims manual and the policy wording are both read by section, not handed over whole.** Both documents are split into their `##`-headed sections at load time in `backend/data.py`, the same way `POLICY_WORDING` loads today. Two operations replace today's `get_policy_wording`: `list_sections(document)` and `get_section(document, heading)`, where `document` is `policy_wording` or `claims_manual`. The per-claim agent gets matching tools, and each read still records a specific step (e.g. "Read policy wording section: 3. Trip Delay"), so the claim page keeps showing what the agent read without any dashboard changes.
- **The model.** `DEFAULT_MODEL` in `agent/main.py` becomes `deepseek/deepseek-v4.1-flash`, used at low reasoning effort by default. `MODEL_NAME` still overrides it, for both agents.
- **Starting a run is still a command, not a dashboard button.** A new `agent/cli.py` (`uv run python -m agent.cli`) takes `--cap N` or `--claim CLM-1001`; with neither, it runs the whole queue uncapped. The dashboard's existing "Run agent" button (one claim, from the queue page) is untouched. The queue page adds a live to-do panel, fed by polling the current run, the same way the claim page already polls while `in progress`.

## Phase 1: Backend — read the policy wording and the claims manual by section

- `backend/data.py`: parse `policy_wording.md` and `claims_manual.md` into ordered `{heading: text}` dicts at load time, splitting on `##` headings.
- Operations: `list_sections(document)` → `GET /api/documents/{document}/sections`, the ordered heading titles; `get_section(document, heading)` → `GET /api/documents/{document}/sections/{heading}`, that section's text. `document` is `policy_wording` or `claims_manual`; an unknown document or heading is a 404.
- Remove `get_policy_wording` / `GET /api/policy-wording` — nothing outside its own tests uses it, and it's superseded by the two operations above.
- `docs/SPEC.md`: drop "The claims manual. For the pilot, the agent works from the policy wording alone." from "Not for now", and add the claims manual alongside the policy wording in "For each claim it should: ... and the policy wording."

**Success criteria**

- [ ] `uv run pytest backend -q` passes, including:
  - [ ] `list_sections("policy_wording")` returns 12 headings in order, starting with `"1. Your plan"`.
  - [ ] `list_sections("claims_manual")` returns 14 headings in order, including `"10. Meals without receipts"`.
  - [ ] `get_section("policy_wording", "3. Trip Delay")` returns text containing `"delay"`.
  - [ ] `get_section("claims_manual", "9. Repeat claims")` returns text containing `"12 months"`.
  - [ ] `get_section("claims_manual", "99. No such section")` returns 404.
  - [ ] `list_sections("not_a_document")` returns 404.
- [ ] `grep -rn "policy-wording\|get_policy_wording" backend agent` returns nothing.
- [ ] Coverage for `backend/` stays at 80% or above.

## Phase 2: Backend — a run and its to-do list

- `backend/db.py`: add `runs` (`run_id` autoincrement, `started_on`, `finished_on`, `summary`) and `run_items` (`run_id`, `claim_id`, `status`, `attempts`, `note`; primary key `(run_id, claim_id)`).
- `backend/runs.py`: `start_run(claim_ids)` creates a run and one `to do` item per claim; `update_run_item(run_id, claim_id, status, note)`; `get_current_run()` returns the most recent run with its items, or `None`; `finish_run(run_id, summary)` sets `finished_on` and `summary`, but raises if any item isn't `done` or `left for a handler`.
- Operations in `backend/main.py`: `start_run` → `POST /api/runs`; `get_current_run` → `GET /api/runs/current` (404 if no run yet); `update_run_item` → `POST /api/runs/{run_id}/items/{claim_id}`; `finish_run` → `POST /api/runs/{run_id}/finish` (409 if items are unsettled).
- `requeue_claim(claim_id)` → `POST /api/claims/{claim_id}/requeue`: moves a `waiting` or `in progress` claim back to `waiting`; 409 on a claim that's `decided` or `waiting for sign-off`.

**Success criteria**

- [ ] `uv run pytest backend -q` passes, including:
  - [ ] `start_run(["CLM-1001", "CLM-1002"])` creates a run with both items `to do`.
  - [ ] `update_run_item` moves an item through `in progress` → `done`, with a note.
  - [ ] `finish_run` on a run with one `to do` item still outstanding returns 409.
  - [ ] `finish_run` on a run whose items are all `done`/`left for a handler` succeeds and `get_current_run` shows the summary and `finished_on` set.
  - [ ] `requeue_claim` on an `in progress` claim sets it back to `waiting`.
  - [ ] `requeue_claim` on a `decided` claim returns 409.
- [ ] Coverage for `backend/` stays at 80% or above.

## Phase 3: The per-claim agent reads the manual, and the model changes

- `agent/main.py`: replace the `get_policy_wording` tool with `list_sections(document)` and `read_section(document, heading)`, each recording a step naming the document and heading. `DEFAULT_MODEL` becomes `deepseek/deepseek-v4.1-flash`.
- `backend/instructions.py`: rewrite `CLAIM_INSTRUCTIONS` (renamed from `AGENT_INSTRUCTIONS`) from the policy wording and the claims manual (never `data/evals/`): look up the sections it needs from both documents rather than assuming either is short enough to read whole; decide using section 2 of the manual's three decisions and its referral reasons (missing document, story and documents disagree, a third claim in 12 months, or the wording and manual still unclear); still call `decide_claim` exactly once.
- `backend/main.py`: rename `get_agent_instructions` to `get_claim_instructions` (`GET /api/claim-instructions`).

**Success criteria**

- [ ] `uv run pytest agent -q` passes, including:
  - [ ] a scripted `list_sections` → `read_section` (policy wording) → `list_sections` → `read_section` (claims manual) → `decide_claim` run against the real backend leaves the claim `decided`.
  - [ ] the recorded steps name the document and heading read, in order.
- [ ] Coverage for `agent/` stays at 80% or above.

## Phase 4: The queue orchestrator — one run, a to-do list, retries, and giving up

- `agent/queue.py`: `run_queue(cap: int | None = None) -> str`.
  - Reads the waiting claims, takes the first `cap` (oldest submitted first) or all of them, and calls `start_run` with that list.
  - Builds a `create_agent` with `QUEUE_INSTRUCTIONS` and three tools: `get_to_do()` (the run's items and their statuses); `work_claim(claim_id)`; `finish_run(summary)`.
  - `work_claim(claim_id)`: marks the item `in progress`; calls the per-claim `run()` under a wall-clock timeout; on success marks the item `done` with a one-line note and returns it; on failure, re-reads the claim — if it's already decided or waiting for sign-off, reports that success and marks `done`; otherwise calls `requeue_claim`, and either marks the item `to do` and retries once, or — on a second failure — marks it `left for a handler` with the error and returns that.
  - `finish_run(summary)`: calls the backend operation; on its 409, returns the still-outstanding claim ids so the orchestrator keeps going instead of stopping.
- `backend/instructions.py`: `QUEUE_INSTRUCTIONS` — plan to work every item on the to-do list, in any order; call `work_claim` once per claim; call `finish_run` with a short summary for the handlers once done; if `finish_run` reports claims left outstanding, keep working them.
- `backend/main.py`: `get_queue_instructions` (`GET /api/queue-instructions`).
- `agent/cli.py`: `uv run python -m agent.cli [--cap N | --claim CLM-1001]`; with neither flag, an uncapped `run_queue()`.
- `docs/SPEC.md`: rewrite "For the pilot, someone starts the agent from the command line..." to describe one run working every waiting claim (or a capped trial, or one named claim), choosing its own order, with a to-do list the team can watch.

**Success criteria**

- [ ] `uv run pytest agent -q` passes, using a stub model for the orchestrator and a monkeypatched per-claim `run()` (never a real model), including:
  - [ ] `run_queue(cap=2)` against two waiting claims starts a run of 2 items and ends with both `done`.
  - [ ] a claim whose monkeypatched `run()` fails once then succeeds ends `done`, with its claim status `decided` and the run item's `attempts` at 2.
  - [ ] a claim whose monkeypatched `run()` always fails ends `left for a handler`, with its claim status back to `waiting` (not stuck `in progress`), after exactly 2 attempts.
  - [ ] a claim whose monkeypatched `run()` raises after already calling the real `decide_claim` is not retried, and its item ends `done`.
  - [ ] `finish_run` called while an item is still outstanding doesn't end the run; the agent is told which claim is left.
  - [ ] a waiting claim outside the cap is left `waiting` and has no run item.
- [ ] Coverage for `agent/` stays at 80% or above.

## Phase 5: Dashboard — the to-do list, and two sets of instructions

- `dashboard/src/api.ts` / `types.ts`: `fetchCurrentRun()` (`GET /api/runs/current`, `null` on 404); a `Run`/`RunItem` type with the four statuses; `fetchClaimInstructions()` and `fetchQueueInstructions()` replacing `fetchInstructions`.
- `dashboard/src/components/RunItemBadge.tsx`: the four statuses in Sea Green / Marigold / Cerulean / Raspberry, mirroring `StatusBadge`.
- `QueuePage.tsx`: above the table, a to-do panel showing the current run's items (claim id, badge, note) when a run exists; polls every 2 seconds while the run is unfinished, the same pattern `ClaimPage` already uses.
- `InstructionsPage.tsx`: two sections, "Working the queue" and "Deciding a claim", one for each instructions text.

**Success criteria**

- [ ] `npx vitest run --root dashboard --coverage` passes at 80% or above, including:
  - [ ] the queue page shows no to-do panel when there's no current run (mocked 404).
  - [ ] it shows each item with its status badge, and polls while unfinished (mocked timers).
  - [ ] the instructions page renders both texts under their own headings.
- [ ] Checked in the browser (Playwright MCP): with a run started from the CLI against a reseeded backend, the queue page's to-do panel fills in and finishes, in both light and dark mode.

## Phase 6: End-to-end tests, the final check, and the real-model run

- Playwright e2e tests that never call a model: start a run by calling `start_run` and `update_run_item` directly over the API (as the e2e tests already script `decide_claim`), then check the queue page's to-do panel renders every status, including `left for a handler`.
- `docs/TECH_STACK.md` and `docs/STATUS.md` updated to describe the harness: the two agents, the sectioned documents, the `runs`/`run_items` tables, the CLI, and the new default model.

**Success criteria**

- [ ] `npm run e2e` passes, covering the to-do panel in all four item statuses.
- [ ] `npm run check` passes in full (ruff, pyright, pytest ≥80%, Prettier, ESLint, tsc, vitest ≥80%, Playwright) with no thresholds lowered and no rules disabled.
- [ ] Manual check (not in the automated suite): reseed the database, then `MODEL_NAME=openrouter/free uv run python -m agent.cli --cap 5`. Report each of the 5 claims' decision and payout, the run's final summary, and the to-do panel's final state in the dashboard. Confirm no claim outside the 5 moved off `waiting`.
- [ ] `docs/SPEC.md`, `docs/TECH_STACK.md`, and `docs/STATUS.md` all match what's built.
