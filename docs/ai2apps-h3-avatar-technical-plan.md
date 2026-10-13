# H3 数字人固定音频与长视频续接方案

日期：2026-10-05。状态：原生 H3 口型不足，已接入自动 MuseTalk 精修并通过真实 Runtime 60 秒处理。长片亮度稳定性仍在验收，未公开发布。

## 目标与产品边界

在现有 MLX H3 上输入人物图片、用户录音和动作描述，生成保留原音轨的数字人视频。先验证 5–8 秒单段，再推进 30/60 秒连续镜头。沿用当前数字人 Mini-App 的统一能力、ACPF 和共享输出，不新增专用 Runtime。是否需要 Runtime 依赖升级，以真实安装验收为准。

H3 用于离线制作带身体动作的素材。FlashHead/AVTR 继续提供快速口播。固定背景轻动作可裁剪后回贴；挥手、转身等大动作生成完整画面，抠像交给 Composer。提示词控制的动作/情绪不能宣称为精确视线或时间控制。

## 已有能力与缺口

已发布 H3 0.9.1 提供 FL2VA、Ref2VA 和 LightX2V/OpenVDN 变体。源码在 `/Users/avdpropang/sdk/minimaxh3/ai2apps-package/`。现有 Ref2VA 参考音频放入条件区，目标音频仍采样；不具备严格 driving_audio 语义。不能直接给它加 avatar_video 标签。

现有 audio VAE、packing、双流 DiT、调度器和分阶段驻留可复用。需要新增目标音频 latent 保护、对应 token 的 timestep、采样掩码、视频上下文续接和分段恢复。MuseTalk 仅完成核心短样片，自动跟踪、遮罩和成片质量仍是独立工作，不能作为已就绪兜底。

本地历史性能基线：M5 Max/128 GiB，512×288/24 fps，LightX2V Q4 四步请求 5 秒耗时 37.39 秒，15 秒耗时 182.08 秒；OpenVDN Q4 八步请求 5 秒耗时 89.31 秒。这是普通视频测试，不是固定音频数字人测试，不据此承诺高清或长片速度。

## 固定音频单段

1. 保存原音轨和摘要，建立以原 PCM 样本数为依据的时长。
2. 全音轨只重采样一次到 H3 条件所需的 32 kHz 双声道；保持时间零点，单声道复制为双声道。
3. 用 Audio VAE 编码目标音频，将其放入目标音频区域；参考音频区语义不变。
4. 按上游掩码算法核对 protected token 的 noise、timestep、归一化、位置编码和调度器更新。仅冻结 latent 而继续传噪声 timestep 是不完整实现。
5. 保留音频 token 对视频的注意力作用；不能删除音频流来加速。
6. 首轮关闭 attention/velocity 缓存，先做基础模型正确性参照，再逐项启用并对照 LightX2V 四/八步。OpenVDN 后置验证。
7. 最终使用原音轨封装。容器不支持直接复制原编码时只做一次编码；“保留原音轨”指内容和时间，不承诺压缩编码后逐样本无损。

固定音频不自动保证嘴型准确；精修路线必须在 H3 结果不达标时独立评估。

## 连续镜头时间轴

初始配置 192 帧（8 秒）窗口、39 帧（1.625 秒）上下文，24 fps。首段产出 192 帧，后续完整窗口新增 153 帧（6.375 秒）。合法共同网格为 39 + 51*k；它同时满足视频 VAE 的 5 + 17*k 网格和 40 Hz 音频网格。

| 段 | 全局起点 | 保护上下文 | 新增画面区间 |
| --- | ---: | ---: | --- |
| 0 | 0 帧 | 0 | [0, 192) |
| 1 | 153 帧 | 39 | [192, 345) |
| 2 | 306 帧 | 39 | [345, 498) |

所有范围半开。最后一段缩到能覆盖剩余内容的最小共同网格，输出时删除多余帧。视频帧数为 ceil(音频样本数×24/采样率)，余量小于一帧，不截断或拉伸语音。

原音轨只在最终封装一次。每段音频窗按全局帧位置换算绝对样本边界，不累加逐段舍入误差；内部窗口使用真实后续音频，仅原始文件尾允许右侧补零。禁止音频 latent 长度不匹配后随意补 token。

### 视频上下文必须先验证

优先保留原始 latent，避免反复重编码，但不能直接假设上一段尾部 latent 可以任意切片：视频 VAE 的时间相位、因果缓存和重定位后的位置编码必须匹配。首轮做解码/重编码对照，再决定哪些 latent 可以复用。固定 latent 不保证解码像素完全相同。

原始人物参考与 FL2VA 首帧/续接上下文的同时使用也是待验证项；当前 MLX 禁止 references 与 images 混用，不能只靠 Host 拼参数绕过。

不默认在人脸上交叉淡化。检查每个接缝的身份、口型、光照和运动；不合格先重做该段，必要时重做后续依赖段。连接段与按句分镜作为备选。连续镜头不达标时不自动伪装成无缝生成。

## 接口与任务编排

内部实验请求包含 reference_image、driving_audio、prompt、seed、model/preset、resolution、window_frames、context_frames。上述窗口参数先不暴露给普通用户。

