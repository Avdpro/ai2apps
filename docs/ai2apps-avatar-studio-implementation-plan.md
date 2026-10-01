# AI2Apps 数字人 Package 技术方案与实现计划

更新日期：2026-10-01。状态：FlashHead 模型 0.1.0 已发布；恢复独立数字人 Mini-App 的开发与实机验收。

后续接入以 [通用数字人能力接口 v1](ai2apps-avatar-capability-contract-v1.md) 为设计依据：App 表达人像、驱动和结果要求，Host 负责能力协商、Provider 选择与模型参数映射。该接口的单人照片离线生成子集已在 Host 与 Mini-App 开发实现，完整公共 API 仍为设计稿。

本文面向 AI2Apps Package、Model Worker 和 MLX 实现工作。目标是在 Apple Silicon 上提供照片说话、模板口播和后续实时数字人 Mini-App。首批复用 EchoMimic V3 MLX、接入 MuseTalk 1.5 MLX；首个自主移植目标为 SoulX-FlashHead Lite，随后推进 Pro，并纳入 AVTR-1、Ex-Omni-2D、InfiniteTalk。

没有公开 MLX 实现不构成淘汰条件。选择依据是用户价值、成片质量、实际速度、内存和安装体积，以及移植和维护成本。优先复用现有 oMLX Runtime，只有依赖或 ABI 隔离确有必要时才新增数字人 Runtime。

本文中的里程碑、性能门槛和 Package 名称是设计决策；社区性能数据不是本机实测结果。许可证不参与本轮优先级评分，保留上游来源及 checkpoint 元数据。

## 产品范围

一个普通 App Package 提供多个 Mini-App，模型作为独立 Model Package 按需安装，Runtime 共享。建议 App Package 源码目录为 `packages/ai2apps-avatar-studio-suite/`，名称和 ID 在创建 manifest 时检查冲突后固定。

| Mini-App | 输入和输出 | 模型路线 |
| --- | --- | --- |
| 照片说话 | 人像图片和音频生成 MP4 | EchoMimic V3，后续 FlashHead |
| 模板口播 | 模板视频和新音频生成嘴型匹配的视频 | MuseTalk 1.5 |
| 高质量数字人 | 图片或上游明确支持的参考素材，加音频或文本条件生成视频 | FlashHead Pro、Ex-Omni-2D，分别呈现实际能力 |
| 实时数字人 | 持续音频输入与连续音视频输出，支持停止和打断 | FlashHead Lite，后续 AVTR-1 |
| 长视频数字人 | 长音频及参考素材生成分段连续视频 | InfiniteTalk，按实际支持开放多人物能力 |

首批只开放已经通过验收的入口。首批输入以用户提供的音频为准；文本转语音后续通过既有音频能力组合，不复制 TTS 引擎。实时传输与对话系统分阶段接入，不把 LLM、ASR、TTS 全部绑定为数字人模型的强制依赖。

MuseTalk 的嘴部重绘与照片驱动生成用途不同。UI 按任务组织，在任务内选择适用模型；不承诺各模型具有相同的姿态、全身、分辨率或时长能力。

## 已核实的基础

- `packages/ai2apps-runtime-omlx/service.yaml` 当前源码版本为 1.8.5，声明 MLX、Metal、ONNX、音视频编解码和视频生成能力，目标为 macOS arm64。
- 当前框架使用 Python 3.11 和 MLX 0.32.0。MLX 与现有原生扩展存在版本约束，新增模型不能自行替换框架版本。
- `packaging/build.py` 的最终裁剪规则会删除 `torch` 和 `cv2`。开发环境安装成功不代表正式 Runtime 可用。
- `packages/ai2apps-model-echomimic-v3-mlx/` 已有原生 MLX 实现、Worker Adapter 和 checkpoint 分发记录；当前声明异步生成，不提供 streaming preview。
- `ai2apps/model_worker/video_capabilities.py` 已支持参考图片、源视频、驱动音频等输入角色；`protocol.py` 和 `server.py` 提供请求、进度、结果 Artifact 和取消基础。
- Mini-App Broker 只执行已经明确实现和授权的能力。视频 Worker 存在，不意味着 Package Mini-App 已经能调用数字人生成。
- `packages/ai2apps-runtime-cuda-torch/` 是另一条 Runtime 路线，现有声明为 Linux ARM64/aarch64，不能视为通用 NVIDIA 平台支持。

