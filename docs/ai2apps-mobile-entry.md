# AI2Apps Mobile Entry Design

Status: Local Mobile Shell implementation active; FRP integration pending
Last updated: 2026-08-14
Scope: AI2Apps Mac/client runtime and WebUI; cloud/FRP server implementation is out of scope

## 1. Purpose

AI2Apps needs a dedicated mobile WebUI surface that can be reached through the
future authenticated FRP remote-access path. The mobile surface is not a
responsive copy of the desktop shell and it must not expose every installed
App automatically.

An App explicitly declares whether it is **Mobile Ready**. For a Mobile Ready
App, the runtime selects the best available UI definition in this order:

```text
Mobile-Entry -> Mini-Entry -> App-Entry
```

This keeps mobile eligibility separate from UI implementation. An App can ship
a purpose-built phone interface, reuse its compact Mini-Entry, or deliberately
reuse its normal Entry.

## 2. Product decisions

1. AI2Apps WebUI provides a dedicated `/mobile` shell.
2. Only Apps with `mobile.ready: true` appear in the Mobile App Catalog.
3. Mobile readiness is explicit and fail-closed. Existing Apps remain hidden
   until their manifests are updated.
4. Entry selection uses the fixed fallback order Mobile-Entry, Mini-Entry,
   App-Entry.
5. `mini_entry.placements` continues to describe conversational desktop
   placement (`inline` and `sidebar`). Mobile eligibility is not encoded in
   that list.
6. All selected entries reuse the same AppInstance, sessions, persistent
   state, Runs, capability grants, Service bindings, and artifacts.
7. Remote-access subscription/entitlement is enforced by the cloud and local
   remote-session boundary. It is separate from whether an App is Mobile
   Ready.
8. System mobile pages such as pairing, connection status, account, and trust
   recovery may be implemented directly by the Mobile Shell rather than as
   third-party App entries.

## 3. App manifest contract

### 3.1 Minimal Mobile Ready App

An App can opt in without adding a new UI resource:

```yaml
schema: ai2apps.app/v1
id: com.example.notes
name: Notes

mobile:
  ready: true

entry:
  kind: sandbox
  resource: ui/entry.html
```

Because neither `mobile_entry` nor `mini_entry` exists, Mobile uses `entry`.
The App publisher is explicitly asserting that the normal Entry is usable on a
phone.

### 3.2 App reusing Mini-Entry

```yaml
schema: ai2apps.app/v1
id: com.example.tasks
name: Tasks

mobile:
  ready: true

entry:
  kind: sandbox
  resource: ui/entry.html

mini_entry:
  kind: schema
  resource: ui/mini.json
  placements:
    - inline
    - sidebar
```

Mobile uses `mini_entry` and renders it in a full-height mobile container.
The `placements` list still governs ConversationSession mounts; it does not
need a `mobile` value.

### 3.3 App with a dedicated Mobile-Entry

```yaml
schema: ai2apps.app/v1
id: com.example.dashboard
name: Dashboard

mobile:
  ready: true

entry:
  kind: sandbox
  resource: ui/entry.html

mini_entry:
  kind: schema
  resource: ui/mini.json
  placements:
    - inline
    - sidebar

mobile_entry:
  kind: sandbox
  resource: ui/mobile.html
```

Mobile always selects `mobile_entry` when it is present and valid.

### 3.4 Validation rules

- `mobile` is optional. Missing `mobile` is equivalent to
  `mobile.ready: false`.
- `mobile.ready` must be a Boolean.
- `mobile_entry` is allowed only on an App manifest.
- `mobile_entry` must use a supported renderer and reference an indexed package
  resource when the renderer requires a resource.
- A manifest with `mobile.ready: true` must resolve to at least one valid entry.
- `mobile_entry` does not make an App Mobile Ready by itself. Requiring the
  explicit flag prevents accidental publication.
