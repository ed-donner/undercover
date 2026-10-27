import { existsSync, unlinkSync } from "node:fs";
import path from "node:path";

export default function globalSetup() {
  const dbPath = path.join(process.cwd(), "backend", "undercover.db");
  for (const suffix of ["", "-wal", "-shm", "-journal"]) {
    const file = dbPath + suffix;
    if (existsSync(file)) unlinkSync(file);
  }
}
