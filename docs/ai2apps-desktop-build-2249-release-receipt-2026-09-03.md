# AI2Apps Desktop 0.1.0 Build 2249 release receipt — 2026-09-03

## Result

Build 2249 was reviewed, tested, built for Apple silicon, Developer ID signed,
notarized and stapled, published to immutable GitHub and ModelScope origins,
and rolled out to 100 percent on the production stable channel.

- Bundle ID / instance: `com.ai2apps.desktop` / `default`
- Runtime profile: `cloud`
- Architecture: `arm64`
- Minimum macOS: `13.0`
- Rollout: `build2249-test`, `10000` basis points
- Production manifest: `https://coder.ai2apps.com/updates/stable.json`
- Final production manifest SHA-256:
  `21de7ddecbb6b08f6f98cacecc698e021125b728649a20dabae25474e24dd84a`

## Changes reviewed

- ACPF now reports the current Package or checkpoint file, per-item percent and
  transferred bytes, plus aggregate progress for multi-file downloads.
- Public ModelScope checkpoint acquisition constructs a pinned HTTPS endpoint
  directly and no longer imports the optional ModelScope Python SDK on the
  trusted `distribution_id` path.
- Signed manifests, immutable revisions, Range responses, declared sizes,
  piece digests and final file SHA-256 verification remain enforced.

The legacy ModelScope SDK compatibility path remains for non-ACPF model recipes,
but the failing Runtime-install-then-checkpoint flow uses the trusted checkpoint
distribution path and no longer reaches that import.

## Tests and gates

- Python/WebUI focused and integration tests: `110/110` passed.
- Swift Desktop suite: `69/69` passed.
- JavaScript syntax, Python compilation and `git diff --check` passed.
- Build 2248 to Build 2249 candidate verification returned `eligible`.
- Developer ID, Hardened Runtime, recursive signature, DMG pairing,
  notarization, staple and Gatekeeper checks passed.

## Signed and notarized artifact

- DMG: `AI2Apps-0.1.0-build2249-macos-arm64.dmg`
- Size: `258948073` bytes
- SHA-256:
  `d3372db64829c24537ebf71029053b1c518f8e99f958fd78656f3a161e8a0061`
- Metadata: `AI2Apps-0.1.0-build2249-macos-arm64.release.json`
- Metadata size: `1011` bytes
- Metadata SHA-256:
  `180c3748fd2a203fc4fbd355c3d2a6fc6679ac008b694085791a47be8063b852`
- App size: `700753858` bytes
- App CDHash: `f9f3e93a3dbc961395045df985936bd22d38bf72`
- Accepted Apple submission: `052bbba7-97f9-4039-9c17-3c221fac05a4`
- Result: `Accepted`, ticket stapled, Gatekeeper accepted as
  `Notarized Developer ID`

The first upload attempt, submission
`8b05014a-94b4-4cc1-93cc-1f4d58ec6528`, ended locally with a multipart upload
connection reset and remained `In Progress` for three ten-minute observation
windows. It was retained as a failed-upload audit record and was not used as
the release notarization identity. The same verified internal DMG was submitted
again; the second upload completed and was accepted.

## Immutable origins

- GitHub release:
  `https://github.com/Avdpro/ai2apps/releases/tag/v0.1.0-build2249`
- ModelScope repository: `ai2apps/desktop-releases`
- ModelScope immutable revision:
  `444d6934b6ff78ebc3ee1b7745fd3c095f8fdcad`

Both origins reported the expected sizes and SHA-256 values. Cloud independently
verified anonymous HEAD, one-byte Range, complete DMG and metadata downloads,
full SHA-256 values and stapled notarization metadata from both the local release
workspace and the production network.

## Production publication

The previously active Build 2248 manifest digest was:

`ae5180d205451e8ceb1d84dd428a7829bde318a2895219b8c8fe3c99a4adf712`

Build 2249 was atomically registered at zero basis points:

- digest:
  `de1952d285691ab592d64fbb00c87c7b113e3c649b74a62ff7a05e49d5c24014`
- history:
  `history/20260902T183119Z-de1952d285691ab592d64fbb00c87c7b113e3c649b74a62ff7a05e49d5c24014.json`

After public Build/rollout/0-bp, GET, HEAD, ETag, 304 and health acceptance,
the same rollout was expanded to 10,000 basis points:

- final digest:
  `21de7ddecbb6b08f6f98cacecc698e021125b728649a20dabae25474e24dd84a`
- history:
  `history/20260902T183214Z-21de7ddecbb6b08f6f98cacecc698e021125b728649a20dabae25474e24dd84a.json`
- operator: `codex-release-automation`
- approval label: `workspace-owner-explicit-approval`

The labels truthfully record automation execution and the workspace owner's
explicit authorization; they are not represented as two independently
authenticated human operators. The production probe returned `status: ok`,
Build 2249 and 10000 basis points. All health, Registry, Checkpoint and JWKS
probes returned 200; recent warning/error/fatal log events were zero.

Detailed Cloud receipt:

`/Users/avdpropang/sdk/ai2apps-cloud/docs/desktop-build-2249-production-publication-2026-09-03.md`

## Source-state exception

The GitHub release targets commit
`66736ccaed462e6f366b03d15c10aec5b43213ff`. This internal upgrade-test binary
was built from the approved mixed, uncommitted workspace under the documented
dirty-tree exception. It is not fully reproducible from the tag alone. No broad
commit containing unrelated workspace changes was created.

## Remaining end-to-end acceptance

Distribution publication is complete. Final product acceptance still requires
a target Mac to discover Build 2249, download it, install it, start the new
Helper/Shell successfully and verify post-update cleanup behavior.

