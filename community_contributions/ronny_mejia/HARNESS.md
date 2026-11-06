# My harness: a queue agent, claim agents and rules the backend enforces

My build of the Week 1 Day 5 harness, made with a coding agent from `docs/HARNESS.md`. I reviewed a six-phase plan before any code, and each phase went in as its own commit through the pre-commit hook.

Code: https://github.com/mejiaronny-code/undercover/tree/week1day5-ronnymejia

## What I built

- **Two agents.** A queue agent runs a whole queue: it writes its to-do list, picks the order, hands each claim to a fresh claim agent that starts clean, and finishes with a short summary. A run can be capped at a number of claims, and the claim agent can still be run on one named claim. Both are LangChain `create_agent` on OpenRouter.
- **Rules the backend enforces, not the prompt.** The run cap is checked atomically in the database, so two runs cannot both take the last slot. A claim that fails before it is decided goes back to `waiting`, and after a second failure it is left in a new fifth state, `needs_handler`. The queue agent cannot finish a run while a claim it took is missed, and no claim is decided or paid twice.
- **Reading the documents by section.** The policy wording and the claims manual are served as numbered sections with a search, so the agent reads only what it needs, and the dashboard shows which sections it read for each claim.
- **Middleware.** Retries for model and tool errors and a limit on model calls, so a bad call cannot loop. The default model is `deepseek/deepseek-v4.1-flash` at low reasoning, and `MODEL_NAME` overrides it.
- **Dashboard.** A sidebar layout with pill status chips, the run's to-do list updating as it works, the summary, what the agent read per claim, and both agents' instructions, read only. It keeps the MonarchWare look in light, dark and mobile.
- **Tests.** pytest with a stub model, including scripted failures (`CLM-1005` fails once and is retried, `CLM-1006` fails twice and goes to a handler), Vitest for the dashboard, and Playwright end to end for the pilot's flows plus a capped run and both failure cases. No test calls a real model.

## A live trial

After reseeding, one run capped at five claims on the default model worked five claims on its own and left 20 waiting: three approved, one declined and one referred. None was decided or paid twice, and no claim was left in progress.

## Takeaways

- The more a rule matters, the less it should depend on the model. The cap, the retry limit and the check for missed claims all live in the backend, so a cheap model that skips the to-do list or stops early cannot break them.
- Giving the queue agent claim agents that start clean kept each claim's reasoning separate, and made a failure on one claim cheap to retry without touching the others.
- Scripted failures in the stub model let me test the retry and `needs_handler` paths end to end, which a real model would only hit by chance.
- Plain, flat lists in the agents' instructions mattered: the dashboard's markdown renderer showed nested lists badly, and the instructions are what the team reads.
- A tight machine changed how I checked the work: I ran the end-to-end tests with a single worker and the full check only at the end, instead of repeatedly.
