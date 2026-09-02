# Ideogram 4 MLX Model Package

AI2Apps Model Worker package for the optimized native MLX Ideogram 4 pipeline.
It supports text-to-image generation and single-reference SDEdit/Remix on Apple
Silicon. The default Q4 Quality path uses staged model residency, BF16 MLP and
SDPA boundaries, fused QK RMSNorm/MRoPE, and prepared static conditioning.

The first request converts the pinned Comfy-Org FP8 source files into a
revision-scoped native Q4 cache. Qwen3-VL tokenizer/config metadata is bundled;
Qwen weights come from the pinned Ideogram source checkpoint. MLX Runtime
1.5.2 provides the locked mflux 0.19 Flux 2 VAE implementation used by this
package.

`native MLX` here means that inference runs on the custom MLX implementation,
not that it uses an unoptimized baseline. The Worker enables staged residency,
BF16 MLP/SDPA boundaries, fused QK RMSNorm/MRoPE, and static-conditioning reuse
by default. `compileDenoisers` is an optional experimental speed tier and is
off on the default Quality path.

The model weights remain governed by the Ideogram Non-Commercial Model
Agreement. AI2Apps exposes the model and its terms; the user decides whether a
particular use is permitted.
