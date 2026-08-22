"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  configuredNodeOverride,
  configuredNodeUrl,
  endpoint,
  normalizeNodeUrl,
  probeNode,
  validatePlatformHealth,
} = require("../src/main/node-connection");

function response(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

test("normalizes loopback and HTTPS node URLs", () => {
  assert.equal(normalizeNodeUrl("http://localhost:8000"), "http://localhost:8000/");
  assert.equal(normalizeNodeUrl("https://node.example.test/base"), "https://node.example.test/base/");
  assert.equal(endpoint("https://node.example.test/base", "/health"), "https://node.example.test/base/health");
});

test("rejects insecure remote, credentialed, and non-HTTP node URLs", () => {
  assert.throws(() => normalizeNodeUrl("http://node.example.test"), /must use HTTPS/);
  assert.throws(() => normalizeNodeUrl("https://user:secret@node.example.test"), /credentials/);
  assert.throws(() => normalizeNodeUrl("file:///tmp/node"), /HTTP or HTTPS/);
});

test("CLI node URL takes precedence over the development environment", () => {
  assert.equal(
    configuredNodeUrl(
      ["electron", ".", "--node-url=http://127.0.0.1:9000"],
      { AI2APPS_DESKTOP_NODE_URL: "https://ignored.example.test" },
    ),
    "http://127.0.0.1:9000/",
  );
  assert.equal(configuredNodeOverride(["electron", "."], {}), null);
});

test("validates the existing AI2Apps platform health contract", () => {
  assert.deepEqual(
    validatePlatformHealth({
      status: "ok",
      product: "ai2apps",
      version: "0.1.0",
      api_version: "v1",
      runtime: { provider: "omlx", attached: true },
      database: { status: "ready" },
    }),
    {
      product: "ai2apps",
      version: "0.1.0",
      apiVersion: "v1",
      databaseStatus: "ready",
      runtimeProvider: "omlx",
    },
  );
  assert.throws(
    () => validatePlatformHealth({ status: "ok", product: "other", api_version: "v1" }),
    /not an AI2Apps node/,
  );
  assert.throws(
    () => validatePlatformHealth({ status: "ok", product: "ai2apps", api_version: "v2" }),
    /Unsupported AI2Apps API version/,
  );
});

test("probes a ready, product-verified AI2Apps node", async () => {
  const calls = [];
  const result = await probeNode("http://127.0.0.1:8000", {
    fetchImpl: async (url) => {
      calls.push(url);
      return url.endsWith("/v1/platform/health")
        ? response(200, {
            status: "ok",
            product: "ai2apps",
            version: "0.1.0",
            api_version: "v1",
            runtime: { provider: "omlx" },
            database: { status: "ready" },
          })
        : response(200, { status: "healthy" });
    },
  });

  assert.equal(result.phase, "ready");
  assert.equal(result.productVerified, true);
  assert.equal(result.authRequired, false);
  assert.deepEqual(calls, [
    "http://127.0.0.1:8000/health",
    "http://127.0.0.1:8000/v1/platform/health",
  ]);
});

test("allows the normal login flow only after public health is ready", async () => {
  const result = await probeNode("http://127.0.0.1:8000", {
    fetchImpl: async (url) =>
      url.endsWith("/v1/platform/health")
        ? response(401, { error: { code: "authentication_required" } })
        : response(200, { status: "healthy" }),
  });

  assert.equal(result.phase, "ready");
  assert.equal(result.authRequired, true);
  assert.equal(result.productVerified, false);
});

test("keeps the bootstrap screen while the server is loading", async () => {
  const result = await probeNode("http://127.0.0.1:8000", {
    fetchImpl: async () => response(503, { status: "loading" }),
  });

  assert.equal(result.phase, "starting");
  assert.equal(result.retryable, true);
});
