# Review of the Agent code after the Harness Implementation

This product is evolving from a pilot towards being a production-ready version, and there are some coding issues and shortcuts that are unacceptable.

This is from reviewing the agent implementation:

1. In the agent implementation, there are more than 20 hard coded URL strings across main.py, queue.py and tools.py. There are 2 ways to call the backend. It's very ugly indeed - this is unfit for a PR. Look at the way main.py imports request from tools in order to make API calls - this is truly terrible. How did this pass a review?
2. The way the code is organized into modules is not OK. queue.py reaches into main. The main module isn't good. There should (obviously) be an api module with all calls to the backend API and with the base URL in one place.
3. The harness is spread out and mixed with UnderCover domain specifics. The agent harness and the tools should be cleanly separated from the business logic and easy to understand. Tools should be in one place. The harness should be in a module like harness.py, not spread across main.py and queue.py. The run_queue function is unweildy. LangChain 1.x has a built-in way to pass state: create_agent(..., context_schema=RunContext), with tools taking a runtime: ToolRuntime[RunContext] argument. With that, all the tools sit together in tools.py.
4. Both instructions are long, step-by-step, prescriptive scripts. This is not a good approach for agentic AI. An agent should have a goal, not a series of fixed workflow steps, otherwise we would just write code instead.

Please follow these steps:

- Confirm that these issues exist, and determine how this was allowed to happen
- Fix the issues
- Investigate whether similar issues exist in the backend and dashboard code. I want clean, idiomatic code, suitable for a PR. The agent implementation does not pass a simple review.
- Retest after fixing.
- Update PROCESS.md and CODE_STANDARDS.md and STATUS.md so that this never repeats, and let me know how you did that.
