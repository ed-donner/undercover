# Week 1 Day 3: my pilot

Burak Gülbol

## What I did

I asked Claude Code to plan the pilot from the spec, read through the plan and then let it build all six phases without changing anything. After that I reseeded the queue, ran the agent on all 25 claims and watched the decisions come in on the dashboard. The plan is in [PLAN.md](PLAN.md).

## What I noticed

The rules held. The two big approvals I checked, CLM-1003 ($3,750) and CLM-1008 ($2,240), are waiting for sign-off and weren't paid.

The decisions are a different story. CLM-1004 was approved at $74 instead of $186, the same mistake I kept seeing on Day 2.

The agent can now see the customer's claim history, but CLM-1019 was still approved. It's the customer's third claim in 12 months, and the rule that sends that to review is in the claims manual, which the agent doesn't get. So having the data wasn't enough when the rule lives somewhere else.

One thing got better: CLM-1021 came out at the right $825. On Day 2 it was $1,053 every time.

## What I'd change

I'd work out the payout in code and give the agent the parts of the claims manual it needs. And I'd spend more time on the plan before saying go. Watching it build was great, but I wasn't always sure what I was supposed to be checking.

## Repo

https://github.com/bgulbol/undercover/tree/week1day3-burak
