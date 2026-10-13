# 数字人模型 MLX 移植记录

日期：2026-09-30。按用户要求，当前先移植模型，Mini-App 与安装发布后置。
所有“通过”仅对应下列明确验证项，不代表全部模型已验收。

## 状态

| 模型 | 已实现、已验证 | 尚未完成 |
| --- | --- | --- |
| EchoMimic V3 | 沿用现有原生 MLX Package | 新 Mini-App 实机验收 |
| MuseTalk 1.5 | 固定社区源码；去除 pipeline OpenCV；真实 Q4 权重完成音频、VAE、UNet、人脸解码；显式人脸框/遮罩模板生成 MP4 | 自动检测与人脸分割；FP16/Q8 对比；成片质量与最终 Runtime 验收 |
| FlashHead Lite | 主干、LTX VAE、Wav2Vec2、分块采样、色彩匹配与 MP4；官方完整权重；512×512 两分块公开人像样例 | 全尺寸上游端到端配对；长视频、取消、精度/性能与最终 Runtime 验收 |
| FlashHead Pro | 原生主干和 Wan VAE；完整官方权重；512×512 两分块公开人像样例 | 全尺寸配对、长视频和最终 Runtime 验收 |
| AVTR-1 | 2026-10-01：授权权重下载成功；MLX HuBERT、完整运动主干和渲染；512²、25 fps、10 秒样片；18 项真实权重对齐和 12 组采样回归 | 渲染优化、原图回贴、双轨对话、长视频质量、Worker/Service 与最终 Runtime 验收 |
| InfiniteTalk | 完整 DiT，单/双人注意力对齐；全量单人权重；T5/CLIP/中文 Wav2Vec2/Wan VAE；原生跨块 MP4，人像抽查通过 | 480² 默认长窗口、真实双人权重、长视频质量和最终 Runtime 验收 |
| Ex-Omni-2D | Teacher DiT、TQGF；Thinker→Talker 16 码本真实权重；codec 编解码、参考音色编码；图像+音频 Teacher 视频，人像抽查通过 | 完整对话编排、视觉/语音输入、长视频和最终 Runtime 验收 |

## 已执行的验证

仓库基线：`e8d5f699202607835010fef1b74614b2181885ba`，本轮新增源码尚未提交。固定上游 commit 和权重 revision 见各 Package 的 lock。

开发机：Apple M5 Max，统一内存 128 GiB；开发 Python 3.13。尚未以最终 Python 3.11 Runtime 替代开发环境验收。
Metal 精确对齐使用 `MLX_ENABLE_TF32=0`。M5 默认 TF32 可产生约 10⁻³ 的差异；没有修改共享 Runtime 的环境变量。
测试引用固定上游实际类体，去除 CUDA/训练依赖，并用 CPU attention 计算参考。

- FlashHead 缩小网络 FP32：最大绝对误差 3.58×10⁻⁷。
- Wan VAE 官方权重 FP32 上游参考：encoder 1.06×10⁻⁶，decoder 1.88×10⁻⁵。
- LTX VAE 缩小 encoder/decoder：最大误差分别 6.56×10⁻⁷、9.24×10⁻⁷。
- AVTR 三维采样：zeros/border/reflection × align_corners × 单层/多层深度，共 12 组，最大误差 1.02×10⁻⁶。
- InfiniteTalk 缩小完整主干：单人 3.28×10⁻⁷，双人 3.73×10⁻⁷。显式随机化上游默认零初始化输出 head，避免全零结果掩盖错误。
- Ex-Omni Teacher 缩小完整主干与音频注入：3.58×10⁻⁷。
- Ex-Omni TQGF：普通/空文本、无遮挡/全遮罩，最大误差 4.77×10⁻⁷。
- MuseTalk Q4：真实权重输出 256² 人脸；显式框与测试遮罩完成 5 帧模板 MP4，未导入 Torch/cv2。
- Ex-Omni Teacher：Wan 1.3B + OmniAvatar + Teacher 检查点全部严格映射；缩小潜变量前向有限值。LoRA 按上游加载到同一个 adapter 的顺序覆盖，最后合并一次。

FlashHead 公开示例来自固定上游 `examples/girl.png` 与 `podcast_sichuan_16k.wav` 前两秒，BF16、4 步、512²、50 输出帧：

| 变体 | 本次生成耗时（已加载权重） | MLX peak bytes |
| --- | ---: | ---: |
| Lite | 3.21 秒 | 9,162,855,688 |
| Pro | 29.19 秒 | 11,276,478,186 |

这是一次两秒样例运行，不是稳态 benchmark，也未达到实时产品验收。Pro 与 Lite 在同一进程依次执行，peak 为进程统计，不等于各自独立 RSS。
已逐帧抽查画面，修复编码前重复归一化导致的白屏；帧数和音轨存在检查不能替代画质检查。嘴型准确度与官方输出成对比较尚待完成。

## 新增全量链路验证

