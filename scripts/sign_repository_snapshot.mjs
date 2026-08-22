#!/usr/bin/env node
/** Sign a prepared repository payload without exporting the private key. */

import { createHash, createPrivateKey, createPublicKey, sign } from "node:crypto";
import { readFile, rename, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";

const localRequire = createRequire(import.meta.url);
let canonicalize;
try {
  ({ canonicalize } = localRequire("json-canonicalize"));
} catch (error) {
  if (error?.code !== "MODULE_NOT_FOUND") throw error;
  ({ canonicalize } = createRequire("/app/package.json")("json-canonicalize"));
}
const PREFIX = Buffer.from("AI2APPS-REPOSITORY-SNAPSHOT-V1\n", "ascii");

function argument(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) {
    throw new Error(`missing required argument: ${name}`);
  }
  return process.argv[index + 1];
}

async function atomicJson(path, value) {
  const temporary = `${path}.${process.pid}.tmp`;
  await writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, {
    encoding: "utf8",
    mode: 0o644,
  });
  await rename(temporary, path);
}

const inputPath = argument("--input");
const privateKeyPath = argument("--private-key");
const catalogPath = argument("--catalog");
const publicKeyPath = argument("--repository-key");
const expectedFingerprint = argument("--expected-fingerprint").replace(/^sha256:/, "");
const expiresDays = Number.parseInt(argument("--expires-days"), 10);
if (!Number.isSafeInteger(expiresDays) || expiresDays < 1 || expiresDays > 90) {
  throw new Error("expires-days must be an integer from 1 to 90");
}

const input = JSON.parse(await readFile(inputPath, "utf8"));
const payload = structuredClone(input?.payload ?? input);
if (
  payload?.domain !== "ai2apps.repository-snapshot.v1"
  || !Number.isSafeInteger(payload.version)
  || payload.version < 1
  || !Array.isArray(payload.releases)
) {
  throw new Error("repository payload is invalid");
}
const generatedAt = new Date();
payload.generatedAt = generatedAt.toISOString();
payload.expiresAt = new Date(
  generatedAt.getTime() + expiresDays * 24 * 60 * 60 * 1000,
).toISOString();

const privateKey = createPrivateKey(await readFile(privateKeyPath, "utf8"));
if (privateKey.asymmetricKeyType !== "ed25519") {
  throw new Error("repository signing key must be Ed25519");
}
const publicKey = createPublicKey(privateKey);
const publicKeyPem = publicKey.export({ type: "spki", format: "pem" }).toString();
const fingerprint = createHash("sha256")
  .update(publicKey.export({ type: "spki", format: "der" }))
  .digest("hex");
if (fingerprint !== expectedFingerprint) {
  throw new Error("repository signing key does not match the pinned fingerprint");
}

const signedBytes = Buffer.concat([
  PREFIX,
  Buffer.from(canonicalize(payload), "utf8"),
]);
const envelope = {
  schemaVersion: "ai2apps.repository-snapshot-envelope.v1",
  payload,
  signature: {
    keyId: fingerprint,
    algorithm: "Ed25519",
    value: sign(null, signedBytes, privateKey).toString("base64url"),
  },
};

await atomicJson(publicKeyPath, { publicKeyPem });
await atomicJson(catalogPath, envelope);
console.log(JSON.stringify({ fingerprint, version: payload.version }));
