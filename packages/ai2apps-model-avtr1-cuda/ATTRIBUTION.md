# 来源

上游代码仓库与固定 commit 见 `upstream-lock.json` 的 `avtr` 项。
保留上游源码中的版权声明。检查点条款以各固定来源的模型卡为准。

FlashHead、InfiniteTalk 共用的 MLX attention、音频与 VAE 实现参考本仓库
`ai2apps-model-echomimic-v3-mlx`；没有复制或修改外部 DMoE checkout。
MuseTalk 核心来自 xocialize/musetalk-mlx；本地适配移除了 pipeline 的 OpenCV 颜色转换依赖。

## AVTR-1 完整链路（2026-10-01）

- `src/avtr_mlx/source_crop.py` 保留 AVTR-1 上游 `components/source_crop.py` 的实现和版权声明，固定 commit `eb1e5a89ed7bec3debe712b090efd676b3a420bd`。
- `model.py` 根据授权的官方 TorchScript 结构实现；转换器只接受 `checkpoint-assets.json` 中固定 SHA-256。
- HuBERT 来自 `avaturn-live/avtr-1`；渲染网络来自 `digital-avatar/ditto-talkinghead`，revision 和逐文件 SHA-256 见 `checkpoint-assets.json`。
- 复用本仓库 `mlx_liveportrait` 的 MLX 图执行器、SCRFD 和姿态变换。Ditto 官方 `core/models/modules/{dense_motion,warping_network}.py` 确认 3D 采样使用零填充、`align_corners=False`。

渲染优化复用 `mlx_liveportrait/metal_grid_sample.py` 及 `native_liveportrait/mlx_modules/mask_conv.py` 中的融合采样和二维展开卷积；原内核来源与许可证见该 Package 的 `THIRD_PARTY_NOTICES.md`。没有修改共享模块。

## Portable Package

Pure Python graph execution, detection and image helpers are vendored from the local MLX LivePortrait package (LICENSE.liveportrait). The packed mask convolution contains only MLX operations. No embedded Metal source or compiled binary is included. Runtime graph inputs use JSON/safetensors converted offline; ONNX is not loaded during packaged inference. Original AVTR component licenses are included without relicensing them.
