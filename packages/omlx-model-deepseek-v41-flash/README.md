# DeepSeek V4.1 Flash SSD Cached-MoE model package

This Package binds the published, immutable original-precision FP4/FP8 SSD-ready checkpoint and the lossless text/vision Worker in AI2Apps oMLX Runtime 1.7.5. It activates the bundled expert store in place and does not create a second expert copy. Burst, block and predictive L2 modes remain disabled in the standard profile.

Version 0.1.1 declares optional reasoning, enabled by default. Runtime 1.7.5
maps the signed Package contract to DeepSeek V4.1's native `chat`/`thinking`
modes and separates `<think>` output from the visible answer.

Checkpoint weights are downloaded from the signed distribution and are not embedded in this Package.