- A broken higher-priority entry is a package validation error. Runtime launch
  must not silently skip a declared but invalid `mobile_entry` and fall back to
  a different UI.
- Package verification, signature, trust, dependency, and permission checks are
  unchanged.

### 3.5 Mobile Web resource contract

Declaring `mobile.ready: true` also asserts that the selected entry works
through the public Mobile gateway's restrictive CSP and route allowlist.

- A packaged `sandbox` entry must index every CSS, JavaScript, font, image, and
  other resource in the package and reference it with a relative URL.
- Packaged Apps must not reference `/admin/static/*`, `/mobile/static/*`,
  localhost URLs, arbitrary local ports, or external CDNs. `/mobile/static/*`
  is reserved for explicitly allowlisted built-in Mobile Shell/system assets.
- Mobile entries must not depend on inline `<style>`, inline `<script>`, inline
  event handlers, `eval`, or dynamic code generation. External indexed assets
  are the portable CSP-safe form.
- App code must use the constrained Mobile Bridge or documented
  `/v1/mobile/*` endpoints. It must not call `/admin/*`, unrestricted
  `/v1/platform/*`, arbitrary local Services, or receive the local API key.
- Servers must return correct MIME types for CSS, JavaScript, JSON, fonts, SVG,
  and raster images while `X-Content-Type-Options: nosniff` is active.

Built-in `host` system Apps are the narrow exception: they must extend the
Mobile App base template, map every dependency through the exact Mobile static
allowlist, and render without `/admin/static/*` references or CSP-dependent
inline CSS and JavaScript.

## 4. Entry resolution

The runtime owns a single deterministic resolver:

```python
def resolve_mobile_entry(manifest):
    if manifest.get("mobile", {}).get("ready") is not True:
        return None
    if manifest.get("mobile_entry") is not None:
        return ("mobile_entry", manifest["mobile_entry"])
    if manifest.get("mini_entry") is not None:
        return ("mini_entry", manifest["mini_entry"])
    if manifest.get("entry") is not None:
        return ("entry", manifest["entry"])
    raise InvalidMobileApp("Mobile Ready App has no usable Entry")
```

The resolver must be shared by package validation, Mobile Catalog generation,
launch, restore, and tests so those paths cannot disagree.

The selected source (`mobile_entry`, `mini_entry`, or `entry`) is returned in
the launch payload and audit event. A mobile mount has `placement: mobile`
regardless of which source was selected. Mobile launch should use a general
entry resolver rather than pretending that every mobile mount is a Mini-Entry
mount.

## 5. Mobile App Catalog

The Mobile Shell consumes a dedicated catalog instead of filtering the desktop
catalog in browser JavaScript.

An App is included only when all of the following are true:

- its effective definition is active;
- its package is installed and passes the applicable trust policy;
- `mobile.ready` is exactly `true`;
- the mobile resolver returns a valid entry;
- the current remote session is authorized to see and launch it.

Each catalog item should contain only presentation and launch metadata needed
by Mobile:

```json
{
  "app_id": "com.example.tasks",
  "display_name": "Tasks",
  "icon": "...",
  "entry_source": "mini_entry",
  "renderer": "schema",
  "instance_policy": "singleton",
  "running": true
}
```

The catalog must not send package filesystem paths, local service credentials,
capability tokens, or desktop-only navigation targets to the browser.

## 6. Mount and lifecycle behavior

Mobile reuses the existing AppInstance lifecycle:

1. The Mobile Shell launches or focuses an AppInstance according to its
   instance policy.
2. The runtime resolves the mobile entry.
3. It creates a durable App mount with `placement: mobile` and records the
   selected `entry_source`.
4. The existing renderer loads the selected resource.
5. Closing the mobile View unmounts it but does not destroy the AppInstance,
   HomeSession, active Runs, state, or artifacts.
6. Reconnection restores authorized mobile mounts after revalidating the
   remote session, App state, package trust, and entitlement.