- InfiniteTalk：7 个 Wan 14B shard + 单人 adapter 全部严格校验，分片加载把 MLX 加载峰值从 75,620,574,472 降至 47,715,940,176 bytes。正式 40 步、256²、9 帧窗口/5 帧重叠生成 10 帧、两个分块；人像抽查通过，峰值 56,075,920,378 bytes。与 Ex-Omni 并发运行耗时 293.82 秒，不可作为独立性能比较。
- Ex-Omni：真实 Thinker 输出 `[1,5,151936]`，对应隐藏状态经 Talker 生成 `[1,2,16]` 码本，全部落在合法范围；测试约 1.10 秒，MLX 峰值 18,416,041,662 bytes。单独 codec 解码 2 帧产生 3840 个有限音频样本，编码也已接通。
- Ex-Omni Teacher：原先裁掉文本尾部补零导致异常纹理；已恢复上游完整 512 位置，新增专用回归。50 步、256²、33 帧窗口生成 11 帧短片，人像抽查通过，27.70 秒，峰值 17,720,673,834 bytes。125 帧窗口、2 秒音频复测生成 51 帧，人像抽查通过；132.52 秒，峰值 17,767,849,146 bytes（期间并发运行小型回归，非独立 benchmark）。
- 运行隔离环境未安装 Torch，MuseTalk、Ex-Omni thinker/talker/codec 与视频链路验证未导入 Torch。开发 `.venv` 的 transformers 会发现并导入可选 Torch，因此没有用环境变量假装隔离。
- 分块帧数回归覆盖 Lite 9 帧和 Pro 5 帧重叠，以及 1、25、33、34、57、58、61、62 帧输出。媒体 float `[-1,1]`、音轨、边界均检查。
- Ex-Omni 参考音色 encoder：复用 Runtime 固定 ECAPA-TDNN，严格加载实际检查点；与 Ex-Omni 上游真实类 FP32 对齐最大误差 1.20×10⁻⁵。24 kHz 波形→`[1,1,1024]` speaker embedding→Talker 的无 Torch 链路已通过。
- Talker 使用 Runtime 已锁定的 mlx-audio；与 Ex-Omni 实际上游类的 prefill/逐 token KV cache 参考误差低于 4×10⁻⁷。

以上短样例不是完整口型质量验收，也不能代替长视频、取消回收和最终打包 Runtime 测试。

## 源码与 Runtime

源码目录位于 `packages/ai2apps-model-{musetalk,flashhead,avtr1,infinitetalk,exomni}-mlx/`。
当前为开发源码，没有用 Service manifest 宣称已安装可用。每个目录固定上游 commit 与权重 revision；检查点不提交到 Git。

推理使用 MLX、mlx-lm、已固定的 mlx-audio、NumPy、Pillow、PyAV、soundfile、scipy、tokenizers；MuseTalk 音频读取还使用现有 librosa。Torch 仅用于开发参考及受限 `weights_only=True` 离线转换，运行时不导入。当前没有证据需要新增数字人 Runtime；最终打包环境验证仍是独立门槛。

Wan VAE、Wav2Vec2 和媒体编码复用本仓库 EchoMimic 的已实现模块，保留来源说明。没有修改其他 Model Package、MoE kernel 或 Cloud。

## 继续顺序

1. MuseTalk 自动人脸检测/分割；FlashHead 全尺寸上游配对和长视频测试。
2. InfiniteTalk 480² 默认窗口与双人真实检查点验收。
3. Ex-Omni 完整对话、视觉/语音输入；继续质量与资源验收。
4. AVTR-1 已完成独立 MLX 图片+音频成片；继续渲染优化、正式依赖和 Worker/Service 接入。
5. 所有模型的独立推理和资源门槛通过后再接 Worker、Service manifest、Mini-App 与正式 Runtime 验收。

## AVTR-1 授权后实测（2026-10-01）

官方 TorchScript 下载成功并转换为 1315 个 safetensors 张量；所有神经网络均以 MLX 执行。单独生成入口检查未导入 Torch/ONNX Runtime。开发推理额外使用 ONNX 静态图解析和 OpenCV 裁剪/编码，尚未做最终 Runtime 依赖验收。

M5 Max / 128 GiB，FP32、TF32 关闭：10 秒 512²/25 fps 视频生成循环 39.01 秒（6.41 fps），MLX peak 5,936,069,464 bytes；不含加载和最后封装。HuBERT/运动/渲染分别 3.08/3.41/32.52 秒。四步 ODE 最大误差 1.88e-5，渲染解码 2.32e-5。视频有 250 帧与 10 秒音轨，抽帧检查通过，完整口型评分未执行。复现与边界见 [AVTR README](../packages/ai2apps-model-avtr1-mlx/README.md)。

AVTR 渲染优化复测：相同 10 秒素材，默认 FP32 路径 31.85 秒，可选 `--renderer fast` 25.86 秒（9.67 fps），MLX peak 4.41 GiB。快速模式只降低解码卷积精度，保持运动主干/归一化 FP32，并有非有限帧回退；12 组姿态像素比较和源缓存切换通过，完整样片无回退。仍未达实时；详细质量差异与边界见上述 README。

AVTR 第二轮优化：批量解码、GPU 像素转换/预取、有界异步直接编码已接入。默认 2 帧批次在快速模式生成相同 10 秒视频 23.75 秒、MLX peak 4.97 GiB；本次 5 帧批次为 24.17 秒/7.76 GiB。原始像素批量对齐、尾批次、非有限帧回退和 3 项编码集成测试通过。三维变形的布局/通道补齐/稀疏采样新实验没有显著收益，未保留；详见 Package README。
