# Plan: the claims pilot

This plan builds the pilot in `docs/SPEC.md` on the skeleton described in `docs/STATUS.md`. It follows `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`, and installs the commit guard in `docs/CLAUDE_PRE_TOOL_USE_HOOK.md`.

Phase 0 installs the Claude Code hook that stops a commit from skipping the pre-commit checks. Phases 1 to 6 built the pilot. Phase 7 was added afterwards, when `docs/SPEC.md` gained a slider between light and dark screens. Phase 8 adds the color-blind mode that `docs/ACCESSIBILITY.md` describes, with a second slider.

## The approach

**The backend owns the rules.** It holds the claims and their state in SQLite, and every rule in the spec is enforced there, not in the agent's prompt. The most important rule is that a payout over $1,000 can't be paid until a handler signs off. The agent is asked to follow the rules, but the system doesn't rely on it.

**The agent only works through the API.** The UnderCover Agent is LangChain's `create_agent` with a small set of tools, and each tool is one backend API call. It also fetches its instructions from the API at the start of each run. This means the dashboard and the agent see the same data, and the agent can't reach anything the API doesn't expose, including `data/evals/`.

**The agent reports each step to the backend.** The agent streams its own run (`agent.stream(..., stream_mode="updates", version="v2")`) and posts each step to the backend: what it said, which tool it called and what came back. While a claim is in progress, the dashboard polls these steps. This is simpler than a WebSocket and enough for three handlers.

**The backend starts the agent.** The dashboard can't run Python, so "Run the agent" calls a backend operation that marks the claim in progress and runs the agent in a background task. A second operation works through every waiting claim, one after another.

**Seed data stays as it is.** On first start the backend copies `data/` into SQLite. Claims, policies, customers and handlers are stored as the JSON documents they already are. The new state lives in its own tables: each claim's status, the decision, the payment, the sign-off and the agent's steps. `data/evals/` and `data/security/` are never loaded.

### Claim states

| State (API) | Label | Meaning | Color |
|---|---|---|---|
| `waiting` | Waiting | In the queue, not yet worked. All 25 claims start here. | Cerulean |
| `in_progress` | In progress | The agent is working on it | Coral |
| `awaiting_sign_off` | Waiting for sign-off | Approved over $1,000; the payment is blocked until a handler signs off | Marigold |
| `decided` | Decided | Declined, referred, or approved and paid | Sea Green |

If an agent run fails or ends without a decision, the backend records a step that says so and moves the claim back to `waiting`, so it never sticks in progress.

### The API

Every operation has an `operation_id`, a one-line docstring and only required inputs.

