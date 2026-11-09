# Plan: our records in the database, not in files

Moves the data the backend reads from `data/` files at startup (claims, policies, customers, plans, handlers, company settings, policy wording and claims manual) into the database, so Supabase holds all of our records. No brief asks for this yet: it comes from the student, and it changes no behavior. Every API response, the agent and the dashboard stay exactly as they are.

## What I found in the code

- `backend/data.py` loads every file into module-level dicts at import. Four modules use them: `db.py` (to seed one `claims` row per claim id), `claims.py` (claim content, policies, customers, handlers), `payouts.py` (plans, add-ons, deductible benefits, the approval limit) and `main.py` (document sections, handlers).
- The `claims` table holds only a claim's state. Its content (story, items, documents, dates) is in `claims.json`.
- `knowledge.json`, `policy_wording_short.md`, `security/` and `evals/` are not used by the product. They stay as files and are out of scope. The backend still never reads `data/evals/`.
- The agent and the dashboard reach all of this through the API, so they don't change.

## Design

**The files become the seed.** `data/*.json` and `data/*.md` stay in the repo as the starting records, as `data/README.md` describes. They are read in one place, when a database is empty, and from then on the database is the source. `npm run seed` still resets everything. Editing a file no longer changes a running system; changing a record means changing the row.

**One table per kind of record**, in the `undercover` schema on Postgres (SQLAlchemy Core, so SQLite is the same):

| Table | One row per | Columns |
|---|---|---|
| `settings` | company setting | `key`, `value` (JSON): the approval limit, the filing window, the repeat-claim review, the allowances, the document versions |
| `plans` | plan | `plan`, `name`, the limits, waiting hours and deductible as columns |
| `add_ons` | add-on | `add_on`, `name`, `effect`, and `electronics_per_item_limit_cents` for the one add-on that has it |
| `deductible_benefits` | benefit the deductible applies to | `benefit` |
| `policies` | policy | `policy_id`, `customer_id`, `plan`, `purchased_on`, `sold_through`, `status`, with `add_ons`, `trip` and `travelers` as JSON |
| `customers` | customer | `customer_id`, `name`, `email`, `phone`, `date_of_birth`, `customer_since`, with `address` and `previous_claims` as JSON |
| `handlers` | handler | `handler_id`, `name`, `role`, `email`, `can_approve_over_limit` |
| `document_sections` | section of a document | `document`, `position`, `heading`, `text` |
| `claims` (existing) | claim | today's state columns plus the claim's content: `policy_id`, `customer_id`, `claim_type`, `submitted_on`, `incident_date`, `incident_location`, `summary`, `story`, `amount_claimed_cents`, with `items` and `documents` as JSON |

Nested lists and objects are JSON columns, not tables of their own: nothing queries inside them, and they come back as the same shapes the API returns today. Plan limits are columns because the payout rules read them one by one.

**Money.** Columns hold whole cents as today. Amounts inside JSON columns keep their exact decimal value: the engine reads JSON back through the same `Decimal` conversion `backend/data.py` uses today (`backend/money.py`), so nothing becomes a float.

**No cache.** Reference reads are small queries on a primary key. A cache would hide an edited row until a restart, which is the problem this change removes. At most 4 connections per process still holds.

**Existing databases.** `create_all` adds new tables but cannot add columns to the live `claims` table, so Supabase needs one `npm run seed` after this change. That wipes claim state and the agent's saved progress. They are test data. The local SQLite file is deleted by the same command.

**Not copied into the database:** the plan's `status` field in `claims.json` (the state column replaces it).

## Phases

### Phase 1: The tables and the file reader

Define every table, and read the files into rows, with nothing using them yet.

- `backend/tables.py` (new): the table definitions only, moved out of `db.py` together with the new ones. `db.py` keeps the engine and `connection()`.
- `backend/seed_data.py` (new): turns `data/*.json` and `data/*.md` into rows for each table, including splitting each document into its `##` sections. The only module that opens `data/`.
- `backend/db.py`: when a database has no rows, insert the rows from `seed_data.py` into every table, in one transaction; the JSON columns read back through the `Decimal` conversion.

**Success criteria**

- [x] `uv run pytest backend -q` passes with the existing tests unchanged.
- [x] A new test builds a fresh SQLite database and checks the row counts: 25 claims, 50 policies, 49 customers, 3 plans, 3 add-ons, 3 handlers, and the sections of both documents.
- [x] A new test reads a policy, a customer and a claim back and finds amounts as `Decimal`, equal to the file's values (no float rounding).
- [x] Starting twice does not duplicate rows.

### Phase 2: Reading reference records

One module for reading the records back, so callers never write SQL.

- `backend/reference.py` (new): `company_setting(key)`, `plan(name)`, `add_on(name)`, `deductible_benefits()`, `policy(policy_id)`, `customer(customer_id)`, `handlers()`, `handler(handler_id)`, `sections(document)`, `section(document, heading)`. It raises `NotFound` for a missing record, as `data.py` does.

