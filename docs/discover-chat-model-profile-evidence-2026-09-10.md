# Discover Chat model profile corrections

## Runtime-card correction (supersedes system-capacity card values below)

Cards now use `runtimeMemoryBytes`, never `minimumMemoryBytes`. The latter stays
the installation hardware floor and is aligned with `general-chat.yaml`.
Signed profiles may provide the new positive-integer runtime field; old profiles
remain valid, but absent runtime facts display an em dash, not system capacity.

| Model | Card runtime GiB | System minimum GiB | Basis |
| --- | ---: | ---: | --- |
| DeepSeek V4 Flash | 33 | 48 | Package service.yaml Lean Top20 estimate |
| DeepSeek V4 Flash 2-bit | 17 | 32 | Package service.yaml Lean Top20 estimate |
| GLM-5.3 Flash | 55 | 64 | Package service.yaml Lean Top80/Hot16 estimate |
| Ornith Vision | 20 | 32 | Package service.yaml Compact Top160 estimate |
| Qwen3.6 | 9 | 16 | Package service.yaml Lean Top80 estimate |
| Qwen Flash Next | 41 | 48 | Package service.yaml Lean Top128 + PLE mmap estimate |
| Qwen3.8 27B | 22.3 | 24 | Measured text MLX peak; vision can reach 25.7 GiB |

Tier names are included in the card source tooltip. These are configuration-
specific runtime estimates, not a guarantee for every context or the tier auto-
selected on a larger machine. Qwen3.5 and the two CUDA Chat models have no verified
runtime figure here and now display an em dash. Other legacy model modalities
also no longer mislabel system requirements as runtime usage.

## Earlier investigation (historical, not current card values)

The version-bounded Local fallback in `ai2apps/packages/discovery.py` is used
only when a valid signed Publisher profile is absent. No existing Package needs
republishing. Scores remain estimates. Memory is an estimated **system capacity**,
not checkpoint size or measured MLX peak; lower-memory hardware acceptance has
not been established by the 128 GiB reference-host benchmarks.

| Model | Checkpoint payload bytes | System GiB | Evidence / configuration |
| --- | ---: | ---: | --- |
| DeepSeek V4 Flash | 159630016721 | 64 | Cached-MoE stream/patch, 54.17 GiB peak |
| DeepSeek V4 Flash 2-bit | 96531101948 | 48 | Cached-MoE stream/patch, 31.46 GiB peak |
| GLM-5.3 Flash Q4 MTP | 181741755745 | 96 | Top80/Hot16, 62.645 GiB text peak; vision up to 61.939 GiB |
| Ornith 1.5 Vision | 20422417145 | 24 | Top160/Hot32, real VLM peak up to 19.720 GiB |
| Qwen3.6 35B | approximately 19 GiB | 16 | Installed Tiered Top120 smoke, 11.489 GiB peak |
| Qwen3.8 27B NVFP4 | 23444503536 | 32 | Full dense model, screenshot peak 25.672 GiB |
| Qwen3.8 Flash Next Q4 | 111601662416 | 48 | Lean Top128/Hot10 + PLE mmap, 41.15 GiB peak |

Checkpoint sizes are selected runtime payloads, not the small Service archive,
nor prepared expert-store disk usage. Cached-MoE conversion can require substantial
additional disk space. Qwen Next Balanced/Performance need more memory than the
minimum Lean configuration; Ornith full-resident defaults on >=32 GiB machines.
GLM's 62.645 GiB measured peak leaves effectively no system headroom on 64 GiB,
so the conservative system estimate is 96 GiB, not the old 32 GiB placeholder.
Longer contexts, concurrent models, and larger images may require more memory.

## Local evidence

- `ai2apps-checkpoint-distribution-batch-upgrade-2026-08-27.md`: DeepSeek and Qwen27B immutable payload totals.
- `deepseek-v4-l1-update-backends-2026-08-10.md`: avoids old atomic-update transient peaks.
- `glm5-3-flash-4bit-mtp-0.1.0-release.md`: GLM payload total.
- `ai2apps-mlx-runtime-1.5.4-direct-l1-glm-release.md`: real text and multi-turn VLM peaks.
- `ai2apps-ornith15-35b-a3b-4bit-vision-0.1.0-release.md`: Ornith payload total.
- `ornith15-qwen36-cached-moe-optimization-2026-08-29.md`: Ornith VLM cache measurements.
- `qwen36-install-pipeline-release-gate-2026-08-10.md`: checkpoint approximately 19 GiB and installed Tiered smoke.
- `qwen38-real-checkpoint-validation-2026-08-16.md`: dense NVFP4 text and vision measurements.
- `qwen38-flash-next-4bit-package-release-handoff-2026-08-29.md`: selected checkpoint payload total.
- `qwen38-next-cached-moe-checkpoint-2026-08-28.md`: Lean/Balanced/Performance peaks.

Qwen3.5, Qwen2.5 CUDA, and Qwen3 VL CUDA retain their existing estimates pending
matching payload totals / runtime evidence. They are not newly measured facts.
Future signed model profiles retain priority and their existing build contract.
The UI now labels binary units correctly as GiB/MiB and retains one decimal
for GiB instead of rounding all larger models to whole units.
