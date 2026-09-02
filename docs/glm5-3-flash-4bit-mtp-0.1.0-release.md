# GLM-5.3 Flash 4-bit MTP 0.1.0 release receipt

Release date: 2026-08-29 (Asia/Shanghai)

## Runtime dependency

- Package: `ai2apps/runtime-omlx`
- Required version: `>=1.5.5 <2.0.0`
- Public Runtime 1.5.5 artifact SHA-256:
  `41199ca4570bd4e62c3b9a6a11df592a91aa6c25d95536007eabefe3cb5b7784`
- Runtime 1.5.5 was checked from its published DMG with its bundled CPython
  3.11 and native extension. `glm_moe_weighted_sum` was present and its
  result matched route materialization with a maximum absolute error of
  `0.0001220703125`.

## Immutable checkpoint distribution

- Distribution ID:
  `dist_ai2apps_glm5_3_flash_4bit_mtp_06d6c753_v1`
- Hugging Face repository: `Vontra/GLM-5.3-Flash-MLX-4bit-MTP`
- Hugging Face revision: `06d6c7530e8290e20fabdc37a825ce07bdfc490c`
- ModelScope repository: `ai2apps/GLM-5.3-Flash-MLX-4bit-MTP`
- ModelScope revision: `760a9f63f4553ff1f725bddf63ca9f20577e4441`
- Verification mode: `ai2apps-local/checkpoint-metadata-verified-v1`
- Selected files: 53
- Estimated bytes: 181,741,755,745
- 8 MiB pieces: 21,666
- Manifest digest:
  `sha256:8557cfce500607635b94fcc7751e49c23506b37a0e180cf8431cdc2e745066f5`
- Submission: `e9ffe57d-ada9-4095-89bc-20e2f73a44d8`
- Review: `aac6a710-6f91-4b22-a4b9-b1ae4fa2d917`
- Published checkpoint Index version: 34
- Anonymous public verification reported `envelopeExactJson: true`.

## Model Package

- Package ID: `ai2apps/model-glm5-3-flash-4bit-mtp`
- Version: `0.1.0`
- Artifact:
  `packages/omlx-model-glm5-3-flash-4bit-mtp/dist/ai2apps-model-glm5-3-flash-4bit-mtp-0.1.0.ai2service`
- Artifact SHA-256:
  `61ce713872fbca5759e80476c626e90a30bab265e238588f23b936fb76602b31`
- Artifact size: 128,288 bytes
- Submission: `236c37bf-dc5b-4709-b194-ddd18178eda2`
- Review: `4c988ef6-4711-4ac3-88f5-8e683253b6e7`
- Published Registry metadata version: 90
- Public catalog:
  `https://coder.ai2apps.com/v1/registry/packages/ai2apps/model-glm5-3-flash-4bit-mtp/catalog`

The Package exposes exact dynamic Cached-MoE execution, Direct-L1, Hot16,
session-aware multimodal inference, and request/session-switchable natural,
Turbo, and Blast modes. The product contract exposes only cached execution;
the engineering full-resident path remains internal for A/B and rollback.

## Verification

- 54 checkpoint distribution, checkpoint publication, Package policy,
  Package Contract v1, Registry, and GLM Package tests passed.
- Runtime Python 3.11 GLM regression: 42 passed and 1 skipped. The remaining
  weighted-sum case initially selected the workspace Python 3.13 extension;
  it was rerun directly against the published Runtime 1.5.5 CPython 3.11
  extension and passed the numerical parity gate.
- The public artifact downloaded anonymously is byte-identical to the local
  signed artifact and has the expected SHA-256.
- The archive contains no checkpoint `.safetensors` files.
- The public artifact binds Runtime 1.5.5, the published distribution ID, and
  the immutable ModelScope revision above.

The one-time browser Cookie authorization applied only to this distribution
and Package publication and expired when publication completed. Public
readback used no Cookie.
