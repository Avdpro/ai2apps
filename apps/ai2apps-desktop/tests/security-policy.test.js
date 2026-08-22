"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  classifyNavigation,
  isAllowedExternalUrl,
  isTrustedIpcSender,
  isTrustedNodeUrl,
} = require("../src/main/security-policy");

const nodeUrl = "http://127.0.0.1:8000/";
const bootstrapUrl = "file:///app/bootstrap/index.html";

test("trusts only the configured node origin", () => {
  assert.equal(isTrustedNodeUrl("http://127.0.0.1:8000/apps/chat", nodeUrl), true);
  assert.equal(isTrustedNodeUrl("blob:http://127.0.0.1:8000/asset", nodeUrl), true);
  assert.equal(isTrustedNodeUrl("http://127.0.0.1:9000/apps/chat", nodeUrl), false);
  assert.equal(isTrustedNodeUrl("https://example.test/", nodeUrl), false);
});

test("classifies node, bootstrap, external, and blocked navigation", () => {
  assert.equal(classifyNavigation(bootstrapUrl, nodeUrl, bootstrapUrl), "bootstrap");
  assert.equal(
    classifyNavigation("http://127.0.0.1:8000/admin", nodeUrl, bootstrapUrl),
    "trusted-node",
  );
  assert.equal(
    classifyNavigation("https://accounts.example.test/login", nodeUrl, bootstrapUrl),
    "external",
  );
  assert.equal(classifyNavigation("javascript:alert(1)", nodeUrl, bootstrapUrl), "blocked");
});

test("allows a narrow set of system-browser protocols", () => {
  assert.equal(isAllowedExternalUrl("https://example.test"), true);
  assert.equal(isAllowedExternalUrl("mailto:support@example.test"), true);
  assert.equal(isAllowedExternalUrl("file:///etc/passwd"), false);
  assert.equal(isAllowedExternalUrl("custom-handler:payload"), false);
});

test("IPC is accepted only from bootstrap or the trusted node", () => {
  assert.equal(isTrustedIpcSender(bootstrapUrl, nodeUrl, bootstrapUrl), true);
  assert.equal(isTrustedIpcSender("http://127.0.0.1:8000/", nodeUrl, bootstrapUrl), true);
  assert.equal(isTrustedIpcSender("https://example.test/", nodeUrl, bootstrapUrl), false);
});
