# Lossy scope-cache Decode modes

The lossy modes are opt-in and apply only to score-routed, single-token
Decode. Exact routing remains the default, and Prefill remains exact.

Set `OMLX_DEEPSEEK_V4_SCOPE_LOSSY_MODE` to one of:

- `exact` (or unset): load every L3 miss exactly.
- `conservative`: inspect the two lowest-weight Top-6 routes and replace an
  L3 miss only when its normalized routing share is at most 10%.
- `tail1`: replace an L3 miss when it is the lowest-weight Top-6 route.
- `tail2`: replace L3 misses among the two lowest-weight Top-6 routes.
- `head2`: protect only the two highest-weight Top-6 routes; replace every L3
  miss among ranks 3 through 6. Only a Top-2 miss can reach SSD.

`aggressive-1` and `aggressive-2` are aliases for `tail1` and `tail2`.
`protect2` is an alias for `head2`.
Override the conservative threshold with
`OMLX_DEEPSEEK_V4_SCOPE_LOSSY_THRESHOLD`.

Replacement happens before the resident miss mask is evaluated. The GPU:

1. sorts the six selected routes by their actual router weights;
2. masks candidates to the immutable Top60 plus the current rolling Hot8;
3. excludes experts already present in the original Top-6;
4. picks the highest bias-corrected router-score candidate; and
5. replaces only eligible L3 routes while retaining their original gate
   weights.

No selected expert ID, route weight, or replacement decision is copied to the
CPU. Replacement counters are read at the existing per-layer miss-detection
barrier. `scripts/bench_scope_once.py` reports replaced routes, avoided L3
misses, and layers whose L3 access was eliminated.

Example:

```bash
OMLX_DEEPSEEK_V4_SCOPE_LOSSY_MODE=conservative \
OMLX_DEEPSEEK_V4_SCOPE_LOSSY_THRESHOLD=0.10 \
  .venv/bin/python scripts/bench_scope_once.py MODEL DATASET SAMPLE \
  --gen 32 --output artifacts/lossy-scope/conservative.json
```
