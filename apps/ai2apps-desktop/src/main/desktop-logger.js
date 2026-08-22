"use strict";

const fs = require("node:fs");
const path = require("node:path");
const util = require("node:util");

const MAX_LOG_BYTES = 2 * 1024 * 1024;

function redact(value) {
  return String(value)
    .replace(/(authorization\s*[:=]\s*bearer\s+)[^\s,;]+/gi, "$1[redacted]")
    .replace(/((?:api[_-]?key|token|ticket|secret)\s*[:=]\s*)[^\s,;]+/gi, "$1[redacted]");
}

function createDesktopLogger(logDirectory) {
  const directory = path.resolve(logDirectory);
  const filename = path.join(directory, "desktop.log");
  fs.mkdirSync(directory, { recursive: true });

  function rotate() {
    try {
      if (fs.statSync(filename).size < MAX_LOG_BYTES) {
        return;
      }
      fs.renameSync(filename, `${filename}.1`);
    } catch (error) {
      if (error.code !== "ENOENT") {
        throw error;
      }
    }
  }

  function write(level, ...values) {
    try {
      rotate();
      const detail = values
        .map((value) => (typeof value === "string" ? value : util.inspect(value, { depth: 4 })))
        .join(" ");
      fs.appendFileSync(
        filename,
        `${new Date().toISOString()} ${level.toUpperCase()} ${redact(detail)}\n`,
        { encoding: "utf8", mode: 0o600 },
      );
    } catch (error) {
      console.error("Desktop log write failed", error);
    }
  }

  return {
    directory,
    filename,
    info: (...values) => write("info", ...values),
    warn: (...values) => write("warn", ...values),
    error: (...values) => write("error", ...values),
  };
}

module.exports = { createDesktopLogger, redact };
