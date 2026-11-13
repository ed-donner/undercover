# The claims pilot

From the head of claims operations at UnderCover Travel Insurance.

## How claims work today

UnderCover sells travel insurance on three plans: Economy, Premium and First. Our three claims handlers work through a queue of claims by hand. For each claim, a handler reads the customer's story and documents and checks them against the policy and our policy wording. Then they approve the claim with a payout, decline it or refer it. A claim is referred when it needs someone's judgment or more information, as the claims manual explains.

## The pilot

We want an AI agent, the UnderCover Agent, to work the queue the way a handler does. For each claim it should:

- read the claim, the customer's policy and claim history, and relevant sections of the policy wording and claims manual
- approve, decline or refer the claim
- work out the payout when it approves
- explain the decision in two or three sentences, along with the relevant section of the policy

Our goal is to handle claims straight through, as accurately as our handlers do.

## What the team needs to see

- The queue, with where each claim stands: waiting, in progress, waiting for sign-off or decided.
- Each claim in full, with the agent's decision and its reasons.
- What the agent is doing on a claim while it works, step by step.
- The agent's instructions, read only.
- A queue run's ordered to-do list, with items to do, in progress, done or left for a handler, and its final short summary.
- The exact wording/manual sections read on each claim, including versions and attempt history.

## The harness

Start one agent run for the waiting queue, an explicit cap of distinct claims, or one named claim. The agent chooses the order, maintains its visible plan and delegates each claim to a fresh helper. Retries use the same cap slot; claims outside the run's scope or cap stay untouched.

A pre-decision failure returns the claim to waiting and is retried automatically within the run. After two failed attempts, leave it flagged for a handler, without inventing a coverage decision. Failure counts survive later runs. Failures after a committed decision preserve it and any payment/sign-off. One bad claim must not stop the other claims. Before finishing, check for missed work within the cap.

Only one queue or named run is active at a time, with sequential helpers. Run/task/activity records persist locally, but interrupted runs do not resume automatically after a backend restart.

## Rules

- A payout over $1,000 needs a handler's sign-off. The agent can approve such a claim, but the payment waits until a handler signs off. The system must block the payment until then, even if the agent tries to pay.
- Decisions follow the policy wording and claims manual. The wording is the contract; the manual supplies handling and interpretation rules. Source sections are looked up as needed, not automatically supplied as whole documents.
- Our handlers' own decisions on these claims are in `data/evals/`. We use them to check the agent's work. The agent must never see them.
- Amounts are in US dollars.

## Our records

Everything is in `data/`, described in `data/README.md`: the claims queue, the policies, the customers, the plans, the handlers, the policy wording and the claims manual. The held-out claims in `data/evals/` are for checking the agent later and stay out of the queue.

## Not for now

- No sign-in. Everyone who uses the screens sees everything.
- No real payments.
- No messages to customers.
