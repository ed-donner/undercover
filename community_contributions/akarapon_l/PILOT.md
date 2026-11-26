# UnderCover pilot

The Week 1 Day 3 pilot turned the health-check skeleton into a local claims desk. The UnderCover Agent works a 25-claim queue and records decisions in SQLite. Claims handlers can review the evidence, follow the agent's progress, and sign off on larger simulated payouts from the dashboard.

## What is built

### FastAPI and SQLite

- Seeded the queue from `data/claims.json` in file order, from `CLM-1001` through `CLM-1025`. A fresh database starts with 25 waiting claims. Restarts reuse the database and preserve claim order, decisions, and payments.
- Joined claims with their supporting documents, policies, plans, add-ons, and customer claim histories. Loaded the policy wording and eligible handlers from the approved seed files. The evaluation set, security fixtures, and claims manual stay outside the pilot's seed and agent inputs.
- Exposed API operations for health, the queue, claim details, policy wording, eligible handlers, agent instructions, and claim activity. Added operations to start and release a claim, record a decision, sign off, and record a simulated payment.
- Kept workflow stage, decision outcome, and payment as separate records or fields. The four workflow stages are Waiting, In progress, Waiting for sign-off, and Decided. The agent can approve, decline, or refer a claim.
- Enforced the $1,000 boundary in the payment operation. An approval of exactly $1,000 can proceed without sign-off. A payout above $1,000 requires sign-off by an eligible handler. The API checks the approved amount in integer cents and records one simulated payment per claim, even when requests are retried or arrive concurrently.

### UnderCover Agent

- Implemented single-claim processing in `run(claim_id, thread_id)`. The agent reads its system instructions, policy wording, and claim evidence through the backend API. The case evidence includes the customer's story, supporting documents, plan terms, add-ons, and previous claims.
- Used LangChain's `create_agent` with OpenRouter. The default is `openai/gpt-6-luna` with low reasoning effort. A user can set `MODEL_NAME` to choose another supported model.
- Defined a structured decision with the outcome, amount in US cents, explanation, and policy citation. The instructions ask for a two- or three-sentence explanation. The runner records the validated decision and requests payment for an eligible approval.
- Recorded timestamped activity as work happens, including reading records and policy wording, reviewing evidence, and recording decisions, sign-offs, and payments. A handled failure before a decision returns the claim to Waiting for retry. If a payment fails after a decision, the decision remains available and the payment can be retried separately.
- Added `uv run -m agent` to work every waiting claim in queue order and `uv run -m agent CLM-1001` to work one waiting claim. The CLI prints the recorded outcome for each claim it works.

### Handler dashboard

- Migrated the frontend from React to Svelte with Vite and strict TypeScript. Removed React, React DOM, and their build, test, and type packages. Kept the health endpoint and the dashboard's backend connection indicator.
- Applied Ubuntu for headings and body text, Ubuntu Italic for accents, and JetBrains Mono for numbers and identifiers. Used the reference palette of navy `#213448`, steel blue `#547792`, pale blue `#94B4C1`, and cream `#EAE0CF` across light and dark themes. 
- Built a responsive queue with stage counts and a table showing claim ID, summary, type, submission date, claimed amount, status, and payout. The queue polls the API so changes appear while the CLI works. Alternating row backgrounds separate adjacent claims in both themes.
- Updated the Status column to show the agent's actual outcome once available. Approved uses mint, Declined uses rose, and Referred uses amber, with visible text labels. Over-limit approvals also show **Waiting for sign-off** until a handler signs off.
- Added the Payout column to the right of Status. It shows the approved amount, including approvals awaiting sign-off, `$0.00` for declines, and a dash when the amount is undetermined. Claimed and Payout are separate amounts.
- Built a detail view with the original story, itemized costs, supporting documents, policy and trip details, prior claims, the decision and cited policy section, payment state, and live activity. Added handler selection, sign-off, and payment retry. A failed payment request leaves a recorded sign-off visible.
- Added a read-only view showing the exact agent instructions served by the backend.

## Tooling and checks

- Switched Python type checking from Pyright to ty. The project locks ty in `uv.lock`, and `uv sync` installs it alongside Ruff and the test dependencies. The type-check scope covers `backend/` and `agent/`, including their tests.
- Configured Prettier, ESLint, TypeScript, `svelte-check`, and Vitest for the Svelte frontend. Lefthook formats matching staged files and runs the relevant Python or frontend checks at commit time. The full handoff command is `npm run check`, which also runs Playwright.
- Used scripted model replies for automated tests. Playwright runs against a disposable SQLite database and separate local ports. The suite verified queue order, persisted state, the sign-off boundary, duplicate payment requests, both CLI modes, live updates, read-only instructions, outcome badges, payout display, and alternating rows in both themes.
- The full suite passed with 17 Python tests, 7 frontend unit tests, and 2 Playwright tests. Python coverage was 96.65% and frontend statement coverage was 95.98%, both above the 80% thresholds. 

The student also shared a live CLI run covering all 25 claims. The terminal showed approve, decline, and refer outcomes while the dashboard summarized 21 Decided claims and 4 Waiting for sign-off. That walkthrough led to displaying each decision directly in the queue alongside any sign-off still required.

## Run the pilot

From the repository root, run `uv sync`, `npm install`, and `npm run dev`. Open [the dashboard](http://localhost:5173) or [the interactive API docs](http://localhost:8000/docs). Put `OPENROUTER_API_KEY` in `.env` before running the agent against OpenRouter.

The backend creates `undercover.sqlite3` at the repository root on first startup. `UNDERCOVER_DB` can point to a separate database. The pilot operates locally with simulated payments and a shared handler dashboard. 

The [pilot plan](PLAN.md) contains the completed acceptance checklist.
