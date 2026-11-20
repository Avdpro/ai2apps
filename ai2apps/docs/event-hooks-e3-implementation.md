# Event Hook E3：消费执行与后台委托

2026-11-02。建立在 [E2](event-hooks-e2-implementation.md) 的事实匹配之上；默认规则仍只观察，只有明确启用 background 的新委托才可执行。总设计见 [平台 Event/Hook](platform-events-and-bot-hooks-v1.md)。

## 执行入口

Schema 103 增加执行、Run 绑定、因果根占用、步骤结果、消费报告、收件确认及 System Task 持久受理凭据。扫描与执行分离；执行复用 SystemTaskService，不在页面或 SSE 中推进。受理凭据绑定 owner/App/请求内容，即使 Task 已完成也返回原任务；历史被清理后拒绝自动重新提交。任务受理与 Hook 回写之间崩溃可对账恢复。

ConsumerType 只由宿主 Python 注册 validate/prepare/execute，可选 session。JSON/HTTP/事件不能注册回调、命令、代码或 URL。普通 App 可按自己的权限和服务登记处理器；目前具体 App 验证对象是 Messager。三种已接通的消费者为：

- `messager.bot.observe`：取得详情后，向该 Bot 原有的持久 App Chat 提交一个 `origin=hook` 的 Run。用户手动对话正在执行时排队；同 delivery 的 request_id 固定，重启复用原 Run。职责属于动态 owner context，稳定身份只有 bot_id；旧单一会话迁移保留历史。身份职责变化使旧后台计划失效。
- `messager.app.observe`：Messager 所有的固定事件收件箱处理器，通过 AaAT 读取并保存报告，任务及 `/hooks/{id}/deliveries` 可查。当前没有新增独立的 App 收件箱页面。
- `studio.mini-app.event-inbox`：Package 声明 `requirements.capabilities` 中的 `events.subscribe`；后台处理另需 `events.background`。绑定 studio、Mini-App、App 实例、Package digest；卸载、升级或资源撤权均拒绝旧委托。后台只执行宿主固定的 `event-inbox/v1` 处理器，页面不在时也能读取并保存报告。Package 自定义后台代码和任意 AaAT 工作流不在本阶段范围。

Mini-App 重挂载后，经过现有 mount/broker 和 MessageChannel 使用 `events.list`、`events.watch`、`events.ack` 取得并处理报告。每次读取重新核验 mount、签名声明与 digest。`web/static/js/mini_app_events.js` 的 `AI2AppsMiniAppEvents.watch(port,rpc,consume,{signal})` 调用 Mini-App 自己的消费函数；成功后确认，失败不确认，实例关闭取消监听。投递是至少一次，消费函数须按 delivery_id 幂等。消息由绑定的真实端口传递，不向 frame 暴露 Cookie、凭据或后台授权。

`events.subscribe` 向宿主申请预览，宿主在顶层展示事件类型、范围、筛选、模式和到期时间并获得用户确认，才调用标准保存接口。Package 不能自行上传执行入口。仅 observe_only 的 Mini-App 规则保存匹配记录；宿主后台详情报告需要明确的 background 委托。

## AaAT 详情

事件目录公开固定的 `(capability, provider_id, version)` 绑定。三个业务 owner 各自实现，复用业务读取权限；Hook 不解释业务字段：

| 类型 | AaAT | 返回范围 |
| --- | --- | --- |
| 频道更新结束 | `intelligence.event_details` | run.new_article_ids 对应的当前文章元信息与摘要；最多20条，标记 missing、total、truncated、current、非历史快照 |
| 视频产物生成 | `video.event_details` | 生成任务、模型、完成时间和稳定 artifact 引用；不含本地路径或下载凭据 |
| 声音角色创建 | `voice.event_details` | 当前声音角色名称、来源、状态、模型；不含参考音频、参考转写或私有缓存 |

每次实际读取校验事件属于 actor、subject 仍可访问、详情接口版本未变；第一次结果持久化作该 delivery 的有界证据。命中缓存也必须重新检查授权。模型阅读的是这些不可信业务资料，不能据此获得执行权限。