Mobile mounts are not required to belong to a ConversationSession. When a
Mobile Entry is opened from a conversation, `interaction_session_id` may be
attached so the App receives the relevant conversation context.

Suggested audit events are:

```text
app.mobile_entry.mount
app.mobile_entry.restore
app.mobile_entry.unmount
app.mobile_entry.denied
```

Each event should include the AppInstance ID, mount ID, selected entry source,
renderer, remote device/session identity, and denial reason where applicable.

## 7. Renderer and bridge policy

### 7.1 Renderer policy

Mobile reuses the existing `schema`, `safe-html`, and `sandbox` renderers.

- `schema` is the preferred renderer for compact, structured Mobile UI.
- `safe-html` remains sanitized and scriptless.
- `sandbox` runs with the existing restrictive iframe/CSP boundary and calls
  host functions through the controlled bridge.
- `host` is permitted on Mobile only for explicitly allowlisted, built-in
  system Apps. Third-party `host` resources are rejected.

The same policy applies after fallback. Declaring an App Mobile Ready does not
turn a third-party `host` App-Entry into a remotely accessible host component.

### 7.2 Mobile Bridge

The Mobile Bridge is a constrained surface over the existing Shell Bridge. It
may expose operations such as:

- read and update App state;
- create or observe authorized AgentRuns;
- request capabilities through the normal policy engine;
- open and export App artifacts;
- mount another Mobile Ready App when policy permits;
- update title, badge, navigation, and close state.

It must not expose unrestricted local URLs, filesystem paths, shell execution,
Terminal, desktop administration pages, raw Service credentials, FRP control
credentials, or the desktop Shell's complete navigation API.

Capability grants remain scoped, auditable, revocable, and bound to the App,
AppInstance, user/device remote session, and requested operation.

## 8. Mobile Shell behavior

The initial `/mobile` shell should provide:

- authenticated connection and device state;
- a Mobile App Catalog/home screen;
- App launch, back, close, reconnect, and recovery navigation;
- phone viewport and safe-area handling;
- full-height scrolling for Mini-Entry fallback;
- virtual-keyboard resize handling;
- portrait-first responsive layout with usable landscape behavior;
- loading, offline, Mac unavailable, tunnel expired, entitlement denied,
  permission denied, and App incompatible states;
- no links that escape into the desktop `/admin` shell.

Fallback to App-Entry is a compatibility mechanism, not automatic responsive
conversion. The App publisher owns the assertion made by `mobile.ready: true`.
The Mobile Shell supplies the container, viewport, navigation chrome, and error
recovery but does not rewrite an App's desktop layout.

## 9. Remote-access boundary

The FRP system transports the authenticated Mobile session to the Mac; it does
not decide which Apps are Mobile Ready or which Entry is selected.

The expected request path is:

```text
Phone browser
  -> https://device-<32 hex slug>.ai2apps.com
  -> wildcard edge route allowlist
  -> authorized FRP tunnel
  -> local Mobile gateway on the Mac
  -> Mobile Catalog / mobile mount / constrained App APIs
```

Remote access must terminate at a narrow local Mobile gateway. It must not
publish the complete local admin server or arbitrary localhost ports through
FRP. The gateway revalidates the signed remote session and applies local App,
capability, trust, and audit policy even if the cloud has already authenticated
the user.

Cloud enforces `remote.connect` at device creation, relay admission and handoff
exchange. The Mobile Gateway accepts only an EdDSA token with issuer
`ai2apps-cloud`, audience `ai2apps-remote-mobile-v1`, its exact device ID and
current `access_epoch`. The Cloud token lasts at most five minutes, the local
HttpOnly session lasts at most 15 minutes, and the Gateway fails closed after
60 seconds without a successful access-epoch check.

## 10. Required implementation changes

The current runtime supports Entry and conversational Mini-Entry mounts with
`entry`, `inline`, and `sidebar` placements. Mobile implementation will require
at least:

