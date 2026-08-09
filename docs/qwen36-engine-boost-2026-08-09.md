# Qwen3.6 Engine Boost — Head2 / Tail2

## Runtime policy

Qwen Engine Boost is now supported independently from the DeepSeek policy:

| Product mode | Runtime mode | Qwen Top-8 behavior |
|---|---|---|
| Natural | Exact | Compute all original routes; load every real miss |
| Turbo | Tail2 | Replace nonresident misses among the two lowest-weight routes |
| Blast | Head2 | Protect the two highest-weight routes; replace lower misses |

Replacement selection remains on the GPU. Candidates come from the physical
cache visible to the selected engine: L1/Hot for Flesh, the whole fixed arena
for Arena, and L1 plus L0 Tail for Tiered. Original route weights are retained.
The implementation identifies routes by actual gate weight rather than relying
on the unspecified order returned by Top-K.

Modes are per session. API/WebUI changes are queued and published by the MLX
executor at the next completed-token boundary. Qwen Cache-MoE KV namespaces are
session-owned, so a live exact/lossy change cannot expose mixed-policy KV to a
different session.

## Arena 300-token benchmark

Prompt: a single-file HTML fireworks page. Arena used Top96 + Tail24, adaptive
L1 was Off, and prefill used `dual128-shared`.

| Mode | Decode TPS | vs Natural | Replaced routes | Miss routes after policy |
|---|---:|---:|---:|---:|
| Natural | 32.94 | — | 0 | exact path |
| Turbo / Tail2 | 34.33 | +4.2% | 3,916 | 5,767 |
| Blast / Head2 | 42.74 | +29.7% | 12,770 | 1,240 |

The three output hashes differ by design. Turbo is a modest speed/quality
trade-off; Blast removes substantially more exact expert work and therefore
has materially higher quality risk.

Additional layout smoke tests completed successfully:

- Flesh + Tail2: 96 tokens, 26.85 TPS, no miss in this short scope-matched run.
- Tiered + Head2: 96 tokens, 33.64 TPS, 5,036 routes replaced and 612 SSD
  experts loaded.

Artifacts are under `artifacts/qwen36-boost-2026-08-09/`.

## Head3 / Tail3 experiment

Qwen routes Top-8 rather than DeepSeek V4's Top-6, so two Qwen-only policies
were added without changing the Natural/Turbo/Blast product mapping:

- Tail3 replaces eligible misses among the lowest three routes.
- Head3 protects the highest three routes and may replace the lower five.

The same 300-token workload was run through all three engines:

| Engine | Natural | Tail3 | Change | Head3 | Change |
|---|---:|---:|---:|---:|---:|
| Flesh | 22.61 | 25.96 | +14.8% | 29.01 | +28.3% |
| Arena | 30.98 | 34.10 | +10.1% | 37.24 | +20.2% |
| Tiered | 31.83 | 31.40 | -1.4% | 32.95 | +3.5% |

Arena's direct same-version comparison was:

| Policy | TPS | Change | Routes replaced | SSD experts |
|---|---:|---:|---:|---:|
| Natural | 30.98 | — | 0 | 8,759 |
| Tail2 | 34.30 | +10.7% | 3,916 | 5,767 |
| Tail3 | 34.10 | +10.1% | 5,761 | 4,117 |
| Head3 | 37.24 | +20.2% | 9,594 | 2,030 |
| Head2 | 43.08 | +39.1% | 12,770 | 1,240 |

Tail3 removes more SSD traffic than Tail2 but is not faster here; its extra GPU
candidate/replacement work consumes the I/O saving. Head3 gives up substantial
speed versus Head2, while protecting 50% more high-weight routes and replacing
about 25% fewer routes. It is the more defensible balanced aggressive policy;
Head2 remains the maximum-speed momentary Rush policy.

This matrix also exposed and fixed a backend isolation bug: when
`dual128-shared` was selected, Flesh single-token Decode could enter the dual
prefill branch. Every experimental prefill backend is now explicitly gated to
sequence length greater than one. A regression test protects this boundary.
