# Ornith 1.5 35B A3B / Qwen3.6 Cached-MoE optimization checkpoint

Date: 2026-08-29

## Source and storage

- Checkpoint: `ornith-ai/Ornith-1.5-35B-A3B-MLX-4bit`
- Pinned revision: `19504d912fa8fc7622bf6b1de3db5d5d890b1f02`
- Architecture: 40 routed layers, 256 experts/layer, Top-8, affine Q4/group64.
- The converter writes one page-aligned, fused `gate_up_proj` + `down_proj`
  record per expert in the final MLX compute layout. No split intermediate
  store is created.
- Store variant: `qwen3.6-affine-q4-gate-up-fused-direct-v3`.
- Record size: 1,769,472 bytes/expert; routed store size: 18,119,557,120 bytes.
- Real native-loader validation compared all six affine-Q4 tensor segments
  byte-for-byte after loading experts 7 and 193 into nonmatching slots.

## Implemented runtime paths

- Direct Decode: native `preadv` writes SSD-ready expert records directly to
  final unified-memory L0 slots. The Python bytearray/tensor/stack path remains
  available through `OMLX_MOE_DIRECT_L1=0` for A/B and rollback.
- Direct Prefill: `workspace256-direct` uses one shared 256-slot SwitchGLU.
  Experts retain global IDs and the stock physical kernel shape. Resident rows
  are gathered from L1/L0 and misses are written directly into their final
  global slots before the layer is evaluated.
- Direct Scope/L1 commits: session Scope changes and adaptive L1 updates use
  the same native destination-slot loader when an expert is not already in L1
  or L0.
- Existing tiered L0 LFU replacement remains the Decode Hot bank.
- Existing session-owned adaptive L1 remains exact and can update between
  decode steps. Token-level speculative transaction stays opt-in and off.

## Scope profile

- Dataset: `/Users/avdpropang/sdk/DMoE/configs/scope-dataset.v2.json` (explicit
  artifact path only; no DMoE runtime code is copied).
- Ten scopes: business/finance, coding, data/AI, general, humanities/social,
  legal/policy, math/logic, medical/health, science/engineering, and creative
  writing.
- Training artifact: `benchmarks/profiles/ornith15-qwen36-scope-train10-v1.json`.
- Each scope used ten train samples; Prefill and Decode are ranked separately;
  every layer stores the complete 256-expert order.
- Independent mixed Chinese/English test split, ten samples/scope:

| L1 | Prefill route coverage | Decode route coverage | Decode router-mass coverage |
|---:|---:|---:|---:|
| 120 | 92.63% | 96.12% | 96.88% |
| 160 | 96.91% | 97.94% | 98.36% |
| 192 | 98.52% | 98.77% | 99.01% |

## Measured results

Machine-local single-request results. Decode uses the same 49-token coding
prompt and 256 generated tokens unless noted.

| Configuration | Decode TPS | MLX peak | Output parity |
|---|---:|---:|---|
| Full resident Q4 | 136.06 | 18.45 GiB | reference |
| Top120 + Hot24 | 42.62 | 11.49 GiB | strict prefill not measured |
| Top160 + Hot16 | 46.51 | 13.74 GiB | exact hash |
| Top160 + Hot24 | 47.63 | 14.32 GiB | exact hash |
| Top160 + Hot32 | 49.11 | 14.82 GiB | exact hash |
| Top192 + Hot32 | 53.06 | 16.97 GiB | exact hash |

Direct Decode A/B at Top160 + Hot32: 46.42 TPS off versus 49.11 TPS on
(+5.8%); TTFT improved from 0.531 s to 0.465 s. A strict Top160 Prefill loaded
750 SSD experts / 1.33 GB in 0.091 s through the direct path.

Long repetitive coding prompts on Top160 + Hot24/32 exceed 5,600 prompt
tokens/s at 4K after warmup. The 512-token cold/JIT case is 565 tok/s and the
second run is 643 tok/s.

Adaptive L1 at Top160 + Hot32 improved a 512-token Decode from 48.99 to 50.45
TPS (+3.0%). It made one exact 40-layer commit in 83 ms and preserved the
output hash. All promoted experts in this run were reusable from resident
banks, so no SSD read was required.

## Rejected or non-default experiments

- Per-layer 216-slot Prefill workspaces reached 25.7 GiB MLX peak and are not
  suitable for the small-footprint default.
- `stable-swap` is fast and low-memory but changes floating-point reduction
  order; its generated token hash diverged from full resident. It remains an
  optional speed experiment, not the exact default.
- Token transaction reduced Top160 from 47.63 to 31.68 TPS and Top192 from
  53.06 to 37.39 TPS because miss tokens require full-token recomputation.
- Increasing L0 from 16 to 32 is worthwhile; Top160 improved from 46.51 to
  49.11 TPS for about 1.08 GiB additional MLX memory.

## Recommended tiers

- Compact default: Top160 L1 + Hot32 L0, `workspace256-direct`, Direct loader
  auto/on, token transaction off. Peak measured at 14.82 GiB.
- Performance: Top192 L1 + Hot32 L0 with the same exact paths. Peak measured
  at 16.97 GiB.
