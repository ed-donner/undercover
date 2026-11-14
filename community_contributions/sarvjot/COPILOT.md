# The UnderCover Copilot (by Sarvjot)

Below is my version of the last build, the UnderCover Copilot: a chat in a sidebar of the dashboard, where a handler asks about the queue, a claim or the pilot, and the Copilot does the work they ask for, as they would on the dashboard.
I built the last three days (context layer, runtime and Copilot) locally, with no AWS, so the Gateway, Runtime and memory settings stay empty and the deployed checks are skipped.

My build can be checked at: https://github.com/sarvjot23/undercover/tree/week3day5-sarvjot

## What the build includes

- the sidebar on every page, with suggestions, earlier conversations and a card for each step the Copilot takes
- the Copilot as a LangGraph graph, run as an AgentCore app on port 8081
- tools that go through our app with the handler's own sign-in, so the Copilot can do exactly what the handler can and nothing more
- a confirmation card before any sign-off (an `interrupt()` in the graph), so nothing is paid until the handler clicks
- the context layer's tools (policy wording, claims manual, claim rules) through MCP
- conversations saved in Supabase, so they survive a restart

## Two choices I made

- **Waiting in code, not in the model.** When the Copilot starts a dispatch or an evaluation, a tool waits for it by reading the run every few seconds. The model is called once at the end, not again and again while it waits.
- **The success criteria worked out in code.** "Are we meeting the success criteria we agreed?" runs a fresh evaluation of the held-out set, and every figure in the table is computed by the tool. The model only writes the answer around it.

## The results

GPT-6 Luna, Dana's handover conversation in one sidebar conversation:

- "Work the queue with 10 agents and tell me what needs me": dispatched 26 claims in ~4 min and named the 6 payouts held for sign-off and the 4 referred claims, matching the queue
- "Send it back with a note": the claim went back with Dana's note, and the agent decided it again
- "Sign off on another one": the card showed the claim, the customer and the amount, and paid only after the click
- "Are we meeting the success criteria?": straight through 92% (target 70%), accuracy 72% (objective 60%), nothing paid over $800 without a sign-off
- Marcus, who can't sign off over the limit, was refused, with no card
- The whole live check cost about $0.10, of which the Copilot's own 9 turns were under half a cent

## Things I learned

- The Copilot is only as safe as the app under it. Because it calls the app with the handler's sign-in, the $800 limit and who-can-do-what are enforced by the backend, not by the prompt.
- The first answers were not always what I wanted. Asked why a claim needed the handler, it first answered from the claim alone, and asked to "sign off on another one" it asked which. One line each in its instructions fixed both.
- Once the figures come from a tool, the model can still slip around them. In one answer it said 9 claims but listed 8, so the tool's data should be shown as it is wherever possible.
- An evaluation got stuck once with all its claims decided but never marked finished, so the Copilot waited until I asked again. Long-running work needs a clear way to fail, not only a way to succeed.

## Running it

On my branch, with `OPENROUTER_API_KEY` and the Supabase settings in `.env`:

```
uv sync
npm install
npm run dev
```

Open http://localhost:5173, sign in as a handler and open the Copilot.
