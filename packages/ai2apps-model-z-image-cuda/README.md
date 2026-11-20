# Z-Image Turbo CUDA — development source

Pinned official BF16 checkpoints and CUDA Diffusers adapter. Fixed distribution
specs are included, but distribution IDs remain unbound pending publication
and public signature verification. No weights are bundled.

Z-Image Turbo uses the CUDA adapter default of 9 steps, guidance zero, and
rejects negative prompts. Memory values are estimates.

Requires released CUDA Runtime >=0.6.0; formal signed installation remains pending.
Adapter source is copied from spark/cuda_next_image_adapter.py and must stay aligned.
