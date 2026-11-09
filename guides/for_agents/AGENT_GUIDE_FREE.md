# The free route

How the course works for a student who spends nothing, so you can support them: the free version of each lab in Weeks 1 and 2, and the Render route that replaces AWS in Week 3. Read `guides/for_agents/AGENT_COURSE_GUIDE.md` first, for what runs through the whole course.

Ed's rule is that no money needs to be spent to take the course. A typical student spends about $10 on OpenRouter credit, and there's a free alternative for every day.

## The free route in general

- **The model:** `openrouter/free`, which needs no credit. OpenRouter allows 20 requests a minute on free models, and 50 a day on an account that has never bought credit, or 1,000 a day once it has bought $10. An account with a negative balance gets a 402 error, even on free models.
- **Results vary:** `openrouter/free` picks a different free model for nearly every request, so a student's results won't match Ed's, and a model can go off track. Running the cell again is usually the answer. A comparison between runs needs one named free model, with an ID ending in `:free`.
- **Privacy:** free endpoints may train on prompts. Everything in the course is fictional data, and the two switches at openrouter.ai/settings/privacy are part of Week 1 Day 1's setup.
- **The free notebooks:** each lab that calls a model has a twin with `free` in its name, in `labs/`. Each one says at the top how many requests it makes, and most default to `TINY = True`. A student short of requests can make a run smaller still, or carry on the next day.
- **The product on free models:** `MODEL_NAME=openrouter/free` in `.env` overrides the model everywhere in the product. From Week 2 Day 5, set it before `npm run seed`, since the seed stores the model in the configuration.
- **Free services:** OpenCode Zen for the coding agent, Langfuse Cloud's Hobby plan and Supabase's free plan (neither needs a card), and Render's free web services in Week 3.
- **Watch-only parts:** Runpod on Week 1 Day 4, the Claude Agent SDK on Week 1 Day 5 (Lab 1), and the AWS labs in Week 3. Local models with Ollama (Week 1 Day 4) are an option, but small local models struggle with the claims.

## Weeks 1 and 2

| Day | Free route |
|---|---|
| W1D1 | `setup/setup.ipynb` already uses `openrouter/free`. |
| W1D2 | `week1day2free`, about 30 requests. |
| W1D3 | The build with OpenCode and OpenCode Zen's free models. GitHub Copilot and Cursor have free tiers too. |
| W1D4 | `week1day4free`, about 22 requests, plus three local models with Ollama. `week1day4cpu` has local models small enough for a computer without a GPU. |
| W1D5 | Lab 1 is watch-only. `week1day5_lab2free` runs Deep Agents on the free dots.3 Note Preview over three claims in `labs/lab2free_desk`, about 35 requests, so once a day. |
| W2D1 | `week2day1free`, about 30 requests, with a free Langfuse account. |
| W2D2 | `week2day2free`, about 40 requests. |
| W2D3 | `week2day3free`, about 15 requests, with a free Supabase project. |
| W2D4 | `week2day4free`, about 35 requests: 5 claims with 3 claim agents at once, 10 to 15 minutes. |
| W2D5 | `week2day5free`, about 40 requests with one claim from each set, or about 25 if the student stops after round 1. Jev is skipped on free models. |

- **The builds:** free coding models need one small change at a time, with `npm run check` and a commit after each, and a second or third try. The product works on free models with `MODEL_NAME` set.
- **Too many requests for a day:** a full evaluation, a swarm of 25 or an improvement round on the dashboard needs more than 50 requests. On the free route the student builds and tests these features but runs them small, or watches Ed's runs.

## Week 3: the Render route

The free route for Week 3 is a written guide for each day, in markdown notebooks in `labs/`: `week3day1free`, `week3day2_lab2free`, `week3day3free`, `week3day4_lab2free` and `week3day5_lab1free`. Week 3 Day 2's Lab 1 has a free twin that runs code, `week3day2_lab1free`, about 25 requests. Instead of Lambda and AgentCore, the product runs as free web services on Render, with the same Supabase database as the laptop. There's no Gateway, Policy, Memory or Runtime on this route, and the student watches those parts in the main labs.

