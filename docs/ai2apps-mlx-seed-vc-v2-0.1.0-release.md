# AI2Apps MLX Seed-VC v2 0.1.0 release receipt

Date: 2026-09-05 (Asia/Shanghai)

## Package release

- Package: `ai2apps/model-seed-vc-v2-mlx 0.1.0`
- Artifact SHA-256: `070db748df6e4aa395120a2a5f3391eb2476e44f8f7e959af14246474af513d2`
- Artifact size: `72201` bytes
- Manifest SHA-256: `23b48be78424ee6220a4a5af5f2301c2e64aad2d46036eeb4bdb022d1ff58172`
- Envelope SHA-256: `5ab18b2361678e49c11590c8c5a2e80c1839fa7ba4cfe65bfd91e84740263e42`
- Runtime dependency: `ai2apps/runtime-omlx >=1.6.2 <2.0.0`
- Cloud submission: `033aebc4-5745-447c-9206-7c73783d4374`
- Review: `8e01acd2-8ef4-4f42-bf61-43af1fd52324`, approved
- Release status: `published`
- Repository metadata immediately after publication: `117`

The Package exposes native MLX Seed-VC v2 zero-shot voice conversion with
request-scoped multipart reference audio. It includes 10-step fast timbre,
30-step quality timbre, and 30-step autoregressive voice profiles plus separate
intelligibility/similarity guidance, length adjustment, and deterministic seed
controls. Reference audio is not persisted as a Voice Profile. The Package
archive does not contain checkpoint weights.

## Checkpoint distribution

- Distribution: `dist_ai2apps_mlx_seed_vc_v2_2122cee1_v1`
- Model: `ai2apps.model.seed-vc-v2-mlx/default`
- Files: `16`; pieces: `267`; estimated bytes: `2236581603`
- Manifest digest: `sha256:568c0c49919eb61c6d29a85f2222cfdecdad1c109914c4f656c510fa9694e92b`
- Hugging Face repository: `Avdpro/MLX-Seed-VC-v2`
- Hugging Face immutable revision: `2122cee1aff2b0e17a843dfa7cdc0464271c43b4`
- ModelScope repository: `ai2apps/MLX-Seed-VC-v2`
- ModelScope immutable revision: `f1c5ab39dbea53e68829d0c3ff8321acdcee16fa`
- Checkpoint submission: `63d6ad3b-e54d-4c93-8a86-485ad2e46ab2`
- Checkpoint review: `f71992a8-4e96-486e-8b9e-09be274d189d`, approved
- Checkpoint index version at publication: `51`

Both immutable provider revisions were metadata-verified before publication.
A fresh anonymous client verified checkpoint index v51 and byte-exact equality
with the locally signed distribution envelope.

## Acceptance

- Focused discovery, audio capability, checkpoint, Worker, multipart, and
  Package regression: `89 passed`.
- Prior real Metal acceptance covered the same final MLX model implementation,
  including 30-step multipart reference conversion. A fresh isolated Platform
  base then installed the exact published artifact digest with Runtime 1.6.2,
  resolved the final distribution path, and reported
  `ai2apps.model.seed-vc-v2-mlx` as `active`.
- A fresh anonymous Cloud client verified public Repository snapshot v117,
  downloaded the Package, verified its Publisher signature and artifact hash,
  and confirmed that the public envelope exactly equals the local envelope.

Production Cloud v1 did not yet accept the newer signed `discovery` and
`modelProfile` top-level manifest fields. Release 0.1.0 therefore uses the
existing explicit, version-bounded Local legacy discovery mapping. The Cloud
upgrade requirement is recorded in
`docs/ai2apps-cloud-package-discovery-schema-requirements.md`; no Cloud code was
modified from this repository.
