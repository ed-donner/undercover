# Week 2 Day 1 - the concise wording, and what a mistake costs

Notebook: [week2day1_wording_tradeoff.ipynb](week2day1_wording_tradeoff.ipynb). Every experiment uses the payout tool, runs 3 times on the 25 harder claims, and is a dataset run in Langfuse.

## The lab first

With `N_TIMES = 3`, the baseline got 40 of 75 wrong and the payout tool 10 of 75 (Ed had 36 and 8). The payout tool almost doubled the LLM cost, from 0.005 to 0.009 dollars a run, and cut the cost of mistakes from about 9,850 to 2,730 dollars a run.

## The concise wording

The handlers' note on CLM-1214 says the concise wording leaves out a rule: a delay on the way home keeps the cover going past the return date. I expected a wrongful decline there. I was wrong: every wording got CLM-1214 right in all 9 runs.

The claim the concise wording really broke was CLM-1216: right 3 of 3 with the full wording, 0 of 3 with the concise one. It paid 2,005.90 where the handler paid 1,677.90, every time. The full wording says "a pair or a set, **such as a pair of shoes, a suit or a camera with its lens**, counts as one item". The concise one keeps the rule and drops the examples, so the model counted the camera and the lens as two items. I put the examples back, eleven words, and it was right 3 of 3.

| GPT-6 Luna, payout tool | Full | Concise | Concise + examples |
|---|---|---|---|
| Decision and payout right | 88.0% | 86.7% | **92.0%** |
| Cost of mistakes a run | 2,556 | 2,398 | **1,052** |
| Input tokens a claim | 9,659 | 7,647 | 8,074 |
| Seconds a claim | 4.5 | 4.5 | 4.4 |

So yes, the concise wording keeps the accuracy and uses fewer tokens, but it isn't faster. With the examples back it did better than the full wording. Three runs is not many, and runs moved between 19 and 24 right, so the 1216 fix is the solid part. The rest may be partly noise.

## Changing WRONGFUL_DECLINE

I scored the same answers again without calling the model, and added the scores to each run in Langfuse (`cost_of_mistakes_wd500` and so on).

| Cost of mistakes a run, at a wrongful decline of | 500 | 1,500 | 3,000 | 5,000 |
|---|---|---|---|---|
| Full | 890 | 2,556 | 5,056 | 8,390 |
| Concise | 1,065 | 2,398 | 4,398 | 7,065 |
| Concise + examples | **385** | **1,052** | **2,052** | 3,385 |
| DeepSeek V4.1 Flash, concise + rule | 1,884 | 1,884 | **1,884** | **1,884** |

Between full and concise, the answer flips: full is cheaper at 500, concise from 1,500 up. Once the examples are back, the wording choice doesn't depend on the figure any more. The model choice does. DeepSeek made no wrongful declines, so above about 2,750 dollars it is the cheaper choice, even though its LLM cost is 7 times higher (0.058 against 0.008 dollars a run) and it is 3 times slower. The LLM cost is cents. The mistakes are thousands of dollars.

Most of the wrongful-decline difference is CLM-1218. With the full wording, Luna (reasoning off) declined it in all 3 runs, and one rationale changes its mind halfway: "Decline under section 9 ... Actually the policy was purchased before the storm was named, so that exclusion does not apply". The decision still says decline.

## What I take away

- The eval found a different problem from the one I was told to expect.
- Shortening a document can drop an example that makes a rule clear, not just the rule itself.
- The cost of a wrongful decline is a business number, and it can decide the model.
