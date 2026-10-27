// PreToolUse hook for Edit, Write and MultiEdit.
// Asks the human to confirm a change that would loosen a check, instead of letting Claude do it quietly.
import { allow, ask, readInput, relativePath } from "./lib.mjs";

// Changing any of these files changes the rules, so a person confirms it every time.
const RULE_FILES = [
  /^lefthook\.yml$/,
  /^\.claude\//,
  /^\.github\/workflows\//,
  /(^|\/)(eslint|tsconfig|playwright|prettier|vitest|vite)[^/]*\.(config\.)?(js|mjs|cjs|ts|json)$/,
  /(^|\/)\.?prettierrc/,
  /(^|\/)ruff\.toml$/,
];

// These files are edited all the time, for dependencies and scripts, so only a change that touches a rule is confirmed.
const MIXED_FILES = [/^pyproject\.toml$/, /^package\.json$/];
const LOOSENING =
  /fail_under|\bignore\b|per-file-ignores|\bexclude\b|\bomit\b|\bselect\b|threshold|coverage|"check[^"]*"\s*:|"prepare"\s*:|strict/i;

// Comments that silence a linter, a type checker or the coverage report, and tests that are switched off.
const SUPPRESSIONS =
  /#\s*noqa|#\s*type:\s*ignore|#\s*pyright:\s*ignore|#\s*pragma:\s*no cover|eslint-disable|@ts-ignore|@ts-nocheck|@ts-expect-error|istanbul ignore|v8 ignore|\.skip\(|\bit\.todo\(|\btest\.fixme\(/;
const SOURCE = /\.(py|ts|tsx|js|jsx|mjs)$/;

const { tool_input: input = {} } = readInput();
const path = relativePath(input.file_path);
const added = [input.content, input.new_string, ...(input.edits ?? []).map((edit) => edit.new_string)]
  .filter((text) => typeof text === "string")
  .join("\n");

if (RULE_FILES.some((pattern) => pattern.test(path))) {
  ask(`${path} defines the repo's checks. Confirm that this change is intended and doesn't loosen anything.`);
}
if (MIXED_FILES.some((pattern) => pattern.test(path)) && LOOSENING.test(added)) {
  ask(`This change to ${path} touches a rule, a threshold or a check script. Please confirm it.`);
}
if (SOURCE.test(path) && SUPPRESSIONS.test(added)) {
  ask(`This change to ${path} adds a comment or a skip that silences a check. Please confirm it.`);
}

allow();
