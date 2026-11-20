# 来源

上游代码仓库与固定 commit 见 `upstream-lock.json` 的 `musetalk` 项。
保留上游源码中的版权声明。检查点条款以各固定来源的模型卡为准。

FlashHead、InfiniteTalk 共用的 MLX attention、音频与 VAE 实现参考本仓库
`ai2apps-model-echomimic-v3-mlx`；没有复制或修改外部 DMoE checkout。
MuseTalk 核心来自 xocialize/musetalk-mlx；本地适配移除了 pipeline 的 OpenCV 颜色转换依赖。

## Automatic mouth refinement

`face_detection.py` and `onnx_mlx.py` reuse the local LivePortrait portable MLX helpers (LICENSE.liveportrait). YuNet uses OpenCV Zoo commit 47534e27c9851bb1128ccc0102f1145e27f23f98, the 2023mar model (LICENSE.yunet). `face_parsing.py` implements the BiSeNet architecture from zllrunning/face-parsing.PyTorch commit d2e684cf1588b46145635e8fe7bcc29544e5537e (LICENSE.face-parsing). Converted weights: mlx-community/face-parsing-bisenet-bf16 revision 5f2aa216736b9a98eb366e56bcbad472548247f4. No platform FFI is used.
