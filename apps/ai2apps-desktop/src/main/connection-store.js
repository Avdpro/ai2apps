"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const {
  DEFAULT_NODE_URL,
  isLoopbackHostname,
  normalizeNodeUrl,
} = require("./node-connection");

const STORE_VERSION = 1;
const DEFAULT_CONNECTION_ID = "local-default";

function nowIso(clock) {
  return clock().toISOString();
}

function cleanName(value) {
  const name = String(value || "").trim();
  if (!name || name.length > 120) {
    throw new Error("Connection name must contain 1 to 120 characters.");
  }
  return name;
}

function kindForUrl(url) {
  return isLoopbackHostname(new URL(url).hostname) ? "existing-local" : "remote";
}

function publicConnection(value) {
  return {
    id: value.id,
    name: value.name,
    url: value.url,
    kind: value.kind,
    trustState: value.trustState,
    createdAt: value.createdAt,
    updatedAt: value.updatedAt,
    lastUsedAt: value.lastUsedAt,
  };
}

function defaultConnection(clock) {
  const timestamp = nowIso(clock);
  return {
    id: DEFAULT_CONNECTION_ID,
    name: "This Mac",
    url: DEFAULT_NODE_URL,
    kind: "existing-local",
    trustState: "local",
    createdAt: timestamp,
    updatedAt: timestamp,
    lastUsedAt: null,
  };
}

class ConnectionStore {
  constructor(filename, options = {}) {
    this.filename = path.resolve(filename);
    this.clock = options.clock || (() => new Date());
    this.randomId = options.randomId || (() => crypto.randomUUID());
    this.state = this.#load();
  }

  #load() {
    let raw;
    try {
      raw = JSON.parse(fs.readFileSync(this.filename, "utf8"));
    } catch (error) {
      if (error.code !== "ENOENT" && !(error instanceof SyntaxError)) {
        throw error;
      }
      const connection = defaultConnection(this.clock);
      return {
        version: STORE_VERSION,
        activeConnectionId: connection.id,
        connections: [connection],
      };
    }

    if (raw?.version !== STORE_VERSION || !Array.isArray(raw.connections)) {
      throw new Error("Unsupported Desktop connection store format.");
    }

    const seen = new Set();
    const connections = raw.connections.map((item) => {
      const id = String(item?.id || "");
      if (!id || seen.has(id)) {
        throw new Error("Desktop connection store contains an invalid ID.");
      }
      seen.add(id);
      const url = normalizeNodeUrl(item.url);
      const kind = kindForUrl(url);
      return {
        id,
        name: cleanName(item.name),
        url,
        kind,
        trustState: kind === "existing-local" ? "local" : "user-added",
        createdAt: String(item.createdAt || nowIso(this.clock)),
        updatedAt: String(item.updatedAt || nowIso(this.clock)),
        lastUsedAt: item.lastUsedAt ? String(item.lastUsedAt) : null,
      };
    });

    if (!connections.some((item) => item.id === DEFAULT_CONNECTION_ID)) {
      connections.unshift(defaultConnection(this.clock));
    }
    const requestedActive = String(raw.activeConnectionId || "");
    const activeConnectionId = connections.some((item) => item.id === requestedActive)
      ? requestedActive
      : DEFAULT_CONNECTION_ID;
    return { version: STORE_VERSION, activeConnectionId, connections };
  }

  #save() {
    fs.mkdirSync(path.dirname(this.filename), { recursive: true });
    const temporary = `${this.filename}.tmp-${process.pid}-${crypto.randomBytes(4).toString("hex")}`;
    const serialized = `${JSON.stringify(this.state, null, 2)}\n`;
    try {
      fs.writeFileSync(temporary, serialized, { encoding: "utf8", mode: 0o600 });
      fs.renameSync(temporary, this.filename);
      try {
        fs.chmodSync(this.filename, 0o600);
      } catch {
        // Windows and some managed filesystems do not implement POSIX modes.
      }
    } finally {
      try {
        fs.unlinkSync(temporary);
      } catch (error) {
        if (error.code !== "ENOENT") {
          throw error;
        }
      }
    }
  }

  snapshot() {
    return {
      version: this.state.version,
      activeConnectionId: this.state.activeConnectionId,
      connections: this.state.connections.map(publicConnection),
    };
  }

  active() {
    const connection = this.state.connections.find(
      (item) => item.id === this.state.activeConnectionId,
    );
    return publicConnection(connection || this.state.connections[0]);
  }

  add(input) {
    const name = cleanName(input?.name);
    const url = normalizeNodeUrl(input?.url);
    const existing = this.state.connections.find((item) => item.url === url);
    const timestamp = nowIso(this.clock);
    if (existing) {
      existing.name = name;
      existing.updatedAt = timestamp;
      this.state.activeConnectionId = existing.id;
      this.#save();
      return publicConnection(existing);
    }

    const kind = kindForUrl(url);
    const connection = {
      id: `connection-${this.randomId()}`,
      name,
      url,
      kind,
      trustState: kind === "existing-local" ? "local" : "user-added",
      createdAt: timestamp,
      updatedAt: timestamp,
      lastUsedAt: null,
    };
    this.state.connections.push(connection);
    this.state.activeConnectionId = connection.id;
    this.#save();
    return publicConnection(connection);
  }

  select(connectionId) {
    const connection = this.state.connections.find((item) => item.id === connectionId);
    if (!connection) {
      throw new Error("Desktop connection was not found.");
    }
    this.state.activeConnectionId = connection.id;
    connection.lastUsedAt = nowIso(this.clock);
    connection.updatedAt = connection.lastUsedAt;
    this.#save();
    return publicConnection(connection);
  }

  remove(connectionId) {
    if (connectionId === DEFAULT_CONNECTION_ID) {
      throw new Error("The default local connection cannot be removed.");
    }
    const index = this.state.connections.findIndex((item) => item.id === connectionId);
    if (index < 0) {
      throw new Error("Desktop connection was not found.");
    }
    const [removed] = this.state.connections.splice(index, 1);
    if (this.state.activeConnectionId === connectionId) {
      this.state.activeConnectionId = DEFAULT_CONNECTION_ID;
    }
    this.#save();
    return publicConnection(removed);
  }
}

module.exports = {
  ConnectionStore,
  DEFAULT_CONNECTION_ID,
  STORE_VERSION,
};