### What runs where

| Day | On Render | On the laptop |
|---|---|---|
| W3D1 | A Render account | |
| W3D2 | The app (backend and dashboard) | The agent |
| W3D3 | The app | The agent and the context layer |
| W3D4 | The app and the agent | The first run of a claim |
| W3D5 | The app, the agent and the Copilot | The first run of two claims |

### The three services

Each one is a Python 3 web service in the same region as the student's Supabase project (Virginia for us-east-1), on the $0 / month Free instance.

- **The app** (W3D2), named `undercover`:
  - **Build:** `uv sync --frozen --only-group server && npm ci --ignore-scripts && npm run build`.
  - **Start:** `uv run --no-sync uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
  - **Health check path:** `/api/health`.
  - **Variables:** `DATABASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`, `UNDERCOVER_API_KEY` and, for free models, `MODEL_NAME`. Then `UNDERCOVER_AGENT` from W3D4 and `UNDERCOVER_COPILOT` from W3D5.
- **The agent** (W3D4), named `undercover-agent`:
  - **Build:** `uv sync --frozen --only-group runtime --only-group context`.
  - **Start:** `uv run --no-sync python -m context & uv run --no-sync uvicorn agent.entrypoint:app --host 0.0.0.0 --port $PORT`. The context layer runs inside the service at `http://127.0.0.1:8006/mcp`.
  - **Health check path:** `/ping`.
  - **Variables:** `OPENROUTER_API_KEY`, `UNDERCOVER_API_KEY` (the same key as the app's), `DATABASE_URL` and `UNDERCOVER_API`, the app's address on Render.
- **The Copilot** (W3D5), named `undercover-copilot`:
  - **Build:** the same as the agent's.
  - **Start:** the agent's, with the Copilot's app in place of `agent.entrypoint:app`. In Ed's build that's `agent.copilot.entrypoint:app`; in the student's own build, the `dev:copilot` script in `package.json` names it.
  - **Health check path:** `/ping`.
  - **Variables:** `OPENROUTER_API_KEY`, `DATABASE_URL` and `UNDERCOVER_API`, without the agent's key. The handler's sign-in protects it, and its memory is off.

`MODEL_NAME` goes on the app only, because the app names the model for everything in the product.

### Render's screens

Render's screens change, so the guides link to Render's documentation. As of October 2026:

- **Ed's build or the student's own:** Ed's build deploys from `https://github.com/ed-donner/undercover` through **Public Git Repository**, choosing the day's end branch. The student's own build goes in a private repository of their own, connected through **Git Provider**.
- **Creating a service:**
  - Choose **New**, then **Web Service**.
  - The form runs Name, Project (optional), Language, Branch, Region, Root Directory, Build Command, Start Command, Compute and Environment Variables, then **Advanced** with the Health Check Path.
  - The Build Command box may arrive filled in, so replace it.
  - **Compute starts at $7 / month**, so the student must choose **$0 / month**.
  - The button is **Deploy web service**.
- **Names:** if the name is taken, Render adds a suffix, such as `undercover-1hgy`, and the service's address follows it. Wherever a guide says `https://undercover.onrender.com`, the student uses their own address.
- **Branches:** the branch list shows only the first 15 branches, so `week3day4-start`, `week3day5-start` and `week3day5-end` appear only when the student types the name. On a service's **Settings** page, changing the **Branch** and choosing **Save changes** deploys the new branch straight away.
- **Variables:**
  - **Add from .env** takes several pasted lines at once.
  - On an existing service, the **Environment** page needs **Edit**, then **Add variable**.
  - Its button is **Save, rebuild, and deploy**, with **Save and deploy** under its arrow.
  - The two `VITE_SUPABASE` lines are read when the dashboard is built, so changing them needs the rebuild.
- **Where to look:**
  - Each service has **Events** (each deploy and what started it), **Deploys** (with build logs) and **Logs** (the running service).
  - **Manual Deploy** offers Deploy latest commit and **Restart service**.
  - **Delete or suspend** is at the bottom of **Settings**.

### Free instances

- **Spinning down:** a free service stops after 15 minutes without a request, and Render's health checks don't keep it up. The next request wakes it. In testing the app took about 35 seconds and the agent about 60, while Render showed a "waking up" page.
- **The app waits only 10 seconds for the agent or the Copilot.** Before any work, the student opens `https://<their-agent>.onrender.com/ping` (and the Copilot's on Day 5) and waits for `"status": "Healthy"`.
- **Limits:**
  - 750 free instance hours a month, shared across the workspace. Services that spin down use far fewer.
  - No disk that survives a restart, which is fine because the data is in Supabase.
  - No shell.
  - 512 MB of memory, which is enough for each service.
- **Supabase's free plan allows 15 database connections at once,** so the guides stop `npm run dev` on the laptop before the work moves to Render.
- **Cost:** the services are free and there's nothing to tear down. The student deletes them when they've finished with them.

### Day by day

- **W3D1:** a Render account, then GitHub under **Git Deployment Credentials** in Account Settings, for the student's own builds. Signing in with GitHub and letting Render deploy from GitHub are separate permissions. Step 3 explains the free tier.
- **W3D2:**
  - **On Ed's branch:** `.env` has no `UNDERCOVER_API_KEY` until the student adds one, since the build is what adds it. It goes in before `npm run dev` and before it's copied to Render; the Week 3 guide has the command that prints one.
  - **After the deploy:** the app is live in a minute or two. `/api/health` answers `{"status":"ok"}`, and `/api/claims/CLM-1901` gives a 401, because a browser doesn't send the agent's key.
  - **Sign-in:** Dana signs in on the deployed dashboard and sees the same queue as on the laptop.
  - **Dispatches** say the agent's service isn't running, which is expected until Day 4. A sign-off works and pays.
  - **The checks:** they live in the app itself (the key, the sign-in and the $1,000 limit), where the AWS route adds the Gateway's Policy.
- **W3D3:**
  - **On Render:** only the app moves to `week3day3-end`. The context layer runs on the laptop beside the agent, which calls it directly when there's no Gateway in `.env`.
  - **The claims:** after `npm run seed` and `npm run dev`, `uv run -m agent CLM-1005` and `uv run -m agent CLM-1006`. On the Render app, each claim's page shows the lookups with their file and owner, the Context used panel and the decision record.
  - **No memory step on CLM-1006,** since there's no Memory on this route.
  - **Timing:** in testing on free models, Ed's build approved CLM-1005 at $243 and CLM-1006 at $425, as in his recording, in about 80 seconds each.
- **W3D4:**
  - **The two services:** the app moves to `week3day4-end`, and the agent becomes a second service. The app gets `UNDERCOVER_AGENT`.
  - **The first run, on the laptop:** after `npm run seed` and `npm run dev`, `uv run -m agent CLM-1011` approves and prints a line like `CLM-1011  approve  $1,110.00, waiting for sign-off`. The claim graph's place is saved in Supabase. Then the student stops `npm run dev`.
  - **The send back:** on the Render app, Dana sends the claim back with a note. The agent on Render logs "Async task started: resume", loads the thread from Supabase and decides again. In testing that took 20 to 60 seconds. The claim's page then shows the new decision, with the old one under **Decisions sent back**.
  - **Langfuse in the logs:** the agent's logs show an "Authentication error" from Langfuse saying its client is disabled. That's expected, since the service has no Langfuse keys.
- **W3D5:**
  - **The services:** both move to `week3day5-end`, the Copilot becomes a third service, and the app gets `UNDERCOVER_COPILOT`.
  - **Checking the Copilot's app:** before creating the service, the guide checks the Copilot's `module:name` with `uv run --isolated --only-group runtime --only-group context uvicorn <copilot-app> --port 8090`, which installs only what Render will. A missing package shows up here.
  - **The first runs, on the laptop:** after `npm run seed` and `npm run dev`, the student works CLM-1003 and CLM-1011, which wait for sign-off, then stops `npm run dev`.
  - **The handover, in one conversation as Dana:** "What needs me?", "Why does CLM-1011 need me?", a send back with a note, then "Sign off on another one", which brings up a confirmation card before **Sign off and pay**.
  - **The restart:** **Restart service** on the Copilot's **Manual Deploy** menu takes about 30 seconds, and the old instance answers until the new one is ready. The student reloads the dashboard, opens the conversation from **Earlier conversations** (the history icon at the top of the sidebar) and asks a follow-up.
  - **The fifth question:** the main lab's "Are we meeting the success criteria we agreed?" runs a held-out evaluation, which needs more than the free allowance.

### Free models in Week 3

- **Decisions vary from run to run.** In testing, CLM-1011 came out at $1,110 on one run, with the $350 from Meridian Air and the deductible taken off and a pair or set limited to $300 as one item. On another run it came out at $1,500, missing the pair-or-set rule. Either way the send back works. The note says whatever looks wrong, and if the decision looks right, the student sends it back anyway with a note asking the agent to check something.
- **Claims can take a while.** In testing a claim took from 40 seconds to 6 minutes, once because one free model wrote 16,000 tokens in a single reply.
- **The Copilot's actions are reliable, but its explanations on free models can be shaky.** In testing it said payouts over the limit were "below the approval limit". It sometimes looks up only the claim and the settings, without the agent's steps or the context layer. A follow-up after the restart answers from the conversation, so it can be out of date about a claim worked since.
- **Requests:**
  - Each claim the agent works takes about 10 to 15 requests.
  - In testing, W3D4's first run took 11 and the send back 3.
  - On W3D5, each Copilot turn takes one to four.
  - A dispatch, evaluation or round from the deployed dashboard needs far more than 50 a day. A student who has bought $10 of credit gets 1,000 a day on free models.

### Common problems

- **A deploy fails:**
  - Read the build log on the service's **Deploys** page.
  - The usual causes are a Build Command that wasn't replaced and a missing variable.
  - If the service starts and then fails on a missing module, the package isn't in the dependency group the build installs: `server` for the app, `runtime` and `context` for the agent and the Copilot.
- **The deployed dashboard says the agent's service isn't running:**
  - Check `UNDERCOVER_AGENT` on the app: it starts with `https://` and has no slash at the end, since the app adds `/invocations` to it. `UNDERCOVER_COPILOT` is the same.
  - The agent may be asleep: open its `/ping`, wait, and try again.
- **A 401 between the app and the agent** means the two services have different values for `UNDERCOVER_API_KEY`.
- **Only Dana can sign off over $1,000,** from Week 2 Day 5's build. Marcus and Priya can't.
- **The database and the branch disagree:**
  - Each day's seed builds that day's tables, so after switching branches the student runs `npm run seed` on the laptop, with `MODEL_NAME` set for free models.
  - Going back to an earlier day's branch on a database seeded by a later one can fail. The earlier seed can't drop tables that later days' tables depend on, so it rolls back and changes nothing. The earlier app can also fail to show steps it doesn't know.
  - The fix, with the student's agreement, is `drop schema undercover cascade;` in Supabase's SQL Editor, then `npm run seed` on the branch. It deletes UnderCover's tables and data, and leaves the handlers' sign-ins alone.
- **The student's own build deploys twice:** a service connected through Git Provider may deploy by itself on each push, depending on its Auto-Deploy setting. If it did, the guides' **Manual Deploy** step isn't needed.
