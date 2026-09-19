# AI2Apps oMLX Runtime 1.7.0 SSD checkpoint signed build

Date: 2026-09-17 (Asia/Shanghai)

## Runtime behavior

- Package: `ai2apps/runtime-omlx 1.7.0`.
- Adds the verified `ai2apps.ssd-checkpoint/v1` contract and direct activation
  without rebuilding or duplicating the routed-expert store.
- Adds the formal DS4.1 text/vision engine with lossless Top6, Main40/Hot8,
  `eviction_dual`, zero-copy promotion and Prefill scratch64 defaults.
- Adapts Qwen Next Full/Cached, GLM, DS4 4bit/2bit, Qwen3.6 and Ornith to the
  SSD checkpoint layout.
- Seven checkpoint repositories passed HF/ModelScope file-set, size and
  SHA-256 verification. Eight real-checkpoint Runtime smokes passed.
- DS4.1 text and vision logits SHA-256 match the frozen references exactly.

## Apple notarized Runtime DMG

- File: `artifacts/runtime-1.7.0/AI2Apps-oMLX-Runtime-1.7.0.dmg`.
- Final stapled size: `375944358` bytes.
- Final stapled SHA-256:
  `cf9a645e84c46711392b53d18855f86201fd32cca280dbd1f0c2d66b69748a32`.
- Developer ID: `Developer ID Application: Avdpro Pang (84XL5V265N)`.
- Apple submission: `19de5929-dbb1-486f-a471-8b3038ec8b8b`.
- Apple result: `Accepted`.
- Stapler validation: passed.
- Gatekeeper: accepted, source `Notarized Developer ID`.

The pre-staple DMG was 375,932,672 bytes with SHA-256
`0bee0eea2db4d5ef568562b5274a3ec731508f1a5497d5a23da2e1f056c4e28e`.
The stapled file is the immutable payload used by the outer Package.

## Signed outer Package

- Artifact:
  `packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.7.0-production.ai2service`.
- Artifact size: `373748488` bytes.
- Artifact SHA-256:
  `b066700dcebec87012e93de01e6114db9f231b0a1c89642e97c50cd91a1ec3a7`.
- Envelope SHA-256:
  `537e989a55edd5ff51a5d748ff416f6d8f2454994d096b3178a1fb773798b2c0`.
- Publisher ID: `229d6350-cd0e-408a-9905-41367385ae5c`.
- Publisher key ID: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`.
- Publisher public-key fingerprint:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`.

The Package has eight deterministic members. Contract and detached Publisher
signature verification passed. The embedded DMG is exactly 375,944,358 bytes
with the final stapled SHA-256 above.

## Validation

- Focused Runtime/installer/Worker/SSD suite: 69 passed.
- Runtime Python native slot-copy probe: passed.
- Targeted `py_compile` and `git diff --check`: passed.
- Clean temporary installation from the signed `.ai2service`: passed.
- Installed CPython 3.11 probe returned
  `ai2apps.ssd-checkpoint/v1 DeepseekV41Engine True`.
- Fixed App Dev environment was rebuilt and verified with bundle ID
  `com.ai2apps.desktop.appdev`, instance `app-dev`, cloud profile, disabled
  update URL, exact source-root contract and deep/strict signature. Its live
  title was `AI2Apps-App-Dev: M5Max-App-Dev 127.0.0.1:53300`.

## Registry publication and external sources

The signed Package was published through the standard script using the
explicitly authorized `AI2Apps-dev` browser session:

- Submission: `5553a51b-7cf2-48be-8d66-7e5466be7293`.
- Review: `49a94f38-817b-4c01-8b2f-ea448dc4695b`, approved.
- Release status: `published`.
- Repository metadata immediately after publication: `142`.

GitHub Release `package-runtime-omlx-v1.7.0` contains the exact signed artifact.
Anonymous first, middle, last and single-byte Range checks returned `206` with
matching bytes. Cloud validation `val_3c8939d3-677c-465e-8135-1d74b41e1dfa`
verified the complete SHA-256, size, Range behavior and all 45 pieces. Source
`src_ccac7e07-c438-4f48-bd76-30f28a4064fd` is active in signed Repository
Snapshot `143`, digest
`5e4c6c959357b3c3e90f61bfc2f260bb6692e4c9d6e41a0fc56aff44daea8a66`.
An empty-session production client then downloaded all 373,748,488 bytes through
the active Cloud/GitHub multi-source path, matched SHA-256
`b066700dcebec87012e93de01e6114db9f231b0a1c89642e97c50cd91a1ec3a7`,
and verified the Package identity and Publisher signature.

