# VoxCPM2 与 IndexTTS 2.5：AI2Apps 模型实现需求

日期：2026-09-22  
接收方：模型实现 / oMLX Runtime / Model Worker / 模型 Package 团队  
需求方：Voice Studio  
状态：待实现与实测；本文不表示已完成适配或批准生产发布。

## 1. 目标与优先级

支持在 Apple Silicon Mac 本地使用 VoxCPM2 2B、IndexTTS 2.5，服务于 Characters 的参考克隆、角色试听和 Audiobook 的逐句配音。核心目标是在使用固定角色参考音频的同时，调整每句台词的情绪和语速。

- P0：VoxCPM2 可控参考克隆、中文/英文/混合文本、表达指令、现有统一接口、完整离线运行。
- P0：IndexTTS 2.5 单参考克隆、情绪数值控制、语速控制、中文与英文。
- P1：VoxCPM2 无参考声音设计、音频加文本续写克隆；IndexTTS 情绪描述转向量。
- P2：独立情绪参考音频、高级情绪向量 UI、流式输出和其他语言扩展。先公布真实支持情况，不阻塞 P0。

优先交付 VoxCPM2，IndexTTS 2.5 单独交付。后者若暂无可用 Metal/MLX 路径，应先报告适配成本、阻塞点及替代方案，不能用 CPU-only 或远程调用冒充本地 GPU 支持。

## 2. 已核实的上游能力与边界

| 项目 | VoxCPM2 2B | IndexTTS 2.5 |
| --- | --- | --- |
| 音色克隆 | 单段短参考音频，可控克隆模式无需转写 | 单段参考音频，基础克隆无需转写 |
| 克隆时情绪控制 | 自然语言风格指令 | 情绪向量、情绪文本或独立情绪参考音频 |
| 克隆时语速控制 | 自然语言指令，不能承诺精确倍速 | `duration_factor`，上游范围 0.5–2.0，大于 1 更慢 |
| 另一种克隆方式 | 音频 + 精确转写的 continuation/Ultimate Cloning | 不应无依据宣称转写可提高效果 |
| 无参考声音设计 | 官方支持 | 本需求不声明支持 |
| 输出 | 官方声明原生 48kHz | 以选定 revision 的实际输出为准 |
| 本地适配 | MLX-Audio 支持列表已列出 VoxCPM2，仍须验证当前 Runtime | 本需求未确认 MLX 适配，须实现侧核实 |

“单段克隆”不是保证任意一个词或极短录音也有良好效果。实现侧必须给出验证后的建议时长和硬限制，不得猜测填入 3 秒、10 秒等门槛。模型规模、权重磁盘占用、运行峰值内存应分别报告；IndexTTS 官方仓库当前约 5.49GB，不等于完整依赖大小或运行内存。

## 3. 现有接入契约

沿用 `ai2apps-model-worker/v1`、`audio_speech` operation 和 `ai2apps.audio-capabilities/v1`，复用现有 Model Invocation Gateway、任务调度、权限上下文、错误响应及音频转换链路。不得为两个模型另建只供特定 UI 调用的私有 TTS API。

当前调用形式：

- 通用字段：`model`、`input`、`response_format`、`speed`、`instructions`。
- JSON 情绪：`style: {emotion: "happy"}`。
- multipart 情绪：标量 `emotion=happy`。
- multipart 参考音频：`reference_audio` 文件部分；可选 `ref_text`。
- 当前角色克隆请求会移除预设演员 `voice` 字段；不得要求用户额外选择预设演员。

兼容示例（说明 multipart 各部分，不是新增 JSON 文件传输协议）：

```text
operation: audio_speech
model: <模型侧注册的稳定 model id>
input: 今天是个好天气。Hello, it's nice to meet you.
speed: 1.25
emotion: happy
response_format: wav
reference_audio: <音频文件>
ref_text: <可选的参考音频转写，不是待合成文本>
```

正式包 ID、量化 variant ID、Runtime 最低版本由实现侧确定并在交付时给出，不能使用本文占位符。输入和控制字段必须独立；适配器内部构造上游提示，但输出不得读出“开心、稍快”等控制说明。

## 4. VoxCPM2 实现要求

### 4.1 可控参考克隆（P0 默认）

将 `reference_audio` 映射到上游 `reference_wav_path`。模型可在保持参考音色时使用表达指令控制情绪、快慢和风格。无 `ref_text` 必须能运行。

现有角色可能保存了 ASR 转写。仅仅提供 `ref_text`，不得自动切换到 continuation 模式，以免改变控制语义。默认可控克隆模式下，转写不作为必需条件，也不应谎报已用其提升相似度。

### 4.2 语速和情绪

- `speed=1.0` 不注入额外快慢指令。其他值映射为上游支持的风格描述；具体范围、档位、模板与语言经实测确定并记录。
- 必须标为指令式控制；不能把 `speed=1.5` 宣称为严格缩短至原时长的 2/3。
- 情绪枚举映射为风格描述，并与角色音色参考共同传入。只公布测试通过的枚举。
- 用户 `instructions` 与标准情绪/语速出现冲突时，标准字段优先；公布明确的组合规则，避免重复或相反指令。
- 不支持的值在推理前给出明确错误，不静默忽略。

