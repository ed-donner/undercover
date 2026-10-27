// PreToolUse hook for Bash. Blocks the ways of getting round the pre-commit hook.
import { spawnSync } from "node:child_process";
import { allow, ask, deny, readInput } from "./lib.mjs";

const PROTECTED = String.raw`(lefthook\.yml|\.claude[\\/]|\.github[\\/]workflows|\.git[\\/]hooks|eslint\.config|tsconfig|playwright\.config|vite\.config|pyproject\.toml)`;
const WRITES = String.raw`(>|\bsed\s+-i|\btee\b|\bmv\b|\bcp\b|\brm\b|\bdel\b|\bchmod\b|Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item|\bgit\s+(checkout|restore)\b)`;

const RULES = [
  [/--no-verify\b/, "--no-verify skips the pre-commit hook. Fix what the hook reports instead."],
  [
    /\bgit\b[^;&|\n]*\bcommit\b[^;&|\n]*\s-[a-zA-Z]*n[a-zA-Z]*(?=\s|$)/,
    "git commit -n is --no-verify. Fix what the hook reports instead.",
  ],
  [/\bgit\b[^;&|\n]*\bpush\b/, "Never push. Tell the user the work is committed and let them push."],
  [/core\.hooksPath/i, "Changing core.hooksPath would switch the pre-commit hook off."],
  [/\b(LEFTHOOK(_EXCLUDE)?|HUSKY|SKIP|PRE_COMMIT_ALLOW_NO_CONFIG)\s*=/, "Setting this variable skips the pre-commit hook."],
  [/\blefthook\s+(uninstall|install\s+--reset-hooks-path)/, "That would remove the pre-commit hook."],
  [/\bgit\s+config\b[^;&|\n]*\bhooks?\b/i, "Changing git's hook configuration is not allowed."],
];

const { tool_input: input = {} } = readInput();
const command = String(input.command ?? "");
// Quoted text can't change what git does, so it is dropped before the checks that look at flags.
const unquoted = command.replace(/"[^"]*"|'[^']*'/g, '""');

// A rule that looks at short flags only reads the unquoted text, so a commit message can mention -n.
const QUOTE_SAFE = new Set([RULES[1][0]]);

for (const [pattern, reason] of RULES) {
  const text = QUOTE_SAFE.has(pattern) ? unquoted : command;
  if (pattern.test(text)) deny(`Blocked by the repo's guardrails. ${reason}`);
}

// Work goes on a branch of its own, so a commit on main is refused. GUARDRAILS_BRANCH stands in for git in the tests.
if (/\bgit\b[^;&|\n]*\bcommit\b/.test(unquoted)) {
  const branch =
    process.env.GUARDRAILS_BRANCH ??
    spawnSync("git", ["branch", "--show-current"], { encoding: "utf8" }).stdout.trim();
  if (["main", "master"].includes(branch)) {
    deny(`Blocked by the repo's guardrails. You're on ${branch}. Create a branch, then commit there.`);
  }
}

if (new RegExp(`${WRITES}[^\\n]*${PROTECTED}|${PROTECTED}[^\\n]*${WRITES}`, "i").test(unquoted)) {
  ask("This command changes a file that the guardrails protect. Please confirm.");
}

allow();
