# AI2Apps oMLX Runtime 1.7.1 shared-checkpoint release

Date: 2026-09-18 (Asia/Shanghai)

## Runtime behavior

- Package: `ai2apps/runtime-omlx 1.7.1`.
- Treats `.gitattributes` as Hub repository metadata when validating an
  `ai2apps.ssd-checkpoint/v1` snapshot. Published Checkpoint Distributions may
  intentionally omit that file even when an older SSD marker recorded it.
- Runtime payload files, declared sizes, the safetensors index digest,
  `external-tensors.json`, expert-store manifest, model family and layout remain
  strictly validated.
- This fixes DeepSeek V4.1 installation after the complete 475 GB snapshot has
  already been imported into the machine-wide shared Checkpoint cache.

## Signed artifacts

- Apple-notarized DMG:
  `artifacts/runtime-1.7.1/AI2Apps-oMLX-Runtime-1.7.1.dmg`
  - bytes: `374746767`
  - SHA-256: `19ecad5c2d9511214a79f02d6c36716514b9c280201cefa68d74f4c4da8ab98c`
  - Apple submission: `9c90a4aa-728b-4863-8a42-11c38cb60636`
  - result: Accepted; staple and Gatekeeper verification passed.
- Publisher-signed Package:
  `packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.7.1-production.ai2service`
  - bytes: `372560699`
  - SHA-256: `df6f95e37a8e48073597b2aa6a5d2aa86c4e4be2f872c34a989d666290f19982`
  - envelope SHA-256: `f68efb66b3d22a0987bf620bc2cf336d50a23a0f21261241d36bf72fa09e38e0`
  - Publisher key fingerprint:
    `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

The detached Publisher signature verifies against the registered production
public key. The embedded DMG is byte-identical to the notarized file.

## Validation

- Focused Runtime, acquisition, installer, distribution and provider suite:
  `104 passed`.
- Isolated installation of the exact signed Runtime and DeepSeek V4.1 Package:
  passed; the Worker reached `running` and dependency locking selected 1.7.1.
- The installed Runtime CPython 3.11 validated the real shared DS4.1 snapshot
  while `.gitattributes` was absent. Schema, family, layout and tensor-payload
  verification all passed.
- Fixed App-Dev and Test Apps were rebuilt through their required scripts and
  passed release-bundle and deep/strict signature verification. App-Dev
  restarted as instance `app-dev`; its native title is
  `AI2Apps-App-Dev: HunterPoints 127.0.0.1:53678`.

## External sources and publication

- ModelScope repository: `ai2apps/desktop-releases`.
- Immutable revision: `75866a48aa1c36cd1f2c646feeda98a449b2c77e`.
- Public URL:
  `https://modelscope.cn/models/ai2apps/desktop-releases/resolve/75866a48aa1c36cd1f2c646feeda98a449b2c77e/ai2apps-runtime-omlx-1.7.1-production.ai2service`.
- ModelScope metadata size and SHA-256 match the local Package. Anonymous first,
  middle, final and single-byte requests returned exact
  `200 + Content-Range` payloads. A full anonymous download also matched all
  `372560699` bytes and the Package SHA-256.
- GitHub Release `package-runtime-omlx-v1.7.1` contains the exact signed
  artifact. The first two upload attempts reached the assets endpoint but failed
  at server-side persistence with `HTTP 500: Error saving asset`; both incomplete
  `starter` records were deleted. A later upload to the same draft succeeded.
  GitHub reports the exact size and SHA-256, all four anonymous Range samples
  returned standard HTTP 206 with matching bytes, and a full anonymous download
  matched the local Package SHA-256.
- Registry submission `13bd374a-066c-48f3-988b-fce01504cebd` and review
  `8d983fe2-c232-493d-9eab-308e299b45eb` are published.
- GitHub source `src_7d826f25-3101-4521-b341-2583678f182b` passed validation
  `val_ebd95a54-9b20-4b97-8db5-ff6b7eb5fb21`: all 48 pieces used strict HTTP
  206 and matched piece-set digest
  `c1bcf1adb5d59c9f98fd1e3411f818e81e7e9b6b3e7f5691a7be0113e0b3c092`.
- ModelScope source `src_9aee54d3-b2de-4f9d-8ece-f9d463c29194` passed
  validation `val_f8d744ff-5fd3-4beb-9470-fa7ef449f54d`: all 48 pieces used the
  approved `200 + Content-Range` compatibility mode and matched the same
  piece-set digest.
- Both immutable external sources are active. Final Repository metadata version
  is `157`, with snapshot digest
  `92b35944484e26cfd4786bfaf88940a1f9f0648450b5e6c6a04acf69f4ef8252`.
- A fresh anonymous Registry client downloaded and verified 1.7.1 against the
  pinned Repository key. Its 372560699 bytes, SHA-256 and detached signature
  envelope exactly match the local final artifact.
- App-Dev Discover independently reports `Local 1.7.0` and `Cloud 1.7.1` with
  the expected Upgrade action, confirming that the development client consumes
  the new production snapshot. The real shared-checkpoint fix was separately
  accepted by the exact signed 1.7.1 Runtime and DS4.1 clean-install smoke above.

## Post-release follow-up

App-Dev later reproduced a second activation issue after the shared snapshot
was reused successfully: the Worker distribution view was read-only, while SSD
activation still needed to add its Package-owned Scope profile and local model
descriptor. The follow-up implementation opens only those metadata directories
for the atomic commit and restores the original read-only modes afterward;
weights and expert payloads remain read-only throughout. This activation step
runs in Desktop Local, not the installed inference Runtime. App-Dev loaded the
fix from its development source, activated the existing 475.27 GB shared
snapshot without downloading, restarted Local, and completed a real local
DeepSeek V4.1 chat response. The immutable Runtime 1.7.1 artifact remains valid;
the Local activation fix belongs in the next Desktop build.
