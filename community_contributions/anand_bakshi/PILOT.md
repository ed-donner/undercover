# Anand Bakshi: the UnderCover pilot

My build of the Week 1 Day 3 pilot is on the `week1day3-AB` branch of my fork:
https://github.com/anandbakshi76/undercover/tree/week1day3-AB

## What I did

I planned the pilot from `docs/SPEC.md` with my coding agent (the plan is in `PLAN.md` here), reviewed it, then built it in six phases, one commit each:

1. Records and the read API: FastAPI and SQLite, seeded from `data/`, leaving out the eval answer key
2. Decisions, payments and sign-off: claim states, with payouts over $1,000 held for a handler's sign-off
3. The UnderCover Agent: `create_agent` on OpenRouter, with tools that call the backend and post each step
4. Dashboard shell, queue and instructions: React, Vite and TypeScript in the UnderCover brand
5. The claim page: the policy, the decision and its reason, the payment, the agent's steps as it works, and sign-off
6. End-to-end Playwright tests, live checks and the handover in `docs/STATUS.md`

After the plan, I added a dark mode switch that remembers the choice.

In the live checks the agent approved and paid CLM-1001 and CLM-1002, declined CLM-1013 (inside the 12-hour waiting period), referred CLM-1010 (whether the alcohol exclusion applies) and approved CLM-1008 for $2,240, which waited for sign-off.

## Takeaways

- Reviewing a written plan before any code was the most useful step: it was where I could change the approach cheaply.
- Building in phases with a commit for each kept every step small enough to check, and easy to go back to.
- Rules that matter to the business, such as sign-off over $1,000, belong in the backend, not in the agent's instructions, so the agent can't get around them.
- End-to-end tests that stand in for the agent let the whole product be checked without spending on model calls.
