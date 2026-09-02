# AI2Apps DeepSeek V4 Flash 2-bit 0.3.3 Direct-L1 release receipt

Release date: 2026-08-28

## Release identity

- Package ID: `ai2apps/model-deepseek-v4-flash-2bit`
- Version: `0.3.3`
- Checkpoint: `mlx-community/DeepSeek-V4-Flash-2bit-DQ`
- Immutable revision: `722bf559b7de93575b2320973cf2002e05bfe6c9`
- Published checkpoint distribution:
  `dist_ai2apps_deepseek_v4_flash_2bit_dq_722bf559_v1`
- Runtime dependency: `ai2apps/runtime-omlx >=1.5.4 <2.0.0`
- Artifact:
  `packages/omlx-model-deepseek-v4-flash-2bit/dist/omlx-model-deepseek-v4-flash-2bit-0.3.3-production.ai2service`
- Artifact SHA-256: `d1d4e5625f1dc00909657bdef190b9ccec6d386cafbbdcf02eb91148fa276f69`
- Artifact size: `50552` bytes
- Publisher ID: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher key fingerprint SHA-256:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

## Delivered behavior

- The model Worker enables native Direct-L1 Decode and DeepSeek V4 Direct
  Prefill by default when used with Runtime 1.5.4.
- Explicit Host values remain authoritative. Setting
  `OMLX_MOE_DIRECT_L1=0` and `OMLX_DEEPSEEK_V4_DIRECT_PREFILL=0` preserves the
  old loader for A/B and rollback.
- The pinned checkpoint, existing Scope Pack, and published checkpoint
  distribution remain unchanged.
- No checkpoint bytes are embedded in the Service Package.

## Validation

- `46 passed`: adapter package, Runtime dependency, Package Contract,
  checkpoint publication, Scope Pack, and release-gate suites.
- The production Publisher signature verifies with the same public key used by
  the published Runtime 1.5.4.
- Archive audit contains 11 metadata/source files and no model weights.
- Runtime 1.5.4 is publicly published and discoverable before this dependent
  Package is submitted.
- Direct-L1 runtime results and strict cache trajectory evidence are recorded in
  `docs/ai2apps-mlx-runtime-1.5.4-direct-l1-glm-release.md`.

## Cloud publication and public read-back

- Submission ID: `e9422fbc-0336-40ed-ae50-cb47dcf3e4e7`
- Review ID: `5dcac6f5-cd78-404b-bcb3-f52719eb8488`
- Review decision: `approved`
- Release status: `published`
- Published at: `2026-08-28T08:01:41.425Z`
- Repository metadata version returned by publication: `88`

Anonymous public Registry read-back, without a browser Cookie, confirmed:

- catalog latest version: `0.3.3`;
- release status: `published`;
- artifact digest and size match the signed local artifact;
- Publisher ID and key ID match the established AI2Apps release context;
- a clean anonymous artifact download has the expected SHA-256;
- the downloaded Package declares Runtime `>=1.5.4 <2.0.0` and checkpoint
  distribution `dist_ai2apps_deepseek_v4_flash_2bit_dq_722bf559_v1`.

The one-release browser Cookie authorization expired immediately after Cloud
publication and was not used for public Registry verification.
