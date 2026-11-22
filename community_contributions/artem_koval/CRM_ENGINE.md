# The CRM engine: one engine, five domain packs

This file is the write-up. The engine itself lives in my fork, on the branch
`artem_koval-crm-engine`, under `community_contributions/artem_koval/crm/`:

https://github.com/ArtemKoval/undercover/tree/artem_koval-crm-engine/community_contributions/artem_koval/crm

## What it is

The week one milestones of this course build an insurance backoffice: a queue
of trip-delay claims, an AI case worker that reads each claim and decides it
against policy documents, a sign-off for large awards, and payment. This
contribution extends that build into a domain-agnostic CRM engine. The engine
carries the generic words: case, contract, award, worker, decision. Each
domain is a pack folder under `domains/`, and the pack carries every domain
word: the seed data, the award rules, the policy documents, the agent
instructions, and the eval sets. One seam at `domains/loader.py` keeps the
engine code free of domain nouns. `CRM_DOMAIN` names the active pack, and the
same engine runs all five:

| Pack | Domain | The desk decides |
| --- | --- | --- |
| `insurance` | A fictional travel insurer | Trip-delay claims against policy tiers |
| `helpdesk` | FastFix IT support | Support entries against service contracts |
| `opsdemo` | Nimbus OpsDesk | Site incidents against operations agreements |
| `library` | Northgate Public Library | Checkout and renewal requests against membership rules |
| `garage` | AutoFix Vehicle Repair | Repair jobs against service agreement tiers, with routing to a garage fleet |

A pack switch changes the words on every screen, the rules the engine
enforces, and the cases in the queue.

## The five desks

Every shot below shows the live dev stack, started fresh for that pack, with
no model key and no mock. The branch carries the full set under
`crm/docs/screenshots/<pack>/`: the sign-in page, the queue, one case, the
scoreboard, and the settings. `bash e2e/capture_domains.sh` recaptures the
set for every pack.

### insurance — the travel insurer

Dana Whitfield's claims desk: Maya Patel's canceled flight, decided against
Section 3 of the policy.

![insurance queue](https://raw.githubusercontent.com/ArtemKoval/undercover/artem_koval-crm-engine/community_contributions/artem_koval/crm/docs/screenshots/insurance/r2-queue.png)

![insurance case](https://raw.githubusercontent.com/ArtemKoval/undercover/artem_koval-crm-engine/community_contributions/artem_koval/crm/docs/screenshots/insurance/r3-case.png)

### helpdesk — FastFix IT support

Priya Nair's support desk: a two-hour platform outage that stopped ticket
intake at four clinics, claimed against the service contract.

![helpdesk queue](https://raw.githubusercontent.com/ArtemKoval/undercover/artem_koval-crm-engine/community_contributions/artem_koval/crm/docs/screenshots/helpdesk/r2-queue.png)

![helpdesk case](https://raw.githubusercontent.com/ArtemKoval/undercover/artem_koval-crm-engine/community_contributions/artem_koval/crm/docs/screenshots/helpdesk/r3-case.png)

### opsdemo — Nimbus OpsDesk

Ida Sorensen's operations desk: badge readers at a clinic site refused every
staff card for a morning, claimed under the site's operations agreement.

![opsdemo queue](https://raw.githubusercontent.com/ArtemKoval/undercover/artem_koval-crm-engine/community_contributions/artem_koval/crm/docs/screenshots/opsdemo/r2-queue.png)

![opsdemo case](https://raw.githubusercontent.com/ArtemKoval/undercover/artem_koval-crm-engine/community_contributions/artem_koval/crm/docs/screenshots/opsdemo/r3-case.png)

### library — the Northgate Public Library loan desk

Rosa Meridian works checkout and renewal requests against the membership
rules. The case page offers "Approve and issue", "Decline the request", and
"Refer to the lead librarian", and cites the loan rules it relied on.

![library queue](https://raw.githubusercontent.com/ArtemKoval/undercover/artem_koval-crm-engine/community_contributions/artem_koval/crm/docs/screenshots/library/r2-queue.png)

![library case](https://raw.githubusercontent.com/ArtemKoval/undercover/artem_koval-crm-engine/community_contributions/artem_koval/crm/docs/screenshots/library/r3-case.png)

### garage — the AutoFix Vehicle Repair desk

Gordon Vale's repair desk: ten repair jobs wait, the queue carries an
Estimate column, and the case page offers "Authorize the repair", "Decline
the job", and "Refer to the service manager" under the Repair rules.

![garage queue](https://raw.githubusercontent.com/ArtemKoval/undercover/artem_koval-crm-engine/community_contributions/artem_koval/crm/docs/screenshots/garage/r2-queue.png)

![garage case](https://raw.githubusercontent.com/ArtemKoval/undercover/artem_koval-crm-engine/community_contributions/artem_koval/crm/docs/screenshots/garage/r3-case.png)

## What a pack carries

- `manifest.json` — the pack identity: the resolution kinds, the outcome
  kinds, the documents, the settings, and the approval limit.
- `rules.py` — the pure award arithmetic. The engine calls it before any
  decision records, so the number on the desk comes from the pack's rules,
  not from the model.
- `policy/` — the wording and the desk manual, as documents with owners and
  versions.
- `context/` — the lookups the agent reads: the glossary, the plans, the
  data dictionary, the case rules, and the reference data.
- `data/` — the seed: cases, customers, contracts, workers, and the company.
- `instructions/` — the brief each case agent reads before it works a case.
- `evals/` — the labeled decisions and the held-out sets.

`uv run python validate.py <pack>` checks a pack against the engine
contract. `uv run python smoke.py <pack>` seeds a temporary database and
works three cases on a stub model, with no network and no key.

## What the engine adds past week one

- The sign-in, with worker roles and the over-limit sign-off.
- The award resolution: the pack's pure rules settle the award, and the
  agent's judgment works inside that frame.
- The dispatch panel: one run works the waiting cases, with a cap on the
  case agents that work at once.
- The scoreboard, the improvement rounds, and the configuration page:
  evaluations against the labeled sets, an improver that proposes versions,
  and a verdict that keeps a version or rolls it back.
- The AWS invoke path beside a local emulator, with a wiring gate.
- A hermetic suite: a stub model replaces OpenRouter in the tests, the e2e
  specs start their own stack, and no test calls a real model.

## Run it

```bash
git clone https://github.com/ArtemKoval/undercover
cd undercover
git checkout artem_koval-crm-engine
cd community_contributions/artem_koval/crm
uv sync && npm install
cp .env.example .env
npm run seed && npm run dev
```

Open `http://127.0.0.1:5173` and sign in with
`dana.whitfield@undercover.example` and the dev password `crm-dev`. Switch
the desk with:

```bash
CRM_DOMAIN=library npm run seed && CRM_DOMAIN=library npm run dev
```

The README in the folder carries the sign-in table for all five packs, the
check commands, and the layout map.

## Takeaways

- One seam beats many switches. The loader names the pack contract, so a new
  domain lands as a folder, and the engine code stays unchanged.
- Pure rules and agent judgment stay separate. The rules settle the award,
  and the agent reads the policy, weighs the story, and records the
  decision.
- Policy lives in documents with owners and versions, not in code paths.
- Tests that need no model key keep the agent work honest: the harness, the
  guards, and all five desks stay testable on a laptop.