以上是源码与配置核查，不代替目标设备上的已安装 Runtime 验证。

## 模型范围与移植顺序

| 模型 | 起点 | 实现重点 | 优先级 |
| --- | --- | --- | --- |
| EchoMimic V3 | 仓库已有 MLX Model Package | 复用安装、Worker 与权重，接入 Mini-App 并复测成片 | P0 产品基线 |
| MuseTalk 1.5 | 社区已有 MLX 核心及 FP16/Q8/Q4 权重 | 音频特征、人脸检测与分割、裁剪融合、完整视频流程 | P0 新模型 |
| SoulX-FlashHead Lite | 官方 CUDA 推理与权重 | 模型、音频编码、VAE、采样和分块状态的 MLX 移植 | P1 首个自主移植 |
| SoulX-FlashHead Pro | 官方 CUDA 推理与权重 | 单独验证 VAE 和配置差异，复用已证明兼容的模块 | P1 Lite 之后 |
| AVTR-1 | 官方 CUDA/TensorRT 路线 | 音频及运动模型、外观重建、三维采样和变形算子 | P2 实时交互 |
| Ex-Omni-2D | 官方组合式生成链路 | 逐级对齐语言、语音条件与视频生成接口，控制总体内存 | P2 高质量生成 |
| InfiniteTalk | 官方 Wan 系视频生成路线 | 音频条件注入、视频网络、VAE、长序列分段及多人对齐 | P3 长视频扩展 |

除 EchoMimic 和 MuseTalk 外，本轮未找到经过核验的完整公开 MLX 实现。每个模型开工时重新检查上游进展并固定代码 commit、权重 revision 和配置，避免重复移植。

### EchoMimic V3

沿用现有服务 ID、权重 revision、精度与 fast/exact 预设。已有音频编码器、VAE 和视频处理可作为其他移植的参考，但必须经过架构、权重布局和数值对齐后才能复用。

现有内存配置从 32 GiB 档起步，具体设备仍需复测。输出 25 FPS 仅描述播放帧率，不用于宣称实时生成。首批产品验收包括进度、取消、超长音频处理和共享输出。

### MuseTalk 1.5

优先审计 xocialize 实现，参考 dahai80 的完整流程经验。先固定一个实现来源，避免未经验证拼接两个项目。逐项完成：

1. 使用转换好的 MLX 权重，运行时不引入 PyTorch 权重转换。
2. 对齐音频采样率、mel、Whisper 特征和分帧窗口；社区 README 的 torch-free mel 待办必须在实际代码中核实。
3. 以 MLX 或 ONNX 实现完整人脸检测、关键点、分割和遮罩流程；CPU 执行不能被当作无 Torch 依赖的证明。
4. 处理无脸、多脸、遮挡、侧脸、模板循环及输入时长不一致。第一版多脸要求用户明确选择目标，未实现时明确拒绝。
5. 对比 FP16、Q8 和 Q4 的画质、嘴型、内存与速度后选择默认项。

社区 Q4 模型卡列出的体积约 1.51 GB，并不包含我们完整安装所需的所有前后处理模型和运行库。社区约 34 faces/s、batch=8 是核心吞吐参考，不作为端到端实时承诺。

### FlashHead Lite 与 Pro

先建立官方参考输入和中间张量，再移植音频编码器、主干网络、位置编码、attention、VAE 和采样流程。Lite 与 Pro 分别审计，不能仅替换权重即宣称兼容。

