# Review: how the code conforms to `docs/`

Reviewed against `SPEC.md`, `TECH_STACK.md`, `CODE_STANDARDS.md`, `PROCESS.md`, `BRAND.md`, `STATUS.md` and the two briefs `HARNESS.md` and `DURABLE.md`, on branch `week2day3-steveH`.

## Verdict

The build conforms well. Every behavior in the spec and both briefs is implemented and tested, and the structure rules from `CODE_STANDARDS.md` mostly hold, with `test_structure.py` and ESLint enforcing the machine-checkable ones. The issues below are small. The most important are an unmet success criterion from the Durable brief, a latent `.env` override, and some duplicated literals.

## Checks run

| Check | Result |
|---|---|
| pyright | 0 errors |
| ruff format and lint | pass |
| pytest | 113 passed, 98% coverage (threshold 80%) |
| prettier, eslint, tsc | pass |
| vitest | 19 passed, 94% statements (threshold 80%) |
| Playwright | 6 passed |

I did not run the agent against a real model or inspect Supabase, so the live-run claims in `STATUS.md` are taken as written.

## What conforms

- **SPEC rules.**
  - The over-$1,000 sign-off is enforced in the backend by a conditional `UPDATE` in `claims.pay`, whatever the agent does.
  - The limit lives in one place (`payouts.needs_sign_off`, from the `settings` record), and a test checks the agent never mentions it.
  - Decide and pay are idempotent, and a different decision on a decided claim returns 409.
  - Sign-off records who and when, and sets the status to in progress.
  - A missed sign-off is picked up by `carry_on`.
  - A stopped claim carries on from its saved thread without a new attempt (`work.py`).
  - A failed claim gets `thread + 1` and is tried once more, then left for a handler.
  - Nothing outside tests mentions `evals`, and a test checks that.
- **TECH_STACK.**
  - Every operation has an `operation_id` and a one-line docstring.
  - SQLAlchemy Core is used with the `undercover` schema on Postgres.
  - Connection limits are 4 for the backend and 2 for the checkpointer.
  - Money is `Decimal`, a two-decimal string on the wire and cents in the database. There are no floats.
  - Tracing is confined to `tracing.py`, Postgres to `checkpoint.py`, HTTP to `api.py`, and reads of `data/` to `seed_data.py`.
  - The model is the default DeepSeek with `MODEL_NAME` as an override, with a 120 s timeout and a 30-call limit.
- **CODE_STANDARDS 8 to 12.**
  - Tools are module-level and read their state from `ToolRuntime`.
  - The harness knows no claims.
  - Instructions state a goal, the resources and the rules, and point to the wording and manual.
  - Routes are thin and errors become 404 and 409 in one place.
  - The dashboard calls `fetch` only through `api.ts`, and ESLint enforces that.
- **HARNESS and DURABLE briefs.**
  - Run cap, one-claim mode, to-do list on the queue page, subagent per claim, section-by-section reading shown as steps, retry and give-up, and the finish check are all present.
  - Payout operation, Langfuse session per claim thread, Supabase, interrupt-based sign-off, sync checkpointer with `durability="sync"`, and the separate agent service are all present.
  - The e2e tests use the stand-in on port 8003.
  - The Durable sidenote is in `PLAN_DURABLE.md`.
- **Earlier human reviews.** The queue totals including "Left for a handler" are on the queue page. `/api/runs/current` now returns 200 with `null`, so the 404 noise is gone.

## Findings

### Should fix

1. **Durable brief criterion not met: connection count.** The brief says Supabase should show no more than 12 connections. `STATUS.md` records 11 to 16 and attributes it to the pooler. It is documented honestly, but the criterion is still unmet and nothing was changed to meet it. Either close the pools when idle or agree with the head of claims operations that the criterion is relaxed.

2. **`load_dotenv(override=True)` in `agent/harness.py:19`.**
   - It runs at import and lets `.env` override variables already in the shell. A per-run `MODEL_NAME=openrouter/free`, as `PROCESS.md` prescribes for hand checks, would be silently ignored once `.env` defines `MODEL_NAME`. It does not today (`.env` has none), so the problem is latent.
   - `npm run dev` already passes `.env`, so this duplicates it.
   - It also means that importing a module loads secrets. Tests are safe only because `conftest.py` strips `DATABASE_URL` and the Langfuse keys.
   - Use `load_dotenv()` without `override`, and call it from `__main__.py`, the entry point that needs it.

