# The UnderCover pilot (by Sarvjot)

Below is my version of the Undercover Pilot. I decided to let the user start the agent inside the app, while showing its work, and making few visual enhancements, while keeping the core of the app similar.

My build can be checked at: https://github.com/sarvjot23/undercover/tree/week1day3-sarvjot

![The live view, mid-run](https://github.com/sarvjot23/undercover/raw/week1day3-sarvjot/docs/screenshots/live-view.png)

## What the build includes

- the dashboard
  - the queue
  - option to check the exact steps which agent is performing
  - agent's final decision
  - the instructions
- the UnderCover agent (LangChain agent with access to 4 tools)
- the backend (with FastAPI and SQLite)
- the checks with tests

## What I added: the live view

I thought it might be interesting to have a sneak peek on how the agent is working. So I came up with the idea of adding Live View in the app, with a refined frontend.
Below are the details:

- In full screen, you can check one claim at a time, including:
  - claim's details
  - agent's steps
  - animated stamp (Approved, Declined, Referred, Waiting for sign-off)
  - Payout counting up
  - Number of claims done / Number of claims remaining
  - Next claim
- Summary at the end

![The summary at the end of a run](https://github.com/sarvjot23/undercover/raw/week1day3-sarvjot/docs/screenshots/live-summary.png)

## How I worked with the coding agent

Claude Code on Opus 5.5, with a commit after each phase:

- Before the build: I changed the brand to a gold palette, and changed sign-off limit from $1,000 to $800
- Planning with agent: ~5 min
- Core build (backend, agent, dashboard): ~37 min (in comparison to Ed's 32 mins)
- Live view: ~30 min, plus ~8 min (end-to-end tests)
- Automated + Manual Testing:
  - unit and component tests for the live view's logic and animations
  - Playwright tests following claims through to the summary
  - a real run of all 25 claims, watched live in the browser
- A bug I found: leaving and reopening the live view showed "1 of 21" instead of "6 of 25"
  - fixed by taking the counts from backend, with 3 new tests: ~16 min

## The results

GPT-6 Luna at low effort, working all 25 claims in the queue:

- A full run: ~6.5 min for about 1 cent
- My latest run: 12 approved, 5 declined, 3 referred, 5 waiting for sign-off
  - $2,889 approved and paid, $8,895 waiting for sign-off
- Same totals as Ed's run (17 approvals, 5 declines, 3 referrals), but with the $800 limit, 5 approvals wait for sign-off instead of 3

## Things I learned:

- How fast we can get things done in 2026, with coding agents, with majority of it working.
- Reviewing the plan before any code was written can it easy to change things, like adding the live view.
- The $800 limit is enforced by the backend (not the prompt), so the agent can't pay over it even if it tries.
- The strict checks ran before every commit, so every phase was ensured to be working, before moving to next steps.

## Running it

On my branch, with `OPENROUTER_API_KEY` in `.env`:

```
uv sync
npm install
npm run dev
```

Open http://localhost:5173 and click "Run the queue".
