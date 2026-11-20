# AVTR-1 MLX

已用授权的官方完整权重跑通独立「图片 + 音轨 → 数字人视频」入口。所有神经网络由 MLX 执行；Torch 只用于离线转换和开发参考，ONNX Runtime 只用于对齐测试。已实现通用 Model Worker 与 Mini-App Provider；模型 Package 0.1.0 已完成签名构建和实际安装沙箱推理验收；生产发布状态以 Registry 为准。

## 实现

- 原生 MLX 条件编码器、18 层运动网络、四分支 CFG、渐进噪声和自回归历史；默认 5 个 ODE 时间点，即 4 次 Euler 网络求值。
- HuBERT、SCRFD、106/203 关键点、外观/姿态提取、拼接、3D 变形和图像解码均通过 MLX 运算执行。发布权重使用离线转换后的 JSON 图与 safetensors，不依赖 ONNX 解析器或 ONNX Runtime。
- 复用仓库 `omlx-model-liveportrait` 的图执行器与检测代码，增加 AVTR 所需 Conv1d、LayerNormalization、ScatterND 和 GridSample3D。相关纯 Python 辅助代码已随本 Package 携带并记录来源，不再加载其它模型 Package 的源码目录。
- 保留官方裁剪代码和来源声明。默认按原图尺寸回贴输出，可选 512² 裁剪画面；单说话音轨、听者音轨置零。Worker 支持任务取消及线程退出等待；未实现透明背景、双轨对话。

## 2026-10-01 实测

Apple M5 Max / 128 GiB，Python 3.13，MLX 0.32.0，FP32、`MLX_ENABLE_TF32=0`。使用官方 `ben.png` 与固定上游 `example/speaker_1.ogg`。

| 项目 | 结果 |
| --- | ---: |
| 视频 | 10 秒，512×512，25 fps，250 帧，H.264 + AAC |
| 生成循环 | 39.01 秒，6.41 fps |
| HuBERT / 运动 / 渲染 | 3.08 / 3.41 / 32.52 秒 |
| MLX 峰值分配 | 5,936,069,464 bytes，约 5.53 GiB |
| 推理权重合计 | 约 2.55 GB（不含重复的原始 TorchScript） |

生成时间包含逐帧编码，不含权重加载、肖像预处理和最后的音画封装。它是单次 10 秒样例，不是长时间稳态或实时验收；MLX peak 不等同于进程 RSS。此前 2 秒样例耗时 7.90 秒。

18 项真实权重对齐通过：四步 ODE 最大误差 1.88e-5，HuBERT 2.13e-5，外观提取 2.30e-4，变形 5.22e-6，解码 2.32e-5。三维采样 12 组回归通过。已抽查 10 秒样片画面；尚未做官方完整成片配对或口型客观评分。

开发产物位于仓库 `artifacts/avtr1-mlx-20261001/`，含 `ben-10s.mp4`、计时 JSON 和 `parity.json`。

## 复现

从仓库根目录执行。Worker 使用现有 Runtime 1.8.5 的 MLX、NumPy、SciPy、Pillow、PyAV、soundfile 与 safetensors。离线转换需要 ONNX，原始运动权重转换另需 Torch；对齐测试需要 onnxruntime。独立开发 CLI 的视频写入使用 FFmpeg。真实 Runtime 依赖验证已通过，签名 Package 的 Managed Service 隔离安装、重启及真实推理验收已通过。

`checkpoint-assets.json` 固定各文件的 Hugging Face 仓库、revision、尺寸和 SHA-256。下载使用现有 HF 登录授权，推理不自动下载。原始 TorchScript 转换前强制校验已审阅文件的 SHA-256，并生成 `conversion.json`。

```sh
PYTHON=.venv/bin/python
WEIGHTS=/tmp/ai2apps-avatar-checkpoints/avtr1
PKG=packages/ai2apps-model-avtr1-mlx
$PYTHON "$PKG/scripts/download_weights.py" --output "$WEIGHTS"
$PYTHON "$PKG/scripts/convert_motion.py" \
  --input "$WEIGHTS/build_artifacts/avtr1.scripted.pt" --output "$WEIGHTS"
$PYTHON "$PKG/scripts/generate.py" --model-root "$WEIGHTS" \
  --image /absolute/path/portrait.png --audio /absolute/path/speech.wav \
  --output /absolute/path/avatar.mp4 --seconds 10 --steps 5 --seed 42
$PYTHON "$PKG/scripts/validate.py" --model-root "$WEIGHTS" \
  --image /absolute/path/portrait.png --report /absolute/path/parity.json
```