Host 负责冻结素材、分段、取消、恢复、全局时间轴和最终封装；Worker 负责音频编码、受保护条件与单窗口采样。运行记录存储模型/权重摘要、输入摘要、参数、每段 seed、前驱摘要和输出摘要。前段重做后，下游缓存失效。字幕按原音轨时间生成。

验收后再给签名模型声明增加 avatar_video 与 reference_image + driving_audio，接入现有 Mini-App。连续长度由编排器提供，不把模型单窗上限改成 60 秒。不先承诺旧 Runtime 具备新接口，不发布未经真实推理验收的声明。

## 阶段与验收

- P0：文档、绝对时间轴、尾部补齐、半开帧区间、采样网格测试。当前已开始。
- P1：5–8 秒固定音频原型；同图片/音频/seed 对比普通 Ref2VA、基础固定音频和 LightX2V。至少中文快语速、停顿、英文各一例；逐帧检查爆破音闭唇及静音闭嘴，记录可用同步评估和人工结论。
- P2：两个窗口续接，再推进 30/60 秒。检查无缺帧/重复帧、原音轨无重复/漏字、偏移不随段数累积；接缝及身份人工验收。时间对齐自动检查目标小于一帧；感知口型阈值需与现有模型基线共同校准。
- P3：只有 P1 不足时推进 MuseTalk 精修，对侧脸、手遮挡、牙齿和表情单独验收，不默认全片强修嘴部。
- P4：Mini-App/ACPF 接入、签名包独立安装、取消/恢复及共享输出验收，然后发布。

每次真实跑测记录机器、源码提交、权重版本、冷/热总耗时、音频编码/DiT/解码/封装分项、MLX 峰值及进程内存、成片时长、失败次数。优化先证明质量不退化，再报告速度。

## 本轮实现

`ai2apps/avatar/h3_timeline.py` 提供实验性窗口规划与 32 kHz 条件音频样本范围。尚未接入生产 Provider，不代表固定音频或连续镜头已跑通。

## 参考

- 官方模型能力：https://github.com/MiniMax-AI/MiniMax-H3
- 社区掩码与时间网格实现：https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef/blob/main/TECHNICAL_ARCHITECTURE.md
- 本地性能记录：`/Users/avdpropang/sdk/minimaxh3/docs/h3-mlx-variant-evaluation.md`
- 现有数字人状态：`docs/ai2apps-avatar-model-port-status.md`

### P0 验证结果

2026-10-05：`python -m pytest tests/test_ai2apps_h3_timeline.py -q`，33 passed。覆盖 16/32/44.1/48 kHz、亚帧短音频、非整数秒、30 秒接缝布局及长序列样本舍入。首次从 ai2apps 子目录运行被同名 secrets 包影响，改从仓库根目录运行通过。退出时沙箱提示无 Metal 设备；本轮只执行 CPU 时间轴测试，未进行 GPU 推理。

### P1 实现进展

H3 源码新增 `driving_audio` 和 `video_context` 路径，位置在 minimaxh3/ai2apps-package/src/minimax_h3_mlx。当前调度器使用 t=1-sigma，干净条件必须是 **t=1.0**。固定目标音频同时绑定 clean timestep、latent 和每步更新，最终跳过音频 VAE 重建。受保护视频前缀按上游使用 t=max(t_video, 0.999)，同时混入 0.001 的原目标噪声；逐步恢复受保护 latent。第一轮视频上下文使用解码帧重编码以验证时间相位，尚未直接复用尾部 latent。

`avatar.py` 提供分段生成、磁盘片段存储、原音轨统一封装、逐步取消和依赖摘要恢复。缓存绑定输入、权重身份、采样参数及实现源码；前段失效后不复用下游。`avatar_timeline.py` 是当前 Host 实验时间轴的 Package 内副本，使安装后不依赖尚未发布的 Host 模块；接入阶段需同步测试两个文件一致性。

新增 MLX 掩码及既有打包/调度器回归 9 项通过；使用模拟模型和真实 FFmpeg 的三段重叠、损坏恢复、原音频窗口及取消测试 2 项通过。真实基础 Q4、50 步、512×512、90 帧固定录音测试正在执行，未出视觉验收结论。

Worker 接入使用独立的 avatar-base-4bit、avatar-lightx2v-4step-4bit、avatar-lightx2v-8step-4bit 身份（尚未写入对外模型声明）。原普通视频模型保持 15 秒契约。新身份复用原有 pinned Distribution；音频入口遵循现有 reference_image + driving_audio 和 preserve_driving_audio 语义。新增 adapter 输入及原 Worker 回归 21 项通过。

### 2026-10-05 真实样片与对照

机器为 Apple M5 Max / 128 GiB，Q4 基础权重，512×512、24 fps，关闭近似 attention/velocity 缓存。

| 测试 | 输出 | 模型/总耗时 | MLX 峰值 | 结论 |
| --- | --- | --- | --- | --- |
| Base 50 步固定音频 | 90 帧 / 3.75 秒 | 607.67 秒模型时间 | 19.21 GB | 画面稳定，未独立证明准确口型 |
| LightX2V 4 步固定音频 | 90 帧 / 3.75 秒 | 69.90 秒模型时间 | 29.98 GB | 约快 8.7 倍，速度比较不等于质量相同 |
| 4 步、强说话提示、静音 | 90 帧 / 3.75 秒 | 56.49 秒模型时间 | 29.98 GB | 静音仍张嘴，拒绝据此宣称同步通过 |
| 4 步、中性提示、静音 | 90 帧 / 3.75 秒 | 120.87 秒模型时间 | 29.98 GB | 接触表显示闭嘴；本次与前一任务有短暂资源重叠，不作速度基线 |
| 4 步、90 帧窗、39 帧重叠，三段 | 154 帧 / 6.416667 秒 | 267.17 秒端到端 | 29.98 GB | 原始音轨 6.400167 秒；容器音轨 6.400 秒，后段构图轻微漂移，继续验证 |

