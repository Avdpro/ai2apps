# Qwen3.8 27B CUDA

Version 0.2.0 candidate uses native NVFP4 for 168 MLP projections on GB10.
The remaining FP8 projections are dequantized to BF16. Requires Runtime
0.3.0 and its nvfp4-sm121 capability. Published 0.1.0 remains the BF16 baseline.

Checkpoint identity and signed distribution are unchanged. Independent Worker
and Registry/Host acceptance must pass before this candidate is released.
