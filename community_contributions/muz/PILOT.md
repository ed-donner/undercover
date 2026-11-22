# The UnderCover claims pilot, plus the claims manual

This is my Week 1 Day 3 build for Ed Donner's course, AI FDE: The Forward Deployed Engineer & Agentic AI Architect. I directed Claude Code through the course's process: "Please plan the pilot" wrote a six-phase plan with success criteria, and "Please implement the plan for the pilot" built it phase by phase, with tests and a commit for each phase. Afterwards I scored the agent on the held-out claims and improved its prompt.

My build: https://github.com/muz234/undercover/tree/week1day3-muz

The plan it followed: https://github.com/muz234/undercover/blob/week1day3-muz/docs/PLAN.md

## What I built

```
dashboard (React, :5173) ──/api──▶ backend (FastAPI, :8000) ──▶ SQLite (undercover.db)
                                        ▲                       seeded from data/
UnderCover Agent (LangChain create_agent on OpenRouter)
  HTTP only ────────────────────────────┘
```

- **Backend:** FastAPI and SQLite. Every operation has an `operation_id`, a one-line docstring and no optional inputs, and a test checks this. It owns each claim's status, decision, payment and the agent's steps, and serves the agent's instructions, the policy wording and the claims manual.
- **Agent:** `create_agent` on `openai/gpt-6-luna` at low effort, or the model in `MODEL_NAME`. Its tools call the backend API only: `get_claim`, `get_policy`, `get_plan`, `get_customer`, `get_policy_wording`, `get_claims_manual`, `record_decision` and `pay_claim`. Each tool call is posted to the claim as a step.
- **Dashboard:** React, Vite and TypeScript in strict mode, in UnderCover's brand, light and dark. The queue, each claim in full with a Run agent button, the agent's steps as they happen and a sign-off form, and the agent's instructions, read only. The queue and claim pages refresh every 60 seconds.

## Things worth knowing

- **The $1,000 rule lives in the backend, not the prompt.** The payment is refused until a handler signs off, whatever the agent tries, and signing off pays it. The refusal comes back to the agent as the tool's result.
- **A half-finished run is rolled back.** The first full run on the free tier of my OpenRouter account hit 429 rate limits (20 requests per minute for new accounts). A claim with an approval recorded but no payment stayed in progress forever. A failed run now discards its decision and returns the claim to the queue. The model client retries up to 10 times.
- **A bug the unit tests missed.** SQLite connections were used across threads, which returned a 500 on the customer endpoint in the browser while every test passed. Checking the app in the browser found it.
- **Scoring uses a throwaway backend.** `scoring/score_held_out.py` loads the held-out claims into a temporary database, runs the agent through the real backend on its own port, and reads the answer key only after every run. The backend and the agent never see `data/evals/`, and a test checks the backend never opens it.

## How the agent scored

I scored it on the 25 held-out claims, fully correct meaning the right decision and the right payout:

| Prompt | Fully correct |
|---|---|
| Pilot, wording only | 18/25 |
| Plus a rule that an incomplete required document counts as missing | 21/25 |
| Plus the claims manual | 23/25 |
| Plus a rule to refer a third claim in 12 months | 25/25 |

Caveats: I wrote the last two rules after reading the held-out claims they fix, so 25/25 is a development score and not a clean test. My first version of the third-claim rule was ignored by the model. It worked only after I rewrote it as a step-by-step count with a worked date example. The claims manual is outside the pilot's spec; I added it afterwards because four of the misses needed it.

## Takeaways

- A success criterion you can run (a curl call, a browser check) found two real bugs that passing tests did not.
- A rule for a small model needs to be a procedure with an example, not a sentence.
- Keep the answer key behind a boundary in code, and score through the real system.
