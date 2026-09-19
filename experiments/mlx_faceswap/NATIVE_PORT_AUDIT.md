# Specialized LivePortrait MLX port audit

Date: 2026-09-05

The community `fasterliveportrait-mlx` project was audited at commit
`d5361f4806c14fe2051eecb1dd5a89930f46db0d`. Its converted weight repository
was pinned at revision `2cc2ac92c9fe65ca4fb68cb1a1556ead285e7391`.

## What is useful

- model-specific NHWC networks instead of a node-by-node ONNX graph executor;
- `mx.compile` around stable appearance, motion, and SPADE paths;
- a Metal 3D GridSample implementation and fused layout variants;
- source-feature caching and optional temporal warp reuse;
- mature relative-motion, crop stabilization, multi-face, animal, and JoyVASA
  orchestration ideas.

The complete upstream application dependency set is not appropriate for an
AI2Apps model Package. The core models themselves use MLX and NumPy, while the
Gradio/audio application pulls in substantially more dependencies.

## Same-input measurements

The comparison used our FP32 ONNX/Bundle execution as the numerical baseline,
the pinned converted native weights, deterministic inputs, and warm medians.

| Component | Baseline FP32 | Native FP32 | Native BF16 |
| --- | ---: | ---: | ---: |
| Appearance | 6.62 ms | 6.01 ms | 5.44 ms |
| Motion | 4.42 ms | 2.46 ms | 2.23 ms |
| Warping + SPADE | 122.01 ms | 98.82 ms | 72.82 ms |

FP32 native motion was close to the baseline (expression mean absolute error
`0.0000296`); FP32 rendered pixels differed by mean `1.10` and maximum `34` on
the deterministic stress input. BF16 was faster but differed by mean `22.56`
rendered intensity levels on that stress input. Native FP16 motion produced
non-finite outputs and is rejected.

## Integration decision

Keep the parser-free Bundle/FP32 executor as the independent quality and
conversion reference. The specialized human LivePortrait core has now been
integrated under `native_liveportrait/` with its MIT license and fixed source
commit. It loads weights reproduced directly from the official LivePortrait
revision recorded in `MODEL_PROVENANCE.md`.

1. the MIT Metal GridSample was integrated with a pure-MLX fallback;
2. model-specific appearance, motion, stitching/retargeting, warping, and SPADE
   blocks are available through `NativeMLXLivePortrait`;
3. BF16 may become an explicit speed profile but must not silently replace the
   quality profile;
4. FP16 motion must remain disabled.

The integrated Metal GridSample reduced the full locked warping/SPADE graph
median from `127.91 ms` to `125.31 ms` (about 2%) because GridSample is only one
part of the combined graph. Its real-image crop changed by mean `0.298` and
maximum `10` 8-bit intensity levels versus the gather implementation.

On the end-to-end regression portrait, native FP32 and graph FP32 full-frame
JPEG outputs differed by mean `0.0137`, maximum `9`, and no channel values over
10. On the 60-frame H.264 regression, decoded frames differed by mean `0.0731`
intensity levels; the worst frame mean was `0.0853`. Native FP32 processed all
60 frames at 6.05 FPS versus 5.39 FPS for the graph path, a 12.2% throughput
increase. This clears native FP32 as the preferred Package engine while the
graph path remains the release oracle.

On the real-image smoke, explicit BF16 reduced the measured render section from
199.9 ms to 158.4 ms (20.8%). Against native FP32 the full-frame output mean
difference was 0.0778, maximum 53; 0.107% of channel values differed by more
than 10 and 0.0245% by more than 20. It remains visibly close on this input but
the earlier deterministic stress case was substantially worse, so BF16 stays
an opt-in `fast` profile rather than the default.