先以 MLX 标准算子和 attention 实现正确版本，确认 mask、精度、张量布局、缓存更新和分块边界；profiling 后才针对瓶颈编写 Metal kernel。CUDA FlashAttention 或 SageAttention 的调用形式不必照搬，但数学语义必须对齐。

先生成固定短片，再做连续分块。验证音频上下文、缓存重置、边界重叠、首帧与后续块、长时身份保持。量化、近似缓存和编译优化放在正确性基线之后。

### AVTR-1

拆分神经网络与 TensorRT 专用执行层。建立三维 grid sampling、warping、插值、坐标归一化及 padding 边界的独立参考样例。先提供正确的 MLX 实现，再依据耗时决定 Metal 优化。

完成单次驱动后再接持续会话、倾听和说话状态切换。新增 Runtime 无法替代 TensorRT/CUDA 算子的移植。

### Ex-Omni-2D

同时记录用户提供的 Hugging Face 仓库与官方代码、权重来源的对应关系。以实际可下载的完整链路为实施对象；未发布的蒸馏或 Student 权重不能作为首版性能假设。

分别验证文本与语音条件、语音单元或特征接口、视频生成和输出同步。Qwen 或 Wan 某个子模型已有 MLX，只减少该模块工作量，不代表整条链路已兼容。先测模块串行加载和内存回收，再决定是否支持驻留并发。

### InfiniteTalk

先验证单人物短片，再做长视频分段和多人音频映射。用边界样例检查口型、姿态、人物身份、帧重复或缺失和音频连续性。不得仅凭沿用 Wan 模块宣布完成。

## Package 与 Host 架构

调用顺序为：Mini-App → 受 mount 约束的 MessageChannel → Host Capability Broker → 模型选择与调度 → 隔离 Model Worker → Host Run 和 Artifact → Studio 共享预览与输出。

### App Package

- 使用现有 `ai2apps.package-manifest.v1` 普通 `app` 类型，`app.yaml.mini_apps` 为唯一 Mini-App 声明来源。
- 主要挂载到 Video Studio；仅提供 Mini-App 时设置 `navigation.launcher: false`，保留契约要求的顶层 entry。
- 页面只声明语义能力，不写模型下载 URL、Worker 地址、checkpoint 路径或安装计划。
- 复用现有 Bridge、草稿、设置恢复和进度契约。能力不支持时明确提示，不静默换模型。
- 输出归 Video Studio Host 所有，不增加每个 Mini-App 的历史、下载或拖拽实现。若以后挂载 Voice Studio，严格遵守 Quick Read 的唯一 Preview & Output 契约。

### Model Package

每个模型族使用独立 Service Package；Lite/Pro 或精度变体是否共包，由依赖和 checkpoint 布局决定。现有 EchoMimic ID 保持不变。

Adapter 复用 `video_generation` 请求及已验证的 `video_capabilities`。首批支持 reference_image 或 source_video 与 driving_audio 的明确组合。公开分辨率、时长、预设、取消和恢复能力必须与实际实现一致。

模型加载使用 Host 准备并验证的本地 checkpoint。Worker 离线运行，不在首次生成时自行下载文件。权重转换工具与推理依赖分离，转换记录包括源 revision、张量映射、dtype、量化配置、输出大小及 SHA-256。

### Host 接入

为照片驱动和模板口播增加明确的语义能力及受信任 ACPF Profile 映射，名称在实施时与现有 Registry 对齐。Host 负责模型选择、输入校验和媒体规范化、资源调度、进度取消、结果持久化及错误映射。

沿用当前 Broker 的 actor、mount、Package digest 和能力 allowlist 校验。安装后的 opaque-origin sandbox 不允许直连 Local API；开发时 same-origin 便利不能成为运行依赖。新增能力必须通过真实 Package mount 验证。

不预设需要 Cloud 改动。如遇现有 Cloud 契约缺口，另写变更需求交给 Cloud 项目。

## Runtime 决策

默认使用 `ai2apps.runtime.omlx`。第一轮只做缺口清单，不提前建立专用 Runtime。

