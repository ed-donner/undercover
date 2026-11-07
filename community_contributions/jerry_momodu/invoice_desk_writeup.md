# Invoice Desk: the Week 1 Day 5 harness pattern, applied to accounts payable

An accounts payable agent for a fictional wholesaler. It works a queue of supplier invoices against purchase orders and goods received notes, then approves and pays, rejects, or escalates each one to a person. It takes the UnderCover harness idea, "the model decides, the harness enforces", to a new use case and makes it more production-shaped.

Code: https://github.com/Jerrymomodu/undercover/tree/jerry_momodu-invoice-desk/community_contributions/jerry_momodu/invoice_desk

## What's different from the UnderCover harness

- **Code runs the queue, the model only judges.** Fixed stages (checks, route, judge, guard, decide, pay) instead of an LLM queue agent.
- **Checkpointed state.** Each stage saves its result in one transaction, so a crashed worker is resumed, not restarted: the model is never asked twice and nothing is paid twice.
- **Parallel workers on leases.** A worker claims a job with `UPDATE ... RETURNING`; an expired lease frees it; a worker that lost its lease can't save.
- **Escalate on uncertainty.** A guard sends the invoice to a person when the model's confidence is under 0.8 or the total is over the limit, whatever the model said.
- **Rules in the database.** SQLite triggers allow only valid state changes, and pay only approved invoices, for the exact total, to the account on file, never the same vendor invoice twice.
- **Rules first.** Deterministic checks settle 8 of 15 invoices with no model call.
- **Evals.** 15 labelled invoices; a wrong approval counts as a critical error and fails the run.

## Takeaways

- Most of a queue is mechanical. Keeping the model to the one judgement step made the system cheaper and easier to trust.
- The evals paid off on the first run: 14 of 15. The model escalated a clean £11,600 invoice because the policy says invoices over £5,000 need "a reviewer", and it didn't know it was the reviewer. One sentence in the instructions fixed it, and it now passes 15 of 15.
- Putting the money rules in the database means even a buggy agent can't pay twice or to the wrong account.
