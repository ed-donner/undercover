// Shared helpers for the Claude Code hooks in this folder.
// Claude Code runs a hook as a command and sends the tool call as JSON on stdin.
// A PreToolUse hook answers with JSON on stdout: allow, ask (the human must confirm) or deny.
import { readFileSync } from "node:fs";

export function readInput() {
  try {
    return JSON.parse(readFileSync(0, "utf8"));
  } catch {
    return {};
  }
}

function answer(permissionDecision, reason) {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision,
        permissionDecisionReason: reason,
      },
    }),
  );
  process.exit(0);
}

/** Stop the tool call. The reason goes back to Claude, which has to find another way. */
export const deny = (reason) => answer("deny", reason);

/** Pause the tool call until the human confirms it in the terminal. */
export const ask = (reason) => answer("ask", reason);

/** Let the tool call through. */
export const allow = () => process.exit(0);

/** Forward slashes, and relative to the project, so one set of patterns works on Windows and Mac. */
export function relativePath(filePath, projectDir = process.env.CLAUDE_PROJECT_DIR ?? process.cwd()) {
  const normal = (value) => value.replaceAll("\\", "/");
  const root = normal(projectDir).replace(/\/$/, "");
  const path = normal(filePath ?? "");
  return path.toLowerCase().startsWith(`${root.toLowerCase()}/`) ? path.slice(root.length + 1) : path;
}