| 依赖情况 | 决策 |
| --- | --- |
| MLX、ONNX 和现有媒体库即可完成 | 只增加 Model Package 与 Host 适配 |
| 仅缺少 OpenCV 等有限依赖 | 比较替换所需操作与加入 headless 依赖的成本，验证最终裁剪产物 |
| 需要重型 PyTorch/MPS、无法协调的 MLX/原生 ABI 或大量专用原生库 | 建立独立数字人 Runtime，复用 Worker 协议和发布设施 |
| 只适合 CUDA/TensorRT 的后端 | 使用独立 NVIDIA Runtime 路线，单列 OS 和架构支持矩阵 |

每个新增依赖记录 wheel、支持架构、安装字节、传递依赖、动态库冲突和离线导入结果。若调整共享 Runtime，必须回归既有关键推理路径，避免影响 MoE kernel 或替换其 ABI。

Runtime 和模型体积分别计量：压缩下载大小、展开安装大小、checkpoint 大小、转换临时空间与首次运行缓存。内存分别记录进程 RSS、MLX active/peak/cache 和系统内存压力，不把统一内存的重叠统计直接相加。

## 实时会话阶段

离线 MP4 完成后再定义增量音频输入和持续帧输出。已有 SSE 或字节流只提供传输基础，不代表双向会话已经完成。

会话契约需包含采样率和时间戳、chunk 序号、session 与 generation 标识、有界队列、背压、背压超限策略、取消与重新开始、断连清理、模型卸载和资源配额。打断必须使旧 generation 的排队帧失效，避免旧音频或旧嘴型继续播放。

先做本地 Host 会话。只有跨设备或网络会议需求确定后才引入 WebRTC/LiveKit，并单独评估其依赖。持续对话引入 ASR、LLM、TTS 后另测总延迟，不能沿用渲染器自身延迟。

## 验证与性能记录

### 数值正确性

固定上游 commit、checkpoint、输入、随机种子、采样器、dtype 和初始噪声。相同 seed 不保证不同框架生成相同噪声，因此保存并复用实际输入张量。

按模块保存参考张量，记录 shape、均值、方差、最大绝对误差和相对误差。容差依据 dtype 与模块误差传播，在优化前固定；不设一个覆盖全部扩散链路的任意阈值。验证张量布局、attention mask、时序 padding、卷积和 VAE 分块边界。

需要 CUDA 的参考链路在可用 NVIDIA 环境生成 fixture，并保存命令和校验值。若尚无参考环境，明确标记待验证，不以能出图替代数值对齐。

### 成片质量

用有使用权的固定人像与中英文音频，覆盖快慢语速、停顿、侧脸、遮挡、无脸、多脸、长音频和分块边界。检查身份保持、口型、牙齿和脸部伪影、动作自然度、闪烁和音画同步。

同模型移植前后采用成对样例。适用时记录 SyncNet 等口型指标及图像相似度，但不跨模型单凭一个分数排序。量化版单独对比基线并保留可回退精度。

### 性能口径

每次报告包含设备芯片、GPU 核数、内存、macOS、Runtime 和 MLX 版本、模型 revision、精度、分辨率、batch、音频长度、预处理与缓存状态。

- 冷启动：进程启动至模型可用；另记录 checkpoint 下载和准备耗时。
- 首帧延迟：可消费的首个音频输入至可显示首帧，单列预热情况。
- 端到端速度：完整成片时长除以总处理时长；同时报告模型核心 FPS 和预处理、推理、编码各阶段耗时。
- 实时性能：持续输入下的 FPS、P50/P95 延迟、队列深度和丢帧；batch 吞吐不能替代单流延迟。
- 稳定性：连续任务后的内存回收、取消延迟和失败恢复。

设备矩阵按实际可用设备填写；建议覆盖 16/24、32/48、64 GiB 以上档位，未测试的设备只标为待测。EchoMimic 等大模型可明确限制支持档位，不强求所有模型覆盖入门 Mac。

