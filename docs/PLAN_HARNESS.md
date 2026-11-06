# Plan: the harness

This plan builds the brief in `docs/HARNESS.md` on top of the pilot as `docs/STATUS.md` describes it, following `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`. It has five phases, each building on the last. Every phase ends with its checks green, `docs/STATUS.md` updated and a commit. `docs/PLAN.md` stays as the pilot's finished plan.

## What we're building

In the pilot, our code organizes the work: a Python loop hands the agent one claim at a time, and the agent reads the whole policy wording on every claim. After this build the agent organizes its own work. The code around it, the harness, makes sure the work gets done and that nothing goes wrong twice.

- **The queue agent** runs once for the whole queue. It lists the waiting claims, plans a to-do list, hands each claim to the claim agent, tries a failed claim again and finishes with a summary for the handlers.
- **The claim agent** is the pilot's agent, started fresh for each claim. It looks up the sections of the policy wording and the claims manual it needs, instead of reading the whole wording.
- **The harness** retries failed model and tool calls, limits how long each agent can run, puts a failed claim back in the queue, and stops either agent from finishing with its work undone.
- **The backend** gains runs (each with its to-do list and summary), the two documents section by section, a `left_for_handler` status and an operation that releases a failed claim.
- **The dashboard** shows the current run's to-do list on the queue page, what the agent read on each claim page, and both sets of instructions.

```
uv run -m agent --cap 5
 +- queue agent: list_waiting_claims, write_todos, work_claim      --> backend /api
 |   +- work_claim(CLM-1007), one claim at a time
 |       +- start_claim
 |       +- claim agent, fresh for each attempt: get_claim, get_policy, get_customer,
 |       |    list_sections, search_documents, read_section, record_decision, pay_claim
 |       |    (every step posted to the claim, as in the pilot)
 |       +- read the claim back from the backend; release_claim if it isn't done
 |       +- one line back to the queue agent
 +- finish_run with the summary            dashboard polls: the run's to-do list, each claim
```

## Key decisions, and why

1. **Two agents, both on `create_agent`, and the claim agent is a tool of the queue agent.** `work_claim(claim_id)` builds a new claim agent with its own instructions and a new thread id, and starts it with nothing but "Decide claim CLM-1007." The queue agent sees only the one line that comes back, so its context grows by a line per claim and the claim agent never carries earlier claims. That keeps the cost of each step flat through a long run. The brief asks for no other framework, so the to-do list and the subagent are our own code on LangChain. Deep Agents has both and is installed for the labs, but it stays out of the product.

2. **The harness judges each attempt from the backend's record, not from what the model says.** When the claim agent stops, `work_claim` reads the claim back and writes the line itself: "CLM-1001: approved $420.00 and paid.", "CLM-1003: approved $1,500.00, waiting for sign-off.", "CLM-1013: declined." or what went wrong. A model can say it paid when it didn't, but the backend's record can't be wrong about that.

3. **Problems are put right at three levels.**
   - *A call.* LangChain's `ModelRetryMiddleware` retries a model call that fails or times out, with backoff. `ToolRetryMiddleware` does the same for a tool whose call to the backend fails. These are the only retries: the OpenAI client's own retries are turned off, so three retries means three. Retrying a decision or a payment is safe because the backend refuses a second one.
   - *An attempt.* Each agent has a limit on model calls (`ModelCallLimitMiddleware`): 25 for a claim attempt, and 10 plus 4 per claim for the queue agent. A model going round in circles stops and costs little. LangGraph's own default step limit in this version is 10,007, which in practice is no limit.
   - *A claim.* An attempt that ends with the claim unfinished is a failure, whether an error ended it or the agent just stopped. `work_claim` records a failure step on the claim and calls `release_claim`. The backend counts the attempts: a claim goes back to `waiting` after its first failure and to `left_for_handler` after its second. The backend enforces this, as it does the $1,000 rule, so it holds across runs and whatever the agent does.