| Operation | Route | Used by |
|---|---|---|
| `health` | `GET /api/health` | dashboard |
| `list_claims` | `GET /api/claims` | dashboard |
| `get_claim` | `GET /api/claims/{claim_id}` | dashboard, agent |
| `get_policy` | `GET /api/policies/{policy_id}` | dashboard, agent |
| `get_claim_history` | `GET /api/customers/{customer_id}/history` | dashboard, agent |
| `get_policy_wording` | `GET /api/policy-wording` | agent |
| `get_instructions` | `GET /api/instructions` | dashboard, agent |
| `list_handlers` | `GET /api/handlers` | dashboard |
| `list_steps` | `GET /api/claims/{claim_id}/steps` | dashboard |
| `add_step` | `POST /api/claims/{claim_id}/steps` | agent |
| `record_decision` | `POST /api/claims/{claim_id}/decision` | agent |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` | agent |
| `sign_off` | `POST /api/claims/{claim_id}/sign-off` | dashboard |
| `start_agent` | `POST /api/claims/{claim_id}/agent` | dashboard |
| `work_queue` | `POST /api/queue/agent` | dashboard |

`get_claim_history` returns only the customer's name and earlier claims. It leaves out their contact details and date of birth because the agent doesn't need them.

### The payment rules, in `pay_claim` and `sign_off`

- `record_decision(decision, payout, reason, policy_section)` takes `approve`, `decline` or `refer`. Declines and referrals have a payout of 0 and go straight to `decided`. An approval of $1,000 or less stays `in_progress` until it's paid. An approval over $1,000 goes to `awaiting_sign_off`.
- `pay_claim(amount)` pays only an approved claim, only for exactly the approved payout and only once. Over $1,000 it is refused with HTTP 409, "A payout over $1,000.00 needs a handler's sign-off", unless a handler has signed off. A payment moves the claim to `decided`.
- `sign_off(handler_id)` works only on a claim in `awaiting_sign_off`. It records the handler, releases the payment and moves the claim to `decided`.
- The $1,000 limit comes from `payout_approval_limit` in `data/company.json`.
- No real money moves. A payment is a row in the database.

### What's deliberately left out

As `docs/SPEC.md` says: no claims manual (the agent works from the policy wording alone), no sign-in, no real payments and no messages to customers. Scoring against `data/evals/` is also left out; that comes in a later build.

### Running the agent costs money

Tests never call a model. Six success criteria run the real agent on the engineer's OpenRouter key: two in Phase 3 and three in Phase 6, on claims CLM-1001, CLM-1003, CLM-1013 and CLM-1004 (CLM-1001 runs twice). Each run is one claim on `openai/gpt-6-luna` with low reasoning effort, or on `MODEL_NAME` if it's set, and costs a few cents at most.

---

## Phase 0: the commit guard

**Builds:** the Claude Code hook in `docs/CLAUDE_PRE_TOOL_USE_HOOK.md`: `.claude/settings.json` and `.claude/hooks/guard-commit.mjs`, copied exactly from that document and checked in. `.gitignore` ignores only `.claude/settings.local.json`. Claude Code may ask for approval to write under `.claude/`.

**Why first:** every later phase ends with a commit through the pre-commit hook, so the guard must be in place before the first one. It backs the rule in `docs/PROCESS.md`: never use `git commit --no-verify`. It blocks `--no-verify`, `git commit -n`, `LEFTHOOK=0` and `core.hooksPath`, and logs each block to `~/.claude/blocked-commits.log`. It also logs every `git` command it sees to `~/.claude/guard-calls.log`, to show that it is being called.

Success criteria:

- [x] Both files exist and match `docs/CLAUDE_PRE_TOOL_USE_HOOK.md`.
- [x] `.claude/settings.json` is valid JSON with a `PreToolUse` entry that matches `Bash`.
- [x] With sample input piped to the script and a temporary `HOME`: `git commit -m "x" --no-verify`, `git commit -n`, `LEFTHOOK=0 git commit` and `git -c core.hooksPath=x commit` each exit 2 and write one log line with `time`, `session`, `cwd`, `transcript` and `command`. `git commit -m "x"`, `git log -n 5` and `npm run check` exit 0 and add nothing to `blocked-commits.log`. Every command that contains `git`, and no other, adds a line to `guard-calls.log` with `blocked` true or false.
- [x] `git status` shows the two files as the only changes, and the commit goes through the pre-commit hook with its jobs skipped.
- [x] If Claude Code has loaded the hook in this session, a real `git commit --no-verify` is blocked with its message. Otherwise this is checked in the next session. The blocked command changes nothing. Checked in a later session: the command was blocked with "Blocked: the pre-commit checks must run." and changed nothing.

## Phase 1: the records and the queue (backend)

**Builds:** the SQLite database seeded from `data/` and the read operations: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions` and `list_handlers`. The agent's instructions are written to `backend/instructions.md`. They cover its job, the order of work, how to work out a payout under section 10 of the wording, when to refer, the two- or three-sentence reason with its policy section, and paying after an approval.

**Why first:** everything else reads from these records.

- `backend/db.py`: connect, create the tables and seed from `data/`. The path comes from `UNDERCOVER_DB` and defaults to `undercover.db`, which `*.db` in `.gitignore` already covers.
- `backend/seed.py`: `uv run -m backend.seed` rebuilds the database from `data/`, for a fresh start. `npm run reset` runs it.
- `backend/models.py`: Pydantic models for the responses, with `Literal` types for the states and decisions.

