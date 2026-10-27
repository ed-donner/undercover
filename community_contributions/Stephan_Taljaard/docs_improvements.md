# Tightening the pilot's docs before planning

Before planning the Week 1 Day 3 pilot, I read `docs/` against the skeleton, the configs and `data/`, looking for gaps a coding agent would have to guess at. Below are the six I closed in my own copy, with the wording I added, so you can paste it into yours.

The docs are short on purpose, and finding gaps during planning is part of the course. So treat these as optional. Editing `docs/` may also give you merge conflicts when you pull Ed's updates.

## 1. Sign-off in the pilot (`docs/SPEC.md`)

The rules say a payout over $1,000 waits for a handler's sign-off, but nothing says how a handler signs off, and the Sign off button only arrives in Week 3 Day 4. Without a note, the agent may build a sign-off screen early, or leave those claims with no way out.

Add under **Not for now**:

```markdown
- Signing off from the screens. In the pilot, a claim over $1,000 that the agent approves stays waiting for sign-off, and its payment stays blocked. A handler signs it off outside the system for now.
```

## 2. How the agent gets started (`docs/SPEC.md`)

The spec doesn't say what starts the agent on a claim. That choice decides what "in progress" means and where the step-by-step view gets its data.

Add to the end of **The pilot**:

```markdown
For the pilot, someone starts the agent from the command line. It works through every waiting claim in the queue, one at a time. A claim shows as in progress while the agent works on it.
```

## 3. Money (`docs/CODE_STANDARDS.md`)

Payouts combine deductibles, item limits and plan maximums, and floats can round them wrongly.

Add as item 7:

```markdown
7. Money: never use floats for amounts. Use `Decimal` in Python and whole cents in TypeScript, and round to the cent only when a payout is worked out.
```

## 4. Which README (`docs/CODE_STANDARDS.md`)

"A short README" doesn't say which README, and the only one in the repo is the course's README at the root.

Replace item 3 with:

```markdown
3. Be concise: no emojis. The product has no README of its own: `docs/STATUS.md` says what's built and how to run it. Never edit the root `README.md`, which belongs to the course.
```

## 5. The plan's file name (`docs/PROCESS.md`)

Step 3 of **Implementing** names `docs/PLAN.md`, but from Week 1 Day 5 the plans are `docs/PLAN_<NAME>.md`.

Replace step 3 with:

```markdown
3. Tick off its criteria in the plan's file, such as `docs/PLAN.md` or `docs/PLAN_HARNESS.md`, and update `docs/STATUS.md`.
```

## 6. Testing the real agent (`docs/PROCESS.md`)

"Tests never call a model" is right, but then every check can pass without the agent ever deciding a real claim. It's also unclear whether the end-to-end tests count.

In **Rules**, replace the first bullet with:

```markdown
- Add tests with each change. Tests never call a model, the end-to-end tests included: use a stub model, or test the screens with data already in place.
```

Then add:

```markdown
- When a build changes the agent, run it on one claim with a real model before you hand the work over, with `MODEL_NAME=openrouter/free` unless asked otherwise, and report what it decided. This is a check by hand, not a test.
```

## Also worth adding (`docs/PROCESS.md`)

Under **Planning**, after the bullet about phases. Each gap above then shows up in the plan, where you can review it:

```markdown
- Start the plan with a short "Open questions and assumptions" section: anything the documents leave unclear, and what you assumed.
```

## Other gaps I noticed but left alone

- `BRAND.md`: white text on Cerulean (3.96:1) and on Raspberry (3.62:1) is below the 4.5:1 that WCAG AA asks for in normal-size text. It also gives no darkened values for Sea Green and Marigold, and doesn't say which color goes with approve, refer and decline.
- `TECH_STACK.md`: it doesn't say how SQLite is seeded from `data/`, which ports the backend and dashboard use, or where the agent's instructions live.
- `STATUS.md`: it doesn't yet say how to run the product, though `AGENTS.md` says it should.