实时模式的拟定产品门槛为目标设备上连续 10 分钟端到端达到 25 FPS、队列不持续增长、无持续音画漂移；随后进行 60 分钟稳定性测试。未达到则继续提供异步视频生成，不能标为实时。首帧及打断延迟目标在首轮基线后确定并锁定。

## 实施里程碑

| 阶段 | 交付物 | 完成条件 |
| --- | --- | --- |
| M0 基线准备 | 源码与权重锁定清单、依赖差异表、样例和 benchmark 记录格式 | 核对最终 Runtime；确认参考执行环境；记录待验证项 |
| M1 Package 与 EchoMimic | 新 App Package、照片说话入口、Broker 与安装恢复、共享输出 | 在固定 App-Dev 环境完成真实生成、取消和跨 Mini-App 输出选择 |
| M2 MuseTalk | 完整无 Torch 推理流程、Model Package、模板口播入口 | FP16/Q8/Q4 对比和最终 Runtime 离线执行通过 |
| M3 FlashHead Lite | 权重转换、逐模块 MLX、参考对齐和短片基线 | 有参考对齐证据、完整视频输出及 Mac 性能记录 |
| M4 FlashHead Pro | 差异模块与精度、质量预设 | 独立正确性、质量和资源门槛通过 |
| M5 实时与 AVTR-1 | Host 会话协议、实时 UI、AVTR-1 MLX 与算子验证 | 有界缓存、打断、音画同步和持续运行验收通过 |
| M6 Ex-Omni-2D | 端到端链路 MLX 化、资源分档与高质量入口 | 实际发布权重完整运行，内存与质量记录齐全 |
| M7 InfiniteTalk | 长视频与按能力开放的多人入口 | 分段边界、长时稳定性及人物音频映射通过 |

2026-09-30 调整：先完成模型移植与独立 CLI/数值验证，再恢复 M1 和各模型 Mini-App。FlashHead 是首个自主移植模型。M5 至 M7 的先后可以依据前面实测结果调整，并在本文记录原因。未完成前一阶段的正确性基线，不叠加该模型的量化和近似优化。

## 第一批具体任务

- [ ] 固定 EchoMimic 现有实现及 MuseTalk、FlashHead 的上游 revision，列出完整文件和依赖。
- [ ] 检查最终 oMLX Runtime 的离线导入和模型运行能力，形成 OpenCV 处理决定。
- [ ] 创建普通 App Package 源码目录和两个首批 Mini-App，复用现有 Bridge 与样式规范。
- [ ] 增加数字人语义能力、ACPF 映射、Broker 调用和 Host 共享输出接线。
- [ ] 完成 EchoMimic 从安装恢复到成片、取消、错误恢复的产品闭环。
- [ ] 建立 MuseTalk 完整流程及 FlashHead 的转换和参考对齐工具，再推进模型实现。

### 2026 年 9 月 30 日实施进展

- 已创建 `packages/ai2apps-avatar-studio-suite/`，当前只声明照片说话；尚未接通的模型不展示可用入口。
- 已增加 EchoMimic 的 `video.avatar_generation` ACPF Profile、Broker 调用、图片与音频上传，以及现有视频队列到 Studio Run 和 Artifact 的接线。首版限定 512 × 512、exact/fast、音频最多 10 分钟。
- 已加入进度、停止生成及断连取消；复用已有 Artifact，Mini-App 不维护输出历史或下载实现。
- Package manifest 和 ACPF 校验通过；新增 Python 回归覆盖声明、权限、预设、输入上限、成功输出、Worker 失败和断连取消。与既有 Broker、视频队列、Mini-App、Video Studio 合计 76 项 Python 测试通过；Node 数字人取消、setup 和 Voice Studio 输出选择回归通过。
- App-Dev 界面控制按固定 bundle ID 和路径读取均超时，尚未完成真实 mount、控件可访问性和真实模型成片验收。测试进程退出时报告沙箱内 Metal 设备不可见；Python 回归通过不代表 GPU 推理通过。
- 仍需补齐：最终 Runtime 依赖审计，上游 revision 清单，真实安装恢复与成片验收，取消后的实机状态及 Host 重启中的任务恢复验证，M2 及后续模型。未下载新权重、变更 Runtime 或发布制品。M0、M1 均未标为完成。

