# Appeals to the ombudsman

From the head of claims operations, with our complaints team and our compliance team.

This isn't one of the course's briefs. It's the student's own extension of the product, written as UnderCover's brief so the plan can follow it. Draft for the student's review.

## Where we're heading

When a customer disagrees with our final decision on a claim, they can take it to the ombudsman, an independent body that decides what is fair and reasonable in the circumstances, not only what the policy wording says. The ombudsman either upholds the complaint, and directs us to put it right, or doesn't uphold it, and our decision stands. Either way the ombudsman's decision binds us if the customer accepts it.

Today our records stop at our own decision. We have nowhere to say that a customer appealed, what the ombudsman decided, what we were told to pay or whether we paid it. So we can't answer the questions our head of claims is asked: how many of our decisions are appealed, how many are upheld, and what upheld appeals cost us.

We'd like our handlers to record an appeal against a decided claim, record the ombudsman's decision, and pay any redress the ombudsman directs, in the dashboard or through the Copilot, with the same care we take over any payment. And we'd like to see how our decisions stand up: an Appeals page with the numbers, and each claim's page keeping what happened to it.

This document says what the appeals process does and how it should feel to use. The design is yours, apart from our IT team's choices.

## What we want

### 1. Recording an appeal

- A handler can record an appeal against a claim that has a final decision, approved and paid or declined, whether the agent or a handler made it. A claim that is still waiting, in progress, held for a sign-off, sent back or referred to a handler has no final decision and can't be appealed, and the page and our app say why.
- An appeal records the claim, the ombudsman's reference for the complaint, the date it reached us, the customer's grounds in their own words (up to 2,000 characters) and which handler recorded it, with the time.
- A claim has at most one appeal.
- An appeal is `with the ombudsman` until its decision is recorded.
- Any signed-in handler may record an appeal. Our app checks the handler, as it does for every action.

### 2. Recording the ombudsman's decision

- When the ombudsman decides, a handler records the outcome: `upheld` or `not upheld`, the date of the decision, the ombudsman's reason (up to 2,000 characters), and who recorded it and when. The decision comes from the ombudsman's letter. No model produces or changes an outcome.
- When the outcome is upheld, the handler also records the redress the ombudsman directs, as three amounts in US dollars: the claim amount still owed, compensation for distress and inconvenience, and interest. Each is zero or more, and together they come to more than zero. When the outcome is not upheld, there is no redress.
- A recorded outcome can't be changed in this build. A handler who recorded it wrongly asks our platform team, and the records show who recorded it.
- Any signed-in handler may record an outcome.

### 3. Paying redress

- Redress is paid by a handler who can sign off payouts over the approval limit, at any amount, since an ombudsman's award is binding and rare. When that handler signs off, the sign-off pays the redress in the same step, and the payment records who signed off and when. Anyone else who looks at redress waiting to be paid sees what they can't do and why, and our app refuses it as well.
- The amount paid is the three amounts as recorded, and a handler can't change them when paying.
- An appeal's redress is paid once. Paying it twice is refused. A claim's own payout and an appeal's redress are two separate payments, and the records keep them apart.
- The agent never pays redress. The agent's API key doesn't reach any of this: the appeals routes accept a signed-in handler only.

### 4. What a claim's page shows

- The claim's decision stays exactly as it was made. An appeal never rewrites it, and it never goes back to the agent. The claim page gains a panel for the appeal, below the decision, with the customer's grounds, the ombudsman's outcome and reason, the redress with each of its three amounts, and the payment with who signed it off and when.
- A claim with an appeal shows a label next to its status: `appeal open`, `appeal upheld, redress waiting`, `appeal upheld, redress paid` or `appeal not upheld`. The claim's own status and the queue's five counts don't change.
- On a decided claim with no appeal, the page offers Record an appeal. On a claim with an open appeal, it offers Record the ombudsman's decision, with the redress amounts when the outcome is upheld. On one with unpaid redress, a handler who can sign off sees Pay redress, with a confirmation first, as for any payout.

### 5. The Appeals page

- A new page, Appeals, in the dashboard's navigation beside the Scoreboard, which needs a signed-in handler as every page does.
- Four figures at the top, worked out in code from our records: appeals open, upheld, not upheld, and the upheld share of those decided. Two more: the redress paid so far, and the redress waiting to be paid.
- Below them, every appeal, newest first: claim, customer, plan, the claim's decision and payout, the appeal's status and dates, the outcome and the redress. A filter by status. Each row links to its claim.
- It looks like the rest of the dashboard: light and dark, fonts and colors from `docs/BRAND.md`, and it works beside the Copilot's sidebar and on a narrow window.
- With no appeals, the page says so and says how to record one.