Success criteria:

- [x] `uv run pytest backend` passes. Each test runs against its own temporary database.
- [x] A test walks `app.openapi()` and asserts that every operation has an `operationId`, a one-line summary and no optional parameters or body fields.
- [x] `GET /api/claims` returns 25 claims, all `waiting`, with `claim_id`, `summary`, `claim_type`, `amount_claimed`, `submitted_on`, `customer_name` and `status`.
- [x] `GET /api/claims/CLM-1001` returns the story, the 3 items, the 4 documents and `"status": "waiting"`, with `decision`, `payment` and `sign_off` all `null`.
- [x] `GET /api/claims/CLM-9999` returns 404.
- [x] `GET /api/policies/POL-2001` returns the Premium plan, the trip to Rome and the traveler Maya Patel.
- [x] `GET /api/customers/CUS-3001/history` returns Maya Patel's one earlier claim, CLM-0412, and no email, phone, address or date of birth.
- [x] `GET /api/policy-wording` returns `data/policy_wording.md`, starting "# UnderCover Travel Insurance: Policy Wording".
- [x] `GET /api/instructions` returns the text of `backend/instructions.md`.
- [x] `GET /api/handlers` returns the 3 handlers.
- [x] `uv run -m backend.seed` rebuilds the database. A test runs it twice and finds 25 waiting claims.
- [x] `grep -rn "evals\|security" backend agent` finds no reference to `data/evals/` or `data/security/`.
- [x] `npm run check:python` passes with coverage at or above 80%.

## Phase 2: decisions, payments, sign-off and steps (backend)

**Builds:** `record_decision`, `pay_claim`, `sign_off`, `add_step` and `list_steps`, with the payment rules above. `ClaimSummary` also gains `decision` and `payout`: `list_claims` reads them from the decisions table with a left join, so both are `null` until the agent records a decision. They are outputs, so the "no optional inputs" rule is unaffected.

**Why now:** this is the core of the spec. Testing these rules on their own, before any model is involved, proves that the system blocks an over-limit payment however the agent behaves.

Success criteria:

- [x] `uv run pytest backend` passes, with a test for each rule below.
- [x] Approving CLM-1001 with a payout of 420.00 leaves it `in_progress`. `pay_claim` with 420.00 records the payment and moves it to `decided`.
- [x] Approving CLM-1003 with a payout of 3,750.00 moves it to `awaiting_sign_off`. `pay_claim` with 3,750.00 then returns 409 with "A payout over $1,000.00 needs a handler's sign-off", and no payment is recorded.
- [x] `sign_off` on CLM-1003 with `HND-01` records Dana Whitfield's sign-off and the payment, and moves it to `decided`. A second `pay_claim` returns 409.
- [x] `pay_claim` returns 409 on a claim that is declined, referred or has no decision, and when the amount isn't the approved payout.
- [x] `sign_off` returns 409 on a claim that isn't `awaiting_sign_off`, and 404 for an unknown handler.
- [x] Declining or referring moves the claim to `decided` with a payout of 0. A second `record_decision` on a decided claim returns 409.
- [x] `record_decision` returns 422 for a decision other than `approve`, `decline` or `refer`, or for a negative payout.
- [x] `add_step` stores a step with its `thread_id`, `kind` (`message`, `tool_call` or `tool_result`) and `text`. `list_steps` returns the claim's steps oldest first.
- [x] `list_claims` returns `decision` and `payout` as `null` for an undecided claim, and the decision and payout once one is recorded.
- [x] `npm run check:python` passes with coverage at or above 80%.

## Phase 3: the UnderCover Agent

**Builds:** the agent in `agent/main.py`, replacing the hello-world one. Its single entry point is `run(claim_id, thread_id)`.

