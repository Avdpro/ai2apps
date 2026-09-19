# AI2Apps Desktop 0.1.0 Build 2251 release receipt — 2026-09-20

## Result

Build 2251 was built from the clean, pushed source commit, Developer ID signed,
notarized and stapled, published to immutable GitHub and ModelScope origins,
and rolled out to 100 percent on the production stable channel.

- Bundle ID / instance: `com.ai2apps.desktop` / `default`
- Runtime profile: `cloud`
- Architecture: `arm64`
- Minimum macOS: `13.0`
- Source commit: `12af6aa9bfd7bf853fbdbe752fbc8712e60bdbde`
- Rollout: `build2251-test`, `10000` basis points
- Production manifest: `https://coder.ai2apps.com/updates/stable.json`
- Final production manifest SHA-256:
  `3e3cecaa8a2aaf4f58e6c7a2ac5de4331ff28b026ad2f155f0b8ecb937e1a5dd`

## Changes reviewed

- ACPF installation success remains visible until explicit confirmation.
- Runtime and Package downloads run concurrently and restore installation state
  after AI2Apps restarts.
- Discover and ACPF show the current item, per-item and aggregate progress,
  transferred bytes, speed and ETA where applicable.
- Adaptive full-checkpoint downloads and shared-checkpoint reuse are included.
- DeepSeek V4 `auto` tier selection and Chat performance metrics are included.
- Desktop contracts align with the published oMLX Runtime 1.7.8.
- Imagine Studio now has explicit FLUX.2 Klein 9B generation and editing ACPF
  profiles, including the 48 GiB floor and non-commercial license notice.

## Tests and gates

- Python release suite: `10050 passed, 67 skipped, 74 deselected, 0 failed`.
- AI2Apps Test System: `80 passed, 1 skipped`.
- Front-end focused tests: `4/4` passed.
- Swift Desktop suite: `77/77` passed.
- Homebrew Formula suite: `12/12` passed.
- Developer ID, Hardened Runtime, recursive signature, DMG integrity,
  notarization, staple and Gatekeeper checks passed.

The user additionally completed App-Dev physical acceptance for ACPF success,
Runtime/Package parallel download and restart recovery, DeepSeek V4 `auto` and
Chat metrics, Discover item progress, and an adaptive full-model download.

## Signed and notarized artifact

- DMG: `AI2Apps-0.1.0-build2251-macos-arm64.dmg`
- Size: `264564008` bytes
- SHA-256:
  `d25b1b09d84b6bc3a24d0503c81d5e02165e1aab352a82c3c6da63d4c1752c94`
- Metadata: `AI2Apps-0.1.0-build2251-macos-arm64.release.json`
- Metadata size: `1011` bytes
- Metadata SHA-256:
  `9c6a841928fb8675ade39014a2ee064ca19383b2cf0d673309ff5dccba49f441`
- App size: `707935042` bytes
- App CDHash: `cd70b85d91f62c3c47525bb850d362e0b05a97ea`
- Accepted Apple submission: `9e7332b1-c4fe-40a7-a182-6d6a3d763215`
- Result: `Accepted`, ticket stapled, Gatekeeper accepted as
  `Notarized Developer ID`

The release DMG contains the verified App. The retained unpacked build-directory
App was not used as a release artifact after its post-build copy changed; the
DMG-mounted App independently passed deep/strict code-sign and Gatekeeper checks.

## Immutable origins

- GitHub release:
  `https://github.com/Avdpro/ai2apps/releases/tag/v0.1.0-build2251`
- ModelScope repository: `ai2apps/desktop-releases`
- ModelScope immutable revision:
  `900bb17bee0d80949da98675dc369e9e28a1846c`

Both origins report the exact local sizes and SHA-256 values. Cloud independently
verified the local artifacts, anonymous Range behavior, complete downloads,
full SHA-256 values, byte-identical metadata and stapled release identity.

This upload exposed the ModelScope immutable endpoint's valid `HTTP 200 +
Content-Range` behavior. The Desktop Cloud preflight was aligned with the
already deployed NXR-003 policy: this compatibility is accepted only for the
allowlisted immutable ModelScope host and only with exact Content-Range,
Content-Length, requested bytes and final whole-file SHA-256. GitHub remains
strict HTTP 206. Focused tests passed `19/19`, TypeScript `--noEmit` passed, and
the production release used minimal tool image
`ai2apps-cloud:desktop-update-modelscope-range-v1-20260920`, image ID
`sha256:6437c8ddf96f83a8a608bbc13bc60ab8606ba7915ffabe1279de5f4adab35304`.
The active Cloud application container was not restarted or replaced.

## Production publication

The previously active Build 2249 manifest digest was:

`21de7ddecbb6b08f6f98cacecc698e021125b728649a20dabae25474e24dd84a`

Build 2251 was atomically registered at zero basis points:

- digest:
  `d1f00546233a8609af10d1c6218a213fe4411b7259a604cfdf82f139ae57c7b0`
- history:
  `history/20260919T221602Z-d1f00546233a8609af10d1c6218a213fe4411b7259a604cfdf82f139ae57c7b0.json`

After public GET, HEAD, ETag, conditional 304, Build identity and health
acceptance, the same rollout was expanded to 10,000 basis points:

- final digest:
  `3e3cecaa8a2aaf4f58e6c7a2ac5de4331ff28b026ad2f155f0b8ecb937e1a5dd`
- history:
  `history/20260919T221700Z-3e3cecaa8a2aaf4f58e6c7a2ac5de4331ff28b026ad2f155f0b8ecb937e1a5dd.json`
- operator: `codex-release-automation`
- approval label: `workspace-owner-explicit-approval`

The labels truthfully record automation execution and the workspace owner's
explicit authorization; they are not represented as two independently
authenticated human operators. The final public probe returned `status: ok`,
Build 2251 and 10000 basis points. Cloud health and database readiness remained
healthy, and recent high-severity application log matches were zero.

## Remaining end-to-end acceptance

Distribution publication is complete. A machine on Build 2249 should now be
eligible for Build 2251. Final updater acceptance still requires that target Mac
to discover, download, install and start Build 2251, then confirm post-update
cleanup and normal product operation.
