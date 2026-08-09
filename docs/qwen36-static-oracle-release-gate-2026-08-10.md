# Qwen3.6 static-oracle release gate

Date: 2026-08-10

Repository source commit before the measurement-only additions:
`2f36265eb21c6812c395e05c09b562394849ae1d`.

The independent Arena engine now has a fail-closed static-oracle transaction.
It keeps Router indices on device, executes the compact per-layer `SwitchGLU`
slab without per-layer CPU synchronization, and validates all mapped route IDs
once after the run. A missed route invalidates the complete output and reports
only the first trustworthy layer for offline re-sealing.

The oracle is prepared from a deterministic warmup. Request preparation is
then pinned to the sealed layout so the semantic scope initializer cannot
silently restore the old Top-120 bank between repetitions.

## Adjacent Metal A/B

Prompt: `Explain in one sentence why mmap is useful.`

| Path | Decode TPS | Peak MLX | Miss/patch/SSD | Output |
|---|---:|---:|---:|---|
| unchanged full resident | 97.23 | 18.45 GiB | n/a | reference |
| compact static oracle, steady mean runs 2-3 | 92.49 | 11.62 GiB | 0 / 0 / 0 B | exact hash |

The static-oracle/full-resident ratio is **95.1%**, above the required 85%
first performance gate. All three timed oracle repetitions produced the same
SHA-256 text hash as the unchanged full-resident engine. A separate sampler-
boundary capture compared all 33 scheduler logits rows (including its final
look-ahead row): every ordered Top-10 was identical and the maximum absolute
logit error was **0.0**. End-of-run validation took about 3.2 ms and is included
separately in the raw artifact.

Raw evidence:

- `artifacts/release-gate/qwen36-full-resident-mmap-32.json`
- `artifacts/release-gate/qwen36-static-oracle-direct-map-32x3.json`
- `artifacts/release-gate/qwen36-static-oracle-batched-validation-32x3.json`
- `artifacts/release-gate/qwen36-static-oracle-top10-32.json`

The parity capture used `scripts/capture_qwen36_full_logits.py` against the
unchanged resident engine, followed by `scripts/bench_qwen36_static_oracle.py`
with `--logits-reference`, `--compact-slab`, `--scope coding`, Top-120 and a
24-slot Tail. Both runs used greedy decoding and the identical raw prompt.

The zero-miss slab is an offline ceiling and release-gate tool, not a serving
claim. Deployed Tiered/Arena TPS remains recorded separately because real
requests can miss and load experts from SSD.
