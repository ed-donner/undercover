# Week 2 Day 3: durable state, with a handler who can sign off or reject

Darko Martinovic

My build of the durable-state brief in `docs/DURABLE.md`, on my own harness (`HARNESS.md`, next to this file) rather than on Ed's `week2day3-start`. I read Ed's `week2day3-end` before planning and followed his design where it fit my code. The code is in my fork:

- The build as delivered: [week2day3-end](https://github.com/Darko-Martinovic/ai-fde-undercover/tree/week2day3-end)
- The plan I built it from, in six phases, with what it leaves out: [docs/PLAN_DURABLE.md](https://github.com/Darko-Martinovic/ai-fde-undercover/blob/week2day3-end/docs/PLAN_DURABLE.md)
- What is built and every live run: [docs/STATUS.md](https://github.com/Darko-Martinovic/ai-fde-undercover/blob/week2day3-end/docs/STATUS.md)

![A payout signed off on the dashboard and paid by the agent's service](https://raw.githubusercontent.com/Darko-Martinovic/ai-fde-undercover/c4be977a18ac78c4f77ef4f424df4d9b2b8b1d7c/docs/screenshots/durable-signed-off-paid.png)

## What it does

The records are on Supabase, and the claim agent is a LangGraph graph that saves its progress there after every step. An approval over $1,000 pauses the graph with `interrupt()`. A handler reviews it on the dashboard, the backend records the review, and once that is committed it asks the agent's own service to pick the claim up. A claim stopped partway, by a crash, a restart or Stop, carries on from its last step the next time the agent runs. Each piece of work on a claim is a Langfuse trace in the session named after the claim's thread, so the work before a pause and the payment after it are found together.

My addition to the brief: the handler can reject the payout with a note, as well as sign it off. The note reaches the agent as a message, the agent looks at the claim again and decides again, and that decision always goes back to a handler. A payout rejected twice is referred. It comes from my Week 2 Day 3 challenge, where a note that named the rule fixed wrong payouts and a rejection with no reason made a right payout wrong, so the backend requires the note.

## How it differs from Ed's `week2day3-end`

| | Ed's build | Mine |
|---|---|---|
| A held payout | A handler signs it off and the agent pays | Sign off, or reject with a note (`review_payout`, one operation for both). The backend enforces what happens after a rejection, so the agent can't close the claim alone |
| Repeats | A repeated decision or payment counts as done; a claim has one decision, and the agent makes one tool call at a time (`max_concurrency`) | The same for repeats, but a rejection means a claim can have several decisions, so each claim has a `revision` and a decision or payment moves the claim only from the revision it read: two at the same moment are recorded once, and the one that loses gets a repeat or a refusal |
| Run and Stop | Command line only, with no Stop | Also from the dashboard. Stop leaves the claim in progress with its saved progress, and the next run, or Carry on on a claim's page, carries on every claim left in progress |
| Code | The graph, the checkpointer, the runs and the queue agent in one `harness.py`; the routes in `main.py` | `graph.py`, `checkpoints.py`, `harness.py`, `queue_agent.py` and `service.py`; the backend's rules in `claim_rules.py`, the reviews in `reviews.py`, the SQL in `backend/store/` |
| Tests | 20 unit test files | 45, and Playwright tests where a review reaches a stand-in for the agent's service |

## Live runs

All on Claude Haiku 5.5 with the backend, the agent's service and the dashboard running against Supabase:

- **Five claims.** Run 5 on the dashboard worked the five oldest claims in 1 min 5 s, for $0.0217: CLM-1001 approved and paid $420.00, CLM-1008 ($2,240.00) and CLM-1011 ($1,150.00) held for a sign-off, CLM-1010 declined and CLM-1018 referred, the same decisions as my harness's Run 5 on October 21.
- **A sign-off.** Signing off CLM-1008 showed it paid, with the handler and the time, four seconds later. The agent's service resumed the claim's thread past its pause and paid it with no model call.
- **A rejection.** CLM-1011 rejected with a note about the dress shirts and the deductible: the agent checked the calculation again, recorded the same payout with reasons that answered the note, and the claim went back for a sign-off.
- **A restart.** A queue run killed partway through CLM-1001 was carried on by the next run on the same thread, with one attempt, one decision and no failure. A claim signed off while the agent's service was down stayed in progress and was paid first by the next run.

## Takeaways

- **The backend has to make repeats safe, not the agent.** ToolNode runs a reply's tool calls side by side, so a reply with `decide_claim` twice reaches the backend twice at once, and in my tests that recorded two decisions. The `revision` check fixed it for every caller, including a step that runs again after a restart.
- **ToolNode's error handling needs care.** With `wrap_tool_call` set, ToolNode handed every error back to the model, so a broken backend no longer failed the claim. A `handle_tool_errors` function that turns only the backend's refusals into text and raises anything else, as Ed's build does, kept both.
- **Supabase's free session pooler is small.** It allows 15 clients, and processes killed during testing kept their sessions for about a minute, so the pool filled and requests failed with errors that looked like bugs. Three connections per process, and waiting a minute before reseeding after killing servers, kept it working.
- **A rejection needs the rules in the backend.** Without them, an agent told "this is wrong" could decline the claim or approve less than the limit and close it with nobody looking again.
