# Checkpoint storage inventory — 2026-09-19

## Current state

- Main data volume: 7.3 TiB total, 5.9 TiB used, 1.3 TiB available (82% used).
- Canonical AI2Apps checkpoint cache:
  `~/Library/Caches/AI2Apps/shared/checkpoint-cache-v1`
- The shared cache contains 16 complete signed distributions totaling about
  1.115 TiB logically.
- No files were deleted during this audit.
- Sizes below are path/logical sizes. Hard links and APFS clones mean that
  adding the rows does not equal physical disk usage or reclaimable space.

## Canonical shared distributions

| Checkpoint | Logical size | Current fixed-instance use |
| --- | ---: | --- |
| DeepSeek V4.1 Flash SSD | 475.27 GiB | App-Dev |
| GLM 5.3 Flash SSD | 169.27 GiB | App-Dev |
| DeepSeek V4 Flash SSD | 148.67 GiB | None detected |
| Qwen3.8 Flash Next SSD | 103.94 GiB | Dev |
| Qwen Image Edit | 53.76 GiB | None detected |
| Qwen Image | 53.74 GiB | None detected |
| Z-Image Turbo | 30.59 GiB | None detected |
| Ideogram 4 | 27.46 GiB | None detected |
| Qwen3.8 27B NVFP4 | 21.83 GiB | Test |
| Z-Image Base | 19.13 GiB | None detected |
| Ornith 1.5 Vision SSD | 19.02 GiB | None detected |
| FLUX.2 Klein 4B | 14.88 GiB | None detected |
| Qwen3 TTS 1.7B | 2.87 GiB | Dev |
| SenseVoice | 0.87 GiB | Dev |
| Qwen3 ASR 0.6B | 0.66 GiB | None detected |
| Punctuation restorer | 0.07 GiB | Dev |

The nine distributions with no detected service reference total about
367.9 GiB logically. They can be removed if re-download on next use is
acceptable. A purge must remove every alias for the same immutable object;
deleting only the shared snapshot can release little or no physical space.

## Legacy and duplicate stores

### `~/.omlx` — about 357 GiB

- `models/DeepSeek-V4-Flash`: about 137 GiB
- `models/Qwen3.8-Flash-Next`: about 104 GiB
- `models/Qwen3.8-NVFP4`: about 22 GiB
- `models/Ornith-1.5-Vision`: about 19 GiB
- old Qwen Next expert store: about 70 GiB
- cache data: about 4.9 GiB

These paths were last modified around 2026-08-28 and had no open files during
the audit. AI2Apps fixed instances now resolve their installed distributions
through the shared checkpoint cache. This is a strong cleanup candidate if the
standalone oMLX CLI no longer needs its private store.

### Global download and derived caches

- `~/.cache/huggingface/hub`: about 378 GiB by `du`, 62 repository caches.
- `~/.cache/modelscope`: about 84 GiB.
- `~/.cache/ai2apps`: about 104 GiB, including generated Ideogram Q4/Q8/BF16
  variants and an older Ideogram source checkout.
- `~/.cache/ai2apps-development`: about 26 GiB, primarily a generated Z-Image
  variant.

The HF and ModelScope entries matching signed shared distributions are mostly
hard-linked or cloned already. Removing only one cache view may therefore save
little space. The two old AI2Apps derived-cache trees are regenerable and are
good cleanup candidates.

## Current repository artifacts

`/Users/avdpropang/sdk/omlx-moe-cache` is about 1.9 TiB logically, of which
`artifacts/` accounts for about 1.8 TiB.

### High-confidence removable artifacts

| Path | Logical size | Reason |
| --- | ---: | --- |
| `artifacts/glm5-3-flash-q4-expert-store` | 160 GiB | Obsolete split-v1 GLM store; current GLM distribution uses fused-v2 |
| `artifacts/release-models` | 86 GiB | Published DeepSeek V4 2-bit release staging |
| `artifacts/release-gate` | 87 GiB | Qwen3.6 installation/download test caches |
| `artifacts/qwen3.6-35b-a3b-4bit` | 34 GiB | Two old expert stores; SSD distribution is published |
| `benchmarks/qwen_image/results/worker-cache` | 34 GiB | Regenerable benchmark worker cache |

