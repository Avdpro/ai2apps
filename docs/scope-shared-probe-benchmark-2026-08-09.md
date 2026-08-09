# Shared-only scope probe benchmark (2026-08-09)

## Question

Can the target model's own backbone, routers, and shared experts select the
scope, without a separately trained classifier?

The tested probe keeps the first three hash-routed MoE layers exact. In layers
3--42 it runs attention, the router, and the shared expert, but deliberately
skips all routed-expert computation. The exact pass over the same tokens is the
performance oracle: the winning scope is the Top-60 bank with the highest
weighted coverage of the real router choices.

Two objectives are reported:

- `top6`: coverage of all six routed experts, weighted by router weight.
- `head2`: coverage of the two highest-weight experts, matching the aggressive
  Head2 runtime policy more closely.

## Inputs

- Source commit: `49ec271676ba9c14bbebb75da1912e3fcb5fb0f4`, plus the uncommitted
  scope-cache experiment changes in this worktree.
- Model: `/path/to/dmoe/artifacts/deepseek-v4-flash/source`
- Dataset: `/path/to/dmoe/configs/scope-dataset.v2.json`
- Profile: `phase-long128-v1/tiered-top60-global4.json`
- Scopes: 10
- Held-out prompts: 30, three validation/test samples per scope
- Prompt lengths in this sample: 22--34 tokens
- Output: `artifacts/scope-shared-probe-2026-08-09/heldout30-max128.json`

Command shape:

```bash
OMLX_DEEPSEEK_V4_EXPERT_STORE=/path/to/dynamoe/artifacts/moe-expert-major \
./.venv/bin/python scripts/bench_scope_shared_probe.py \
  /path/to/dmoe/artifacts/deepseek-v4-flash/source \
  /path/to/dmoe/configs/scope-dataset.v2.json \
  /path/to/dmoe/artifacts/deepseek-v4-flash/scope-study/phase-long128-v1/tiered-top60-global4.json \
  --samples-per-scope 3 --max-tokens 128 \
  --output artifacts/scope-shared-probe-2026-08-09/heldout30-max128.json
```

The benchmark rejects non-exact lossy routing modes and does not write into the
DMoE repository. The `general` bank is the initial physical cache bank; it is
not supplied to the selector as a label, and exact fallback preserves the
Router decisions used by the oracle.

## Results

| Objective | Exact-oracle agreement | Dataset-label accuracy | Oracle label accuracy | Mean coverage regret | Worst regret |
|---|---:|---:|---:|---:|---:|
| Head2 | 66.7% | 60.0% | 90.0% | 0.948 pp | 9.925 pp |
| Top6 | 70.0% | 70.0% | 96.7% | 0.935 pp | 9.999 pp |

The warmed median exact Prefill took 1.362 s. The shared-only probe took
0.155 s, or 11.0% of the exact pass. The first sample was excluded from timing
medians because it included compilation/cold-start work.

`coding`, `math_logic`, `medical_health`, and `science_engineering` were clean
on all three prompts for both objectives. Most ambiguity occurred among
`business_finance`, `data_ai`, `general`, `humanities_social`, `legal_policy`,
and `writing_creative`.

The semantic dataset label is not always the performance-optimal bank. Even the
exact oracle selected the nominal label only 90.0% (Head2) or 96.7% (Top6) of
the time. Scope selection should therefore be trained and evaluated against
routing coverage or end-to-end quality, not label accuracy alone.

## Confidence gate

Using the difference between the probe's best and second-best scope as its
confidence margin:

| Objective | Margin | Accepted | Oracle agreement | Mean regret | Worst regret |
|---|---:|---:|---:|---:|---:|
| Head2 | >= 0.010 | 17/30 | 88.2% | 0.152 pp | 2.017 pp |
| Head2 | >= 0.020 | 11/30 | 100.0% | 0 | 0 |
| Top6 | >= 0.010 | 19/30 | 94.7% | 0.526 pp | 9.999 pp |
| Top6 | >= 0.020 | 12/30 | 100.0% | 0 | 0 |

The perfect result at margin 0.020 is evidence from only 11--12 accepted
samples, not a calibrated production guarantee.

## Conclusion

The hypothesis is partly correct. The target backbone plus shared expert is a
cheap and useful scope signal, but the current one-pass argmax is not accurate
enough to be the only selector: 30--33% of prompts choose a different bank from
the exact performance oracle, and one failure loses about ten percentage points
of weighted expert coverage.

The appropriate design is a cascaded selector:

1. Run the shared-only probe over every configured leaf scope, with the scope
   count and names read dynamically from the profile.
2. Directly accept only a calibrated high-confidence result.
3. For ambiguous prompts, retain the probe's Top-K candidates and refine them
   with a small amount of routed-expert computation or a hierarchical
   parent-to-child pass.

This keeps the user's intended no-separate-classifier architecture while
avoiding unconditional decisions where the experiment shows it is unsafe.

## Probe-depth sweep

A follow-up run tested whether the shared-only Prefill needs all 43 layers. It
uses the same 30 prompts and exact Top6 oracle, and truncates the probe after a
configured total number of transformer layers. Since layers 0--2 are
hash-routed, a ten-layer probe accumulates seven score-routed layers (3--9).

Output:
`artifacts/scope-shared-probe-2026-08-09/depth-sweep30-top6.json`

| Probe layers | Oracle agreement | Label accuracy | Mean regret | Worst regret | Median time | Oracle in Top-3 |
|---:|---:|---:|---:|---:|---:|---:|
| 6 | 66.7% | 70.0% | 0.821 pp | 5.613 pp | 41.1 ms | 93.3% |
| 8 | 63.3% | 66.7% | 1.201 pp | 10.096 pp | 38.6 ms | 96.7% |
| 10 | 66.7% | 70.0% | 1.044 pp | 10.096 pp | 41.7 ms | 93.3% |
| 12 | 66.7% | 70.0% | 1.044 pp | 10.096 pp | 45.2 ms | 96.7% |
| **16** | **80.0%** | **83.3%** | **0.390 pp** | **4.790 pp** | **51.2 ms** | **93.3%** |
| 24 | 73.3% | 70.0% | 1.020 pp | 10.096 pp | 64.5 ms | 90.0% |
| 43 | 70.0% | 70.0% | 0.936 pp | 10.096 pp | 94.7 ms | 93.3% |

The exact Prefill median in this sweep was 1.094 s. Ten layers cost 3.8% of
that pass and were 2.27x faster than the 43-layer probe. Sixteen layers cost
4.7% and were 1.85x faster than 43 layers.

The result is non-monotonic: more shared-only layers do not necessarily improve
selection. A likely explanation is that omitting routed-expert outputs makes
the probe hidden state increasingly diverge from the target trajectory. On
this sample, layers 3--15 contain a better scope signal than the full
shared-only trajectory.

Ten layers validate the latency hypothesis and are adequate for cheap Top-K
candidate recall, but they do not match the best correctness point. Sixteen
layers are the current default candidate: they improve oracle agreement from
70% to 80%, cut mean regret by more than half, and still take only about 51 ms.
This choice must be revalidated on a larger, longer, multilingual set before it
is treated as fixed.

The runtime configuration now defaults to 16 total probe layers. It can use the
entire model with:

```bash
OMLX_DEEPSEEK_V4_SCOPE_PROBE_DEPTH=43
```

The benchmark follows this setting when `--probe-depths` is omitted; an
explicit `--probe-depths` remains available for experimental sweeps.
