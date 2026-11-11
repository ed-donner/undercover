# Parth Shukla's UnderCover pilot

I built the Week 1 claims pilot with a FastAPI/SQLite backend, a LangChain agent on OpenRouter, and a React dashboard. After trying the queue, I extended the pilot to make claim outcomes clearer, let handlers resolve uncertain cases, and recover from stalled agent runs.

## What I added

- **Explicit outcomes:** replaced the ambiguous `decided` status with approved, declined, and waiting for human review. A claim is only shown as approved once its simulated payment is recorded. Approval awaiting payment remains in progress.
- **Human referral and resolution:** the agent can use `refer_human` when evidence is missing or conflicting, policy wording is ambiguous, or it cannot confidently settle the claim. Handlers can approve or deny with a reason and policy reference. The original referral and final reviewer remain visible.
- **One click for the waiting queue:** Run agent processes the current waiting claims automatically, one at a time. The dashboard shows the active claim and queue position, continues after individual errors, and refreshes the queue after each attempt.
- **Queue overview:** six large cards show total, waiting, approved, denied, referred-to-human, and waiting-for-sign-off counts.
- **Automatic recovery:** a backend watchdog checks every five seconds. An undecided, unpaid attempt becomes eligible for a rerun after two minutes, once the active worker has stopped. There are three attempts total: the initial run and two reruns. If the third attempt stalls, the claim goes to human review instead of starting a fourth.

## Safeguards and lessons

Running all waiting claims concurrently caused failures during my trial. Sequential processing keeps the single-process pilot manageable while removing the need to start every claim manually. Backend serialization also prevents recovery from starting a second worker alongside an active one.

Retry timestamps and attempt counts survive a backend restart. Recovery preserves saved decisions and payments, and does not guess the age of older claims with no recorded start time. Model requests time out after 30 seconds, with a 90-second budget checked before model turns; the two-minute recovery window does not forcibly interrupt an active call.

Human review retains the pilot's $1,000 payment-authority rule. An over-limit approval needs an authorized handler's sign-off. Transactions prevent repeated reviews or payments from overwriting completed work. SQLite migrations preserve existing records, and run errors report the saved claim state so a failed final reply does not hide a completed decision.

The last full implementation check passed with 118 Python tests, 53 dashboard tests, and 22 browser tests. Recovery tests use a simulated clock and stub models, without paid model calls.

This is still a local pilot: simulated payments, no sign-in, no distributed scheduler, and no durable model checkpoint. Selecting a handler records attribution rather than proving identity.

## Plan and source

[Full implementation](https://github.com/parthkd4920/undercover/tree/week1day3-parthshukla).

[PLAN.md](PLAN.md) is a copy of my implementation plan, including its history. The final sequential-processing and automatic-recovery sections supersede the earlier concurrent batch design. The source branch's `docs/STATUS.md` and `docs/CHANGELOG.md` describe the delivered workflow and limitations.

The contribution contains this write-up and the plan; the full application belongs in my fork rather than in the course repository's contribution folder.
