# The UnderCover Auditor

My capstone: a third agent for UnderCover, beside the claim agent and the Copilot. It helps a claims operations manager judge how accurately the agent handles claims and see patterns across claims that nobody deciding one claim can see, such as repeated lenient approvals for the same or linked claimants.

Code: https://github.com/kxs7733/undercover/tree/kx-auditor-capstone, on top of `week3day5-end`. Start with `docs/AUDITOR.md`, `backend/audit_checks.py` and `agent/auditor/graph.py`.

## How it works

Code finds, the model explains.

- **Six checks in code, with no model:** repeat claimants, linked claimants, payouts just under the limit, send-backs that raised a payout, sign-off patterns and third claims paid without referral. There's also a scorecard of each agent version's accuracy and leniency, as figures only, so the Auditor never sees a handler's decision on a labeled claim.
- **The model only writes the explanation,** and the app checks it. It refuses accusing words, claims outside the finding and any figure not in the evidence.
- **Sign-off above a limit:** a finding with a risk score of 70 or more, or paid more than the approval limit, pauses in `interrupt()` until the manager opens a case or dismisses it. The Auditor can't open one itself.
- **No customer's words reach it:** no stories, documents, reasons or notes, and no contact details, so a claim can't talk it out of a finding.
- **Assignment pieces:** `PostgresSaver` checkpoints in Supabase, the context layer over MCP, a `PostgresStore` namespace per manager holding their dismissals, and four free Render services from `render.yaml`. No AWS, so no Runtime, Gateway or AgentCore Memory. The memory looks dismissals up by exact pattern, without pgvector.

## Success measures, set before the build

I added a planted scenario with `npm run seed:audit`: a linked group, a second senior handler whose send-backs raise payouts, an injected customer story, and innocent decoys.

| Measure | Target | Result |
|---|---|---|
| Planted patterns found | All | 6 of 6 |
| Decoys wrongly flagged | At most 1 | 0 |
| Model's figures not in the evidence | 0 | None kept |
| Accusing words, or contact details reaching the model | 0 | None |
| An injected story changes the result | Never | It didn't |
| A pause survives a restart with nothing redone | Yes | Yes, and one paused on the laptop finished on Render |
| Cost of an audit | Under $0.50 | About $0.002 |
| `npm run check` | Green | All but `e2e/copilot.spec.ts:59`, which was already flaky here before my changes and passes alone |

I wrote both the scenario and the checks, so this shows the checks catch known patterns, not how they'd do on real claims. Details are in `docs/STATUS.md`.

## What I took away

- **The most interesting risk isn't the agent's.** A person could steer an honest agent by sending decisions back until the payout rises, and nothing on a single claim shows it.
- **The Auditor flagged the agent too.** It raised CLM-1019, outside my scenario: version 1 paid a third claim in 12 months that the manual says to refer. The course data includes that claim as a test of the rule, so it's a known hard case, but it was caught from the payment records alone.
- **Independent review earned its keep.** Two fresh reviewers found problems my tests had passed, including an audit stuck after a restart and agent-written free text that could reach the Auditor.
