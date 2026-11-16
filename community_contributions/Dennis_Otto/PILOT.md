# UnderCover pilot: Dennis Otto

My pilot build of UnderCover, following the plan in [PLAN.md](PLAN.md).

**Code:** https://github.com/Dennotto2007/undercover/tree/week1day3-DennisOtto

## What I built

1. Backend records and the read API
2. Decisions, the payment block and sign-off
3. The UnderCover Agent and a worker that runs claims one at a time
4. Dashboard pages, in light and dark modes
5. Run agent, live steps and sign-off in the dashboard
6. A real-model smoke check and the final documents

I changed `docs/BRAND.md` to a blue palette before building. After the plan was done, I added an overview page with claim counts, total payouts and claim types by status.

## Results

All 25 claims in the queue are worked: 16 approved, 5 declined and 4 referred. Payouts total $11,899.00, with $4,759.00 paid and $7,140.00 waiting for a handler's sign-off.

`npm run check` passes: 48 Python tests, 16 dashboard tests and 4 Playwright journeys. I have not scored the decisions against the handlers' answers yet.

## Takeaways

- **Put the rule in the backend, not the prompt.** The $1,000 limit is enforced where the payment happens, so it held in a test where the agent was scripted to try to pay anyway.
- **A second opinion on the plan was worth it.** I had Codex review the plan before any code was written. It caught that the payment checks needed to run in one transaction. I turned down its idea of a guard on each run, because with one worker there was nothing to guard against. You still have to judge the advice.
- **Green tests do not prove the agent works.** Every stub test passed and five real runs finished cleanly. Then in the full queue run, 3 of 25 claims stopped without a decision. Failing safely mattered: nothing was paid, the claims went back to waiting, and all three finished when I ran them again. I do not know the cause yet.
- **Working is not the same as accurate.** The agent gets through the queue, but only the evaluations will show whether its decisions match the handlers'.
