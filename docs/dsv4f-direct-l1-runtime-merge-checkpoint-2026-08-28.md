# DSV4F Direct-L1 Runtime merge checkpoint — 2026-08-28

## Status

This is the accepted local oMLX experiment to carry into the next AI2Apps oMLX
Runtime upgrade. It is intentionally **not** merged into, built as, or published
as the current Runtime package. The current formal Runtime remains unchanged.

- Research branch: `experiment/moe-cache`
- Base commit: `66736ccaed462e6f366b03d15c10aec5b43213ff`
- State: base commit plus the working-tree changes named below
- Local MLX used for validation: `0.32.0`
- Model: DeepSeek-V4-Flash 2-bit expert-major checkpoint
- Expert store: existing compute-ready six-segment `.moe` records; no new
  checkpoint conversion is required
- Validation: 313 benchmark/DeepSeek/GLM cache tests passed

## Code to carry forward

Runtime-side implementation:

- `omlx/custom_kernels/glm_moe_dsa/csrc/expert_loader.h`
- `omlx/custom_kernels/glm_moe_dsa/csrc/expert_loader.cpp`
- `omlx/custom_kernels/glm_moe_dsa/csrc/bindings.cpp`
- `omlx/custom_kernels/glm_moe_dsa/csrc/CMakeLists.txt`
- `omlx/custom_kernels/glm_moe_dsa/fast.py`
- `omlx/cache/direct_l1.py`
- `omlx/patches/deepseek_v4/scope_cache.py`
- `omlx/patches/glm5_next_cache/dynamic_cache.py`

Benchmark and regression support:

- `scripts/bench_scope_once.py`
- `omlx/admin/benchmark.py` (`OMLX_BENCH_PROMPT_PREFIX` only)
- `tests/test_direct_l1.py`
- `tests/test_glm5_native_expert_loader.py`
- `tests/test_benchmark.py`

Do not copy modules from the sibling DMoE checkout. Continue to consume its
Scope profile and dataset only through explicit paths.

## Storage and native ABI contract

The native loader performs six-vector positional `preadv` directly into
evaluated, row-contiguous MLX array backing. DSV4F records must remain in this
exact on-disk order:

1. `gate_proj.weight`
2. `gate_proj.scales`
3. `down_proj.weight`
4. `down_proj.scales`
5. `up_proj.weight`
6. `up_proj.scales`

The sum of the six destination slot sizes must equal `record_bytes`. The loader
does no dtype conversion, reshaping, or CPU-to-GPU copy. Unified-memory backing
is already in its final compute shape. GLM keeps the historical
`preadv_fused_experts` symbol; Python exposes the layout-neutral
`preadv_expert_segments` alias.

When upgrading MLX, rebuild the extension against the new Runtime's exact
Python, MLX headers/libraries, deployment target, and arm64 ABI. Never carry a
previous `_ext*.so` or linked dylib into a new Runtime unchanged.

## Experiment controls

```bash
# Decode/L1: 0 = legacy, 1 = require native, auto = native when available
OMLX_MOE_DIRECT_L1=1

# Prefill transient banks: 0 = legacy staging/stack, 1 = final-shape direct
OMLX_DEEPSEEK_V4_DIRECT_PREFILL=1

# Fixed cross-process benchmark token sequence
OMLX_BENCH_PROMPT_PREFIX=BENCH-DIRECT-PREFILL-AB
```

The legacy paths must remain available for rollout A/B and rollback. A forced
`OMLX_MOE_DIRECT_L1=1` must fail loudly if the native symbol is unavailable;
it must never silently report a direct run while using staging.

## Accepted performance gates

All comparisons use exact routing. The final strict runs have identical cache
trajectories between the compared paths.

### Decode loader

Fixed 25-token coding prompt, 64 generated tokens:

| Path | Decode TPS | Loader time | Peak |
|---|---:|---:|---:|
| Legacy staging/stack | 8.25 average | 5.786 s | 55.933 GB |
| Direct SSD-to-L1 | 11.10 average | 3.928 s | 55.865 GB |

Acceptance: +34.5% Decode TPS, -32.1% loader time, and the same 1,920
Decode-expert loads.

### Direct Prefill

Both arms below already use Direct Decode; only the Prefill switch changes.

| Prompt | Legacy Prefill | Direct Prefill | TTFT change | Peak |
|---:|---:|---:|---:|---:|
| 128 | 13 tok/s average | 18 tok/s average | 9.847 -> 7.173 s | 56.2 GB direct |
| 4,096 | 158 tok/s | 219 tok/s | 25.863 -> 18.668 s | 62.5 GB |
| 10,000 | 217 tok/s | 266 tok/s | 46.142 -> 37.521 s | 65.4 GB |

The isolated 10K A/B used the same fixed token sequence and loaded 15,296
Prefill plus 553 Decode experts in both arms. Loader time changed from 21.339
to 15.926 seconds; Decode remained 8.1 TPS. Do not use the earlier sequential
4K-then-10K run as a gate because the second case showed thermal/scheduling
drift.

## Correctness gates for the Runtime merge

The upgraded Runtime must pass all of the following before enabling the new
path by default:

1. Rebuild and load the native extension in the packaged Runtime environment.
2. Run the real-store tensor check: load at least two nonadjacent experts into
   nonmatching physical slots and compare every element of all six tensors with
   legacy record views.
3. Run `tests/test_glm5_native_expert_loader.py` and
   `tests/test_direct_l1.py` on a Metal-capable host.
4. Run the complete DeepSeek/GLM cache regression set used by this checkpoint.
5. Repeat fixed-prompt Decode `OMLX_MOE_DIRECT_L1=0/1`; require identical
   expert counts, fallback calls, and Hot8-only calls.
6. Repeat fixed-prompt Prefill
   `OMLX_DEEPSEEK_V4_DIRECT_PREFILL=0/1`; require identical Prefill/Decode
   expert counts and unchanged Decode TPS.
7. Repeat isolated 4K and 10K cold-SSD runs with `F_NOCACHE`; record TTFT,
   Prefill TPS, Decode TPS, loader time, active memory, and peak memory.
8. Verify a Runtime Package install/launch/health/stop cycle before publication.

Regressions that invalidate the merge include tensor mismatch, changed cache
trajectory, silent native fallback, loss of the legacy A/B path, increased peak
above the target machine's admission limit, or a material loss against the
accepted TPS gates.

## Deferred work

Dual-arena Prefill is not part of this accepted checkpoint. The current Direct
Prefill implementation is synchronous. A future prototype may write the next
inactive bank while Metal evaluates the active bank, but it must be benchmarked
and accepted independently before entering the Runtime merge.

Full raw commands and benchmark notes are in
`artifacts/direct-l1-ab-2026-08-28/README.md`.