音频由 soundfile 与 SciPy 转为 16 kHz 单声道；当前输出按 5 帧分块向下截到 0.2 秒倍数。生成入口强制关闭 M5 TF32，并检查推理未导入 Torch 或 ONNX Runtime。

当前 Worker 已接入通用数字人接口，使用纯 MLX 运算与 PyAV 编码；已完成签名与安装验收。本轮无需新增 Runtime。

## 渲染优化（2026-10-01）

同一 M5 Max、ben 肖像、10 秒音频、seed=42、5 个 ODE 时间点，保持 512² / 25 fps：

| 模式 | 生成循环 | 相对原版速度 | MLX peak | 渲染耗时 |
| --- | ---: | ---: | ---: | ---: |
| 原版记录 | 39.01 s | 1.00× | 5.53 GiB | 32.52 s |
| `optimized`（默认） | 31.85 s | 1.22× | 5.28 GiB | 26.84 s |
| `fast`（可选） | 25.86 s | 1.51× | 4.41 GiB | 20.83 s |

两种优化模式均使用：Metal 融合三维采样、7³ mask 卷积改写为等价二维卷积、按肖像缓存固定子图、编译动态变形图、NHWC 解码器和预排布权重；相同静音听者的 HuBERT 特征只算一次。主运动网络保持 FP32，ODE 次数、尺寸与帧数均未减少。

`optimized` 全程 FP32。`fast` 仅将解码卷积改为带 1/256 输入缩放的 FP16；输出还原为 FP32 后执行偏置、归一化和残差运算。普通 FP16 解码出现溢出，未采用；快速模式遇到非有限帧会用原始 FP32 路径重新渲染并记录 `render_fallbacks`。本次 250 帧没有回退。默认继续使用高精度模式，因为混合精度尚未经过多肖像、长视频验收。

12 组中性/小幅/大幅关键点扰动与原始渲染逐像素比较：

- `optimized` 最大绝对误差 1.37e-4，最大平均绝对误差 4.80e-7。
- `fast` 每帧平均绝对误差 2.82e-4–4.93e-4，PSNR 56.55–62.97 dB；个别像素最大差异 0.1233（像素范围 0–1）。这不是逐像素无损模式。
- 切换源关键点后的缓存隔离对齐通过；250 帧视频与 10 秒音轨检查、抽帧检查通过。
- 已验证更改编译运动网络的收益不足以抵消本次短片的首次编译开销，未设为默认；额外 TensorOps 卷积和 BF16 方案没有带来足够收益，未接入。

在已有生成命令后加 `--renderer fast` 使用最快已验证模式；`--renderer reference` 保留原始渲染实现用于回归（静音特征缓存仍生效）。

```sh
$PYTHON "$PKG/scripts/validate_renderer.py" --model-root "$WEIGHTS" \
  --image /absolute/path/portrait.png --report /absolute/path/renderer-parity.json
```

实测文件：`artifacts/avtr1-mlx-20261001/{ben-optimized,ben-fast}.mp4`、同名 JSON 以及 `renderer-parity.json`。这些是单次短片结果，仍未达到 25 fps 实时生成。优化不涉及生产 Runtime 或 Package 发布。

## 第二轮：批量、异步编码与三维优化验证

相同 10 秒素材、`--renderer fast`、seed=42，尺寸/25 fps/ODE 次数/模型精度均不变：

| 实现 | 生成循环 | 最终文件就绪（不含权重加载） | MLX peak |
| --- | ---: | ---: | ---: |
| 上一轮快速模式 | 25.86 s | 未记录 | 4.41 GiB |
| 本轮 1 帧批次 | 24.60 s | 24.83 s | 4.48 GiB |
| 本轮 2 帧批次（默认） | **23.75 s** | **23.98 s** | **4.97 GiB** |
| 本轮 5 帧批次 | 24.17 s | 24.41 s | 7.76 GiB |