4. **Neither agent can stop with its work undone.** A small middleware of our own runs when an agent is about to finish. It checks the backend and, if something is left, sends the agent back with a reminder. It's an `after_model` hook that jumps back to the model, and I tried it against the installed LangChain. The claim agent gets a reminder if it has recorded no decision, or has approved $1,000 or less without paying. The queue agent gets one if it has missed a waiting claim within its cap, including one that failed once and is waiting for its second try. The instructions ask both agents to check for themselves, and the middleware is there for when a model forgets. It reminds an agent at most twice. After that the agent stops, and the level above handles it.

5. **"Left for a handler" is a fifth status, kept apart from the others.**

   | Status | What it means | Who acts |
   |---|---|---|
   | `decided`, with the decision `refer` | The agent decided the claim needs a person's judgment or a missing document | A handler, as in the pilot |
   | `waiting_for_sign_off` | The agent approved a payout over $1,000 | A handler signs off, which pays it |
   | `left_for_handler` | The agent failed on the claim twice, or approved it and failed to pay | A handler works the claim |

   A claim that was approved but not paid can't go back in the queue, because its decision is final. So a failure after the decision leaves it for a handler straight away. The payment is retried within the attempt and the claim agent is reminded to pay, so this should be rare. The dashboard has no screen for a handler to work these claims, just as it has none for referrals.

6. **`work_claim` enforces the cap and the scope, not the prompt.** `uv run -m agent --cap 5` lets the run start five claims, and a sixth is refused with "This run is capped at 5 claims." The cap counts claims, not attempts, so the second try at a failed claim doesn't use it up. `uv run -m agent CLM-1004` runs the same queue agent, limited to the claims named. Claims are worked one at a time: `work_claim` holds a lock, so if the model asks for two claims in one turn, the second waits for the first. Nobody asked for parallel work.

7. **The to-do list is our own `write_todos` tool, stored on the run in the backend.** It works like LangChain's `TodoListMiddleware`: the agent sends the whole list each time, a pattern models know well. But that middleware has three statuses and keeps the list inside the agent, where the dashboard can't see it. Ours has the four statuses the brief names (`to_do`, `in_progress`, `done` and `left_for_handler`) and saves each version through `update_todos`. A run is a row in the backend with its to-do list, its summary and its start and finish times. The queue page shows the latest one.

8. **The documents are looked up section by section.** The backend splits the policy wording (12 sections) and the claims manual (14) at their numbered headings. The claim agent gets three tools: `list_sections` (the contents of both documents), `search_documents(query)` (a keyword search that returns the five best sections with the lines that match) and `read_section(document, section)`. The contents show how each document is laid out, and the search finds what a title hides, such as the note on wild animals inside the manual's section 7, "Interpretation notes". Two short documents don't need embeddings. The agent's whole-wording tool goes. The `get_policy_wording` operation stays in the backend for anything else that uses it.

9. **Two sets of instructions, written as goals.** `backend/instructions/queue.md` and `backend/instructions/claim.md` are served together by `get_instructions` and shown together on the instructions page. They say what to achieve and what matters. The wording comes first and the manual covers what the wording leaves open. A claim is referred only for the manual's reasons. The reason is written for a handler. They aren't a numbered list of steps, and they don't repeat the manual's rules, since the agent now looks those up. They're written from the wording and the manual only, never from `data/evals/`.

10. **The model.** Both agents use DeepSeek V4.1 Flash (`deepseek/deepseek-v4.1-flash`) at low reasoning, or the model in `MODEL_NAME` if it's set. Your `.env` doesn't set it, so the live run uses the default.

## Changes to the API

Every operation keeps an `operation_id`, a one-line docstring and only required inputs, and the OpenAPI test covers the new ones. An unknown id returns `404`, the wrong state `409` and invalid input `422`, as before.

| Operation | Route | Inputs | What it does |
|---|---|---|---|
| `list_sections` | `GET /api/documents/sections` | | The number and title of every section of the policy wording and the claims manual |
| `search_documents` | `GET /api/documents/search` | `query` | Up to five sections that best match the query's words, best first, with the lines that match |
| `read_section` | `GET /api/documents/{document}/sections/{section}` | | One section in full. `document` is `policy_wording` or `claims_manual` |
| `release_claim` | `POST /api/claims/{claim_id}/release` | | After a failed attempt on a claim in progress. With no decision, back to `waiting`, or `left_for_handler` at the second failure. With a decision, `left_for_handler` |
| `start_run` | `POST /api/runs` | | Starts a run with an empty to-do list |
| `update_todos` | `PUT /api/runs/{run_id}/todos` | `todos` | Replaces the run's to-do list. Each item has `content` and `status`. Refused once the run has finished |
| `finish_run` | `POST /api/runs/{run_id}/finish` | `summary` | Records the summary and the finish time, once |
| `get_latest_run` | `GET /api/runs/latest` | | The most recent run, or `null` before the first |

