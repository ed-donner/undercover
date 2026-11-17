# Week 2 Day 4: Agent Swarms, with the assignment

My version of `labs/week2day4.ipynb`. Parts 1 to 4 are the lab as it is, with paths changed for this folder. The assignment comes after Part 4.

- **Challenge:** a `score_run` node after `work_claim` scores the whole run and puts the scores in the state. It runs once, after the last claim agent, because all the claim agents run in the same LangGraph step. It's tried with the stand-in, the flaky stand-in and the real swarm.
- **Stretch challenge:** the dispatcher, compiled with `PostgresSaver`, runs in its own process from `durable_dispatcher.py`. The notebook kills that process partway through the run and resumes the thread from a new process with `invoke(None, config)`.

## What the stretch found

LangGraph works again only the claims with no saved result. Whether a finished claim's result is saved depends on how the swarm is capped:

- With `max_concurrency=5` as the only cap, LangGraph runs the claim agents and the saves of their results on one 5-thread pool. The saves wait in the queue behind the claims still to run, so a kill partway through loses every finished claim, and the whole batch is worked again.
- With a pool larger than the batch (`max_concurrency=30`) and a semaphore in the node that lets 5 claims work at once, each result is saved as its claim finishes. Only the unfinished claims are worked again, plus any whose save hadn't reached Supabase before the kill.

A claim can therefore be worked twice. Keeping decisions final has to happen in the backend, not in the agent's memory.

## Running it

Open `week2day4_assignment.ipynb` in VS Code or Cursor on the `.venv` kernel. It needs `OPENROUTER_API_KEY`, the Langfuse keys and Day 3's `DATABASE_URL` in `.env`. The stretch uses a stand-in and calls no model.