1. extend App manifest parsing and archive validation for `mobile` and
   `mobile_entry`;
2. add the shared mobile entry resolver;
3. add `mobile` to the durable mount placement schema and migration;
4. preserve and return `entry_source` for mobile mounts;
5. add Mobile Catalog and mobile launch/focus/mount/restore endpoints;
6. add `app.mobile_entry.*` audit events;
7. build the `/mobile` shell and renderer containers;
8. add a constrained Mobile Bridge and remote-session middleware;
9. add built-in Mobile Shell pages for connection, pairing, account, and trust
   recovery;
10. update App Studio/package tooling to edit, preview, validate, and test
    Mobile Ready declarations and Mobile-Entry resources.

The existing generic Mini-Entry launcher must not make an App Mobile Ready and
must never be used to bypass the resolver's explicit opt-in rule.

## 11. Delivery sequence

Manifest/runtime work and the local `/mobile` Shell can be developed and tested
over the same Wi-Fi independently of FRP. External-network integration begins
after the FRP contract is stable enough to provide authenticated device/session
identity and a local Mobile gateway handoff.

### Current implementation snapshot — 2026-08-14

- added explicit `mobile.ready` and optional `mobile_entry` validation;
- implemented deterministic Mobile-Entry, Mini-Entry, App-Entry resolution;
- added durable `mobile` mounts and entry-source persistence;
- added the Mobile App Catalog and open/focus/restore endpoints;
- added the local `/mobile` Shell with Home, Dock, Launcher, App Switcher, and
  a bounded warm-frame pool;
- marked Dashboard, Account, Agents, Chat, and Trust Center Mobile Ready;
- kept Terminal, Coder, Models, and other desktop-only Apps out of Mobile;
- left remote-session middleware and FRP handoff for Phase M3.

### Phase M0 — FRP contract (completed 2026-08-14)

- Cloud OpenAPI 1.3.0 and `remote-access-client-integration-v1.md` fix the
  device, pairing, handoff, JWT, JWKS, revoke and usage contracts;
- FRP 0.62.1 is pinned with authenticated TLS and a fixed loopback target;
- device credentials use `Authorization: Device <deviceId>.<connectorSecret>`;
- entitlement, 60-second revocation, expiry, reconnect and audit identifiers
  are fixed by the Cloud contract.

### Phase M1 — Manifest and runtime

- implement validation and deterministic resolution;
- migrate mount persistence;
- implement catalog and launch APIs;
- add unit and contract tests.

### Phase M2 — Local Mobile Shell

- implement `/mobile` and system connection pages;
- render all three fallback cases;
- test locally and on the same Wi-Fi before enabling FRP access.

### Phase M3 — Remote integration

- connect the Mobile gateway to the FRP session boundary;
- enforce premium entitlement and device authorization;
- test reconnect, expiry, revocation, Mac offline, and tunnel replacement.

Current implementation snapshot:

- schema v22 persists only non-secret remote device state;
- connector secret is stored directly in the platform SecretBackend;
- Account App exposes register, start/stop, pair, rotate, revoke and usage;
- one-use handoff exchange verifies Ed25519 JWKS and creates a restart-invalidated
  15-minute local HttpOnly session;
- remote requests are isolated to `/mobile/*` and `/v1/mobile/*`, with exact
  Host/Origin checks and no local API-key injection;
- a pinned frpc 0.62.1 supervisor uses the trusted application template,
  exponential restart backoff with jitter and immediate local stop semantics;
- the authenticated desktop release packages the exact 2026 Remote Access CA
  (`SHA-256 2c460459daae289916e999a03baa3b4658fdfc0fb6a92243a002a601ad5017c0`)
  and rejects any replacement trust anchor;
- the macOS release packages pinned arm64 and x86_64 frpc binaries, verifies
  their SHA-256 digests before use, and otherwise discovers the private
  `<base>/platform/remote/bin/frpc` installation;
