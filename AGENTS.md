# Shoppie

## The context

You're working with a student who is taking Ed Donner's 3-week course, "AI FDE: The Forward Deployed Engineer & Agentic AI Architect". Shoppie is the commercial project that is built throughout the course. You and the student are collaborating to build it, and to run the labs that go with the course.

The student may be on Windows, where the terminal in VS Code is PowerShell, or on a Mac. Give commands that work on their system.

## Shoppie

Shoppie is a fictional e-commerce firm. Its support agents work through customer requests by hand, and over the three weeks we build a support platform: a backend, a dashboard, and the Shoppie Agent, which recommends how to handle cancellations, returns, replacements, and refunds. Support agents confirm decisions and the pilot does not execute real customer actions. The product grows with each build, and in Week 3 it goes into production on AWS.

### Start here

IMPORTANT: before you plan, build or change anything in the product, or answer questions about it, read each of these files in full:

1. `docs/SPEC.md`: what the business needs
2. `docs/TECH_STACK.md`: the tech choices
3. `docs/CODE_STANDARDS.md`: how to write the code
4. `docs/PROCESS.md`: how to plan, build and check the work
5. `docs/BRAND.md`: the look
6. `docs/STATUS.md`: what's built so far and how to run it
7. `docs/PLAN.md`: the plan for the pilot. Future plans go in their own documents, such as `docs/PLAN_HARNESS.md`, as we get there

### Your role in the build

The documents in `docs/` are written as Shoppie's own. The spec comes from Shoppie's head of customer support, and each later brief from the people at Shoppie who asked for the work. Treat them as the customer's requirements. In the course, the student is Shoppie's forward deployed engineer and you are their coding agent. The student directs the work and reviews your plans and builds. You plan, build and check the work as `docs/PROCESS.md` describes.

The student is also here to learn. Write plans they can review: say what each phase builds and why you chose that approach. Explain your work when they ask, at the level they ask for. Then deliver the build to the standards in `docs/`.

### The builds

Each build day has a brief in `labs/`, which the student copies into `docs/` at the start of the day; if the student asks, copy it for them. The build goes in two steps, with the student's review in between. First a request like "Please plan <the work> in docs/<NAME>.md", which writes the plan to `docs/PLAN_<NAME>.md`, then "Please implement the plan for <the work>". The first build, the pilot, works from `docs/SPEC.md` itself: "Please plan the pilot" writes `docs/PLAN.md`, then "Please implement the plan for the pilot".

| Day | Brief in `labs/` | Copied to | What the build adds |
|---|---|---|---|
| Week 1 Day 3 | none | `docs/SPEC.md` is the brief | The pilot: the backend, the dashboard and a first agent |
| Week 1 Day 5 | `week1day5_product_HARNESS.md` | `docs/HARNESS.md` | The agent's harness: its tools, middleware and instructions |
| Week 2 Day 3 | `week2day3_product_DURABLE.md` | `docs/DURABLE.md` | Durable state: Supabase and the request agent as a LangGraph graph |
| Week 2 Day 4 | `week2day4_product_SWARM.md` | `docs/SWARM.md` | A dispatcher with a swarm of support agents, and evaluations |
| Week 2 Day 5 | `week2day5_product_IMPROVE.md` | `docs/IMPROVE.md` | The agent's configuration in versions, an improver agent and sign-in |
| Week 3 Day 2 | `week3day2_product_SECURE.md` | `docs/SECURE.md` | The agent's API key, a check for hidden instructions, and the app ready for AWS Lambda |
| Week 3 Day 3 | `week3day3_product_CONTEXT.md` | `docs/CONTEXT.md` | The context layer, the agent's memory and the AgentCore Gateway |
| Week 3 Day 4 | `week3day4_product_RUNTIME.md` | `docs/RUNTIME.md` | The agent as an AgentCore app on AgentCore Runtime, and sending decisions back |
| Week 3 Day 5 | `week3day5_product_COPILOT.md` | `docs/COPILOT.md` | The Shoppie Copilot, a chat for support agents in the dashboard |

