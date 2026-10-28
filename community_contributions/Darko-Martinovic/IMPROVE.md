# Week 2 Day 5: an improver that improves the claim agent, with handlers who sign in

Darko Martinovic

My build of the self-improvement brief in `docs/IMPROVE.md`, on top of my swarm build ([PR #67](https://github.com/ed-donner/undercover/pull/67)) rather than on Ed's `week2day5-start`. I read Ed's `week2day5-end` before planning and followed his design where it fit my code, and compare the two below. The code is in my fork:

- The build as delivered: [week2day5-end](https://github.com/Darko-Martinovic/ai-fde-agentic-engineering/tree/week2day5-end)
- The plan I built it from, in seven phases, with where the build differs from it: [docs/PLAN_IMPROVE.md](https://github.com/Darko-Martinovic/ai-fde-agentic-engineering/blob/week2day5-end/docs/PLAN_IMPROVE.md)
- What is built and every live run: [docs/STATUS.md](https://github.com/Darko-Martinovic/ai-fde-agentic-engineering/blob/week2day5-end/docs/STATUS.md)

![The Improvement page after two live rounds: version 2 kept, version 3 rolled back](https://raw.githubusercontent.com/Darko-Martinovic/ai-fde-agentic-engineering/f17c63231ce622a320288b10d57055e40f8eb149/docs/screenshots/w2d5/improvement-light.png)

## What it does

Handlers sign in through Supabase Auth, and the backend checks each token against the project's public keys. Anyone signed in sees everything; only a handler who can sign off payouts over the limit (Dana Whitfield) signs off or rejects a held payout, changes the settings, starts or stops a round, and approves or rejects the improver's proposals. The others see why they can't.

The claim agent's instructions, model and reasoning effort are kept in versions, each with what it changed as a diff, why, who proposed and approved it, and its held-out scores. The approval limit and what a round works to (the objectives, the noise, the tolerance, the spending limit) are settings, kept as a history of who changed what.

A round runs the lab's loop inside the product. The current version is evaluated where it needs to be, once on the evaluation set and twice on the held-out set. The improver, a LangChain `create_agent` with the lab's four tools, follows its recipe: it reads the evaluation set's mistakes beside the handlers' reasons, proposes a change and pauses in `HumanInTheLoopMiddleware`. The page shows the change as a diff with the model before and after and the improver's reason; a handler approves it after a confirmation, or rejects it with a reason the improver reads as the tool's answer. An approved change is evaluated the same way, the backend keeps or rolls it back by the business's rule on the held-out set, whose claims the improver never sees, only their scores, and the improver ends the round by proposing a better recipe. Jev grades every evaluated copy's explanation against the handler's reason. Once a round reaches its spending limit it starts no more claims, and it refuses an evaluation it estimates it can't afford; claims already working finish, so it can go a little over.

## How it differs from Ed's `week2day5-end`

| | Ed's build | Mine |
|---|---|---|
| Version 1 and the first recipe | GPT-6 Luna with no reasoning; the first recipe tries a model or a higher reasoning effort before it adds rules | GPT-6 Luna at low, as the brief says, and the lab's first recipe, which adds a rule for each mistake |
| The improver's model | GPT-6.1 Sol at medium | GPT-6 Luna at medium, as in the lab |
| A held payout | A sign-off | A sign-off, or a rejection with a note the agent decides again from, as in my earlier builds |
| Reads the dashboard polls | Each in a fixed number of queries, however many rounds and runs there are | Each evaluation scored as it is read, so `GET /api/evaluations` takes about 3 seconds on Supabase with nine evaluations |
| Structure | The claim operations in `main.py`; a router each for runs, the configuration (with the settings) and improvement | A router per resource, with a separate one for what only the agent's service writes to a round (`rounds.py`) and one for the settings |
| API checks | Tests and end-to-end tests | The same, plus a Postman collection with a request for every operation, run with newman against Supabase |

## Live runs

On GPT-6 Luna, with the backend, the agent's service and the dashboard running against Supabase, after one reseed, signed in as Dana Whitfield on the dashboard.

- **Round 1.** Version 1 scored 76% on the evaluation set and 80% and 84% on the held-out set. The improver's first proposal added five rules with the claims manual's numbers written in. I rejected it, saying rules should point to the wording and the manual rather than restate them; its next proposal kept two checks, the cause of a delay as the carrier's evidence shows it and the manual's repeat-claim rules, each pointing at its sections. I approved it. Version 2 scored 96% and 92% on the held-out set, a grade of 1.68 against 1.48, and was kept: "accuracy, grade improved". The recipe it proposed groups mistakes by rule and grounds each change in a section; I approved it. The round cost $0.15 of its $0.50.
- **Round 2.** Version 2 already had its evaluations, so the improver went straight to a change, a check on per-item limits and add-ons, which I approved. Version 3 scored 92% and 92%, a grade of 1.58, and was rolled back: "no score improved by more than the noise". Its recipe, which asks for the decision failure itself to be told apart from the explanation around it, was approved. $0.08.
- **Noise.** Version 1's two held-out runs differed by 4 points of accuracy against a noise of 10, by 0.02 in grade against 0.15, and by 8% and 2% in cost and time per claim against 15%. Ed's differed by 8 points and 0.16, so one run of 25 claims can move about as far as the noise allows, which is why the rule averages two.
- **A dispatch and a sign-off.** A dispatch at N=25 on version 2 worked all 25 claims in 90 seconds for $0.02: 15 approved, 4 declined, 6 referred, three held for a sign-off. Signed in as Marcus Oyelaran, a sign-off and a settings change were refused, each saying why; Dana's sign-off showed the claim paid 4.1 seconds later.
- **Langfuse.** Each round's improver traces are in one session named after its thread, four for round 1 and three for round 2, one per stretch between reviews; its evaluations' claims carry its tag. The v2 observations endpoint ignores a plain `tags` parameter: the tag filter goes in its `filter` parameter.

The checks spent $0.25, by the backend's records and by the key's usage alike.

## Takeaways

- **A rejection goes back into the next proposal.** The improver's first proposal on both builds was a pile of rules, and on both a handler rejected it with a reason the next proposal took in. In my round that next change was kept; in Ed's it was rolled back. One round each can't say more than that the loop works as the lab drew it.
- **A slow read stopped a page from ever loading.** My dashboard's polls aborted a request still in flight at each tick. With nine evaluations the Scoreboard's read on Supabase takes about 3 seconds against a 2-second poll, so it never finished, and in development React's strict mode made it worse: the first, aborted load marked the poll free while the second was still running. A poll now waits for its load, and gives up on one that never answers after three intervals. Ed's build does both already: its polls wait for each answer, and it answers the reads in a fixed number of queries.
- **Time per claim at N=25 is long, and steady.** My claims took about 72 seconds each at 25 at once and Ed's about 31, on the same model but at low reasoning against his none. I think mine also waits longer for the database connections, but I haven't measured it. It was steady between runs, so it decided no verdict, but it would if the noise on time were tighter.