- Tools, one per API call: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision` and `pay_claim`. When the backend refuses a call (4xx), the tool returns the backend's message to the model so it can see why, for example a blocked payment.
- At the start of each run, the system prompt is fetched from `get_instructions`.
- The run is streamed, and each model message, tool call and tool result is posted with `add_step`.
- `uv run -m agent CLM-1001` runs the agent on one claim from the command line.
- The backend gets `start_agent` and `work_queue`. Both run the agent in a FastAPI background task, and each run gets a new `thread_id`. The backend records "Agent started" and "Agent finished" steps around each run. If a run fails or ends without a decision, it records why and puts the claim back to `waiting`.
- The backend URL comes from `BACKEND_URL`, defaulting to `http://localhost:8000`.

**Why here:** the backend now enforces every rule, so the agent can be built and tested against it with a stub model.

Success criteria:

- [x] `uv run pytest agent` passes with a stub model (`GenericFakeChatModel`) and the backend through `TestClient`. No test calls a real model.
- [x] A stub run on CLM-1001 that reads the claim, policy, history and wording, approves 420.00 and pays leaves the claim `decided`, with a step for every message, tool call and tool result.
- [x] A stub run on CLM-1003 that approves 3,750.00 and then calls `pay_claim` leaves it `awaiting_sign_off` with no payment. The step trail shows the 409 message returned to the model.
- [x] A stub run that ends without a decision puts the claim back to `waiting`, with a step that says so.
- [x] `POST /api/claims/CLM-1001/agent` returns 202 and the claim moves to `in_progress` (agent stubbed in the backend test). It returns 409 if the claim isn't `waiting`.
- [x] `POST /api/queue/agent` runs the stubbed agent on every waiting claim in turn (backend test).
- [x] The agent's system prompt is the text from `GET /api/instructions` (test).
- [x] **Real model.** With `npm run dev:backend` running, `uv run -m agent CLM-1001` ends with CLM-1001 `decided`. `GET /api/claims/CLM-1001` shows a decision, a payout, a reason of two or three sentences and a policy section, and `GET /api/claims/CLM-1001/steps` lists the agent's steps.
- [x] **Real model.** `uv run -m agent CLM-1003` ends with a decision. If the agent approves over $1,000, the claim is `awaiting_sign_off` and has no payment.
- [x] `npm run check:python` passes with coverage at or above 80%.

## Phase 4: the dashboard, the queue and the claim

**Builds:** the dashboard in UnderCover's brand, replacing the health page.

- A header with the UnderCover name and a short tagline in Instrument Serif. Instrument Sans for the text and JetBrains Mono for claim ids and amounts, loaded from Google Fonts.
- **The queue:** a count of claims in each state, and a table with the eight columns in `docs/SPEC.md`: Claim, Customer (with the summary beneath), Type, Submitted, Claimed, Status, Decision and Payout. The Status cell is a chip in the state's color. The Decision cell reuses `VerdictChip`, and the Payout cell uses `money()` right-aligned like Claimed. A decline or referral shows `$0.00`, as on the claim page. With no decision yet, both cells show a muted dash.
- **The claim:** the summary, the story, the items, the documents, the policy (plan, add-ons, trip dates, trip cost and travelers) and the claim history. When there's a decision, it also shows the decision, the payout, the reason, the policy section, the payment and any sign-off.
- Light and dark modes that follow the system setting, with the brand's page backgrounds and rounded panels without outlines. Amounts are formatted as $1,250.00.
- Hash links such as `#/claims/CLM-1001`, so a claim can be opened directly. This needs no router library.
- `dashboard/src/api.ts` holds typed fetch functions for each operation. TypeScript is strict, with no `any`.
- **Separate end-to-end data:** the Playwright tests get their own backend on port 8001 with its own database, rebuilt by `backend.seed` at the start of each run, and their own Vite on port 5174. The tests never change the data you use in `npm run dev`. The Vite proxy target comes from `API_URL`, defaulting to `http://127.0.0.1:8000`.

**Why here:** the backend has real data and decisions to show by now, and the handlers' first need is to see the queue and each claim in full.

Success criteria:

