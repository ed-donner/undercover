# Week 1 Day 5: the harness

Ryan Boal

My build of the harness brief in `docs/HARNESS.md`, starting from Ed's `week1day5-start`. I directed the work; Claude Code planned and built it in six phases.

**Code:** https://github.com/ryanboal/undercover/tree/week1day5-start (the branch keeps Ed's name, but holds the finished build)

**Plan:** [PLAN_HARNESS.md](https://github.com/ryanboal/undercover/blob/week1day5-start/docs/PLAN_HARNESS.md)

## How it works

- **A queue agent and a claim agent.** The queue agent plans the run as a to-do list and hands each claim to a fresh claim agent, which reports back in a line. Both use LangChain's `create_agent` and its middleware.
- **Rules in code.** The model chooses the order and writes the summary. The tools enforce the cap and the check for missed claims, and the backend enforces retries, sign-off and never deciding or paying twice.
- **Looking things up.** The wording and the manual are split into 26 sections and searched with SQLite's FTS5. The instructions hold only their contents, and the claim page shows each section the agent read.
- **Failures.** A claim that fails goes back in the queue. After a second failure it moves to a new state, Needs a handler, instead of being recorded as a referral the agent never made.

## Live runs and score

All on DeepSeek V4.1 Flash, scored against the handlers' decisions in `data/evals/decisions.json` after each run. The agent never sees that file.

| Run | Time | Decision and payout right |
|---|---|---|
| Capped at five, before the fixes below | about 1.5 min | 5 of 5 |
| All 25, after the fixes | 7 min 46 s | 24 of 25 |

| Difficulty, in the full run | Claims | Right |
|---|---|---|
| Routine | 15 | 15 |
| Needs the manual or the claim history | 5 | 5 |
| Hard | 5 | 4 |

The miss was CLM-1025, approved and paid at $71.00. The handler referred it because the carrier's certificate doesn't give the cause of the delay. The agent took the cause from the customer's story and said the certificate confirmed it.

In the full run, three approvals over $1,000 were held for sign-off and the other twelve were paid once each. No claim failed in either run, so the retries and outage handling have been tested only with stub models. Each run was done once, and the held-out claims are not scored.

## What we learned

- **A contents list mostly replaced search.** Only 3 of the 25 claim agents in the full run searched. The others went straight to the sections they needed.
- **Search needed stemming.** A search for "monkey" missed "Monkeys" until we turned on the Porter stemmer.
- **A request in the instructions isn't a rule.** They ask for reasons of two or three sentences, and three of the five in the first run ran longer. The limits enforced in code held.

## Gaps found after the build

Every check was green, but rereading the code for this write-up found four gaps. Each now has a fix and tests that failed before it.

- `--cap 0` ran the whole queue, because zero was read as no cap. A cap below 1 is now refused.
- A claim agent that failed between approving and paying left the claim unpaid. The harness now pays it, within the sign-off limit.
- A second run released the claim the first was working on. Only one agent now runs at a time on a machine.
- A backend error at the wrong moment stopped the run. Short outages are now waited out, and the run carries on after other backend errors. With stub models, a run survived the backend being killed and restarted. A backend that stays down still ends the run, and the next one puts right what was left.

## My takeaways

- **Let the model organize, and let the code guarantee.** The agent planned its own work and kept its own to-do list, and I didn't need to trust it with the cap or the payments, because the tools and the backend refuse what isn't allowed.
- **Green checks only cover the failures you thought of.** The build met every criterion in its plan and still had four gaps. Asking "what if it stops right here?" at each step found them, so I'd put that question in the plan next time.
- **A lost reply is harder than a failed request.** When a reply never arrives, the payment may or may not have gone through. Retrying blindly isn't safe, so the harness checks the claim's state and the backend refuses a second payment.
- **Scoring found what the checks couldn't.** The harness worked as designed on CLM-1025, and the decision was still wrong: the agent read the right rule, then trusted the story over the document. I haven't tuned the instructions to this miss, because they must not come from the answer key. Next I'd try a general rule from the manual, that a document must itself state what it has to prove, and test it on the held-out claims.
