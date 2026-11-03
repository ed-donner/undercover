## Week 2 Day 5: can the improver make the claim agent cheaper?

My version of the Week 2 Day 5 lab, with two experiments on the same question. The first is Ed's assignment: give the improver a shorter policy wording as a choice, and see whether it finds a cheaper prompt. The second is Ed's stretch challenge from the free lab: a cheap model for routine claims and a stronger one for the rest. Everything else is Ed's lab, on GPT-6 Luna.

Before the improver starts, Ed's agent runs with each choice, without the improver, so the improver's picks can be checked against them. The improver never sees those runs. I ran the wording experiment four times and the routing experiment twice, on 25 claims. In these runs every proposal was approved without a person reading it, so the notebook could run from top to bottom. Ed's rule in code still decided which versions were kept.

**How to read the tables.** Every figure is from the held-out set, 25 claims the improver never reads. Accuracy is the share of claims where the decision and the payout match the handler's. The grade is a judge model's score from 0 (F) to 3 (A) for how well the agent's explanation matches the handler's reason. The cost of mistakes is what the wrong decisions would cost UnderCover in a run of 25 claims: $1,500 for a wrongful decline, $50 for a needless referral, and the money paid wrongly on an approval.

Ed's rule keeps a new version when three things hold. Accuracy is at least 0.6 and the grade at least 1.0. At least one measure improves by more than its noise: 0.1 for accuracy, 0.15 for the grade, 15% for cost and for time. And none gets worse by more than its tolerance: 0.1 for accuracy, 0.15 for the grade, 100% for cost, and 25% for time, raised to 200% in the routing experiment.

### 1. A shorter prompt

The policy wording is most of the claim agent's prompt. The improver can choose among three versions of it, and give each claim either the whole wording or only part of it:

- **The full wording** is `data/policy_wording.md`, the policy as written: 1,369 words in 12 numbered sections. Ed's lab uses it.
- **Ed's short wording** is `data/policy_wording_short.md`, Ed's rewrite from Week 1 Day 4: 808 words. It rephrases the rules more briefly and drops the section numbers.
- **My short wording** is my rewrite from Week 2 Day 1 ([my first contribution](../week2day1_models_and_wording/README.md)): 1,191 words. It shortens only the prose around the rules. Every definition, threshold and example is copied word for word, and the 12 numbered sections stay.
- **Only the sections needed** isn't a rewrite. Each claim gets, word for word, the sections every claim needs (1, 8, 9, 10, 11 and 12) and the one for its own benefit, such as baggage or trip delay. That's 664 to 860 words of the full wording a claim. It needs numbered sections, so it works with the full wording and mine, not Ed's.

**No cheaper prompt.** The prompt gets 25% shorter, but the cost falls only 4% to 6%, because about 95% of the prompt is read from the provider's cache at a fraction of the price. Ed's rule counts a cost saving only above 15%.

Ed's agent with each choice, without the improver, averaged over eight runs on the held-out set. The last row combines two choices.

| Ed's agent with | Accuracy | Grade | Seconds a claim | Prompt tokens a claim | Cost a claim |
|---|---|---|---|---|---|
| The full wording, whole, as in Ed's lab | 0.73 | 1.31 | 7.4 | 9,100 | $0.000254 |
| Ed's short wording, whole | 0.70 | 0.91 | 7.5 | 6,800 | $0.000238 |
| My short wording, whole | 0.74 | 1.32 | 12.5 | 8,200 | $0.000253 |
| The full wording, only the sections needed | 0.70 | 1.29 | 6.5 | 6,900 | $0.000241 |
| My short wording, only the sections needed | 0.70 | 1.25 | 6.6 | 6,700 | $0.000244 |

- **Ed's short wording drops the grade below the 1.0 objective.** The agent's explanations match the handlers' reasons less well. On Week 2 Day 1 I found that this wording loses meaning in places.
- **Only the sections needed makes a claim about 12% faster.** Accuracy and the grade stay within the noise.
- **The improver chose my short wording with only the sections needed in 9 of its 11 proposals, and never Ed's.** It rewrote the agent's rules in the same proposals, so the 3 versions it kept most likely owe their better grade to the rules. The wording alone never raised the grade past the noise.

### 2. A cheaper model for routine claims

In one of my runs, all nine claims version 1 got wrong on the evaluation set were baggage or trip delay claims. So a rule in code sends those to the stronger slot, and everything else to the routine one. That's 15 of the 25 held-out claims as hard ones. In this part the improver chooses only the models, not the rules, so any change comes from the models.

**Routing isn't cheaper than one cheap model.** Luna at low for routine claims and medium for hard ones gets the grade of medium for every claim, for a quarter of medium's extra cost. It doesn't get medium's accuracy.

Each setup, without the improver, averaged over four runs on the held-out set:

| Luna's reasoning | Accuracy | Grade | Seconds a claim | Cost a claim | Cost of mistakes |
|---|---|---|---|---|---|
| Low for every claim | 0.69 | 1.24 | 6.6 | $0.000249 | $3,824 |
| Medium for every claim | 0.78 | 1.39 | 8.6 | $0.000330 | $958 |
| Low for routine, medium for hard claims | 0.74 | 1.42 | 7.7 | $0.000268 | $2,605 |
| None for routine, medium for hard claims | 0.75 | 1.43 | 7.5 | $0.000281 | $2,454 |

- **The improver found the routing in its first round, both times.** It kept Luna at low for routine claims and gave the hard ones medium reasoning. The rule kept it both times, for a better grade.
- **Its second idea failed both times.** It moved the hard claims to Gemini 3.5 Flash-Lite, which cost about 9 times as much a claim and lowered the grade, so the rule rolled it back.
- **Medium for every claim made the fewest costly mistakes.** Its cost of mistakes was about a third of routing's. The accuracy gap is inside the noise, but a few wrongful declines at $1,500 each make the difference. For a claim that costs a few hundredths of a cent, medium everywhere looks like the better buy.
- **The hard claims are the majority, so routing can't save much.** The cheap model gets only 8 to 10 of the 25 claims.

### Files and running it

`week2day5_scoreboard.csv` has every run behind the tables above, with columns for the run and the experiment. Run 1's figures are rounded, taken from its printed output. Running the notebook replaces the file with your own runs.

The notebook runs from this folder on the `.venv` kernel with the keys in `.env`, like the lab, and reads my short wording from `../week2day1_models_and_wording/`. One run of both experiments takes about 25 minutes and costs about 50 cents.