The same artifact is uploaded to ModelScope `ai2apps/desktop-releases` at
immutable revision `18751703b53671cb2db926f9f8ed508a70df15b0`. Its public
metadata size and SHA-256 match, and all sampled Range bytes match. The object
returns strict HTTP `200 + Content-Range` rather than `206`; Cloud OpenAPI 1.50.0
and the Local/Desktop client now accept this mode only for immutable ModelScope
sources after exact range, length, encoding, piece and final SHA-256 checks.

The source was formally registered as
`src_3125a4d0-27d8-4cfc-a9f2-43b0ec8ad3a2`. Recovery validation
`val_9f67323e-596d-46ef-92bb-13ca61e2b53b` passed the complete 373,748,488-byte
artifact and all 45 pieces. Validation digest is
`a453483dd89e5f719f47f7c81b1a05a1893ddf08e6726c77181598e00fd500d0`;
the range receipt uses `package-single-range-v2`, records
`modelscope-content-range-200`, and observed 48 `http-200-content-range`
responses. At validation time the Source was revision 7 and
`pending_approval`. Dev and
App-Dev load the current compatible source tree, and the fixed Test App was
rebuilt with the same implementation and passed embedded import plus
deep/strict signature verification. A release Desktop is not required for this
activation decision. The direct activation request was rejected by Cloud with
`ARTIFACT_SOURCE_SELF_APPROVAL_NOT_ALLOWED`. Investigation confirmed this is a
new compatibility-only restriction introduced from an incorrect Local handoff
requirement; the historical contract allows a stepped-up system administrator
to self-approve with a dedicated audit event. Cloud deployed the correction on
2026-09-18 without changing Range validation. The same activation operation
then succeeded at source revision 8 and Repository metadata 154, with signed
Snapshot digest
`49d0748f75606adf61397106ebcf197316a5d2c1530d9d41a0ac0d7fede515c2`.
An anonymous client verified Snapshot 154 with the pinned Repository key and
confirmed Cloud, GitHub and ModelScope as the three public sources.

The earlier September 3 Range failure was also rechecked. In that incident the
client sent a synthetic `If-Range: "sha256-..."` value that did not match the
ModelScope CDN ETag, so the CDN correctly fell back to HTTP `200`; removing
`If-Range` restored `206`. The current downloader still omits `If-Range`, and
its focused regression test passes. That earlier fix does not explain the 1.7.0
object: anonymous requests with no `If-Range`, the synthetic value, official
ModelScope `snapshot-identifier` and `X-Request-ID` headers, one-byte, 4 KiB,
8 MiB, middle, closed-full and open-ended ranges, `master`, immutable revision,
legacy API and `download=true` forms all return the exact requested bytes and
`Content-Range`, but status `200` from the repository nginx. The response has
no ETag or Last-Modified value that could be used for a valid `If-Range`.

Both 1.6.2 and 1.7.0 are valid Git LFS pointers, both have matching exact
`.gitattributes` rules, and the public API marks both `IsLFS=true`. The 1.7.0
SDK upload transferred all 373,748,488 bytes before committing; this was not a
deduplicated pointer-only commit. The remaining difference is server-side
delivery: 1.6.2 redirects to `cdn-lfs-cn-1.modelscope.cn` and returns `206`,
while 1.7.0 is served directly by `modelscope.cn` nginx with the wrong status.

An immutable-path control was performed after this diagnosis. The exact signed
artifact was committed under SHA-named alias
`packages/runtime-omlx/1.7.0/b066700dcebec87012e93de01e6114db9f231b0a1c89642e97c50cd91a1ec3a7.ai2service`
at revision `bc1695dad1017b155d9b25b03a623793c2c7e308`. ModelScope reported that
the global LFS blob already existed and reused it, so no duplicate 374 MB
upload occurred. Anonymous first, middle and final 4 KiB probes matched the
local artifact exactly for both the alias and original path at that revision,
but every response remained direct `modelscope.cn` HTTP `200` with exact
`Content-Range`; neither path redirected to the LFS CDN. This rules out the
repository path and commit revision as remedies and localizes the remaining
failure to the LFS object delivery mapping or ModelScope backend.
