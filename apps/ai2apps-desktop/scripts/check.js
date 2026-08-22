"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const files = [
  "src/main/index.js",
  "src/main/connection-store.js",
  "src/main/desktop-logger.js",
  "src/main/node-connection.js",
  "src/main/security-policy.js",
  "src/preload/index.js",
  "src/renderer/bootstrap/bootstrap.js",
  "scripts/smoke.js",
  "scripts/package-macos.js",
  "tests/connection-store.test.js",
  "tests/desktop-logger.test.js",
  "tests/node-connection.test.js",
  "tests/security-policy.test.js",
];

for (const relative of files) {
  const absolute = path.join(root, relative);
  if (!fs.existsSync(absolute)) {
    console.error(`Missing expected file: ${relative}`);
    process.exit(1);
  }
  const result = spawnSync(process.execPath, ["--check", absolute], {
    stdio: "inherit",
  });
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

console.log(`Checked ${files.length} JavaScript files.`);