### 4.3 其他模式（P1）

无参考的 Voice Design 应支持独立声音描述与试听文本。Ultimate/continuation 模式使用参考音频及精确转写，但应作为显式模式选择，单独验证情绪/语速可控性。若现有 schema 无法表达模式差异，提交兼容扩展方案或注册不同逻辑 variant；不得偷偷根据是否存在转写切换模式。

## 5. IndexTTS 2.5 实现要求

### 5.1 参考克隆

将 `reference_audio` 映射为 `spk_audio_prompt`。单段参考、无转写必须能够合成。若上游不使用 `ref_text`，兼容接受已保存角色的该字段，并在能力说明中明确其不参与基础克隆。

### 5.2 数值语速

统一 `speed` 表示说话速度倍率，大于 1 更快；上游 `duration_factor` 表示时长比例，方向相反。

```text
duration_factor = 1 / speed
speed 0.5  -> duration_factor 2.0
speed 1.0  -> duration_factor 1.0
speed 1.25 -> duration_factor 0.8
speed 2.0  -> duration_factor 0.5
```

上游目前公开范围对应统一接口的 0.5–2.0。边界、实际时长变化与声音质量必须实测。不允许在模型已调速后又做一次同倍率后处理。若控制实际由后处理完成，必须如实声明 fallback 及算法，不伪装原生控制。

### 5.3 情绪

P0 使用上游八维向量顺序：`happy, angry, sad, afraid, disgusted, melancholic, surprised, calm`。固定映射标准枚举与默认强度，公布映射和测试结果。`neutral` 应采用中性默认路径，不机械等同于 `calm`。当前 UI 的 `excited` 不在该向量枚举内，须验证映射并声明，或不公布支持。

P1 文本情绪描述需打包并就绪上游情绪分析依赖；官方要求开启 `use_qwen_emo=True`。该依赖缺失时，不能等到生成中才抛 RuntimeError。数值情绪路径是否能不加载该依赖，应验证并分别报告。

P2 独立 `emo_audio_prompt` 不得复用音色参考字段；需要单独的上传、权限和协议定义。明确其控制表达而非更换角色身份。上游默认关闭随机情绪采样，本需求优先保持音色稳定。

## 6. 能力声明与 Ready

参考现有模型包 `service.yaml`，按实际后端逐项声明：

- `tts.voice_profiles`：支持参考音频；可控克隆的转写非必需；单次输入一个合成参考。模型建议长度与硬限制分开说明。
- `tts.speed`：VoxCPM2 参照现有 `mode: fallback, control: instruction` 的语义；IndexTTS 依据实际实现标明原生时长控制或后处理。不得只凭上游支持就声明当前后端支持。
- `tts.emotion.values`：仅包含适配器可以处理且验证过的值。
- `tts.instructions`：仅当对应模式实际实现时开放。IndexTTS 情绪文本能力不等同于通用声音设计能力。
- `named_voices`、`multi_speaker`、`streaming`：没有实现就标 unsupported；应用逐句切换角色不等于单次模型多说话人生成。
- 格式与采样率：分别声明输入解码、原生输出、转码输出。复用 WAV/MP3 导出链路。

Ready 必须同时检查主权重、编码器、声码器、必要情绪模块、模型配置、后端和固定 revision。不得在点击生成后临时联网下载。可选能力未就绪时应只禁用对应能力，或者将其拆为独立逻辑 variant。

## 7. 素材与角色生命周期

角色参考素材由角色私有存储持有，模型侧只消费已授权请求中的音频，不能依赖 Gallery 路径，也不能自动把参考音频或生成结果写入 Gallery。

Voice Studio 当前会将多个选中片段按顺序规范化并合并为一个 16kHz、单声道 PCM WAV，转写按相同顺序连接。模型侧必须接受这种请求，并校验合并后时长；不得把“一个参考文件”误判为“只能选一个源片段”。如模型需要其他采样率，在适配器中转换并保证时长一致，不能简单修改 WAV 头。

角色保存稳定模型 ID、revision、参考内容标识及相关模式。参考克隆不修改模型权重，不应命名为训练。中间文件按请求隔离并在成功、失败、取消时清理。参考特征缓存应按 owner、模型 revision、音频内容和模式隔离，不能跨用户或角色误用。

## 8. 任务状态、错误与资源

- 接入现有任务状态，成功、失败、超时、取消都必须进入终态，不能让等待对话框永久转圈。
- 长任务支持现有取消机制；没有真实百分比时报告阶段，不伪造进度。
- 错误包含稳定错误码和可展示原因：无效参考、过长、参数不支持、依赖缺失、内存不足、超时等。不能只返回 HTTP 400。
- 错误或重试不得隐式改用其他角色、模型、随机声音或云服务。
- 报告冷启动、热启动、首次音频延迟（如支持）、完整生成耗时、RTF、峰值统一内存与磁盘占用。RTF 必须标明“生成耗时 / 音频时长”，小于 1 才快于实时。

