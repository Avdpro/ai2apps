# AI2Apps MLX-Demucs 0.1.0 release receipt

Date: 2026-09-06 (Asia/Shanghai)

## Package release

- Package: `ai2apps/model-demucs-mlx 0.1.0`
- Artifact: `packages/omlx-model-demucs/dist/ai2apps-model-demucs-mlx-0.1.0.ai2service`
- Artifact SHA-256: `10bae80790089ca8507f75349c8eb83d2104015df5f50de5177dd86720c91252`
- Artifact size: `34658` bytes
- Manifest SHA-256: `9f20f014a2976cba539a70790159c14f0f2fe33a327c9a2bc67653d59ffb821c`
- Envelope SHA-256: `c2163b3ae8f6b1927cb45c32612028ad6909462c440579feb4937633ac5feef5`
- Runtime dependency: `ai2apps/runtime-omlx >=1.6.2 <2.0.0`
- Cloud submission: `7718b21e-ba01-4017-ae83-160254e0f212`
- Review: `7ab6bb66-71a2-4aff-a2db-b68a4b2a76cc`, approved
- Release status: `published`
- Repository metadata version: `120`

The Package exposes native HTDemucs source separation through
`audio_processing/audio_process`. It declares native four-stem music output,
plus explicitly derived vocals/instrumental and dialogue/background profiles.
Unknown profiles are rejected. Results are returned as a ZIP containing PCM16
WAV stems and `ai2apps.audio-separation-result/v1` JSON with container-relative
paths and native-versus-pipeline provenance.

The Package artifact is only 34,658 bytes and therefore retains the permanent
Cloud origin rather than duplicating it to external Package mirrors. Its much
larger checkpoint is independently distributed from Hugging Face and
ModelScope.

## Checkpoint distribution

- Distribution: `dist_ai2apps_mlx_demucs_htdemucs_d4519e24_v1`
- Model: `ai2apps.model.demucs-mlx/default`
- Files: `2`; pieces: `21`; estimated bytes: `168007757`
- Manifest digest: `sha256:96aa8bd0670e3d0a567224abe17d3ab86c79b24e98bb82101a3c2160ee4e6c1e`
- Signed envelope SHA-256: `bfc8772f172638a0aeb8cdc25fd409ac66d6708590d2995c754e7742ecd92ad0`
- Verification receipt SHA-256: `8f37b0fe0d55b9c30ae59b27c600e93d02cce05251505e5982bddf5b452e788c`
- Verification builder: `ai2apps-local/checkpoint-full-dual-download-v1`
- Hugging Face: `mlx-community/demucs-mlx@d4519e24ddc2dd4a11d56a193092433d852c3961`
- ModelScope: `mlx-community/demucs-mlx@3e2b356248c71ec999090ca6e5eebc65654b8893`
- Submission: `ad3524b2-34a9-4244-83fd-f77328b5620f`
- Review: `6210fcc3-dcbd-41b7-bd1d-699c6710a2f7`, approved
- Checkpoint Index version: `54`

Both selected trees were fully downloaded and matched by exact path, size, and
SHA-256. Anonymous verification confirmed the signed Index, Publisher key,
manifest digest, and exact envelope JSON. During the clean installation smoke,
both providers supplied actual pieces: 84,119,785 bytes from ModelScope and
83,887,972 bytes from Hugging Face.

Demucs architecture and checkpoint terms are MIT. The Package includes the
upstream license notice and records that the ModelScope model card says MIT
while its repository metadata currently labels the license as `other`.

## Acceptance

- Focused Package, checkpoint, provider, and separation tests: `57 passed`.
- Ruff and `git diff --check` passed for the release scope.
- Direct Metal Worker smoke processed a 9-second stereo fixture and produced a
  valid dual-track ZIP.
- Clean Managed Service installation used the formal Runtime 1.6.2 and Package
  artifacts, locked the exact Runtime digest, acquired the public distribution,
  restarted with an authorized read-only checkpoint, and returned HTTP 200.
- The managed result contained two 9.0-second, 44.1 kHz stereo WAV files plus
  relative-path JSON; residual reconstruction maximum error was `7.45e-9`.
- Anonymous Registry verification downloaded snapshot v120 and found the
  artifact bytes and envelope JSON exactly equal to the local signed release.

The production Publisher key ID was
`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`; its public-key fingerprint was
`216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`.
The user explicitly authorized the historical Publisher Keychain record and
the exact current AI2Apps-dev browser Cookie only for this distribution and
Package release. No private key, Cookie, Cloud token, or administrator password
was printed, copied, or stored. That temporary authorization ended after the
anonymous verification above.

Source base commit: `11b5b9ac537e42b1029d1f0148bbbe6a33307f8e` on
`experiment/moe-cache`.
