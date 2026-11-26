> Contributed from my own standalone repo: https://github.com/msr-sajid/claims-single-vs-agent
> This is my Week 1 Day 2 take: instead of editing the lab notebook, I rebuilt its experiment (one structured-output call versus an agent with two tools) as a small tested project with its own invented policy and claims. Nothing here uses the course data.

# claims-single-vs-agent

One structured-output LLM call, or an agent with tools in a loop? This repo runs both on the same
small insurance-claims task, scores them against an answer key and compares accuracy, calls and speed.

## Why this exists

When you build with LLMs it is tempting to reach for an agent every time. This is a small experiment
to check that instinct. Each claim is decided two ways:

| | Single call | Agent |
|---|---|---|
| How | One request with the policy wording, policy record and claim. The reply is parsed into a `ClaimDecision` (rationale, decision, payout). | The model gets the claim and two tools, `get_policy` and `record_decision`, and loops until it records a decision. |
| Calls per claim | 1 | 2 or more |

## What I found

I first ran this experiment in a course lab (Ed Donner's "AI FDE" course) on five insurance claims
with OpenRouter's `openrouter/free`, which picks a different free model for each request:

| Approach | Right | Time per claim |
|---|---|---|
| Single structured call | 3 / 5 | 22.8 s |
| Agent with 2 tools | 3 / 5 | 35.4 s |

The agent scored the same and was about 55% slower. The task is a fixed workflow: look up the policy,
apply the rules, decide. Tools in a loop add calls without adding accuracy. Five claims on a rotating
set of free models is a very small sample, so treat it as an observation, not a benchmark.

This repo is my own rebuild of that experiment, with its own fictional policy and claims, so the course
data stays out of it. I have not published results for the demo data yet.

## The demo data (all invented)

`data/` holds a one-page fictional "Wayfarer Mini Policy", five policy records, five claims and an
answer key. The claims test different things: a per-item limit plus a deductible (C-001), a claim the
policy excludes (C-002), a theft with no police report that should be referred (C-003), delay arithmetic
where 9 hours is two full 4-hour blocks (C-004) and a plain medical claim (C-005).

## Layout

| File | Responsibility |
|---|---|
| `src/claims_compare/prompts.py` | The `ClaimDecision` schema and the prompts both approaches share. |
| `src/claims_compare/single.py` | Approach 1: one structured-output call. |
| `src/claims_compare/agent.py` | Approach 2: the tool loop. Bad tool calls become text the model can recover from. |
| `src/claims_compare/scoring.py` | Right means the same decision and a payout within a dollar. |
| `src/claims_compare/cli.py` | `compare-claims`: runs both, prints a table, saves `results/last_run.json`. |

## Run it

You need [uv](https://docs.astral.sh/uv/) and a free [OpenRouter](https://openrouter.ai) key. Free models
need the "free endpoints" switches on at https://openrouter.ai/settings/privacy, and anything you send to
them is not private. Free accounts get 50 free-model requests a day. One full run makes about 15, and the
client retries only once, because retries count against the limit.

```bash
cp .env.example .env     # paste your OPENROUTER_API_KEY
uv sync
uv run compare-claims                         # or --model <an id ending in :free>
```

## Test it

```bash
uv run pytest
uv run ruff check .
```

The tests use a fake client, so they need no key and no network.

## Ideas for next

- Run each specific `:free` model separately and compare, instead of letting `openrouter/free` pick.
- Add cost per claim for paid models.
- Add a "manual" claim that needs information the policy does not contain, to see how each approach fails.

## Credit

The idea comes from a lab in Ed Donner's course "AI FDE: The Forward Deployed Engineer & Agentic AI
Architect". The code, policy and claims here are my own.
