# Cloud Messager FRP production blocker — 2026-08-23

## Status

The FRP lease race and health/handshake routing were fixed by Cloud commit
`6573e5f` and deployed in image
`ai2apps-cloud:frp-messager-hotfix-v1-20260823T025757Z`. Production retesting
confirms those fixes work. Final E2EE delivery remains blocked by one missing
exact Edge route: `POST /v1/messager/peer/v1/messages`.

This document contains no Connector Secret, Device credential, private key,
registration proof, challenge, compact JWT, message ciphertext, or browser
session value.

## Post-hotfix retest — 2026-08-23 03:06Z

### Fixed and verified

- Both Connectors reach Cloud `Online` without `invalid ping` or
  `invalid NewWorkConn` diagnostics.
- Both public origins return the Local schema-v38 JSON response with HTTP 200
  for exact `GET /v1/platform/health`.
- A fresh A-to-B peer assertion is accepted and the public Noise IK handshake
  reaches B Local:

```text
POST /v1/messager/peer/v1/handshakes HTTP/1.1 201 Created
```

This verifies FRP Login/NewProxy/Ping/NewWorkConn, wildcard Host forwarding,
peer assertion verification, replay consumption, and the first Noise IK flight.

### Remaining blocker

After the successful handshake, the initiator sends the encrypted payload to:

```http
POST /v1/messager/peer/v1/messages
```

The deployed Edge allowlist contains only exact health and handshake routes.
The ciphertext route therefore does not reach B Local. A records the message as
`transport=local_e2ee, status=result_unknown`; B has no corresponding inbound
Local message. The client correctly displays that the encrypted message may
have arrived and does not retry or downgrade it to Cloud.

Cloud must add one more exact Device Edge route, preserving the original Host:

```text
POST /v1/messager/peer/v1/messages
```

All other Local routes should remain denied by the default 404. The route body
is Noise ciphertext plus a short session ID; Edge must not log the request body.

After deployment, reuse the existing Devices, keys, friendship and primary
selection. Send a new clientMessageId rather than retrying the result-unknown
message. Acceptance requires B Local to return encrypted HTTP 200 ack, B to
store one `incoming/local_e2ee/received` row, and A to store one
`outgoing/local_e2ee/sent` row.

## Environment

- Cloud API: `https://coder.ai2apps.com`
- OpenAPI: `1.19.0`
- Local FRP client: stock `frpc 0.62.1`
- Local darwin-arm64 frpc SHA-256:
  `49afde483f55927c3eeac9141cae82857cb2f15b9e9d55f4ac45378e761eabcc`
- Auth protocol: `device-credential-v1`
- Proxy type: FRP HTTP proxy with the Cloud-assigned subdomain
- Local targets: two independent loopback-only AI2Apps Local instances

Test Device A:

- Device ID: `3a4cce68-7458-4f2f-9b83-b1478c8c81b6`
- Public origin:
  `https://device-3f57727efd6c9511af658fceefd99205.ai2apps.com`

Test Device B:

- Device ID: `bfebb83e-fe54-4c13-9888-86cbba821f87`
- Public origin:
  `https://device-2de62bd951ac18fcd885360a12553077.ai2apps.com`

Both test Devices may be revoked after Cloud verification is complete.

## Reproduction

1. Bind two independent Local Installations to two production accounts.
2. Select the current Device as each account's primary Device.
3. Establish friendship between the two users.
4. Register both Ed25519/X25519 Messager Device Key bundles through the
   production challenge and proof flow.
5. Start both Remote connectors from Account.
6. Observe both Local projections become:
   `enabled=1`, `online=1`, `proxy_connected=1`, with fresh heartbeat times.
7. Send an A-to-B Local-first Messager text.
8. Probe either public origin's `/v1/platform/health` endpoint.

## Actual results

### frpc diagnostics

The pinned client logs both of these sanitized diagnostics:

```text
StartWorkConn contains error: invalid NewWorkConn
pong message contains error: invalid ping
```

Login/NewProxy progress far enough for Local and Cloud projections to report
the Device online, but Ping and NewWorkConn are rejected or malformed at the
FRP plugin boundary.

### Public edge probes

Both probes return the production nginx 404 page, not the Local health JSON:

```bash
curl -i https://device-3f57727efd6c9511af658fceefd99205.ai2apps.com/v1/platform/health
curl -i https://device-2de62bd951ac18fcd885360a12553077.ai2apps.com/v1/platform/health
```

Observed for both:

```text
HTTP/2 404
server: nginx/1.15.12
content-type: text/html
```

The request therefore does not reach either Local Uvicorn service.

### Messager behavior

Cloud returns a peer assertion whose peer projection is online, so Local
attempts the Noise IK handshake at the asserted public origin. The handshake
POST receives a non-201 response from the public route and Local returns:

```text
HTTP 502
MESSAGER_LOCAL_HANDSHAKE_REJECTED
The peer rejected the encrypted handshake.
```

