# Week 1 Day 4 - fewer tokens, plus the product on Ollama and RunPod

Notebook: [week1day4_fewer_tokens.ipynb](week1day4_fewer_tokens.ipynb). Product changes are on [my fork](https://github.com/bgulbol/undercover/tree/burak-week1day4-local).

## Shorter prompt

The lab's short prompt removes the document text, but some claims depend on it (1016, 1023, 1025). So I cut other things: only my plan's column and this benefit's rows from the Limits table, only the add-ons the policy has, shorter instructions, no `summary`. Then I put the documents back and added three facts computed in code (days to filing, incident before/during/after the trip, items total).

20 claims, 2 runs each:

| Model | Lab prompt | Mine | Input tokens |
|---|---|---|---|
| deepseek-v4.1-flash | 78% | 92% | 1,160 → 1,163 |
| hy4-flash | 68% | 95% | ~1,110 |
| nex-n2.6 | 72% | 95% | ~1,085 |
| inkling-2-small | 78% | 92% | ~1,250 |

(decision and payout both right)

- Without the documents my prompt is 25% shorter with the same accuracy.
- With them, same tokens as the lab, 14-27 points better on every model.
- I didn't expect this one: DeepSeek's output tokens halved (1,568 → 786). With the documents there, it reasons less, so cost per claim fell 35%.

## Local (GTX 1660 Ti laptop, 6 GB)

qwen3.5:4b went from 40% to 60% with my prompt, qwen3.5:2b from 20% to 29%. On the lab prompt the 4B decides worse than "approve everything".

The run slowed from 25 to 3 tokens/s. `ollama ps` said 100% GPU, `nvidia-smi` said 91°C and thermal slowdown. The laptop shut down once. Every answer was saved as it came in, so I lost nothing.

## The product on Ollama and RunPod

I added `MODEL_BASE_URL` to the agent, so the same code runs on OpenRouter, Ollama or vLLM. Two tests, all checks pass.

- Ollama: the agent's prompt is bigger than Ollama's default 4,096 context and Ollama cuts it silently. I raised it to 16k in the Ollama app settings.
- RunPod: A40 48 GB, vLLM, Qwen3.5-9B. Model is 17.6 GB, one request gets 33 tokens/s. That's the A40's memory bandwidth (~700 GB/s ÷ 17.6 GB ≈ 40), not its 48 GB.
- With thinking on, a five-word hello took over a minute. I turned it off on the server with `--default-chat-template-kwargs '{"enable_thinking":false}'` (single quotes, RunPod runs it through a shell).

20 claims, 6 at a time ([script](https://github.com/bgulbol/undercover/blob/burak-week1day4-local/community_contributions/burak_gulbol/run_queue.py)), one run each:

| Qwen3.5-9B | Thinking off | Thinking on |
|---|---|---|
| Decision + payout right | 15/20 | 13/20 |
| Paid when it shouldn't | 2 | 2 |
| Time | 6 min | 11 min |

Thinking didn't help here. CLM-1025 was paid in both runs, but it should be a referral. The $1,000 sign-off stopped two wrong payouts.

RunPod cost $0.54, OpenRouter $0.35.

## What I take away

- The obvious cut was the one that hurt accuracy. You only see it with an eval.
- More context can mean less reasoning, and output tokens are the expensive ones.
- On a laptop, local speed is also about temperature.
- A bigger GPU fits the model, batching makes it fast.
