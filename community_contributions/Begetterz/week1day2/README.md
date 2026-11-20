# Week 1 Day 2: three named free claims agents

Begetterz

Compare Nemotron 3.5 Super VL, Dots3-Note Preview and Liquid LFM 2.5 on the
lab's same five sample claims. The instructions, policy wording and two tools
stay fixed. Correct means the handler's decision matches and the payout is
within $1. All three model IDs end in `:free`.

## Status

**Measurements pending: 0 of 15 pairs completed. No winner yet.**
The account reported 2 of 50 free requests remaining on October 29, 2026.
A claim reserves five requests, so no live claim could start. `results.csv`
contains the header only; it contains no synthetic measurements.

Validation: offline notebook checks and the repository's `npm run check` pass.

## Run

Open `free_model_comparison.ipynb` and select the repository's `.venv` kernel.
Run all cells to check the code offline and display saved measurements.
To measure, set `RUN_LIVE = True`; the root `.env` supplies the OpenRouter key.
Return it to `False` and clear all outputs before committing.

The runner validates free pricing and tool support, paces every model call,
caps each claim at five calls and saves after every completed claim. Rerunning
resumes pending pairs. Provider failures pause the experiment rather than
counting as wrong decisions. Expect roughly 45 requests, possibly across days.
See [OpenRouter's limits](https://openrouter.ai/docs/api_reference/limits).

## Interpretation

The notebook reports correctness, average elapsed and active seconds, model
calls and individual misses. Tied accuracy scores share a rank. It declares a
provisional winner only after all 15 measurements exist. Five claims and one
run cannot establish consistent performance on the full queue. The agent has
no claims manual or customer history; labels are used only by the scorer.