测试输出位于 /tmp/h3-avatar-fixed-base、/tmp/h3-avatar-fixed-light4、/tmp/h3-avatar-fixed-light4-silence、/tmp/h3-avatar-neutral-silence、/tmp/h3-avatar-continuation。三段测试使用视频前缀 t=1.0 的早期实现；之后已按 ComfyUI PR #15375 对齐 0.999，不能把旧样片当成修正后的验收。相关新入口、掩码、分段恢复和原 Worker 回归共 27 项通过。

中性提示的语音对照正在进行。MuseTalk 额外精修只处于实验评估，尚无自动人脸分割或精修质量保证。不得将静音闭嘴单项结果等同于中文/英文音素同步通过。

### Package 工程补齐与当前质量门槛

- 成片分段编码和拼接已改用 Runtime 自带 PyAV：H.264 无 B 帧片段逐包复制，使用绝对时间戳连接；原始单/双声道只编码一次 AAC。无需外部 FFmpeg 程序。新增测试覆盖 39/51/17 帧连接、逐帧 PTS、左右声道脉冲和中途取消保护。
- 缓存可写入 context.data_root/h3-avatar-work，跨 request.output_root 清理后仍能恢复；按源码/权重/输入摘要分区，保留最近四项和七天期限。已加入请求目录删除后的恢复测试。
- Host 会把公开 model ID 改写成 upstream_id。数字人别名因此使用独立的 :avatar upstream 标识，权重仓库与 Distribution 不变；已覆盖两种标识的路由测试。
- 中性提示词的语音样片同样几乎保持闭嘴。当前只能证明提示词影响显著，不能证明四步模型能准确对口型。
- MuseTalk Q4 在插画和公开照片上完成 90 帧精修，但插画嘴周风格变实、细节下降，静音仍有开口，尚未通过可用性门槛。精修实验是 Host Vision 自动框 + 试验椭圆遮罩，不是完成人脸分割，更没有声明为可安装能力。
- 后续先检查未蒸馏基础模型与同步评估，再决定是否使用 H3 动作底片加语音驱动的局部精修。Package 尚未签名构建或发布。


### SyncNet 与长片验收补充（2026-10-05）

评估工具采用官方 SyncNet 源码 907c0b579c2e2d83f0eae1b2ac9e720cde4e5623，权重 SHA-256 961e8696f888fce4f3f3a6c3d5b3267cf5b343100b238e79b2659bff2c605442。先复现官方 example：offset=3、confidence=10.053。人物框使用 macOS Vision，裁剪几何沿用上游；卡通人物属于域外样本，因此只作同素材对比，不能把分数当通用质量阈值。开发评估依赖不进入模型 Package。

| 3.75 秒中文样片 | 偏移（25 Hz 评估帧） | confidence | distance |
| --- | ---: | ---: | ---: |
| H3 Base 50 步，明确说话提示 | 0 | 3.675 | 10.645 |
| H3 LightX2V 4 步，明确说话提示 | 0 | 3.031 | 10.849 |
| H3 Base 50 步，温和说话提示 | 0 | 3.515 | 10.563 |
| H3 LightX2V 4 步，中性提示 | 13 | 0.617 | 15.258 |
| 同一 LightX2V 视频配倒放语音（负对照） | -6 | 1.422 | 11.398 |
| LightX2V 后接 MuseTalk | 1 | 3.559 | 10.607 |

明确说话提示下，固定音频有可测的同步信号。中性提示容易闭嘴；强说话提示配全静音仍会张嘴。MuseTalk 会软化画风、引入约一帧偏移，本版本不作为默认后处理。

30 秒、720 帧、5 窗口首轮耗时 957.29 秒，MLX peak 29.98 GB。素材为 3.75 秒中文片段和 1 秒静音拼接的测试夹具。前缀掩码已使用 0.999，但解码后重新编码上下文导致后段人物/背景逐步变形，接缝邻帧 MAE 4.63–5.12（全片中位数 0.986、P95 2.494）。此轮质量不通过，不能标记长片可用。

修正方向：直接保存归一化视频 latent 尾部。192/39 帧对应 57/12 latent 帧，窗口起点相差 153 像素帧 = 9 个 VAE chunk = 45 latent 帧，保持 17 帧 chunk 相位。首个解码交叠区可能改变，但处于丢弃的 39 帧上下文内。尾部 latent 进入私有缓存的哈希链，不再反复图片编码；实际长片对照仍在运行。普通视频调用不返回/持有该缓存。


### 签名安装、直接 latent 续接和英文对照