### 6. What a customer's history shows

- A customer's claim history, wherever our app shows it, includes each appeal on an earlier claim: the claim, the outcome and its date.
- The claim history the claim agent reads carries one line for each appeal: the claim, whether it was upheld, and the date. It never carries the customer's grounds or the ombudsman's reason.
- An appeal doesn't count as a claim for the repeat-claims rule in claims manual section 9.

### 7. Text from outside is not to be trusted

- The customer's grounds and the ombudsman's reason come from outside our company, as a claim's story does. When a handler records either, a second model checks it for an instruction to the AI, with the same check we use on claims, run once, and its cost kept with the appeal.
- An appeal where the check finds an instruction is marked, shows the reason the check gave, and is recorded all the same. The text is kept and shown to handlers, but no model, the Copilot included, is ever shown the text of a marked appeal. It sees only that the appeal is marked and why.
- The check is the security team's, and the improver cannot change it.

### 8. The Copilot and appeals

- The Copilot can look up appeals: the list, with a status filter, an appeal in full with its claim, and the figures on the Appeals page. What needs a handler now includes appeals waiting for a decision to be recorded and redress waiting for sign-off.
- It can record an appeal and record an outcome when the handler asks and gives it the details, and it passes on any refusal. Cards for these stand out from lookups, as the Copilot's other changes do.
- It can pay redress, and only after the handler answers a confirmation card with the claim, the customer, the three amounts and the ombudsman's reason, read from our records and never from what the model wrote. This is the sign-off's pause, used again: the Copilot checks that the handler may pay it before it pauses, and nothing is paid until the handler presses Sign off and pay.
- It acts as the handler who asked, with that handler's permissions and sign-in, as in `docs/COPILOT.md`.

### 9. Our records at the start

- After `npm run seed`, our records already hold eight appeals, so the Appeals page isn't empty and handlers can see every state: two open, three upheld (one with its redress paid, two waiting), and three not upheld.
- They're on eight earlier claims, already decided and, where approved, paid, by our handlers before the pilot. These are new claims in our records with their policies and customers, and each has a complete decision record as section 14 of the claims manual describes. Any of them paid over the approval limit carries a handler's sign-off. Each appeal fits its claim: an upheld appeal is against a decision that was fairly open to challenge, and a not upheld appeal is against one that stands.
- Draw them from the 25 ombudsman cases in `data/evals/ombudsman/`, which have real outcomes in `sources.json` (10 upheld, 15 not upheld) and aren't in either evaluation set.
- The queue's 26 waiting claims, the two evaluation sets and their decisions don't change, and a dispatch never works the eight, since none is waiting. The eight show in the queue's Decided count like any decided claim, and the guide and the end-to-end tests are brought up to date.

### 10. The documents the agent reads

Data governance has agreed these changes to the context layer's files in `context/`. Each file's review date and version go up.

- **The policy wording** gets a new section on complaints: what a final response is, that a customer unhappy with it may refer the complaint to the ombudsman within six months, and that we'll abide by an ombudsman's decision the customer accepts. This is a new wording version for policies bought from the day it's published. Every policy in our data is older, so the right to go to the ombudsman applies to them through the manual, not through the wording.
- **The claims manual** gets a section on appeals: how a handler records an appeal and an outcome, and how redress is worked out and paid. Section 3, payment authority, says redress is paid only on a sign-off. Section 9 says an appeal is not a repeat claim. Section 11 allows a customer's medical details to go to the ombudsman and to no one else outside the company. Section 12 covers writing to the customer about an appeal. Section 13 says the right to complain applies whatever the wording version. Section 14 says what an appeal's record holds. The manual's version goes up.
- **The claim rules** get the appeal rules: the time limit, one appeal for each claim, and the three parts of redress.
- **The glossary and the data dictionary** get the new terms and fields: appeal, final response, upheld, not upheld, redress, compensation for distress and inconvenience, and the appeal's fields.
- **The settings** gain nothing: redress needs a sign-off at any amount, so no new limit is needed.

### 11. The guide

- The user guide gets a section on appeals and a picture of the Appeals page, in light and dark, and its picture of a claim shows an appeal. Its capture script takes them, and its test still passes.

