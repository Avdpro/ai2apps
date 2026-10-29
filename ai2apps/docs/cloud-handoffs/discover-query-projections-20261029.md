# Discover precise querying and bounded projections — Cloud handoff

Existing Cloud OpenAPI /v1/registry/content and the capability-catalog handoff support exact capability/input_type/output_type, mini_app_category, studio, package_id/version, publisher, App/Mini-App type, device/runtime/memory/storage and bound pagination. Matching remains AND-normalized keywords. The client can implement summary/detail projections and latest-compatible grouping without Cloud changes.

Missing negotiated features requested:

1. Published taxonomy and TAG vocabulary (localized names/stable IDs), and an explicit tag filter with AND/OR semantics. Do not infer unsupported parameters work; advertise in discoveryCapabilities.
2. Server-side projection=summary plus exact card detail lookup, preserving release/digest/provenance and lifecycle revalidation. Summary omits exclusion details and full declarations; counts cover full filters.
3. Negotiated release_policy=latest_compatible per Package/component, with explicit opt-in history. Never choose withdrawn/yanked/revoked releases, or silently substitute the exact version selected for installation.
4. Optional match_status filter to avoid transferring all excluded cards, with exclusion reason aggregates and stable, full-query-bound pagination.

No Cloud code changed in Desktop repository. Existing endpoints must remain compatible; unsupported new fields must be rejected explicitly. Category and TAG suggestions never grant installation or execution authority. Tests must cover old clients, missing declarations, older-compatible release selection, exact digests, revoked releases, cursor mismatch and multilingual metadata.

Desktop currently uses existing category/studio/exact filters only, retains full source records in scoped snapshots and projects summaries locally. Server-side features are optimizations pending Cloud implementation, not prerequisites for the local fix.

## Usage observation follow-up

The live acceptance receipts expose settled AI2Apps `points.charged` and `pricingVersion`; Desktop now preserves them without deriving money from model names or balance differences. `cachedInputTokens` is zero in both historical and new receipts. Please expose whether this number was actually reported by the upstream provider (for example `cacheUsageReported` / provenance), so an unavailable counter normalized to zero cannot be mistaken for an observed KV-cache miss. If provider currency cost is to be compared, expose its observed amount, currency and accounting scope separately from AI2Apps Points. Desktop must leave unknown observations unknown.