- 本地签名候选 `ai2apps/model-minimax-h3` 0.10.0，154067 字节，SHA-256 `204d83d82b8d561d8fb05007a9d5dd3cac3193601ebdb28b95c77dbde03f4b99`。仅为候选，不代表质量通过；尚未公开提交。
- 已用标准独立安装脚本安装 Runtime 1.8.8 与候选包，通过真实 Managed Service Sandbox 生成英文真人照片样片（2.796 秒音轨、68 帧、107.19 秒）。使用 Runtime 内 Python 3.11，未使用开发虚拟环境推理。此项证明安装/协议可用，不代表口型质量通过。
- 安装测试对已拥有的本地权重执行离线逐文件签名摘要验证，未代填用户地域/许可声明，未下载新 H3 权重。基础权重 41,108,034,229 字节，四步适配权重 1,383,679,204 字节。开发 config 多了一个未参与当前管线计算的 variant 字段；测试目录恢复到公开 manifest 的精确配置 SHA-256，未修改原开发目录。
- 直接 latent 的 30 秒对照：720 帧，814.38 秒，MLX peak 29.979 GB。人脸/衣物细节比重编码对照稳定，但旧组装边界 MAE 仍为 4.03–5.62。查明每个 VAE 解码窗口末尾五帧依赖下一段上下文；已改为延后这五帧，使用下一窗解码器本身的交叠输出，未添加二次人脸淡化。生产 VAE 拼接算法的轻量回归证明组装输出与一次连续解码逐帧相同；新组装尚待真实长片验收。
- 30 秒直接 latent 样片逐句 SyncNet 偏移为 -1/-2/-2/-2/-1/-2 帧（25 Hz 评估）；没有逐段增长。全片 confidence 2.097、distance 10.139，含静音区。不能用其替代真人英文验收。
- 英文四步原生样片 SyncNet 落到搜索边界 -15 帧，confidence 1.333、distance 16.161；明确英文提示也无改善。基础 50 步对照和首段 39 帧静音预留对照继续排查。
- MuseTalk 局部嘴部精修作为 P3 对照：英文 confidence 5.299、distance 9.015，原封装有 -2 帧偏移。独立更正原音轨封装后变为 -1 帧、confidence 5.007、distance 9.455；有嘴部柔化，尚非成品。自动检测/遮罩与 Model Package 仍未实现，不宣称已经可安装。
- 修复 MuseTalk 现有开发源中的无 PTS AAC priming、立体声混单声道、按视频帧截音轨以及 floor 尾帧问题。新增 22.05 kHz 双声道随机脉冲相关性测试通过，解码起始误差不超过 2 个采样点。只修改未发布的 MuseTalk 源码，没有影响已发布模型。


### 自动口型精修推进

英文基础 50 步仍失败（SyncNet -15 帧搜索边界，confidence 1.567，distance 15.477）；39 帧静音预留后仍偏移 -4 帧，confidence 1.996。仅改变 H3 提示/步数不能作为产品级口型方案。采用 H3 动作底片 + MuseTalk 局部嘴部精修进入 P3 验证。试验将 24 fps 音频特征 padding 改为 25 fps 相位未改善，因此保持官方 ceil(50/fps) 规则。

自动前处理复用纯 MLX YuNet 图执行器和 BiSeNet；无需 Vision、ctypes、ONNX Runtime 或新 Runtime。BiSeNet 对官方 PyTorch CPU、相同 BF16 权重转 FP32 的 512²照片输入：argmax 一致率 100%，logit 最大差 4.34e-5、平均差 1.18e-6。嘴部 11/12/13 类扩张并羽化，保持上半脸与原背景。完整自动英文片段 68 帧的 CPU 前处理耗时 17.25 秒。口型与融合观感待完整视频验收，不能把分割数值对齐当成生成质量通过。

60 秒真人英文长片（10 窗、1440 帧）正在验证新的五帧解码 holdback。期间有 CPU 前处理和短片 GPU 精修，整轮耗时不作为无资源竞争的速度基线。

发布准备：通过标准脚本读取当前 Dev Installation 会话，返回 an active user session is required；没有读取浏览器 Cookie，也没有创建提交。先完成模型/素材和本地验收，再解决发布身份。旧候选仅验证安装链路；新增精修权重必须先经过固定双源 revision、Distribution 签名发布，之后才更新正式 Package 版本与声明。


### 60 秒与全自动精修验收

真人英文 60 秒、1440 帧、10 窗口的原生 H3 耗时 1692.10 秒，MLX peak 29.979 GB；有其它测试资源重叠，不作纯性能基线。视频和 AAC 音轨均为 60.0 秒，逐帧时间戳误差 0。新版接缝邻帧 MAE 0.894–1.180，全片 P95 0.898；接缝不再有旧版明显错位，但后半段逐渐变暗，视觉验收仍失败。

全自动口型精修在安装的 Runtime 1.8.8 / Python 3.11 完成，额外 161.12 秒，MLX peak 4.369 GB。开头、16.5、32.96、56.04 秒四个语句的 SyncNet offset 均为 -1 帧，confidence 分别 5.315/5.634/5.368/3.903，未累积漂移。短英文自动精修 offset -1、confidence 5.512；中文插画 offset +2、confidence 3.128。成片使用原音轨，精修限定嘴部，仍存在局部纹理柔化。仅支持正面、清晰、无遮挡单人；未把侧脸/遮挡泛化列为已支持。