### 模型先行阶段

最新逐模型状态、数值测试、真实权重测试和未完成项目见 [模型移植记录](ai2apps-avatar-model-port-status.md)。先前“未下载新权重”和沙箱内 Metal 不可见是 M1 当时的状态；本轮已在经批准的 Metal 执行环境下载固定权重并运行推理。

## 开发与发布验收

沿用 `docs/ai2apps-studio-mini-app-package-contract-v1.md`，在 `packages/` 创建源码，使用固定 `AI2Apps-app-dev.app` 开发环境。HTML/CSS/JS 刷新，Host Python 重启对应 Local；Runtime 或原生依赖变化才重建 App-Dev。

实施阶段更新 `docs/ai2apps-desktop-next-release.md` 中对应 Host 或 Runtime 变更项。保留工作区其他任务改动，不覆盖已有 Studio、Broker 和输出相关修改。

必要测试包括：manifest 与能力校验；安装与设置恢复；mount/actor 权限隔离；错误输入与模型能力不匹配；实际 Worker 生成；进度和取消；Artifact 持久化；共享输出和跨 Mini-App 选择；控件可访问名称及键盘操作。实时阶段补充背压、打断、断连和旧帧丢弃测试。

源码 mount 验收通过后，还需按正式 opaque-origin sandbox 安装验收。构建或发布前完整阅读 Package publication runbook，使用既有签名构建和发布脚本；Runtime 如有升级先发布并验证，再发布依赖模型。发布记录区分源码完成、实机通过和正式发布。

## 资料来源

- [Studio Mini-App 契约](ai2apps-studio-mini-app-package-contract-v1.md)
- [Package 发布流程](ai2apps-package-publication-runbook.md)
- [EchoMimic MLX 发布记录](ai2apps-echomimic-v3-mlx-dual-source-release-receipt-2026-08-27.md)
- [MuseTalk MLX 模型核心](https://github.com/xocialize/musetalk-mlx)
- [MuseTalk MLX 完整流程参考](https://github.com/dahai80/musetalk-mlx)
- [MuseTalk MLX Q4 权重](https://huggingface.co/mlx-community/MuseTalk-1.5-q4)
- [SoulX-FlashHead 官方代码](https://github.com/Soul-AILab/SoulX-FlashHead)
- [AVTR-1 官方代码](https://github.com/avaturn-live/avtr-1)
- [Ex-Omni-2D 官方代码](https://github.com/LOGO-CUHKSZ/Ex-Omni-2D-Code)
- [用户提供的 Ex-Omni-2D 仓库](https://huggingface.co/lemonade666/Ex-Omni-2D)
- [InfiniteTalk 官方代码](https://github.com/MeiGen-AI/InfiniteTalk)


## 2026-10-01 Mini-App 接入更新

独立 `ai2apps/avatar-studio-suite` 通过必需的 `video.avatar_generation` 能力解析可选模型，默认 FlashHead Lite，另有 Pro/EchoMimic。模型自身依赖 Runtime；Mini-App 不硬编码具体模型 Package 依赖。界面选项来自签名能力。

本轮替换旧的 HTTP 等待/断连取消路径，改为持久队列、显式取消、冻结输入重试及 Host 共享输出。前述“断连取消”为历史状态，现已废止。Mini-App 页面关闭不取消已接收的任务；Local 重启后的中断任务可重试，不支持推理中间状态续算。

修复 Host 后台 multipart 将结构化参考素材转成 Python 字符串的问题，改为 JSON 编码。发布仍需包含 Host 修改的 Desktop 版本与正式签名 Mini-App 沙箱验收，详见 Desktop 台账 NXR-AVATAR-MINIAPP-20261001。
