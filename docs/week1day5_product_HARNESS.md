# Getting ready for harder claims

From the head of claims operations, with our IT team.

## Where we're heading

Our claims are going to get harder to decide. From now on, decisions follow the claims manual as well as the policy wording, and over the coming months we expect claims with more documents, more rules to weigh and more to look up. We want the UnderCover Agent to grow into that work: taking on longer jobs, working through them on its own, and dealing with problems without someone stepping in.

In the pilot (`docs/STATUS.md`), our code does much of the organizing. It feeds the agent one claim at a time and gives it the whole policy wording every time, and a claim that fails partway stays stuck in progress. We want the agent to organize its own work instead.

## What we want

1. **One run works the whole queue.** We start the agent once and it works every waiting claim, choosing the order itself, then finishes with a short summary for the handlers. For trials we need a way to start a run capped at a number of claims, with the rest left waiting, so a trial on five claims costs little. We still need to be able to run it on one named claim.

2. **A to-do list we can watch.** The agent plans its work as a to-do list and keeps it up to date as it goes, with each item to do, in progress, done or left for a handler. The queue page of the dashboard shows the list for the current run, so the team can see what the agent means to do and how far it has got.

3. **A fresh helper for each claim.** The agent running the queue hands each claim to a subagent that works that one claim from a clean start and reports back in a line: the decision and payout, or what went wrong. This keeps each claim's work focused and stops each step getting more expensive as the run goes on. Every step on a claim is still recorded on that claim.

4. **The claims manual, looked up the way a handler would.** The manual (`data/claims_manual.md`) covers things the wording does not, such as a third claim within 12 months, losses to wild animals and meals without receipts. For each claim the agent should find and read the sections of the manual and the wording it needs, rather than being handed whole documents, and the claim page should show what it read. Please update `docs/SPEC.md`, where the manual is still "Not for now".

5. **Problems are put right automatically.** A long run will meet timeouts, errors from the model provider and steps that fail. One bad claim must never stop the run or leave a claim stuck in progress. A claim that fails before it is decided goes back in the queue to be tried again, and a claim that fails twice is left for a handler. No claim is ever decided or paid twice. Before it finishes, the agent checks that it has not missed a waiting claim within its cap.

6. **The model.** Our trials found DeepSeek V4.1 Flash (`deepseek/deepseek-v4.1-flash` on OpenRouter, with low reasoning effort) the best balance of accuracy, speed and cost, so it becomes the default. `MODEL_NAME` still overrides it.

7. **Instructions we can read.** The instructions page shows the agent's instructions for running the queue and for working a claim. Write them from the policy wording and the manual, never from our handlers' decisions in `data/evals/`.

## What stays the same

- The rules in `docs/SPEC.md`, including sign-off on payouts over $1,000.
- Our tech stack. Build these pieces into our own agent rather than adding another agent framework.
- Tests never call a model, and the code stays simple, as `docs/CODE_STANDARDS.md` asks.

## What done looks like

- `npm run check` is green, with tests on a stub model for each new behavior: the to-do list stored and shown, the cap on a run, a failed claim that does not stop the run, a failed claim going back in the queue and being tried again, a claim that fails twice left for a handler, and the check for missed claims.
- After reseeding, a run capped at five claims on the default model works five claims on its own. The dashboard shows the to-do list filling in and being ticked off, and each claim's steps, including the sections the agent read. The other claims stay waiting.
- `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` describe the product as it now is.

## Planning

Follow `docs/PROCESS.md`, but write this plan to `docs/PLAN_HARNESS.md` and tick it off there. `docs/PLAN.md` is the pilot's finished plan and stays as it is. For any live run with the real model, reseed first and cap the run at five claims.
