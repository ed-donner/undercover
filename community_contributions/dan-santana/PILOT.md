# Dan Santana's UnderCover pilot

[Repository and pilot build](https://github.com/DanLivassan/undercover/tree/main)

Implemented the Week 1 Day 3 pilot from `docs/SPEC.md` with Codex, following the
reviewed plan in [PLAN.md](PLAN.md). The build was completed in six phases, with
local commits and the project's pre-commit checks enabled throughout.

## What the pilot does

- Loads the 25 queue claims into SQLite without overwriting work on restart.
- Gives the LangChain agent HTTP tools for the claim, customer history, policy,
  plan limits, add-ons and complete policy wording.
- Records an approve, decline or refer decision with its calculation, a short
  explanation and the relevant policy section.
- Separates decisions from payments. The backend blocks payouts over $1,000
  until a handler signs off, and repeated payment requests cannot pay twice.
- Shows the queue, claim evidence, live agent activity, decisions and read-only
  instructions in a responsive React dashboard.
- Runs one claim with `uv run -m agent CLM-1001`, or all waiting claims in order
  with `uv run -m agent`.

## Implementation takeaways

The payment limit belongs in the backend transaction. Instructions alone cannot
guarantee that an agent will stop before making an unauthorized payment.
Keeping approval, sign-off and payment separate makes that boundary testable.

A scripted model can exercise the actual agent and its HTTP tools without
paying for model calls. The browser suite pauses that model so it can verify
activity while a claim is still in progress, then releases it to finish.

For this pilot, SQLite and two-second polling provide persistence and a visible
workflow without introducing infrastructure for later course days. Explicit
seed-file selection keeps evaluation data out of the agent's context.

## Validation and scope

`npm run check` passes: 35 Python tests with 99.24% coverage, 15 dashboard tests
with 99.1% statement coverage, six Playwright tests, formatting, lint and types.
The browser checks cover approval and payment, over-limit sign-off, decline,
referral, read-only instructions, keyboard navigation and mobile layout.

Payments are simulated. No sign-in, AWS resources, customer messages, manual
rules or later-course features were added. No evaluation answer keys were read,
and claim accuracy with a live model has not been measured.
