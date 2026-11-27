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
| DeepSeek V4.1 Flash, concise + rule | 1,884 | 1,884 | 1,884 | 1,884 |
| DeepSeek V4.1 Flash, concise + examples | 1,060 | 1,060 | **1,060** | **1,060** |

Between full and concise, the answer flips: full is cheaper at 500, concise from 1,500 up. Once the examples are back, the wording choice doesn't depend on the figure any more. The model choice does.

My first DeepSeek run used the concise + rule wording, without the examples. So it changed the model and the wording at once, and put the break-even at about 2,750 dollars. A comment on LinkedIn made me look again, and I reran DeepSeek on the same wording as Luna. The examples fixed two claims for DeepSeek (CLM-1216 and CLM-1202, both a camera with its lens). Its accuracy went from 90.7% to 97.3%, and its cost of mistakes from 1,884 to 1,060 dollars a run.

The break-even is now about 1,510 dollars. At the lab's 1,500 the two models are tied, 1,052 against 1,060. DeepSeek made no wrongful declines, but its LLM cost is 7 times higher (0.060 against 0.0085 dollars a run) and it is 3 times slower. The LLM cost is cents. The mistakes are thousands of dollars.

Both totals rest on one claim each. 95% of Luna's cost is CLM-1209, wrongly declined in 2 of 3 runs. 90% of DeepSeek's is CLM-1213, wrongly paid 2,868 dollars in one run. Without those two, Luna is about 52 dollars a run and DeepSeek about 104. With 25 claims, the model choice comes down to how often cases like these two turn up, and I'd want more claims like them before trusting it.

Most of the wrongful-decline difference is CLM-1218. With the full wording, Luna (reasoning off) declined it in all 3 runs, and one rationale changes its mind halfway: "Decline under section 9 ... Actually the policy was purchased before the storm was named, so that exclusion does not apply". The decision still says decline.

## What I take away

- The eval found a different problem from the one I was told to expect.
- Shortening a document can drop an example that makes a rule clear, not just the rule itself.
- The cost of a wrongful decline is a business number, and it can decide the model.
- Change one thing at a time. My first model comparison changed the wording too, and that moved the break-even from about 1,510 to 2,750 dollars.
- Before trusting a total, look at which claims make it up.
