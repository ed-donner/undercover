# Appeals to the ombudsman: a brief, a plan and a build

An extension of UnderCover that I wrote as a brief and had my coding agent (Claude Code) plan and build in six phases. It is not one of the course's briefs. The brief is in this folder as [`week3day5assignment_product_APPEALS.md`](week3day5assignment_product_APPEALS.md), and the build is on my fork: https://github.com/stevehome/undercover/tree/week3day4-runtime

## What it adds

When a customer takes one of our final decisions to the ombudsman, a handler can:

- record the appeal against a decided claim (approved and paid, or declined), with the ombudsman's reference and the customer's grounds
- record the ombudsman's decision from its letter: upheld or not upheld
- for an upheld appeal, record the redress as three amounts (the claim still owed, compensation for distress and inconvenience, and interest), which a handler who can sign off pays once, after a confirmation

There is a new Appeals page with the figures (open, upheld, not upheld, the upheld share, redress paid and waiting), a panel on each claim's page, and Copilot tools to look up, record and pay. The decision on the claim is never changed, and the agent never decides an appeal.

The data starts with eight earlier claims and their appeals (two open, three upheld, three not upheld), made from the ombudsman cases in `data/evals/ombudsman/`. The context layer's wording and claims manual have new complaints sections.

## The workflow

Spec first, then the plan, then the build, as the course does it:

1. I asked for options and wrote the brief, `docs/APPEALS.md` (a copy is in this folder).
2. The agent wrote the plan from it, [`docs/PLAN_APPEALS.md`](https://github.com/stevehome/undercover/blob/week3day4-runtime/docs/PLAN_APPEALS.md), with eight decisions it wanted my call on, and six phases with checkbox criteria.
3. It built each phase, checked every criterion, reviewed its own diff against `docs/CODE_STANDARDS.md` and committed:
   [records and documents](https://github.com/stevehome/undercover/commit/ff9ae1e),
   [the app's logic and routes](https://github.com/stevehome/undercover/commit/2de03db),
   [the Copilot](https://github.com/stevehome/undercover/commit/876638d),
   [the dashboard](https://github.com/stevehome/undercover/commit/2d3fc6c),
   [documents and the guide](https://github.com/stevehome/undercover/commit/eea4114),
   [live checks](https://github.com/stevehome/undercover/commit/418a167).

## What the checks showed

- 798 Python tests, 245 dashboard tests at 97% coverage and 34 end-to-end tests, all passing.
- A live run on the default model after one reseed: the Copilot's answer about appeals matched the Appeals page, the redress card survived a reload and paid once, an appeal whose grounds told the AI to approve in full was recorded and marked by the real model (and the Copilot said only that its text was withheld), and a handler who can't sign off was declined with no card.
- The run, the evaluation and the Copilot's turns cost about five cents.

## Takeaways

1. **The live run found what the tests couldn't.** The check of an appeal's text called OpenRouter's chat endpoint at the wrong path and got a 404 page, which came back as a 500. My unit tests faked the client and the end-to-end stand-in answered any path, so both passed. The fix was the right path, a 503 that saves nothing when the check fails, and a stand-in that answers only at the real path. A fake that accepts anything proves little.
2. **Decide the awkward rules in the brief.** The spec said no claim is paid twice, and redress is a second payment on the same claim. Naming that, and making redress its own payment kept once for each appeal, was cheaper in the brief than in the code.
3. **Text from outside is untrusted, even when it is a handler typing it.** The grounds and the ombudsman's reason get the same hidden-instruction check as a claim. The Copilot reads appeals through a second route that leaves out a marked appeal's text. A limit remains: if a handler pastes the text into the Copilot, the model has read it already.
4. **Keep the answer key clear.** The eight starting claims are new records in their own folder, so the two evaluation sets and their scores did not change.
5. **A small change can break a layout.** A sixth link in the navigation pushed Sign out under the Copilot's sidebar, and an existing sign-in test caught it. The header now wraps.
6. **One database, laptop and AWS.** My `.env` and the deployed app share one Supabase database, so `npm run seed` on the laptop reseeds what AWS uses. I wrote [a short deployment guide](https://github.com/stevehome/undercover/blob/week3day4-runtime/docs/DEPLOYING.md) for each kind of change.

## Using the brief

Copy it into `docs/` and ask your agent to plan it, then to implement the plan, as the course does for each day's brief. It expects `data/evals/ombudsman/`, which is not on `main`, and a build with the Copilot from Week 3 Day 5. Nothing in this PR is deployed to AWS.
