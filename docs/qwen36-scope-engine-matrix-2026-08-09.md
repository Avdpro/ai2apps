# Qwen3.6 scope × engine × adaptive-L1 matrix (2026-08-09)

## Configuration

- Source commit: `49ec271676ba9c14bbebb75da1912e3fcb5fb0f4`, plus the
  uncommitted Qwen3.6 cache-engine worktree changes.
- Model: `qwen3.6-35b-a3b-4bit/source`.
- Profile: `joint-hotsets-v3/decode-top120.json`.
- Physical layout: Top-96 L1; Arena/Tiered additionally use Tail-24.
- Adaptive policy: Auto40, one update in every 512-token run.
- Prompt: the first representative prompt for each scope from
  `scope-prompts.v1.json`, rendered with the model chat template.
- Decode: 512 greedy tokens, temperature 0, independent cold process per run.
- TPS includes the in-generation adaptive update pause.

Command:

```bash
./.venv/bin/python scripts/bench_qwen36_scope_engine_matrix.py \
  /path/to/dmoe/artifacts/qwen3.6-35b-a3b-4bit/source \
  /path/to/dmoe/artifacts/qwen3.6-35b-a3b-4bit/scope-study/joint-hotsets-v3/decode-top120.json \
  artifacts/qwen3.6-35b-a3b-4bit/expert-store-fused-v2 \
  /path/to/dmoe/configs/scope-prompts.v1.json \
  --output artifacts/qwen36-scope-engine-matrix-2026-08-09 \
  --max-tokens 512 --experts 96 --tail 24 --max-promotions 40 \
  --full-resident-oracle
```

## Decode TPS

Each cell is `Off / Auto` TPS. The percentage is Auto relative to Off.

| Scope | Flesh | Arena | Tiered |
|---|---:|---:|---:|
| business_finance | 27.10 / 28.01 (+3.37%) | 34.30 / 34.13 (-0.47%) | 35.20 / 35.54 (+0.96%) |
| coding | 21.90 / 24.62 (+12.41%) | 29.88 / 31.51 (+5.45%) | 32.62 / 32.92 (+0.94%) |
| data_ai | 26.87 / 25.44 (-5.34%) | 32.32 / 33.83 (+4.67%) | 34.76 / 34.58 (-0.51%) |
| general | 24.17 / 25.22 (+4.35%) | 31.66 / 31.79 (+0.43%) | 31.99 / 31.78 (-0.66%) |
| humanities_social | 24.14 / 28.32 (+17.31%) | 33.85 / 30.82 (-8.95%) | 33.80 / 31.06 (-8.10%) |
| legal_policy | 24.76 / 28.51 (+15.17%) | 34.25 / 35.05 (+2.35%) | 35.29 / 35.95 (+1.86%) |
| math_logic | 23.15 / 25.37 (+9.60%) | 29.16 / 29.88 (+2.47%) | 28.62 / 29.35 (+2.57%) |
| medical_health | 24.34 / 25.01 (+2.74%) | 30.67 / 30.11 (-1.81%) | 31.68 / 30.31 (-4.32%) |
| science_engineering | 24.84 / 26.63 (+7.20%) | 31.25 / 31.68 (+1.38%) | 31.09 / 31.36 (+0.89%) |
| writing_creative | 23.79 / 26.12 (+9.79%) | 34.25 / 34.19 (-0.16%) | 29.93 / 32.26 (+7.75%) |
| **Arithmetic mean** | **24.51 / 26.33** | **32.16 / 32.30** | **32.50 / 32.51** |

Aggregate observations:

| Engine | Auto wins | Mean paired change | Mean update pause | Mean expert-load reduction |
|---|---:|---:|---:|---:|
| Flesh | 9/10 | +7.66% | 0.260 s | 15.05% |
| Arena | 6/10 | +0.54% | 0.161 s | 7.39% |
| Tiered | 6/10 | +0.14% | 0.173 s | 8.79% |

## Correctness

- Off versus Auto generated-text SHA-256: **30/30 exact**.
- Flesh versus Arena versus Tiered within each scope: **10/10 exact**.
- Every cache result versus the unchanged full-resident MLX result: **30/30
  exact**.
- Every cache run completed all 512 requested tokens.

This proves generated-text parity for this matrix. It does not by itself prove
bitwise equality of every intermediate activation or vocabulary logit. The
separate forced-token Tiered replay covers the first adaptive-update boundary
at full-logit precision.

## Interpretation

Auto40 is clearly valuable for Flesh, where the static bank otherwise pays the
largest miss penalty. Arena and Tiered already adapt their mutable Tail, so a
full L1 update has much smaller average value and occasionally loses more to
its update pause than it recovers in the remaining tokens. In particular,
`humanities_social` should be repeated before treating its roughly 8--9%
Arena/Tiered regression as stable.

The fastest Auto engine is Tiered in six scopes and Arena in four. Flesh is not
the fastest absolute engine in this matrix, despite receiving the largest
relative benefit from Auto.

Recommended policy direction:

1. Keep Auto40 enabled for Flesh.
2. For Arena/Tiered, require a measured miss/TPS benefit gate; do not update
   merely because a checkpoint is due.
3. Retain Off and manual Trigger. Correctness does not constrain this choice;
   it is a performance-policy decision.

Raw results and the machine-readable summary are in
`artifacts/qwen36-scope-engine-matrix-2026-08-09/`.
