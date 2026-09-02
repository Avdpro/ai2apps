# AI2Apps oMLX Runtime 1.5.1 development release

Date: 2026-08-25

## Artifact

- Package ID: `ai2apps/runtime-omlx`
- Service ID: `ai2apps.runtime.omlx`
- Version: `1.5.1`
- Artifact: `packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.5.1-development.ai2service`
- File SHA-256: `562fcd70bec7a7fb275a685e9b1a76b267e02f4709bcef3ba2c017f418607428`
- Package digest: `sha256:583d3e26e7bc0c4b2cf77f7635dd4635161ab788ab2a643e9b13950aedf8aa89`
- Size: `434,014,972` bytes
- Distribution signing: local development
- Publisher key ID: `ai2apps:development-1.5.1-qwen`

This is an installable local-development Runtime. It is not the notarized,
Developer ID production release and has not been submitted to the Cloud
Registry.

## Changes from the 1.5.0 development build

- Raises Model Worker multipart file capacity from 8 to 12 so the transport
  matches MiniMax H3 Ref2VA's ordered-reference contract.
- Rejects more than 12 combined reference image/video/audio inputs at the Host
  boundary.
- Validates known reference video/audio durations against the 2–15 second
  contract before Worker invocation.
- Restores native MLX checkpoint validation for `config.yaml` and `config.yml`
  layouts in addition to `config.json`.
- Fixes the development Runtime builder to emit `META/files.json`, Publisher
  attestation and embedded signature. The previous 1.5.0 development artifact
  was a Cloud Contract artifact and could not be installed through the local
  Service Package Manager.
- Adds the `piexif` and `toml` modules required by mflux's real image-pipeline
  import and save paths. Package-install and Worker-start checks alone did not
  exercise those lazy paths.
- Extends the audited mflux MLX-only patch to Qwen Image: optional PiD decoding
  now imports its torch conversion stack only when explicitly requested. The
  normal Qwen generation/edit paths remain torch-free (`mlx-only-v2`).

## Verification

- Focused Runtime, Worker, video and Package tests: `40 passed`.
- Additional Runtime/image contract set: `45 passed`.
- The final archive passed `ServicePackageArchive.inspect`; eight immutable
  files were covered by the signed package index.
- A clean temporary AI2Apps instance installed Runtime 1.5.1 as the dependency
  of `ai2apps.model.flux2-klein-mlx` 0.1.2. Both packages reached `active`.
- After the mflux import-path fix, a clean temporary instance installed the
  final byte-for-byte Runtime artifact together with
  `ai2apps.model.qwen-image-mlx` 0.1.0; both packages reached `active`. The
  installed digests matched the values recorded in this receipt and the Qwen
  receipt.
- The bundled Runtime Python imported Qwen Image without torch and generated a
  real 512 x 512, four-step Q8 image from the pinned 2512 checkpoint. The first
  measured request completed in 7.489 seconds with a 39.81 GB MLX peak.
- The final focused Runtime/Worker/video/image/package suite passed 50 tests.

The source test process emitted a non-fatal MLX shutdown warning because the
sandboxed test runner did not expose a Metal device. The installed Runtime and
FLUX Worker startup smoke ran outside that sandbox and succeeded.
