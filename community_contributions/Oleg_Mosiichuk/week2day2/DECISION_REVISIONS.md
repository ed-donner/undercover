# Week 2 Day 2: investigating blocked decision revisions

Author: Oleg Mosiichuk

While completing the lab, I compared the agent with and without memory. Memory increased accuracy from 0.64 to 0.92, but the cost of mistakes rose from 1064.60 to 3000. That discrepancy prompted me to inspect the errors rather than treating higher accuracy as sufficient evidence of improvement.

In Langfuse, I checked CLM-1304 and CLM-1306. In both traces, the agent initially recorded decline/0, then attempted to correct its decision: approve/300 for CLM-1304 and approve/427.60 for CLM-1306. The tool rejected both corrections with its message template: `A decision is already recorded on {claim_id}, and decisions are final`.

The necessary facts had been retrieved. The recording mechanism nevertheless preserved the initial incorrect declines, so the evaluator received those answers and assigned a penalty of 1500 to each. In these two cases, finding the evidence and reaching a corrected conclusion were insufficient because the tool prevented that conclusion from becoming the scored result.

My implementation makes tool writes revisable drafts within one claim invocation. Each accepted draft is retained in `decision_history`. The tool description and shared agent instructions explain this behavior. After `await agent.ainvoke(...)` succeeds, `decide` returns the latest valid draft to the evaluator. If invocation raises an exception, an intermediate draft is not returned as a completed result. Invocation-local state is reset in `finally`, preventing drafts from carrying into another case or run. Approval still requires a positive payout; existing evaluator fields and table columns remain compatible.

Six regression cases exercise the actual notebook definitions and LangChain tool with a scripted agent, without paid model calls. They check decline/0 to approve/300, the reverse revision with both entries preserved, rejection of approve/0 without replacing the valid draft, isolation across concurrent cases and repeated runs, exception cleanup, and refusal of calls for another claim or outside an invocation. All six passed.

One subsequent memory experiment used the same 25 cases:

| Metric | Before | After |
| --- | ---: | ---: |
| Accuracy | 0.92 | 0.88 |
| Cost of mistakes | 3000 | 150 |
| Found fact | 1.00 | 1.00 |

Both investigated cases finished correctly after the fix. In this rerun, CLM-1306 revised refer/0 to approve/427.60. Three unnecessary referrals remained: CLM-1309, CLM-1319 and CLM-1323, each costing 50. Data, reference answers, penalties and metric formulas were unchanged; reference answers were not used to choose decisions.

These are separate observed runs, not proof of consistent superiority. Accuracy fell while mistake cost decreased. My takeaway is to examine accuracy, the cost of different errors, and the point at which a decision becomes final.

Implementation in my fork: [published commit](https://github.com/omotsart/undercover/commit/c384aa9560eda5853356a8c2af790c6efc493a5b), [notebook](https://github.com/omotsart/undercover/blob/c384aa9560eda5853356a8c2af790c6efc493a5b/labs/week2day2.ipynb), and [regression tests](https://github.com/omotsart/undercover/blob/c384aa9560eda5853356a8c2af790c6efc493a5b/agent/tests/test_lab_decisions.py).
