# AI2Apps MLX-LivePortrait 0.1.0 release receipt

Date: 2026-09-05 (Asia/Shanghai)

## Package release

- Package: `ai2apps/model-liveportrait-mlx 0.1.0`
- Artifact SHA-256: `e3dfe2afb26086bd163b7d5d01f78d3039992c8d95da5ba6367d4a049ca92164`
- Artifact size: `80999` bytes
- Manifest SHA-256: `91e3207c20f09c4e22c6f74662f6f30ce27120777e8d9be5fe73dcf8fcef8ffc`
- Envelope SHA-256: `870a146c187c6424a645e1cea2b54bc78382fc28ec90f62253558cf99c39af87`
- Runtime dependency: `ai2apps/runtime-omlx >=1.6.2 <2.0.0`
- Cloud submission: `25a55bb7-0887-43e3-9f37-5d5d6ed5f343`
- Review: `2e6637f0-b048-48a9-b439-958a06bf46b4`, approved
- Release status: `published`
- Repository metadata immediately after publication: `118`

The Package exposes native MLX LivePortrait portrait animation on Apple
Silicon. It accepts a reference portrait and a driving video, transfers pose
and expression, and emits H.264 MP4 while optionally preserving the driving
audio. The default quality profile uses FP32; BF16 is an explicit fast profile.
FP16 is rejected because validation found non-finite motion values. Unsupported
controls are rejected rather than silently ignored. The Package archive does
not contain checkpoint weights or InsightFace models.

## Checkpoint distribution

- Distribution: `dist_ai2apps_mlx_liveportrait_2bccacd9_v1`
- Model: `ai2apps.model.liveportrait-mlx/default`
- Files: `16`; pieces: `63`; estimated bytes: `520765331`
- Manifest digest: `sha256:98619d82b35e5ac7c7ced34c2b9bda94ca914f23edecd2ef48aa4dbbc905892e`
- Signed envelope SHA-256: `d48b77002e41870e9b3ebb5a7855b9a1d09528143e6f64c393d6f10243b71f14`
- Hugging Face repository: `Avdpro/MLX-LivePortrait`
- Hugging Face immutable revision: `2bccacd9a89eb4b9d41d3664adc88011a3d5abfb`
- ModelScope repository: `ai2apps/MLX-LivePortrait`
- ModelScope immutable revision: `998f93495e933df9bd5eff2d612662c2e4c195a7`
- Checkpoint submission: `7fb25131-37a8-4328-9188-95bbce21b48b`
- Checkpoint review: `b9105434-057b-487b-993e-ae65cb293136`, approved
- Checkpoint index version at publication and anonymous verification: `52`

Both immutable provider revisions were fully downloaded after upload and
compared by exact relative path, size, and SHA-256. The signed verification
receipt records `ai2apps-local/checkpoint-full-dual-download-v1`, both
providers, all 16 files, all 63 pieces, and all 520765331 bytes. A fresh
anonymous client then verified checkpoint index v52 and exact JSON equality
with the locally signed distribution envelope.

The seven MLX model weights use NPZ. The accompanying YuNet detector uses the
parser-free oMLX bundle format with safetensors weights. LivePortrait and YuNet
license and notice materials are included in both the checkpoint release and
the Package metadata.

## Acceptance

- Focused geometry, tracking, media, and Worker adapter tests: `14 passed`.
- Ruff passed for `packages/omlx-model-liveportrait`; `git diff --check` passed.
- A fresh anonymous Registry client verified public Repository snapshot v118,
  downloaded version 0.1.0, verified its Repository and Publisher signatures,
  confirmed status `published`, matched the expected artifact SHA-256 and size,
  and found both the artifact bytes and envelope JSON exactly equal to the
  local signed release.
- Real Metal acceptance of the same packaged implementation processed the
  60-frame 960x540 stress video without frame drops at 6.05 FPS. The output was
  valid H.264, and audio-preservation/no-audio behavior was verified on the
  corresponding media cases.
- The exact Runtime 1.6.2 Python 3.11 environment passed its dependency probe
  and encoded H.264/remuxed AAC through PyAV without OpenCV.

The production Publisher public-key fingerprint used for both signatures was
`216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`.
The temporary authorization to read the current AI2Apps-dev browser Cookie was
used only for the named checkpoint and Package publication operations. No
Cookie, Cloud token, or private key value was printed or copied, and that
authorization ended after anonymous public verification.

Source base commit: `11b5b9ac537e42b1029d1f0148bbbe6a33307f8e` on
`experiment/moe-cache`.