已接入 Worker 串行阶段进度与取消：H3 动作底片 → YuNet/BiSeNet 自动嘴部准备 → MuseTalk 精修 → 原音轨成片。失败不返回未精修底片；临时底片清理，最终文件原子替换。首版声明计划限定 512² 内部处理、1–60 秒音轨；原图任意尺寸仍由 Host 裁剪回贴。新增代码依赖在 Runtime 1.8.8 中全部存在，不需新 Runtime。

亮度修复试验：后期分位数调色会放大暗部色块，未加入产品。正在验证续接 latent 与原图 first-frame 条件同时存在的显式实验开关。条件行和受保护目标行分开，时间步单元测试通过。尚未把该开关设为默认。

精修资产固定双源：HF Avdpro/H3-Portrait-Refiner-MLX @ b19653717a136186461fd1fa9ae7a6af000090a3；ModelScope ai2apps/H3-Portrait-Refiner-MLX @ 861f0228351bfd7a2ded792e791b25030f4f8710。包含 MuseTalk、YuNet、BiSeNet 和原始组件条款，不含用户素材或 H3 权重。首次双端完整回下载正在进行。新 Distribution 未发布前不升级正式模型声明；候选生成器先检查受信任 Registry 是否存在该 Distribution。Dev 和 App Dev 的 Installation 会话均返回需要 active user session；未读取 Cookie、未创建提交。


### 最新验收：原图末帧条件与口型精修（2026-10-05）

续接窗口同时使用受保护 latent 前缀与原图末帧软条件。first-frame 条件未能阻止变暗，因此未采用；末帧条件在完整 60 秒测试中保持人脸及背景亮度。该策略已接入 Worker。仍保留五帧解码 holdback 和原音轨一次封装。

M5 Max / 128 GiB、512×512、24 fps、4 步 Q4：H3 60 秒/1440 帧耗时 1569.60 秒，MLX 峰值 29.980 GB；安装的 Runtime 1.8.8 精修额外 144.33 秒，峰值 4.369 GB。合计 1713.93 秒（28.57 分钟，约 28.6 倍片长）。视频/音轨均 60 秒，逐帧 PTS 误差 0。精修后接缝 MAE 0.952–1.185，全片 P95 0.906。四个语句 offset 均为 -1 个 25 Hz 评估帧（约 40 ms），confidence 5.315/5.710/5.169/4.467，无累积偏移。抽样接触表已检查；此结果不代表侧脸、遮挡等输入同样可靠。

50 步英文底片也完成自动精修：额外 8.70 秒，offset -1、confidence 4.947。首版两个入口为 4 步 Turbo（1–60 秒）和 50 步（1–8 秒），推荐至少 64 GiB 内存。现有 Mini-App 共用 avatar_video 契约，任意原图尺寸由 Host 裁剪回贴。Worker/适配器 26 项、时间线/媒体/遮罩/通用数字人 72 项回归通过。

新增精修 Distribution 已签名，双端全量回下载 20 文件、184 pieces、1,536,290,232 字节一致。ID 为 dist_ai2apps_h3_portrait_refiner_b1965371_v1，manifest digest 为 sha256:86622208693a231725f898776ff1a8ca18835e3c075aeb9d1a1252b1aa3f2d59。当前尚未发布，不能据此声称正式 Package 已构建或安装验收完成。已发起本次 Package 0.10.0 与该 Distribution 的 Cookie 授权问题；Installation 会话不可用，未读 Cookie、未创建 Cloud submission。

待授权后使用标准脚本完成 Distribution 提交/审核/发布和公网签名回读，再运行受 Registry 检查保护的候选生成器、标准 Package 构建、真实隔离安装与推理，最后正式发布并增加 ACPF 入口。旧 native-only 0.10.0 本地归档口型失败，禁止发布。发布辅助脚本和签名材料保存在 artifacts/h3-avatar-20261005/release/；最终长片为 artifacts/h3-avatar-20261005/photo60-endanchored-refined.mp4。


### 交付完成（2026-10-06）

H3 0.10.0 原始 accepted 字节正式发布，submission 1701c811-203a-469b-9227-b1a56f19b90e，Snapshot 255，匿名完整下载验签通过。Cloud 候选恢复后未重建制品。两个入口各自绑定公开精修 Distribution，共用相同固定双源权重。真实双入口安装推理、生命周期、Mini-App 模型发现和原图回贴规划已验证，60 秒质量证据见正式回执。Host 新增两个 ACPF 选项并通过 23 项回归，随后续 Desktop 更新分发；本轮不涉及 Desktop 发布。详见 ai2apps-h3-avatar-package-0.10.0-release.md。


## 后续版本：完整变种选择与宿主持久长任务（2026-10-06，进行中）

0.10.0 是两入口且限制 60/8 秒的已发布版本；不能把它视为完整的任意长片和全部 H3 变种交付。后续不只放宽 duration 字段。

