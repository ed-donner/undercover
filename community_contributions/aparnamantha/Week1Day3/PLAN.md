# Plan: the Contribution Reviewer pilot

This plan builds the pilot in `docs/SPEC.md`. The Contribution Reviewer is an agent that works a queue of pull requests the way a maintainer does. Maintainers use a dashboard to watch it work and to sign off on sensitive changes.

## Starting point and approach

The repo has a hello-world skeleton: a FastAPI health route, a `create_agent` agent with one tool, a React page and one Playwright test. `data/` still holds the travel-insurance records, so there is no pull request data yet. Phase 1 creates it.

Key choices:

- **Rules are enforced by the system, not the model.** The backend decides whether a pull request needs sign-off by matching its changed paths against the repository's policy patterns. It refuses a merge without sign-off, and it refuses an Accept when a required test failed. Even if the agent gets something wrong, it can't break these rules.
- **The agent sees the business only through the API.** It reads pull requests, guidelines, files, tests, history and its own instructions with HTTP tools. The backend never loads `data/evals/`, so nothing the agent can reach holds the answers.
- **The activity timeline comes from the tools, not the model.** Each tool records a timeline step when it runs, so the steps a maintainer sees are always accurate and complete.
- **Merging is simulated.** "Merge" means the backend records the pull request as merged. There's no GitHub integration.
- **The dashboard polls rather than streams.** While a review is in progress, the detail view re-fetches once a second. This is simple and good enough for the pilot.
- **SQLite is a working copy.** The backend builds `backend/undercover.db` (gitignored) from `data/contributions/` on first start. `POST /api/reset` rebuilds it, which keeps the end-to-end tests repeatable.

Statuses follow `docs/BRAND.md`: `waiting`, `in_progress`, `waiting_for_signoff` and `decided`. Decisions are `accept`, `request_changes` and `refer`.

---

## Phase 1: Seed data and documents

**Builds:** the pull request records that the spec lists, plus the maintainers' answer key. The documents are brought into line with the new product.

**Why first:** every later phase reads this data, and the eval set has to exist before the agent does, so that it's written without the agent's influence.

- `data/contributions/`, kept apart from the insurance data that is already there:
  - `repositories.json`: two fictional repositories. `quillwire` is a fictional Python HTTP client and `plotmoss` is a fictional TypeScript charting library. Each entry has its description, language, license and required checks.
  - `policies.json`: for each repository, the sensitive path patterns by category (`authentication`, `authorization`, `security`, `dependencies`, `release`), the allowed dependency licenses and the required-file rules (for example, "changes under `src/` need a test change and a `CHANGELOG.md` entry").
  - `guidelines/quillwire.md` and `guidelines/plotmoss.md`: contribution guidelines with numbered sections (such as `§3.2 Tests`) so the agent can cite them.
  - `maintainers.json`: four maintainers.
  - `contributors.json`: each contributor's history, meaning earlier pull requests with date, outcome and a one-line summary.
  - `pull_requests.json`: a queue of 20 pull requests. Each has id (`quillwire-1042`), repository, number, title, author, description, opened date, labels, and changed files with path, status, additions, deletions and a short patch.
  - `test_results.json`: the check runs for each pull request, with name, required flag, status and a one-line output.
  - `source_files.json`: the current contents of the relevant source files, keyed by repository and path.
- The queue mixes routine Accepts, Request changes (a failing required test, a missing test or changelog entry, style violations), Refers (an architectural change, an incompatible license, a vague description) and sensitive pull requests that touch auth, dependency manifests or release configuration.
- `data/evals/contribution_decisions.json`: the maintainers' decision for each queued pull request, with decision, guideline section, the checks that failed, and what the pull request tests.
- `data/evals/held_out_pull_requests.json` and `held_out_contribution_decisions.json`: 10 more pull requests with decisions, kept out of the queue.
- A "Contribution reviewer data" section in `data/README.md`. `docs/TECH_STACK.md` is updated from claims to pull requests (the entry point takes a pull request id; merging is a separate operation).
- `backend/tests/test_seed_data.py` checks the data's integrity.

Success criteria:

- [x] `uv run pytest backend/tests/test_seed_data.py` passes. It checks that every pull request's repository, author and test results exist; every eval decision matches a queued pull request; and no held-out id appears in the queue.
- [x] The queue has 20 pull requests across both repositories, with at least 4 of each decision and at least 4 that need sign-off.
- [x] Every eval decision cites a guideline section that exists in that repository's guidelines file.
- [x] `data/README.md` and `docs/TECH_STACK.md` describe pull requests, not claims.
- [x] `npm run check` passes.

## Phase 2: Backend read API

**Builds:** the SQLite store and every read operation that the agent and dashboard need.

