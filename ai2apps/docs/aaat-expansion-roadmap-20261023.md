# AaAT 接入顺序与进度

沿用本对话确定的顺序，不按底层模型或参数拆分大量工具。业务声明、输入和结果解释由所属 App 提供，共享 AS 不添加业务分支。

| 批次 | 范围 | 当前状态 |
|---|---|---|
| 第一批 1 | 音频人声/背景分离、指定说话人换声 | 本轮接入 voice.separate、voice.replace_speaker（分析/换声阶段）；回归及 App-Dev 记录见下 |
| 第一批 2 | 视频字幕：转写、翻译、导出、烧录 | 已有 video.subtitles，沿用当前实现 |
| 第一批 3 | 视频基础处理：提取音频、截取、拼接、超分辨率 | 本轮接入 video.process（提取/截取/拼接）和 video.upscale；复用既有服务，不按模型拆工具 |
| 第二批 1 | 视频本地化：配音翻译、指定角色换声 | 已接入 video.dub、video.replace_speaker；单旁白/声音权利确认、实测见下 |
| 第二批 2 | 音乐、音效、带歌词歌曲 | 待接入；复用实际 Provider 参数与共享输出 |
| 第二批 3 | 素材库协作：归档集合、跨 App 素材交接 | 已有搜索/读取和 Session/Gallery 引用；集合写入、组合流程待补 |
| 第三批 | 视频项目与复杂创作 | 待设计项目编辑交接与真实结果返回 |
| 后续候选 | 视频生成、数字人、角色管理 | 逐项核验实际 Provider、模型和恢复条件，不把目录推荐视为可执行能力 |

## 本轮：Voice Studio 音频处理

- `voice.separate`：素材引用、实际可用的分离拓扑，复用既有已安装的 source-separation Mini-App、Studio Job 和 Demucs 等声明模型。
- `voice.replace_speaker`：一个用户目标入口，`analyze` 返回真实说话人 ID 和有界样例；`replace` 只能使用同 Session/actor/Installation、同素材及 stat 指纹的分析证据，选择已观察角色和参考音频，使用权确认默认 false。
- 分析不换声；替换保留原时间线、非目标人声和背景，复用原 broker。原始录音最多一小时，参考音频最多60秒，仍受实际模型约束。
- 所有输入通过 Session 附件、Session Artifact 或自有 Gallery ID 定位。源文件及参考音频只持有原路径和 stat 指纹；执行时按需解码，执行前后检查，变化/移动要求重新选择。不会在提交时复制或读入整个源文件。生成结果可由宿主正常归档。
- 参数表单提供中英文，中文界面用中文，其余回退英文。缺模型时保留参数和素材，经现有 Desktop ACPF 配置；Mobile 沿用去 Desktop 的配置提示。安装/许可不由工具自动批准。
- 既有 Studio Job 是唯一执行状态源；不依赖页面或 mount。显式取消请求取消原 job，不换 Provider 重放。业务输出仍在 Voice Studio 唯一 Preview & Output；Chat 返回同 Session 的实际结果文件。
- 分析 JSON 持久化和发布也复用原 Voice 共享输出；UI 原有交互式分析流程保持兼容。新增观察记录只是选择角色的证据，不是第二份媒体历史或可执行授权。

## 回归与真实验收

- 新增8项音频 owner/队列回归：当前素材归属、跨Session、使用权、实际角色、原路径引用、模型未就绪、幂等与参数变化、分析JSON/换声WAV/分离ZIP及共享输出。模型推理为 fixture，实际存储、任务、发布使用生产实现。
- 99项音频/视频 owner、字幕、后台语音/视频、Broker和超分辨率回归通过。旧视频测试中“删除输入后继续成功”的预期与已确定的原路径引用合同冲突：已改成关闭页面保持原文件，并新增删除原文件必须失败且无产物的检查。
- 9项语音输出/音频 bridge/跨 Mini-App 输出选择测试通过；25项表单单元/真实浏览器测试通过（包含任意两个Provider的小数/整数输入）；完整AaAT边界门禁284项通过。
- App-Dev 真正执行 Chat Agent → 素材查询 → 中文确认表单 → voice.separate → 已安装 MLX Demucs。Run run_09b1412ed9844aa59b56e844002668a8，Studio Job stjob_592ebef8995b4071b64157a33de58b75，Studio Run strun_cfc84344d32c4c288a0754f0ead602aa，均已完成。
- 输入是现有合成测试视频 gala_a4cc98742de74e35994c72f347fe1b13（2782字节）；不把请求中“约4秒英文”当成真实内容证据，也不宣称试听或音质合格。实际作业持有 source_reference，没有 staged source；结果ZIP363010字节，宿主发布 vocals / instrumental 两条 WAV，Chat 返回ZIP。未安装新模型。
- 说话人分析 App-Dev 真实完成：Job stjob_30aef73b904943a5a8228fd77bbe4533 / Run strun_49f2f36f520d4781932b0df3cf899864。原路径输入196474字节的本机合成WAV；真实模型返回 speaker_0 及与合成文案一致的样例文本，consent=false，未换声。分析证据在原Session持久化。换声的推理/混合发布链路使用fixture回归，未宣称真实换声质量验收。