These existing operations change:

- `get_instructions` returns `queue` and `claim` in place of `text`.
- `add_step` takes a fourth `kind`, `failure`.
- `get_claim` and `list_claims` include `attempts`, the number of failed attempts.
- `pay_claim` also needs the claim to be in progress, so an agent can't pay a claim left for a handler.

The database gains a `runs` table and an `attempts` column, so a database from the pilot needs `uv run -m backend.seed`.

## Phase 1: The wording and the manual, section by section

Builds `backend/documents.py`, which splits both documents at their `## ` headings, and the `list_sections`, `search_documents` and `read_section` operations. The claim agent swaps `get_policy_wording` for the three lookup tools, and `backend/instructions.md` is rewritten as goals that draw on the manual. `docs/SPEC.md` now says decisions follow the wording and the manual. This phase comes first because it stands on its own, and the claim agent in every later phase uses it.

- [x] `GET /api/documents/sections` returns the policy wording's 12 sections and the claims manual's 14, including `claims_manual` 9, "Repeat claims", and `policy_wording` 10, "How we work out your payment".
- [x] `GET /api/documents/claims_manual/sections/10` returns "Meals without receipts" with the $35 allowance, and `GET /api/documents/policy_wording/sections/3` returns "Trip Delay".
- [x] `GET /api/documents/claims_manual/sections/99` returns `404`, and an unknown document returns `422`.
- [x] `GET /api/documents/search?query=monkey` returns the claims manual's section 7 with the line on wild animals. `query=meals without receipts` puts the manual's section 10 first, and a query that matches nothing returns an empty list.
- [x] A stub claim agent that calls `search_documents` and `read_section` records both calls and their results as steps on the claim, in order.
- [x] The claim agent's tools are `get_claim`, `get_policy`, `get_customer`, `list_sections`, `search_documents`, `read_section`, `record_decision` and `pay_claim`.
- [x] `docs/SPEC.md` says decisions follow the policy wording and the claims manual, and no longer lists the manual under "Not for now".
- [x] `npm run check:python` passes.

## Phase 2: A failed claim is put right

Builds the claim agent's side of the harness. The backend adds `attempts`, the `left_for_handler` status, the `failure` step and `release_claim`, and `pay_claim` now needs a claim in progress. The agent splits into `agent/common.py` (the backend client and the model) and `agent/claim_agent.py`. In it, `work(claim_id)` starts the claim, runs one attempt of the claim agent in a fresh context, judges the attempt from the backend, releases the claim if it isn't done and returns one line. The claim agent gets the retry and call-limit middleware and the finish check from decision 4, and the default model becomes DeepSeek V4.1 Flash. Until Phase 3, `uv run -m agent` still works the waiting claims in a loop, now through `work`, so a failure prints a line and the loop moves on. This phase comes before the queue agent because the queue agent relies on `work` always coming back with a line.

