# Bulent Yalazi: the UnderCover pilot

My build of the Week 1 Day 3 pilot is on the `week1day3-bulent` branch of my fork:
https://github.com/bulent70/undercover/tree/week1day3-bulent

## What I did

I planned the pilot from `docs/SPEC.md` with my coding agent, reviewed the plan, then built it in six phases, one commit each:

1. Records and the read API: FastAPI and SQLite, seeded only from named files in `data/`, with a test that no response carries eval fields
2. The workflow and the payment rule: claim states, with payouts over $1,000 refused until a handler signs off
3. The UnderCover Agent: `create_agent` on OpenRouter, with tools that call the backend and every step recorded from the agent's stream
4. The dashboard: queue, claim and instructions pages in the UnderCover brand, light and dark mode
5. Watching the agent and signing off: steps polled while it works, a handler picker and "Sign off and pay", and Playwright tests on their own database
6. `uv run -m agent --queue` and the handover in `docs/STATUS.md`

After the plan, I added each claim's decision and payout to the queue.

Working the whole queue with `openai/gpt-6-luna` gave 15 approve, 6 decline and 4 refer. Three approvals were over $1,000 and waited for sign-off: CLM-1003, CLM-1008 and CLM-1011. The decisions are not yet scored against `data/evals/`.

## Takeaways

- The first live run showed the agent guessing the policy and customer ids before reading the claim. One line in its instructions fixed it.
- A test hung because parallel tool calls shared one test client. A stack dump found the cause faster than guessing.
- Keeping the payment rule in the backend means the agent can try to pay and simply gets a refusal it can read.
- On Windows, Norton sets `SSLKEYLOGFILE`, which makes Python exit with no error. Clearing it fixed pytest and the agent.
