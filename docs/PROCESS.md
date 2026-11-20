# Process

`uv sync` and `npm install` at the repo root install everything, including a git pre-commit hook. `npm run dev` starts the backend and the dashboard.

`npm run check` runs every check:

- Python: ruff (lint and format), pyright, and pytest with 80% coverage
- TypeScript: ESLint, Prettier, tsc, and vitest with 80% coverage
- Playwright end-to-end tests

The pre-commit hook runs the format, lint, type and unit test checks on every commit.
Architecture regression tests run within pytest and Vitest, so the same hook checks the recorded module boundaries too. They supplement source review; green checks and coverage alone are not approval.

## Planning

When asked to plan, as in "Please plan the pilot", write the plan to `docs/PLAN.md` and write no code.

- Split the work into phases, usually 5 or 6, each building on the last.
- Identify module responsibilities and dependency direction before assigning files: transport, harness, tools, domain services, HTTP adapters and presentation. Record which existing boundaries must remain intact.
- Give each phase detailed success criteria that you can verify yourself: tests that pass, commands and their output, API calls and their responses, and pages you check in the browser with the Playwright MCP server. Write each one as a checkbox.
- Then stop and wait until you are asked to implement the plan.

## Implementing

When asked to implement the plan, as in "Please implement the plan for the pilot", build every phase in order without stopping. For each phase:

1. Build it, with tests.
2. Check every success criterion and fix whatever fails. Complete the architecture review below before treating the phase as checked.
3. Tick off its criteria in `docs/PLAN.md` and update `docs/STATUS.md`.
4. Commit. The pre-commit hook runs the checks; if it fails, fix the problem and commit again.

When the last phase is done, run `npm run check` and report the results.

## Architecture review gate

Before each implementation commit and final handover, inspect the actual diff, including new/untracked files, plus the affected callers. Record the findings and verification in `docs/STATUS.md` or the active plan.

- Trace one read and one write end to end. Confirm a single transport owner per client, named operations, and entry points that compose rather than export reusable implementation details.
- Inspect imports and state ownership: no imports back into entry points, no circular dependencies, no domain logic in generic harness code, and no mutable tool closures or cross-invocation state. Check the runtime-injected schema actually hides trusted dependencies/IDs from the model.
- Inspect backend handlers for SQL/business decisions, shared contracts for domain coupling, and dashboard components for URL strings, transport and string-based action routing. Investigate equivalent problems in adjacent layers rather than fixing only the reported example.
- Review prompts for goals and authority boundaries, not prescriptive workflows. Distinguish tested plumbing from model behavior; when prompts change, state whether a freshly seeded, isolated cap-five live trial was run. Do not carry prior live evidence forward as verification of new prompts.
- Recheck backend-enforced scope, retries, completion, provenance and payment/sign-off boundaries after moving code. Add contract/isolation regressions and executable architecture checks for newly established boundaries; keep the existing behavioral tests.
- Run all checks without weakening rules or thresholds. Report exact results, blockers and unverified claims. If review finds a boundary violation, fix it before committing, regardless of coverage.

The harness human review exposed a missing gate: acceptance tests and coverage had been used as a substitute for examining architecture. The explicit source-review checklist and executable boundaries above address that gap; neither can guarantee that all future design problems are caught.

## Rules

- Add tests with each change. Tests never call a model; use a stub model.
- Outside a plan, commit each change once you have checked it.
- Run `npm run check` before you hand work over.
- Never use `git commit --no-verify`.
- Never lower a threshold, turn off a rule or exclude a file to get a green run. If a rule looks wrong, stop and ask.
- Keep `docs/STATUS.md` up to date.
- Never push.
- Don't open `data/evals/` unless you're asked to.
- Everything must work on Windows: write `package.json` scripts as `uv run` commands or `.mjs` files.