- 逐一验证现有八种 H3 motion 配置：FL2VA Q4/Q8、Ref2VA Q4/Q8、LightX2V 4/8 步、OpenVDN DMD8/StageB50。Ref2VA 需要参考条件与 latent 续接兼容实现，不能把 FL2VA keyframe 路径直接套用。
- 宿主固定图片、完整音轨、参数、Package digest 与 checkpoint pins；每次只执行一个窗口，调度器可在段间释放 GPU。任务私有中间产物包含视频、模型续接状态和全局帧区间；输入或模型身份变化不可复用。
- Host 持久保存有摘要的连续段。取消/重启后验证已完成前缀；损坏段及其后继重新执行。最终保留原音轨并合成到原图画布，只有整片成功才进入统一 Output。
- 已新增 avatar/segments.py 和 avatar/segment_jobs.py：有界 ZIP_STORED 协议、文件摘要、任务/前驱绑定、原子接收、连续帧覆盖、取消恢复。基础测试覆盖长于 60 秒及一小时计划、损坏段恢复、模型/输入改变、路径与重复成员拒绝。尚未接入实际 Worker/VideoTask，也未对外声明支持。
- 后续口型精修必须按全局音频位置保留 Whisper 上下文；禁止直接重置每段音频相位。需要段边界 SyncNet/视觉验证以及真实重启/取消续作证据。内存/资源控制按每段计算，总时长由输入资源约束而不是旧 8/60 秒门槛决定。


### 2026-10-06 分段执行进展

Host 的 VideoTask 已在显式 `avatar_segments` 声明下接入单窗口调用，持久记录模型 Package 摘要、输入摘要和状态前驱。每个窗口生成后验证 MP4 的帧数与时间戳，最终只合并一次完整原音轨。重试仅读取同一用户的已终止任务，仍逐段验证；正常退出时将未完成的分段任务恢复为队列状态。

Worker 新增单窗口生成与全局时间口型精修。Whisper 按原始 30 秒边界提取所需块，不在窗口边界重新起算音频特征。真实 60 秒音轨的四段（含 30 秒边界）与整段特征完全一致。真实 187 帧精修耗时 23.20 秒，24 FPS 时间戳连续，临时视频没有音轨。

八个 H3 变种的内部路由已接入，尚未写入发布声明。Ref2VA 保留其参考图输入路径，与 FL2VA 首尾帧条件分别处理。发布前仍须完成每个变种的实际质量、速度与跨窗口验收，以及超过 60 秒的真实长任务和 App 操作验收。现有 0.10.0 的限额没有通过修改已发布归档规避。


#### 分段验收和后续运行

- 真实两窗口 9 秒结果：216 帧、视频与音轨均 9 秒、时间戳误差 0；总耗时 261.20 秒。跨接缝 5–9 秒 SyncNet 为 -1 个评估帧（-40 ms），confidence 5.211。产物保存在 `artifacts/h3-avatar-20261006/segmented/`。
- Worker 请求/封包定向测试 9 项通过；Host 用户取消与正常关闭交错测试通过。模型版本变化时，旧缓存不进入新模型重试。
- Host 拼接不依赖模型 Runtime 的 soundfile；采用标准库 WAV 读取元数据，已有 PyAV 流式编码完整音轨。双声道 AAC 延迟实测不超过 2 个采样点，保留音轨尾部。
- `experiments/h3_avatar/validate_segmented_variant.py` 覆盖真实 Worker adapter、所选变种依赖、分段封包、完整音轨合并和时间/峰值内存统计。八变种 `--validate-only` 均通过，这只是文件与绑定检查，不代表质量验收。
- 69 秒长任务及其后的八变种串行 smoke 正在独立测试进程中执行。尚未发布新的模型声明、Package 或 Desktop。


### 69 秒真实跨窗口结果（2026-10-06）

69 秒音轨已完成 11 段、1656 帧生成；H.264 视频和 AAC 音轨均为 69.0 秒，帧时间戳误差为 0。总耗时 2225.39 秒（37.09 分钟，M5 Max / 128 GiB，含加载、分段精修与拼接；同时存在轻量 Host 验证，不作为严格稳态吞吐基准）。5–9、29–33、58–63、64–69 秒四处 SyncNet 均为 -40 ms，confidence 分别 4.701、4.741、5.197、5.669。联系图检查未见累计亮度或人物位置明显漂移；局部嘴部仍有柔化。详细 JSON 和完整视频已保存到本仓库 artifacts。

六个新增 avatar 模型身份的 Distribution 已用原 Publisher/密钥完成本地签名与双端全文件校验，每个绑定同一 20 文件、184 pieces、1,536,290,232 字节资产，未公开发布。旧 0.10.0 两个 Distribution 保留。新候选计划使用 0.11.0，须等待全部变种效果/速度及真实安装验收，不能提前宣布交付。

新版内层 `service.yaml` 将要求 `compatibility.features: [avatar.segmented-jobs.v1]`。Host 使用现有功能门槛检查，新旧 Host 允许/拒绝的单元验证及 Package 37 项回归通过，无需 Cloud schema 扩展。该功能代码仍需随 Desktop 更新分发。

发布会话状态：标准脚本以 Dev Installation session 只读查询 Publisher 返回 active user session required；未读 Cookie。原 Publisher 和公钥已通过最新匿名签名 Index（107）及精确 Keychain 记录派生指纹复核。后续需要管理员会话时，须依发布手册为 0.11.0 单独获得授权；不复用已完成的 0.10.0 授权。


### 变体短片验证与输入配额（2026-10-06）

