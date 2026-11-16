# My UnderCover pilot (Week 1 Day 3)

My build is on my fork: [FAbbas99/undercover, branch week1day3-FazalAbbas](https://github.com/FAbbas99/undercover/tree/week1day3-FazalAbbas). The plan I worked from is [PLAN.md](PLAN.md) in this folder.

## What I did

I asked my coding agent to plan the pilot from `docs/SPEC.md`, read the plan and pushed back on a few things, then had it build in six phases, one commit each:

1. Backend data and read operations (FastAPI on SQLite)
2. Decisions, sign-off and the payment rule
3. The UnderCover Agent, with four tools that all go through the backend
4. The dashboard's queue and claim page
5. Running the agent from the dashboard, live steps, sign-off and the agent's instructions
6. End-to-end tests and the status doc

The plan changed quite a bit between the first draft and the one I approved. The e2e tests in the first draft would have reused the dev backend, which meant a test run could call the real model on the real database, so they now get their own servers on 8001 and 5174 with a scripted model. The first draft was also vague about what happens after a sign-off, so now signing off pays the claim in the same step. And customers' contact details are no longer sent to the agent, since it doesn't need them.

After the six phases I added four things of my own:

- `uv run -m agent CLM-1001` runs the agent on one claim from the terminal
- `uv run -m agent` works through every waiting claim and prints a summary at the end
- model calls retry for about a minute when OpenRouter rate-limits them (my account is new, and I hit the limit a lot in the Day 2 lab)
- the queue shows each claim's decision and payout, so I can see how a batch went without opening every claim

## How it did

On a full run of the queue with Luna at low effort, the agent got 17 of 25 claims right:

| Difficulty | Right |
|---|---|
| Routine | 15 of 15 |
| Hard | 2 of 5 |
| Manual | 0 of 5 |

Three approvals came to more than $1,000 (CLM-1003, CLM-1008 and CLM-1011), and all three were left waiting for a handler's sign-off, as the spec asks. On CLM-1003 the agent tried to pay the $3,750 anyway, and the backend refused it.

## My takeaways

- **Reviewing the plan was the most useful hour of the day.** Every problem I caught there was a five-minute edit. Caught after the build, the e2e one would have meant redoing a phase.
- **Put the rules where the model can't reach them.** The $1,000 limit lives in the backend, not in the prompt. The agent did try to pay $3,750 on one claim and was stopped. If the limit had only been in the prompt, that payment would have gone through.
- **The manual claims are 0 for 5, and that's expected.** They depend on the claims manual and the customer's history, which the pilot deliberately leaves out. The agent can't be expected to know a rule it was never given.
- **Small commits made it easy to follow.** One phase per commit, with the tests passing each time, meant I could review each step on its own and always knew what had changed.
- **Tests that never call a model are worth the setup.** All 77 tests run against a stub model, so they're free, fast and give the same answer every time.
