import json,statistics
from pathlib import Path
root=Path('artifacts/dsv41-l1-eviction-20260915');r=json.loads((root/'results.json').read_text());assert len(r)==8
rows=[]
for case in dict.fromkeys(x['case'] for x in r):
 for policy in ['baseline','eviction_dual']:
  a=[x for x in r if x['case']==case and x['policy']==policy];assert len(a)==2
  assert a[0]['read_bytes']==a[1]['read_bytes']
  assert a[0]['adaptive']['per_layer_counts']==a[1]['adaptive']['per_layer_counts']
  counts=a[0]['adaptive']['per_layer_counts'];row=dict(case=case,policy=policy,tps=statistics.mean(x['tps'] for x in a),hit=100*sum(c[0]+c[1] for c in counts)/sum(sum(c) for c in counts),read_gb=a[0]['read_bytes']/1e9,readbacks=a[0]['readbacks'],fences=a[0]['adaptive']['bank_fence_calls'],copy_seconds=statistics.mean(x['adaptive']['promotion_reuse']['copy_seconds'] for x in a),io_seconds=statistics.mean(sum(x['adaptive']['decode_io_seconds'].values()) for x in a),peak_gb=max(x['peak'] for x in a)/1e9)
  rows.append(row)
(root/'summary.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
text='''# DS4.1F L0 eviction promotion — 2026-09-15

Historical memcpy-stage results: use `--promotion-copy` with eviction_dual to
reproduce this variant. Current eviction_dual defaults to zero-copy slot exchange.

New `eviction_dual` policy promotes only experts actually about to leave L0.
Ranks use the existing 8/64 half-life, 75%/25% mix. At most four evicted experts
are considered per miss, score >=3 and advantage >2 over a replaceable L1 expert.
Current requested L1 experts are protected. Free L0 slots do not cause promotion.
No standalone periodic maintenance, frequency readback or promotion fence.

Natural miss IDs/ages/scores share one readback (previously two for IDs/ages).
Burst IDs/required/mapping/ages/scores share one readback (previously four).
All-hit routing IDs remain on device. The existing per-layer hit flag readback
is unchanged. Rank updates execute on GPU. Copies and SSD writes share exactly
one existing miss fence; all lazy bank consumers finish before any overwrite.
Payloads are copied before the evicted L0 source is overwritten. No SSD reread
for promotions. Native GLM/Qwen preadv remains the miss loader.

## Paired results

Two cases, two repeats in AB/BA order, eight fresh processes. Exact generated IDs
and every logits hash match across policies. Six small native/bank tests passed,
including one-fence copy-before-overwrite and current-request protection.

| Case | Policy | TPS | Hit % | Requested GB | Cache readbacks | Bank fences | Copy s | I/O s | Peak GB |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
'''
for x in rows:text+=f"| {x['case']} | {x['policy']} | {x['tps']:.3f} | {x['hit']:.3f} | {x['read_gb']:.3f} | {x['readbacks']} | {x['fences']} | {x['copy_seconds']:.3f} | {x['io_seconds']:.3f} | {x['peak_gb']:.3f} |\n"
text+='''
Readbacks are cache-path API calls reconstructed from actual miss events and the
inspected call sites, not Metal driver transaction counts. They include the
per-layer `.item()`, miss `.tolist()` calls and baseline periodic score reads.
Unchanged output/logits reads are excluded. Bank fences are instrumented `_fence`
calls including initialization/Prefill, which are identical across each pair.
Both counts must not increase in any pair. These checks prove no added policy
boundary; different routing/cache behavior can still change miss counts on other
prompts, so the paired totals are not a universal guarantee for all workloads.
GPU task execution time can change even with fewer host readbacks.

Requested GB includes initialization/Prefill; I/O and copy times are distinct.
TPS excludes Prefill and includes all Decode forwards. Peak budget is 65 decimal GB. Natural Decode is exact;
Burst remains approximate. Top2/Block1 and Top4/Block4 each passed a 32-step
smoke test with 7680 committed routes, Hot copies and peak <55.116 GB. No model Runtime/Package has been published.

Run `.venv/bin/python experiments/dsv41_analysis/l1_policy/benchmark_eviction.py`.
Receipts and source snapshot: `artifacts/dsv41-l1-eviction-20260915/`.
'''
text+='\n## Decision and post-benchmark guards\n\nKeep `baseline` as the default reproducible control and expose the new mechanism\nwith `--l1-policy eviction_dual`. Short/long TPS changed -1.20%/-0.75%; no speedup\nis claimed. Fewer readbacks and lower requested bytes are repeatable across both\nruns. Copy time still rises (long: 0.834→2.065 s) while native I/O falls only\n36.240→35.506 s, so reduced synchronization count alone is insufficient.\n\nAfter throughput collection, added a host-only guard against float32 metadata\nage overflow and rejected the incompatible legacy `--promotion-reread` flag.\nThese guards add no GPU readbacks or fences and do not change tested arithmetic.\nThe original and final source snapshots are both retained.\n'
Path('docs/dsv41f-l1-eviction-promotion-2026-09-15.md').write_text(text)
