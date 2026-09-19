# Qwen3.8 Flash Next 4-bit Cached-MoE model package

Adds the pinned Vontra MLX 4-bit checkpoint recipe, ten-scope profile, and
multimodal Worker adapter required by AI2Apps/oMLX Runtime 1.7.5 or later.

The checkpoint and generated expert store are acquired and prepared at install
time. They are not embedded in this Package.

This release binds the published SSD-ready checkpoint and requires AI2Apps
oMLX Runtime 1.7.5 or later. Version 0.1.4 declares optional reasoning, enabled
by default, with structured reasoning transport. The expert store is activated in place without a
second conversion copy. Automatic memory selection preserves Balanced Top160
when it fits and downgrades to Lean Top128; Performance Top224 remains an
explicit choice.
