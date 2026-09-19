# Ornith 1.5 35B A3B 4-bit Vision model package

Adds the pinned, byte-equivalent Hugging Face/ModelScope MLX 4-bit + BF16
vision checkpoint and the ten-Scope Cached-MoE profile used by AI2Apps/oMLX.

Full-resident inference is the product default on machines where the model
fits. Exact Top160/Hot32 and Top192/Hot32 Cached-MoE tiers remain available
for smaller-memory or multi-model workloads. Boost is off by default.

This release binds the published SSD-ready checkpoint and requires AI2Apps oMLX Runtime 1.7.2 or later. The expert store is activated in place without a second conversion copy. Version 0.1.3 keeps exact Full mode on the SSD layout by injecting all 256 routed experts from that store during VLM loading.

Version 0.1.4 declares Ornith as a required-reasoning model and requires
Runtime 1.7.5 or later for structured reasoning transport. Its checkpoint-owned
template already opens generation with `<think>`, so no template override is needed.
