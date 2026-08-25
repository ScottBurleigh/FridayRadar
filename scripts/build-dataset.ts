#!/usr/bin/env npx tsx
/** Compile data/raw + MaxPreps into data/fridayradar.json */
import { spawn } from "node:child_process";
import { join } from "node:path";

const child = spawn("python3", [join(import.meta.dirname, "ingest.py")], { stdio: "inherit" });
child.on("exit", (code) => process.exit(code ?? 1));
