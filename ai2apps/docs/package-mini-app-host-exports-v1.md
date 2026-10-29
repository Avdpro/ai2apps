# Installed Mini-App Host SDK exports v1

A signed `app.yaml.mini_apps[].aaat` declaration owns the Mini-App's public AaAT
capability name, interface version, host placement, input schema, fields,
confirmation policy, localized presentation and Agent context. Capability catalog
summaries describe discoverable software but cannot create executable Providers.

The schema is `ai2apps.mini-app-host-exports/v1`, with a nonempty `exports` array.
Each export has exactly `name`, `interfaceVersion`, `host`, `sdk`, `inputSchema`,
`fields`, `displayName`, `summary`, `agentContext`, `selectionRequired`, and
`options`. The signed capability catalog must declare the same Mini-App identity,
name and interface version; the host must be an actual Mini-App placement. Remote
JSON schema references and reserved routing parameters are rejected.

A native owner registers typed Host SDK protocols with the Package binder at
platform composition time. These protocols contain only native implementation
callbacks and authoritative effects/capability guards. Package JSON cannot select
Python modules, load arbitrary code, override admission effects or grant authority.
Owners retain existing job, Profile binding, material ACL, consent and shared output
checks. Functional execution goes through the same durable Agent Tool lifecycle.
The generic binder contains no business Tool names, Mini-App IDs or domain logic.

The installed exact release and effective definition are checked at discovery,
parameter inspection, prepare, invocation and after submission. Disable/uninstall,
release or declaration changes, unsupported SDKs and invalid placements revoke
Providers and forms. Old receipts are invalidated by the Provider version. A change
after submission is an uncertain outcome and cannot cause fallback or replay.
SDK model readiness may narrow the Package input contract but cannot add public
parameters absent from the signed Package declaration.

Package exports are owned by the Package App, even when placed in a Studio. The
host's In-App Chat may use them only for the validated current Mini-App and exact
signed host placement. The Provider key must match that specific host export;
sharing a Mini-App identity/capability across two hosts does not admit both
execution bindings into either Chat. A generic trusted owner export-access predicate allows
this composition without loosening other App Chat ownership checks.

Native routed gateways may explicitly declare themselves reusable by additional
Providers. A Package SDK may share one only when its native effects and required
capabilities are subsets of the gateway guards. Unrelated gateway collisions stay
rejected. SDK callbacks never replace the underlying native Provider. Removed
legacy composition releases public names while preserving old descriptor IDs and
invocation history.

Fixed Dev/App-Dev source Packages use the existing trusted development loader and
its validated source manifest/catalog; no release snapshot or copied overlay is
used. Source bindings are explicitly distinct from signed production installs.
Production registration always requires exact installed artifact provenance.

This protocol requires a matching Desktop host. Package installation on an older
Desktop does not provide these new lifecycle guarantees; a coordinated Desktop
release remains necessary. No Cloud API changes are introduced.

Explicitly reopening an idle App Chat refreshes the installed Provider bindings
while preserving the conversation. An active admitted turn prevents this scope
refresh; its old authorization/receipts cannot be upgraded implicitly. Uninstall
and reinstall still change Provider versions and invalidate old receipts.
