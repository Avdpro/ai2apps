# DeepSeek V4 Flash 2-bit release smoke

Date: 2026-08-10

## Installed artifact

- Catalog model: `deepseek-v4-flash-2bit`
- Hugging Face source: `mlx-community/DeepSeek-V4-Flash-2bit-DQ`
- Fixed revision: `722bf559b7de93575b2320973cf2002e05bfe6c9`
- Checkpoint validation: 19/19 safetensors shards, index complete
- AI2Apps conversion: 43/43 routed layers, about 63 seconds
- Download behavior: local HF cache reused (`cache_hit=true`)
- Expert-major store: about 86 GiB
- Installed memory tier: `auto`; this 128 GiB device resolves it to Top-60

The real checkpoint exposed two release blockers that synthetic fixtures did
not cover. Its stacked expert projections can span multiple safetensors shards,
so the DeepSeek offset manifest now records a source file per tensor. It also
uses mixed quantization widths across layers: expert records observed by the
runtime are not a model-wide constant. The fallback loader now resizes reused
staging buffers to each layer's exact `record_bytes`.

## Real Metal smoke

Command: `scripts/bench_flesh_adaptive_l1.py` with exact/off mode, packaged
Scope Pack, installed expert store, one warmup token and eight measured tokens.

- Model load: 6.71 seconds
- Completion: 8/8 tokens, `finish_reason=length`
- Short decode: 9.48 tokens/second (diagnostic only)
- Scope selection: `math_logic`
- L1 bank switch: successful, Top-60
- Rolling cache: 40 Hot8 layers active
- Lossy replacements: 0

Raw evidence:
`artifacts/release-gate/deepseek-v4-flash-2bit-smoke-8.json`.

The focused installer/Scope Pack/staging tests pass 16/16. The wider selected
DeepSeek regression set passes 209/215; the six remaining failures are existing
DSpark bit-exact and legacy reduced-bank expectations outside these changed
paths. This smoke proves install, conversion, cache activation and real decode;
it is not a long-context throughput benchmark.
