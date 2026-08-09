# DeepSeek V4 adaptive-L1 update backends (2026-08-10)

## Why the old path peaked

The original `atomic` backend prepared a complete replacement Top60 switch for
every changed layer before publishing any of them. A 40-layer update therefore
kept the complete old and new L1 banks alive at the same time.

Two bounded-memory alternatives are now available:

- `stream`: rebuild complete layers in groups and publish/release each group.
- `patch`: detach mutable backing once, then overwrite only promoted physical
  slots and publish the new ID lookup. This is now the default.

Set `OMLX_DEEPSEEK_V4_L1_UPDATE_BACKEND` to `atomic`, `stream`, or `patch`.
`OMLX_DEEPSEEK_V4_L1_STREAM_LAYERS` controls the stream group size and defaults
to 4. `OMLX_DEEPSEEK_V4_L1_PATCH_VALIDATE=1` enables exact post-write tensor
checks for testing.

Both bounded backends quiesce inference once before mutation. Stream publishes
only complete layer groups, while patch publishes only after a complete layer
slot write. Both paths restore original layer IDs and tensors from the expert
store if a later layer fails.

## 2-bit Top60, 1,024-token comparison

All runs used the same HTML prompt, selected `coding`, triggered one interval
and one turn-end update, promoted the same 2,386 experts, and generated the same
text SHA256 (`6a69ed43588d7baf...`). Patch validation was enabled.

| Backend | Decode | Final 128 | MLX active | MLX peak | Adaptive time | Turn-end wait | L1 bytes |
|---|---:|---:|---:|---:|---:|---:|---:|
| atomic | 10.12 TPS | 10.85 TPS | 31.23 GiB | 50.40 GiB | 3.05 s | 1.44 s | 60.30 GB |
| stream4 | 10.36 TPS | 11.21 TPS | 31.23 GiB | 31.46 GiB | 3.28 s | 1.66 s | 60.30 GB |
| patch + validation | 10.35 TPS | 11.15 TPS | 31.23 GiB | 31.46 GiB | 1.56 s | 0.61 s | 38.12 GB |

Stream removes 18.94 GiB of transient peak memory at the cost of about 0.23 s
across two updates. Patch removes the same peak, reduces L1 read/write bytes by
36.8%, and halves adaptive update time even with tensor validation enabled.
Normal decode throughput did not regress.

## 4-bit compatibility gate

A 256-token 4-bit/MXFP4 run manually triggered a 40-layer, 1,591-slot patch at
token 128 with tensor validation enabled. Every write validated, the generated
text exactly matched the corresponding prefix from the previous 4-bit Off and
Auto runs, and MLX peak stayed at the existing 54.17 GiB baseline instead of
the previous 82.47 GiB Auto peak. The validated update took 1.46 seconds.

## Artifacts

- `artifacts/release-gate/deepseek2bit-html-auto-stream4-1024-memory.json`
- `artifacts/release-gate/deepseek2bit-html-auto-patch-validated-1024-memory.json`
- `artifacts/release-gate/deepseek4bit-html-auto-patch-validated-manual128-256-memory.json`