These paths total about 401 GiB logically. No open files were found.

### Migration tree

`artifacts/chat-checkpoint-migration-20260914` is about 1.2 TiB logically. Its
complete SSD model directories are now APFS-cloned or hard-linked to canonical
cache objects. Several DeepSeek V4.1 experiment scripts still use the migration
path as their default, so the exact complete model directories should be
replaced with symlinks to the shared cache rather than removed blindly.

Old intermediates in this tree are stronger cleanup candidates:

- `glm5-fused-v2`: about 163 GiB
- DeepSeek V4 2-bit SSD staging: about 90 GiB
- Qwen3.6 SSD staging: about 19 GiB
- Ornith fused-v3 staging: about 17 GiB

They total about 289 GiB logically. Published remote copies exist.

### Research datasets and fixtures

DeepSeek V4.1 L2 predictor collections, prefill captures, Metal fixtures and
attention-reuse datasets account for more than 100 GiB. They are regenerable,
but they remain useful if L2 predictor work resumes, so they belong in a second
cleanup tier or cold archive rather than the first deletion batch.

Runtime build output under `packages/ai2apps-runtime-omlx/dist` is about 30 GiB
and was modified on the audit date. Keep the current signed/notarized build;
older published Runtime staging versions can be pruned separately after their
release receipts are checked.

## Other project stores

### `/Users/avdpropang/sdk/dmoe/artifacts` — about 661 GiB

- GLM 5.2 source weights: about 334 GiB
- DeepSeek V4 source plus layer slabs: about 286 GiB
- Qwen3.6 source, conversion and scope artifacts: about 40 GiB

No open files were found. These are old baseline/research inputs superseded by
newer signed SSD distributions, but this repository's policy prohibits editing
the sibling DMoE checkout. Cleanup must be performed from the DMoE project or
as a separately authorized filesystem operation.

### `/Users/avdpropang/sdk/minimaxh3/models` — about 440 GiB physical-path usage

The directory contains roughly 288 GiB of experimental FastH3, OpenVDN and
LightX2V variants, plus development Q4/Q8/CUDA model variants. Published model
packages use immutable distributions. If active MiniMax H3 development is
finished, experimental and development-only variants are a large conditional
cleanup target.

### Smaller stores

- `/Users/avdpropang/sdk/models`: about 74 GiB, mostly Stable Diffusion 1.5,
  Stable Video Diffusion, MimicMotion, DisPose and DWPose.
- `/Users/avdpropang/sdk/testmodeldownload`: about 17 GiB, an old download-test
  directory and a strong cleanup candidate.
- `/Users/avdpropang/sdk/echomimic-v3-mlx/models`: about 35 GiB; keep if
  EchoMimic development continues.
- `~/.ollama`: about 33 GiB across six manifests; remove with `ollama rm` if
  Ollama is no longer used.

## Recommended cleanup order

1. Delete obsolete repository staging and caches: about 401 GiB logical.
2. Delete `sdk/testmodeldownload` and the old AI2Apps derived caches: about
   147 GiB logical.
3. Delete legacy `~/.omlx`: about 357 GiB logical, after confirming standalone
   oMLX private-cache compatibility is no longer needed.
4. Remove migration intermediates and replace retained complete migration paths
   with symlinks to canonical shared snapshots: about 289 GiB logical.
5. Optionally purge the nine inactive shared distributions and every matching
   cache alias: about 367.9 GiB logical.
6. Review DMoE and MiniMax H3 from their owning projects; together they expose
   close to another 1 TiB of old or conditional data.

The first four steps represent about 1.19 TiB of logical paths. Actual disk
recovery will be lower because some files share APFS extents. Free space should
be measured after each batch rather than estimated by summing directory sizes.