## 本轮：视频基础处理与结果引用

- 一个 `video.process` 用户目标入口提供 extract_audio / trim / join。输入仅限当前Session或自有Gallery视频；提取/截取一份，拼接2–10份，按数组顺序允许同一片段重复出现。时间范围仅适用于截取，不能静默忽略其他操作的非零时间参数。
- 复用已有 Composer source store、render_composition、音频提取器和持久 Studio Job。截取/拼接输出沿用首个视频画布、30fps、原音轨，最长10分钟；画布64–3840×64–2160，提交前检查源时长与时间范围。无生成模型依赖。
- `video.upscale` 使用明确选择的已安装模型和原 UpscalingJobs；原视频最大1GiB，2×放大、分段/帧数/时长/自定义提示词支持完全服从实际模型声明，不从模型名字推断。新AaAT输入以stat引用登记，不复制原视频；原字节上传兼容入口保留。
- 同一Invocation绑定源指纹、参数和原持久job，重读不创建第二个任务。现有共享Output发布结果，Chat持有同Session Artifact，可继续传入兼容App；没有新增Mini-App历史或播放/下载实现。
- 新增4项视频owner回归，实际PyAV截取15帧、拼接60帧并校验顺序；覆盖重复调用同job、跨Session/无音轨/无效时间/无意义参数拒绝。超分使用fixture推理，实际队列和输出发布。
- App-Dev Run run_f927af946b7b4293abd460bcc1e4c1dc 真实完成三步，并逐步在Chat确认：
  - 提取音频 Job stjob_d08dd4557e5e4bf69a0c15f22ea9f89b，WAV196652字节、1.024秒。
  - 截取原视频0–0.5秒 Job stjob_3efb248320d04a5ea9739e424caa9ed9，MP43180字节、15帧、0.5秒，保留音轨。
  - 将上一步实际Session Artifact引用两次拼接 Job stjob_497a8b6609824d71b1d9b1620188fa41，MP44220字节、30帧、1秒，保留音轨。
- 三步结果以实际媒体解码核验；作业payload全部是source reference。没有安装模型、字幕翻译或生成性视频处理。超分真实模型推理未执行，不将fixture测试计为真实超分验收。

## 通用缺口与边界评审

实际0.5秒截取表单暴露HTML number默认step=1，会拦住合法JSON Schema number。
共享表单现在只依赖Schema类型：integer保留step=1，number使用step=any；服务端JSON
Schema及确认守卫不变。任意arbitrary.alpha/package.beta两组真实浏览器测试验证小数
提交、刷新恢复以及整数拒绝1.5。没有视频字段名、App ID或业务路由判断。

最终App-Dev端口52352；固定App/Helper的DevelopmentSourceRoot均为
/Users/avdpropang/sdk/omlx-moe-cache。真实Local日志确认voice_aaat.py、video_aaat.py及
builtin_apps.py从本checkout导入；native标题为AI2Apps-App-Dev: App-Dev 127.0.0.1:52352。
最终提供的agent_parameter_forms.js与checkout逐字节相同。Python经空闲标准Helper重启，
JS仅刷新Shell；不需要重建或发布Desktop。分析结果在Local重启后仍可见，0.5秒草稿在
Shell刷新后保留并成功提交。

## 第二批 1：视频配音翻译和指定角色换声

