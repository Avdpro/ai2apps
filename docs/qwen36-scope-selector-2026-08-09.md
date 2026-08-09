# Qwen3.6 target-backbone scope selector

## Design inherited from DS4F

The selector is not a separately trained semantic classifier. It runs the
target model's own backbone, routers, and shared experts, skips routed-expert
compute, and scores every configured scope by weighted Router coverage.

The Qwen implementation is independent and changes the model-specific pieces:

- Top-8 routes instead of DeepSeek Top-6.
- Forty routed layers with no initial three hash-routed layers.
- Decode Top-N masks from the active Qwen memory tier (Top80/96/120).
- Arbitrary scope count and names read from the Scope Pack.
- Maximum 1024 probe tokens. Inputs up to that size are read in full; longer
  conversations retain 128 leading tokens plus the most recent 896 tokens.
  Router evidence is accumulated in independent 128-token windows so a shallow
  probe remains stable over long and mixed-domain conversations.

## Balanced depth sweep

The oracle runs the exact routed trajectory and chooses the scope whose Top96
Decode bank has the highest weighted coverage. The held-out sample contains 40
prompts across ten scopes, balanced 20 Chinese / 20 English.

| Probe depth | Oracle agreement | Label accuracy | Oracle in Top3 | Mean regret | Worst regret | Median time |
|---:|---:|---:|---:|---:|---:|---:|
| **8** | **70.0%** | 62.5% | **92.5%** | 0.798 pp | 6.942 pp | **3.7 ms** |
| 12 | 67.5% | 57.5% | 92.5% | **0.707 pp** | **4.620 pp** | 5.2 ms |
| 16 | 60.0% | 52.5% | 90.0% | 1.013 pp | 5.472 pp | 6.7 ms |
| 24 | 60.0% | 52.5% | 90.0% | 1.286 pp | 5.472 pp | 9.9 ms |
| 40 | 67.5% | 62.5% | 77.5% | 0.748 pp | 5.354 pp | 16.6 ms |

The exact oracle matched the dataset's semantic label 90% of the time. As in
DS4F, the performance-optimal bank and the nominal topic label are related but
not identical.

The table above is the historical short-prompt sweep. Serving now uses a 1024
token ceiling so that longer and mixed-domain requests expose substantially
more Router evidence; the selector still consumes only the actual prompt
length when it is shorter.

## 1024-token probe validation

A synthetic 1200-token sweep repeated one held-out prompt from each of the ten
scopes. A single contiguous 1024-token shallow trajectory degraded shared
oracle agreement from 7/10 to 4/10, which is why serving does not use that
form. Accumulating eight independent 128-token windows restored agreement to
7/10 and kept the confidence cascade at 9/10. Median shared-probe time rose
from 6.2 ms at 128 tokens to 47.4 ms at 1024 tokens. Median exact-refinement
time was 712 ms when it was required. These repeated prompts validate
long-input stability and cost, not a semantic-accuracy gain; a natural
mixed-context corpus remains the appropriate accuracy gate.

Artifacts:

- `artifacts/qwen36-scope-probe-2026-08-09/long-context-1200-max128.json`
- `artifacts/qwen36-scope-probe-2026-08-09/long-context-1200-max1024-window128.json`

Unlike DS4F, Qwen's best cheap point is eight layers. Extending the shared-only
trajectory is non-monotonic and does not repair ambiguous decisions.

## Confidence cascade

At depth 8, a shared-probe margin of at least 0.010 accepted 19/40 prompts and
matched the exact oracle on all 19 in this sample. The production path is:

1. Run the 8-layer shared-only Top8 probe.
2. Accept immediately when margin is at least 0.010.
3. Otherwise run an exact routed-router refinement on the same truncated input.
4. Activate the selected scope's L1/L0 atomically for the owning Session.
5. Put the selected scope in the KV-cache namespace.

Exact refinement took a median of about 222 ms in the sweep. Re-running deeper
shared-only probes or averaging 8/12/40-layer scores did not improve oracle
agreement, so it is not used as the ambiguity fallback.

## Serving validation

Starting from a physical `general` bank, the HTML fireworks coding request was
classified as `coding` by Flesh, Arena, and Tiered. The request had shared
margin 0.00443, triggered exact refinement, and then rewrote all forty scope
layers. Selector time was about 281 ms, bank activation about 422 ms, and total
TTFT about 1.0--1.1 seconds. All three engines produced identical token hashes.

A two-turn same-Session test with Auto-L1 enabled completed two policy checks
and one adaptive trigger in every engine. Both turn hashes matched across all
three engines, and the active scope remained `coding`.

Artifacts:

- `artifacts/qwen36-scope-probe-2026-08-09/depth-sweep-balanced40-top96.json`
- `artifacts/qwen36-scope-selector-2026-08-09/`
