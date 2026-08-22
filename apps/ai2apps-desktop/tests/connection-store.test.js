"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  ConnectionStore,
  DEFAULT_CONNECTION_ID,
} = require("../src/main/connection-store");

function fixture() {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "ai2apps-connections-"));
  const filename = path.join(directory, "connections.json");
  let tick = 0;
  const options = {
    clock: () => new Date(Date.UTC(2026, 7, 16, 0, 0, tick++)),
    randomId: () => "test-id",
  };
  return {
    directory,
    filename,
    options,
    cleanup: () => fs.rmSync(directory, { recursive: true, force: true }),
  };
}

test("creates a default local connection without touching the server", (context) => {
  const value = fixture();
  context.after(value.cleanup);
  const store = new ConnectionStore(value.filename, value.options);

  assert.deepEqual(store.active(), {
    id: DEFAULT_CONNECTION_ID,
    name: "This Mac",
    url: "http://127.0.0.1:8000/",
    kind: "existing-local",
    trustState: "local",
    createdAt: "2026-08-16T00:00:00.000Z",
    updatedAt: "2026-08-16T00:00:00.000Z",
    lastUsedAt: null,
  });
  assert.equal(fs.existsSync(value.filename), false);
});

test("persists a user-added HTTPS remote connection with no credentials", (context) => {
  const value = fixture();
  context.after(value.cleanup);
  const store = new ConnectionStore(value.filename, value.options);
  const added = store.add({ name: "Spark", url: "https://spark.example.test" });

  assert.equal(added.kind, "remote");
  assert.equal(added.trustState, "user-added");
  assert.equal(store.active().url, "https://spark.example.test/");
  const serialized = fs.readFileSync(value.filename, "utf8");
  assert.doesNotMatch(serialized, /credential|password|secret/i);

  const reopened = new ConnectionStore(value.filename, value.options);
  assert.equal(reopened.active().name, "Spark");
});

test("rejects insecure remote URLs before writing the store", (context) => {
  const value = fixture();
  context.after(value.cleanup);
  const store = new ConnectionStore(value.filename, value.options);

  assert.throws(
    () => store.add({ name: "Unsafe", url: "http://spark.example.test" }),
    /must use HTTPS/,
  );
  assert.equal(fs.existsSync(value.filename), false);
});

test("removing the active remote connection falls back to the default local node", (context) => {
  const value = fixture();
  context.after(value.cleanup);
  const store = new ConnectionStore(value.filename, value.options);
  const added = store.add({ name: "Spark", url: "https://spark.example.test" });
  store.remove(added.id);

  assert.equal(store.active().id, DEFAULT_CONNECTION_ID);
  assert.throws(() => store.remove(DEFAULT_CONNECTION_ID), /cannot be removed/);
});