- [x] `vitest` tests cover the queue table, a decided row showing its decision chip and payout, an undecided row showing a dash in both columns, the state counts, the claim view with and without a decision, and money formatting.
- [x] Playwright e2e: the queue shows 25 claims, and each state's count matches the chips in the table (the e2e tests share one database and run in parallel, so a fixed "Waiting 25" would depend on test order). Clicking CLM-1001 shows Maya Patel's story, its 3 items with amounts such as $245.00, and the Premium plan.
- [x] Playwright e2e: after the test approves CLM-1014 for $650.00 through the API, its queue row shows "Approved" and "$650.00".
- [x] Playwright e2e: after the test records a decision on a claim through the API, that claim's page shows the decision, payout, reason and policy section.
- [x] Checked in the browser, in light and dark mode (with the Playwright MCP server): the queue and claim pages use the brand's fonts and colors, panels are rounded with no outline, there are no one-edge borders and no thin line across the top of the page, and screenshots are reviewed. The queue is also checked at 1280 px and 1541 px wide: all eight columns fit, and only Customer wraps.
- [x] `npm run check:ts` passes with coverage at or above 80%. `npm run e2e` passes.

## Phase 5: the dashboard, the agent at work

**Builds:**

- **Run the agent:** a button on a waiting claim, and "Work the queue" on the queue page.
- **The agent's steps:** a timeline on the claim page with each message, tool call and tool result. Long tool results fold away. While the claim is in progress, the page polls every two seconds, and the queue refreshes too.
- **Sign-off:** on a claim waiting for sign-off, a panel says the payment is on hold (in Raspberry), with a handler picker and a "Sign off and pay" button. After sign-off, the panel shows who signed off and the payment.
- **Instructions:** a page with the agent's instructions from `GET /api/instructions`, read only.

**Why here:** this phase covers the rest of what the team needs to see: the agent at work, the sign-off and the instructions.

Success criteria:

- [x] `vitest` tests cover the steps timeline, the polling while in progress, the sign-off panel and the instructions page.
- [x] Playwright e2e: the test approves CLM-1012 over $1,000 through the API and tries to pay it, which returns 409. The claim page shows "Waiting for sign-off" and the payment on hold. Signing off as Priya Raman shows "Decided" and the payment, and the queue counts update.
- [x] Playwright e2e: steps posted through the API show up on the claim page in order.
- [x] Playwright e2e: the instructions page shows the text from `backend/instructions.md` and has no way to edit it.
- [x] Checked in the browser (with the Playwright MCP server): the steps timeline, the sign-off panel and the instructions page in light and dark mode, with screenshots reviewed.
- [x] `npm run check:ts` and `npm run e2e` pass.

## Phase 6: end to end, and handover

**Builds:** no new features. This phase runs the whole pilot as a handler would and brings the docs up to date.

- `docs/STATUS.md`: what's built, how to run it (`npm run dev`, `npm run reset`, `uv run -m agent <claim_id>`) and the states.
- `README.md`: a short note on running the pilot. It stays concise.

Success criteria:

- [x] `npm run reset` gives 25 waiting claims.
- [x] **Real model, in the browser (with the Playwright MCP server).** With `npm run dev` running, "Run the agent" on CLM-1001 shows the claim in progress, the steps appearing as the agent works, and then the decision with its reason and policy section.
- [x] **Real model, in the browser.** "Run the agent" on CLM-1013 and CLM-1004 ends with each claim decided or waiting for sign-off, and the queue counts match.
- [x] Any claim the real agent approved over $1,000 shows the payment on hold until a handler signs off in the dashboard. (CLM-1003 was also run from the dashboard for this, since the other three claims are under $1,000.)
- [x] `docs/STATUS.md` and `README.md` are updated.
- [x] `npm run check` passes: ruff, pyright, pytest at 80% or more, ESLint, Prettier, tsc, vitest at 80% or more, and Playwright.

## Phase 7: a light and dark slider

