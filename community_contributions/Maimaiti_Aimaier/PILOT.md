# Maimaiti Aimaier: the UnderCover pilot

My build of the Week 1 Day 3 pilot is on the `week1day3-omar` branch of my fork:
https://github.com/omarkusan/undercover/tree/week1day3-omar

## What I did

I planned the pilot from `docs/SPEC.md` with my coding agent (the plan is in [PLAN.md](PLAN.md) here), reviewed it, then built it in six phases, one commit each:

1. The records: FastAPI on SQLite through Python's built-in `sqlite3`, seeded from `data/`. Tests check that no code reaches `data/evals/` and that no response returns a customer's contact details.
2. The claim workflow and the payment rule: start, steps, decide, pay and sign-off. The backend refuses any payment over $1,000 until a handler signs off, and the sign-off makes the payment, so a claim can't end up signed off but unpaid.
3. The UnderCover Agent: `create_agent` on OpenRouter, with tools that go only through the backend's API. The instructions live in the backend, which serves them with the policy wording added at the end as the agent's whole system prompt. The agent reports each tool call, result and reply to the backend as a step.
4. The dashboard and the queue: React in the UnderCover brand, in light and dark mode, with hash addresses and state counts that refresh every 2 seconds. The Playwright tests run their own backend, dashboard and database, so `npm run check` never touches the dev data.
5. The claim page with the agent's steps as they happen, sign-off with a handler's name, and the instructions page, read only.
6. Working the queue: `npm run agent` decides every waiting claim in order, and `docs/STATUS.md` says how to run it all.

Two choices in the plan worth a look: the agent runs from the command line, not from a button in the dashboard, so the backend doesn't depend on the agent; and a referred claim counts as Decided with the decision Refer, keeping to the spec's four states.

## The run

In my last run of the full queue, the agent approved 17 claims, declined 6 and referred 2. Three approvals were over $1,000 (CLM-1003 for $3,750, CLM-1008 for $2,240 and CLM-1011 for $1,150) and are waiting for a handler's sign-off, unpaid. The agent's accuracy against the handlers' decisions isn't measured yet, since that needs `data/evals/`.

## Takeaways

- A rule that matters to the business, like sign-off over $1,000, belongs in the backend, not only in the prompt. A test with a stub model that tries to pay anyway proves the agent can't get around it.
- Showing handlers the exact system prompt the agent receives makes its decisions easier to trust and to question.
- Reviewing a written plan, then building in phases with a commit each, kept every step small enough to check.
