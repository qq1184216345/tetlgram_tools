import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const isWin = process.platform === "win32";
const venvPython = join(root, ".venv", isWin ? "Scripts/python.exe" : "bin/python");

if (!existsSync(venvPython)) {
  console.error("虚拟环境不存在，请先运行: npm run setup:python");
  process.exit(1);
}

const child = spawn(venvPython, ["-m", "backend.main"], {
  cwd: root,
  stdio: "inherit",
  shell: isWin,
});

child.on("exit", (code) => process.exit(code ?? 0));