## Our IT team's choices

- **No model decides an appeal.** A model's only part in appeals is the check for hidden instructions and the Copilot's reading, recording and paying through the tools above.
- **Our app keeps the appeals** in our Supabase database, in new tables in the `undercover` schema, with the redress payment separate from the claim's own payment. The database, not the code alone, refuses a second appeal for a claim and a second payment of an appeal's redress.
- **The routes follow `docs/TECH_STACK.md`:** an `operation_id`, a one-line docstring, no optional inputs, and recording and paying as separate operations. Each takes a signed-in handler's sign-in and none takes the agent's key. The Gateway's six operations for the agent stay as they are.
- **Our app checks the handler on every action,** as it does today. Recording an appeal or an outcome needs any signed-in handler. Paying redress needs a handler who can sign off over the limit.
- **The Copilot's tools** are added to the Copilot's agent package as the others are, calling the same routes with the handler's sign-in. Its instructions say what appeals are and what it may do with them.
- **Nothing here calls the ombudsman.** Handlers type in what the ombudsman's letters say.

## What stays the same

- The rules in `docs/SPEC.md`, with one change to its wording: a claim's payout is never paid twice, and an appeal's redress is a second, separate payment, paid once for each appeal. The approval limit, the sign-off that pays, the Gateway's Policy and the security check stay as they are.
- A claim is never decided twice by the agent. An appeal never sends a decision back to the agent, and the agent never sees an appeal's text.
- The claim agent, the dispatcher, the improver and their configuration. Nothing here changes how the agent decides.
- The evaluation sets, their decisions and the held-out set stay out of the agent's sight, as `docs/SPEC.md` says.
- The Copilot's sign-in handling, confirmation card and conversations, as `docs/COPILOT.md` describes.
- Tests never call a model, AWS, Supabase Auth or the Gateway, `npm run check` never reads `.env`, and the code follows `docs/CODE_STANDARDS.md`.
- `npm run seed` rebuilds everything, the eight appeals included. Everything `npm run dev` starts, `npm run build` and `npm run check` work on Windows too.
- Nothing in this change creates or deletes anything on AWS.

## How we'll know it's done

- `npm run check` is green with `.env` moved out of the way. Tests with a stub model and stand-ins cover: recording an appeal on a decided claim and its refusal on one that isn't decided or already has an appeal; recording an upheld outcome with redress and a not upheld one without; a handler who can't sign off refused redress; redress paid once and a second payment refused by the database; the three amounts paid as recorded; the agent's key refused on every appeals route; a marked appeal's text never reaching the Copilot or the agent; the claim history the agent reads carrying no grounds or reasons; the Appeals page's figures worked out in code; and the Copilot's pause before redress, answered by a freshly built Copilot on the same saved state. End-to-end tests drive the Appeals page, the claim page's panel and the Copilot's card against stand-ins.
- After one `npm run seed`, with `npm run dev` running on the default model: the Appeals page shows the eight appeals in their five states and its figures match the records, signed in as Dana Whitfield. Then, in one Copilot conversation:
  1. "What appeals do we have, and how many has the ombudsman upheld?"
  2. "Pay the redress on CLM-..., the one waiting." The Copilot shows the confirmation card, and pays once she confirms.
  3. "Record an appeal on CLM-..., because the customer says ..." on a claim decided earlier, then the ombudsman's decision on it.

  Signed in as Marcus Oyelaran, a request to pay redress is declined with the reason. Check the Appeals page and the sidebar in light and dark mode through the Playwright MCP server, and report what the runs spent.

- The user guide is refreshed with `npm run guide`, with every picture looked at before it's committed.
- `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/STATUS.md` describe the product as it now is.

## Not for now

- The agent deciding, preparing or predicting appeals, and scoring its decisions against the ombudsman's. The cases in `data/evals/ombudsman/` suit this later.
- The improver or the claim agent learning from upheld appeals.
- Letters to the customer or the ombudsman, and any contact with either.
- A second appeal, withdrawing an appeal, and changing a recorded outcome.
- A time limit enforced by the app. The documents state it, and a handler judges it.
- Bulk import of the ombudsman's decisions.

## Planning

Follow `docs/PROCESS.md`, but write this plan to `docs/PLAN_APPEALS.md` and tick it off there. Plan five or six phases and commit at the end of each. Do the live checks last, after reseeding once.