3. **Status strings are repeated as literals (rule 14).**
   - `"waiting"`, `"in progress"`, `"waiting for sign-off"` and `"decided"` appear 11 times in `backend/claims.py`.
   - They appear again as `WAITING_FOR_SIGN_OFF` in `agent/claim_nodes.py`, in `backend/seed_data.py` and in the dashboard's `ClaimStatus` type.
   - The run-item statuses are written separately in `agent/api.py`, `backend/main.py` and the dashboard.
   - The same goes for `Benefit` and `Line` in `agent/api.py` and `backend/payouts.py`.
   - Crossing a process boundary justifies some duplication, but within the backend the statuses should be named constants in one module.

### Worth fixing

4. **A business rule sits in a route (rule 12).** `list_handlers` in `backend/main.py:117` filters on `can_approve_over_limit`. Move the filter into `reference.py`.

5. **`run_agent` route does two things, and the second can fail.** `claims.start_work` marks the claim in progress, then `agent_process.start` spawns the process. If the spawn fails, the claim is stuck in progress, which `HARNESS.md` says must not happen. `carry_on` would later pick it up, but the user sees a stuck claim until then.

6. **A claim started from the dashboard can be double-worked.** `list_unfinished` returns every claim with status "in progress". If a handler clicks "Run agent" and someone then runs `uv run -m agent`, `carry_on` resumes that claim in a second process on the same thread. The backend stops a double decision or payment, but the two agents duplicate model spend and steps.

7. **Dashboard polling gaps.**
   - `ClaimPage` polls only while the status is "in progress". A page opened on a waiting claim does not update when a run picks it up.
   - `QueuePage` stops polling once the run has finished, so a sign-off and payment made afterwards leave the totals stale until reload. This matters because the totals were a human-review request.

8. **`api.fetchCurrentRun` repeats `getJson`** (`dashboard/src/api.ts:74`) instead of calling `getJson<Run | null>`. That is one block of plumbing written twice (rule 14).

9. **Brand: JetBrains Mono is used only for `pre`.** `BRAND.md` says code, numbers and identifiers use it. Claim ids, amounts and the totals use Instrument Sans. The font is loaded in `index.html` and left unused for these.

10. **Unhandled fetch failures in the dashboard.** `ClaimPage` and `QueuePage` use `void fetch...then(set...)` with no error path. A backend outage gives no message and a rejected promise. The standards discourage defensive code, but a failed load deserves one visible line.

### Minor

11. **Tests patch private names (rule 15).** `agent/tests/test_checkpoint.py:42,49` calls `checkpoint._make_saver.cache_clear()`. Give `checkpoint` a public reset, or test through `saver()`.
12. **Stale docstrings.** `backend/runs.py:1` says the to-do list is "tracked in SQLite", and `backend/db.py:1` says it holds "table definitions", which live in `tables.py`.
13. **`ClaimContext` and `RunContext` live in `tools.py`.** `claim_nodes`, `claim_graph` and `agents` import the context type from the tools module. It is a type shared by the graph and the tools, so it belongs in a small module of its own.
14. **`BACKEND_URL` is a constant with no environment override** (`agent/api.py:13`). It is in one place as rule 9 asks, but the Week 3 move to AWS will need it configurable.
15. **Coverage excludes `src/main.tsx`.** `PROCESS.md` forbids excluding a file to get green. It is only the React entry point, but the rule is absolute. The dashboard threshold also covers statements only.
16. **`decide` accepts any payout with any decision.** A decline with a non-zero payout is stored as given. `pay` refuses it because the decision is not approve, but the record is inconsistent.

## Suggested order

1. Fix 2 (`override=True`), the quickest and the riskiest to leave.
2. Settle 1 with the head of claims operations.
3. Do 3 and 4 together as one cleanup of constants and the route filter.
4. Do 7 and 8 in one dashboard change.
5. Leave the rest for a tidy-up pass.
