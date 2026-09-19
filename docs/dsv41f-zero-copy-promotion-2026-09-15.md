# DS4.1F zero-copy expert promotion — 2026-09-15

The eviction_dual policy now exchanges physical-slot ownership instead of copying
expert payload. An expert promoted out of L0 stays at its existing address; the
incoming miss overwrites the evicted L1 expert's slot. Main40/Hot8 are logical
roles, not fixed address ranges. The six packed expert arrays retain their sizes,
FP4 representation and physical layout; GPU gather_qmm accesses physical slots
through the existing expert lookup. No CPU memcpy or GPU copy dispatch is needed
for promotion. Native preadv writes only incoming miss payloads.

Natural and Burst count Main/Hot hits using a GPU-resident physical-slot role
mask after slot exchange, rather than slot-number thresholds. Burst snapshots
its pre-replacement counters in each speculative record so committing/replaying
uses the correct classification. LRU ages remain attached to physical slots;
newly loaded slots get the current request age through the existing update.

The existing miss readback and single write fence are reused. All-hit expert IDs
stay on GPU. Role-mask publication is a tiny host-to-device update, with no new
GPU-to-host readback. No model forward, router or fused expert kernel changes.

## Verification and results

160 randomized bank operations match the copy policy's logical cache and read
bytes, validate actual expert bytes, protect currently requested experts, and
assert one fence per miss and zero calls to the copy routine. Legacy native-copy
tests also pass. Eight fresh model runs: short128 and input2083/decode512, each
copy/swap then swap/copy. Every generated ID and logits hash matches, as do all
logical promotions, per-layer Main/Hot/miss counts, requested bytes and fences.

| Case | Variant | TPS | Promotion GB | Copy seconds | Readback calls | Bank fences | Peak GB |
|---|---|---:|---:|---:|---:|---:|---:|
| coding-en-train-18 | copy | 4.510 | 23.802 | 0.712 | 9211 | 4171 | 55.217 |
| coding-en-train-18 | swap | 4.692 | 0.000 | 0.000 | 9211 | 4171 | 55.211 |
| long-math_logic-zh-test | copy | 4.888 | 97.989 | 2.082 | 36967 | 16567 | 57.315 |
| long-math_logic-zh-test | swap | 5.007 | 0.000 | 0.000 | 36967 | 16567 | 57.336 |

TPS excludes Prefill and includes all Decode forwards. Readbacks are cache-path
API calls derived from actual events and inspected call sites, not driver packet
counts. Bank fences are instrumented _fence calls, including identical Prefill
and initialization. Requested bytes are application I/O, not physical SSD traffic.

Burst Top2/Block1 and Top4/Block4 each passed a copy/swap 32-step pair:
logits, all cache counters, read bytes, fence counts and rollback statistics
match exactly; swap has zero promotion-copy bytes.

## Interpreting the prior copy result

The earlier experiment added about 63 GB of promotion copying while removing
about 56 GB of expert read requests. Comparing added copy seconds with saved read
seconds did not compare equal work. In one recorded long run, copying processed
about 47 GB/s; native read requests about 17 GB/s. The latter includes OS caching
and is not a hardware SSD benchmark. Memory copying was not slower per byte; it
was additional traffic that is now eliminated.

## Use

`--l1-policy eviction_dual` now uses slot exchange by default.
Add `--promotion-copy` only for the same-policy memcpy control.
The overall CLI L1-policy default remains baseline for historical reproducibility.
No extra expert capacity or checkpoint conversion; no Runtime/Package publication.

Run `.venv/bin/python experiments/dsv41_analysis/l1_policy/benchmark_slot_swap.py`.
Artifacts and source hashes: `artifacts/dsv41-slot-swap-20260915/`.

## Outcome

Observed paired mean gain: short +4.03%, long +2.43%. This is a bounded two-case,
two-repeat measurement, not a broad workload guarantee. Promotions eliminate
23.802 GB/97.989 GB of extra memory copying respectively. Expert read requests,
cache decisions and synchronization counts stay identical. Peak <=57.336 GB.
The zero-copy implementation is the default within eviction_dual; global policy
selection remains baseline for historical reproducibility.
