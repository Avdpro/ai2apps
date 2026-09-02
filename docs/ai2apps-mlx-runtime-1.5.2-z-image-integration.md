# AI2Apps oMLX Runtime 1.5.2 and Z-Image integration

Date: 2026-08-26

## Release boundary

Runtime 1.5.2 keeps the shared execution layer model-agnostic. It contains
mflux 0.19.0, MLX 0.32.0 and the deterministic `mlx-only-v3` compatibility
patch. The patch makes optional Z-Image ControlNet and PiD imports lazy, so
normal generation does not require Torch or OpenCV.

The model-specific Metal implementation ships in the separate
`ai2apps/model-z-image-mlx` 0.1.1 package. This prevents future Runtime changes,
including Ref2VA work, from being coupled to Z-Image kernels.

## Model package contract

- model: `Tongyi-MAI/Z-Image-Turbo`;
- Hugging Face revision: `f332072aa78be7aecdf3ee76d5c247082da564a6`;
- ModelScope `master` is the preferred download source;
- operations: text-to-image generation and single-reference image editing;
- profiles: Q8 default, Q4 low-memory, BF16 explicit;
- default geometry: 1024 x 1024, eight steps, guidance zero;
- edit input: one verified PNG/JPEG/WebP data URL, default strength 0.75;
- Runtime dependency: `ai2apps/runtime-omlx >=1.5.2,<2.0.0`;
- concurrency: one request per Metal device.

Q8 and Q4 source checkpoints are converted once into revision-keyed native
mflux checkpoints. Conversion is protected by a process lock, written to a
staging directory, validated, and atomically renamed. A cache receipt fixes
the source revision, bits, group size 64 and mflux version. Insufficient disk or
conversion failure safely falls back to the already loaded source pipeline.

## Optimization contract

On Apple Metal, the package automatically replaces the four repeated
RMSNorm/AdaLN compositions in every timestep-conditioned block with two
audited Metal kernels. Non-Metal or unavailable-Metal environments keep the
upstream MLX graph. Per-step synchronization remains enabled, preserving real
progress, cancellation and timing semantics.

The validated Q8/512 two-prompt median changed from 3.808 to 3.381 seconds
(11.2% faster), with the same quality contract and peak-memory class. The
production package canary completed in 3.789 seconds including its cold first
compiled request, reported the Metal path enabled, and peaked at 13.10 GB after
the post-load memory reset.

## Verification receipt

- Z-Image package unit tests: 6/6;
- package, Runtime, capability and Worker focused suite: 43/43 passed;
- development `.ai2service` build and archive inspection: passed;
- real package-entry Q8/512 Metal canary: passed;
- image capability normalization: persistent cache and Metal fusion flags are
  preserved;
- Python compilation and `git diff --check`: required before handoff.

One pre-existing Registry test currently fails independently because its fake
service envelope omits `payload.publisherKeyId`; the failure reproduces alone
and is outside the Z-Image/Runtime change set.

## Local development candidates

These candidates were built with one-time local Publisher keys for archive and
installation-contract validation. They are not production-signed or submitted
to the Cloud Registry. The temporary private keys and the 1.8 GB Runtime build
directory were deleted after construction; the artifacts and public-key
sidecars remain in `/private/tmp`.

| Package | Path | Package digest | File SHA-256 | Bytes |
| --- | --- | --- | --- | ---: |
| Runtime 1.5.2 | `/private/tmp/ai2apps-runtime-omlx-1.5.2-development.ai2service` | `sha256:fd4cfd828fba9c2efbf1e5cc40c6a44cdb48a50649e27ffec9348ccff9a1602f` | `63eb425285fe4619db2423ef88ec609546b6d6709f0221753cf2da1e5d5c3a41` | 433,968,004 |
| Z-Image 0.1.0 | `/private/tmp/ai2apps.model.z-image-mlx-0.1.0.ai2service` | `sha256:b0cf640478755e585b7359db905b6cf5486233d11901f26c661291cb8f0c1885` | `29bb16c12751f9cdcb9e92900a3c24d3144e6bcd65031e988ae76fe3dbf3dea6` | 14,304 |
| Z-Image 0.1.1 Img2Img | `/private/tmp/ai2apps.model.z-image-mlx-0.1.1.ai2service` | `sha256:62dd9d2cad92418512c696fc0db69020d6fcafe48938ab88fdfc03d832d4961d` | `e95d882f8eec22138db6443b7c7dde02fb697c5d2dd3111e4b7838fab9793c13` | 15,542 |
