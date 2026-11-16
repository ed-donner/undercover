# My pilot: the UnderCover claims platform

My build of the Week 1 pilot, made with a coding agent from `docs/SPEC.md`. The plan I reviewed before building is in `PLAN.md` next to this file.

Code: https://github.com/mejiaronny-code/undercover/tree/week1day3-ronnymejia

## What I built

- **Backend** (FastAPI and SQLite), seeded from `data/`. It never reads `data/evals/` or `data/security/`. It serves claims, policies, customers, plans, handlers, the policy wording and the agent's instructions, and it records decisions, payments, sign-offs and the agent's steps.
- **The payment block lives in the backend.** A payout over $1,000 returns 409 until a handler with `can_approve_over_limit` signs off. The agent has a pay tool, so the rule is tested against an agent that tries to pay.
- **The agent** decides one claim with seven tools that call the backend's API. Each tool call is logged as a step. Its instructions are a file the backend serves, and the agent loads them from the API, so the dashboard and the agent always show the same text.
- **Running the agent**: from the terminal (`uv run -m agent.main CLM-1001`, or with no ids for every waiting claim) and from the dashboard. Waiting claims run four at a time, a model error is retried up to three times, and a failed claim does not stop the rest.
- **Dashboard** (React, Vite, TypeScript) in the MonarchWare look, light and dark: the queue with state filters, a claim in full with the agent's steps, Run agent and Sign off buttons, a Run agent on queue button, and a read-only page for the instructions. The queue and claim pages refresh on their own.
- **Tests**: pytest for the backend and agent with a stub model, Vitest for the dashboard, and Playwright end to end with a scripted agent (a small claim paid straight through, and a payout over $1,000 that waits for sign-off).

## Takeaways

- Writing the plan first and reviewing it before any code made the build predictable. The decisions section caught things I would have found late otherwise, such as where the payment rule should live.
- A rule the business must never break belongs in the backend, not in the agent's prompt. The prompt asks the agent to behave, and the backend makes the other outcome impossible.
- Running through the real flow showed problems the tests did not: the agent only worked the first claim, and runs started from the terminal did not show up in the dashboard until the CLI went through the backend.
- Tests with a stub model keep the suite free and fast, and one real run by hand checks that the model and the tools work together.
