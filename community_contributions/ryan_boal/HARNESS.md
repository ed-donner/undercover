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

## A live run capped at five

One run on DeepSeek V4.1 Flash took about a minute and a half. I have not scored it against the evals. The run was before the fixes below, which I have tested only with stub models.

| Claim | Decision | Payment | Sections read |
|---|---|---|---|
| CLM-1001 | Approve $420.00 | Paid | 9 |
| CLM-1008 | Approve $2,240.00 | Held for sign-off | 8 |
| CLM-1010 | Decline | None | 8 |
| CLM-1011 | Approve $1,150.00 | Held for sign-off | 8 |
| CLM-1018 | Refer | None | 7 |

No claim failed, so the retry paths have been tested only with stub models.

## What we learned

- **A contents list mostly replaced search.** Only one of the five claim agents searched. The others went straight to the sections they needed.
- **Search needed stemming.** A search for "monkey" missed "Monkeys" until we turned on the Porter stemmer.
- **A request in the instructions isn't a rule.** They ask for reasons of two or three sentences, and three of the five ran longer. The limits enforced in code held.

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
- **Next: score it.** One run of five claims shows that the harness works, but says little about whether the decisions are right. I'd score it against the handlers' decisions, then see whether it can read fewer sections without losing accuracy.
