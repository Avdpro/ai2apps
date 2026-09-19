# AI2Apps oMLX Runtime 1.6.1 release receipt

Date: 2026-09-05 (Asia/Shanghai)

## Release

- Package: `ai2apps/runtime-omlx 1.6.1`
- Artifact SHA-256:
  `20f5b5a1cb2f5a6cc943be0b50dad5a8552428558e7b84531048f35aa6ec0321`
- Artifact size: `373172093` bytes
- Embedded notarized DMG SHA-256:
  `99a55e11fb74af445a8dd898de9db78088e1165a830f75bb1445ebe813913990`
- Embedded notarized DMG size: `375365231` bytes
- Publisher ID: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher key fingerprint:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`
- Manifest SHA-256:
  `37b1e1f4a34d10c19466d59baa4a1c5ce494ed05730b4e0efff17f7b24f7ce37`
- Envelope SHA-256:
  `2d5b1e1c4a0b5f1a5c70028c4c4a338d3c0c5566b738fe95d90591ec5666b764`
- Cloud submission: `788fc4be-d148-4340-b2de-4c4c046fed4b`
- Review: `29299eb5-5898-42ca-b52a-e9d7d0069fb6`, approved
- Release status: `published`
- Published at: `2026-09-04T22:00:37.169Z`

Runtime 1.6.1 adds request-scoped multipart reference audio and validated
voice-conversion controls to `POST /v1/audio/process`. It declares
`audio-reference-input-v1`, forwards Seed-VC v2 timbre/AR and dual-CFG controls,
and retains the existing MLX/Python dependency layer.

## Apple and Package verification

- Developer ID identity: `Developer ID Application: Avdpro Pang (84XL5V265N)`
- Apple notarization submission: `c6dab5b4-42da-4865-967d-972df333fef9`, accepted
- Stapler validation: passed
- Gatekeeper assessment: accepted as `Notarized Developer ID`
- Outer Package members: 8 deterministic members
- Embedded DMG byte identity: matched the stapled final DMG
- Focused Runtime/API/capability regression: `50 passed, 4 deselected`

## Immutable external origins

- GitHub tag: `package-runtime-omlx-v1.6.1`
- GitHub URL:
  `https://github.com/Avdpro/ai2apps/releases/download/package-runtime-omlx-v1.6.1/ai2apps-runtime-omlx-1.6.1-production.ai2service`
- ModelScope repository: `ai2apps/desktop-releases`
- ModelScope immutable revision: `4190557b4096224e6f5eef207e63031f4140ea0f`
- ModelScope URL:
  `https://modelscope.cn/models/ai2apps/desktop-releases/resolve/4190557b4096224e6f5eef207e63031f4140ea0f/ai2apps-runtime-omlx-1.6.1-production.ai2service`

GitHub asset metadata and ModelScope immutable-revision metadata both report
size `373172093` and SHA-256
`20f5b5a1cb2f5a6cc943be0b50dad5a8552428558e7b84531048f35aa6ec0321`.

## Cloud source validation and activation

- ModelScope source: `src_4b82b57f-5520-4863-8947-beb23041c72e`
- ModelScope validation: `val_c546a544-9820-447b-9e0f-e72fb47b77ea`
- ModelScope validation digest:
  `41b942a7fb633c1d13d6d51bacf4b401ee872eb828189d0e44eb567ea7baee25`
- GitHub source: `src_f5839b37-52b4-40f3-b410-1ca81e368fb5`
- GitHub validation: `val_4edb339d-8418-4f31-b1cc-5d23c0c42789`
- GitHub validation digest:
  `25e55b48101897ade52c5ae5d938351e29fb924039b846e0d2c1b85ad7b69c16`
- Final source revision/ETag: `6` / `"sources-6"`
- Final Repository metadata version: `112`
- Final Repository Snapshot digest:
  `07b291b7b03d8db805c0c6ee68c41e11f7ceeb9fb3f936a98fde75f5303cfc14`

Both external sources passed Cloud's complete size, SHA-256, HTTP Range and
45-piece manifest validation before activation. The signed public Snapshot
contains exactly the active Cloud, ModelScope and GitHub sources.

## Anonymous acceptance

An empty-session client fetched and cryptographically verified public Snapshot
v112, then used the production multi-source downloader to retrieve and verify
all 45 pieces. ModelScope won the observed piece races in this run. The assembled
Package was `373172093` bytes with SHA-256
`20f5b5a1cb2f5a6cc943be0b50dad5a8552428558e7b84531048f35aa6ec0321`,
and its Publisher signature verified successfully. Independent Cloud source
validation proves that GitHub and ModelScope each support Range and return the
same complete signed artifact; Cloud remains the compatibility fallback.

Cookie access was restricted to this `ai2apps/runtime-omlx 1.6.1` publication
and source activation. No Cookie, token, Apple secret or Publisher private key
was printed, copied or retained in this receipt. That authorization expired
when the final source/read-back verification completed.
