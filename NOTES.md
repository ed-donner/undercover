# Notes

## Week 1 Day 4 lab: flaky OpenRouter provider for DeepSeek V4.1 Flash

Running `deepseek = run("deepseek/deepseek-v4.1-flash", "low", claims, labels)` in `labs/week1day4.ipynb` raised a pydantic `ValidationError` — `EOF while parsing a string` — because one of OpenRouter's providers for that model returned truncated JSON while still reporting `finish_reason: "stop"`.

Checked by reproducing the single-claim call directly (bypassing `.parse()` so the raw response could be inspected): across all 20 claims and several different providers (Together, InferenceNet, Morph, Wafer, CoreWeave, Relace, ModelRun, Cohere, Fireworks), every call came back with valid, complete JSON and `finish_reason: "stop"`. So it's not a systematic problem with the prompt, the schema, or a token limit — it's the same class of issue the lab already documents for GLM 5.3 Flash's `wafer` provider (cell 33), just intermittent and on a different provider this time.

Fix: gave `decide()` (cell `c60b9b2c`) a small retry — up to 2 attempts, retrying on `ValidationError` — since OpenRouter's routing is non-deterministic per call, so a retry likely lands on a working provider. Added `ValidationError` to the pydantic import in cell `bac9c230`.
