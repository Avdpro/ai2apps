# App / Mini-App 模型需求声明检查（2026-11-18）

## 范围与证据

本次静态检查了源码中的 14 个 Studio Mini-App、17 个 placement/export 绑定、10 个 typed Host SDK，包含显式暂停自动开发挂载的 Package 源码；同时核对普通朗读、基础转写、图像生成/编辑的本地 owner 入口和现有 ACPF profile。这个数量不是 Dev 已安装清单，也不代表逐一完成真实模型推理。

源码清单：`acceptance/model-requirements-source-audit-20261118.json`。
安装修复的实机证据：`acceptance/bot-form-only-install-review-20261118.json`。

## 已修正

| 项目 | 问题与修正 |
| --- | --- |
| 漫画翻译 | 已有图片、英文目标仍被显示成参数确认；实际缺本地 OXR。owner 补齐 OCR 缺项提示、真实翻译模型清单、model_id 映射与和执行一致的默认值。模型已就绪且必填参数齐全时不强制确认。没有可用模型与没有指定可选模型分开处理。 |
| Package Mini-App 的 select 字段 | 签名 schema 已声明 enum，而 fields 没重复 options 时，共享表单崩溃。Binder 从同一可信 schema 补齐选项；客户端独立兼容缺失/null options，后续字段及按钮仍能显示。 |
| 通用配置卡片 | configuration_required 明确显示“配置运行环境”，保留原参数和素材，提供原 ACPF 配置入口。Discover 安装 handoff 仍保持其正式审核标题与流程。Desktop 和 Mobile 使用同一表单组件；Mobile 保留其 Desktop 配置提示。 |

Dev 已通过刷新恢复当前待输入卡片：Language、format、direction、model 和操作按钮均出现，原 ACPF 显示 SoMark OXR、依赖与“下载并配置”。尚未替用户下载模型。经用户明确允许，仅结束这次未提交翻译的等待后，已在 Dev 空闲时通过标准 Helper 重载。再次原话验收明确显示 OXR 缺项、English 和默认 DeepSeek，见 `acceptance/comic-model-setup-card-20261118.json`。真实 OCR 下载与安装后自动续接未执行；自动续接仅有通用协议和状态守卫夹具验证。

## 现有支持较完整的入口

- 普通 Quick Read 和基础转写：按实际 ready 模型给出默认模型/模型字段与 operations 配置请求，已有参数可直接执行。
- 图像生成与编辑：由 Imagine owner 提供可用模型、兼容约束和选择要求；不在 General 增加模型或业务名规则。
- 音乐/音效/歌曲：声明实际生成能力、模型清单和 ACPF 入口；歌曲的模型许可确认应保留。
- Talking Portrait：有 model_id、模型相关 preset/resolution 和配置入口；肖像/声音使用权属于独立批准，不能用“免参数确认”取消。
- 详细转写：有 compact/quality 可用性检查和所属 host 配置入口。
- Article Cards / Fantasy Feed：当前 owner 主要接收已经写好的内容并调用确定性 renderer，不能仅因产品含“AI”就推断它们必须另装推理模型。

## 需要下一批完善的已确认缺口

