# Pilot: the UnderCover claims platform

Rongjun Geng, Week 1 Day 3.

- My build: <https://github.com/rjgeng/undercover/tree/week1day3-rj>
- The plans: `docs/PLAN.md` for the pilot, and `docs/PLAN_PILOT_FIXES.md` for the fixes that came from comparing it with Ed's build

## What I did

1. Asked Claude Code (Opus 5.5 at extra high effort) to plan the pilot from the documents in `docs/`. It wrote `docs/PLAN.md`: 6 phases, 9 design decisions and checkable criteria for each phase.
2. Before I reviewed the plan, four review agents went through it, each from a different angle, and a skeptic tried to refute each one's findings. 29 of the 33 findings held up and went into the plan before any code was written.
3. Asked it to implement the plan. Phases 1 to 5 took about 20 minutes, with one commit per phase through the pre-commit hook and never `--no-verify`.
4. While it built, two code reviews ran in the background, one on the backend and one on the agent and dashboard, again with a skeptic checking each finding. Their fixes went in as two separate commits.
5. Phase 6 ran the real agent on the whole queue with the dashboard open.
6. Compared my branch with Ed's `week1day3-end`, with a second agent checking each difference before it counted.
7. Planned the fixes in `docs/PLAN_PILOT_FIXES.md`, had that plan reviewed the same way, and built its four phases. The fourth gave the agent a procedural prompt and ran the queue a second time.
8. The second run raised a question for the business: can an approval pay $0.00? I decided it can't, since the spec has handlers "approve the claim with a payout". Ed's build already refused it, which my comparison had missed. A fifth phase added that rule and two small prompt changes, and ran the queue a third time.

## The decisions I reviewed

1. The backend owns each claim's state, and the $1,000 rule lives in `pay_claim`, not in the prompt.
2. A referral is a decision, so a referred claim is `decided` with the decision `refer`.
3. Sign-off pays the claim in the same operation. Exactly $1,000.00 needs no sign-off. After the second run, an approval must also pay more than $0.00.
4. The harness does the fixed steps in code: it starts the claim and puts the instructions and the policy wording in the system prompt. The model makes the decision through five tools.
5. A tool gives the backend's refusal back to the model as text, because a tool that raises ends the whole run.
6. No customer record's contact details reach the model. In the pilot, the agent's history tool stripped them. The fixes moved that into the backend: `get_claim_history` returns only the earlier claims, and no route serves the email, phone, date of birth or address from anyone's customer record. A claim's own documents still reach the model as the customer filed them, and CLM-1008's county notice gives the customer's home address.
7. The dashboard polls every 2 seconds, with hash routes and no router library.
8. The end-to-end tests run on their own ports and database, and each test that changes a claim uses one of its own.
9. The product never reads the claims manual, `knowledge.json`, `data/security/` or `data/evals/`.

## Checks

- Python: ruff and pyright clean, 61 tests, 99% coverage. The tests fail on any file read without an encoding, so a problem that would only show on Windows shows on a Mac too.
- Dashboard: Prettier, ESLint and tsc clean, 24 tests, 99% to 100% statement coverage (it varies a little between runs).
- End to end: 6 Playwright tests, run in parallel workers. A model is never called in tests.

## Three runs of the queue

Each run started from a freshly seeded queue and ran `uv run -m agent` on all 25 claims, on GPT-6 Luna at low reasoning, for a few cents.

| Run | What changed before it | Time | Approved | Declined | Referred |
| --- | --- | --- | --- | --- | --- |
| 1 | The pilot: a prompt that states the goal, plus the policy wording | about 8 min | 16 | 6 | 3 |
| 2 | A numbered procedure, its coverage and payout rules citing the wording; one tool call at a time | 4 min 54 s | 17 | 5 | 3 |
| 3 | No approval at $0.00; refer in the spec's words; a pair or a set is one item | 16 min 33 s | 16 | 6 | 3 |

Every run held the same three claims for sign-off: CLM-1003 at $3,750, CLM-1008 at $2,240 and CLM-1011. After the first run, Claude Code signed off CLM-1011 as Dana Whitfield through the dashboard, with a Playwright script, and it was paid.

Run 2 read every claim first, then read the policy and the history with that claim's own ids. In run 1, the model had guessed the ids from the claim id until a refusal corrected it. Five claims came out differently across the runs:

- **CLM-1018 and CLM-1020 swapped.** Run 2 approved CLM-1018 at $330, which run 1 had referred, and referred CLM-1020, which run 1 had approved at $240. Run 3 agreed with run 2 on both.
- **Run 2 approved CLM-1024 at $0.00.** An earlier claim had already paid $250 for the same phone, which left nothing under the $300 per-item limit after the $50 deductible. Run 1 had declined it. The backend now refuses an approval at $0.00, and run 3 declined it too.
- **CLM-1011 went from $1,150 to $1,330 and back.** In run 3 the agent counted the jacket and trousers as one suit, and the camera and its lens as one item, as section 5 says, and came to run 1's $1,150. Run 2's reasons weren't kept, so I can't say which step gave it $180 more.
- **Run 3 got CLM-1021 wrong, by my reading.** It gave the headphones the Electronics Plus limit, but section 8's list of electronics doesn't include headphones. Its $954 should be $825, which runs 1 and 2 paid, and none of the prompt changes touched it. I left the prompt alone: changing it after every run to fix one claim is chasing noise, and the held-out claims are the way to measure accuracy.

