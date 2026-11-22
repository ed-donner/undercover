## What I found

**The challenge:** using the agent, what is the cheapest model that gets at least 15 of 25 claims right, consistently?

**My answer: GPT-6 Luna at low effort.** It scored 18 and 17, for under a cent a run ($0.0092 and $0.0069).

### How I tested it

Every model went through Part 4's agent, with the same claims, tools, prompt and `is_right` scoring. Each model and effort ran twice, and passed when both runs scored 15 or more. The models were the OpenRouter models from Parts 2 and 3, Sol included, and every local Ollama model that can call tools.

| Model | Effort | Runs | Cost per run | Passes |
|---|---|---|---|---|
| openai/gpt-6-sol | high | 20, 20 | $0.2217, $0.1582 | yes |
| openai/gpt-6-luna | medium | 17, 19 | $0.0120, $0.0096 | yes |
| openai/gpt-6-luna | low | 18, 17 | $0.0092, $0.0069 | yes |
| ollama/qwen3.8:27b | low | 17, 17 | $0 | yes |
| openai/gpt-oss-120b | high | 15, 16 | $0.0253, $0.0346 | yes |
| google/gemini-3.5-flash-lite | low | 15, 15 | $0.0987, $0.0909 | yes, just |
| openai/gpt-oss-120b | medium | 15, 14 | $0.0168, $0.0186 | no |
| openai/gpt-oss-120b | low | 13, 10 | $0.0131, $0.0151 | no |
| ollama/gemma4:e2b | none | 7, 6 (an earlier run) | $0 | no |
| ollama/llama3 | none | not run | n/a | can't call tools |

### Takeaways

- **Luna at low is the cheapest model that passes.** Sol was the most accurate, with 20 both times, but cost more than 20 times as much.
- **A free local model matched the paid ones on accuracy, but not on speed.** Qwen 3.8 27B, run locally through Ollama, scored 17 and 17. But it took minutes a claim where Luna took seconds, and it needs a machine with about 27 GB of GPU memory. For a claims queue, saving a fraction of a cent a claim isn't worth that, so I ruled local out. The case for local would be keeping claims data on our own machines, which this lab doesn't require.
- **Running more than once matters.** gpt-oss-120b at medium scored 16 on one run in an earlier test, then 14 and 14, and 15 then 14 here. One run would have called it a pass.
- **Cheap per token isn't cheap per run.** Through the agent, gpt-oss-120b cost more than Luna at every effort and was less accurate. Gemini Flash Lite was the fastest, but cost about 10 times as much as Luna and only just passed.

### Consensus

I added the consensus section to see whether the wrong answers follow patterns we could make decisions on. It pools every run's misses and asks a judge model, Claude Sonnet, whether the runs that missed a claim went wrong for the same reason. It judged 20 claims for about $0.13.

It had less value than I expected, but it did explain the accuracy ceiling. Most of the shared reasons were missing information: the handler relied on something the models never saw, such as the claims manual or the customer's history. So a better model or a reworded prompt won't win those claims back, which is why every model tops out around 15 to 20 of 25 and a cheap model gets close to the expensive ones. The fix is giving the models that information.

With Claude's help