四种变体的真实 Worker 单秒 smoke 已完成：LightX2V 4 步 42.34 秒、LightX2V 8 步 62.78 秒、OpenVDN DMD8 83.59 秒、Ref2VA Q4 50 步 298.85 秒（均含进程及加载开销，不代表稳态速度）。四份输出均为 24 帧 H.264 / AAC，时间戳误差 0；首尾图未发现损坏、随机噪声或主体丢失。其余变体继续串行验证，单秒结果不替代跨窗口验收。

其余七种变体已安排串行 9 秒两窗口验收；调度会等所有短片 smoke 成功后启动，遇到失败立即停止，避免多个推理进程争抢 GPU。Turbo 4 步已有 9 秒和 69 秒证据。

标准化音轨为 16 kHz 单声道 PCM16；沿用现有 Host/Worker 100 MiB 输入边界，Host 实际允许的分段任务时长为 3276 秒（54 分 36 秒），取模型声明上限与资源配额的较小值。8 秒是内部生成窗口，不再限制总视频时长。17 项 Avatar Studio 测试通过，包含资源边界校验；相关 Host 模块 Ruff 检查通过。

H3 0.11.0 及其六个新增权重 Distribution 的 Cookie 授权已单独请求，尚未获得答复；继续独立验证，未读取 Cookie 或创建 Cloud submission。候选声明准备脚本在执行前强制匿名验证全部八份 Distribution 已公开，因此未提前修改现有 service.yaml 的版本与权重绑定。


安装后恢复验收脚本已准备：`experiments/h3_avatar/validate_host_recovery.py`。它要求真实安装模型，在第二段已进入 Worker 后重建持久队列，随后主动取消并重试，核对第一段只调用一次、私有封包摘要不变、最终视频 216 帧且只有成功任务发布 Artifact。目前仅通过语法与 Ruff 检查，尚未执行，不计作端到端验收通过。短片验证已到六种，FL2VA Q8 总耗时 308.52 秒；24 帧与时间戳检查、首尾画面检查通过。


### 八变体短片结果（2026-10-06）

八种真实 Worker 单秒输入测试均成功，24 帧、H.264/AAC、PTS 误差 0。每种按完整一秒均匀抽样 12 帧检查，中间画面未发现随机噪声、主体消失或损坏帧；嘴部柔化和生成式头部/表情变化仍存在。下表含进程启动和加载开销，不能按倍率外推长视频速度，也不是严格稳态基准。

| 变体 | 步数 | 整体耗时（秒） | MLX 峰值（GiB） |
|---|---:|---:|---:|
| lightx2v-4step-4bit | 4 | 42.34 | 27.92 |
| lightx2v-8step-4bit | 8 | 62.78 | 27.92 |
| openvdn-dmd8-4bit | 8 | 83.59 | 38.36 |
| ref2va-4bit | 50 | 298.85 | 17.89 |
| ref2va-8bit | 50 | 319.11 | 33.31 |
| base-8bit | 50 | 308.52 | 33.31 |
| openvdn-stageb50-4bit | 50 | 456.25 | 21.62 |
| base-4bit | 50 | 322.04 | 17.89 |

剩余七变体的 9 秒跨窗口任务已经启动，首先是 Ref2VA Q4；当前短片结果不替代跨窗口与实际签名安装验收。原始视频、12 帧联系图与 JSON 已保存至 `artifacts/h3-avatar-20261006/variants/`。


### Ref2VA Q4 两窗口实测（2026-10-06）

9 秒输入已通过真实两窗口生成与口型精修：216 帧，视频和音频均 9.0 秒，PTS 误差 0；接缝 187 处 RGB 帧差 1.062，低于整片帧差 p95 1.283。检查接缝前后 185–189 帧及全片均匀采样，未见人物位置、背景或曝光突变；生成式表情变化与嘴部柔化仍存在。5–9 秒 SyncNet 偏移 -40 ms、confidence 7.470。模型内部总耗时 2590.27 秒（43.17 分钟），第一窗口 1870.32 秒、第二窗口 719.91 秒，MLX 峰值 19,214,764,700 bytes。该结果属于直接 Worker adapter 原型，未替代签名 Package 的实际安装/重启验收。

结果存于 `artifacts/h3-avatar-20261006/variants/avatar-ref2va-4bit/continuation9/`；其余六种跨窗口任务继续串行，当前为 Ref2VA Q8。Turbo 4 步先前已通过 9 秒和 69 秒结果。


### Ref2VA Q8 两窗口实测（2026-10-06）

9 秒两窗口结果：216 帧，视频/音轨均 9.0 秒，PTS 误差 0；接缝 187 处帧差 1.176（全片 p95 1.683），逐帧检查接缝未见人物位置、曝光或背景突变。5–9 秒 SyncNet 为 0 ms、confidence 7.785。总耗时 2629.24 秒（43.82 分钟），MLX 峰值 35,764,931,228 bytes。此单样本同步结果不能推导 Q8 普遍优于 Q4；两者都属于速度较慢的 50 步选项。结果归档到 `artifacts/h3-avatar-20261006/variants/avatar-ref2va-8bit/continuation9/`。

当前跨窗口验收已完成 Turbo4、Ref2VA Q4、Ref2VA Q8；8 步 Turbo 正在运行。标准 Installation 发布会话再次只读查询仍返回 active user session required，未读 Cookie、未创建 Cloud submission。


### LightX2V 8 步两窗口实测（2026-10-06）

