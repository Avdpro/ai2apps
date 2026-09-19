# AI2Apps oMLX Runtime 1.6.2 release receipt

Date: 2026-09-05 (Asia/Shanghai)

## Release

- Package: `ai2apps/runtime-omlx 1.6.2`
- Artifact SHA-256:
  `040bdf2e5bc32fed203bbc695d5bd34ebd5e514a70a7b38dd8a97f0cdc28943a`
- Artifact size: `376086471` bytes
- Manifest SHA-256:
  `232207dc0f94034f2d3d48aedc462650d0b5be488f432008210b026895a750f6`
- Envelope SHA-256:
  `74e8e6b974ac806e25282c8a007e24c52b2549333de7b759f546837d928f9abe`
- Embedded notarized DMG SHA-256:
  `4284fa871464f4530556e3a5684ba126d6b64e9d648e95298d4e11d40898c1fb`
- Embedded notarized DMG size: `378279314` bytes
- Publisher ID: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher key fingerprint:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`
- Cloud submission: `45f01f49-ce7b-41a6-90f7-db7ae6162246`
- Review: `2fcf0454-8535-447d-92bb-474fd94ada54`, approved
- Release status: `published`
- Repository metadata immediately after publication: `113`

Runtime 1.6.2 adds the bounded, cancellable `audio_voice_training` Worker
operation, `POST /v1/audio/voices/train`, and the explicit
`audio-voice-training-v1` capability. RVC training defaults to FP16 forward and
backward compute with FP32 Adam master weights and optimizer state; BF16 and
FP32 remain explicit alternatives.

## Apple and Package verification

- Developer ID identity: `Developer ID Application: Avdpro Pang (84XL5V265N)`
- Apple notarization submission: `c68c2dd5-c5a2-4872-9606-128e11aceadd`, accepted
- Stapler validation: passed
- Gatekeeper assessment: accepted as `Notarized Developer ID`
- Bundled interpreter: CPython `3.11.10`
- `cp313`, `cpython-313`, and `python3.13` Runtime paths: none
- Outer Package members: 8 deterministic members
- Embedded DMG byte identity: matched the stapled final DMG
- Runtime/Worker/Provider/resource/builder regression: `71 passed`
- Metal audio route/STT regression: `37 passed`, 4 deselected

The final mounted Bundle contained both `/v1/audio/voices/train` and the
`audio_voice_training` Worker route. Its deep/strict signature, whole DMG
signature, staple, Gatekeeper assessment, Package Contract and Publisher
envelope all passed.

## Immutable external origins

- GitHub tag: `package-runtime-omlx-v1.6.2`
- GitHub URL:
  `https://github.com/Avdpro/ai2apps/releases/download/package-runtime-omlx-v1.6.2/ai2apps-runtime-omlx-1.6.2-production.ai2service`
- ModelScope repository: `ai2apps/desktop-releases`
- ModelScope immutable revision: `97e28e20e9c420e50297d8891b2d1f4e2cb111d9`
- ModelScope URL:
  `https://modelscope.cn/models/ai2apps/desktop-releases/resolve/97e28e20e9c420e50297d8891b2d1f4e2cb111d9/ai2apps-runtime-omlx-1.6.2-production.ai2service`

Both origin metadata records report size `376086471` and SHA-256
`040bdf2e5bc32fed203bbc695d5bd34ebd5e514a70a7b38dd8a97f0cdc28943a`.
Anonymous first, middle, last, and one-byte Range requests returned `206`,
correct `Content-Range`, and bytes identical to the local signed artifact.

## Cloud source validation and activation

- ModelScope source: `src_ef207cc5-5668-4928-b63d-4bf5174a0855`
- ModelScope validation: `val_9bd45e9b-7649-4889-ab31-09d3b64c7f0b`
- ModelScope validation digest:
  `992e4edf6febb4c544997df2f63aebf6f34e299f5936cf862a0f99876e11acde`
- GitHub source: `src_ecb03e62-25a5-4e86-a223-6ba38d90db7a`
- GitHub validation: `val_4dfd9976-b72b-4c91-ad9d-6798156f56b7`
- GitHub validation digest:
  `c18ae7c3913b9a86464b2f9267588072dab44019a65a706ac2f7cf9ab53f7ef5`
- Final source revision/ETag: `6` / `"sources-6"`
- Final Repository metadata version: `115`
- Final Repository Snapshot digest:
  `3988af3b34516d38e184496baa78750995cf389786214fa61dfa89596a2420c9`

Both external sources passed Cloud's complete size, SHA-256, HTTP Range and
45-piece manifest validation before activation. The signed public Snapshot
contains exactly the active Cloud, ModelScope and GitHub sources.

## Anonymous acceptance

A fresh client with an empty in-memory session store fetched and verified
public Snapshot v115, then used the production multi-source downloader to
retrieve and verify all 45 pieces. The assembled Package was `376086471` bytes
with SHA-256
`040bdf2e5bc32fed203bbc695d5bd34ebd5e514a70a7b38dd8a97f0cdc28943a`;
its Package identity and Publisher signature verified successfully. ModelScope
won most observed piece races and Cloud also returned valid pieces.

Cookie access was restricted to this `ai2apps/runtime-omlx 1.6.2` publication
and source activation. No Cookie, token, Apple secret or Publisher private key
was printed, copied or retained. That authorization expired after the final
source/read-back verification completed.
