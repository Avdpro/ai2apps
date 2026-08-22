"use strict";

const http = require("node:http");
const path = require("node:path");
const { spawn } = require("node:child_process");

const executableOverride = process.env.AI2APPS_DESKTOP_EXECUTABLE;
const electronPath = executableOverride || require("electron");
const appRoot = path.resolve(__dirname, "..");

function json(response, status, body) {
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
  });
  response.end(JSON.stringify(body));
}

const server = http.createServer((request, response) => {
  if (request.url === "/health") {
    json(response, 200, { status: "healthy" });
    return;
  }
  if (request.url === "/v1/platform/health") {
    json(response, 200, {
      status: "ok",
      product: "ai2apps",
      version: "0.1.0-smoke",
      api_version: "v1",
      runtime: { provider: "smoke", attached: true },
      database: { status: "ready" },
    });
    return;
  }
  if (request.url === "/") {
    response.writeHead(200, {
      "content-type": "text/html; charset=utf-8",
      "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'",
      "cache-control": "no-store",
    });
    response.end(
      "<!doctype html><meta charset=utf-8><title>AI2Apps Smoke</title>" +
        "<style>body{font:16px system-ui;padding:3rem}</style>" +
        "<h1>AI2Apps Desktop Shell smoke</h1>",
    );
    return;
  }
  response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
  response.end("Not found");
});

server.listen(0, "127.0.0.1", () => {
  const address = server.address();
  const nodeUrl = `http://127.0.0.1:${address.port}/`;
  const args = [`--node-url=${nodeUrl}`, "--smoke-exit-after-load"];
  if (!executableOverride) {
    args.unshift(appRoot);
  }
  const child = spawn(electronPath, args, { stdio: "inherit" });
  const timeout = setTimeout(() => {
    console.error("Electron launch smoke timed out.");
    child.kill("SIGTERM");
  }, 20000);

  child.on("error", (error) => {
    clearTimeout(timeout);
    server.close();
    console.error(error);
    process.exitCode = 1;
  });
  child.on("exit", (code, signal) => {
    clearTimeout(timeout);
    server.close();
    if (code !== 0) {
      console.error(`Electron launch smoke failed (code=${code}, signal=${signal || "none"}).`);
      process.exitCode = 1;
    }
  });
});
