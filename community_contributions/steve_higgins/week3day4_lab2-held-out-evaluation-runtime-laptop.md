## Week 3 Day 4 lab 2 challenge: the held-out evaluation on Runtime and on the laptop

The challenge asks to run the held-out evaluation with the agent on Runtime, run it again on the laptop, and compare time per claim and cost. `community_contributions/steve_higgins/week3day4_lab2_compare_runs.py` prints the comparison from the database (`uv run --env-file .env python community_contributions/steve_higgins/week3day4_lab2_compare_runs.py runtime=16,17 laptop=21,22`); it only reads.

All runs are the held-out set, 25 claims, 25 agents at once, `openai/gpt-6-luna` at medium effort, configuration version 2.

| | Runtime, Lambda limit 10 (runs 16, 17) | Runtime, limit 1000 (run 24) | Laptop (runs 21, 22) |
|---|---|---|---|
| Refusals by the context layer | 158 and 203 | 0 | 0 |
| Model calls | 303 and 299 | 216 | 214 and 214 |
| Wall time per claim | 8.5 to 9.1 s | 5.4 s | 6.7 to 6.9 s |
| Working time per claim | 136 to 141 s | 64 s | 117 to 122 s |
| Cost per claim | $0.0018 to $0.0020 | $0.00195 | $0.0019 |

1. **Cost is the same on both routes**, about $0.0019 a claim ($0.048 for the run). That is the model's cost as the app records it; the AWS bill for Runtime and Lambda is not in it.
2. **The first Runtime runs were slower than the laptop and made about 40% more model calls, because Lambda throttled them.** The Gateway's calls to the context layer's Lambda, and the Gateway's calls to the app, answered 429 (`ConcurrentInvocationLimitExceeded`, or "returned HTTP 429 to the initialize handshake"). The agent passes that on as "Refused by the context layer: ...", and the model asks again, often with a different query. Found by comparing `claim_steps` for CLM-1111: run 16 had 11 refusals and 22 model calls over 205 s; run 21 (laptop) had none and 9 calls over 120 s. Nothing else differed: the agent code is the same package on both routes, the configuration version is the same, and memory is off for evaluation claims (`agent/memory.py` `open_for`). The laptop calls the app and the context layer directly, so it never goes through the Gateway or the limit.
3. **Raising the Lambda "Concurrent executions" quota from 10 to 1000 (Service Quotas, `us-east-1`) removed it.** Run 24 had no refusals and 216 calls, and was about 20% faster than the laptop by wall clock (134 s against about 170 s for the run). It is one Runtime run and two laptop runs, and the laptop reaches the database in `eu-west-1` over home internet, so treat the gap as indicative.
4. **The agent now tries a Gateway call again after a 429** (`agent/gateway.py`, [commit `e399307`](https://github.com/stevehome/undercover/commit/e399307), up to 6 tries with a growing wait). It matches only the three message forms above, so a refusal that merely contains "429" is left to the model. Run 24 was made without it; it takes effect on Runtime after `agentcore deploy`.
5. **The runtime's logs do not show a claim.** The log group `/aws/bedrock-agentcore/runtimes/undercover_default_agent-mhoaRxCQpr-DEFAULT` has one stream per session, and an evaluation is one session: "Async task started: run" and "Async task completed: run" around the whole 25 claims (18:14:51 to 18:16:54 for run 24), with the startup lines (`Created a workload identity`) and nothing per claim. A claim's steps, with timing, are in `claim_steps` and its calls in `model_calls`. Per-claim lines in the logs would need the agent to log each tool call, and a redeploy.
6. **The IAM user `--------` cannot list quota requests** (`servicequotas:ListRequestedServiceQuotaChangeHistoryByQuota` is denied), so the request was made in the console. It could read the value (`aws service-quotas get-service-quota --service-code lambda --quota-code L-B99A9384 --region us-east-1`).