- `video.dub` 单旁白翻译配音，目标语言沿用UI的中/英/日/韩。声音来源为自有且就绪的语音角色，或显式选择声明模型临时克隆原声；不创建新的语音角色，不假装支持多角色配音。单旁白/使用权均在参数表单确认。默认开启原有ASR回听核验，复用原翻译、时长适配、TTS、背景分离及混音服务。
- `video.replace_speaker` 包含analyze/replace阶段，不拆成多个Tool。分析返回真实JSON（修复原video-package错误标为MP4）；观察说话人编号和样例绑定Session与原视频指纹，增加视频工作流标记，音频分析不能冒用。换声需明确目标编号、参考音频及consent=true，保留其他声音与原时间线。
- 两个入口均使用已安装Mini-App的实际声明、原Studio后台队列、Invocation幂等键与共享Video Output。仅提交源/参考的stat引用，无输入拷贝；视频混音器直接打开Path，必要解码和生成产物不受“原文件不复制”限制。大视频解码/混音在线程执行，避免阻塞Local事件循环。发布前再次验证引用；模型缺失保留参数并交Desktop ACPF。
- AS无业务改动；新增Owner适配器及组合注册。待发布登记 NXR-VIDEO-LOCALIZATION-AAAT-20261023。

### App-Dev 真实验收（本批）

- 合成输入：本机生成65帧/6.5秒视频，含约6.144秒机器合成英文旁白，134108字节；通过Desktop统一附件按钮登记原文件引用 attc_b93f07a6ca3f45c4bdace225a4aaa2ba。
- 真实分析 Job `stjob_bbed27bd975047e7831f20201df1f8c9` / Run `strun_88ce365c059f40d4a47b32296e61b32e` 成功，正确返回speaker_0和合成文案；JSON1155字节，已进入唯一共享Video Output及当前Chat Session。
- 配音翻译 Job `stjob_23a03a703c994be38510d681a910c492` / Run `strun_f5e93350039c4c36a0aad0fd05316b1a` 真实成功。表单确认en→zh、单旁白与合成声音使用权，显式选择临时原声克隆及已安装声明模型 `ai2apps.model.voxcpm2/8bit`，开启ASR回听核验。输出MP4为135852字节，65帧与原视频逐帧相同，含288个可解码音频帧且非静音。未评价主观听感或翻译质量。
- 配音期间刷新Shell，原后台Job继续执行，返回后Chat看到完成结果。输入payload持有source_reference，无staged source；未安装模型。
- 指定角色换声以相同视频分析凭据、speaker_0及另一段本机合成AIFF参考音频实际走到确认。App-Dev没有就绪的voice-conversion模型，提交前被拒绝，无新Job/产物。真实换声推理不能算通过；推理部分以fixture覆盖真实队列及发布。
- 据此完善Owner描述：缺分离/换声前置模型时仍允许analyze，但表单Schema在prepare阶段拒绝replace，显示配置所需能力入口和保留草稿提示，避免先进入execute再产生不确定结果。安装后重新检查恢复可用阶段；不会自动安装或改用其他工具。新增回归明确核验错误phase=prepare和零任务。

最终验证：293项AaAT强制边界/行为回归通过；92项定向Owner/Broker/媒体处理回归、
新增缺模型prepare阶段断言单测及9项共享Output/音频bridge测试通过。换声真实模型
缺失的预检由fixture验证，未标为真实换声推理验收。App-Dev最终端口57770，固定
App与Helper源根均为当前Git checkout；真实Local日志确认本批模块从该checkout
导入，served表单JS逐字节一致，native标题为
AI2Apps-App-Dev: App-Dev 127.0.0.1:57770。标准Helper空闲重启后分析/配音结果仍在，
无活动Run或Studio Job。未重建App、未发布Desktop或Package。

### 后续补齐：真实指定角色换声与保留性验收

此前缺模型限制已解除：App-Dev通过原ACPF配置Seed-VC v2。真实多说话人样例暴露
旧媒体入口mono解码的问题，已在公共codec与Studio媒体层修复；并把整段峰值归一化
改为只限制新换声轨，保留其他角色和背景的原音量。AS未增加业务特例。

Job stjob_a8c824fc57504055bbe20c895c8ef0d3已完成并进入视频共享Output，243帧及时间戳
与原视频完全一致。非目标B相关性0.998768、音量差−0.057dB；片头/片尾背景相关性
0.999866/0.999997，立体声背景未坍缩。后续转写三段台词全文一致。音轨经过分离、
重采样和AAC重编码，保留内容不等于逐样本无损，也不是主观音色相似度评测。

103项定向回归、297项强制AaAT门禁、9项共享输出测试通过；最终App-Dev端口60157。
完整证据和复现实测脚本见[指定角色换声验收](video-speaker-preservation-20261023.md)。