## 9. 验收清单

提供可复现脚本、固定输入和生成音频，不以截图或上游宣传替代结果。

| 编号 | 验收场景 | 通过条件 |
| --- | --- | --- |
| A1 | 单段清晰中文录音，无转写 | 两模型均完成参考克隆；不触发训练或额外下载 |
| A2 | 英文参考与英文目标、中英混合目标、跨语言克隆 | 输出可理解、不读出控制词；记录错读、漏字、重复及音色表现 |
| A3 | 同参考同文本，中性/开心/悲伤/愤怒 | 情绪可感知，角色身份仍可辨；人工试听和原始音频留档 |
| A4 | speed 0.75/1/1.25/1.5 | IndexTTS 方向正确并报告实际比例；VoxCPM2 评估多次生成的快慢趋势，不按精确倍率验收 |
| A5 | 情绪与语速同时启用 | 不能互相覆盖、报不支持或出现双重变速 |
| A6 | 两个角色交替生成至少 20 句 | 不串音色、不串缓存；失败可定位到具体句子 |
| A7 | 多段材料合并、超长/损坏参考 | 合法合并可运行；非法输入推理前明确拒绝 |
| A8 | Characters 试听及 Audiobook 后台逐句调用 | 两条链路都通过，JSON/multipart 情绪语义一致 |
| A9 | 断网后冷启动、依赖缺失 | 完整安装可离线运行；缺依赖时准确显示未就绪 |
| A10 | 取消、超时、内存不足、重试 | 有终态、无悬挂等待、无临时文件无限增长 |
| A11 | WAV/MP3 导出、重启后角色复用 | 音频可播放，参考与模型绑定可恢复，不依赖 Gallery |
| A12 | 不同量化版本 | 分别报告音质和内存，不把全精度通过结果视为量化版通过 |

至少在一台明确型号/内存的 Apple Silicon Mac 上实测。报告 OS、Runtime/MLX 版本、模型 revision、量化精度、随机种子及控制参数。与现有 Qwen Base 或 CosyVoice3 使用相同输入对比，不直接引用 NVIDIA 测速作为 Mac 结果。

## 10. 许可和交付要求

VoxCPM2 官方代码与权重标为 Apache-2.0：分发保留许可证、版权、适用 NOTICE，并标记修改；辅助依赖仍需分别列出许可。

IndexTTS 2.5 官方代码/权重使用 Bilibili Model Use License Agreement，不能标成 Apache/MIT 或无条件自由商用。模型包需附所用 revision 的原始许可并落实分发条款，包括下游协议义务、量化/修改版本非背书声明，以及限制改进其他商业 AI 模型的条款。协议设有本人或关联方月活超过 1 亿、上年营收超过人民币 10 亿元需单独许可的门槛；还对输出/衍生物有较宽定义。生产分发前需完成对应条款审查，不能只展示“可商用”标签。

交付物：

1. 每个模型的 Worker 适配、Runtime 依赖、Package manifest、权重固定 revision 和完整辅助模型清单。
2. 最终能力表、字段映射、模式差异、错误码和限制说明。
3. Mac 实测报告、复现脚本、试听样例和验收结果；未完成项明确标识。
4. UI/统一协议需扩展的字段另列清单，区分已支持与拟议字段；与 Voice Studio 侧协同，不能自行改变现有语义。
5. 可供开发环境验证的包及升级/回退方式。本文只要求支持与交付，不授权发布生产包或修改 Cloud；如需 Cloud 配合，另交需求文档。

## 11. 官方依据与当前代码参考

上游资料核对日期：2026-09-22。实现应固定 revision；若内容变化，交付报告需注明差异。

- VoxCPM2：https://github.com/OpenBMB/VoxCPM
- VoxCPM2 权重与许可：https://huggingface.co/openbmb/VoxCPM2
- VoxCPM 代码许可：https://github.com/OpenBMB/VoxCPM/blob/main/LICENSE
- IndexTTS 2.5 API、情绪及 duration_factor：https://github.com/index-tts/index-tts
- IndexTTS 2.5 权重：https://huggingface.co/IndexTeam/IndexTTS-2.5
- IndexTTS 模型许可：https://huggingface.co/IndexTeam/IndexTTS-2.5/blob/main/LICENSE
- MLX-Audio 支持列表：https://github.com/Blaizzy/mlx-audio#supported-models

本地仓库参考（相对仓库根目录 `omlx-moe-cache/`）：

- `packages/omlx-model-cosyvoice3-0.5b/service.yaml`：现有能力和 Runtime 声明。
- `packages/omlx-model-qwen3-tts-1.7b/service.yaml`：Design、克隆、预设音色的区别。
- `ai2apps/readaloud/training.py`：参考要求、校验、合并。
- `ai2apps/readaloud/tasks.py`：角色绑定、后台 multipart 调用、情绪/语速传输。
- `ai2apps/readaloud/materials.py`：角色私有参考素材存储。
