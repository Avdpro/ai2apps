# Qwen3.6 Cache-MoE prefill backend exploration

Date: 2026-08-09

## Configuration

- Model: `qwen3.6-35b-a3b-4bit/source`
- Scope: `coding`
- Decode engine: Arena, Top96 + Tail24
- Prefill lengths: 128, 512, and 1024 tokens
- Each length ran twice in one warm process; the second run is reported below.
- L1 optimization was off so the prefill backend was the only changing variable.

Select a backend with `OMLX_QWEN36_PREFILL_BACKEND`:

- `stable-swap`: existing exact baseline and the default.
- `workspace96`: negative control that restacks resident and SSD experts into a
  shared per-layer scratch bank.
- `packed96`: `workspace96` plus sorted MoE and native weighted-sum.
- `global96`: DMoE-style global resident arena plus 96 shared miss slots.
- `global96-packed`: `global96` plus sorted MoE and native weighted-sum.
- `layer216`: persistent per-layer Top120 + 96 private staging slots.
- `layer248`: persistent per-layer Top120 + 128 private staging slots.
- `dual128`: native dual-source QMM with per-layer 128-slot staging.
- `dual128-shared`: the same kernel with one stream-ordered shared staging bank.

All new backends fail closed to `stable-swap` when a layer exceeds the staging
capacity. None changes the single-token Decode path.

## Warm prefill result

| Backend | 128 tok/s | 512 tok/s | 1024 tok/s | Decision |
|---|---:|---:|---:|---|
| `stable-swap` | **308.8** | **799.1** | **1267.6** | Keep as default |
| `workspace96` | 161.7 | 486.1 | 932.4 | Negative control |
| `packed96` | 184.7 | 541.8 | 945.2 | Compute helps; restack dominates |
| `global96` | 295.1 | 682.1 | 940.4 | Lower I/O, oversized RHS is slow |
| `global96-packed` | 302.8 | 681.5 | 952.3 | Best experiment, still below baseline |
| `layer216` | 266.6 | 784.8 | 1319.9 | Fast long prefill; 96-slot fallback remains |

`packed96` reduced accumulated workspace compute from about 0.840 s to
0.619 s, but resident snapshot/patch still cost about 3.77 s. This reproduces
the DMoE result that restacking resident views is not a viable optimization.

`global96` removed resident restacking and reduced the measured prefill expert
loads from 17,904 to about 14,300 records (roughly 20%). It nevertheless made
long prefill slower. The generic Qwen affine `gather_qmm` is sensitive to the
approximately 4,900-entry RHS bank; the small 120-entry per-layer banks in the
baseline compute faster. Native sorted weighted-sum removes the final scatter,
but does not remove this RHS-bank penalty.

## Correctness

The HTML prompt smoke test used:

```text
帮我写一个网页，中间有个按钮，点击后开始放礼花
```

`stable-swap`, `packed96`, `global96`, and `global96-packed` produced the same
token IDs and SHA-256 text hash for the checked generation. The model loading
check reported all 40 layer layouts matching. The focused regression suite also
passed: 15/15 tests.

Artifacts are under `artifacts/qwen36-prefill-exploration-2026-08-09/`.

## Required next kernel

The next high-potential implementation is not another Python bank composition.
It is a Qwen-specific dual-source gathered QMM whose RHS source is selected per
route:

1. Keep each layer's compact resident bank unchanged.
2. Put only miss experts into a shared 96-slot bank.
3. Pass source-bit plus local-slot indices to one sorted quantized QMM.
4. Preserve the canonical route ordering and use native weighted-sum.

This combines the baseline's small resident-bank locality with DMoE's reduced
SSD traffic. It also avoids the numerical regrouping that previously caused
hit/miss split execution to diverge.

## Per-layer private staging result

The intermediate `layer216`/`layer248` design gives every layer a persistent
compact bank. Unlike the global arena, its RHS stays small. Unlike the shared
workspace, the next layer uses different backing storage, so the graph does not
need a GPU synchronization before proceeding.

Five consecutive 1024-token runs produced:

| Backend | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Steady mean (3-5) |
|---|---:|---:|---:|---:|---:|---:|
| `stable-swap` | 1114.6 | 1284.1 | 1286.3 | 1283.1 | 1287.7 | **1285.7** |
| `layer216` | 895.6 | 1272.5 | 1513.1 | 1506.3 | 1507.1 | **1508.8** |
| `layer248` | 878.4 | 1275.8 | 1543.9 | 1552.1 | 1557.6 | **1551.2** |

The final `layer248` version prebuilds its banks during engine startup and owns
a stable Top120 mapping. Decode Tail replacement therefore does not rebuild the
prefill bank; only an adaptive protected-L1 change invalidates it. Three fresh
1024-token requests measured 1299.7, 1497.4, and 1503.6 tok/s. The last two
average 1500.5 tok/s, about 16.7% over the 1285.7 tok/s steady baseline. SSD
expert reads fell from 3,629 to about 3,132 per request (13.7%), with zero
staging fallbacks.

A 1024-token multi-token output check matched the baseline SHA-256 hash. A
four-turn real Auto-L1 conversation completed four checks, two triggers, and
eight physical layout commits without stale prefill banks. `layer248`
duplicates about 16.35 GiB of expert storage, so it is an ideal-memory
experimental backend, not the default for 32 GiB systems. The result establishes
the compute target for a dual-source kernel without the duplicated resident
bank.

## Dual-source gathered QMM result

The requested kernel is now implemented. It accepts sorted route segments and
selects either the existing compact resident bank or the staging bank from the
high bit of each encoded expert ID. Gate/up and down projections use the same
source mapping, so hits and misses are not numerically regrouped. On M5 the
kernel dispatches a segmented 64x64x64 NAX QMM; older supported devices keep a
segmented classic-Metal fallback.

Three fresh 1024-token requests measured:

| Backend | Run 1 | Run 2 | Run 3 | Steady mean (2-3) | Extra expert memory |
|---|---:|---:|---:|---:|---:|
| `dual128` | 1191.0 | 1420.5 | 1422.6 | **1421.6 tok/s** | ~8.44 GiB |
| `dual128-shared` | 1165.3 | 1380.7 | 1393.7 | **1387.2 tok/s** | ~0.21 GiB |

Against the 1285.7 tok/s stable baseline, those steady results are +10.6% and
+7.9%, respectively. The shared version is about 2.5% slower than private
per-layer staging, but saves roughly 8.23 GiB. It loaded about 3,053 SSD expert
records per request, approximately 15.9% fewer than the baseline's 3,629, and
reported zero staging fallbacks.

The HTML generation smoke test matched the stable backend's token IDs and text
hash. A four-turn coding conversation with Auto-L1 enabled completed four
checks, two triggers, eight physical commits, and three prefill layout swaps.
All four output token hashes exactly matched the corresponding run with the
global Auto switch disabled. The shared staging bank is therefore the best
current memory/performance trade-off. It remains opt-in until the full scope
matrix has passed; `stable-swap` remains the default.
