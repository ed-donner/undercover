# Week 1 Day 3: My pilot build

I forked the repo and built the pilot by following the steps in the instructions and the video, just as you did. Everything worked, and the UnderCover Agent processed every claim in the queue except one.

## The one claim that got stuck

CLM-1016 (Robert Haines) stayed on **In progress**. I asked Claude to look into it. Twice, the agent had finished with its decision written in a message instead of recording it with the `decide_claim` tool, so the claim was never actually decided.

The fix was a small change to the agent's instructions in `backend/instructions.md`. They now say a claim is decided only when the agent calls `decide_claim`, so it must always call it before it finishes and must never end with its decision written in a message. Claude also added a test in `backend/tests/test_workflow.py` to check the instructions say this.

I re-ran the claim with:

    uv run -m agent CLM-1016

This time it was processed and **Declined**, and the whole queue was done.

## What I learned

**Building with a coding agent**

- Plan first, then build. The plan in `PLAN.md` splits the pilot into six phases, each with success criteria the agent checks itself, and I reviewed it before any code was written.
- The documents in `docs/` steer the agent. The spec, tech stack, code standards and process tell it what to build and how to check it.

**How an AI agent should be built**

- Business rules belong in code, not in the prompt. The backend blocks any payout over $1,000.00 until a handler signs off, whatever the agent tries.
- The agent works only through tools on the backend's API, and it records every step, so handlers can watch it work and check its reasoning.
- Agents can fail quietly. CLM-1016 didn't crash: the agent just never called `decide_claim`. One clear sentence in its instructions fixed it, with a test to keep it there.

**Git and sharing my work**

- Branches keep work apart. A file on one branch seems to disappear on another, but it isn't lost.
- `origin` is Ed's repo, which I pull from, and `fork` is my copy, which I push to.
- A pull request asks Ed to pull my branch into his repo. Starting the branch from his `main` means it carries only these files, and `git diff --numstat` shows exactly what's in it before I push.
- Commits, pushes and branches can all be undone without losing work.

**Working with Claude**

- Asking for my approval before anything was final, and asking for the steps so I could run the commands myself, helped me learn as I went.

## Thank you

I can't wait to go through the rest of the course. I'm super excited, and thank you for all you do. I have all your courses, and you are my go-to instructor for AI knowledge.
