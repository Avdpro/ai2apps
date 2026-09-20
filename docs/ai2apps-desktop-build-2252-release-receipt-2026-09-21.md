# AI2Apps Desktop 0.1.0 Build 2252 release receipt — 2026-09-21

## Result

Build 2252 was built from a clean, pushed source commit, Developer ID signed,
notarized and stapled, published to immutable GitHub and ModelScope origins,
and rolled out to 100 percent on the production stable channel. One target-Mac
upgrade remains required for updater end-to-end acceptance.

- Bundle ID / instance: `com.ai2apps.desktop` / `default`
- Runtime profile: `cloud`
- Architecture: `arm64`
- Minimum macOS: `13.0`
- Source commit: `9521a6d674babd03125ed0e310c926863dbd6cde`
- Rollout ID: `build2252-test`
- Rollout: `10000` basis points
- Production manifest: `https://coder.ai2apps.com/updates/stable.json`
- Final production manifest SHA-256:
  `894271943aa4977d78fae3a4c2f0d622382662905fd123b26a2e285df5002254`
- Previous production build / digest: `2251` /
  `3e3cecaa8a2aaf4f58e6c7a2ac5de4331ff28b026ad2f155f0b8ecb937e1a5dd`

## Included change

- `NXR-VERIFIED-OVERLAY-CHECKPOINT-READINESS-20260921`: Desktop Local now
  recognizes a Registry-installed immutable overlay checkpoint from its verified
  receipt instead of requiring a standalone model root layout. This fixes
  activation for MiniMax H3 LightX2V 4-step/8-step and OpenVDN DMD 8-step /
  Stage-B 50-step variants while retaining the existing standalone checkpoint
  gates for FL2VA, Ref2VA, Transformer, Diffusers, ONNX and SSD Cached-MoE.
- The accepted overlay must match the Package `distribution_id`, manifest
  digest, exact file set, read-only regular-file state and the installer-recorded
  device/inode/size/mtime receipt. Mutation, extra files, symlinks or identity
  mismatch fail closed.
- No oMLX Runtime or model Package version changes are included.

## Tests and Test instance

- Focused Python: `107 passed`.
- Swift Desktop: `77 passed`.
- `git diff --check`: passed before source freeze.
- Fixed Test App was rebuilt with `build-test-app.sh`, launched, and verified as
  `com.ai2apps.desktop.test`, instance `test`, cloud Runtime, non-Development
  snapshot, production update URL, valid release layout and valid deep signature.
- App-Dev real activation reused the completed shared OpenVDN checkpoint, passed
  all four ACPF steps, supplied a non-empty checkpoint path to the Worker and
  exposed `(Local) AI2Apps-MLX · OpenVDN H3 DMD 8-step Q4` as ready.

## Signed and notarized artifact

- DMG: `AI2Apps-0.1.0-build2252-macos-arm64.dmg`
- DMG size: `264511065` bytes
- DMG SHA-256:
  `261849e3a56c3ab55d423a15de3550b4d5fd1333a1d0a1d7112f219b79016d94`
- Metadata: `AI2Apps-0.1.0-build2252-macos-arm64.release.json`
- Metadata size: `1011` bytes
- Metadata SHA-256:
  `750d86b320a6ec970725b5b456b254dc544c2ba3b6bee04313d15169f5d90f63`
- App size: `707938521` bytes
- App CDHash: `c98f0332e749cf2f1dc3205f3f331f9bcfcfe296`
- Runtime manifest SHA-256:
  `2048f9c90bdc42992f7c6a6c6e5be28ed6f9bec51130a7dc91921d1eec0e9bce`
- Apple submission: `3850a24c-4457-4516-b9d0-ff4cee2cc806`
- Result: `Accepted`; DMG stapled; Stapler, Gatekeeper, deep/strict signing,
  Runtime, DMG and metadata verification passed.

## Immutable origins

- GitHub release:
  `https://github.com/Avdpro/ai2apps/releases/tag/v0.1.0-build2252`
- GitHub target commit:
  `9521a6d674babd03125ed0e310c926863dbd6cde`
- ModelScope repository: `ai2apps/desktop-releases`
- ModelScope immutable revision:
  `735eb1d4a1bfbc30677fc80308fc2bb9330a0429`

Both origins were anonymously downloaded in full after publication. All four
downloaded files matched the local sizes and SHA-256 values exactly. GitHub
returned strict `206` for a one-byte Range request. ModelScope returned its
allowlisted compatibility form, `200` with exact
`Content-Range: bytes 0-0/264511065`, `Content-Length: 1` and one payload byte.

## Production publication

Prepared manifests:

- 0% registration:
  `apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.0-build2252/stable-zero.json`
  - SHA-256:
    `77239fb9518bae45407dec2de2165fbd1290262d9f2a82d21d7f6c7db6d469cd`
- 100% reference manifest:
  `apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.0-build2252/stable.json`
  - SHA-256:
    `9b257980d9189723b9910c64fb60f382e703ca912c73db5f49f160de79eb75ad`

The protected Cloud workflow used the fixed publication image
`ai2apps-cloud:desktop-update-modelscope-range-v1-20260920`, image ID
`sha256:6437c8ddf96f83a8a608bbc13bc60ab8606ba7915ffabe1279de5f4adab35304`.
The active Cloud application container was not restarted or replaced.

Before publication, the Cloud host verified the uploaded local DMG, metadata
and both manifests against their expected sizes and SHA-256 values. Manifest
validation and strict dual-origin preflight passed, including complete downloads,
Range compatibility and notarization metadata.

Build 2252 was atomically registered at zero basis points:

- digest:
  `01b790f16a3fdc88ca050d48fae4308b55871b46ebfd0379f9713cd85d557498`
- history:
  `history/20260920T211743Z-01b790f16a3fdc88ca050d48fae4308b55871b46ebfd0379f9713cd85d557498.json`

After public GET, HEAD, ETag, conditional 304, Build identity, rollout identity,
Cloud health and database readiness passed, the same `build2252-test` rollout
was expanded to 10,000 basis points:

- final digest:
  `894271943aa4977d78fae3a4c2f0d622382662905fd123b26a2e285df5002254`
- history:
  `history/20260920T211920Z-894271943aa4977d78fae3a4c2f0d622382662905fd123b26a2e285df5002254.json`
- operator: `codex-release-automation`
- approval label: `workspace-owner-explicit-approval`

The labels truthfully record automation execution and the workspace owner's
explicit authorization; they are not represented as two independently
authenticated human operators. The final public probe returned `status: ok`,
Build 2252, rollout ID `build2252-test` and 10,000 basis points. Public HEAD
returned HTTP 200, conditional ETag returned 304, Cloud and database remained
healthy with zero restarts, and recent high-severity application log matches
were zero.

## Remaining end-to-end acceptance

Distribution publication is complete. A target Mac on Build 2251 must discover,
download, install and start Build 2252, then confirm post-update cleanup and
normal operation.

`/Applications/AI2Apps.app` was not present on this build host, so the local
`verify-update-candidate.py` comparison could not run. This does not replace the
required target-Mac end-to-end upgrade acceptance.
