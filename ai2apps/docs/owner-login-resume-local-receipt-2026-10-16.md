# Owner login resume — Local reliable logout

Cloud contract: OpenAPI 1.71.0 / owner-login-resume-logout-v1.

Local now persists logout proofs through the existing instance-scoped SecretBackend before dropping sessions. Cloud failures retain the outbox and retry with bounded exponential backoff (5–60 seconds). Restarted services read the same protected outbox; pending or unreadable state blocks declarations, resume hints and handoff exchanges. Queue delivery and handoff exchange share a lock. Successful Cloud revoke followed by local acknowledgement failure is safely retried using the idempotent endpoint.

Logout invalidates all local sessions sharing the Cloud browser session and device. The response distinguishes Local logout from Cloud confirmation (`revocationPending`, `cloudConfirmed`). Storage failure preserves the original session and cookie for retry, returns 503, and does not claim success. The web client suppresses automatic recovery as soon as logout is requested and offers retry on failure. No business requests are replayed.

The outbox has no legacy cross-instance migration. Proofs never appear in browser responses, logs or repository files. Existing namespaced Keychain/encrypted-vault implementations supply persistence and protection. Missing credentials or corrupt storage remain fail-closed rather than erasing outstanding revocations.

Capability declaration includes the new reliable-logout field after the outbox barrier passes. The existing READY and SPACE_GATEWAY_READY switches are unchanged. Source currently has both disabled; this receipt does not claim live activation or mobile acceptance. When enabling the target instance through the existing deployment workflow, drain pending logout first, declare capability, then explicitly enter once because Cloud changes capability revision.

Validation includes offline logout/restart/recovery, failed persistence, corrupt outbox, idempotent retry after failed local acknowledgement, concurrent new handoff, and declaration contract. Real Chrome/iPhone Safari/App, background >30 minutes and >8-hour continuity remain unverified.

Test results: 37 Python tests and 13 Owner web tests passed. Dev and App-Dev metadata and last Local import logs point to this checkout; no process restart or production readiness declaration was performed.

## Activation — 2026-10-17

User explicitly requested activation. Enabled the existing Owner Home and space gateway readiness flags. All 37 Owner/self-managed regression tests passed. Waited for Dev active work to finish, then restarted only Dev Local through its standard Helper.

Dev PID 96860, port 52584; App and Helper source metadata and new Local import logs point to the live checkout. Served owner_session.js matches checkout bytes. At 01:54:05 +08:00 Cloud returned owner-login-resume-v1, recorded as `Owner login resume capability confirmed=True`. No Cloud source or database changes were made. App-Dev was not restarted.

The earlier activation-pending note above is superseded. One explicit entry is required to establish continuity after the capability revision change. Real iPhone/Safari/App long-duration acceptance remains pending.
