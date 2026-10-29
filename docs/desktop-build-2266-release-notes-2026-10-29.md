# AI2Apps 0.1.8 Build 2266

Apple Silicon Desktop update. The compact cloud Runtime is bundled; model execution Runtimes and checkpoints remain separate downloads.

## Changes

- Make SearchAll and WebReader built-in AI Browser Mini-Apps, with fast search as the default and existing consent controls preserved.
- Improve Agent tool discovery, multi-turn context restoration, current-request routing and exact parameter contracts without inheriting prior approvals or replaying uncertain actions.
- Use installed Package declarations for Package-owned capabilities; strengthen ownership and lifecycle isolation.
- Improve Discover filtering, pagination, compact details and installation handoff presentation.
- Add durable Chat audio, video and document cards with owner-scoped access, including Mobile support.
- Improve Todo directory creation, configuration panel focus and exact-route vision capability reporting.
- Fix Mobile page loading when rendering the new media cards.

Independent Package, model Runtime, iOS and Cloud registry retirement operations are outside this Desktop release. Keychain reauthorization behavior is unchanged and remains subject to fresh-install/restart/upgrade acceptance. This release does not claim universal model efficiency improvements or resolve all website capture limitations.

Cloud rollout and target-Mac end-to-end upgrade acceptance are separate steps.

## Validation

- Host regression: 2776 passed, 2 skipped. Initial failures were repaired and the entire suite rerun successfully.
- Mandatory Agent authority boundaries: 657 passed; frontend: 1031 passed.
- Frozen candidate/mobile/workflow checks: 46 passed; Swift: 79 Swift Testing and 2 XCTest passed.
- Signed artifact isolated cold Local startup: 3.167 seconds, schema96, served asset hashes verified.
- Temporary 2265-to-2266 updater replacement and strict signature checks passed; this is not target-Mac UI acceptance.
- Bundle source matches the frozen candidate, no model Runtime or model checkpoints bundled. App size717311728 bytes, an increase of850582 bytes over2265.

Source commit: `55f85f062697779c787f70dca8e460962a848f30` (release branch, not a main merge).

Apple notarization: Accepted and stapled, submission `572222b7-99d3-423a-8885-7dbab6b1483c`.
DMG:268270717 bytes; SHA-256 `769b2c5d1f97b49fcd98de25474ac0ae494f91bcd5565f51385032913d18bfed`.
Release metadata SHA-256:`d135805535df551c06e3b80727a1e711391ce5a42e925a0bd17fc92040621e3d`.
