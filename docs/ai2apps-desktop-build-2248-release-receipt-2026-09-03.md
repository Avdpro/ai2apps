# AI2Apps Desktop 0.1.0 Build 2248 release receipt — 2026-09-03

## Result

Build 2248 was built for Apple silicon, Developer ID signed, notarized and
stapled, published to immutable GitHub and ModelScope origins, and rolled out
to 100 percent on the production stable channel.

- Bundle ID / instance: `com.ai2apps.desktop` / `default`
- Runtime profile: `cloud`
- Architecture: `arm64`
- Minimum macOS: `13.0`
- Rollout: `build2248-test`, `10000` basis points
- Production manifest: `https://coder.ai2apps.com/updates/stable.json`
- Final production manifest SHA-256:
  `ae5180d205451e8ceb1d84dd428a7829bde318a2895219b8c8fe3c99a4adf712`

## Change under test

The updater still retains the installed App through replacement validation and
the no-UI health check, so an installation-stage failure can restore it. On a
successful post-update handoff, the replacement Launcher waits for the old
Helper to exit, launches the new Helper and visible Shell, then removes the
derived sibling `AI2Apps.previous.app`. Missing backups are harmless; symbolic
links and non-directory backup paths fail closed.

Build 2247 to Build 2248 candidate verification returned `eligible`. The full
Swift suite passed `69/69` tests, including backup removal, missing-backup and
symbolic-link rejection cases.

## Signed and notarized artifact

- DMG: `AI2Apps-0.1.0-build2248-macos-arm64.dmg`
- Size: `258963318` bytes
- SHA-256:
  `14d61da0f278008cf44cd9d950131e15bfa874a89904dbb43a689e3f15fe3fbd`
- Metadata: `AI2Apps-0.1.0-build2248-macos-arm64.release.json`
- Metadata size: `1011` bytes
- Metadata SHA-256:
  `e34208fda0faf44ffe796601d662efe31d0d3ab91455b1122af46121af475035`
- App CDHash: `d20abd296be30385165a97abc8a42ddaccbd438a`
- Apple submission: `2c3dccef-6753-4eef-947b-b3f387905de4`
- Apple result: `Accepted`, ticket stapled, Gatekeeper accepted as
  `Notarized Developer ID`

## Immutable origins

- GitHub release:
  `https://github.com/Avdpro/ai2apps/releases/tag/v0.1.0-build2248`
- ModelScope repository: `ai2apps/desktop-releases`
- ModelScope immutable revision:
  `512b5d05e1fb6041420e5d7ae7471fd060f471c9`

Both origins reported the expected sizes and SHA-256 values. Local one-byte
Range probes returned HTTP 206 and exactly one byte from each origin. The Cloud
release workflow subsequently repeated HEAD, Range, size, complete-download
SHA-256 and notarization-metadata verification for both origins.

## Production publication

The previously active Build 2247 manifest digest was:

`441cb847d395f5f7c97ad3f9612fd6e544faf4364bf858336a1d0aecc10bdc1d`

Build 2248 was atomically registered at zero basis points:

- digest:
  `05b8caa0e88a3081999d8f3f92d53c184fe122810f4c8303116356298a3df717`
- history:
  `history/20260902T160507Z-05b8caa0e88a3081999d8f3f92d53c184fe122810f4c8303116356298a3df717.json`

After public GET, HEAD, ETag, 304 and manifest-field acceptance, the same
rollout was atomically expanded to 10,000 basis points:

- final digest:
  `ae5180d205451e8ceb1d84dd428a7829bde318a2895219b8c8fe3c99a4adf712`
- history:
  `history/20260902T160620Z-ae5180d205451e8ceb1d84dd428a7829bde318a2895219b8c8fe3c99a4adf712.json`
- operator: `codex-release-automation`
- approval: `workspace-owner-explicit-approval`
- audit events added: `publish` and `rollout`; append-only total: `9`

Production GET/HEAD returned 200 and conditional ETag returned 304. Eleven
health and existing API probes returned 200, the production probe reported
`status: ok`, and release-window error-log matches were zero. The serving
container remained healthy; no Cloud image, database, Nginx or API-contract
change was required.

Detailed Cloud receipt:

`/Users/avdpropang/sdk/ai2apps-cloud/docs/desktop-build-2248-production-publication-2026-09-03.md`

## Source-state exception

The GitHub release targets commit
`66736ccaed462e6f366b03d15c10aec5b43213ff`. This internal upgrade-test binary
was built from the current mixed, uncommitted workspace under the documented
dirty-tree exception. It includes workspace changes that are not fully
reproducible from the tag alone. No broad commit containing unrelated changes
was created for this release.

## Remaining end-to-end acceptance

Distribution publication is complete. The release is not marked fully
end-to-end accepted until the target Mac upgrades from Build 2247 to 2248, the
new Helper and Shell start, and `/Applications/AI2Apps.previous.app` is observed
to be absent.
