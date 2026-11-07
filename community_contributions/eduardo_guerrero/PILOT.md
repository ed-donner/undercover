# UnderCover Pilot — Built with DeepSeek Harness

## Overview

I completed the UnderCover pilot from Week 1 Day 3 of Ed Donner's AI FDE course using **DeepSeek Harness (DSH) with DeepSeek-V4-Pro**, instead of Claude Code.

The goal was to explore Agentic Development Life Cycle (ADLC) practices using an alternative coding agent while following the project's existing specifications, development process, and quality standards.

## Development approach

I followed a specification-driven workflow:

1. Used the existing `AGENTS.md` and documentation in `docs/` as the project's development instructions.
2. Asked DeepSeek Harness to create `docs/PLAN.md` before writing application code.
3. Reviewed the implementation plan, which contained five phases with verifiable acceptance criteria.
4. Instructed DeepSeek to implement the approved plan, run tests, resolve failures, and document progress.
5. Verified that the dashboard was accessible and that claim details could be opened.

## What was built

- **Backend:** FastAPI, SQLite, claim management, decisions, payment approval rules, and REST endpoints.
- **AI Agent:** LangChain `create_agent` with backend API tools and configurable LLM integration.
- **Frontend:** React, Vite, and TypeScript dashboard for claim management.
- **Testing:** Python unit tests, TypeScript tests, and Playwright end-to-end tests.

## Validation results

| Test suite | Results | Coverage |
|---|---|---|
| Python | 39 tests passed | 96% |
| TypeScript | 12 tests passed | 91% |
| Playwright | 6 tests passed | — |

The complete `npm run check` command passed, as reported by DeepSeek Harness.

I also manually verified that the dashboard loads and displays claim details.

Automated agent tests used stub models, avoiding paid LLM calls. Live-model accuracy was not evaluated during this pilot.

## Challenges and lessons learned

On Linux, the DeepSeek Harness web interface initially failed to open the project directory with a `directoryPicker/pick failed: Failed to fetch` error.

Launching DSH with the following configuration resolved the issue:

```bash
env -u DISPLAY -u WAYLAND_DISPLAY \
DSH_WORKSPACE="$PWD" \
npx @deepseek-ai/dsh web --no-open
```

This allowed me to select the UnderCover project directory and continue development.

My main takeaway is that coding agents can implement substantial features when provided with clear specifications, a documented development process, and automated verification. Reviewing the plan before implementation helped maintain control over the work.

## Implementation

The complete pilot implementation is available in my fork:

[UnderCover pilot — eduardo_guerrero_week1day2](https://github.com/EduardoGuerreroIniguez/undercover/tree/eduardo_guerrero_week1day2)

The implementation follows the original project's technology stack and does not introduce real payments or deployment infrastructure.