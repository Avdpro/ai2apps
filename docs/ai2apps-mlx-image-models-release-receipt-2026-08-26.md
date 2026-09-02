# AI2Apps MLX Image Models Release Receipt

Date: 2026-08-26 (Asia/Shanghai)

## Result

The following production releases were signed by the official AI2Apps Publisher, approved, published, and confirmed visible in the public AI2Apps Cloud Registry catalog:

| Package | Version | Artifact SHA-256 | Size | Submission ID |
| --- | --- | --- | ---: | --- |
| `ai2apps/runtime-omlx` | `1.5.2` | `ba47b1b722545176da8177e61ce9a7df15738e45019efe7ee67f1d2f4c4de8ad` | 455,221,956 | `f2ce6a99-9124-4315-8b07-676e65d677fb` |
| `ai2apps/model-flux2-klein-mlx` | `0.1.2` | `33950638e56e5d3ad9c27d0bb4aa92f32934ea9b44fc391488088894b48fd14f` | 18,177 | `b48e629b-ec6b-4f01-a04d-64883d6d62a7` |
| `ai2apps/model-qwen-image-mlx` | `0.1.0` | `bbfc3a5aec9ee99b10e6a6af3201175e23f884e24c42a7b31fce2c99bf679f9e` | 16,771 | `bd6984d7-c7b0-46ff-8dbd-bf111ad69c67` |
| `ai2apps/model-z-image-mlx` | `0.1.1` | `4ffb4df1d11207025e7dffff7d0a155776407f59ad876f5e21419e3e19c11fef` | 16,170 | `ae62cb55-94e6-484d-9d59-8787f4fea834` |
| `ai2apps/model-ideogram4-mlx` | `0.1.0` | `67a599fa8aa5100ed0ab295fa4c3a400d6c65b623ca995777d90f5e2bbbaaa08` | 3,801,830 | `5a932eb0-a1df-4799-a721-bf9b769aee4b` |

The final repository metadata version after publication was `60`.

## Runtime trust evidence

- Final notarized DMG SHA-256: `3a7519cf43d33f1b9f29bed3a8673b813149931f5c3ef5bd8f0ca22386073b7e`
- Apple notarization submission: `1a499a6c-e417-4549-aa48-922aca630729`
- Notarization status: `Accepted`
- Staple validation: passed
- Host `codesign --verify --strict`: passed
- Host Gatekeeper assessment: `accepted`, source `Notarized Developer ID`
- Runtime layers inspected: MLX `0.32.0`, mflux `0.19.0`, ai2apps `0.1.0`

## Publisher evidence

- Publisher ID: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Public-key fingerprint: `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`
- All five detached Ed25519 envelopes were verified against the exact published artifact bytes.
- No private key value was printed or persisted outside the existing macOS Keychain record.

## Verification gates

- 59 targeted Runtime/model/capability tests passed before release packaging.
- 25 Package Contract and Registry tests passed.
- 15 inference Runtime package tests passed.
- Each final Cloud Contract model artifact was installed in a separate clean platform instance with the final Runtime artifact.
- Runtime `1.5.2` materialized and activated after the required platform restart.
- FLUX, Qwen Image, Z-Image, and Ideogram 4 Workers all reached `running`.
- Every model dependency lock resolved to Runtime digest `sha256:ba47b1b722545176da8177e61ce9a7df15738e45019efe7ee67f1d2f4c4de8ad`.
- Public Registry catalog queries returned each target as the latest published version with the expected SHA-256.

The clean-install release gate intentionally did not download checkpoints or run paid/large-weight generation. Prior implementation benchmarks and inference evidence remain in the model implementation documents; this release gate verifies exact production artifacts, trust, installation, dependency resolution, and Worker startup.

## Release-gate corrections

- The smoke tool now supports detached Cloud Contract packages directly through the same Contract-to-Service conversion used by the Registry installer.
- Developer ID DMG installation relies on Gatekeeper for the notarized media assessment; final host validation also confirmed compatibility with the existing extra `codesign` check.
- Ideogram 4 is described as single-image Remix editing in the public catalog. Multi-reference editing was not claimed as a verified `0.1.0` capability.

## Authorization closure

The temporary authorization to read the AI2Apps dev browser session Cookie was used only for these five release operations and final status checks. Its use ended after public catalog verification. No Cookie value was printed or copied into this receipt.
