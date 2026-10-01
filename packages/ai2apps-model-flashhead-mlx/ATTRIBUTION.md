# 来源

上游代码仓库与固定 commit 见 `upstream-lock.json` 的 `flashhead` 项。
保留上游源码中的版权声明。检查点条款以各固定来源的模型卡为准。

FlashHead、InfiniteTalk 共用的 MLX attention、音频与 VAE 实现参考本仓库
`ai2apps-model-echomimic-v3-mlx`；没有复制或修改外部 DMoE checkout。
MuseTalk 核心来自 xocialize/musetalk-mlx；本地适配移除了 pipeline 的 OpenCV 颜色转换依赖。
