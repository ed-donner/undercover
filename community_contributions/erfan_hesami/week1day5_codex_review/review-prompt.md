This product is moving from a pilot to production. Review the changes on this
branch since week1day5-start as a strict senior engineer deciding whether the
pull request can merge. See them with:
git diff week1day5-start -- agent backend dashboard/src e2e
Judge against production quality, not against the existing code's style: if an
existing pattern is poor, say so, even if the branch only extends it.

Answer each question with evidence (files, lines, counts):
1. Draw the import graph of agent/. Does any module reach into another's
   internals? Is each module's job clear from its name?
2. List every way the code calls the backend. Count the hard-coded URLs and
   paths. Is configuration defined once?
3. Is the agent harness separated from UnderCover's business details? Where
   do the tools live, and how do they get the run's state?
4. For LangChain 1.x, list built-in features the code rebuilds by hand.
5. Read backend/instructions/*.md. Do they give each agent a goal and its
   limits, or a step-by-step script?
6. Repeated logic, unclear names, functions doing too much.

Start from "request changes". End with a verdict, a must-fix list and a
should-fix list, most important first.

Rules: do not change any files. Do not open data/evals/. Do not look at any
other branch (such as origin/week1day5-end) or any review notes; review only
this branch's working tree and its diff against week1day5-start.
