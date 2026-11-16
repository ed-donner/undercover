# Can AI review AI's code?

My end-of-Week-1 assignment, on the Week 1 Day 5 harness build. By Erfan Hesami, November 2026.

## Why

My coding agent built the Day 5 harness, and every test passed. Ed's human review of his own build of the same thing found eight design problems and called it "unfit for a PR". I wanted to know whether an AI reviewer could catch what he caught, and what it would take. Ed's review gave me an answer key to score against.

## What I did

1. Built the harness with Claude Code, from the brief. The tests passed and a live run worked.
2. Asked Codex to review it, with its built-in review and then with a question about code quality.
3. Checked Ed's eight problems against my build. All eight were there.
4. Wrote a review prompt (`review-prompt.md`) that sets a production standard and asks questions with countable answers, such as "count the hard-coded paths". I wrote down Ed's eight problems as a rubric (`rubric.md`) before the run, and scored Codex against it. Codex could not see Ed's notes.
5. Refactored my build from Ed's notes, without reading his code, with a review by a fresh subagent before every commit. Then I ran the same prompt again, unchanged.
6. Ran the refactored agent on the whole queue, and compared my refactor with Ed's.

## The outcome

- **Codex's own reviews found none of the eight problems.** It found one real bug and called the code "generally clean".
- **With my prompt, Codex found 6 of the 8 and half-found the other 2.** It also found a security gap Ed hadn't mentioned: the agent took the claim id from the model, so a hidden instruction in a customer's claim could point it at another claim. The score flatters a little, because I wrote the questions after reading Ed's notes.
- **After the refactor, the same prompt found 5 of the 8 fixed and 3 partly left.** The agent now takes the claim, policy and customer from LangChain's context, which closes the security gap.
- **The fresh reviews caught bugs every test had missed.** An empty list reached the model as blank text, so for 21 of the 25 claims it saw nothing instead of "no earlier claims", and my rewrite of the instructions had dropped most of the manual's interpretation topics.
- **The refactored agent decided all 25 claims** in 9 minutes 19 seconds for $0.11 on DeepSeek V4.1 Flash, with no failures and every payment rule held. The decisions are not yet scored against the answer key.
- **My refactor came out close to Ed's:** the same four modules and the same decisions on the five trial claims. His is leaner and more idiomatic, with a middleware that records each step and a search tool that keeps his instructions short. Mine goes further on security and has a full run behind it.

## What I learned

- A reviewer, human or AI, finds what you ask it to look for, against the standard you give it.
- Questions with countable answers make an AI reviewer look instead of skim.
- An agent reviewing its own code goes easy on it, so get fresh eyes before each commit.
- You can test a reviewer the way you test an agent: an answer key, written first, and a score.

## Use it yourself

Run the prompt on your own branch with Codex CLI, from the root of the repo:

```
codex exec -s read-only "$(cat community_contributions/erfan_hesami/week1day5_codex_review/review-prompt.md)"
```

And check by hand whether your claim agent's tools take a claim, policy or customer id from the model.

- My build before the refactor: https://github.com/HopeFan/undercover/tree/week1day5-ehesami
- After it: https://github.com/HopeFan/undercover/tree/week1day5-refactor
- `review-prompt.md`: the review prompt
- `rubric.md`: Ed's eight problems as a scoring rubric, written before the run
