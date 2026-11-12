# Harness: the UnderCover Agent runs the queue

Rongjun Geng, Week 1 Day 5.

- My build: <https://github.com/rjgeng/undercover/tree/week1day5-rj>, built on Ed's `week1day5-start`
- The plan: `docs/PLAN_HARNESS.md`. The human review: `docs/HUMAN_REVIEW_HARNESS.md`
- My Day 3 write-up: `community_contributions/rongjun_geng/PILOT.md`

## What I did

1. Started from Ed's `week1day5-start`, his pilot with the brief in `docs/HARNESS.md`.
2. Asked Claude Code (Opus 5.5) to plan the harness. It wrote `docs/PLAN_HARNESS.md`: six phases with 67 checkable criteria, and the choices the brief left open.
3. Reviewed the plan against the brief in `docs/HARNESS.md` before any code, checking that each of its seven requirements and the guarantees had a phase with checkable criteria, and approved it before asking it to build.
4. Asked it to implement the plan. The six phases took about half an hour, one commit each through the pre-commit hook, never `--no-verify`.
5. Phase 6 ran the real agent on a reseeded queue, capped at five claims, with the dashboard open through the Playwright MCP server. The first run failed two criteria. After the fixes, the second passed.
6. Ran a capped run of the next five claims myself.
7. Reviewed the code as a person, as Ed does in the lecture, and gave Claude Code the findings in `docs/HUMAN_REVIEW_HARNESS.md` to confirm, decide and carry out. Then I read the diff myself.

## How it works

- **Two agents on LangChain's `create_agent`, and no other framework.** `deepagents` stays in the labs.
- **The helper agent is a tool.** The queue agent's `work_claim` takes a claim into the run and creates a fresh claim agent for it. It catches any failure, and returns one line, such as `CLM-1001: approve $420.00, paid`. The queue agent's history grows by one line per claim.
- **The to-do list is a tool of our own,** `update_todos`, not LangChain's `TodoListMiddleware`. The list has to live in the backend for the dashboard, and it needs a fourth state, Left for a handler.
- **The backend holds every guarantee.**
  - A run can't take more claims than its cap, or finish while it has missed a waiting claim or left a to-do item open.
  - Only a claim in progress can fail. It goes back in the queue, and the second time it's left for a handler, so nothing is decided or paid twice.
  - Starting a run stops one left unfinished.
- **The run id reaches the queue agent's tools through LangChain's runtime context,** never from the model.
- **The claim agent reads the manual by section.** The backend splits the policy wording and the claims manual at their numbered headings. The agent reads a section with `read_section`, and the claim page lists what it read.
- **The instructions come from the policy wording and the claims manual,** never from the handlers' decisions in `data/evals/`.
- **Retries happen in one place.** A model call times out after 60 seconds, and `ModelRetryMiddleware` retries it twice. A tool that fails fails the claim, which goes back in the queue.
- **LangGraph stops an agent after 25 steps by default,** which would have cut off a run of five claims. A run now gets 20 steps per claim, and a claim agent 60.
- **The model is DeepSeek V4.1 Flash at low reasoning,** as the brief asks.

## Checks

- Python: ruff and pyright clean, 98 tests, 99.7% coverage, including two tests that send requests at the same moment.
- Dashboard: Prettier, ESLint and tsc clean, 32 tests, 100% statement coverage.
- End to end: 8 Playwright tests, including the queue page following a run's to-do list to its summary.
- A model is never called in tests. The stub model can also raise scripted errors, so the tests cover a timeout, a retry and a claim that fails twice.

## The live runs

Each of these runs started from a freshly seeded queue, capped at five claims.

| Run | What changed before it | Time | What it showed |
| --- | --- | --- | --- |
| 1 | The plan as built | 1 min 27 s | It finished with the last to-do item still In progress, and two reasons ran to four sentences |
| 2 | `finish_run` refuses while an item is open, and reasons are "never more" than three sentences | 1 min 8 s | Every item ticked off as it went, and every reason three sentences |
| 3 | The instructions rewritten as goal and tools, after the review | 62 s | The list stayed as planned until the end, and payouts waiting for sign-off were marked Done |
| 4 | The instructions say why the list must stay true, because the handlers watch it live | 27 s | Every item closed correctly. The agent handed out all five claims at once |

All four runs took the five oldest submissions and made the same decisions:

- CLM-1001 was approved for $420.00 and paid.
- CLM-1008 ($2,240.00) and CLM-1011 ($1,150.00) were approved and held for sign-off.
- CLM-1018 was referred for a missing proof of value.
- CLM-1010 was declined under the alcohol exclusion.

No claim failed. My own run of the next five declined CLM-1015 and CLM-1012, paid CLM-1004 $186.00, held CLM-1003 at $3,750.00 and referred CLM-1023.

Before the review, each claim agent read 10 to 12 sections, mostly the same ones every time. Since the review, the sections every claim needs come in its instructions, and it looks up two or three for the claim in front of it.

## What the human review found

- **The instructions were scripted procedures.** Confirmed. The queue agent now gets the goal, the tools and what the handlers rely on, since the backend holds the guarantees. The claim agent is given the sections every claim needs, and looks up the rest. Runs 3 and 4 show what this changed.
- **An approval of $0.00 was enforced only in the prompt.** Not confirmed. Ed's backend has refused it since the pilot, so nothing changed.
- **A new HTTP client for every backend call.** Kept. Opening a connection to the local backend costs very little next to a model call of several seconds.
- **The process docs.** `docs/PROCESS.md` now has a human review after each build. `docs/CODE_STANDARDS.md` records the standards it used: goal and tools over scripts, money and state rules in the backend, one place for configuration, and harness apart from domain code.

## What the review caught that the tests didn't

Looking for the same patterns elsewhere found a race on the run's cap. The cap held only while the queue agent followed its instruction to hand out one claim at a time. With eight `take_claim` calls sent at once, a cap of 1 was broken in 14 of 20 tries, and a claim could be started twice.

Each write request now takes SQLite's write lock before its check, with tests that failed before the fix. That fix was needed straight away: in run 4 the agent chose to work all five claims at once. My Day 3 pilot took this lock on every write from the start. Ed's pilot, which this build starts from, didn't, and an agent that calls tools in parallel made the gap matter.

## Takeaways

1. **Live runs catch what stub tests can't.** All the tests passed while the last to-do item was left open, the reasons ran long and the list went stale.
2. **Put the guarantees in the backend, and make them hold under parallel calls.** A rule that holds one request at a time isn't a guarantee once the agent can work in parallel. Here the real guard on the cap had been a line in the prompt. With that fixed, the agent could be given the goal.
3. **A goal needs its reason.** Taking out the steps lost the list's live updates, until the instructions said who watches it and why.
4. **Give up front what every claim needs.** Then the sections the agent looks up show its judgment, not a routine.
5. **Look past the review's own findings.** One of its three findings didn't hold, and the most important bug came from looking for the same pattern elsewhere.

## Not done

- I didn't score the agent against the handlers' decisions, and `data/evals/` was never opened.
- A run of the whole queue could hand out every waiting claim at once. Five at once is tested live, but twenty is not.
- A run starts from the command line, not the dashboard, and only one run goes at a time.
- I haven't compared my build with Ed's `week1day5-end` yet.