- [ ] Through the API: start a claim and release it, and it's `waiting` with `attempts` 1. Start it and release it again, and it's `left_for_handler` with `attempts` 2, and a third start returns `409`.
- [ ] Releasing a claim that is waiting, decided or waiting for sign-off returns `409` and changes nothing.
- [ ] Releasing a claim approved for $420 and not paid leaves it `left_for_handler` with its decision, and `pay_claim` on it then returns `409`.
- [ ] A stub run that approves CLM-1001 for $420 and pays it returns "CLM-1001: approved $420.00 and paid." Tests check the lines for a decline, a referral and an approval waiting for sign-off the same way.
- [ ] With a stub model that raises on every call, `work` returns a line saying what went wrong instead of raising. The claim is `waiting` with `attempts` 1, with a `failure` step under that attempt's thread id. A second `work` leaves it `left_for_handler`.
- [ ] With a stub model that raises once and then decides, the retry middleware recovers, the claim is decided and `attempts` stays 0.
- [ ] A tool whose call to the backend fails once with a connection error is retried, and the attempt succeeds.
- [ ] A stub model that calls `get_claim` again and again stops at the model call limit, and the claim is released.
- [ ] The finish check: a stub that approves $420 and stops is reminded, then pays, and the claim ends `decided` and paid. A stub that stops without a decision is reminded, and if it stops again the claim is released.
- [ ] `uv run -m agent`, tested with the stub, carries on to the next claim after one fails.
- [ ] The default model is `deepseek/deepseek-v4.1-flash` at low reasoning, `MODEL_NAME` overrides it, and `docs/TECH_STACK.md` says so.
- [ ] `docs/SPEC.md` adds "left for a handler" to the queue's statuses, with the rules that a claim that fails twice is left for a handler and that no claim is decided or paid twice.
- [ ] `npm run check:python` passes.

## Phase 3: The queue agent

Builds runs in the backend (`start_run`, `update_todos`, `finish_run` and `get_latest_run`) and `agent/queue_agent.py`. The queue agent has three tools, `list_waiting_claims`, `write_todos` and `work_claim`, with its own retry and call-limit middleware and the finish check for missed claims. `run(cap, claim_ids)` starts a run, works it and records the summary. If the queue agent itself fails, the run is finished with "The run stopped: ..." and the error goes on to the command line. No claim is left in progress, because the queue agent can only fail between claims. The instructions split into `backend/instructions/queue.md` and `claim.md`, and the dashboard's instructions page shows both. The command line becomes `uv run -m agent [--cap N] [claim ids]`. It prints each claim's line as it comes, then the summary. `agent/main.py` goes.

- [ ] Through the API: `GET /api/runs/latest` is `null` on a fresh database. `POST /api/runs` returns run 1 with an empty to-do list. `PUT /api/runs/1/todos` replaces the list, and a status other than the four returns `422`. Finishing records the summary, and after that, updating the to-do list or finishing again returns `409`. `GET /api/runs/latest` returns the newest run.
- [ ] `GET /api/instructions` returns `queue` and `claim`, from the two files.
- [ ] The cap: a stub run with a cap of 2 that tries to work three claims gets a refusal for the third, which stays waiting, and exactly two claims have left `waiting`.
- [ ] The to-do list: a stub run's `write_todos` calls are saved to the run, and `GET /api/runs/latest` returns the last list with its statuses.
- [ ] A failed claim doesn't stop the run: with the claim agent stubbed to fail on CLM-1002, the run goes on to decide CLM-1003, and CLM-1002 is `waiting` with `attempts` 1.
- [ ] A failed claim is tried again: the same run works CLM-1002 a second time and decides it, and with a cap of 2 the second try isn't refused.
- [ ] A claim that fails twice is reported to the queue agent as left for a handler, its status is `left_for_handler`, and the run finishes normally.
- [ ] The check for missed claims: a stub that finishes after one of the two claims within its cap is sent back with the missed claim's id, works it and finishes. A stub that keeps finishing early is reminded twice, and then the run ends. A run that has used its cap finishes with the other claims still waiting and gets no reminder.
- [ ] A named run: with `CLM-1004` named, the queue agent can work CLM-1004 and nothing else, and `work_claim` on any other claim is refused.
- [ ] The summary is saved by `finish_run` and printed last. A queue agent whose every model call fails leaves the run finished with "The run stopped" and no claim in progress.
- [ ] `list_waiting_claims` gives the queue agent no customer names, and `get_customer` still gives the claim agent no personal details.
- [ ] Outside its tests, `agent/` opens no files and imports nothing from `backend/`: `grep -rnE "open\(|from backend|import backend" agent --include='*.py'` finds matches only in `agent/tests/`.
- [ ] Vitest: the instructions page shows the instructions for running the queue and for working a claim, with no way to change them.
- [ ] `docs/SPEC.md` describes one run for the whole queue, the cap, the to-do list and the summary. `docs/TECH_STACK.md` describes the two agents and their entry points.
- [ ] `npm run check` passes.

## Phase 4: The dashboard

