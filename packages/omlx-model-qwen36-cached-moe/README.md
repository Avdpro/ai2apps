# Qwen3.6 35B A3B Cached-MoE model package

Adds the pinned MLX 4-bit checkpoint recipe and Scope Pack needed by
AI2Apps/oMLX.

Version 0.3.4 declares optional reasoning, enabled by default, and requires
AI2Apps oMLX Runtime 1.7.5 or later for structured reasoning transport. The
expert store is activated in place without a second conversion copy.
