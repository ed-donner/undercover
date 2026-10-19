# AI FDE: The Forward Deployed Engineer & Agentic AI Architect

## UnderCover Agent: the Travel Insurance Platform

![An alien in disguise joins a line of travelers](assets/undercover.jpg)

Welcome to the most substantive commercial project I've ever made on any course! We will work on this project throughout the 3-week journey, culminating in a capstone that is truly enterprise grade.

This is the repo that accompanies the course. UnderCover is a fictional travel insurer. Over the three weeks we build its claims platform and an AI agent that handles claims, and in Week 3 we deploy it all to AWS.

_If you're looking at this in VS Code or Cursor, right-click `README.md` in the Explorer on the left and choose **Open Preview** to see it formatted._

## Key links

- My curriculum of courses on Udemy: [edwarddonner.com/curriculum](https://edwarddonner.com/curriculum)
- The course [resources](https://edwarddonner.com/2026/10/14/ai-fde-the-forward-deployed-engineer-agentic-ai-architect/)
- My digital avatar, which answers common questions about my courses: [edwarddonner.com/avatar](https://edwarddonner.com/avatar)

And in case you haven't heard it from me enough, I'd be delighted if you'd consider connecting or following on [LinkedIn](https://www.linkedin.com/in/eddonner/) or subscribing on [YouTube](https://youtube.com/@edward.donner).

## A note on API costs

While about $10 of API spend would be typical for this course, there are free alternatives for everything. Most labs have a free version whose name ends in `free`, the installation steps include a free coding agent, and in Week 3 the free route uses Render in place of AWS.

## For immediate help

Just ask your coding agent (Cursor, Claude Code, etc.). I've equipped it with full knowledge of the course, the labs and this project, and it can help!

## Sharing your work

I'd love to see what you build! Please share it with a pull request to `community_contributions`. The steps for that, and for pulling the latest code, are in [guides/for_agents/AGENT_GIT_GUIDE.md](guides/for_agents/AGENT_GIT_GUIDE.md), and your coding agent can take you through them.

## The journey

Week 1 Day 1 is in the `setup/` folder and Week 1 Day 2 is in `labs/`. From Week 1 Day 3 onwards we work in the entire repo. The installation steps for each day are in [setup/INSTRUCTIONS.md](setup/INSTRUCTIONS.md), and the [guides](guides/) folder has guides to the command line, git, Python and other foundations if you'd like a refresher.

### Switching to my version

You can follow the whole course on `main` with your own build, without ever switching branches. On each day that we build the product with a coding agent, my version is on two branches:

- `week1day5-start` and so on: my build so far, with the day's product brief in `docs/`
- `week1day5-end` and so on: my build at the end of the day

Switch to one with `git checkout`, for example `git checkout week1day5-end`. If you carry on with your own build instead, copy the day's brief from `labs/` into `docs/` yourself, for example `labs/week1day5_product_HARNESS.md` to `docs/HARNESS.md`.

Commit your own changes before you switch branches. Your `.env` file isn't in git, so it stays as it is when you switch.

### Week 1: Become an AI Engineer

**Day 1: Path to FDE**
- The opening Colab: [Instant gratification](https://colab.research.google.com/drive/1tyDDXRnhdZll3dLpwuo_r3viQL4FzUwo?usp=sharing)
- [setup/setup.ipynb](setup/setup.ipynb): the same notebook on your own computer, with your key in a `.env` file
- [setup/INSTRUCTIONS.md](setup/INSTRUCTIONS.md): installing the tools and cloning this repo

**Day 2: Frontier LLMs & Agents**
- Lab: [labs/week1day2.ipynb](labs/week1day2.ipynb), or [labs/week1day2free.ipynb](labs/week1day2free.ipynb) on free models

**Day 3: Coding Agents & ADLC**
- Installing a coding agent: [setup/INSTRUCTIONS.md](setup/INSTRUCTIONS.md#week-1-day-3)
- Your coding agent builds the pilot on `main` from the documents in [docs/](docs/)
- My build: `git checkout week1day3-end`

**Day 4: Open-Source, Local, Token Cost**
- Lab: [labs/week1day4.ipynb](labs/week1day4.ipynb), or [labs/week1day4free.ipynb](labs/week1day4free.ipynb) on free models, or [labs/week1day4cpu.ipynb](labs/week1day4cpu.ipynb) for a computer without a GPU

**Day 5: Harness Engineering**
- To start from my build: `git checkout week1day5-start`
- Lab 1: [labs/week1day5_lab1.ipynb](labs/week1day5_lab1.ipynb), the Claude Agent SDK
- Lab 2: [labs/week1day5_lab2.ipynb](labs/week1day5_lab2.ipynb), Deep Agents, or [labs/week1day5_lab2free.ipynb](labs/week1day5_lab2free.ipynb) on free models
- Product brief: [labs/week1day5_product_HARNESS.md](labs/week1day5_product_HARNESS.md), copied to `docs/HARNESS.md`
- My build: `git checkout week1day5-end`

### Week 2: Become an AI Architect

**Day 1: Agent Architecture, Evals, Observability**
- Lab: [labs/week2day1.ipynb](labs/week2day1.ipynb), or [labs/week2day1free.ipynb](labs/week2day1free.ipynb) on free models

**Day 2: Agentic RAG, MCP, Memory**
- Lab: [labs/week2day2.ipynb](labs/week2day2.ipynb), or [labs/week2day2free.ipynb](labs/week2day2free.ipynb) on free models

**Day 3: Durable State & Human in the Loop**
- To start from my build: `git checkout week2day3-start`
- Lab: [labs/week2day3.ipynb](labs/week2day3.ipynb), or [labs/week2day3free.ipynb](labs/week2day3free.ipynb) on free models
- Product brief: [labs/week2day3_product_DURABLE.md](labs/week2day3_product_DURABLE.md), copied to `docs/DURABLE.md`
- My build: `git checkout week2day3-end`

**Day 4: Agent Swarms**
- To start from my build: `git checkout week2day4-start`
- Lab: [labs/week2day4.ipynb](labs/week2day4.ipynb), or [labs/week2day4free.ipynb](labs/week2day4free.ipynb) on free models
- Product brief: [labs/week2day4_product_SWARM.md](labs/week2day4_product_SWARM.md), copied to `docs/SWARM.md`
- My build: `git checkout week2day4-end`

**Day 5: Self-Improvement, RSI**
- To start from my build: `git checkout week2day5-start`
- Lab: [labs/week2day5.ipynb](labs/week2day5.ipynb), or [labs/week2day5free.ipynb](labs/week2day5free.ipynb) on free models
- Product brief: [labs/week2day5_product_IMPROVE.md](labs/week2day5_product_IMPROVE.md), copied to `docs/IMPROVE.md`
- My build: `git checkout week2day5-end`

### Week 3: Become an AI FDE

This week UnderCover goes into production on AWS, and the free route uses Render. To see what you're spending on AWS, run `uv run monitor.py`.

**Day 1: AI Solutions Architect**
- Lab: [labs/week3day1.ipynb](labs/week3day1.ipynb), setting up AWS, or [labs/week3day1free.ipynb](labs/week3day1free.ipynb), setting up Render

**Day 2: Security, Guardrails, API Gateways**
- To start from my build: `git checkout week3day2-start`
- Lab 1: [labs/week3day2_lab1.ipynb](labs/week3day2_lab1.ipynb), or [labs/week3day2_lab1free.ipynb](labs/week3day2_lab1free.ipynb) on free models
- Product brief: [labs/week3day2_product_SECURE.md](labs/week3day2_product_SECURE.md), copied to `docs/SECURE.md`
- My build: `git checkout week3day2-end`
- Lab 2: [labs/week3day2_lab2.ipynb](labs/week3day2_lab2.ipynb) on AWS, or [labs/week3day2_lab2free.ipynb](labs/week3day2_lab2free.ipynb) on Render

**Day 3: Enterprise Context Layer & Integrations**
- To start from my build: `git checkout week3day3-start`
- Product brief: [labs/week3day3_product_CONTEXT.md](labs/week3day3_product_CONTEXT.md), copied to `docs/CONTEXT.md`
- My build: `git checkout week3day3-end`
- Lab: [labs/week3day3.ipynb](labs/week3day3.ipynb) on AWS, or [labs/week3day3free.ipynb](labs/week3day3free.ipynb) on your own computer

**Day 4: Production Deployment**
- To start from my build: `git checkout week3day4-start`
- Lab 1: [labs/week3day4_lab1.ipynb](labs/week3day4_lab1.ipynb), AgentCore Runtime
- Product brief: [labs/week3day4_product_RUNTIME.md](labs/week3day4_product_RUNTIME.md), copied to `docs/RUNTIME.md`
- My build: `git checkout week3day4-end`
- Lab 2: [labs/week3day4_lab2.ipynb](labs/week3day4_lab2.ipynb) on AWS, or [labs/week3day4_lab2free.ipynb](labs/week3day4_lab2free.ipynb) on Render

**Day 5: Capstone**
- To start from my build: `git checkout week3day5-start`
- Product brief: [labs/week3day5_product_COPILOT.md](labs/week3day5_product_COPILOT.md), copied to `docs/COPILOT.md`
- My build: `git checkout week3day5-end`
- Lab 1: [labs/week3day5_lab1.ipynb](labs/week3day5_lab1.ipynb) on AWS, or [labs/week3day5_lab1free.ipynb](labs/week3day5_lab1free.ipynb) on Render
- Lab 2: [labs/week3day5_lab2.ipynb](labs/week3day5_lab2.ipynb), the final teardown

## The branches

| Command | What it gets you |
|---|---|
| `git checkout main` | The starting point: setup, labs, guides, data, and the product's documents and skeleton before the Week 1 Day 3 build |
| `git checkout week1day3-end` | The pilot: a FastAPI backend, a dashboard for claims handlers and a first agent |
| `git checkout week1day5-start` | My build so far, with the brief in `docs/HARNESS.md` |
| `git checkout week1day5-end` | The agent's harness: its tools, middleware and instructions, and the claims manual as documents it can search |
| `git checkout week2day3-start` | My build so far, with the brief in `docs/DURABLE.md` |
| `git checkout week2day3-end` | Durable state: Supabase, the claim agent as a LangGraph graph that carries on after a restart, and the payout rules |
| `git checkout week2day4-start` | My build so far, with the brief in `docs/SWARM.md` |
| `git checkout week2day4-end` | The swarm: a dispatcher, started from the dashboard, that works the claims with up to 25 claim agents in parallel |
| `git checkout week2day5-start` | My build so far, with the brief in `docs/IMPROVE.md` |
| `git checkout week2day5-end` | Self-improvement: the agent's configuration in versions, an improver agent whose changes a handler approves, and sign-in for handlers |
| `git checkout week3day2-start` | My build so far, with the brief in `docs/SECURE.md` |
| `git checkout week3day2-end` | Security: an API key for the agent, a check for instructions hidden in claims, and the app ready to run on Lambda |
| `git checkout week3day3-start` | My build so far, with the brief in `docs/CONTEXT.md` |
| `git checkout week3day3-end` | The context layer as its own MCP server, a memory for the agent, and the agent's tools through the Gateway |
| `git checkout week3day4-start` | My build so far, with the brief in `docs/RUNTIME.md` and the `runtime/` and `agentcore/` folders for deploying the agent |
| `git checkout week3day4-end` | The agent as an AgentCore app, and Sign off or Send back for a claim waiting on a handler |
| `git checkout week3day5-start` | My build so far, with the brief in `docs/COPILOT.md` |
| `git checkout week3day5-end` | The finished product, with the UnderCover Copilot, a chat for handlers in the dashboard's sidebar |

## Running the claims pilot

- `npm run dev` starts the backend on port 8000 and the dashboard at http://localhost:5173.
- The agent runs from the dashboard: "Run agent" on a claim, "Run trial" for a run capped at a number of claims, or "Run agent on all waiting claims". From the command line: `uv run -m agent.main CLM-1001` for one claim, `uv run -m agent.main queue --limit 5` for a capped run. It needs `OPENROUTER_API_KEY` in `.env`.
- The queue lives in `backend/undercover.db`, created from `data/` on first start. Delete the file to reset it.
- `npm run check` runs every check, including the end-to-end tests, which use their own ports and a throwaway database.
- `docs/STATUS.md` says what is built.
