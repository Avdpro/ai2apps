# Bot 实时对话 P0：输入准入切片

日期：2026-11-18。状态：内部实现，尚未开放语音模式；不是完整 P0 验收。

## 所有权与入口

`BotDialogue.realtime_inputs` 提供模型无关的显式输入组，实现在
`messager/realtime_inputs.py`。它只保存输入、冻结成员和复用原准入键，
不调用业务 Tool、不判断任务意图、不回答或批准 Interaction。
新任务/续接由原 `BotDialogue.submit` 的 owner 判断；Task-Session 与
job/Worker Run 的原映射保持不变。共享 General Agent 无新增业务分支。

内部调用顺序：

1. `create(principal, bot_id, sid, request_id, model=...)`：宿主显式创建组，
   冻结模型、语言、时区和可选 Task-Session。相同创建键改参拒绝。
2. `add(..., input_id, source=..., text=..., attachment_ids=...)`：只接受最终
   语音转写、文字和附件引用，服务端序号决定顺序。临时字幕不持久化；
   输入 ID 重放去重、改参拒绝。组最多 16 个输入、16000 字符、8 个附件。
3. `close(..., expected_revision)`：复核组版本，冻结成员、合并正文和
   附件内容指纹。关闭不自动派发；解析完成也不自动关闭组。
4. `dispatch(...)`：所有依赖附件 ready 后，以稳定
   `realtime-group:<group_id>` 键经原 Bot 准入。返回 `dialogue_run_id`，
   不将该 ID 声称为逻辑任务 ID。重复调用返回原准入回执。

组绑定 actor、installation、client_scope 和已授权主 Bot Session。
每次操作重新校验原 App Chat 访问与 Bot 类型，附件必须属于该 Session。
本切片只支持 Agent Bot；Flash/ASC 不从这里改变各自入口。

## 持久化和故障窗口

`messager_realtime_groups` 保存配置、状态、冻结输入及准入回执，
`messager_realtime_inputs` 保存独立输入 ID 和服务端序号。
原始音频不进入这两张表。

关闭后的 pending 记录是准入待办。Bot 原准入持久去重与本模块写回回执
之间可能崩溃；恢复后仍提交同键同参，由接收端返回原 Run。接收端已有
回执时，不因附件后续被删除或解析状态变化而再次创建工作。尚未准入的
组遇到解析失败保持待处理，内容指纹变化直接拒绝。

这不承诺底层工具效果 exactly-once，也不自动重试未知工具效果。
本切片没有启动扫描器；pending 的调度/取消/保留策略须随会话生命周期补齐。

## 验证与剩余工作

`tests/test_bot_realtime_inputs.py` 使用真实 SQLite、原 Bot 准入和任务链路，
覆盖创建/输入重放冲突、组版本、冻结后拒绝追加、partial 拒绝、附件 ready/
失败/内容变化、跨会话和 principal 隔离、容量限制及准入后回执前崩溃。
异步链路使用确定性模型夹具，验证相同 Task-Session 的两个不同 Worker Run。
没有调用付费模型或实际外部效果。

新增测试已纳入 `tests/run_aaat_boundaries.py`。最终命令及结果记录在根目录
`docs/ai2apps-desktop-next-release.md` 的 NXR-BOT-REALTIME-P0-20261118。

后续 P0 还需：VoiceSession/controller lease 与 epoch fencing、受保护 API、
待办组生命周期/保留与恢复调度、播放确认、原任务状态/结果事件投影、
游标过期快照恢复及模拟实时适配器。完成租约与宿主边界前，不应把本内部
接口直接挂到媒体或浏览器请求。P1 才接入语音 UI 与实际模型。

本轮未重启/激活 Dev 或 App-Dev；运行实例没有因此获得语音功能。