| 优先级 | 所属入口 | 源码发现 | 建议 |
| --- | --- | --- | --- |
| P1 | 视频工坊 placement 的音轨分离/角色换声 | `studio/package_sdk.py:media_descriptor` 复用 Voice descriptor，install.appId 仍指向 Voice；但 Provider.configuration_app_id 是当前 placement host。`api/parameter_forms.py:setup` 正确校验归属时会拒绝不匹配的配置入口。replace_video 的配置 capability 也应与实际视频执行路径一致。 | 在 typed SDK owner 组合层使用当前已验证 placement host 和执行模式的真实配置 capability；保留通用归属守卫，增加双 host 回归。 |
| P1 | Frozen Time | `frozen_descriptor` 判断任意一种几何模型 ready 即可，但实际执行使用所选 depth，缺省 vggt。可能 DA ready / VGGT 缺失却报告无需配置；安装入口固定 vggt，也不能表达明确选 DA 的请求。 | 根据用户选择或 App 默认几何方案计算真实依赖和 ACPF capability，避免以“任一可用”代替当前选择可用。描述和 prepare 都需消费同一个选择。 |
| P1 | 字幕翻译 / 视频音轨翻译等复合能力 | owner 会检查标准任务模型，但当前 ACPF profile 主要安装转写/分离组件；Studio broker 的 llm.text readiness 直接为 true，不能证明任务模型路由已配置。 | 将“缺安装模型”和“已有模型但未设置默认路由”分开声明；为路由配置提供明确入口，不能靠反复安装语音模型恢复。具体方案仍由 owner 声明，不在 General 猜业务需求。 |
| P2（Voice-only 已修正，见下节） | 音频角色换声 analyze / replace | descriptor 的 configuration_required 主要按分析所需转写模型判断；实际 replace 还依赖分离与换声模型。视频原生 owner 已限制缺模型时只允许 analyze，Package 复用路径需统一。 | 按 action 分阶段描述需求，允许现有分析先完成，执行换声前只请求缺失组件；保留使用权确认。 |
| P2 | 多个依赖的静止时间、视频配音等 | 部分 descriptor 只有 configuration_required 布尔值，缺少具体是哪一项不可用；ACPF 可以显示计划，但 Agent 不能据此准确解释缺项。 | 增加有界、可信的缺项说明，复用现有 owner / ACPF 数据，不把全部模型目录塞进 Bot System Prompt。 |

这些是源码级发现，未在 Dev 逐一创建真实付费/媒体任务；本轮未把上表全部当作已修复。未修改 Package 签名产物、未重新发布 Package，也未取消模型许可、Access 或结果未知保护。

## Voice Studio 单 Studio 范围整改（2026-11-18）

按当前 placement 核对，本轮仅处理「录音角色换声」。音轨分离、详细转写、视频角色换声属于多 Studio Mini-App，不纳入本轮；字幕/配音翻译和 Frozen Time 也不属于本轮 Voice-only 范围。

录音角色换声复用当前 owner 的分阶段依赖检查：分析需要详细转写/说话人识别，替换阶段另检查对白/背景分离和声音转换。Voice-only descriptor 补充双语缺项说明，并在替换阶段将 conversion_profile 的选项、schema 和默认值统一限定为执行器实际可用的质量配置。分析阶段不校验尚未使用的质量偏好。保留真实分析记录、素材归属、参考音频和明确使用权确认，不改变通用 Agent 业务边界。

修改位于 Host typed SDK 的 owner 适配层；现有 Package 已声明全部质量枚举，Host 只收窄可用集合，不改变 Package 文件或签名声明，因此本项无需重发 Package，也未读取 Dev Cookie。需要更新 Local Python 才会在已运行实例生效。

验证为依赖就绪状态/推理夹具和真实 Binder、队列、输出路径回归，不代表真实模型推理或 Dev 实机安装验收。

最终验证：标准门禁入口选取 `voice_processing_aaat or package_mini_app_exports or aaat_architecture or exact_parameter_contract`，74 项通过、1439 项未选（86.56 秒，退出码 0）；随后补充 Binder 用例并将分析阶段字段保持原样后，最终 Voice owner / Binder 34 项通过。未运行全量门禁；架构选集退出时的 headless Metal 清理提示未影响退出码。日志分别为 `/tmp/voice-aaat-audit-gate-20261118.log`、`/tmp/voice-aaat-audit-final-20261118.log`。

## 视频相关整改（2026-11-18）

本轮修正上述表格的视频 placement 配置归属、静止时间当前几何模型判断、字幕与视频配音的默认文本路由缺项，以及视频换声的分析/替换分阶段判断。Package typed SDK 使用已验证的 placement host 给出安装入口；静止时间按默认 VGGT 或明确选择的 DA 加 Meridian 检查，描述与提交前预检读取同一选择。分析阶段仅要求转写，替换阶段再要求对白/背景分离与换声模型，使用权和已观察说话人守卫保留。

字幕和配音将缺转写/分离模型与缺标准任务模型默认路由分开；只有缺语音组件才提供对应 ACPF 安装入口，单独缺路由时提示到模型默认使用页配置，避免重复下载安装语音模型。owner 通过有界 `constraints.missing_requirements` 向精确参数契约报告缺项，不把全量模型目录加入 Agent 上下文。

