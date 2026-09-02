# Ornith 1.5 35B A3B 4-bit Vision model package

Adds the pinned, byte-equivalent Hugging Face/ModelScope MLX 4-bit + BF16
vision checkpoint and the ten-Scope Cached-MoE profile used by AI2Apps/oMLX.

Full-resident inference is the product default on machines where the model
fits. Exact Top160/Hot32 and Top192/Hot32 Cached-MoE tiers remain available
for smaller-memory or multi-model workloads. Boost is off by default.
