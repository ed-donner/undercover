// Runs a command with the variables in .env, when there is a .env file.
// Used as: node --env-file-if-exists=.env scripts/run-with-env.mjs uv run ...
import { spawn } from "node:child_process";

const [command, ...args] = process.argv.slice(2);
const child = spawn(command, args, { stdio: "inherit" });

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal));
}
child.on("exit", (code) => process.exit(code ?? 1));