Builds the run panel on the queue page. It shows the latest run's number, when it started, whether it's running or finished, its to-do list with each item's status and, once it's finished, its summary, refreshing every 2 seconds. The new status, left for a handler, gets a count and a Raspberry badge, the brand's fifth color. The to-do statuses use the same colors as the claim statuses: Cerulean for to do, Marigold for in progress, Sea Green for done and Raspberry for left for a handler. On the claim page:

- "What the agent read" lists the sections it read, with their titles from `list_sections`.
- The lookup steps get labels, such as "Searched the documents for 'monkey'".
- Failure steps are marked, and a line shows where each new attempt starts.
- The decision panel covers a claim left for a handler and a claim back in the queue after a failure.
- The decision's section is labeled "Relied on", since it can now come from the manual.

- [ ] Vitest tests cover the run panel from a stubbed API (no run yet, a running run with an item in each status, and a finished run with its summary), the five status counts, the badge for a claim left for a handler, the list of sections read with their titles, the lookup labels, the failure steps and the attempt lines, and the decision panel for a claim left for a handler.
- [ ] `npm run check:ts` passes: Prettier, ESLint, tsc and vitest with at least 80% coverage.
- [ ] End-to-end: after a run is started and its to-do list posted through the API, the queue page shows each item and its status. An update shows without a reload, and after the run finishes, the page shows its summary.
- [ ] End-to-end: a claim started and released twice through the API shows "Left for a handler" on its page, with its failure steps, and the queue shows it as left for a handler.
- [ ] End-to-end: after a `read_section` step for the claims manual's section 9 is posted through the API, the claim page lists "Claims manual, section 9: Repeat claims" under what the agent read.
- [ ] End-to-end: the instructions page shows both sets of instructions.
- [ ] In the browser with the Playwright MCP server, the queue page with a run, and a claim page with lookups and a failure, read clearly in light and dark mode and follow the brand, and the console shows no errors.
- [ ] `npm run check` passes.

## Phase 5: The harness on real claims

Runs the real queue agent on DeepSeek V4.1 Flash through OpenRouter for the first time, capped at five claims as the brief asks. `npm run dev` is up, with the dashboard open through the Playwright MCP server. The phase fixes whatever the run turns up, most likely in the instructions, and reseeds before any second run. It's the only phase that calls a model, and five claims on this model should cost a few cents.

- [ ] After `uv run -m backend.seed`, `uv run -m agent --cap 5` prints a line for each of five claims, then a summary for the handlers.
- [ ] While it runs, the queue page shows the to-do list appear and its items move to in progress and then done, and at the end the run shows as finished with its summary.
- [ ] Afterwards, five claims have left `waiting`, 20 are still waiting, and none is in progress.
- [ ] Each of the five claim pages shows the agent's steps, with at least one section of the manual or the wording under what the agent read. Each decided claim has a decision, a reason of two or three sentences and the section it relies on.
- [ ] Among the five, every approval of $1,000 or less is paid, and every approval over $1,000 is waiting for sign-off and unpaid.
- [ ] If the run retried a claim or left one for a handler, its page shows the failure, and if the cause is in our code or instructions, it's fixed.
- [ ] `docs/STATUS.md`, `docs/SPEC.md` and `docs/TECH_STACK.md` describe the product as it now is. `docs/STATUS.md` says how to run it (`npm run dev`, `uv run -m agent --cap 5`, `uv run -m agent <claim ids>`, `uv run -m agent`, `uv run -m backend.seed` and `npm run check`) and that a database from the pilot needs reseeding.
- [ ] `npm run check` passes, and the results are reported.

## Not in this build

- Scoring the agent against the handlers' decisions in `data/evals/`. `docs/PROCESS.md` says not to open that folder unless asked, so I'll do it only if you ask.
- Working claims in parallel.
- Screens for a handler to work a referred claim or one left for a handler, and a button on the dashboard that starts a run.
- A record of the queue agent's own steps. Its to-do list, the line for each claim and its summary are what the team sees.
- Stopping a run with Ctrl+C partway through a claim leaves that claim in progress. Reseed to start again.
- Searching the documents by meaning. A keyword search is enough for two short documents.
- Wording versions (the manual's section 13), since there's only one version.
- Sign-in, real payments and messages to customers, as before.
