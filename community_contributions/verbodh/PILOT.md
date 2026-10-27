# UnderCover pilot: VerBodh

My build of the Week 1 Day 3 pilot, planned in `docs/PLAN.md` (copied here) and built with Claude Code.

Repo: https://github.com/VerbodhDev/undercover-fde

## What I built

- **Backend:** FastAPI on SQLite, seeded from `data/` on first start. Read routes for claims, policies, claim history, the policy wording and handlers; write routes to start a claim, record steps, decide, pay and sign off.
- **Payment rule in the backend:** a payout over $1,000 is refused (403) until a handler signs off, the amount must match the approved payout, and a claim can only be paid once.
- **Agent:** LangChain `create_agent` on OpenRouter with six tools that call the backend over HTTP. It has no sign-off tool, so it cannot get round the rule.
- **Dashboard:** React and Vite. The queue, each claim with the agent's steps appearing live, the agent's instructions, handler sign-off, light and dark mode.
- **Checks:** 48 Python tests (99% coverage), 8 dashboard tests, 4 Playwright tests on their own ports and database.

## How it went

- Phases 1 to 5 done. The whole-queue run decided 10 of 25 claims before my OpenRouter credits ran out.
- The two large approvals (CLM-1003, $3,750 and CLM-1008, $2,240) stopped at "waiting for sign-off" as they should.

## Takeaways

- **Put the rule in the backend, not the prompt.** The agent was told about the $1,000 limit, but what made it safe was the 403.
- **Real runs find what tests miss.** The model guessed a policy id from the claim id; one clearer line in the instructions fixed it.
- **Concurrency bites early.** The dashboard polling and the agent together hit SQLite's same-thread check. I wrote a test that failed first, then fixed it.
- **Give e2e its own servers and database**, so tests never touch the dev data.
- **Watch the credits.** One failed model call stops the whole queue run; the next build should let it carry on to the next claim.
