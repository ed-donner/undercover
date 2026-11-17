# Week 2 Day 4: a swarm of claim agents and a scoreboard

My build of `docs/SWARM.md`, starting from `week2day4-start`, done with Claude Code in six phases, each reviewed by a fresh subagent before its commit.

Branch: https://github.com/Jerrymomodu/undercover/tree/jerry_momodu-week2day4-swarm-build
Plan: https://github.com/Jerrymomodu/undercover/blob/jerry_momodu-week2day4-swarm-build/docs/PLAN_SWARM.md

## What it adds

- **A dispatcher in place of the queue agent**, `agent/dispatcher.py`, in the lab's style: a LangGraph graph with no model that lists the claims, fans out one `Send` per claim, works them with `max_concurrency` set to N, and finishes the run in a node that runs once after every worker (the lab assignment's `score_run` pattern). It has no checkpointer: each claim keeps its own thread, so a claim that waits days for a sign-off holds up nothing.
- **Problems put right:** a `RetryPolicy` on rate limits and timeouts carries a claim on as the same attempt, an `error_handler` leaves a claim whose waits ran out in progress for the next dispatch, and any other failure is tried once more in the same dispatch.
- **A saver per claim run** on one shared pool of 4 connections, since `PostgresSaver` holds a lock around every read and write.
- **Cost and time for every claim:** each model reply's tokens and `usage.cost`, and the agent's time per run of the claim graph, so a wait for a sign-off is never counted.
- **Evaluations and a scoreboard:** copies of the labeled sets, out of the queue and never signed off, scored by `backend/scoring.py`, the only reader of the answer key, with the lab's measures.

## Takeaways

- Check the framework, not just your code. In LangGraph 1.2.12, a node's `error_handler` ran but its error still stopped the graph whenever several `Send` tasks ran at once. A small experiment showed it, and 1.2.22 fixes it, so the build pins `langgraph>=1.2.22`.
- `max_concurrency` sizes one thread pool shared by a graph's tasks and its checkpoint saves. With a checkpointer and more tasks than threads, finished tasks aren't saved until late in the step. The dispatcher avoids this by saving nothing itself.
- Live runs find the limits the tests can't. At N=25 the run took about as long as its slowest claims, but each claim took nearly four times longer than at N=3, and a sign-off took 13 seconds to pay instead of five. The backend's 4 connections were the queue: at about 180 ms a round trip to Supabase, 18 agents ask for more than 4 connections can serve.
- Fresh reviewers earn their keep. They found a dispatch that never finished when its only claim ran out of waits, a test that couldn't fail, and an endpoint that accepted an evaluation's copies for a dispatch.
