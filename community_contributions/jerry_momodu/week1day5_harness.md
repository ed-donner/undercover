# Week 1 Day 5: the agent's harness

My build of `docs/HARNESS.md`, starting from `week1day5-start`, done with Claude Code in six phases.

Branch: https://github.com/Jerrymomodu/undercover/tree/week1day5-jerry_momodu
Plan: https://github.com/Jerrymomodu/undercover/blob/week1day5-jerry_momodu/docs/PLAN_HARNESS.md

## What it adds

- **A queue agent and a claim agent**, both built with `create_agent`. The queue agent plans the run as a to-do list and hands each claim to a fresh claim agent through a `work_claim` tool, so its context grows by one line per claim, not by a whole claim's work.
- **Our own `write_todos` tool** rather than `TodoListMiddleware`, because the list needs a fourth state (left for a handler) and has to live in the backend for the dashboard to show it.
- **Sections in place of whole documents.** The policy wording and claims manual are split at their headings at seed time. The claim agent calls `list_sections` and `read_section`, and the claim page shows "What the agent read".
- **Recovery at three levels:** LangChain's retry and call-limit middleware for one call, `release_claim` for one claim (back in the queue on the first failure, left for a handler on the second), and a summary that says why if the whole run stops.
- **The cap and the missed-claims check enforced in code.** `work_claim` refuses a new claim past the cap, and `finish_run` refuses to finish while a waiting claim is missed under the cap.

## Takeaways

- The model decides, the harness enforces. Anything that must always hold (the cap, the retry count, never paying twice) belongs in code or the backend, not in the instructions.
- Subagents are mostly about context: a fresh claim agent per claim keeps every step of the run about the same cost.
- Live trials find what tests don't. The model left "Write the summary" in progress at the end of the first run, so `finish_run` now ticks off the last items itself.