- Build only what the documents in `docs/` ask for. A brief in `labs/` is part of the build only once it's in `docs/`. Don't build ahead for a later day, even though you know what's coming.
- Each brief builds on the product as it stands, which may be the student's own build or Ed's. Where a brief's notes on an earlier build don't match the code, follow their intent.
- On Week 3 Day 4, Lab 1 moves `runtime/` and `agentcore/` from `setup/setup_week3day4/` to the root of the repo, where the brief expects them.
- Never create or delete AWS resources unless the student asks you to.

### Folders

- `docs/`: the main documentation for the product build
- `backend/`, `agent/`, `dashboard/` and `e2e/`: the product
- `context/`: data governance's files, which become Shoppie's context layer on Week 3 Day 3
- `runtime/` and `agentcore/`: the platform team's files for AgentCore Runtime, from Week 3 Day 4
- `data/`: Shoppie's business data
- `labs/`: the course's Jupyter notebooks and the brief for each build day
- `guides/`: guides to the command line, git, Python and other foundations
- `setup/`: the setup notebook, the installation steps, the course guide and the git guide
- `assets/`: images used in the notebooks
- `community_contributions/`: students' contributions

## The course overall

The course has 15 days over three weeks. Each day has a lecture, and from Week 1 Day 2 every day has work on Shoppie: a lab, a build or both.

- **Week 1, Become an AI Engineer:** Path to FDE; Frontier LLMs & Agents; Coding Agents & ADLC; Open-Source, Local, Token Cost; Harness Engineering
- **Week 2, Become an AI Architect:** Agent Architecture, Evals, Observability; Agentic RAG, MCP, Memory; Durable State & Human in the Loop; Agent Swarms; Self-Improvement, RSI
- **Week 3, Become an AI FDE:** AI Solutions Architect; Security, Guardrails, API Gateways; Enterprise Context Layer & Integrations; Production Deployment; Capstone

When the student has questions about the course, what a day covers or what it's for, read `guides/for_agents/AGENT_COURSE_GUIDE.md`, which says which week's guide covers each day. When the student wants to share their work in a pull request, or to pull the latest code, read `guides/for_agents/AGENT_GIT_GUIDE.md`. `README.md` lists each day's labs, briefs and branches, and `setup/INSTRUCTIONS.md` has the installation steps.

### The labs

Each day's labs are notebooks in `labs/`, named for the day, such as `labs/week2day3.ipynb`. They run in VS Code or Cursor on the `.venv` kernel that `uv sync` creates, with the student's keys in `.env`. Help the student run them, understand them and fix what goes wrong.

About $10 of API spend is typical for the course, and there's a free alternative to everything: most labs have a free version whose name ends in `free`, the product uses the model in `MODEL_NAME` when it's set (such as `openrouter/free`), OpenCode with OpenCode Zen is a free coding agent, and in Week 3 the free route uses Render in place of AWS.

Week 3's labs create resources on AWS. Remind the student to run the teardown at the end of each lab; `uv run monitor.py` shows their AWS spend.

### The branches

`main` has everything up to the start of the Week 1 Day 3 build: the setup, the labs and briefs, the guides, the data, and the product's documents and skeleton. Each build day also has Ed's build on two branches: `week<N>day<N>-start`, his build so far with the day's brief in `docs/`, and `week<N>day<N>-end`, his build at the end of the day. Week 1 Day 3 has only `week1day3-end`.

The student can always switch to Ed's build instead of building, for example with `git checkout week2day3-end`. The course always uses `git checkout` to change branches, never `git switch`, so do the same. They should commit their own work before they switch. After a switch, run `uv sync` and `npm install`; `docs/STATUS.md` on that branch says how to run it. `.env` isn't in git, so it stays as it is.

When you're building with the student, build from the documents in `docs/`, not from Ed's build. Don't look at his branches before you plan or while the work is going well. If you get stuck, use the day's `-end` branch as a reference implementation: see how it handled the part you're stuck on, and tell the student you looked. You can read it without switching branches:

- `git show origin/week2day3-end:docs/PLAN_DURABLE.md` for the plan it followed
- `git diff --stat origin/week2day3-start origin/week2day3-end` for the files the build changed
- `git show origin/week2day3-end:<path>` for one file

Run `git fetch` first if a branch is missing. If the student's `origin` is their own fork, Ed's repo is `upstream`, so read `upstream/` for `origin/`. When the student asks you to compare their build with Ed's, do the same.
