# Bot 文本咨询 C1 实施说明

2026-11-03。总体设计见 [Bot 通信与任务协作](bot-communication-and-collaboration-v1.md)。本阶段交付同一 Local、同一用户的文本咨询；带工具的立即单层任务委派已由 [C2](bot-delegation-c2-implementation.md) 接入，长期联系授权和多层协作仍属于后续阶段。

## 用户路径

用户可以在 Bot 对话中要求“请某个 Bot 帮我评价这个方案”。发起 Bot 通过 `messager.bot.directory` 发现当前可用的自有 Bot，再通过 `messager.bot.consult` 准备咨询。名字只是展示；请求保存稳定 Bot 身份。

准备咨询只保存待审阅请求，不发送问题、不运行接收模型。发起 Bot 对话的信息流展示接收 Bot、确切问题、回复模型和授权范围。用户选择“允许本次咨询”后，宿主创建唯一的无工具咨询 Run；“不发送”不创建执行。用户可继续聊天，也可取消尚未完成的咨询。回复带接收 Bot 名称写回原发起会话，不在其他 Bot 的主对话重复发布。

每次确认只允许发送已展示文字，并使用所示模型回答一次，可能产生模型用量。不会自动共享用户历史、长期记忆、照片、文件或 App 权限。接收方缺少事实时只在回复中指出所缺内容，不能调用工具、发起新的咨询或申请执行权限；需要这些能力时使用 C2 委派，不扩大文本咨询本身的权限。

## 宿主与运行边界

实现位于 `messager/communication.py`，由 Messager owner 注册两项可信 AaAT 与专用的无工具执行器。共享 General、Tool 路由器和模型循环没有 Bot 身份特判。目录与提案只接受当前前台 Bot Run 的可信调用上下文；Hook、后台计划、终态 Run 和伪造发送者均不能发起咨询。

原工作为 Bot 的前台独立任务时，宿主通过原任务绑定找到发起 Bot 主对话，而不是把授权卡放在内部执行 Session。提案持久保存原会话、发起 Run、接收方身份、源授权快照、接收方权限版本、确切文字、模型与审阅摘要。批准时复核这些范围；接收方改名/职责变更、权限变化、原会话归档和过期请求不能按旧卡发送。不会转向其他 Bot 或换模型重试。

接收方使用专用执行器，只向模型提供冻结的接收方身份职责与已审阅问题，不加载其他会话、记忆或 Tool。最多一次模型回合，拒绝模型返回的 Tool 调用；失败和取消有终态回执，不自动重新发起咨询。单次限制为 120 秒和 1000 输出 token；每个发起 Bot 最多 10 个待处理请求，每用户每天最多 20 个请求。此阶段不存在递归委派入口。

## 持久化与恢复

`messager_bot_consultations` 保存请求身份、审阅、原始范围与唯一 Run 绑定。原 Tool invocation 是幂等键；同键改参拒绝。批准在平台事务内创建/复用同一 Run 并保存绑定；重复批准不创建第二次模型执行。审阅有效期为一小时。

系统 Task observer 只观察原 Run 并写回原会话，不负责执行模型。它具有稳定去重键，支持恢复；Bot/Todo 恢复时补齐批准事务与 observer 创建之间的故障窗口。即使没有打开 Messager，结果仍由后台 observer 持久投影。信息流读取可补齐终态回执，但不创建或重试模型工作。

Bot 清理/撤权复用原权限版本变化，并停止涉及该 Bot 的待发送/活动咨询；清理审阅包含这些请求和运行。观察器也重新检查身份/权限，旧模型结果不越过撤权变成新的成功反馈。终态消息按请求身份幂等写入。产物/图片 UI 实现保持原样。

## Local 接口

| 接口 | 用途 |
| --- | --- |
| `GET /messager/bots/{bot_id}/communication/targets` | 获取有归属校验的咨询目录 |
| `GET /messager/bots/{bot_id}/work` 的 `communications` | 原 Bot 对话读取待审阅和进行中请求 |
| `POST /messager/bots/{bot_id}/communication/{ref}/decisions/approve` | 同源 Local desktop 按原 review_hash 确认一次咨询 |
| 同路径的 `reject` | 拒绝发送，不运行接收模型 |
| `POST /messager/bots/{bot_id}/communication/{ref}/cancel` | 停止原咨询，不创建替代请求 |

所有接口继续使用现有 principal、App 能力和资源归属检查；改变状态的入口还要求 Local desktop 同源宿主。模型不能直接调用批准入口。通用 App 访问 许可不能替代咨询卡确认。

## 验证与后续

自动化验收使用真实 SQLite、API、Agent Runtime 与可控模型，覆盖：发现与待审阅提案、同源批准、唯一 Run、原对话回复、拒绝、取消、过期、跨用户和其他 Bot 请求隔离、接收者设置变化、撤权、无工具/无私有记忆、后台 observer、恢复去重及前端显式按钮。确定性模型验收不等同于真实付费模型效果验收。

2026-11-04 的 [C2 实施说明](bot-delegation-c2-implementation.md) 记录实际接收 Bot 的 Todo/Task-Session、权限交集与审批、逻辑等待、父回合恢复及两处对话的同一原始交互。C1 咨询与 C2 执行入口仍分开，咨询答案不冒充 Task 交付物。

验收记录：[C1 收据](acceptance/bot-communication-c1-20261103/README.md)。完整 AaAT 门禁 1044 项通过（588.99 秒，退出 0），相关 Bot 前端 75 项通过。固定 App-Dev 已按标准 Helper 空闲检查重载，并验证实际导入路径、接口、存储表及服务资源；真实付费模型咨询尚未作为本次验收执行。