**Builds:** a slider in the dashboard's header, on every page, between light and dark. This is a dashboard-only change; the backend and the agent are not touched.

- **One attribute decides the look.** The `<html>` element carries `data-theme="light"` or `data-theme="dark"`. The dark colors in `dashboard/src/styles.css` move from the `prefers-color-scheme` media query to `:root[data-theme="dark"]`, so the stylesheet answers to one thing only.
- **The right mode from the first frame.** A few lines of script in `dashboard/index.html` set the attribute before the page draws: the saved choice if there is one, otherwise the computer's setting. Setting it from React instead would flash the wrong mode on every load.
- **The slider.** A "Dark mode" slider in the header, after "Agent instructions": a small track with a round dot, with the label beside it. The dot at the left means off and at the right means on. Clicking it flips the attribute and saves the choice in the browser's `localStorage`.
- **A real switch for screen readers.** `ThemeSwitch` in `dashboard/src/ThemeSwitch.tsx` is a `<button>`, so Space and Enter work, with `role="switch"` and `aria-checked`. A screen reader says "Dark mode, switch, off" or "on". The dot is `aria-hidden`, since the role already says the state.
- **The position carries the state, not the color.** The track is the muted text color when off and the fixed action color (`--action`) when on, so the color-blind palette in Phase 8 does not recolor it. Both keep at least 3:1 contrast against the page in light and dark. The dot is white.
- **Easy to hit and to see.** The track is about 44 by 24 pixels, and the slider has a visible focus ring. The dot moves with a short transition, which `prefers-reduced-motion: reduce` turns off.
- **Layout.** The header links, label and slider stay on one baseline. Nothing else in the header moves.
- **Starts in the computer's setting, as the spec says.** Until someone uses the switch, each load follows the computer's setting. After that, their saved choice wins. The choice is kept per browser, since the pilot has no sign-in.

**Why this approach:** keeping the mode in one attribute on `<html>` means the CSS, the start-up script and the slider never disagree, and the start-up script avoids a flash of the wrong mode. A slider matches what the control is, something that is on or off and not an action, and a `<button>` with `role="switch"` gives it that meaning for screen readers and the keyboard. It needs no new libraries.

Success criteria:

- [x] `vitest`: the slider is a switch named "Dark mode". `aria-checked` is `false` while the mode is off and `true` while it is on, and matches `data-theme` on `<html>`. Clicking flips both and saves the choice, and clicking again switches back. The dot is `aria-hidden`.
- [x] Playwright e2e: with the browser set to light and nothing saved, the queue starts light, with the page background `#F0F4F5`. Clicking the "Dark mode" switch turns it dark, with the background `#04232E` and `aria-checked="true"`. After a reload, and on the instructions page, it is still dark.
- [x] Playwright e2e: with the browser set to dark and nothing saved, the page starts dark. Choosing light is remembered after a reload.
- [x] Playwright e2e: off puts the dot at the left of the track and on puts it at the right (the dot's center is left of the track's center when off, and right of it when on), in light and in dark.
- [x] Playwright e2e: with the keyboard, Tab reaches the slider, Space flips it, and it shows a focus ring. With `prefers-reduced-motion: reduce`, the dot's transition duration is `0s`.
- [x] Checked in the browser (with the Playwright MCP server): the slider in the header on the queue, a claim and the instructions page, off and on, in both modes, with no flash of the other mode on reload. The dot is at the left when off and at the right when on, and the links and slider line up. Screenshots are reviewed. The no-flash check records the mode when the HTML finishes parsing, before the app runs, for each mix of computer setting and saved choice.
- [x] `docs/STATUS.md` says how to switch modes.
- [x] `npm run check` passes.

## Phase 8: a color-blind mode

**Builds:** the color-blind mode in `docs/ACCESSIBILITY.md`: a "Color-blind mode" slider in the header, next to "Dark mode". When it is on, the claim-state, decision and payment-on-hold colors change to the Okabe-Ito colors in that document, and each decision chip gains a symbol: a check, a cross or an arrow. When it is off, which is the default, the dashboard is exactly as `docs/BRAND.md` describes. This is a dashboard-only change.