本轮只修改 Host owner、预检与测试，未改签名 Package 声明，无需发布新版 Package 或读取 Dev Cookie。定向 owner 回归 29 项通过；标准 AaAT 门禁入口选取架构、Package 绑定、精确参数契约、配置表单与相关 owner 共 128 项通过、1386 项未选（175.70 秒，退出码 0）。一次全量 1514 项运行到 21% 未发现失败后主动停止，不算全量通过。真实 Dev 模型安装与生成未执行。

## 整改后的独立复核（2026-11-18）

用户将视频和音频分别整改后，本轮按原清单复核当前源码，未继续修改执行代码。视频 placement 的可信配置宿主、Frozen Time 所选 depth 的后端预检、`llm.text` 默认路由就绪判断、音视频换声的阶段依赖和有界缺项列表均已有对应实现。现有相关回归重新运行 **66 项通过，46.39 秒，退出码 0**；但不能据此将整张清单关闭，补充探针发现以下遗漏。

| 优先级 | 仍需修正 | 复核证据与影响 |
| --- | --- | --- |
| P1 | 视频配音真实目录函数缺少 broker 初始化 | `studio/video_localization_aaat.py:catalog` 直接使用未定义的 `broker`；未替换 catalog 的 descriptor 调用立即抛出 `NameError`，无法描述或执行配音。现有 `test_video_localization_aaat.py:setup` 将整个 catalog 替换为夹具，因而现有绿测未覆盖此路径。应补真实 catalog 组合路径的回归，仅隔离外部模型/推理。 |
| P1 | 无安装计划的缺项卡片缺少恢复入口 | 字幕仅缺 `standard_task_model_route` 时，或配音仅缺 `ready_voice_character_or_clone` 时，owner 返回 `configuration_required=true, install=None`。共享表单将“重新检查”与 install 绑定，浏览器复现只有禁用的提交和取消。用户在模型默认使用页或 Voice Studio 配置完成后，原卡片没有直接重新检查/续接入口。应提供独立的重新检查；配置导航仍由可信 owner 提供，不制造无关安装计划。 |
| P2 | 普通选择字段变化没有刷新动态依赖 | `depth` / `action` 通过 `model_field` 驱动后端依赖，但表单仅在展示类型为 model 时重新加载；普通 select 只保存草稿和 required/missing/invalid。隔离浏览器中 VGGT 缺失切到已就绪 DA，仍只有一次读取，提交仍禁用，原配置目标未刷新；analyze/replace 使用同一变化路径。应按可信的依赖选择字段刷新当前契约、配置目标和就绪状态，不把业务字段名写进共享 UI。 |
| P2 | 分析阶段配置仍指向整套换声依赖 | Voice owner 在 action=analyze 时正确只报告缺 detailed_transcription，但 install capability 仍为 audio.speaker_voice_replacement；对应 ACPF 包含转写、Demucs、Seed-VC，最低设备门槛也高于独立转写。Video replacement 同样固定整套换声入口。需要按当前阶段选真实配置目标，避免只做分析也要求下载、验证未来换声组件。 |

复核证据：[独立复核记录](acceptance/model-requirements-independent-review-20261118.json)。浏览器为隔离的共享表单测试页面，不是 Dev 实机验收；无下载、无模型推理、无 Access/许可批准。两项整改记录均仍标记 Dev 激活/真实安装验收未完成，本轮未重载实例、未将定向通过描述为新的完整门禁通过。

### 独立复核遗漏的修正

- 视频配音 `catalog` 恢复真实 `StudioCapabilityBroker` 初始化，并新增未替换 catalog 的目录组合回归；不再依赖整体替换该函数的旧夹具掩盖错误。
- 缺模型默认路由或可用音色、但没有 ACPF 安装计划的参数卡片，现在独立提供“重新检查”。用户在模型/Voice Studio 完成配置后，可保留原草稿刷新，不会被禁用提交和取消两个动作困住。
- 可信 owner 的 `model_field` 随当前参数合同送到共享表单；普通 select 选项变化也会先保存草稿，再重新读取动态依赖、配置目标和提交状态。未按 `depth`、`action` 等业务字段名在通用 UI 增加分支。
- analyze 阶段的配置目标改为 `audio.detailed_transcription`，replace 阶段仍为相应音频/视频完整换声能力；两个 placement 都维持原宿主归属校验。单纯分析不再要求安装 Demucs、Seed-VC。

