# AI2Apps MLX-GhostV2 Actor Replacement 0.1.0 release receipt

Date: 2026-09-06 (Asia/Shanghai)

## Package release

- Package: `ai2apps/model-face-swap-mlx 0.1.0`
- Artifact: `packages/omlx-model-face-swap/dist/ai2apps-model-face-swap-mlx-0.1.0-production.ai2service`
- Artifact SHA-256: `aa2ddc29cf9de007946883ed441c8e3dc0a6b1e9bf1d3a27ba5596e56a323edf`
- Artifact size: `45926` bytes
- Manifest SHA-256: `e7a1b0029d143193db2c8658b2cbf65cb2268b6db4b78472e48a974eb3f54eae`
- Envelope SHA-256: `8ff73955ff66995db03a23c962ea07ed63cacfbea251a12174a74de48d3ac98b`
- Runtime dependency: `ai2apps/runtime-omlx >=1.6.2 <2.0.0`
- Cloud submission: `89ef128c-c664-4e48-b1c6-39f8ee0aab2f`
- Review: `707f361f-480c-44bd-8aa4-c0f461238e10`, approved
- Release status: `published`
- Repository metadata version at publication and anonymous verification: `119`

The Package exposes native MLX FP16 GhostV2 actor replacement for images and
videos on Apple Silicon. It combines YuNet face detection, CVLFace identity
encoding, stable face tracking, a native NHWC MLX generator, face compositing,
H.264 output, and optional source-audio preservation. GhostV2 is the only
product-facing engine; there is no InSwapper or CPU fallback. Machines with
less than 16 GiB unified memory are rejected before model loading.

The signed archive contains 26 controlled files and no checkpoint weights.
Because the Package artifact itself is only 45,926 bytes, it retains the Cloud
artifact origin. The separately distributed 599 MB checkpoint has the required
Hugging Face and ModelScope sources.

## Checkpoint distribution

- Distribution: `dist_ai2apps_mlx_ghostv2_974d5556_v1`
- Model: `ai2apps.model.face-swap-mlx/default`
- Files: `14`; pieces: `72`; estimated bytes: `599153766`
- Manifest digest: `sha256:fd6bf1200592c92ae78538e4e0a74f8e28030d00e8a4838adb06cb4f54db42d4`
- Signed envelope SHA-256: `50c1acaebcbc133a8f2cbf3a5323a78c23ae6e654ea035ae6abfd09f3f09b185`
- Verification builder: `ai2apps-local/checkpoint-full-dual-download-v1`
- Hugging Face repository: `Avdpro/MLX-GhostV2`
- Hugging Face immutable revision: `974d5556c454219594623de8f7a2eae4e5783ee2`
- ModelScope repository: `ai2apps/MLX-GhostV2`
- ModelScope immutable revision: `627c704a6d196ae6c1d6db6d953d7a4467846b4c`
- Checkpoint submission: `50b5d39a-9457-43ef-a1ac-a3f815f3ad87`
- Checkpoint review: `8e70d0f7-daba-429b-aee6-aaf4f1f021a1`, approved
- Checkpoint index version at publication and anonymous verification: `53`

Both immutable provider revisions were fully downloaded after upload and
compared by exact relative path, size, and SHA-256. The selected 14-file trees
were identical and contained 599,153,766 bytes. A fresh anonymous Checkpoint
Registry client then verified Index v53, the Publisher signature, manifest
digest, and exact JSON equality with the locally signed envelope.

The checkpoint contains the native MLX GhostV2 generator, the oMLX CVLFace
identity encoder, and the oMLX YuNet detector. GhostV2 weights and sources are
BSD-3-Clause; YuNet is MIT. License and notice files are included in the
checkpoint and Package metadata.

## Acceptance

- Ruff passed for the Package and focused tests.
- GhostV2 adapter, geometry, media, tracking, and conversion tests: `24 passed`.
- Package Contract and Worker tests: `30 passed`.
- `git diff --check` passed for the release scope.
- A fresh anonymous Registry client verified Repository snapshot v119,
  downloaded version 0.1.0, verified Repository and Publisher signatures,
  matched the expected artifact SHA-256 and size, and found both artifact bytes
  and envelope JSON exactly equal to the local signed release.
- A clean isolated managed-service installation installed the formal Runtime
  1.6.2 and GhostV2 0.1.0 artifacts, activated both services, started the
  GhostV2 Worker, and recorded an exact `ai2apps.runtime.omlx 1.6.2` dependency
  lock for the model Package.
- Real Runtime 1.6.2 Python 3.11/Metal smoke tests processed an image and a
  five-frame H.264 video, with the video audio stream preserved. The measured
  M5 Max profiles were 39.91 FPS for quality at 960x540, 53.07 FPS for fast
  export at 960x540, and 32.13 FPS for fast export at 1080p.

The production Publisher key ID was
`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`; its public-key fingerprint was
`216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`.
The user explicitly authorized access to the matching historical SecretBackend
namespace for these two signatures. No private key, Cookie, Cloud token, or
administrator password was printed, copied, or stored in the receipt. The
temporary authorization to read the exact current AI2Apps-dev browser Cookie
was used only for the named checkpoint distribution and Package publication,
and ended after anonymous public verification.

Source base commit: `11b5b9ac537e42b1029d1f0148bbbe6a33307f8e` on
`experiment/moe-cache`.
