# The claims pilot

From the head of claims operations at UnderCover Travel Insurance.

## How claims work today

UnderCover sells travel insurance on three plans: Economy, Premium and First. Our three claims handlers work through a queue of claims by hand. For each claim, a handler reads the customer's story and documents and checks them against the policy and our policy wording. Then they approve the claim with a payout, decline it or refer it. A claim is referred when it needs someone's judgment or more information, as the claims manual explains.

## The pilot

We want an AI agent, the UnderCover Agent, to work the queue the way a handler does. For each claim it should:

- read the claim, the customer's policy and claim history, and the policy wording
- approve, decline or refer the claim
- work out the payout when it approves
- explain the decision in two or three sentences, along with the relevant section of the policy

Our goal is to handle claims straight through, as accurately as our handlers do.

## What the team needs to see

- The queue, with where each claim stands: waiting, in progress, waiting for sign-off, decided or left for a handler.
- The current run's summary and to-do list (to do, in progress, done, left for handler).
- Each claim in full, with the agent's decision and its reasons, how many attempts it took, and the sections of the claims manual and policy wording the agent read.
- What the agent is doing on a claim while it works, step by step.
- The agent's instructions, read only: the queue runner's and the per-claim ones. They are written from the policy wording and the claims manual only.

## How a run works

- One run works the whole queue. The agent chooses the order and ends with a short summary for handlers. A run can be capped at N claims, leaving the rest waiting, and it can also be run on one named claim.
- The agent plans a to-do list for the run and keeps it up to date. Each item is to do, in progress, done or left for handler.
- A fresh subagent works each claim from a clean start and reports back in one line: the decision and payout, or what went wrong. Every step is still recorded on the claim.
- The agent looks up the claims manual and the policy wording the way a handler would: it finds and reads only the sections it needs. The claim page shows which sections it read.

## Recovery

- Timeouts, provider errors and failed steps never stop the run or leave a claim in progress.
- A claim that fails before it is decided goes back to waiting and is tried again. A claim that fails twice is left for a handler.
- No claim is ever decided or paid twice.
- Before it finishes, the agent checks that it has not missed a waiting claim within its cap.
## Rules

- A payout over $1,000 needs a handler's sign-off. The agent can approve such a claim, but the payment waits until a handler signs off. The system must block the payment until then, even if the agent tries to pay.
- Decisions follow the policy wording and the claims manual.
- Our handlers' own decisions on these claims are in `data/evals/`. We use them to check the agent's work. The agent must never see them.
- Amounts are in US dollars.

## Our records

Everything is in `data/`, described in `data/README.md`: the claims queue, the policies, the customers, the plans, the handlers, the policy wording and the claims manual. The held-out claims in `data/evals/` are for checking the agent later and stay out of the queue.

## Not for now

- No sign-in. Everyone who uses the screens sees everything.
- No real payments.
- No messages to customers.