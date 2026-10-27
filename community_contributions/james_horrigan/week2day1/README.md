## Week 2 Day 1: Full vs short policy wording

### What I ran

Two experiments on UnderCover's 25 harder claims, each run 3 times with GPT-6 Luna, reasoning off, both using the payout tool:

- **Full wording:** the agent with `data/policy_wording.md`
- **Short wording:** the agent with the concise `data/policy_wording_short.md` from Week 1 Day 4

### Results (averaged over 3 runs)

|                                | Full wording | Short wording |
| ------------------------------ | ------------ | ------------- |
| Accuracy (decision and amount) | 0.880        | 0.853         |
| Decision accuracy              | 0.960        | 0.947         |
| Kappa                          | 0.935        | 0.911         |
| Cost of mistakes per run       | $293         | $974          |
| LLM cost per run               | $0.009       | $0.010        |
| Straight-through rate          | 0.72         | 0.73          |

### Does the short wording keep the accuracy?

Yes on the face of it, but the bigger difference shows up in the cost of mistakes. The short wording's mistakes cost more than three times as much.

### Is it cheaper or faster?

No. LLM cost was about the same. The tokens saved in the system prompt are small next to the claim, the tool calls and the output. Each run of 25 claims took about 3 to 3.5 minutes with either wording.

### Where the short wording lost money

- **CLM-1223:** declined a claim the handler referred, a $1,500 wrongful decline (1 of 3 runs)
- **CLM-1216:** overpaid by $328 (2 of 3 runs), the full wording got it right every time
- **CLM-1207:** paid $32.50 too little (2 of 3 runs). The customer claimed $950 for a sketchbook that cost $32.50, because it held a year of their drawings. The right answer is to pay for the book but not the drawings. The full wording says so directly: "For a laptop, a drive, a notebook or a document we pay for the physical item, and we do not pay for the data, the writing or the work it holds." The short wording cuts this to "Not covered: the value of data or work on a device". It no longer says the physical item is still paid, and it doesn't mention notebooks. So the agent left the sketchbook out altogether. The full wording got this claim right in all 3 runs

Even leaving out the $1,500 decline, the short wording averages about $474 a run against $293.

### Changing WRONGFUL_DECLINE

| WRONGFUL_DECLINE | Full | Short  |
| ---------------- | ---- | ------ |
| $500             | $293 | $640   |
| $1,500           | $293 | $974   |
| $5,000           | $293 | $2,140 |
| $10,000          | $293 | $3,807 |

The full wording made no wrongful declines, so its cost doesn't change. The short wording made one in three runs, so its cost rises with the figure. The choice stays the same at every value, and the gap grows the more UnderCover weighs wrongful declines.

### Conclusion

Keep the full wording. The short wording saves nothing on model cost or speed, and it adds mistakes that cost far more than the model does. One wrongful decline costs $1,500, while a whole run of 25 claims costs about a cent in tokens.

### Lessons

- **Score by cost, not just accuracy.** Accuracy put the two wordings almost level, while the cost of mistakes separated them clearly.
- **Look at the claims, not just the averages.** The wrong claims show which rules the short wording lost.