- `backend/db.py`: the schema (`pull_requests`, `files`, `test_results`, `reviews`, `activity`, `signoffs`) and a loader that seeds from `data/contributions/` only.
- `backend/main.py` routes. Each has an `operation_id`, a one-line docstring and no optional inputs:
  - `list_pull_requests`, `GET /api/pull-requests`: queue cards with status, changed-file count, test summary, age, `needs_signoff` and the categories touched
  - `get_pull_request`, `GET /api/pull-requests/{id}`: the full record, with review, activity and sign-off
  - `get_test_results`, `GET /api/pull-requests/{id}/tests`
  - `get_guidelines`, `GET /api/repositories/{repo}/guidelines`
  - `get_policies`, `GET /api/repositories/{repo}/policies`
  - `get_source_file`, `GET /api/repositories/{repo}/files/{path}`
  - `get_contributor`, `GET /api/contributors/{login}`
  - `list_maintainers`, `GET /api/maintainers`
  - `reset`, `POST /api/reset`
- `needs_signoff` and the sensitive categories are worked out from the changed paths and the policy patterns.

Success criteria:

- [x] `uv run pytest backend` passes, with tests for each route through FastAPI's `TestClient` against a temporary database.
- [x] `curl localhost:8000/api/pull-requests` returns 20 cards, all `waiting`.
- [x] A pull request that changes a dependency manifest returns `needs_signoff: true` with category `dependencies`, and a docs-only pull request returns `false`.
- [x] `GET /api/pull-requests/does-not-exist` returns 404.
- [x] A test shows that the loader never reads `data/evals/`, and no API response contains a field from the eval files.
- [x] Every route in `app.openapi()` has an `operation_id` and a summary, and no optional parameters (checked by a test).
- [x] `npm run check` passes.

## Phase 3: Review lifecycle and the sign-off gate

**Builds:** the write operations that move a pull request through the queue, with the spec's rules enforced in the backend.

- `start_review`, `POST /api/pull-requests/{id}/start`: `waiting` to `in_progress`
- `record_activity`, `POST /api/pull-requests/{id}/activity`: a timeline step (`read_contribution`, `loaded_guidelines`, `inspected_files`, `checked_tests_and_policy`, `prepared_recommendation`) with a detail line and timestamp
- `record_decision`, `POST /api/pull-requests/{id}/decision`: decision, summary (two or three sentences), guideline section, checks (name, passed, note), findings (severity, file, line, message, rule) and requested changes
  - It rejects `accept` with 422 when a required test failed.
  - It rejects `request_changes` with no requested changes.
  - `accept` on a sensitive pull request moves it to `waiting_for_signoff`. Everything else moves to `decided`.
- `sign_off`, `POST /api/pull-requests/{id}/signoff`: takes a maintainer id and moves `waiting_for_signoff` to `decided`
- `merge_pull_request`, `POST /api/pull-requests/{id}/merge`: records the merge
  - 409 unless the decision is `accept`
  - 409 with "Maintainer sign-off required" while a sensitive pull request has no sign-off
- `get_instructions`, `GET /api/agent/instructions`: returns `backend/instructions/reviewer.md`, the agent's instructions (written in Phase 4)

Success criteria:

- [x] `uv run pytest backend` passes, with tests for every transition and refusal.
- [x] Recording `accept` on a sensitive pull request and then calling merge returns 409. After `sign_off`, merge returns 200 and the pull request shows as merged.
- [x] Recording `accept` on a pull request with a failed required test returns 422 and leaves its status unchanged.
- [x] Merging a `request_changes` or `refer` pull request returns 409.
- [x] Signing off on a pull request that isn't waiting for sign-off returns 409.
- [x] `npm run check` passes.

## Phase 4: The Contribution Reviewer agent

**Builds:** the agent, plus the way to run it from the backend.

- `backend/instructions/reviewer.md`: the instructions. They cover how to work through the review steps, when to Accept, Request changes or Refer, the rule that the agent never accepts with failed required tests, missing required files or an unresolved security or licensing concern, how to cite a guideline section, a two- or three-sentence summary, and specific requested changes.
- `agent/main.py`: `run(pull_request_id, thread_id)`. On start, it fetches its instructions from `get_instructions`.
  - Tools: `get_pull_request`, `get_guidelines`, `get_policies`, `get_source_file`, `get_test_results`, `get_contributor`, `record_decision` and `merge_pull_request`.
  - Each read tool posts its timeline step to `record_activity` itself.
  - The model is `openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME` if set.