This error is intentionally non-retryable. The client preserves the draft and
does not send a Cloud duplicate. Earlier tests with stopped connectors returned
a retryable 503 and correctly used the Cloud offline fallback.

## Expected results

1. A valid Device credential must be accepted for Login, NewProxy, Ping, and
   NewWorkConn using the same authoritative run lease.
2. The wildcard Device hostname must route through the edge to frps' HTTP
   vhost listener and then to the registered Local HTTP proxy.
3. `GET <device-origin>/v1/platform/health` must return the Local JSON response
   with HTTP 200, not an nginx page.
4. A valid Messager handshake POST must reach
   `/v1/messager/peer/v1/handshakes` on the recipient Local instance.
5. Cloud must not project `online=true` for a Device that cannot establish
   authenticated work connections.

## Cloud investigation points

### FRP Auth Plugin / sidecar

- Capture sanitized accept/reject metrics for `Ping` and `NewWorkConn` for the
  two Device IDs above.
- Compare the actual stock FRP 0.62.1 plugin request body with the parser used
  by the sidecar/Cloud internal endpoint.
- Verify `run_id` extraction for both top-level content and nested
  `content.user.run_id`; do not assume fields that stock 0.62.1 omits or shapes
  differently.
- Verify NewProxy creates the authoritative lease before the first Ping or
  NewWorkConn can be evaluated.
- Verify the plugin returns the exact FRP response envelope expected by 0.62.1,
  not merely an internal API success object.
- Confirm no old-run lease from a previous test Device session is rejecting the
  current run.

### Edge / frps HTTP vhost

- Verify wildcard `device-*.ai2apps.com` host routing reaches the frps HTTP
  vhost port rather than the default nginx 404 server.
- Verify TLS termination preserves the original Host header required for FRP
  subdomain routing.
- Verify the Cloud-assigned subdomain is present in the active NewProxy
  registration and matches the Device record exactly.

### Presence projection

- Do not mark a Device usable merely because Login or NewProxy was accepted.
- Require an accepted current-run heartbeat and a usable proxy/work-connection
  state before returning `online=true` in Messager peer assertions.
- Expire or clear the projection promptly after Ping/NewWorkConn rejection.

## Acceptance checks after the fix

1. Both public health probes return Local HTTP 200 JSON.
2. No `invalid ping` or `invalid NewWorkConn` diagnostic appears for at least
   two heartbeat intervals.
3. A-to-B and B-to-A text messages complete with `transport=local_e2ee`.
4. Recipient Local storage contains the inbound plaintext; Cloud storage,
   logs, audit, and metrics contain no plaintext, Noise payload, proof, private
   key, or compact assertion.
5. Stop B's connector and verify A gets retryable Local-unavailable behavior
   followed by exactly one Cloud offline message.
6. Restore B, rotate one Messager key, and confirm a fresh assertion and Noise
   handshake succeed without stale-key reuse.

## Production resolution and client acceptance

Cloud deployed the FRP lease-race fix (`6573e5f`, deployment `08488b7`) and
the exact ciphertext route (`6fbc974`, deployment `9404136`) on 2026-08-23.
The client acceptance run then produced the following results:

- Both public Device health endpoints returned the Local schema-v38 health
  document with HTTP 200.
- No `invalid ping` or `invalid NewWorkConn` diagnostic appeared after the
  connectors were restarted.
- A-to-B message `2a17b9c3-5348-4d7b-960d-b43b7980e819` was stored as
  `outgoing/local_e2ee/sent` on A and `incoming/local_e2ee/received` on B.
- B-to-A message `d50b2e4a-f05d-428a-96d7-e53145064e52` was stored as
  `outgoing/local_e2ee/sent` on B and `incoming/local_e2ee/received` on A.
- Recipient logs recorded handshake HTTP 201 and ciphertext-message HTTP 200;
  sender logs recorded the Local send HTTP 200 in both directions.
- After B's connector was stopped and its presence expired, A's Local send
  returned retryable HTTP 503 and exactly one Cloud offline POST returned HTTP
  201. Message `a1552b79-7dc4-4b47-a770-4013301e859e` appears exactly once as
  `outgoing/cloud_offline/sent` on A and once as
  `incoming/cloud_offline/received` on B.
- B's connector was restored and its public health endpoint again returned
  HTTP 200.
- B then rotated both its Ed25519 identity key and X25519 static-DH key. The
  append-only Local audit event proves both fingerprints changed. A subsequent
  A-to-B exchange obtained a fresh assertion, completed a new Noise IK
  handshake with HTTP 201, delivered ciphertext with HTTP 200, and stored
  message `c91ac0a6-bdfb-4ae2-a571-ac7b43e55022` exactly once as
  `outgoing/local_e2ee/sent` on A and `incoming/local_e2ee/received` on B.
  The recipient's fingerprint-binding checks make the successful handshake
  evidence that the assertion used the current key rather than the stale key.

Checks 1, 2, 3, 5, and 6 are complete. The Local side of check 4 is complete;
Cloud-side storage/log/audit inspection remains a Cloud operational check.
