# oMLX MoE Cache Experiment Plan

Base: oMLX `49ec271676ba9c14bbebb75da1912e3fcb5fb0f4` (`0.5.8.dev1`).

## Architecture seam

The compiled DeepSeek V4 router already returns device-resident global expert
IDs and routing weights. Replace only the expert bank consumed by `SwitchGLU`:

1. Keep global router IDs on device.
2. Translate them through a 256-entry `expert_to_slot` MLX lookup table.
3. Execute the existing oMLX gather-QMM/fused kernels against a smaller,
   immutable resident slot bank.
4. Produce a device-side miss flag without host synchronization on the all-hit
   path.

## Phases

### P0: unchanged baseline

- Benchmark the selected DeepSeek V4 checkpoint in full-resident oMLX.
- Capture exact prompt/token stream, cold TPS, steady TPS, active and peak memory.

### P1: static oracle adapter

- Import a DMoE route trace and build per-layer route unions.
- Keep the three hash layers fully resident.
- Install immutable score-layer slot banks and device lookup tables.
- Require zero misses and exact output/Top-10 parity.
- Gate: at least 85% of the P0 steady TPS with materially lower memory.

### P2: static scope Top-N

- Replace oracle unions with Top30/40/50/60 scope profiles.
- Measure hit rate and all-hit token speed without dynamic replacement.

### P3: exact miss fallback

- Synchronize only when a miss is known to block the current layer.
- Materialize missing experts, replace slots at a safe boundary, and retry.
- Keep the normal all-hit route free of per-layer host reads.

### P4: I/O and static-policy optimization

- Reuse DMoE scope, history, rolling-window, and phase-separated policies.
- Add prefetch and batched telemetry at token/layer-window boundaries.

### Deferred: session-adaptive L1

Dynamic L1 promotion is intentionally deferred until multi-turn Session and
Thread switching have a stable ownership model. The offline result is
positive, but implementing a mutable global L1 before Session isolation would
couple unrelated conversations and create work that must later be redesigned.

The recorded design, evidence, and re-entry gates are in
[`session-adaptive-l1-roadmap.md`](session-adaptive-l1-roadmap.md). Current
runtime work must not enable dynamic L1 replacement by default.

## Non-goals for P1

- Dynamic LRU replacement.
- Lossy routing.
- Reimplementing oMLX attention or MoE kernels.
- Sharing mutable runtime code with the DMoE repository.
