# Guardrails for Claude Code

`docs/PROCESS.md` asks Claude Code to run the checks, never use `git commit --no-verify` and never push. This turns those instructions into Claude Code hooks that enforce them, with CI as the one gate nothing local can switch off. It follows the layering in [ed-donner/bench](https://github.com/ed-donner/bench/blob/main/docs/CONTROLS.md) and adds hooks that act before a bypass happens.

| Layer | What it does | Bypassable |
|---|---|---|
| `guard-bash.mjs` (PreToolUse, Bash) | Denies `--no-verify`, `git commit -n`, `git push`, `core.hooksPath`, `LEFTHOOK=0`, `HUSKY=0`, `SKIP=`, `lefthook uninstall` and a commit on `main`. Asks before a shell command writes to a file that defines the checks | A command the patterns miss, or a person |
| `guard-files.mjs` (PreToolUse, Edit/Write) | Asks for confirmation before a change to `lefthook.yml`, `.claude/`, lint, type and test configs or workflows, a rule or threshold in `pyproject.toml` or `package.json`, or a `noqa`, `type: ignore`, `eslint-disable`, `@ts-ignore`, `pragma: no cover` or `.skip(` | A person can say yes |
| `stop-check.mjs` (Stop) | Holds the turn open while `check:python` or `check:ts` fails on the changed files. Blocks once for each state of the files: if Claude stops again without changing anything, or a later turn only reads, it goes through with a warning, so it can't loop. A check that can't run counts as a failure | Once per change, then it relents |
| GitHub Actions and branch protection | Runs `npm run check` on every PR; `check` is a required status | No |

A deny stops the command. An ask pauses until a person confirms. Only the last row is a gate; the rest keep the agent from skipping a check by shortcut.

## Install

Copy `.claude/` and `.github/workflows/check.yml` to the repo root and commit them. Nothing is installed: the hooks are Node `.mjs` files, so they run on Windows and Mac.

In GitHub, add a ruleset for the default branch with enforcement active and an empty bypass list. Block deletions and force pushes, require a pull request, and require the status check `check` (the job name in `check.yml`; renaming the job quietly stops the requirement matching).

Add to `docs/PROCESS.md` under Rules:

```
- Never work on `main`. Create a branch before you commit.
- Claude Code hooks enforce these rules. If one blocks you or asks for confirmation, don't look for another way round: explain what you were trying to do and let the user decide.
- Fix the code, don't loosen the config. Never edit `.claude/`, `lefthook.yml` or a lint, type or coverage setting to make a check pass.
```

Edit `CHECKS` in `stop-check.mjs` and `RULE_FILES` in `guard-files.mjs` to fit the repo.

## Test

`node --test .claude/hooks` feeds each hook the JSON Claude Code sends and checks the decision, and runs the Stop hook in a scratch git repo.

## Limits

- The hooks read command text, so a bypass the patterns don't foresee can get through. That is what CI is for: nothing is *merged* unless it passes, but a client-side hook can't stop a *commit*.
- Quoted text is searched too, so a commit message that mentions `--no-verify` or `LEFTHOOK=` is denied on purpose.
- The Stop hook uses its own marker, not `stop_hook_active`, which the current hooks documentation no longer lists. The hook input and output formats are Claude Code's and change, so check them against the current docs and try a short real session before relying on this.
