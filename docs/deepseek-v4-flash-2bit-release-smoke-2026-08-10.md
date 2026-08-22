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

## Full-checkpoint execution smoke

Date: 2026-08-17

- oMLX source commit: `2cd82afd077893d9ddb12b83d6f11a40cc4b1c17`
- Device unified memory: 128 GiB
- Execution setting: `moe_execution_mode=full`
- Runtime: package discovery -> `EnginePool.get_engine(...)` -> standard
  `BatchedEngine` (no Scope Pack or expert-store runtime)
- Full checkpoint admission estimate: 94.39 GiB, including the standard 5%
  runtime allowance
- Observed MLX peak: 89.93 GiB through the EnginePool product path
- Result: four of four requested tokens completed without an OOM
- Cold end-to-end time: 21.03 seconds (load, prefill, and four-token decode)

An additional chat-template run completed 22 prompt tokens and 16 completion
tokens in 19.83 seconds with a 89.97 GiB MLX peak. Its diagnostic cold
end-to-end rate was 0.81 tokens/second; this is not a steady-state decode
measurement. The recursive installed directory is about 176 GiB because it
also contains the independently generated Cached-MoE expert store. Admission
correctly counts only the root checkpoint safetensors and does not double-count
that store.

## Prepared-checkpoint execution smoke

Date: 2026-08-17

The installer-produced layout was exercised without changing the installed
source model. A temporary model view contained a 4.0 GiB backbone checkpoint
with all routed-expert tensors removed and referenced the existing 85.9 GiB
expert-major store. No original expert tensors were visible to the runtime.

- Cached mode: Top-20 experts, one output token, 2.78-second load, 3.61-second
  end-to-end time, 18.91 GiB MLX peak.
- Full mode: all 256 experts, one output token, 20.27-second load, 32.33-second
  end-to-end time, 91.77 GiB MLX peak.
- Both modes emitted the same one-token smoke output (`Ir`).

This validates that both selectable execution modes use the transformed
expert store after the original checkpoint is released. The temporary test
view was removed after the smoke run; the installed source checkpoint was not
modified.