9 秒两窗口输出 216 帧，音视频时长均 9 秒、PTS 误差 0；全片与接缝 185–189 帧检查未见突发位置/背景/曝光变化。接缝帧差 1.116，略高于全片 p95 0.981，应与视觉检查一起理解。跨接缝 SyncNet -40 ms、confidence 4.901。总耗时 486.39 秒（8.11 分钟），第一段 352.08 秒、第二段 134.26 秒；MLX 峰值 29,980,131,694 bytes。结果存于 `artifacts/h3-avatar-20261006/variants/avatar-lightx2v-8step-4bit/continuation9/`。

目前跨窗口通过项为 Turbo4、Turbo8、Ref2VA Q4/Q8；DMD8 正在运行，随后 FL2VA Q8、StageB50、FL2VA Q4。签名 Package 安装/恢复测试及公开发布均未完成。


### OpenVDN DMD8 两窗口实测（2026-10-06）

9 秒成片为 216 帧，视频/音轨均 9.0 秒，PTS 误差 0；接缝帧差 1.002（全片 p95 0.784），接缝前后没有明显位置、曝光或背景突变。5–9 秒 SyncNet -40 ms/confidence 3.860，低于本次 Turbo 样本，因此补查 0–4 秒：同样 -40 ms/confidence 6.041，未见偏移随分段累积。后段较低置信度与嘴部柔化如实保留，不将数值解释为所有变体感知质量相同。总耗时 530.07 秒（8.83 分钟），MLX 峰值 41,186,293,750 bytes。结果存于 `artifacts/h3-avatar-20261006/variants/avatar-openvdn-dmd8-4bit/continuation9/`。

跨窗口已完成五种，余下 FL2VA Q8、StageB50、FL2VA Q4；当前正在运行 FL2VA Q8。恢复验收脚本改以 Worker running 且未 cancel_requested 判定新请求进入执行，避免短暂 progress phase 或旧请求取消清理造成误判；该脚本仍待在签名安装后执行。


### FL2VA Q8 两窗口实测与源码一致性（2026-10-06）

FL2VA Q8 9 秒两窗口输出 216 帧、音视频均 9 秒、PTS 误差 0。接缝帧差 1.191（全片 p95 1.174），抽样及接缝 185–189 帧检查连续；跨接缝 SyncNet -40 ms/confidence 4.602。总耗时 2799.43 秒（46.66 分钟），MLX 峰值 35,764,636,316 bytes。归档路径：`artifacts/h3-avatar-20261006/variants/avatar-base-8bit/continuation9/`。

源码核对记录 `artifacts/h3-avatar-20261006/variants/source-audit.json` 已核验此前完成的 8 次短片和 4 次两窗口运行，其模型配置/输入/所有 Python 源文件与当次 job digest 一致；本次 FL2VA Q8 和后续结果将纳入最终核对。Host 与 Worker 封包代码 AST 除相同标准库 imports 排序外一致，原始 diff 也已检查，仅格式和导入排序变化。

当前六种变体完成跨窗口验收，StageB50 正在运行，之后为 FL2VA Q4；签名安装与恢复验收、正式发布尚未完成。

### Stage-B50 continuation acceptance (2026-10-06)

The real Worker adapter generated two windows totaling 9 seconds (216 frames) in 3297.23 seconds, with peak MLX memory 23,217,209,962 bytes. H.264/AAC durations are both 9.0 seconds and video timestamp error is zero. Boundary samples show no abrupt placement, exposure or background change; local mouth softening remains. SyncNet over seconds 5-9 reports -40 ms offset, confidence 4.983. Evidence: `artifacts/h3-avatar-20261006/variants/avatar-openvdn-stageb50-4bit/continuation9/acceptance.json`. Seven of eight variants now have cross-window evidence; FL2VA Q4 is running. These remain source/adapter tests, not installed signed Package or Host restart acceptance.

### All-variant continuation evidence complete (2026-10-06)

FL2VA Q4 completed two windows totaling 9 seconds / 216 frames in 2786.39 seconds, peak MLX memory 19,214,469,788 bytes. H.264/AAC durations are both 9.0 seconds; video timestamp error is zero. Boundary samples show no abrupt placement, exposure or background change, with local mouth softening still visible. SyncNet seconds 5-9: -40 ms, confidence 4.574. All eight variants now have real cross-window evidence. The source audit verifies 15 adapter runs (eight short and seven continuation runs) against current source and video hashes; Turbo4 continuation evidence is retained separately.

Remaining release gates: publish six signed refiner Distributions using an authorized session; declare/build/sign 0.11.0 through standard scripts; verify actual installation, persistent queue reconstruction, explicit cancellation/retry, and separately full Local restart; publish and verify Package plus update provisioning profiles. No installed-Package or full-process-restart acceptance is claimed by the adapter results.

### Published 0.11.0 acceptance (2026-10-06)

Package 0.11.0 is published at Snapshot 261. Six additional refiner Distributions are published and verified anonymously. Exact signed Package installation, queue reconstruction/cancel/retry, independent Local process restart (only segment 1 reinvoked), model catalog and stop/restart/uninstall passed. Public downloaded bytes match the installed candidate. Eight ACPF choices now require >=0.11.0. Details: `docs/ai2apps-h3-avatar-0.11.0-release.md`. Host feature delivery remains a Desktop release item, not a model Package payload.
