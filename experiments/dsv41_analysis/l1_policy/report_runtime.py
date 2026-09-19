"""Summarize the bounded paired comparison without treating I/O savings as TPS."""
import json,statistics
from pathlib import Path
root=Path('artifacts/dsv41-l1-runtime-20260915')
r=json.loads((root/'results.json').read_text());assert len(r)==12
rows=[]
for case in dict.fromkeys(x['case'] for x in r):
 for policy in ['baseline','dual_fast75','probation32_8']:
  a=[x for x in r if x['case']==case and x['policy']==policy];assert len(a)==2
  assert a[0]['read_bytes']==a[1]['read_bytes']
  assert a[0]['adaptive']['per_layer_counts']==a[1]['adaptive']['per_layer_counts']
  assert a[0]['adaptive']['promotions']==a[1]['adaptive']['promotions']
  count=a[0]['adaptive']['per_layer_counts'];hits=sum(c[0]+c[1] for c in count)/sum(sum(c) for c in count)*100
  rows.append(dict(case=case,policy=policy,tps=statistics.mean(x['tps'] for x in a),hit=hits,read_gb=a[0]['read_bytes']/1e9,copy_seconds=statistics.mean(x['adaptive']['promotion_reuse']['copy_seconds'] for x in a),io_seconds=statistics.mean(sum(x['adaptive']['decode_io_seconds'].values()) for x in a),peak_gb=max(x['peak'] for x in a)/1e9))
(root/'summary.json').write_text(json.dumps(rows,indent=2))
text='''# DS4.1F L1 replacement policy integration — 2026-09-15

Implemented dual-frequency and protected/trial L1 policies on the existing Hot
promotion memory-reuse path. Main40/Hot8, checkpoint, quantization, native preadv,
router and model forward remain common across policies. Natural Decode remains
lossless. Baseline remains the default; alternatives are explicit CLI options.

## Bounded paired verification

Two fixtures: coding-en-train-18 (128 Decode), long-math_logic-zh-test
(2083 input / 512 Decode). Two repeats, order baseline/dual/probation then
probation/dual/baseline, 12 fresh processes. No full-corpus throughput claim.
All generated IDs and every logits SHA-256 match across policies and repeats.
Independent MLX policy versus NumPy frozen-route replay checks promotion experts
and target slots at layers 0/19/39 for all three policies. All footprint peaks
are below the 65 decimal GB budget.

SSD bytes below are application-requested expert bytes including initialization
and Prefill, not physical device traffic. Native I/O time is Decode-only; copy
seconds are reported separately. TPS excludes Prefill and includes all Decode forwards.

| Case | Policy | Decode TPS | Hit % | Requested GB | Decode I/O s | Copy s | Peak GB |
|---|---|---:|---:|---:|---:|---:|---:|
'''
for x in rows:text+=f"| {x['case']} | {x['policy']} | {x['tps']:.3f} | {x['hit']:.3f} | {x['read_gb']:.3f} | {x['io_seconds']:.3f} | {x['copy_seconds']:.3f} | {x['peak_gb']:.3f} |\n"
text+='''
## Decision

Keep baseline as default. Short Decode mean TPS changes: dual -2.17%, trial
-2.85%; long Decode: dual -2.83%, trial -1.86%. Both candidates improve hit rate
and requested bytes, but neither improves throughput in these paired samples.
Long Decode saves 32.958/44.990 GB for dual/trial, while promotion copying grows
from 0.832 seconds to 1.954/2.067 seconds. SSD time does not scale linearly with
requested bytes; maintenance and memory movement still matter. This result does
not establish that every prompt will regress, but does not justify a new default.

Candidate manifests initially inherited legacy `decay=.5` metadata. Their actual
algorithm used the 8/64 half-lives throughout; the final code corrects reporting
only (`decay=null`, explicit half-lives, weight and trial-slot count). No numerical
or scheduling code changed after the paired benchmark.

## Use and limits

`--l1-policy baseline|dual_fast75|probation32_8`; Hot copies stay enabled.
The baseline uses 16-step maintenance. Both candidates use 8-step maintenance,
8/64-token half-lives and 75%/25% weighting. The probation policy admits only
Hot-resident candidates seen at least twice in the last 32 committed routes;
eight Main slots are trial slots, with logical protected/trial role exchanges.
For Main40 this is 32 protected +8 trial; larger/smaller Main banks keep eight
trial slots. No extra expert slots or predicted L2 is allocated.

Burst shares maintenance and updates frequencies only when a layer commits.
Different retained tail experts can change approximate Burst output; exact
cross-policy parity is only asserted for Natural Decode. Two 32-step Burst smoke tests passed: dual Top2/Block1 and probation
Top4/Block4, with exactly 7680 committed routes each and successful Hot copying.
Full Burst performance qualification is not part of this small experiment.

Run: `.venv/bin/python experiments/dsv41_analysis/l1_policy/benchmark_runtime.py`
Test: `.venv/bin/python experiments/dsv41_analysis/l1_policy/test_runtime.py`
Receipts: `artifacts/dsv41-l1-runtime-20260915/`; source commit and per-file hashes
are in source-manifest.json, code in source.tar.gz. No Runtime or Package release.
'''
Path('docs/dsv41f-l1-runtime-policies-2026-09-15.md').write_text(text)
print(json.dumps(rows,indent=2))
