# P3 native rendering leases

`acefox-rendering-leases.patch` is an additive patch against the AI2Apps AceFox
checkout (Firefox 153), preserving its existing changes. Apply with `patch -p1
--forward` after a dry run, then build with `./mach build`. Do not reset that
checkout or copy an entire diff containing unrelated work. The native tests read
that checkout: `node ai2apps/browser/native_rendering/test_protocol.mjs <acefox-root>`.
Use the standard fixed App-Dev builder to package the resulting Acefox.app.

## Protected BiDi extension, version 1

All commands remain on the authenticated native BiDi session and transparent
Gateway. Only `shell`/`agent` native processes support them; content cannot call
internal root methods. Existing context/Profile and executor access checks remain
mandatory. Task/holder metadata provides attribution, never authority.

- `browsingContext.getRenderingLeaseCapabilities {context}` reports version,
  scope, purposes, TTL limit, cleanup and existing permanent safeguard status.
- `acquireRenderingLease {context,purpose,holder,ttlMs}` requires a top-level
  navigable, purpose layout/capture/input, holder <=128 characters, TTL 100–60000ms.
  Returns opaque lease, expiry and actual window scope/reference count.
- `renewRenderingLease {context,lease}` extends an active lease by at most 60s.
- `releaseRenderingLease {context,lease}` is idempotent and rejects mismatched
  contexts. Only the connection that acquired a lease can renew/release it.
- `getRenderingLeaseState {context}` reports native window/context counts for
  diagnostics. It returns no content or credentials.

The real macOS widget counter participates in DispatchOcclusionEvent and
recomputes on both acquisition and release, without restoring/selecting/focusing
windows. This is window scope, not page scope; tabs sharing a window share its
rendering conditions. It does not change document.visibilityState or CSS, and
cannot promise readiness of a minimized/hidden/unselected tab. Existing bounded
input preparation and screenshot failure handling remain in force.

SDK same-task/context/purpose nesting shares a native handle. Other purposes or
holders get separate native references. Screenshot concurrency is independently
bounded to two per host; Profile input serialization is unchanged, and ordinary
content reading has no rendering quota or lease. Screenshot leases end before
model inference. Long native input leases renew every 20s. Known leases release
in finally and graceful detach; native socket close releases only that socket's
leases, including acquire/close races. Context destruction and session teardown
release native references. TTL also covers process failure and lost acquire or
release responses. An unconfirmed release is logged as such, never as success;
no browser effect is replayed to recover a lease.

Existing AI2APPS_BACKGROUND_HOST/agent overrides remain enabled. Thus releasing a
lease removes its native reference but does not yet restore default occlusion
throttling in these hosts. P4 must measure and validate replacement before these
safeguards can be removed. Unsupported legacy hosts explicitly report SDK
fallback to the existing policy; they are not reported as native leased hosts.

## P4 measurement diagnostics

`acefox-rendering-diagnostics.patch` applies after the P3 lease patch. It adds
read-only `nativeOccluded` and `chromeCompositorPaused` fields to the existing
`getRenderingLeaseState` response, using window utilities. The compositor field
describes the chrome window, not per-tab GPU attribution. No new command,
permission, input or rendering policy is introduced. The native protocol test
also checks these fields. This diagnostic build was tested in isolated native
processes only and has not replaced either fixed development App.

The [P4 comparison](../../docs/acceptance/webagent-rendering-performance-20261027/README.md)
shows lower retained-animation idle costs, but its memory-growth gate failed.
Full acceptance is held; BACKGROUND_HOST/agent safeguards remain enabled.