本轮保留的改动：

- Warp 仍逐帧执行固定形状图，解码器支持 1/2/5 帧批次；当前没有声称整个三维网络已经改成原生多帧 batch。2 帧模式会正确处理每个 5 帧分块的 2+2+1 尾批次。
- GPU 完成裁剪与 uint8 像素转换，CPU 取回的数据从每通道 4 字节降到 1 字节；提前提交下一批 GPU 工作，与上一批取回/编码重叠。
- 有界编码队列（最多两个批次）直接向 FFmpeg 写 RGB，生成 H.264/AAC 成片，移除了中间 MPEG-4 视频及二次转码。临时结果仅成功完成后原子替换目标文件；编码失败会停止子进程、清理临时文件并保留旧目标。
- 默认批次为 2；5 帧在解码微基准更快，但本次完整短片没有更快且内存明显增加，因此不设为默认。各条为单次整段测试，小幅差异仍可能受系统波动影响。

三维变形实验结果（warm microbenchmark）：连续 channels-last 布局约 51.94 ms，对照 52.44 ms，收益不足；mask 通道补齐版本约 55.84–57.42 ms，未优于既有路径；稀疏共享特征采样 53.21 ms，对照 53.24 ms。没有确认可重复的显著收益，这些实验实现未保留到默认代码中。

验证：FP32/快速模式下，2 帧和 5 帧 batch 与逐帧输出在所测 5 组不同姿态中逐元素一致，GPU uint8 转换也一致；尾批次顺序通过。注入非有限帧后仅该帧回退到原始 FP32，位置正确。编码集成测试 3 项通过，覆盖同步/异步画面一致和帧序、失败保留已有目标、空闲 worker 中止清理。默认组合成片有 250 帧、10 秒音轨，无回退；5 帧样片抽帧检查通过。

```sh
# 在前面的 generate.py 命令后添加：
--renderer fast --render-batch-size 2 --output-mode crop
# 内存充裕时可对比 5；回归同步编码可用 --sync-encoder。

$PYTHON "$PKG/scripts/test_video_writer.py"
$PYTHON "$PKG/scripts/validate_batches.py" --model-root "$WEIGHTS" \
  --image /absolute/path/portrait.png --report /absolute/path/batch-parity.json
```

产物：`ben-fast-batch{1,2}-v2.mp4`、`ben-fast-batch5.mp4` 及同名 JSON、`batch-parity.json` 均在 `artifacts/avtr1-mlx-20261001/`。本轮默认快速组合约 10.53 fps；没有达到实时，也没有修改生产 Runtime 或发布 Package。


## 原图尺寸输出（2026-10-01）

开发入口默认 `--output-mode source`：检测最大人脸，保留官方旋转/缩放裁剪的逆变换，模型仍生成 512×512，再回贴到原始 RGB 画布。宽高比和人物位置由原图决定，不拉伸整幅画面。`--output-mode crop` 保留原来的 512×512 输出；复现上面的历史性能数字时必须使用此选项。

通用实现位于 `ai2apps/avatar/composition.py` 的 `SourceCanvas`，输入为 RGB uint8 原图、裁剪到原图的 2×3/3×3 仿射变换以及裁剪宽高。其他模型可提供自己的裁剪变换复用它，无须依赖 AVTR 网络。羽化遮罩和原图背景项一次计算，仅在与画布相交的区域逐帧变换；使用预乘颜色插值防止旋转边界产生黑边。生成结果逐帧送入有界编码队列，避免积累整段全尺寸视频。

这一步只融合裁剪边界，不做人物抠像、背景替换或背景补全。输出是不透明 H.264/AAC MP4。裁剪覆盖区域之外的 RGB 像素在编码前与原图相同；有损视频编码后不保证逐像素相等。模型可能改变裁剪内部的背景，大幅动作也可能留下重影；本次仅做短片和几何验收。过小或不可检测的人脸仍会报错；多人物默认选择最大脸。

偶数宽高使用 `yuv420p`；任意一边为奇数时使用 `yuv444p`，保留精确宽高，不补边或拉伸。4:4:4 的播放器/硬件解码支持较少，面向常见播放器优先使用偶数尺寸素材。画布由原图决定，不提供独立的目标尺寸重排版参数。