- **Four state colors and one alert color carry everything.** The stylesheet already gives each decision the color of a claim state: Approved matches Decided, Declined matches In progress and Referred matches Waiting for sign-off. The color-blind mapping keeps those pairs. So `dashboard/src/styles.css` gets five variables (`--waiting`, `--in-progress`, `--sign-off`, `--decided` and `--alert`) plus the text color on each. The chips, the count-tile dots and the payment-on-hold box use them, and `:root[data-colors="color-blind"]` overrides them with the values and text colors in `docs/ACCESSIBILITY.md`.
- **Set before the page draws, like dark mode.** The start-up lines in `dashboard/index.html` also set `data-colors` on `<html>`, from the saved choice or else `brand`. There is no computer setting to start from, so the mode starts off.
- **One switch component for both modes.** `ThemeSwitch` becomes `ModeSwitch` in `dashboard/src/ModeSwitch.tsx`, which takes the label, the `<html>` attribute, its on and off values, and the storage key. It keeps Phase 7's slider, `role="switch"` and `aria-checked`. The header uses it twice: "Dark mode" (`data-theme`, `undercover-theme`) and "Color-blind mode" (`data-colors`, `undercover-colors`). Both look and behave the same. The slider's colors don't depend on the mode, so the color-blind palette leaves them alone.
- **Symbols on the decision chips.** `VerdictChip` in `dashboard/src/Chips.tsx` renders a small inline SVG before the word: a check for Approved, a cross for Declined and an arrow for Referred. Each has `aria-hidden="true"`, since the word already says it. CSS hides the symbols unless the mode is on, so React does not need to know the mode.

**Why this approach:** it reuses Phase 7's pattern of one attribute on `<html>`, set before the page draws. The mode is pure CSS, and the default brand look cannot change by accident, because the brand values stay where they are and the mode only overrides them.

Success criteria:

- [x] `vitest`: `ModeSwitch` works for both modes. It is a switch with its label as its name, `aria-checked` matches the attribute on `<html>`, and clicking it flips both and saves the choice under its own key, without touching the other mode.
- [x] `vitest`: each decision chip renders its symbol (check, cross or arrow) with `aria-hidden="true"`, and the chip's accessible name is still just its word, such as "Approved".
- [x] Playwright e2e: with nothing saved, the mode is off and the brand is unchanged. A Waiting chip is Cerulean `rgb(17, 138, 178)` with white text, a Decided chip is Sea Green, and no symbol is visible.
- [x] Playwright e2e: turning on "Color-blind mode" changes the chips to the colors in `docs/ACCESSIBILITY.md`. Waiting becomes `rgb(0, 114, 178)` with white text, and Decided becomes `rgb(0, 158, 115)` with black text. A decision chip shows its symbol, on the claim page and in the queue's Decision column, and the payment-on-hold box becomes `rgb(204, 121, 167)` with black text, on a claim the test approves over $1,000 through the API. The mode stays on after a reload, and turning it off restores the brand colors.
- [x] Playwright e2e: the two sliders are independent. With both on, the page is dark and the chips use the color-blind colors. Turning either off leaves the other as it was.
- [x] Playwright e2e: each slider puts its dot at the left when off and at the right when on, with color-blind mode on and off, and Space flips each from the keyboard.
- [x] No flash on load, checked as in Phase 7: when the HTML finishes parsing, before the app runs, `data-colors` already holds the saved choice, or `brand` with nothing saved.
- [x] Checked in the browser with the Playwright MCP server if its tools are loaded, otherwise with a Playwright script: the queue, a decided claim and a claim waiting for sign-off, with the mode on, in light and in dark. The header's two sliders line up with the page links, and the dot is at the left when off and at the right when on. Screenshots are reviewed.
- [x] `docs/STATUS.md` describes the color-blind mode and points to `docs/ACCESSIBILITY.md`.
- [x] `npm run check` passes.
