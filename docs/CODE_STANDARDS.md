# Code standards

1. Keep it simple, do not overcomplicate.
2. Comments only when necessary.
3. Be concise: a short README and no emojis.
4. IMPORTANT: avoid overly defensive code. Handle exceptions only when necessary.
5. Use uv: ALWAYS `uv run`, NEVER `python3`.
6. TypeScript: strict mode, never `any`.

7. Money: never use floats for amounts. Use `Decimal` in Python and whole cents in TypeScript, and round to the cent only when a payout is worked out. On the wire an amount is a string of dollars to the cent, such as `"420.00"`; SQLite keeps whole cents. The dashboard converts at `api.ts` and nowhere else.

## Structure

Code that passes the linters can still be unfit for a pull request. These rules are about how the code is organized; reviewers check them, and `agent/tests/test_structure.py` and the ESLint config enforce what a machine can.

8. One module, one job, named for the job. Never `main.py` as a place to put things. A module never imports from another module's entry point, and two modules never share a helper by importing it from a third that is not about that helper.
9. Every outside call has one home. The agent reaches the backend only through `agent/api.py`: the base URL and every path appear there and nowhere else, errors are handled one way, and no other agent module imports `httpx`. The dashboard reaches the backend only through `dashboard/src/api.ts`, which checks every response. The backend reaches the database only through its logic modules (`claims.py`, `runs.py`), never from a route.
10. The agent harness is separate from the business. `agent/harness.py` knows models and how to run an agent, not claims. `agent/tools.py` holds every tool, defined at module level. A tool gets its state from `ToolRuntime[Context]` (LangChain's `context_schema`), never from a closure, a module global or a factory that builds tools per call. Entry points that wire these together (`agent/agents.py`) are short.
11. Instructions state the goal, the resources the agent has, and the rules it must not break. They are not numbered steps: a fixed sequence of steps is code, so write it as code. Point to the policy wording and the claims manual instead of copying their rules into a prompt.
12. Routes are thin. A route validates its input and calls one function in a logic module. Business rules and SQL do not live in routes. Logic modules raise `NotFound` and `Conflict`; one place in `backend/main.py` turns those into 404 and 409. Database access goes through `db.connection()`, which commits, rolls back and closes.
13. No defensive code for states that cannot happen, and no `except` that hides a failure. A timeout is set on the client that can hang (the model, `httpx`), not simulated around it with threads.
14. Say it once. A value, a format or a block of plumbing that appears twice becomes one function (`formatMoney`, `usePolling`, `api._call`). A magic string or number is a named constant in one place.
15. Tests go through public seams: the API, an agent run with a scripted model, a function's arguments. A test that patches another module's private helper is testing the shape of the code, and it will lock a bad shape in.

## Review before you hand work over

Reading your own diff as a pull request reviewer is part of the work, not a courtesy. Before every commit, go through the diff and answer these questions; if any answer is no, fix it first.

- Could I explain each module's job in one sentence, from its name?
- Does anything import something it should not need to know about (an entry point, a private name, a sibling's internals)?
- Is any URL, path, model name or other literal written in more than one place?
- Is any logic or SQL in a route, or any HTTP in a tool?
- Does any prompt read as a recipe of numbered steps?
- Is there a block of code that appears twice?
- Would a stranger reading this for the first time say "ship it"?
