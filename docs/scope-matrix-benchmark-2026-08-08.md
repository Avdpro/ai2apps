# DeepSeek V4 10-Scope oMLX versus DMoE benchmark

Date: 2026-08-08 (Asia/Shanghai)

## Method

- Hardware: Apple M5 Max, 128 GB unified memory.
- Model: `/path/to/dmoe/artifacts/deepseek-v4-flash/source`.
- Policy: the same `tiered-top60-global4.json`, full 256-expert hash layers,
  and per-score-layer rolling Top8.
- Workload: the first Chinese held-out validation sample in each of the ten
  scopes from `calibration-heldout-split-v1.json`.
- Generation: greedy, 32 Decode steps.
- Every scope/runtime pair runs in a clean process. Model-load time is excluded.
- oMLX uses the packed expert-major store, four parallel `preadv` workers and
  Darwin `F_NOCACHE`. DMoE uses its original offset/layer-slab mmap path.

The oMLX `gen_tps` metric excludes time to first token. DMoE's stored
`decode_tokens_per_second` includes the first Decode row, whose Metal compile
cost varies from 1.0 to 8.1 seconds in this matrix. The main table therefore
recomputes DMoE steady Decode as `31 / sum(rows[1:].seconds)` so both sides
exclude the first token.

## Results

| Scope | Prompt tokens | oMLX Prefill | DMoE Prefill | Prefill speedup | oMLX Decode | DMoE steady Decode | Decode speedup | oMLX peak GB | DMoE peak GB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| business_finance | 28 | 4.90 | 1.16 | 4.22× | 7.80 | 2.07 | 3.77× | 55.9 | 63.7 |
| coding | 25 | 4.60 | 0.94 | 4.88× | 7.90 | 2.15 | 3.67× | 55.9 | 63.7 |
| data_ai | 24 | 4.70 | 0.98 | 4.79× | 8.80 | 2.33 | 3.78× | 55.9 | 63.7 |
| general | 23 | 4.10 | 1.15 | 3.58× | 7.90 | 2.30 | 3.43× | 55.9 | 63.7 |
| humanities_social | 24 | 4.30 | 1.21 | 3.56× | 8.40 | 2.07 | 4.06× | 55.9 | 63.7 |
| legal_policy | 23 | 4.50 | 1.19 | 3.79× | 8.90 | 2.34 | 3.80× | 55.9 | 63.7 |
| math_logic | 24 | 4.40 | 1.28 | 3.44× | 8.60 | 2.02 | 4.25× | 55.9 | 63.7 |
| medical_health | 24 | 4.50 | 1.18 | 3.82× | 9.40 | 2.52 | 3.74× | 55.9 | 63.7 |
| science_engineering | 23 | 4.50 | 1.23 | 3.65× | 8.60 | 1.79 | 4.80× | 55.9 | 63.7 |
| writing_creative | 24 | 4.50 | 1.03 | 4.35× | 8.10 | 1.79 | 4.52× | 55.9 | 63.7 |

Aggregate arithmetic means:

| Metric | oMLX | DMoE | Ratio |
|---|---:|---:|---:|
| Request-level Prefill TPS | 4.50 | 1.135 | 3.97× |
| Steady Decode TPS | 8.44 | 2.139 | 3.95× |
| Peak active memory | 55.92 GB | 63.72 GB | 12.2% lower |

The median per-scope speedups are 3.80× for Prefill and 3.79× for aligned
steady Decode. The unaligned DMoE Decode mean is 1.73 TPS; comparing against it
would produce a 4.88× result, but that unfairly charges first-token compilation
only to DMoE.

## Interpretation and limits

- oMLX is faster in every measured scope. Aligned Decode speedup ranges from
  3.43× (`general`) to 4.80× (`science_engineering`).
- oMLX Decode ranges from 7.8 to 9.4 TPS. The fastest sample,
  `medical_health`, also has the fewest oMLX Decode L3 loads (897). The two
  slowest samples select about 1,200 L3 experts.
- Prefill is request-level rather than pure resident-kernel throughput. oMLX
  installs immutable Top60 at model load; DMoE constructs its scope slabs in
  the timed Prefill phase. This difference is real for these two runtime
  designs but explains part of the approximately 4× Prefill result.
- oMLX deliberately bypasses the filesystem cache while DMoE retains its
  original mmap behavior, so storage caching does not favor oMLX.
- This is one held-out prompt per scope, not a confidence interval. At least
  four samples per scope and alternating runtime order are required for a
  publication-grade median.
- Both runs use the same source checkpoint, prompt encoder, scope profile and
  greedy workload. This matrix measures performance; it does not replace the
  still-pending full-resident Top-10 parity gate.

## Artifacts

Raw per-scope JSON is under `artifacts/scope-matrix-2026-08-08/`. The oMLX
files include TTFT, Prefill/Decode TPS, peak memory, L3 expert counts and I/O
time. DMoE files retain all 32 Decode rows and Top-10 token IDs.

The oMLX command is implemented by `scripts/bench_scope_once.py`. DMoE was run
read-only with `PYTHONDONTWRITEBYTECODE=1`; its output paths pointed into this
repository, and no DMoE source or artifact was modified.

## Coding page-cache A/B

The matrix above deliberately enabled Darwin `F_NOCACHE`. The same
`coding-zh-validation-05` prompt was subsequently run twice with `F_NOCACHE`
disabled. Prompt tokens, generated route trajectory and expert counts were
identical in all three runs: 916 Prefill transient experts and 1,006 Decode L3
experts.

| Storage mode | Prefill TPS | TTFT | Decode TPS | Read + publish |
|---|---:|---:|---:|---:|
| `F_NOCACHE`, matrix control | 4.6 | 5.477 s | 7.9 | 3.956 s |
| Normal page cache, run 1 | 7.2 | 3.489 s | 9.0 | 3.479 s |
| Normal page cache, run 2 | 5.1 | 4.881 s | 8.6 | 3.420 s |

The two normal-cache runs average 8.8 Decode TPS, 11.4% above the `F_NOCACHE`
control. Average loader-boundary time falls 12.8%. Request-level Prefill is
noisier but averages 6.15 TPS versus 4.6 TPS. The second run does not exceed
the first, so repeatedly warming the filesystem cache is not an additional
scaling mechanism; Metal publication, route synchronization and miss compute
become the dominant remainder.