### 验证

M5 Max / 128 GiB，fast renderer、batch=2、seed=42、50 帧/2 秒、25 fps。测试素材由官方 ben 肖像裁取并放在横图右侧/竖图下方；最初测试素材错误地丢弃了原图 Alpha，导致白边；该样片仅证明尺寸与定位，不能作为边缘质量验收。现已修复，见下文。

| 原图/输出尺寸 | 生成阶段 | 回贴 CPU 时间（包含于生成阶段） | 文件就绪（不含权重加载） |
| --- | ---: | ---: | ---: |
| 1920×1080，右侧人物 | 4.91 s | 0.168 s（3.35 ms/帧） | 5.21 s |
| 1080×1920，下方人物 | 5.09 s | 0.227 s（4.54 ms/帧） | 5.43 s |

两组均无渲染回退，MLX peak 约 4.97 GiB。MP4 轨道/尺寸/帧数检查及抽帧目视检查通过。`stage_seconds.render` 包含合成与编码提交，`composition` 是其中单独测得的 CPU 回贴时间，不应重复相加。

```sh
.venv/bin/python packages/ai2apps-model-avtr1-mlx/scripts/test_source_canvas.py
.venv/bin/python packages/ai2apps-model-avtr1-mlx/scripts/test_video_writer.py
```

5 项新回归覆盖恒等融合、边缘羽化、旋转/越界/黑边、非方形裁剪与角落定位、非法矩阵，以及 1920×1080、360×640、321×181 的真实编码；原有 3 项编码帧序/失败原子性/线程清理测试通过。开发产物为 `artifacts/avtr1-mlx-20261001/ben-{corner,portrait}-source.mp4` 与同名计时 JSON。

该阶段仅验证独立入口；下述通用 Host 集成已覆盖 AVTR、FlashHead Lite/Pro 和 EchoMimic，尚未部署生产。

### Alpha 读取修复

透明输入先应用 EXIF 方向，再用已有 Alpha 合成到黑色底色后送入模型，避免直接转 RGB 暴露透明像素中的白色。此处理不估计人物遮罩；普通 RGB 图片保持不变。若需其他背景，应先用图片已有 Alpha 合成目标画布。修正后的角落样片为 `ben-corner-alpha-corrected.mp4`，素材通过 RGBA alpha_composite 合成蓝色画布。旧的 `ben-corner-source.mp4` 白边样片保留供问题追溯。

## Package 与通用回贴验收（2026-10-01）

- AVTR-1 Package 0.1.0 是模型 Package，依赖 Runtime >=1.8.5,<2，不内置 Runtime。
- Host 通过系统 Vision 定位人脸，裁剪到模型原生分辨率；生成后按逆变换回贴原图。Mini-App 默认“保留原图尺寸”，也可选择原生裁剪画面。矩形边缘羽化不承担人物抠像。
- 原图先进行 EXIF 方向处理与 Alpha 合成，支持偏置人物和非正方形画布；输出保留原始画布、帧率和音轨。没有检测到人脸时明确报错。
- 使用实际 Python 3.11 Runtime 对 1920×1080 角落人物完成四个模型的真实推理。AVTR 生成 2 秒耗时 8.76 秒，FlashHead Lite 5.44 秒，Pro 30.97 秒；EchoMimic 生成 3.24 秒耗时 91.27 秒。时间包含加载与回贴，仅作为短片功能验收，不代表稳态吞吐。
- AVTR 推理未导入 cv2、onnx、torch、onnxruntime 或另一个 Package 的模块。发布版本使用纯 MLX 渲染算子；上面的早期自定义 Metal 优化数据不等同于发布 Worker 性能。
- 权重已按用户授权公开上传双源，并从两个固定 revision 全量下载验证：HF `57bfb656636e9fdb24646a2711a7bb606cbd7cb5`；ModelScope `17caeffa78ee672e36e22e6f3d798ccef90e7c45`。共 30 个分发文件，22 个模型资产约 2.55 GB。
- Distribution `dist_ai2apps_avtr1_mlx_57bfb656_v1` 已正式发布并经匿名签名 Index 96 验证；模型 manifest 声明固定 revision 与该 Distribution。模型 Package 发布状态以 Registry 为准。
