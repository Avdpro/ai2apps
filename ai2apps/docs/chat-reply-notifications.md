# Chat 回复完成通知

2026-10-23。复用通知合同 1.3 的 `app.custom`、现有 Device-auth producer/outbox 和 iOS 点击确认机制，不新增 Cloud 接口，不修改预览或静音偏好。

## 后端完成与恢复

Chat owner 注册一个受信任的通知 source，现有 producer 循环在能力协商后运行它。只处理当前 Installation Owner 的 Chat collection 中，已完成的根 Run、实际已保存的 assistant message 和非空最终结果；普通 Chat 与 General Agent 最终回答均适用。不通知中间输出、子 Run、内部不可发现执行器、失败或取消的回合。

`chat.reply:<run_id>` 是稳定幂等键。outbox 与 `chat.reply.notification_queued` 决策事件在同一数据库事务中提交。进程在回复完成后、通知入队前退出，下次 source 会补偿；通知失败不回滚回复、不重新调用模型。首次启用以持久事件记录时间边界，不补发启用前已完成的历史记录；只补偿最近 24 小时的完成结果。Cloud 未协商 App route 能力时等待，不伪造其它 Task 跳转。

正文仅为通用“Chat 回复已完成 / 对话有一条新回复”，不包含问题、回答、思考、会话标题或附件。Owner-only Device 通知不能代替成员推送：成员的私有会话不发送给 Owner。继续使用现有 outbox 的身份 epoch、重试、过期和 Cloud 通知授权规则。

## 手机点击

目标是 `{type: app_route, app_id: ai2apps.general-chat, route: conversation, id: <session_id>}`。iOS 重新读取 Cloud detail，验证来源 Desktop，调用当前手机身份的 Local resolve-target，再导航；不把推送参数当授权。

Owner Mobile 使用现有 Owner 会话。签名 Agent / unified Owner-Agent 入口通过同一 `signedFetch` 的精确 `/v1/mobile/chat/notification-target` 操作，在原有签名/lease 校验后解析目标；此操作仅接受 Chat 目标，不增加任意 HTTP 代理。iOS 需采用本次 WebSession 改动以支持独立签名 Agent 会话；Owner-only 入口沿用既有原生合同。

Chat route 使用原始 `ChatRepository(principal=当前身份)` 校验 actor、client_scope、会话状态。Desktop、owner-home 和 mobile-agent 列表仍隔离；不合并会话，不改写来源，不放宽 scope。来源是当前手机身份的 Chat 时，页面直接加载原 Session，不依赖最近选中项或列表分页；成功展示后才确认 opened/read。删除、归档、无权限、切换来源 Desktop或身份不匹配时明确失败，不回退到其它对话。Desktop-origin 通知在无法访问其原会话的手机入口上不会冒充可打开。

Mobile iframe 保留原有 mount token / notification ID / active frame 校验；inline Chat 在本页确认。Owner/Agent 重连和入口重定向均保留通知参数。普通刷新与无通知入口的默认选择行为不变。

手机端其它身份/会话集合并未同步：同一账户并不意味着可以跨 `client_scope` 打开任意会话。本次只对当前手机入口确实有权访问的原会话提供直达；未来跨端共享对话需要另行设计，不借通知接口绕过。

## AaAT 等待用户输入与确认（2026-10-23）

Chat collection 内的 AaAT `agent_interactions`（包括 delegated child）是待处理操作的唯一状态源。Owner adapter 扫描最近24小时内仍为 pending、deadline 未到且所属 Run 为 waiting_input/waiting_capability 的记录，按 `chat.interaction:<interaction_id>` 入队；同一表单保存草稿或重复恢复不会产生新通知，下一次新的 Interaction 则有独立通知。当前仍有效的近期等待在升级后可以补偿通知；已提交的历史交互不补发。不把普通网络/模型等待或 task_progress.waiting 当成人工输入。

固定通知只区分“Chat 需要你填写信息”和“Chat 需要你确认”，不包含 prompt、参数草稿、工具名、业务标题、权限范围或思考内容。pending 检查同时核对会话归属、App 状态、Run 取消/期限及祖先委托未结束。outbox 与通知决策在同一事务中写入；新增通用的 trusted delivery guard 在发送和重试之前重查所属业务状态，已处理/取消/过期则把未发出项标记 cancelled；守卫暂不可用时延后重试，不能带病发送。已经被 Cloud 接受的推送无法由本地撤回，因此点击仍需再次核验。

`interaction` App route 以 opaque interaction ID 定位，后端从持久关系解析原 Session/Run，继续使用当前 actor/client_scope，不能由 URL 指定另一个任务。手机精确读取原 Run、恢复已保存草稿并滚动聚焦对应表单/确认卡；参数描述加载失败、步骤已处理或过期不确认 opened/read，不回退到别的表单。点击通知不提交参数、不批准权限、不切换 Provider、不发起新的业务执行。App 专属 handoff 保持原来的“在目标 App/桌面完成”提示，不伪造可在手机完成的能力。

这次接入是 Chat 所属 AaAT 会话；其它 App 独立持有的 Session/任务须由其 owner 注册真实通知目标，不能借本接口跨会话归属。原生客户端复用前一版自定义 App route，无新增 iOS Native 代码。

验收：71项后端、253项AaAT门禁与23项不重复Node/Chrome测试通过。真实App-Dev Run `run_d49ebe4c9f964aca8b116a1c427518f9` 进入参数表单等待，原生界面可见预填标题及待补字段，没有执行 `todo.create`；Interaction `int_57af0ea9f29242fe9ea75c57c0608291` 的唯一通知 `dc9ef02e-f23a-47e3-9d6d-4215855ece82` 已被Cloud接受（attempts=1）。验收后明确取消该Run，未提交表单。App-Dev Local PID52645/port52930、源码导入路径及三份服务JS已核对；Dev活动任务未重启。Cloud接受不等于手机锁屏送达或点击验收。

## 验证边界

真实 SQLite/Run scheduler 测试覆盖普通与 Agent 完成、Owner/scope 隔离、能力等待、历史排除、事务回滚和幂等恢复。Chrome 390px 测试覆盖 iframe/inline 原会话展示、不可访问时失败且不误开其它会话；保留断线恢复与 mount 绑定回归。iOS Simulator 编译通过不等于锁屏推送 received/opened/read 真机验收；本次未发布 Cloud、Desktop 或 Runtime Package，也不自动修改通知授权或安装手机 App。

实际 App-Dev 已通过自身 Helper 空闲重启，Local PID50478/端口51391；App/Helper source root、运行时 notification bridge 导入路径与三份 Mobile JS 服务字节均已核对。真实普通 Chat Run `run_370b8411160840ff97bca1288b4d0594` 保存“通知验收完成”，其唯一通知 `21560b99-7f25-409c-9ff7-0d3304b41df7` 已获 Cloud 接受（submitted，attempts=1，error_code=null），不是手机已收到/已打开的证明。77 项后端、253 项 AaAT 门禁和11项不重复 Node/Chrome 测试通过。通用 Dev 保留现有活动任务，未重启。
