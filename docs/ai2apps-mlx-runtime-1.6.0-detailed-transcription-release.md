# AI2Apps oMLX Runtime 1.6.0 release receipt

Date: 2026-09-04 (Asia/Shanghai)

## Release

- Package: `ai2apps/runtime-omlx 1.6.0`
- Artifact SHA-256:
  `ce4f946b4f3a9f90f5e68e07d1d8a965e4ba1634a89fe895dfd6ca2a9c03a9a5`
- Artifact size: `382501589` bytes
- Publisher ID: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Cloud submission: `cb038b5f-2cac-4bda-93ad-f90eaa42f5d3`
- Review: `554f0370-5cac-4144-b6b4-2c462042242f`, approved
- Release status: `published`
- Initial Repository metadata version: `105`

The signed/notarized artifact identity, Apple notarization, Publisher
fingerprint, Python 3.11 and native ABI gates are recorded in
`docs/ai2apps-mlx-runtime-1.6.0-detailed-transcription-signed-build.md`.

## Immutable external origins

- GitHub tag: `package-runtime-omlx-v1.6.0`
- GitHub URL:
  `https://github.com/Avdpro/ai2apps/releases/download/package-runtime-omlx-v1.6.0/ai2apps-runtime-omlx-1.6.0-production.ai2service`
- ModelScope repository: `ai2apps/desktop-releases`
- ModelScope immutable revision: `833d90985f29d51aa0e2fa1b96384063d0cedc74`
- ModelScope URL:
  `https://modelscope.cn/models/ai2apps/desktop-releases/resolve/833d90985f29d51aa0e2fa1b96384063d0cedc74/ai2apps-runtime-omlx-1.6.0-production.ai2service`

GitHub's asset metadata and ModelScope's immutable-revision metadata both
reported size `382501589` and the exact release SHA-256 above. Neither URL uses
`latest`, a mutable branch, credentials, or temporary redirect parameters.

## Cloud source validation and activation

- ModelScope source: `src_3612eec5-2f25-4bff-b3be-a79aa93761b2`
- ModelScope validation: `val_99b68b85-b475-48d1-af32-3c1657c23f39`
- ModelScope validation digest:
  `1e3dfaf484aa5b1817ef0a74ad25678000d5ee49a1487cc0f4e302f352e659e0`
- GitHub source: `src_42204933-e99f-4df5-bb3d-0c09025fdf74`
- GitHub validation: `val_3765f398-ccff-4c30-8c81-2831fa6b42d3`
- GitHub validation digest:
  `de1e68f8b19d37c9aea7b52895b07d065510f038490709acb4cf8a971022acad`
- Final source revision/ETag: `6` / `"sources-6"`
- Final Repository metadata version: `107`
- Final Repository Snapshot digest:
  `7743d3ff10c23f3f03c7aa2f277498b87f1c506496b27a5e9846999707da12dc`

Both external sources passed Cloud's complete size, SHA-256, HTTP Range, and
46-piece manifest validation before activation. The final signed Repository
Snapshot exposes exactly Cloud, ModelScope, and GitHub as active sources while
retaining the original Cloud compatibility URL.

## Anonymous acceptance

An empty-session client fetched and cryptographically verified public Snapshot
v107, then used the production multi-source downloader to retrieve all 46
pieces. ModelScope and Cloud both won pieces during the same download. The
assembled Package was `382501589` bytes with SHA-256
`ce4f946b4f3a9f90f5e68e07d1d8a965e4ba1634a89fe895dfd6ca2a9c03a9a5`,
and its Publisher signature verified successfully. The isolated temporary
download cache was removed after the test.

Cookie access was restricted to this `ai2apps/runtime-omlx 1.6.0` publication
and source activation. No Cookie, token, Apple secret, or Publisher private key
was printed, copied, or retained in this receipt. That authorization expired
when the final source/read-back verification completed.
