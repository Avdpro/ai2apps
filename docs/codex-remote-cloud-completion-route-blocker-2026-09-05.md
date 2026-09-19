# Codex Remote production completion-route blocker

Status: client integration blocker found during the 2026-09-05 production handoff review.

## Observable mismatch

The Cloud implementation returns the pairing assertion to:

```text
https://device-<32 hex>.ai2apps.com/codex-remote/complete#assertion=...
```

However, the production Edge `device-*` virtual host only forwards `/mobile/*`, `/v1/mobile/*`, and the existing narrowly allowlisted Device APIs. It has no `/codex-remote/complete` location and ends with `location / { return 404; }`.

The dedicated Codex Remote virtual host does forward `/codex-remote/*`, but its origin is allocated only by the proxy lease:

```text
https://codex-<36 hex>.ai2apps.com
```

Therefore a real browser cannot deliver the 120-second assertion to the local plugin using the current redirect URL.

## Required Cloud correction

Prefer changing confirmation so it resolves the active, unexpired proxy lease for the same Bridge/Device and returns:

```text
https://codex-<lease public slug>.ai2apps.com/codex-remote/complete#assertion=...
```

The confirmation transaction must fail closed when no matching active lease exists. It must bind the selected lease to the same Bridge, Device, Installation, account, Device epoch and Bridge epoch already validated for the grant. Do not accept a client-supplied redirect or public origin.

Alternative: add an exact `/codex-remote/complete` route to the `device-*` Edge and implement a trusted Local forward from the existing Mobile Gateway to `127.0.0.1:47133`. This is less desirable because it introduces an AI2Apps Desktop/Local change and couples the personal plugin to the existing Device FRPC.

## Acceptance

1. Confirmation with an active matching Codex lease returns its Cloud-assigned `codex-*` origin.
2. Missing, expired, revoked, wrong-Bridge, wrong-Device, wrong-Installation, or wrong-epoch lease fails generically.
3. The returned assertion still appears only in the URL fragment and retains the current 120-second maximum lifetime.
4. The `codex-*` Edge forwards the completion page to `127.0.0.1:47133`; neither Edge nor application logs contain the assertion or fragment.
5. No caller-controlled redirect, host, subdomain, proxy name, local address, or port is accepted.
