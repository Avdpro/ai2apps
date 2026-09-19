# AI2Apps oMLX Runtime 1.7.8 Qwen3.6 Tiered pre-split candidate

Date: 2026-09-20 (Asia/Shanghai)

Status: production publication and anonymous exact-byte verification complete;
formal receipt: `docs/ai2apps-mlx-runtime-1.7.8-qwen36-tiered-presplit-release.md`

## Incident

The Qwen3.6 SSD reader correctly materializes a Tiered checkpoint as two banks:
120 protected experts in `switch_mlp` and 24 replaceable experts in
`tail_switch_mlp`. The text-model sanitizer still accepted only a 256-expert
full bank or a transient 144-expert combined bank, so it rejected the valid
120-row protected bank with:

`Qwen3.6 layer 0 gate_proj.weight has 120 experts; expected 256 or compact 144`

The VLM sanitizer already accepted this pre-split representation.

## Fix

The text-model sanitizer now accepts an already separated Tiered layout only
when the primary count exactly equals the configured resident count and the
matching tail tensor exists with exactly the configured tail count. Full
256-row and legacy combined 144-row layouts remain unchanged.

This is a Runtime fix. The published Qwen3.6 0.3.4 Model Package, scope pack,
and immutable checkpoint are correct and do not need an upgrade.

## Verification

- 34 Qwen3.6 model-patch, I/O-reader, and scope-policy tests passed.
- The regression exercises the production Top120 + Tail24 split explicitly.
- 24 related Cache-MoE Worker, Inference Runtime Package, and Runtime builder
  tests passed.
- One pre-existing DeepSeek 2-bit adapter test fails independently of this
  Qwen3.6-only change and was not modified.

The standard Runtime builder produced the development candidate:

- Package digest:
  `sha256:5cdf27b732cc80d5d4d8e56619aec01784863fc0c834f94504a417e4ee154e76`
- Artifact SHA-256:
  `a7d7bd6b2eed895d6f7b4f26e6fc90fff69a2f95fb4cf8aeeba1575889aebe8c`

The standard Package Manager installed the candidate into the persistent
`app-dev` instance. On the next Local start, the staged-Runtime transaction
activated 1.7.8, retained 1.7.7, and atomically relocked every compatible active
model, including `ai2apps.model.qwen36-35b` 0.3.4, to the 1.7.8 digest. No model
Package or checkpoint was rebuilt or modified.

The live Qwen3.6 Worker was then verified to execute from the materialized
1.7.8 Runtime path. A real Chat request, `20+20=？请只回答结果。`, completed with
`40`; the former 120-versus-256/144 load error did not recur. The Chat metrics
reported non-zero Prefill and Token Gen throughput.

Runtime Package metadata advances to 1.7.8 because the published 1.7.7 artifact
is immutable. The production artifact was subsequently Developer ID signed,
Apple notarized, Publisher signed, published, and anonymously verified.
