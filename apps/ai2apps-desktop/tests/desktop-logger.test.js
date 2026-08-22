"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { redact } = require("../src/main/desktop-logger");

test("redacts bearer credentials and common secret fields", () => {
  const value = redact(
    "Authorization: Bearer abc123 api_key=key-value token:ticket-value safe=value",
  );
  assert.doesNotMatch(value, /abc123|key-value|ticket-value/);
  assert.match(value, /safe=value/);
});
