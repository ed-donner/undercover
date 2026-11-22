# The UnderCover Agent's harness

This is my Week 1 Day 5 build for Ed Donner's course, AI FDE: The Forward Deployed Engineer & Agentic AI Architect. I'm UnderCover's forward deployed engineer, and I directed Claude Code (Claude Opus 5.5) through the course's process: a plan in six phases with success criteria, the build, then Ed's code review in `docs/HUMAN_REVIEW_HARNESS.md` and the fixes it asked for.

My build: https://github.com/Feyisa-Diba/undercover/tree/week1day5-start

The plan it followed: https://github.com/Feyisa-Diba/undercover/blob/week1day5-start/docs/PLAN_HARNESS.md

Its status, with the live trial and the known limitations: https://github.com/Feyisa-Diba/undercover/blob/week1day5-start/docs/STATUS.md

## What I built

The harness turns the pilot's single agent into two, built with LangChain's `create_agent` on OpenRouter:

- **The queue agent** plans a run as a to-do list that the handlers watch on the dashboard. It hands each claim to a claim agent, within a cap: `uv run -m agent --cap 5`.
- **The claim agent** works one claim from a clean start. Instead of being handed whole documents, it looks up the sections of the policy wording and the claims manual it needs with `list_sections`, `search_sections` and `read_section`.
- **Middleware** retries a failed model call 3 times with backoff, and stops a claim agent after 30 model calls. An `after_model` hook sends the queue agent back to work, at most 3 times, if it tries to finish while there are claims it could still work.
- **Recovery:**
  - A claim that fails goes back in the queue, and one that fails twice is left for a handler.
  - A claim left in progress by a run that stopped is released when the next run starts.
- **The dashboard** shows:
  - the to-do list
  - claims left for a handler
  - the sections the agent read
  - failed steps

```
uv run -m agent ─▶ harness.py ─▶ tools.py ─▶ api.py ─▶ backend /api ─▶ SQLite
                   model,         11 tools,    every backend call,
                   middleware,    thin         one base URL
                   recovery       wrappers
```

## Answering the code review

Ed's review found four problems in the first build, and all four were real:

- **Two ways to call the backend.** There were about 20 hard-coded API paths, and `main.py` imported `request` from `tools.py`.
- **Modules that reached into each other.** `queue_agent.py` imported from `main.py`, and there was no module for the backend's API.
- **A harness spread across modules.** The model, the middleware and the recovery were spread across `main.py` and `queue_agent.py`, and mixed with UnderCover's own rules.
- **Scripts, not goals.** Both sets of instructions were numbered, step-by-step scripts.

They got through because every check was green: tests, linters, types and the plan's criteria. None of those can see structure, and nothing asked for a design or a review.

The fix:
- **`agent/api.py`** holds every backend call, with the base URL in one place.
- **`agent/tools.py`** holds all 11 tools, as thin wrappers over `api.py`.
- **`agent/harness.py`** holds the model, the middleware and the recovery.
- **The run's state** reaches the queue agent's tools and middleware through `create_agent(context_schema=RunContext)` and `ToolRuntime[RunContext]`, as the review suggested.
- **The instructions** now give each agent a goal, what a good result is and the constraints it must respect.

I found the same kinds of problem in the backend and the dashboard and fixed them:
- The backend's routes now share one `APIRouter(prefix="/api")`, and one helper replaces five copies of a status check.
- The dashboard has one `BASE_URL`.

So that this doesn't happen again:
- `CODE_STANDARDS.md` has new Structure and Agents sections.
- `PROCESS.md` asks for a design in every plan and a pull-request-style review of each phase's diff before it's committed.

## How it was built

| Phase | What it built | Criteria met |
| --- | --- | --- |
| 1. Attempts, releasing a claim, and runs | Counting a claim's attempts and releasing a failed claim, and runs with a to-do list, in the backend | 11 of 11 |
| 2. The wording and the manual in sections | Sections stored, listed, searched and read | 8 of 8 |
| 3. The claim agent | Eight tools, retries and a call limit, and a line back for each claim | 13 of 13 |
| 4. The queue agent | The to-do list, the cap, the check for missed claims and recovery | 14 of 14 |
| 5. The dashboard | The to-do list, sections read, failed steps and claims left for a handler | 8 of 8 |
| 6. A live trial, and the documents | The trial with the real model, and the spec, tech stack and status | 4 of 8 |

## Test results

The final `npm run check` passed:

- **Python:** 96 pytest tests with 99.56% coverage, plus ruff and pyright with 0 errors.
- **TypeScript:** 33 vitest tests with 100% of statements and lines covered, plus ESLint, Prettier and strict tsc.
- **End to end:** 8 Playwright tests, which watch the to-do list fill in and be ticked off, and cover a claim left for a handler, the sections read, and a handler signing off a held payout.

The tests never call a model. Stub models drive both agents through the real API, including:
- provider errors and retries
- a claim agent that never stops
- a queue agent that tries to finish early
- a claim that fails twice

## Live runs

On November 16, 2026, I ran these on a fresh database with the default model, DeepSeek V4.1 Flash at low reasoning effort:

- **`uv run -m agent CLM-1005`** approved the claim and paid $243.00, in 2 minutes 16 seconds. The claim agent read 14 of the 26 sections, 8 of them in the claims manual.
- **`uv run -m agent --cap 5`**, watched in the browser, worked the five longest-waiting claims in 13 minutes. The to-do list filled in and was ticked off, and 20 claims stayed waiting.
- **A second capped run**, which I started while the first was finishing, worked five claims in 11 minutes, one of them CLM-1010 again.

| Claim | Decision | Payout | Outcome |
| --- | --- | --- | --- |
| CLM-1001 | approve | $800.00 | Not paid. It should have been $420.00 |
| CLM-1003 | approve | $3,750.00 | Waiting for sign-off |
| CLM-1004 | approve | $186.00 | Paid |
| CLM-1008 | approve | $2,240.00 | Waiting for sign-off |
| CLM-1010 | decline | $0.00 | Worked by both runs (below) |
| CLM-1011 | approve | $1,150.00 | Waiting for sign-off |
| CLM-1012 | decline | $0.00 | |
| CLM-1015 | decline | $0.00 | |
| CLM-1018 | refer | $0.00 | Proof of value needed for a jacket bought for cash |

The results:

- Every decision names a section and gives a reason, though three reasons run to four sentences.
- Every approval over $1,000 waits for a handler's sign-off with no payment.
- Each claim agent read 8 to 14 sections, at least 4 of them in the manual.

The trial found two problems, both since fixed with tests on a stub model:

- **The to-do list lagged behind the claims.** The model handed over two claims at once, so the list couldn't be updated until both came back. `work_claim` now keeps each claim's item in step.
- **CLM-1001 was decided too early.** Its claim agent recorded the plan's $800 maximum as the payout, then worked out $420 and tried to record it again. The backend refused to change the decision, or to pay $420 against $800, so no wrong money went out. The instructions now say that a recorded decision is final. The rewrite from a script to a goal had dropped "record, then pay" from the end.

## Not yet verified

Four of phase 6's live criteria are still open:

- **The to-do list kept in step, live.** It was seen working on the trial run, but the fix hasn't had a live run.
- **Every approval paid exactly its payout.** This failed on CLM-1001, and the fix hasn't had a live run.
- **Every worked claim's page.** Its steps and the sections read were checked in the browser for CLM-1008 only.
- **The finished run on the queue page.** The run's finish and summary were checked through the API, but not on the queue page.

The retest needs a fresh database. I've kept the trial's database as it is for now.

## Known limitations

- **One queue run at a time.** A run starts by releasing every claim in progress, so a second run released CLM-1010 while the first was still working it. Two claim agents then worked it at once, and it used up both its attempts.
- **A stopped run is never finished.** A run stopped with Ctrl+C, or whose process is killed, is never marked finished.
- **A recorded decision can't be corrected,** by the agent or by a handler. CLM-1001 stays approved at $800 and unpaid, with nothing to prompt a handler.
- **It's slow.** A claim takes the default model about two minutes, so a run of five takes 11 to 13 minutes.
- **The decisions aren't scored yet** against the handlers' decisions in `data/evals/`. That comes with evaluations in Week 2.

## Takeaways

- **Green checks are not a review.** Every check was green on code that a reviewer rejected on sight. Structure needs a design up front and a review of each diff.
- **A goal still needs its constraints.** Rewriting the instructions as a goal dropped one rule that mattered, and a claim was recorded at the wrong payout. What must happen in a fixed order belongs in code, or in a stated constraint.
- **Let the backend hold the line.** The agent's mistake on CLM-1001 cost nothing, because the backend refused to change a decision or pay a different amount.
- **Live runs find what stubs can't.** Only the real model showed the parallel tool calls that left the to-do list behind, and two runs releasing each other's claims.
