# Cloud handoff: retire standalone browser research Packages

Desktop now owns Search All and Web Reader as built-in AI Browser Mini-Apps.
No Cloud code or production metadata was modified by this Desktop work.

## Confirmed product decision (2026-10-29)

The user explicitly requested removal of these standalone Packages from Cloud:

- `ai2apps/search-all`
- `ai2apps/web-reader`

This supersedes the previous proposal to keep them discoverable for older clients.
Remove their standalone catalog entries from discovery, search, recommendations,
and new-install selection, including capability-based and exact-detail lookups.
Use the standard Cloud Package removal/retirement workflow; preserve its normal
audit records and artifact retention policy. Do not create replacement registry
Packages for these built-in Mini-Apps. This request does not authorize deleting
user data, unrelated Packages, or bypassing registry audit controls.

Older Desktop versions without the built-ins may lose new-install access to these
two capabilities; the Cloud implementation should report their retirement clearly
rather than return a candidate that cannot be installed. Already installed copies
must not be remotely uninstalled. New Desktop versions use their built-in entries.

Desktop registration reserves product-owned Mini-App identities; older installed
copies cannot override their built-in declarations, mount or AaAT binding. It does
not delete the user's old Package state or related browser data. Shopping Pro and
Trip Planner remain independent Packages and must stay discoverable/installable.

Acceptance:

- Neither Package is returned as an installable candidate through keyword,
  capability, category/tag, version, or exact-detail queries; cached results and
  bound cursors must not bypass removal.
- Attempts to install a stale reference receive an explicit retired/unavailable
  response before download or parameter collection.
- New clients retain built-in `web.search`/`web.fetch` with no Cloud installation.
- Existing local copies and user data are preserved; Shopping Pro and Trip Planner
  remain discoverable/installable.
- Cloud supplies a production receipt identifying the removed entries and verified
  query/install behavior. Desktop then performs live discovery acceptance.