- `POST /api/pull-requests/{id}/review` (`review_pull_request`): starts the review and runs the agent in a FastAPI background task, so the dashboard returns at once.
- `uv run -m agent <id>` reviews one pull request from the command line.
- `agent/evaluate.py`: reviews the queue (or `--held-out`) and compares the stored decisions with `data/evals/`. Only this script, which runs outside the agent, reads the answer key. It prints accuracy per decision.
- Tests use a stub chat model that issues scripted tool calls against a `TestClient` backend. They never call a real model.

Success criteria:

- [x] `uv run pytest agent` passes. With the stub model, a run on a routine pull request records all five timeline steps and an `accept`.
- [x] With the stub model scripted to merge a sensitive pull request, the merge tool returns the 409 message, and the pull request stays `waiting_for_signoff`.
- [x] A test shows that the agent's tools only call `/api/` routes and that the `agent/` package (apart from `evaluate.py`) never references `data/`.
- [x] `evaluate.py`'s scoring is unit-tested on fixed inputs.
- [x] Manual, with a real model: `uv run -m agent quillwire-1042` (one pull request, a few cents) records a decision with a guideline section and a two- or three-sentence summary.
- [x] `npm run check` passes.

## Phase 5: Dashboard queue and review detail

**Builds:** the maintainer console from `docs/BRAND.md`, covering the queue and a pull request in full.

- The fonts are Instrument Sans, Instrument Serif and JetBrains Mono. The colors are CSS custom properties, with light and dark modes driven by `prefers-color-scheme`. The layout is a left rail and a 12-column grid, collapsing to a single column and a bottom bar below 900px.
- **Queue:** compact cards (repository and number in mono, title, contributor, status pill with text and icon, file count, test summary, age, risk marker). Filter chips by status and sorting by status, age, risk and repository. Empty, skeleton-loading and error-with-retry states.
- **Detail** (a split view on wide screens):
  - the decision banner (Accept, Request changes, Refer, or Blocked while waiting for sign-off)
  - the scorecard (guideline checks, test checks, security risk, documentation coverage)
  - the summary with its guideline section, findings with severity markers and rule references, and requested changes with a copy button
  - the description, changed files with patches in a dark inset, test results and contributor history
- A "Start review" primary action calls `review_pull_request`.
- Typed API client in `dashboard/src/api.ts`. Components are tested with vitest and Testing Library.

Success criteria:

- [x] `npm run check:ts` passes with at least 80% coverage.
- [x] In the browser (Playwright MCP): the queue shows 20 cards. The "Waiting for sign-off" chip filters them, and sorting by risk puts sensitive pull requests first.
- [x] Selecting a decided pull request shows the banner, the scorecard, findings with rule references and the requested changes, with the main action visible without scrolling at 1440×900.
- [x] At 400px wide the layout is a single column with a bottom navigation bar, and nothing scrolls sideways.
- [x] Dark mode follows the system setting. Statuses always pair color with text and an icon.
- [x] With the backend stopped, the queue shows the error card, and Retry recovers once it's back.

Note: the browser checks in Phases 5 and 6 ran with the project's own Playwright Chromium from a script, because the Playwright MCP server needs Google Chrome, which isn't installed on this machine.

## Phase 6: Live activity, the sign-off gate and instructions

**Builds:** the rest of what maintainers need to see, plus end-to-end tests.

- **Activity timeline:** the five steps, with mono timestamps. Done steps are Sea Green, the active step is Cerulean with one pulse, and pending steps are muted. The detail view polls every second while the review is `in_progress`, and steps and the decision are announced through an `aria-live` region. Motion respects `prefers-reduced-motion`.
- **Approval gate:** on `waiting_for_signoff`, a card shows why sign-off is needed, the affected categories, a maintainer picker and "Sign off". The merge button stays disabled with an explanation until sign-off is recorded. After sign-off, Merge records the merge.
- **Instructions page:** the agent's instructions from `get_instructions`, read only.
- **Playwright tests:** the backend runs with `REVIEWER_STUB=1`, which swaps in a scripted stub model so the tests never call a real model. Each test starts from `POST /api/reset`.
- `docs/STATUS.md` is brought up to date: what's built and how to run it.

Success criteria:

- [x] `npm run e2e` passes. It covers starting a review, watching the timeline steps appear in order and the decision banner arrive; a sensitive pull request that shows the gate with Merge disabled, then sign-off, then a successful merge; and the instructions page showing the instructions with no editing controls.
- [x] In the browser (Playwright MCP), with a real model: reviewing one routine and one sensitive pull request shows the live timeline, and the sensitive one stops at the approval gate.
- [x] Keyboard only, a maintainer can filter the queue, open a pull request, start a review and sign off, with the focus ring visible throughout.
- [x] `npm run check` passes: ruff, pyright and pytest with at least 80% coverage, ESLint, Prettier, tsc and vitest with at least 80% coverage, and Playwright.
- [x] `docs/STATUS.md` describes the built product and how to run it.
