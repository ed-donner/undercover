# Undercover - Aditya Sawant

I used Claude Opus 5.5 with extra high efforts to build the undercover agent. 

## My changes
- Edited the BRAND.md and added my own color palettes.
- Edited TECH_STACK.md and added a folder name '/test' that contain unit test case.

## Bug fixes

### Concurrent requests on the same claim

I tested what happens when several requests hit the same claim at once: ten starts, decisions, payments or sign-offs fired together, five clicks on Run the agent, and a model asking for the same write twice in one turn. No claim was ever paid twice, but:

- **Bug:** two runs could both start the same claim. The backend checked that the claim was waiting, then updated it in a separate step, so other requests could pass the same check in between. In 51 of 75 trials more than one run was told it had the claim.
- **Bug:** the losing decisions, payments and sign-offs got a 500 instead of a 409. Only the database's unique keys stopped them from writing twice.
- **Bug:** the agent crashed on a 500, because it expected every error to be JSON. The crashed run then put the claim back in the queue and threw away its decision. This happened in 44 of 45 runs where the model asked for the same write twice at once.
- **Bug:** every click on Run the agent got a 202, even though only one run could start the claim. The others failed in the background, and the handler wasn't told.
- **Fix:** every route that changes a claim now takes SQLite's write lock (`BEGIN IMMEDIATE`) before it checks anything. The check and the write happen as one step, so exactly one request wins and the rest get a 409.
- **Fix:** `run_agent` starts the claim before it replies, so a second click gets a 409 straight away.
- **Fix:** the agent reads an error that isn't JSON as plain text, and a run now starts its claim before anything else. Any failure after that is recorded and the claim goes back to the queue.
- **Tests:** `tests/backend/test_concurrency.py` and three new agent tests. All of them failed before the fix and pass after it.

Known limit, not fixed: about 40 runs at once use up the backend's worker threads, and it stops answering for 30 seconds. The pilot's 25 claims at once work fine.

## My repo (fork)
https://github.com/adi290491/my_undercover/tree/week1day3-aditya