以上为 Host 代码和表单修正，Package 签名声明未变，不需发布或读取 Dev Cookie。原独立复核记录保留为修复前证据。修复后定向 Python 28 项、共享表单 Node 23 项通过；隔离 Chrome 复测 route-only 卡片已有重新检查（GET 2 次），VGGT 切到已就绪 DA 后重读合同且提交恢复可用。标准 AaAT 门禁入口相关选集 130 项通过、1386 项未选（176.14 秒，退出码 0；退出时 headless Metal 清理提示不影响结果）。未做 Dev 实机模型安装或真实媒体推理。

## Voice Studio 复核补修（2026-11-18）

独立复核指出的遗漏成立。本轮补修 Voice-only 录音角色换声和它依赖的通用表单：

- Voice `replace_audio` 缺省/分析阶段的 ACPF capability 改为 `audio.detailed_transcription`；只有 replace 阶段才请求整套 `audio.speaker_voice_replacement`。保留当前可信 placement host，未改视频换声专属路径。
- Provider 表单桥接透传可信 `model_field`。共享 UI 按声明字段（而非业务字段名或仅 model 控件类型）保存草稿后重新读取契约，刷新缺项、配置入口与提交状态。此通用修复也适用于其它 owner 的普通 select 依赖字段。
- `configuration_required` 且无 install 的卡片增加独立“重新检查”，保留草稿并重新读取契约，不伪造安装计划、不自动提交，也不绕过明确权利确认。

独立浏览器测试 3 项通过，包含 Desktop/Mobile 的依赖切换、无安装计划恢复、草稿保留和零自动提交；跨任意 Provider 字段名的桥接回归 2 项通过。没有使用 Dev Cookie、下载模型或重启实例。本轮不处理视频配音 catalog 的独立错误，也不宣称视频分析阶段安装入口已修正。Package 声明没有变化，无需重发；Host Python 需重载，前端需刷新。

补修门禁结果：标准入口的架构/精确参数契约/Package Binder/Voice owner/共享表单选集 **86 项通过，1428 项未选，148.24 秒，退出码 0**；收集后新增的任意依赖字段桥接 2 项另行通过。浏览器最终复跑 3 项通过（含旧配置入口移除）。未运行全量；退出时 headless Metal 清理提示未影响通过结果。日志 `/tmp/voice-review-followup-gate.log`。

### 第二次独立复核：原四项在源码与定向回归层关闭（2026-11-18）

再次按上一轮四项核查，均已有对应修正，本轮未发现需要继续修改的同范围阻断问题：真实配音 catalog 初始化 broker，测试不再整体替换该目录函数；无 install 的缺项卡片独立提供重新检查；普通 select 根据可信 model_field 保存后刷新契约、配置目标和提交状态；音频/视频原生入口及 Package placement 的分析配置只请求详细转写，替换阶段保留完整换声配置。

独立重跑 owner/Binder Python **68 项通过（47.31 秒）**、任意依赖字段桥接 **2 项通过**、标准门禁架构选集 **28 项通过（1488 项未选，5.37 秒）**、共享表单 Node **23 项通过**、隔离 Desktop/Mobile 浏览器 **3 项通过**，退出码均为 0。架构选集退出后的 headless Metal 清理提示未影响结果。浏览器验证草稿保留、旧配置入口移除、重新检查后恢复提交及零自动提交。详见[第二次独立复核证据](acceptance/model-requirements-independent-rereview-20261118.json)。

本结论仅关闭上述四项代码/定向回归问题，不代表新增完整门禁或 Dev 实机验收已完成。本轮未重载 Dev、未核验运行实例加载这些新改动、未安装模型或执行真实媒体推理；部署生效和真实配置后续接仍是独立待验项。
