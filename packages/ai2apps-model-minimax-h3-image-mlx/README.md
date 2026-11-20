# MiniMax H3-Image MLX 0.1.1

Maintained source recovered from the original 0.1.0 Package artifact, SHA-256
`b9dec1ceb5ce52ef6d2bc8aeca0a454273c728074bb570c45f3388b3d5525b19`.
No source baseline, instance database or model state is copied into Dev/App-Dev.

Supports generation and 1–16 ordered reference images for editing. The existing
pipeline already packs multiple vision features and VAE latents; the adapter and
capability count now expose that implementation. Reference order defines Picture
1, Picture 2, etc. Single-reference cache behavior is preserved; multi-reference
vision features are recomputed.

Weights and dependencies are unchanged: MiniMaxAI/MiniMax-H3-Image at
5f90473023975e6271b0ed1dd84c4e88e4bbc6d3, distribution
dist_ai2apps_minimax_h3_image_5f904730_v1, and the existing H3 shared 4-bit text
encoder. No replacement checkpoint or new conversion is required.

Client reference transport currently accepts PNG/JPEG/WebP, up to 24 MiB decoded
in total. The direct Worker input limit is 64 MiB. Model output stays 512–2048 per
side in multiples of 32, six steps, guidance 1. Transparent output is unsupported.

Publication and real multi-reference inference must pass the standard release
gates; fixture adapter tests do not constitute model inference acceptance.
