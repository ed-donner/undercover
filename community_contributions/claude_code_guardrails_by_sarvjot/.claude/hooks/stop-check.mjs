// Stop hook. Claude can't finish a turn while the checks fail on the files it changed.
// Exit code 2 sends the output back to Claude and keeps it working.
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readInput } from "./lib.mjs";

// Which changed files trigger which check. Playwright is left out because it is slow; the pre-commit hook skips it too.
// GUARDRAILS_TEST_COMMAND replaces the commands, so the tests don't need the whole toolchain.
const CHECKS = [
  { name: "Python", files: /^(backend|agent)\/.*\.py$|^pyproject\.toml$/, command: "npm run check:python" },
  { name: "TypeScript", files: /^(dashboard|e2e)\/|\.config\.|^tsconfig/, command: "npm run check:ts" },
].map((check) => ({ ...check, command: process.env.GUARDRAILS_TEST_COMMAND ?? check.command }));

const run = (command) => spawnSync(command, { shell: true, encoding: "utf8", timeout: 600_000 });
const key = (text) => createHash("sha1").update(text).digest("hex");

// A hook that blocks on failure can cycle for ever: Claude stops, the hook blocks, Claude can't fix it, it stops again.
// So a failure blocks once for each state of the files. If Claude stops again without changing anything, or a later
// turn only reads, the stop goes through with a warning. The documented stop_hook_active field isn't relied on,
// because the hooks documentation no longer lists it.
const { session_id: session = "none" } = readInput();
const reported = join(tmpdir(), `claude-guardrails-reported-${key(process.cwd() + session)}`);
const passed = join(tmpdir(), `claude-guardrails-passed-${key(process.cwd())}`);

const status = run("git status --porcelain -uall");
if (status.status !== 0) {
  process.stderr.write(`git status failed, so the checks can't tell what changed:\n${status.stderr}\n`);
  process.exit(2);
}
const changed = status.stdout
  .split("\n")
  .filter(Boolean)
  .map((line) => line.slice(3).split(" -> ").pop().replaceAll("\\", "/"));
if (changed.length === 0) process.exit(0);

// The state of the files: what git reports, plus the contents of each changed file, since git diff leaves out
// new files. The checks are skipped when it matches the last pass.
const read = (file) => {
  try {
    return readFileSync(file, "utf8");
  } catch {
    return "";
  }
};
const fingerprint = key(status.stdout + run("git diff HEAD").stdout + changed.map(read).join("\n"));
if (existsSync(passed) && readFileSync(passed, "utf8") === fingerprint) process.exit(0);
if (existsSync(reported) && readFileSync(reported, "utf8") === fingerprint) {
  process.stdout.write(
    JSON.stringify({ systemMessage: "The checks are still failing. Fix them before you commit; CI will not merge this." }),
  );
  process.exit(0);
}

// A check that can't run is a failure, never a pass: a control that skips without its tool is worse than none.
const failures = [];
for (const check of CHECKS.filter(({ files }) => changed.some((file) => files.test(file)))) {
  const result = run(check.command);
  if (result.status !== 0) {
    const output = `${result.stdout}\n${result.stderr}`.trim().split("\n").slice(-40).join("\n");
    failures.push(`${check.name} checks failed (${check.command}):\n${output}`);
  }
}

if (failures.length === 0) {
  rmSync(reported, { force: true });
  writeFileSync(passed, fingerprint);
  process.exit(0);
}

writeFileSync(reported, fingerprint);
process.stderr.write(`${failures.join("\n\n")}\n\nFix these, without loosening any check, before you finish.\n`);
process.exit(2);
