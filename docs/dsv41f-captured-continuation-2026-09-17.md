# DS4.1F forward-only captured continuation — 2026-09-17

Status: performance gate failed; not accepted for default use. The performance gate is not satisfied by correctness alone.

Required behavior: no packet admission or fallback; GPU stops at the actual
missing Router, CPU loads its missing experts, and the same multi-layer executor
continues. An all-miss token must not rebuild or encode its suffix repeatedly.

Implementation is isolated in
`experiments/dsv41_analysis/l2_predictor/resume_probe/` and the patched MLX build
`artifacts/dsv41-resume-replay-mlx-build`. It does not replace installed MLX,
production Runtime defaults, or model Packages.

The token graph and ICBs are constructed once. Each Gate records a continuation
position and its six-slot output buffer. On a miss, the existing native SSD bank
loads only the required experts, the host patches those six indices, and the
GPU resumes the recorded commands. Attention, Router, KV updates and cache policy
updates before the miss are not repeated. Future graph handles remain valid;
there is no metadata rollback or Python suffix reconstruction.

Resource handling uses pooled ICBs and parameter arenas, a token Residency Set,
and allocation retirement that preserves normal MLX buffer donation. Captured
commands keep their allocations valid until completion. Resume ranges use actual
command counts. The retained v12 implementation waits for command-buffer completion before changing
cache payload or recycling command resources. Shared Event, asynchronous retirement,
queue-level residency, native-prefix and submission-granularity variants were tried
separately and did not establish a passing performance result.

An optional development variant also pre-encodes the known-safe current MoE to
next Router as a native command buffer. It still submits the conditional suffix
and never uses packet control. Its performance must be measured independently;
it is not assumed better.

Reproduction:

```sh
.venv/bin/python experiments/dsv41_analysis/l2_predictor/resume_probe/build_replay_backend.py
.venv/bin/python experiments/dsv41_analysis/l2_predictor/resume_probe/launch_replay.py \
  --output artifacts/example-replay --prompt 'Explain why a database index speeds up queries.' \
  --decode 32 --prefill-slots 64 --logits-mode hash --expert-no-cache
```

The floor benchmark invalidates all real expert tags at each layer. Every layer
actually loads all six experts through the same native SSD loader and strict
F_NOCACHE as the packet reference. Both paths use fixed input tokens, L0=8,
L1=40, eviction_dual, exact Top6 and the same checkpoint. The fixed-token suffix
includes EOS/repetition because it reuses the existing timing fixture; it is a
performance/parity fixture, not a dialogue-quality benchmark.

Results and source/library hashes are retained in
`artifacts/dsv41-resume-replay-20260917/`. The first frozen ABBA result (v12) is a
failure: all-miss 2.00977 vs 2.05591 TPS, natural 3.95339 vs 4.84065 TPS. It is not
relabelled as success, nor overwritten. Its full-state comparison passed, and
all-miss32 has 1,280 distinct layer executions and 1,312 host boundaries, with zero
packet checks, zero attention replays, identical SSD bytes and bank fence counts.
Subsequent variants are development experiments until another frozen paired gate
passes.


## Retained implementation and acceptance result

Retained source matches the frozen `acceptance-source/resume_probe/` v12 for the
execution implementation. Later variants are archived under
`development-last-source/`; their results are retained but they are not the
current implementation. Source base commit:
`8ff6faf966d56ae92d21bf2d36d9512da5745784`, branch `experiment/moe-cache`, with
pre-existing worktree modifications. No commit/tag/publication was made.

| Workload | Packet full TPS | Captured full TPS | Difference | Packet steady TPS | Captured steady TPS |
|---|---:|---:|---:|---:|---:|
| Forced real all-miss | 2.05591 | 2.00977 | -2.24% | 2.06932 | 2.02710 |
| Natural miss | 4.84065 | 3.95339 | -18.33% | 5.15904 | 4.15793 |

Each cell pools two fixed-input 32-token runs in ABBA order; steady excludes the
first four decode steps. Both controls and candidates use the isolated v4 MLX
library, unchanged mathematical kernels, identical checkpoint and loader, strict
F_NOCACHE, and the same forced input tokens. Natural full-state comparisons cover
all saved tensors and host cache metadata for four decode steps, not just token
agreement. The source/library hashes used for the ABBA run are in
`acceptance-hashes.json`; detailed timings and IO counts are in
`acceptance-results.json`.

This is a concrete repair of the repeated-suffix construction bug, **not** a
successful completion of the requested non-regression performance gate. No
production Runtime or Package default has been switched. In particular, the
natural-miss regression means this cannot be justified as a default replacement
by calling the all-miss difference “small.”

Apple API references used for implementation:
[ICB compute commands](https://developer.apple.com/documentation/metal/mtlindirectcomputecommand),
[Residency Sets](https://developer.apple.com/documentation/metal/simplifying-gpu-resource-management-with-residency-sets).
