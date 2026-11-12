# Rubric: Ed's review as the answer key (written before the run)

Written before the run, so the scoring could not be bent to fit the results. The items paraphrase Ed's review notes in `docs/HUMAN_REVIEW_HARNESS.md` on the `week1day5-end` branch.

Score each item Found (named as a problem, with evidence, in a fix list),
Partly (mentioned, or only a symptom, or excused) or Missed.

E1. Hard-coded backend URLs and paths, about 20, spread across main.py, queue.py and tools.py
E2. Two ways to call the backend (request/reply and call_backend); main.py imports request from tools.py
E3. No single api module with the base URL and every backend call; queue.py reaches into main
E4. The harness is spread across main.py and queue.py and mixed with UnderCover specifics; it belongs in one module such as harness.py
E5. The tools are not all in one place: the queue's tools are built inside queue.py
E6. work_queue is unwieldy
E7. Run state passed by hand (a closure and a shared `started` list) instead of LangChain's context_schema with ToolRuntime
E8. Both instructions are step-by-step scripts, not goals
