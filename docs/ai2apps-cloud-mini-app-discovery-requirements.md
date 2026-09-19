# AI2Apps Cloud Mini-App Discover Requirements

## Objective

Expose signed Mini-App component metadata in Discover without adding a `mini-app` Package type or a second
installation lifecycle. An artifact remains an App Package; Mini-App cards are indexed components of that
Package.

## Registry ingestion

Cloud Registry must accept the optional top-level `miniApps` array in `ai2apps.package-manifest.v1` only
when `package.type` is `app`. It must retain the array exactly as covered by the Publisher signature and
must not synthesize, edit, or trust an unsigned client field.

Each item contains:

- `componentId`: canonical Mini-App identity;
- `displayName`, optional `description`, and optional Lucide-compatible `icon`;
- `version` and `lifecycleKind` (`clip`, `project`, or `live_session`);
- one to eight extensible lower-kebab `categories`;
- one to sixteen canonical Studio IDs in `placements`.

The existing Package builder derives this projection from signed `app.yaml.mini_apps` and rejects a
mismatch. Cloud still applies schema validation and must reject `miniApps` on Agent or Service Packages.

## Search and catalog responses

Registry search, recommendation, and Package catalog responses must return `miniApps` with the containing
Package release. Search must index component ID, display name, description, categories, placements, and
containing Package metadata. A future `content=mini-app` filter may return App Packages containing at least
one matching component; it must not fabricate standalone releases.

Until that filter is available, Desktop requests up to 100 App Packages and performs a compatibility
expansion locally. Pagination completeness must be verified before the client fallback is removed.

## Lifecycle and security

- Artifact URL, Publisher identity, compatibility, permissions, install, upgrade, rollback, and uninstall
  remain those of the containing App Package.
- A component card must never receive a separate artifact digest or mutable version record.
- Cloud must not treat a Studio placement as ownership; one component may be placed in multiple Studios.
- Existing releases without `miniApps` remain valid and installable.
- No production Cloud code is changed from the Desktop repository; this document is the implementation
  handoff for the Cloud project.

## Acceptance

1. Publish an App Package containing two Mini-Apps and verify one App card plus two Mini-App cards.
2. Filter by two different Mini-App categories and by Studio placement.
3. Install either component card and verify only the containing Package installation is created.
4. Upgrade the Package and verify all component cards move to the new signed projection atomically.
5. Reject a non-App Package carrying `miniApps` and a release whose signed projection is malformed.
