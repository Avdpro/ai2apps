# Qwen Image CUDA — development source

Pinned official BF16 checkpoints and CUDA Diffusers adapter. Fixed distribution
specs are included, but distribution IDs remain unbound pending publication
and public signature verification. No weights are bundled.

Qwen uses one serialized generation/edit dispatcher: changing operation releases
the previous pipeline. Square edits below 1024 use a 1024 internal canvas;
non-square and multi-object quality remain pending. Z-Image Turbo uses guidance
zero and rejects negative prompts. Memory values are estimates.

The Qwen-Image-2.1 BF16 development route uses one pipeline for generation and
editing and preserves alpha in PNG and WebP. Spark validated both operations
using the same loaded pipeline. The 2.1 checkpoint build spec declares the
pinned Qwen Research License, attribution requirements, and mandatory
download confirmation through the existing model license flow.

The 2.1 model entry can be activated after authorization for the intended
distribution and use, publication of the signed checkpoint distribution, and
verification of the public index. Requires released CUDA Runtime >=0.6.0;
formal signed installation remains pending.
Adapter source is copied from spark/cuda_next_image_adapter.py and must stay aligned.
