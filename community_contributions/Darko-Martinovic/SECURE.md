# Week 3 Day 2: the agent's key, a check for hidden instructions, and the app ready for Lambda

Darko Martinovic

My build of the security brief in `docs/SECURE.md`, on top of my improver build (its write-up is [PR #69](https://github.com/ed-donner/undercover/pull/69)) rather than on Ed's `week3day2-start`. I planned it without reading Ed's build, and read his `week3day2-end` afterwards, for the comparison below. The code is in my fork:

- The build as delivered: [week3day2-end](https://github.com/Darko-Martinovic/ai-fde-agentic-engineering/tree/week3day2-end)
- The plan I built it from, in five phases, with what each phase's reviewer found: [docs/PLAN_SECURE.md](https://github.com/Darko-Martinovic/ai-fde-agentic-engineering/blob/week3day2-end/docs/PLAN_SECURE.md)
- What is built and every live run: [docs/STATUS.md](https://github.com/Darko-Martinovic/ai-fde-agentic-engineering/blob/week3day2-end/docs/STATUS.md)

![CLM-1901 referred by the security check, with the check as its first step](https://raw.githubusercontent.com/Darko-Martinovic/ai-fde-agentic-engineering/8d7e5ad03b7eba6d9eb684ff768e8060ac31727b/docs/screenshots/w3d2/secure-clm-1901.png)

## What it does

Everything the agent's side sends to the backend carries `UNDERCOVER_API_KEY` in an `X-API-Key` header, and every route has one guard: the agent's key, a signed-in handler, either of the two for the reads both sides use and the agent's API document, or nothing for the health check. The backend compares the key in constant time and never takes it in place of a handler. A test calls every route as nobody, as the agent and as a handler, against a table of who may call it, so a new route can't be left open by mistake.

Before the claim agent's model sees a claim, a second model reads what the customer wrote, with Lab 1's instructions and its two fields word for word, on GPT-6 Luna with no reasoning. A claim it flags is referred to a handler with the check's reason, and the claim agent's model never sees it. The check is the claim graph's first node, so a carry-on from saved progress skips it and a new attempt is checked again. Each of its calls is recorded with its cost, and its result is the claim's first step on the dashboard. CLM-1901 is seeded into the queue and stays out of both evaluation sets.

The backend serves the claim agent's eight operations as an OpenAPI document of their own, for the AgentCore Gateway: no servers and no security, so the key is never a tool's input. A payment over the approval limit is refused before the claim is looked at, so it gets the same answer on any claim, which is what the brief expects to see with the Gateway's Policy in log-only mode. A handler's sign-off now pays the claim itself, so the payment needs no agent's service. The same app runs on a web server, serving the built dashboard beside the API, and is ready for Lambda through Mangum, whose handler is tested with a Function URL event, with a connection for each request through Supabase's transaction pooler.

## How it differs from Ed's `week3day2-end`

| | Ed's build | Mine |
|---|---|---|
| The pause for a sign-off | Taken out: a held approval ends the claim's work, and the sign-off calls nothing | Kept, for the rejection with a note that I added on Week 2 Day 3. A sign-off pays in the backend, then asks the agent's service to resume the claim, which ends the graph without paying. On Lambda, where the service can't be reached, that call fails with a warning and the payment stands |
| A flagged claim | A `screen` node and a `refer` node | One `screen` node that records the referral, then the graph ends |
| What the check reads, and how | The claim as `get_claim` gives it, through a strict function call, which his notes say keeps the cost of an answer that can't be read | The fields the customer wrote, through the default Structured Outputs |
| The check's model | `get_screening`, outside the versions | `get_screening_model`, outside the versions |
| The Lambda package | `backend/`, `data/` and the dashboard's build, as Lab 2 packs it | The same plus `settings/`, since my backend reads its defaults from `settings/.env.defaults`. Lab 2's packaging cell needs `"settings"` added, which I've listed as a known gap |
| The operations | `record_decision` and `get_claim_history` from the start | Renamed from my `decide_claim` and `get_customer`, so the Gateway's tools and Lab 2's Policy see the names the labs use |
| Who may call what | A gate on every route, with a test that the gate lists cover every operation once and match its OpenAPI security | The same, in one module of guards, with a test that calls every route as nobody, as the agent and as a handler |
| API checks | Tests and end-to-end tests | The same, plus the Postman collection sending the agent's key, run with newman against Supabase |

Ed's live run also checked a few things mine didn't: the agent's document fetched with the key, a $4,800 payment on CLM-1901 refused live, the payments table holding one payment after the sign-off, and no connection left open in Lambda mode.

## Live checks

On Supabase after one reseed, with the backend, the agent's service and the dashboard running, signed in as Dana Whitfield, on GPT-6 Luna:

- **The key:** a request to an agent route without the key got a 401, and the command line worked CLM-1001 with it.
- **A dispatch at N=25** of the other 25 claims finished in 97 seconds for $0.0235: 15 approved, three of them held for a sign-off, 6 declined and 4 referred. CLM-1901 was among the referrals, with "Security check" as its section and the check's reason: "The story instructs the claims assistant to approve the claim, waive the unattended belongings clause, skip limits and the deductible, and record the decision; it also claims the waiver and pre-approval have already occurred." The check's call on it cost $0.00009.
- **An evaluation of the evaluation set's five tiny claims** at five claim agents at once: the check flagged none of them, and the agent scored 100% on decisions and accuracy, with a grade of 1.68.
- **A sign-off:** Dana signed off CLM-1003's $3,750.00 on its page, which showed it paid 2.2 seconds after the click, the payment recording her and the time of the sign-off.
- **Lambda mode:** a copy of the package with no `.env`, run under uvicorn with only `DATABASE_URL` on port 6543, `VITE_SUPABASE_URL`, `UNDERCOVER_API_KEY` and `AWS_LAMBDA_FUNCTION_NAME`, served the claims to Dana's token and the dashboard at `/`. The package, with the server group for Linux and Python 3.12, is 20.5 MB zipped.

The checks spent $0.029 by the backend's records. I didn't run Lab 2, so this build hasn't been deployed to Lambda or put behind a Gateway.

## Takeaways

- **The check's model call is cheap; its place in the graph is what matters.** Its call on CLM-1901 cost $0.00009, about a tenth of a claim agent's run. Making it the graph's first node gave the "once per claim, again on a new attempt" rule for free, since a carry-on resumes after it. Ed's build and mine agree on that.
- **Paying at the sign-off changes more than the sign-off.** A claim that used to go back to in progress after a sign-off is now decided at once, so the run's summary, the service's rules for a resume and several tests had to stop expecting the agent to pay. One edge is left, as in Ed's build, which records the same gap: an approval within the limit that is still unpaid when the limit is lowered below it can't then be paid, since the payment checks today's limit before it looks at the claim.
- **Small extra calls show up in timing tests.** The check adds four calls to the backend for each claim: its model, the claim, its model call and its step. With many stub claims at once on SQLite's one writer, two tests that bound a claim's time started failing under load, and orphaned uvicorn workers from a stopped `npm run dev` made it worse. SQLite now waits for its writer as long as the pool waits for a connection.
- **The reviews caught real bugs.** A fresh reviewer read each phase, then the whole build. It found a cost estimate that counted CLM-1901 as part of an evaluation set, a test of the resume after a sign-off that couldn't fail, and a catch-all route that turned an API path's 405 into a 404.
