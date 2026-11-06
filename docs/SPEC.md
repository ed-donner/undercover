# The claims pilot

From the head of claims operations at UnderCover Travel Insurance.

## How claims work today

UnderCover sells travel insurance on three plans: Economy, Premium and First. Our three claims handlers work through a queue of claims by hand. For each claim, a handler reads the customer's story and documents and checks them against the policy and our policy wording. Then they approve the claim with a payout, decline it or refer it. A claim is referred when it needs someone's judgment or more information, as the claims manual explains.

## The pilot

We want an AI agent, the UnderCover Agent, to work the queue the way a handler does. For each claim it should:

- read the claim and the customer's policy and claim history
- find and read the sections of the policy wording and the claims manual that the claim needs, as a handler would, and show what it read
- approve, decline or refer the claim
- work out the payout when it approves
- explain the decision in two or three sentences, along with the relevant section of the policy

Our goal is to handle claims straight through, as accurately as our handlers do.

The agent organizes its own work. We start it once and it works every waiting claim, in the order it chooses, then finishes with a short summary for the handlers. It plans the run as a to-do list and keeps it up to date, and it hands each claim to a helper that works that one claim from a fresh start and reports back in a line. For trials, a run can be capped at a number of claims, with the rest left waiting, or run on named claims.

## What the team needs to see

- The queue, with where each claim stands: waiting, in progress, waiting for sign-off, decided or left for a handler.
- Each claim in full, with the agent's decision and its reasons.
- The to-do list for the current run, with each item to do, in progress, done or left for a handler, and the run's summary when it finishes.
- What the agent is doing on a claim while it works, step by step, including the sections of the wording and the manual it read.
- The agent's instructions for running the queue and for working a claim, read only.

## Rules

- A payout over $1,000 needs a handler's sign-off. The agent can approve such a claim, but the payment waits until a handler signs off. The system must block the payment until then, even if the agent tries to pay.
- Decisions follow the policy wording, which always comes first, and the claims manual, which covers what the wording leaves open, such as a third claim within 12 months, losses to wild animals and meals without receipts.
- A claim the agent fails on goes back in the queue to be tried again, and a claim it fails on twice is left for a handler. No claim is ever decided or paid twice.
- Our handlers' own decisions on these claims are in `data/evals/`. We use them to check the agent's work. The agent must never see them.
- Amounts are in US dollars.

## Our records

Everything is in `data/`, described in `data/README.md`: the claims queue, the policies, the customers, the plans, the handlers, the policy wording and the claims manual. The held-out claims in `data/evals/` are for checking the agent later and stay out of the queue.

## Not for now

- No sign-in. Everyone who uses the screens sees everything.
- No real payments.
- No messages to customers.