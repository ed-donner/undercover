# Can AI review AI's code?

Testing Codex against a human reviewer on the Week 1 Day 5 harness build. By Erfan Hesami, November 10, 2026.

This is my end-of-Week-1 assignment. I built the harness myself, then took it in my own direction: testing whether an AI reviewer can find what a human reviewer found.

My build is at https://github.com/HopeFan/undercover/tree/week1day5-ehesami. It still has the issues described here: this is a review experiment, not the refactor.

## The story

**1. The build looked done.** I had Claude Code build the Day 5 harness for the UnderCover claims agent: the tools, instructions and safety rules that let it work a whole queue of claims on its own. Every test passed, and a live run on five claims worked.

**2. I asked Codex to review it.** I wanted to know whether a second AI could catch what the first one missed. Codex's built-in review (`codex review --base week1day5-start`) found one real bug: asking for a run of 0 claims quietly ran the whole queue. That was all it found.

**3. I asked about code quality.** Asked whether the code was clean, Codex said "generally clean", with seven small suggestions.

**4. Then I found Ed's human review.** Ed had his own coding agent build the same thing and reviewed it himself (`docs/HUMAN_REVIEW_HARNESS.md` on the `week1day5-end` branch). His verdict: "unfit for a PR". He listed eight design problems, such as URLs hard-coded everywhere, two ways of calling the backend, modules reaching into each other, and instructions written as step-by-step scripts instead of goals. All eight were in my build too. Codex had caught none of them. Claude, which wrote the code, half-noticed three and played them down.

**5. I asked why.** It was how I asked, not the tool:

- I used a bug-hunting review, and none of Ed's issues were bugs. The code worked; it was organized badly.
- I told Codex to judge the code against the existing style, but the existing style was the problem, so I had told it to approve.
- I never gave it the standard: production-ready, good enough to merge.

**6. So I built a review harness.** The course teaches that an agent is only as good as its harness, so I built one for the reviewer:

- A standard: "This product is moving to production. Review it like a pull request."
- Questions with countable answers: draw the import graph, count the hard-coded paths, list every way the code calls the backend, check whether the instructions give goals or scripts.
- An answer key: Ed's eight issues as a scoring rubric, written before the run.
- Rules: read-only, no looking at other branches (so no peeking at Ed's notes) and no opening `data/evals/`.

**7. I ran Codex again.** It found 6 of Ed's 8 issues and half-found the other 2. Then it found something Ed had not mentioned: the agent takes a claim's id from the model, and a claim's text comes from the customer, so a hidden instruction in a claim could steer the agent to a different claim. The backend limits the damage, but binding the claim id in trusted context is the right fix.

**8. I was honest about the score.** I wrote the questions after reading Ed's notes, so some of them point the right way and the score is flattering. I did not keep rewording the prompt until it hit 8 of 8, because that would be studying the answer key before the exam. The real test is my next build, where nobody has seen the answers.

### What I learned

- A reviewer, human or AI, finds what you ask it to look for, against the standard you give it.
- "Generally clean" from an AI reviewer can mean you asked the wrong question.
- Questions with countable answers make it look instead of skim.
- A reviewer marking its own work goes easy on itself, so use fresh eyes.
- Human and AI review add up: Ed caught the design, Codex caught a security gap.
- You can test a reviewer the way you test an agent: give it an answer key and score it.

## The numbers

| Reviewer | How it was asked | Ed's 8 issues |
|---|---|---|
| Codex, `codex review` | Its built-in review | 0 |
| Codex, `codex exec` | Code quality against the existing style | 0 |
| Claude Code, its own code | "Is the code clean?" | 0, and 3 in part |
| Codex, `codex exec` | `review-prompt.md` | 6, and 2 in part |

| Ed's issue | Quality review | `review-prompt.md` |
|---|---|---|
| E1. Hard-coded backend URLs and paths | Missed | Found |
| E2. Two ways to call the backend | Missed | Found |
| E3. No single API module; `queue.py` reaches into `main` | Missed | Found |
| E4. Harness spread out and mixed with UnderCover details | Missed | Partly |
| E5. Tools not all in one place | Missed | Partly |
| E6. `work_queue` does too much | Missed | Found |
| E7. Run state passed by hand, not through LangChain's tool runtime | Missed | Found |
| E8. Instructions are step-by-step scripts, not goals | Missed | Found |

## Run it yourself

From the root of the repo, on your own branch, with Codex CLI:

```
codex exec -s read-only "$(cat community_contributions/erfan_hesami/week1day5_codex_review/review-prompt.md)"
```

Check its command log afterwards to be sure it kept to the rules.

## Files

- `review-prompt.md`: the review prompt
- `rubric.md`: Ed's eight issues as a scoring rubric, written before the run