- FRP authentication uses the existing device-scoped Connector Secret already
  stored in Local `SecretBackend`; the frps HTTP plugin validates it on
  `Login`, `NewProxy`, `Ping`, and `NewWorkConn`, so no deployment-global FRP
  credential is embedded in the App or manually provisioned on a device;
- the launcher publishes the Local listener's already-bound dynamic port to
  the FRP runtime, so the proxy always targets this instance's constrained
  Mobile Gateway instead of a legacy fixed port;
- canonical Device UUIDs, integer credential versions and bounded secrets are
  validated before any value reaches the trusted FRP template;
- enabled connectors are stopped locally when their credential enters the
  seven-day rotation window, including during background runtime checks;
- the Cloud/frps side of this contract is specified in
  `docs/ai2apps-cloud-frp-device-auth-requirements-v1.md`;
- Cloud connector responses are accepted only when the fixed server, port,
  HTTP proxy type, device proxy name, 32-hex device subdomain and HTTPS public
  origin all match the v1 policy;
- ambiguous device creation is reconciled through the device list and a new
  credential rotation instead of blindly creating another device;
- Mobile Chat has a dedicated constrained streaming API and never exposes the
  local model API key to phone JavaScript.

Formal integration smoke test — 2026-08-15:

- production account entitlement returned `remote.connect`;
- production device registration, pairing-challenge creation, usage lookup and
  credential rotation succeeded through the local Account App;
- production JWKS returned the expected Ed25519 `remote-mobile-v1` key;
- the created public device origin reached the deployed edge and returned the
  expected offline response before frpc admission;
- official macOS arm64 and amd64 frpc 0.62.1 archives were verified against
  SHA-256 `f9fc616d994a87d790504da21c2f942cd4224637d9ade9a67482f3c23c7f2432`
  and `f951a5aa727a4880f32753ba3c41ecc9dee38a63658760354011e71ea83db995`;
- public tunnel acceptance remains gated by deploying the fail-closed Cloud
  FRP authentication plugin. Device credential rotation and revocation must
  immediately affect new Login, proxy, heartbeat, and work-connection checks.

### Phase M4 — App authoring

- add App Studio Mobile preview and validation;
- publish authoring guidance and reference Apps;
- graduate selected built-in Apps to Mobile Ready.

## 12. Acceptance criteria

- Apps without `mobile.ready: true` never appear in Mobile Catalog responses.
- Entry resolution is exactly Mobile-Entry, Mini-Entry, App-Entry.
- All three paths launch, persist, restore, and unmount against the same
  AppInstance state.
- A declared invalid Mobile-Entry fails validation instead of silently falling
  back.
- Existing Apps remain desktop-only without migration.
- Third-party host renderers cannot become remotely accessible through fallback.
- The Mobile Bridge cannot reach Terminal, unrestricted local URLs, desktop
  administration, raw credentials, or FRP control operations.
- Remote session expiry and revocation close or invalidate active mobile mounts.
- Mac offline, tunnel unavailable, permission denial, and incompatible App
  states are recoverable and understandable on a phone.
- Catalog, launch, capability, restore, denial, and unmount actions are
  auditable by AppInstance and remote device/session identity.
- Every Mobile-ready entry passes a narrow phone-viewport check and an
  authenticated remote-session check with no CSP, blocked-frame,
  missing-resource, MIME-type, or forbidden-route errors.
- Packaged Mobile entries resolve UI assets from their indexed package
  resources; built-in host entries resolve only explicitly allowlisted Mobile
  assets. Neither path depends on `/admin/static/*`.

## 13. Non-goals for the first version

- automatically converting arbitrary desktop UI into a good phone layout;
- exposing every installed App remotely;
- native iOS or Android clients;
- direct phone-to-local-Service access that bypasses the Mobile gateway;
- Terminal or general desktop administration over the Mobile surface;
- using the FRP server as an application-data proxy beyond the traffic needed
  to reach the user's Mac.
