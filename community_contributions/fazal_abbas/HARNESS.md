# My UnderCover agent harness (Week 1 Day 5)

My build is on my fork: [FAbbas99/undercover, branch week1day3-FazalAbbas](https://github.com/FAbbas99/undercover/tree/week1day3-FazalAbbas). The plan I worked from is [PLAN_HARNESS.md](PLAN_HARNESS.md) in this folder.

## What I did

I had my coding agent plan the harness from `docs/HARNESS.md`, read the plan and changed a few things, then build it in six phases, one commit each:

1. The claims manual loaded, and both documents served by section, so the agent reads the parts a claim needs instead of whole documents
2. Runs and their to-do list: the cap, the failure counts, and the check that refuses to finish a run with a claim left unworked
3. The claim worker: one agent per claim, from a clean start, under a wall-clock limit
4. The queue runner: it owns the to-do list, chooses the order, hands each claim to a fresh worker and ends with a summary
5. The dashboard: the to-do list on the queue page, a Start run control with a cap, and the sections each claim's agent read
6. End-to-end tests and the docs

The brief asked for the agent to organize its own work, so the pilot's loop over the claims moved out of my code and into the agent. The backend still owns the rules: the cap, the to-do list, the timeout and the rule that a claim is decided once are all enforced there, whatever the model does.

## Ed's review changed my agent

`docs/HUMAN_REVIEW_HARNESS.md` in Ed's build is a review of a harness, and mine had the same four problems:

- more than twenty hard-coded URLs across the agent, with two ways to call the backend
- a module that reached into another one to make its calls
- the harness spread out and mixed up with the claims domain
- instructions written as long step-by-step scripts, which is not agentic

I fixed all four. The agent is now three modules: `api.py`, one place for every backend call with the base URL in it; `tools.py`, every tool, each taking its claim or run from a `ToolRuntime` context, so the model never carries an id around; and `harness.py`, which builds the two agents. Both instruction documents are now a goal with the rules that bind, rather than a numbered workflow.

## How it did

On a run capped at five claims, with DeepSeek V4.1 Flash at low effort, the agent worked all five on its own and ended with a summary for the handlers:

| | |
|---|---|
| Decided and paid | CLM-1001 $420.00, CLM-1002 $580.00, CLM-1004 $186.00, CLM-1005 $243.00 |
| Waiting for sign-off | CLM-1003, approved for $3,750.00 |
| Left waiting | the other 20 claims |
| Cost | $0.0252 |

The steps on CLM-1002 show it reading four sections of the policy wording and six of the manual, and never a whole document, which is what the brief asked for. It also shows the two claims that read the payout rule in the manual, and the ones that did not.

## My takeaways

- **The review file was worth more than any bug I found.** It cost me a restructure, but the agent is now something I would show someone, and the four points in it are all things I would have repeated in the next build.
- **Putting the cap in the backend made the trial cheap and predictable.** Five claims cost two and a half cents, and I knew that before I started the run, because the agent cannot take more claims than the run gave it.
- **Every failure needs somewhere to go.** A claim that fails goes back to waiting with the reason kept as a step, and after two failures it is left for a handler and no run will take it again. Nothing gets stuck and nothing burns calls in a loop.
- **Goal-led instructions work better than steps.** After the review I cut the numbered workflow out of both documents. The agent still worked the list in order and picked the right tools; what it gained was the room to deal with a claim that did not fit the script.
- **Reading a section beats being handed a document.** The claim page shows exactly which sections the agent read, so a handler can check the decision against the same words the agent used. That is the part of this build I would keep first.
