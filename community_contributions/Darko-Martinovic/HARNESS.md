# Week 1 Day 5: the harness, with capped runs from the dashboard, a choice of model and a model comparison

Darko Martinovic

My build of the harness brief in `docs/HARNESS.md`, built on my own pilot (`PILOT.md`, next to this file) rather than on Ed's `week1day5-start`. The plan I built it from is next to this file as `PLAN_HARNESS.md`. The code is in my fork:

- The harness as delivered: [week1day5-end](https://github.com/Darko-Martinovic/undercover/tree/week1day5-end)
- The model comparison: [bench/results.md](https://github.com/Darko-Martinovic/undercover/blob/week1day5-end/bench/results.md)

![Accuracy by model](https://raw.githubusercontent.com/Darko-Martinovic/undercover/b566c24697e1301c745255b444892635320ea6dd/bench/results.svg)

## How it differs from Ed's `week1day5-end`

| | Ed's build | Mine |
|---|---|---|
| Capped runs | `uv run -m agent --cap 5` | The same, and Run 5 and Run all in the dashboard, with the number of claims in a field |
| Model | `deepseek/deepseek-v4.1-flash` on OpenRouter, or `MODEL_NAME` | Any model in `models.toml`, on OpenRouter, Anthropic or a local Ollama, picked in the dashboard or with `--model`. The running model is shown, never written in code |
| Settings | Defaults in code (`http://127.0.0.1:8000`) | `.env.defaults` (committed), `.env` and `models.toml` with prices; no host, port, URL, model id or price in code, and tests that fail if one appears |
| Watching a run | The latest run's to-do list and summary on the queue | A live run panel: model, claims done of the cap, time taken and time left at the pace so far, model calls, tokens and cost, the to-do list, and the claim being worked with its steps arriving |
| Usage | Not recorded | Each model call's tokens, cost (from `models.toml`) and time, on the run |
| Agent modules | `api.py`, `tools.py`, `harness.py` | The same three, plus `middleware.py` (the step and usage recorders) and `config.py` (the models allowed) |
| Code standards | 1 to 14 | 1 to 22: 15 to 22 are checked by tests, among them functions under 40 lines, modules under 300, ESLint complexity 10, ruff mccabe 8, and one owner for each service's address |
| Pages | Queue, claim, instructions | Queue, claim, Insights (from my pilot) and instructions |
| Accuracy | Not scored | `uv run -m bench`, below |

Both builds took the same decisions on the five longest-waiting claims: CLM-1001 approved and paid $420.00, CLM-1008 and CLM-1011 approved and held for sign-off, CLM-1010 declined and CLM-1018 referred. Ed's took 2 min 9 s on DeepSeek V4.1 Flash; mine took 1 min 34 s and $0.0252 on Claude Haiku 5.5.

## The model comparison

`uv run -m bench` runs each trial in `bench/plan.toml` from a fresh database, through the same harness the dashboard uses, and scores each claim against the handlers' decisions in `data/evals/decisions.json`: the decision, and for an approval the payout within a dollar. Only the scoring module reads `data/evals/`; the agent and the backend never do, and a test checks it. It refuses to start, or go on, when its estimate would pass `BENCH_BUDGET_USD`, keeps its runs in `bench/results.json` so a stopped comparison picks up where it was, and tries again a run the provider refused.

| Model | Claims | Runs | Decision right | Payout right | Undecided | Cost a claim | Time a claim |
|---|---|---|---|---|---|---|---|
| Claude Haiku 5.5 | all 25 | 3 | 84% | 80% (76–84) | 1 | $0.0047 | 16 s |
| Claude Opus 5.5 | the 5 tiny | 3 | 93% (80–100) | 93% (80–100) | 1 | $0.1142 | 21 s |
| Qwen 3.5 4B, local on Ollama | all 25 | 2 | 54% (52–56) | 46% (44–48) | 10 | free | 65 s |

Percentages are the mean of the runs, with their range when they differ. Opus ran only the five tiny claims, to stay within the budget. Qwen 3.5 9B was left out, at three to four minutes a claim on my machine. The whole comparison cost $2.06.

Gemma 4 31B, free on OpenRouter, has no score: every call came back 429, rate-limited upstream, on three tries.

## Takeaways

- **A small hosted model is most of the way there.** Haiku got 21 of 25 decisions right in every run, at half a cent a claim. Opus did better on the tiny claims, at about 24 times the cost, but on five claims one miss is 20 points, so that gap is not yet measured.
- **The misses are referrals.** Haiku's steadiest misses were three claims the handlers referred: it approved two small ones and declined the third, in all three runs. The agent decides where a handler would ask for more, so the referral rules in the instructions are the next thing to work on.
- **A failed claim is a safe claim.** Qwen 3.5 4B left 10 claims undecided across its two runs, at the 30-call limit or with no decision. The harness put each one back in the queue, so none of them paid anything wrong.
- **Free tiers don't make a benchmark.** The free OpenRouter model was refused outright every time. The comparison now tells a refused run apart from a wrong one, and tries it again later instead of scoring it 0%.
- **The guard rails paid for themselves.** The budget check kept the run under $10 (it estimated $5.40 and spent $2.06), and resuming from saved runs meant a crash partway through cost nothing to recover from.
