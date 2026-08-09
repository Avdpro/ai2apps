# Lossy scope-cache benchmark — 2026-08-09

## Configuration

- Source commit: `49ec271676ba9c14bbebb75da1912e3fcb5fb0f4` plus the
  uncommitted `experiment/moe-cache` changes described here.
- Model: `/path/to/dmoe/artifacts/deepseek-v4-flash/source`.
- Scope profile: `phase-long128-v1/tiered-top60-global4.json`, scope
  `coding`.
- Prompt: `coding-zh-validation-05`, 25 encoded prompt tokens.
- Decode: greedy, 32 requested tokens, singleton batch.
- Cache: immutable Top60 plus rolling Hot8, ordinary Darwin page cache.
- Cold-request behavior: startup scope warmup disabled. TTFT therefore includes
  the exact Prefill transient path. The table's Decode TPS is the request's
  producer-side 32-token rate; no separate warmed request was injected.

The runs changed only
`OMLX_DEEPSEEK_V4_SCOPE_LOSSY_MODE=exact|conservative|tail1|tail2|head2`.

## Results

| Mode | Prefill TPS | TTFT | Decode TPS | vs Exact | Decode L3 experts | Replaced routes | L3-free layers | Loader time | Peak memory |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Exact | 4.9 | 5.146 s | 8.9 | — | 1,006 | 0 | 0 | 3.498 s | 55.89 GB |
| Conservative ≤10% | 5.1 | 4.916 s | 9.9 | +11.2% | 746 | 275 | 163 | 2.973 s | 55.81 GB |
| Tail1 | 5.2 | 4.837 s | 9.5 | +6.7% | 770 | 348 | 179 | 3.204 s | 55.92 GB |
| Tail2 | 5.3 | 4.713 s | 11.8 | +32.6% | 488 | 619 | 353 | 2.537 s | 55.63 GB |
| Head2 run 1 | 5.4 | 4.624 s | 15.4 | +73.0% | 166 | 1,075 | 666 | 1.801 s | 54.42 GB |
| Head2 run 2 | 4.9 | 5.056 s | 15.2 | +70.8% | 166 | 1,075 | 666 | 1.795 s | 54.42 GB |

Tail2 reduced Decode expert reads by 51.5% and loader-boundary time by 27.5%.
Conservative retained the intended lower-risk behavior and improved Decode by
11.2%. Tail1 changed the generated trajectory, so it loaded slightly more
experts than Conservative despite replacing more routes; lossy runs are not
route-identical after the first changed hidden state.

Head2 averaged 15.3 Decode TPS, 71.9% above Exact. It reduced Decode expert
reads by 83.5% and produced identical cache counters in both repetitions. This
mode replaces every miss outside the two highest-weight routes, so its quality
risk is materially greater than Tail2 even though its speed result is stable.

These are performance results from one held-out prompt, not a quality claim.
An additional real generation completed in Exact and Tail2 modes and produced
slightly different but structurally similar text, as expected. A multi-scope
logit/KL and task-quality evaluation remains required before selecting a
default lossy mode.

## Reproduction

Use the common environment below and set `MODE` to one of the five modes:

```bash
OMLX_DEEPSEEK_V4_SCOPE_PROFILE=/path/to/dmoe/artifacts/deepseek-v4-flash/scope-study/phase-long128-v1/tiered-top60-global4.json \
OMLX_DEEPSEEK_V4_SCOPE_NAME=coding \
OMLX_DEEPSEEK_V4_EXPERT_STORE=/path/to/dynamoe/artifacts/moe-expert-major \
OMLX_DEEPSEEK_V4_SCOPE_HOT_SLOTS=8 \
OMLX_DEEPSEEK_V4_SCOPE_WARMUP_TOKENS=off \
OMLX_DEEPSEEK_V4_SCOPE_LOSSY_MODE=$MODE \
  .venv/bin/python scripts/bench_scope_once.py \
  /path/to/dmoe/artifacts/deepseek-v4-flash/source \
  /path/to/dmoe/configs/scope-dataset.v2.json \
  coding-zh-validation-05 --gen 32 \
  --output artifacts/lossy-scope-2026-08-09/$MODE-32.json
```

Raw results are in `artifacts/lossy-scope-2026-08-09/`.