**Speed.** I first put run 2's speed down to the procedural prompt. Run 3 then took more than three times as long, though each claim still took only five or six steps. Even the step from reading a claim to reading its policy, which needs no working out, took 2 to 4 seconds for the first two claims and the last five, and 4 to 11 seconds for the 18 in between, most of them 7 or more. The model's response time varies a lot between runs and even within one, so a few runs can't separate the prompt's effect from the provider's.

## What the reviews caught that the tests didn't

- **A race on writes.** Two requests could both pass the same state check, so two runs could start the same claim. Taking SQLite's write lock before each check fixed it. The first version of that fix then failed with `database is locked` under load, because FastAPI committed on a different thread from the one holding the lock. A probe with six concurrent starts per claim found it.
- **Personal data through an id.** The model could pass `../customers/CUS-3001` as a claim id and read a customer's full record. The tools now accept only ids like `CLM-1234`.
- **A payment racing its decision.** With parallel tool calls on, a model that sent the decision and the payment in one message had the payment refused. The model now makes one tool call at a time.
- **Two misreadings of the wording in my fixes plan.** Its draft prompt would have applied the per-item limit to medical bills too, capping CLM-1003's $3,800 hospital bill at $300. It would also have checked that every event fell within the trip, which would have declined CLM-1008, a cancellation, since a cancellation always comes before the trip. Both were fixed before the second run.
- **A crash one of the fixes made possible.** Once a step had to have text, a reply from the model that was only whitespace would have been refused as a step and ended the run. The agent now skips blank notes.

## Compared with Ed's build

Both builds share the same design: the same four claim states, the $1,000 rule in the backend's payment operation, a five-tool agent on `create_agent`, a dashboard that polls every 2 seconds, and end-to-end tests on their own ports. Both first runs held the same three claims for sign-off, and they came out close: 16, 6 and 3 for me against Ed's 17, 5 and 3.

- **Mine was stronger on concurrency and robustness.** It takes a write lock before every state check and commits before responding, and it reseeds in place. Its tools accept only well-formed ids, it makes one tool call at a time with a step limit, it polls in order, and it shows a plain message when the backend is down. Ed's build lets two runs start the same claim. It also deletes the database file on reseed, and it lets `..` in an id reach any route.
- **Ed's was stronger on validating input and on data.** It refused a decision with empty reasons or section, an approval with a $0.00 payout, and a step on a claim nobody had started. Its history operation never served personal data at all, where mine stripped it only in the agent. Every panel showed loading and error states, a decline showed no "$0.00", files were read as UTF-8 for Windows, and a failed claim didn't stop the queue run.
- **The prompts differed the most.** Ed's is a numbered procedure: read the claim first, check the trip dates and the 90-day window, and follow strict rules for when to refer. It also says that an approval always has a payout and that a pair or a set counts as one item. My comparison missed both, and my build came to them only after run 2. Parts of his prompt closely paraphrase the claims manual, which the spec keeps out of the pilot. Mine stated the goal and relied on the wording alone, and my model guessed ids until a refusal corrected it.

**What I took from Ed's build.** The fixes brought in all of his strengths above but one. My build now:

- refuses empty reasons, an approval at $0.00 and a step on a claim nobody has started
- serves no one's email, phone, date of birth or address from the customer records
- shows loading and errors in every panel, and no "$0.00" on a decline
- reads files as UTF-8

It also took three of his dashboard touches: the time of each decision, the add-ons' names and the current page marked in the header. Separately, my error alert is now large and bold, so its white text on Raspberry passes WCAG AA. My prompt is now a procedure too, but every rule in it comes from the policy wording or the spec, none from the claims manual. The one strength I left out is the queue carrying on after a failed claim, which is Week 1 Day 5 work in the course.

## Takeaways

1. **Review the plan before the code.** The plan reviews found a refusal that would have ended the agent's run in the pilot plan, and two misreadings of the wording in the fixes plan, before any of that code existed.
2. **Stub tests don't test the model or concurrency.** All the tests passed while the race and the payment ordering were still there. The code reviews found them, and their probes proved them.
3. **Put the rule where the model can't break it.** The backend refuses a payment over $1,000 until a handler signs off, and an approval of $0.00, whatever the agent tries.
4. **Don't read too much into one run.** The three runs took from 5 to 17 minutes for the same work, and five claims came out differently between them, CLM-1021 with no prompt change that touched it. Comparing prompts needs several runs and a scored set of claims.
5. **Some questions belong to the business.** Whether an approval can pay $0.00 wasn't a coding question. The spec's own words settled it, the same way Ed's build had.

## Not done

I didn't score the agent against the handlers' decisions, and `data/evals/` was never opened. A failed claim still stops the queue run, which the course builds on Week 1 Day 5. The Playwright MCP server needs Google Chrome, which I hadn't installed, so the browser checks ran as Playwright scripts instead.
