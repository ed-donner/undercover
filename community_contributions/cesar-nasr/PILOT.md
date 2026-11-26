# Cesar Nasr's UnderCover pilot

This is my Week 1 pilot for Ed Donner's AI FDE course, built from the project
brief with Codex as my coding agent.

[My repository and pilot build](https://github.com/CesarNasr/undercover/tree/week1day3-cesarnasr)
| [The plan I followed](PLAN.md)

## What I built

- A FastAPI backend with a SQLite database seeded from the 25-claim queue.
  It exposes claims, policies, customer history, plans, policy wording and
  read-only agent instructions through the API.
- A LangChain agent that reads its context through backend tools, records an
  approve, decline or refer decision, calculates a payout and explains the
  decision with policy references. I configured `MODEL_NAME=openrouter/free`.
- A React dashboard for the queue, full claim evidence, decisions and activity,
  with controls to run the agent, sign off and record simulated payments.
  The instructions screen also explains what the agent reads and displays
  the policy wording.
- A CLI: `uv run -m agent` processes waiting claims sequentially in queue order,
  prints each saved decision and a final count. `uv run -m agent CLM-1001`
  processes one waiting claim. Both require the backend to be running and use
  its configured OpenRouter model.
- Backend enforcement of the $1,000 approval limit. An approved payout above
  that amount stays unpaid until a handler signs off. Payment must match the
  full stored approval; partial amounts and duplicate payments are rejected.

Decisions, run activity, sign-offs and simulated payments persist across restarts.
Interrupted undecided claims become available for an explicit retry; model runs
are not durably resumed. The pilot has no sign-in, real payments or customer
messages, and the agent does not receive the claims manual or evaluation files.

## Validation

The current Python suite has 26 passing tests with 98.92% coverage, including a
CLI-to-backend test using a stub model. Frontend checks and 11 component tests
pass, with 97.24% statement coverage. Five Playwright scenarios passed for the
pilot and instructions-screen update using an isolated database and scripted
model, including the sign-off barrier and payment persistence.

On the latest CLI check, `npm run check` passed its Python and frontend stages;
the browser stage could not start because my development backend occupied port
8000. No live-model accuracy score has been established: stub-model tests verify
workflow behavior, not the quality of OpenRouter's decisions.

## My takeaways

- Put the payment rule in the backend. A prompt asking the agent to wait for
  sign-off is not enough to enforce it.
- Separate coverage decisions from payment state. An approved claim can still
  need sign-off or a payment retry.
- A plan with checkable phases makes it easier to review the coding agent's
  work and distinguish implemented behavior from assumptions.
- Dependency compatibility matters. Older lint plugins broke ESLint 10; restoring
  compatible, pinned SonarJS and accessibility plugins fixed the checks without
  disabling rules.
- Operational details matter too: an old server can hold a port or retain an old
  model setting. I documented restarts, database backup/reset and CLI usage.
- Passing automated tests does not prove model accuracy. Clear activity and
  failure reporting are important when trying a real provider.

The full implementation lives in my fork. This contribution shares the write-up
and a copy of my pilot plan so other students can inspect the approach without
changing the course product.
