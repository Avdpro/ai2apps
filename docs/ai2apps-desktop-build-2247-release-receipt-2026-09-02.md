# AI2Apps Desktop 0.1.0 Build 2247 release receipt — 2026-09-02

## Result

AI2Apps Desktop 0.1.0 Build 2247 was built for Apple silicon, signed with the
Developer ID identity, notarized and stapled, uploaded to the immutable
ModelScope and GitHub release origins, and published to the production stable
update channel at 100 percent.

- Bundle ID: `com.ai2apps.desktop`
- Bundle version: `2247`
- Runtime profile: `cloud`
- Architecture: `arm64`
- Minimum macOS version: `13.0`
- Production manifest: `https://coder.ai2apps.com/updates/stable.json`
- Rollout ID: `build2247-test`
- Final rollout: `10000` basis points
- Final production manifest SHA-256:
  `441cb847d395f5f7c97ad3f9612fd6e544faf4364bf858336a1d0aecc10bdc1d`

## Product change

The menu-bar updater now uses distinct monochrome assets for checking or
verifying, downloading, and ready-to-install states. Only the numeric download
percentage is shown next to the icon. A manual update check reports “当前已是最新版本”
in a temporary popover when no update is available.

The complete Swift test suite passed: `65/65` tests.

## Signed and notarized artifact

- DMG: `AI2Apps-0.1.0-build2247-macos-arm64.dmg`
- Size: `258986356` bytes
- SHA-256:
  `c8adcf0689ff4d00a39beb8ef845339f3674f3b2face9f5b5c4cec04204b643f`
- Release metadata: `AI2Apps-0.1.0-build2247-macos-arm64.release.json`
- Metadata size: `1011` bytes
- Metadata SHA-256:
  `572bf477c2d5485758af00e1d5f15f0688b5410970aa0133188ba1ca16c559a8`
- App CDHash: `fc0f6bdf90a8c92d190384aa07e51323da5378f9`
- Apple notarization submission:
  `c83fe916-5801-4342-aae4-6216e66f56ae`
- Notarization result: `Accepted`; DMG ticket stapled; Gatekeeper accepted as
  `Notarized Developer ID`.

The Build 2246 to Build 2247 update-candidate validation returned `eligible`.

## Immutable origins

GitHub release:

- `https://github.com/Avdpro/ai2apps/releases/tag/v0.1.0-build2247`
- release is published as a prerelease;
- both assets report `uploaded` and their remote sizes and SHA-256 digests match
  the local release files.

ModelScope release:

- repository: `ai2apps/desktop-releases`
- immutable revision:
  `4f79fbcf791d70bfe933d36decfe76a9c56a21da`
- both remote files match the local sizes and SHA-256 digests.

One-byte Range probes against both DMG origins returned HTTP 206 and exactly
one byte.

## Production publication

The Cloud release workflow independently validated both manifests and both
origins, including HEAD, Range, complete download, file size, SHA-256 and
notarization metadata.

Build 2247 was first atomically published at zero basis points:

- previous production digest:
  `31234bfc210ce408986a2c362181add2de5915294fd66a84d690d65c7396e29a`
- zero-percent digest:
  `4dbb64d52bd60ab569adeeb066723de464f20a68620afab969f787f0e981eb73`
- history:
  `history/20260902T134045Z-4dbb64d52bd60ab569adeeb066723de464f20a68620afab969f787f0e981eb73.json`

After public GET, HEAD and ETag validation, the same rollout was atomically
expanded to 10,000 basis points:

- final digest:
  `441cb847d395f5f7c97ad3f9612fd6e544faf4364bf858336a1d0aecc10bdc1d`
- history:
  `history/20260902T134835Z-441cb847d395f5f7c97ad3f9612fd6e544faf4364bf858336a1d0aecc10bdc1d.json`
- operator: `codex-release-automation`
- approval label: `workspace-owner-explicit-approval`
- audit events added: `publish` and `rollout`

The final public manifest returned GET/HEAD 200 and conditional ETag 304. It
contains Build 2247, `10000` basis points, and the two immutable ModelScope and
GitHub URLs. The served body SHA-256 equals the final production digest.

The Cloud production probe returned `status: ok`. Ten health and existing API
checks returned 200, the application container remained healthy, and the
release-window error-log match count was zero. No Cloud image, database, Nginx
or API contract change was required.

The detailed Cloud-side receipt is:

`/Users/avdpropang/sdk/ai2apps-cloud/docs/desktop-build-2247-production-publication-2026-09-02.md`

## Source-state exception

The GitHub release targets source commit
`66736ccaed462e6f366b03d15c10aec5b43213ff`. The binary was deliberately built
from the current mixed, uncommitted workspace under the documented internal
dirty-tree exception. It therefore includes uncommitted workspace changes and
is not fully reproducible from the tag alone. No broad commit containing those
unrelated changes was created as part of this release.

## Remaining acceptance

Distribution publication is complete. The remaining end-to-end acceptance is
for an installed Build 2246 client to discover, download, verify, install and
launch Build 2247.
