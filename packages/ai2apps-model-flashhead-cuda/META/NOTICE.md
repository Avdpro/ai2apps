FlashHead CUDA release preparation

Soul-AILab/SoulX-FlashHead, pinned commit 9bc03de06bb0de82cd6bc477804512ae06144bf2. Apache-2.0 checkpoint terms are preserved in LICENSE-Apache-2.0.txt.

AI2Apps shared validation/lifecycle and checkpoint helpers are reused from the local FlashHead MLX Package. The checkpoint import alone is redirected; CUDA code adds request RNG isolation and structured OOM recovery. Native upstream code and dependencies belong to the CUDA Runtime, not this model source.