**Success criteria**

- [x] A new `backend/tests/test_reference.py` goes through each function and compares the result with the same record loaded straight from the file (the test reads the file, not `data.py`).
- [x] A missing policy, customer, plan, add-on, setting, document and section each raise `NotFound`. A missing handler returns `None`, as `data.handler` did, because a sign-off by an unknown handler is a 409, not a 404.
- [x] Sections come back in the order of the document.

### Phase 3: Documents, handlers and settings switch over

Move the smallest users first.

- `backend/main.py`: the section, handler and sections routes call `reference.py`.
- `backend/payouts.py`: the approval limit comes from `reference.company_setting`.
- `backend/claims.py`: the sign-off handler check calls `reference.handler`.
- `backend/data.py`: loses the settings, handlers and documents.

**Success criteria**

- [x] `uv run pytest -q` passes, the payout and sign-off tests unchanged.
- [x] A test changes the approval limit row and shows `needs_sign_off` follows it with no restart.
- [x] `GET /api/documents/policy_wording/sections` and one section return the same text as before (compared with the file in a test).

### Phase 4: Plans, policies and customers switch over

- `backend/payouts.py`: plans, add-ons and the deductible list come from `reference.py`.
- `backend/claims.py`: the claim's policy and the customer's previous claims come from `reference.py`.
- `backend/data.py`: loses plans, policies and customers.

**Success criteria**

- [x] `uv run pytest -q` passes, `test_payouts.py` unchanged.
- [x] `GET /api/claims/CLM-1001` returns the claim merged with policy `POL-2001` and customer `CUS-3001`'s previous claims, as `docs/PLAN.md` described, compared in a test with a result built from the files.
- [x] `POST /api/payouts` gives the same payout as before for a Premium baggage claim and an Economy trip delay.

### Phase 5: The claims' content switches over

- `backend/claims.py`: `list_claims`, `get_claim`, `list_unfinished` and the ordering by `submitted_on` read the content from the `claims` table, ordered in SQL.
- `backend/db.py`: the seed inserts the whole claim, not just its id and status.
- `backend/data.py`: deleted.

**Success criteria**

- [ ] `data.py` is gone and `grep -rn "backend.data\|import data" backend agent` finds nothing.
- [ ] A test compares `GET /api/claims` and `GET /api/claims/<id>` for all 25 claims with values built from `data/claims.json`, `policies.json` and `customers.json`, field by field.
- [ ] `GET /api/claims/CLM-9999` is still 404.
- [ ] `npx vitest run --root dashboard` and `npm run e2e` pass unchanged, which shows the API did not change.

### Phase 6: Supabase, checks and docs

- `agent/tests/test_structure.py`: a new check that only `backend/seed_data.py` opens `data/`, and that nothing under `backend/` or `agent/` mentions `evals`.
- `docs/TECH_STACK.md`, `docs/STATUS.md`, `docs/SPEC.md` (the "Our records" paragraph only, not its Rules) and `data/README.md` describe the files as the seed.

**Success criteria**

- [ ] With `.env`, stop `npm run dev` and run `npm run seed`. Through the Supabase MCP server, `undercover` holds all the new tables with 25 claims, 50 policies, 49 customers, 3 plans, 3 add-ons, 3 handlers, and the sections of both documents.
- [ ] `npm run dev` then shows the queue with 25 claims, and a claim page with its story, items, policy and the customer's history (Playwright MCP, light and dark).
- [ ] A held claim can still be signed off on the dashboard and shows as paid, without a model: after `decide_claim` through the API on a claim over the limit, the sign-off buttons appear, and a sign-off with the agent's service stopped is accepted.
- [ ] The Supabase advisors report nothing new, and I note that the `undercover` schema is not exposed through Supabase's data API (customers' personal data is in it).
- [ ] `pg_stat_activity` for user postgres shows no more connections from our processes than before: still at most 4 in the backend.
- [ ] `npm run check` is green with `.env` moved out of the way.
- [ ] No live model run is needed: the agent and its tools are unchanged and reach everything through the API. If wanted, one claim with `MODEL_NAME=openrouter/free` after a reseed.

## Questions for you

1. **One `claims` table or two?** I put the claim's content and state in one table, which needs the reseed above. A second table (`claim_records`) would keep the Supabase queue as it is, at the cost of a join and two tables for one thing. I recommend one.
2. **JSON columns or full tables** for items, documents, travelers and previous claims? I recommend JSON, as nothing needs to query inside them. Say so if the claims team will want reports on items.
3. **Row-level security.** Customers' personal data would sit in Supabase. The schema is not exposed through the data API, so I have not planned any policies. Tell me if you want RLS turned on anyway.
