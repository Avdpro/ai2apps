# AI2Apps MLX-RVC 0.1.0 release receipt

Date: 2026-09-05 (Asia/Shanghai)

## Package release

- Package: `ai2apps/model-rvc-mlx 0.1.0`
- Artifact SHA-256: `fd000d66f963ba40034ac6330ac83ea9d639b3814843b001050de52c8813e3ed`
- Artifact size: `49828` bytes
- Manifest SHA-256: `06657b0838579721959269fc5e32d7b8aa8073d1db6d8aaf90e22da9e12ab8a2`
- Envelope SHA-256: `3e5e5828ce34daf992fe22ab58049c7e48c3dec474cbb0ec1ed9bdfe9cf982ab`
- Runtime dependency: `ai2apps/runtime-omlx >=1.6.2 <2.0.0`
- Cloud submission: `10c2cd64-cf36-41b3-89d6-d2be99d47f87`
- Review: `c1b4aebd-9f04-4dc5-8e12-46505c322485`, approved
- Release status: `published`
- Repository metadata immediately after publication: `116`

The Package exposes native MLX RVC voice conversion and bounded, cancellable
native MLX voice training. Training defaults to FP16 forward/backward compute
with FP32 Adam master weights and optimizer state, supports resumable complete
checkpoints, and returns a safetensors Voice Bundle. The Package archive does
not contain model checkpoint weights.

## Checkpoint distribution

- Distribution: `dist_ai2apps_mlx_rvc_serena_e70_training_738acad9_v1`
- Model: `ai2apps.model.rvc-mlx/serena-e70`
- Files: `19`; pieces: `169`; estimated bytes: `1410906582`
- Manifest digest: `sha256:0740aedee0f5d21b9f6c2ec8fcb40534da0324bec66891c6991a77d5e8cbdfbc`
- Hugging Face repository: `Avdpro/MLX-RVC-Serena-E70`
- Hugging Face immutable revision: `738acad9f58c074d9f817eeac8c7dac9e2eafa1f`
- ModelScope repository: `ai2apps/MLX-RVC-Serena-E70`
- ModelScope immutable revision: `643998a0bf604279e9f9463d4be1e5423a878038`
- Checkpoint submission: `b75574f2-21f0-40cc-94c5-2e8002ea961a`
- Checkpoint review: `35079c48-7f47-4d5b-931f-2f69113b236b`, approved
- Checkpoint index version at publication: `50`

The immutable distribution includes the Serena e70 voice, ContentVec, RMVPE,
retrieval index, and generator/discriminator training initialization. A root
configuration and valid safetensors marker preserve generic Host checkpoint
validation while the Worker loads the explicitly declared component subtrees.
Both provider revisions were metadata-verified before publication. A fresh
anonymous client later verified checkpoint index v51 and byte-exact equality
with the locally signed distribution envelope.

## Acceptance

- Focused discovery, audio capability, checkpoint, Worker, multipart,
  training-route, and Package regression: `89 passed`.
- A fresh isolated Platform base installed the exact published artifact digest
  with Runtime 1.6.2, resolved the final distribution cache path, and reported
  `ai2apps.model.rvc-mlx` as `active`.
- A fresh anonymous Cloud client verified public Repository snapshot v117,
  downloaded the Package, verified its Publisher signature and artifact hash,
  and confirmed that the public envelope exactly equals the local envelope.

Production Cloud v1 did not yet accept the newer signed `discovery` and
`modelProfile` top-level manifest fields. Release 0.1.0 therefore uses the
existing explicit, version-bounded Local legacy discovery mapping. The Cloud
upgrade requirement is recorded in
`docs/ai2apps-cloud-package-discovery-schema-requirements.md`; no Cloud code was
modified from this repository.