## 后台授权与循环防护

HTTP 预览后台计划要求桌面用户和 `app.coder.use`；执行前重新取得本机 actor 身份及权限。冻结安装 ID、事件/消费者版本、资源范围、owner 计划、详情接口和有效期，默认一天，最长七天。Bot 必须明确指定模型和指令，没有隐式选择其他模型或 Provider 的降级路径。

本阶段后台只可读取**该 delivery 的该 event_id 的固定详情接口**，以及在 Bot 对话中请求用户输入。不能刷新频道、生成素材、发好友消息、创建 Todo 或调用别的 App；这些效应需要后续独立的动作授权。Gateway 与直接 CapabilityRouter 都执行通用宿主 guard，不依赖业务名称；App Chat 的 owner 权限仍同时生效。详情读取、报告保存、每次 Tool 调用及 Bot 等待期间均检查暂停、编辑、撤权和到期。需要用户输入时任务为 partial/needs_user，保留原 Run，不静默重启另一轮执行。

宿主传播 `owner/root_id/depth/ancestry`；未知来源事件仅能观察。因果根与规则的唯一占用在数据库中提交，同一因果链每条规则只运行一次，限制深度8、总激活20。A→A 与 A→B→A 均被抑制；独立的下一次更新有新 root，可再次运行。详情调用传播因果上下文，Intelligence Outbox 在原库保存并在中继恢复来源；旧无来源 Outbox 标为 unknown。

每次执行最多900秒、12个 Tool invocation；Bot Run 进一步限定12步、600秒、24000模型 token。嵌套 Gateway/Router 使用同一 invocation 收据，不重复扣预算。暂停或撤权不会把执行转换成另一个 Tool 的自动重试。未知结果保留失败或用户处理状态。

## 验证与边界

使用真实 SQLite、Gateway、System Tasks、AgentRuntime、App Chat 和消息端口验证。模型输出、Package 签名目录及生成媒体为测试夹具；不代表真实付费模型调用、第三方 Package 全流程或微信发送验收。自动化不为现有用户创建任何规则。

专项回归和完整 AaAT 门禁、开发实例源根/导入/资源验证结果记录于本文件末尾。Local 关闭期间不执行；跨设备/Cloud 离线推送仍需单独设计。

后台计划通过现有预览/保存协议创建，例如 Bot 的 preview 在 E2 字段外增加：

```json
{"execution":{"settings":{"model":"已明确选择的模型 ID","prompt":"阅读新增内容，在本 Bot 会话给出摘要"},"expires_in":86400}}
```

启用沿用 preview_ref + request_id。预览含完整冻结计划；HTTP 只能选择已登记消费者。后台规则编辑会撤销旧版本待执行授权并跳过其未扫描区间，新版本从保存时刻开始；观察规则继续保留 E2 的版本筛选边界。移动端可暂停/删除，不能启用或恢复后台授权。


## 最终验收

- 完整 AaAT 门禁809项通过（342.26秒）；首轮缺失的详情表单中英文说明已补齐，未放宽架构分类或增加业务例外。
- 收尾后的执行/详情/订阅/Studio/Package Mini-App专项78项通过（64.97秒），含事件能力就绪检测、来源撤权后的不可用收件、Package digest隔离。真实 MessageChannel测试2项通过；前端语法与差异空白检查通过。
- 两个固定实例在空闲检查后通过标准 Helper重载。App/Helper源码根、运行导入的事件/执行/宿主/Broker模块、Schema103、三个详情Tool注册、两份前端资源字节与匿名管理401均核验。最终PID：app-dev77912、dev77931。Python与静态资源变化未重建App，未修改实例身份或合并数据。
- 新详情绑定改变事件目录修订；已有E2规则不会自动获得后台权限，声明变化会按原规则暂停并要求重新预览。未在开发实例创建新自动化规则。

可复核记录：[验收收据](acceptance/event-hooks-e3-20261102/receipt.json)。验证使用模型/签名Package目录/合成媒体夹具，尚未验收真实第三方Package的完整界面、付费模型或微信发送。
