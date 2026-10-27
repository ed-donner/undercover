// Run with: node --test .claude/hooks
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const PROJECT = join(here, "..", "..");

function decide(script, toolInput, branch = "feature") {
  const result = spawnSync("node", [join(here, script)], {
    input: JSON.stringify({ tool_input: toolInput }),
    encoding: "utf8",
    env: { ...process.env, CLAUDE_PROJECT_DIR: PROJECT, GUARDRAILS_BRANCH: branch },
  });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout ? JSON.parse(result.stdout).hookSpecificOutput.permissionDecision : "allow";
}

const bash = (command, branch) => decide("guard-bash.mjs", { command }, branch);
const edit = (file_path, new_string = "x = 1") => decide("guard-files.mjs", { file_path, new_string });

test("bash: ways of skipping the pre-commit hook are denied", () => {
  for (const command of [
    "git commit --no-verify -m fix",
    "git commit -m fix --no-verify",
    "git commit -nm fix",
    "git commit -n -m fix",
    "git -c core.hooksPath=/dev/null commit -m fix",
    "git config core.hooksPath .nohooks",
    "LEFTHOOK=0 git commit -m fix",
    "SKIP=lint git commit -m fix",
    "$env:LEFTHOOK = 0; git commit -m fix",
    "npx lefthook uninstall",
    'bash -c "git commit --no-verify -m fix"',
    "git push",
    "git push --force origin main",
    "git -C . push",
  ]) {
    assert.equal(bash(command), "deny", command);
  }
});

test("bash: ordinary commands are allowed", () => {
  for (const command of [
    "git commit -m 'fix the -n flag'",
    "git commit -am fix",
    "git status",
    "git diff HEAD",
    "npm run check",
    "uv run pytest -q",
    "cat lefthook.yml",
    "ls .claude/hooks",
  ]) {
    assert.equal(bash(command), "allow", command);
  }
});

test("bash: quoted text is still searched, so a message that mentions a bypass is denied (a deliberate false positive)", () => {
  assert.equal(bash('git commit -m "document LEFTHOOK=0"'), "deny");
});

test("bash: writing to a protected file asks", () => {
  for (const command of [
    "sed -i 's/80/10/' pyproject.toml",
    "echo x > lefthook.yml",
    "rm .git/hooks/pre-commit",
    "Set-Content .claude/settings.json ''",
  ]) {
    assert.equal(bash(command), "ask", command);
  }
});

test("files: the files that define the checks ask", () => {
  for (const path of [
    "lefthook.yml",
    ".claude/settings.json",
    ".claude/hooks/guard-bash.mjs",
    ".github/workflows/check.yml",
    "eslint.config.js",
    "tsconfig.json",
    "playwright.config.ts",
    "dashboard/vite.config.ts",
  ]) {
    assert.equal(edit(path), "ask", path);
  }
});

test("files: absolute and Windows paths are handled", () => {
  assert.equal(edit(join(PROJECT, "lefthook.yml")), "ask");
  assert.equal(edit(PROJECT.replaceAll("/", "\\") + "\\lefthook.yml"), "ask");
});

test("files: loosening a rule in pyproject.toml or package.json asks, other edits do not", () => {
  assert.equal(edit("pyproject.toml", "fail_under = 10"), "ask");
  assert.equal(edit("pyproject.toml", '[tool.ruff.lint]\nignore = ["E501"]'), "ask");
  assert.equal(edit("package.json", '"check:python": "echo skipped"'), "ask");
  assert.equal(edit("pyproject.toml", '    "httpx>=0.28.1",'), "allow");
  assert.equal(edit("package.json", '"react": "^19.3.0"'), "allow");
});

test("files: comments that silence a check ask", () => {
  for (const text of [
    "import os  # noqa: F401",
    "x: int = 'a'  # type: ignore",
    "def f():  # pragma: no cover",
    "// eslint-disable-next-line",
    "// @ts-ignore",
    "describe.skip('x', () => {})",
  ]) {
    const path = text.startsWith("//") || text.includes("describe") ? "dashboard/src/a.ts" : "backend/a.py";
    assert.equal(edit(path, text), "ask", text);
  }
  assert.equal(edit("backend/a.py", "def add(a, b):\n    return a + b\n"), "allow");
});

test("files: MultiEdit is checked edit by edit", () => {
  const edits = [{ new_string: "ok = True" }, { new_string: "x = f()  # noqa" }];
  assert.equal(decide("guard-files.mjs", { file_path: "backend/a.py", edits }), "ask");
});

test("bash: a commit on main is denied, on a branch it is allowed", () => {
  assert.equal(bash("git commit -m fix", "main"), "deny");
  assert.equal(bash("git commit -m fix", "master"), "deny");
  assert.equal(bash("git commit -m fix", "feature/x"), "allow");
  assert.equal(bash("git status", "main"), "allow");
});

// The stop hook runs in a scratch repo with one changed Python file, and a stand-in for the real check command.
function stop(repo, command, session) {
  const result = spawnSync("node", [join(here, "stop-check.mjs")], {
    cwd: repo,
    input: JSON.stringify({ session_id: session }),
    encoding: "utf8",
    env: { ...process.env, GUARDRAILS_TEST_COMMAND: command },
  });
  return { status: result.status, stderr: result.stderr, stdout: result.stdout };
}

function scratchRepo() {
  const repo = mkdtempSync(join(tmpdir(), "guardrails-"));
  spawnSync("git", ["init", "-q"], { cwd: repo });
  mkdirSync(join(repo, "backend"));
  writeFileSync(join(repo, "backend", "a.py"), "x = 1");
  return repo;
}

test("stop: a failure blocks once for each state of the files, and an unchanged tree goes through", () => {
  const repo = scratchRepo();
  const failing = `node -e "console.error('boom'); process.exit(1)"`;
  const first = stop(repo, failing, "s1");
  assert.equal(first.status, 2);
  assert.match(first.stderr, /boom/);
  const second = stop(repo, failing, "s1");
  assert.equal(second.status, 0, "nothing changed, so the stop goes through");
  assert.match(second.stdout, /systemMessage/);
  assert.equal(stop(repo, failing, "s1").status, 0, "a later turn that only reads isn't blocked again");
  writeFileSync(join(repo, "backend", "a.py"), "x = 2");
  assert.equal(stop(repo, failing, "s1").status, 2, "a new change is checked again");
});

test("stop: passing checks let the turn end, and a missing tool counts as a failure", () => {
  const repo = scratchRepo();
  assert.equal(stop(repo, 'node -e ""', "s2").status, 0);
  const other = scratchRepo();
  assert.equal(stop(other, "this-command-does-not-exist-12345", "s3").status, 2);
});

test("stop: nothing changed means nothing to check", () => {
  const repo = mkdtempSync(join(tmpdir(), "guardrails-"));
  spawnSync("git", ["init", "-q"], { cwd: repo });
  assert.equal(stop(repo, "exit 1", "s4").status, 0);
});
