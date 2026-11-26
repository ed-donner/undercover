# Week 1 Day 3: the UnderCover pilot

Nicholas Dean

My build of the claims pilot from `docs/SPEC.md`, planned and built with a coding agent.

- The code: https://github.com/N-D20/undercover/tree/week1day3-nicholas
- The plan it followed: [docs/PLAN.md](https://github.com/N-D20/undercover/blob/week1day3-nicholas/docs/PLAN.md)

## What I did

1. Asked the coding agent to plan the pilot from the documents in `docs/`. It wrote a plan in six phases, each with success criteria it could check itself, twelve design decisions with the reason for each, and three questions for me.
2. Reviewed the plan, then asked it to implement it. Each phase was built with its tests, checked against its criteria and committed on its own, with the pre-commit hook running on every commit.

## What was built

- **Backend:** FastAPI and SQLite, 13 operations. It loads only the files it needs from `data/`, and a test fails if it opens `data/evals/`, `data/security/` or the claims manual.
- **Agent:** LangChain `create_agent` with three tools, `get_claim`, `record_decision` and `pay_claim`. The policy wording goes in the prompt, since it is short enough to fit. The agent reaches the backend only through its API and posts each step as it works.
- **Dashboard:** the queue with a count for each status, a claim page with the agent's steps arriving live, sign-off for a blocked payment, and the agent's instructions read only. In the brand, in light and dark mode.
- **Running the agent:** from the dashboard, on one claim or the whole queue. The backend runs it in the background, and a run that fails returns its claim to the queue.

## Decisions I would point to

| Decision | Why |
|---|---|
| The $1,000 rule lives in the backend's pay operation, not in the instructions | The spec says the payment must be blocked even if the agent tries to pay. The agent has a pay tool, and the backend refuses it until a handler signs off |
| Deciding and paying are two operations | It makes the block testable: record an approval for $1,800, call pay, get a refusal |
| Sign-off pays the claim in the same operation | The handler doesn't click twice, and the agent doesn't have to wake up again |
| Only a customer's name and claim history are loaded | Nothing in the pilot uses the contact details, so they never reach the agent |
| End-to-end tests play the agent's part through the API | Tests never call a model, and there is no test-only code in the product |

## Checks

`npm run check` passes in full:

- Python: ruff and pyright clean, 42 tests, 99% coverage
- Dashboard: Prettier, ESLint and tsc clean, 10 tests, 100% line coverage
- End to end: 5 Playwright tests, on their own ports and database

## Takeaways

- Strong spec-driven development (SDD) templates drive better results.
- With a strong harness, lower-tier models can perform as well as the flagship frontier models.

## Not done

The agent isn't scored against the handlers' decisions, and `data/evals/` was never opened. A handler can sign off a payment but can't change or reject the agent's decision.