- Adaptive L1: off for short stateless answers; enable for expected Decode of
  at least 512 tokens or a persistent multi-turn same-Scope session. Start at
  token 64, re-evaluate at token 256, and cap promotions at 40/layer.
- Boost remains disabled by default and is outside these lossless benchmarks.

Benchmark JSON files are under `benchmarks/results/ornith15/`.

## Vision-preserving checkpoint

The community `ornith-ai/Ornith-1.5-35B-A3B-MLX-4bit` revision
`19504d912fa8fc7622bf6b1de3db5d5d890b1f02` is language-only despite retaining
the image/video token IDs. The official BF16 checkpoint revision
`10fbf86fed7ecee4a061f8b499a618f46001cac1` contains the complete 27-layer
Qwen3.5 vision tower in `model-00001-of-00016.safetensors`.

`scripts/build_ornith15_mlx_vision_checkpoint.py` now produces a mixed
checkpoint without downloading the remaining 15 BF16 language shards:

- existing Q4 language weights and tokenizer remain unchanged;
- all 333 official `model.visual.*` tensors are streamed byte-for-byte into a
  root-level `vision_tower.*` sidecar;
- the one PyTorch Conv3d patch-embedding tensor is converted from
  `[out,in,t,h,w]` to MLX `[out,t,h,w,in]` layout;
- official processor/image/video configs and `vision_config` are restored;
- the source revision, source SHA-256 and sidecar SHA-256 are recorded in
  `VISION_SIDECAR.json`.

The BF16 visual sidecar is 893,142,496 bytes (about 852 MiB). The resulting
checkpoint remains Q4 for the language body and BF16 for vision; mlx-vlm
instantiates quantized modules only when a matching `.scales` tensor exists,
so the mixed layout is native and keeps visual quality above a speculative Q4
vision conversion.

### Cached VLM correctness fixes

Real image testing found and fixed two Cache-MoE/VLM integration defects:

1. MLX-format checkpoints skip `Model.sanitize()`. VLM Scope layer IDs,
   expert-to-slot maps and Prefill ownership are therefore bound from the
   outer model constructor as well as the sanitizer path.
2. The generic >=1024-token MoE weighted-sum shortcut must not own a compact
   Scope block. It passed global expert IDs directly to a Top-N physical bank,
   bypassing SSD miss loading and corrupting every long Prefill. Cache-aware
   blocks now always enter their exact workspace path first.

The second fix is important beyond vision: before it, 1K text Prefill was
correct while 2.1K text Prefill produced repeated punctuation. After the fix,
the default 2048-token chunked path correctly handles the 2,990-7,591 token
image prompts below.

### Real image results

Top160 + Hot32, Direct Decode enabled, exact mode, eight user-provided images:

- coverage: desktop GitHub, ModelScope and Apple Store pages; mobile payment,
  comics, video-feed and watch-article UIs; one natural watch photograph;
- prompt range: 1,675 to 7,591 tokens;
- peak MLX memory: 17.625 to 19.720 GiB;
- mean end-to-end completion throughput: 10.766 tok/s (includes vision encode
  and Prefill, so it is not steady-state Decode TPS);
- receipt OCR exactly recovered `7-11 / ¥47.10 / 2631` and
  `美团 / ¥1.88 / 8657`;
- article OCR recovered `THEWATCHSPACE`, the full Brunswick 39 title and the
  `27-08-2026 23:00:11` publication timestamp.

Artifacts:

- `benchmarks/ornith15_vision_cases_20260829.json`
- `benchmarks/results/ornith15/vision-quality-top160-hot32.json`

The three-turn session test reused the first image on a text-only follow-up,
then appended a second image. Vision Feature Cache changed by one hit on the
second turn, and by one hit plus one new save on the third turn. The model
correctly answered the original receipt details without re-upload and then
identified the new comics UI and its `狗咬狗` search term. Peak memory across
the three turns was 19.621 GiB. See
`benchmarks/results/ornith15/vision-multiturn-top160-hot32.json`.

Paged session KV was also verified on the hybrid 10-KV/30-GDN architecture.
The scheduler now registers the latest complete 2,048-token recurrent-state
snapshot as an exact session boundary, keeps that safe boundary when a short
follow-up does not cross the next one, and keys a growing multimodal lineage by
the stable session namespace plus its first visual boundary. Per-block
segmented image hashes still perform the final correctness check. In a fresh
three-turn run, both the text-only follow-up and the appended-image turn
reported `cached_tokens=2048`; the former also hit the per-image Vision Feature
Cache, while the latter reused the first image and encoded only the new image.
See `benchmarks/results/ornith15/vision-multiturn-kv-verify.json`.

## Product default

Full-resident Q4 remains the product default when it fits with the normal
system/KV reserve (practically 32 GiB and larger for a single loaded model): it
is much faster and the full VLM measured 20.888 GiB peak on the receipt case.
Cached-MoE is an explicit small-memory, multi-model-residency or unusually
large-KV option. For vision its measured Top160 + Hot32 peak was 17.339 GiB on
the same receipt and at most 19.720 GiB across the eight-image suite. A future
Ornith Package should therefore ship `moe_execution_mode=full` as its default
while retaining Cached-MoE as a live setting; Boost stays off by default.
