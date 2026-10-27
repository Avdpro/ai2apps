# Browser/WebAgent Task 执行策略与预算

可信 Source、WebAgentInvocation/ Mini-App submit 的 `execution_policy` 使用同一验证、编译和持久化链路；网页、模型返回的业务正文不能修改这些参数。适用于共享 WebAgent Task，不声称所有 System Task 或 General Agent 已迁移到这一结构。

| 参数 | 默认 | 含义 |
|---|---|---|
| allow_user_intervention | true | 可按既有协议请求人工协助或审批；false 时在创建人工 Interaction 前失败，绝不自动批准 |
| timeout_seconds | null | 不新增 Task 总时限；正数为从入队开始的总秒数，包括排队、准备页面、执行和等待 |
| recovery_timeout_seconds | null | 不新增自动恢复累计时间上限；非负秒数，0 禁止自动恢复 |
| max_recovery_attempts | null | 不新增自动恢复累计次数上限；非负整数，0 禁止自动恢复 |
| visual_locating | true | 允许视觉定位，仍要求已选模型声明图像能力 |
| visual_review | on_recovery | off / on_recovery / always |
| allow_visual_state_confirmation | false | 仅未知状态可选择视觉补充；不能覆盖 owner 明确失败 |
| readback | true | 必须实际回读；false 不合法 |

null 表示没有新增的预算限制，**不是移除旧保护**：既有 Run deadline、单步/模型时限、无进展 watchdog、普通文章读取10秒、访问预检2秒、视觉弹窗恢复默认4秒及原有恢复循环上限继续兼容。显式 recovery_timeout_seconds 可替代弹窗视觉恢复的旧4秒局部值，同时所有恢复仍受剩余累计预算和总时限约束。

## 恢复范围

预算覆盖视觉定位/缺失目标恢复、列表结构恢复和 adaptive 自动恢复。编译动作失败后的一次 adaptive 恢复观察/决策/动作周期计一次（原本声明为 interpreted 的主执行规划不算恢复）；列表模型恢复计一次；无现成目标的视觉恢复包含定位、单次输入与回读，嵌套 helper 不重复扣减。同一 Task 的所有调用共享已用次数和时间；正常必需的视觉复核/业务操作不因“恢复次数耗尽”被豁免。读取已加载可见正文是原读取的只读提取，不是一次新的有副作用恢复。

恢复开始前持久化次数和 active_since，结束后持久化耗时。Local 在恢复中停止时，重启按 active_since 保守计入已过时间（包括停机时间），不返还次数。该机制不授予重放不确定点击、提交或网络效果的权限；原 action journal、owner 证据和取消边界继续有效。

## 总时限与恢复

入队时将绝对 task_deadline_at 写入原 browser_context；幂等重提不能刷新它。创建 Run 使用剩余预算并保留旧 Run 上限。队列及运行监控负责终止过期任务，浏览器执行 runner 还以剩余时间覆盖页面绑定/创建和实际动作。清理可在后台继续，不允许超时变成重新执行操作。

timeout_seconds 和恢复上限在嵌套调用中取更严格值；allow_user_intervention=false 与关闭的视觉策略不能由子能力重新开启。owner 的 mandatory visual review/readback 与调用方关闭视觉冲突时返回策略错误，不降低 owner 检查。正常购物车保持 minimum_execution_policy.visual_review=always、readback=true 以及数量等业务回读。

## 调用方专用值

快速搜索来源查询、结果页读取明确传入：

```json
{
  "allow_user_intervention": false,
  "visual_locating": false,
  "visual_review": "off",
  "timeout_seconds": 10
}
```

恢复预算/次数仍采用 null，允许在总时限内进行既有非视觉恢复；不会自动开启视觉或请求人工。普通搜索/搜索适配器的 Web Reader 保留此前无人值守10秒行为，通过显式 allow_user_intervention=false、timeout_seconds=10 表达，视觉仍由 owner/default 策略决定。其他旧调用不传新增字段时保留原行为。

搜索仍从同一次已确认结果中有限补位，保存成功原文与失败原因，不另发搜索，不以摘要片段代替正文，不放宽引用、访问限制、权限或费用确认。

## 兼容与验证

旧持久 IR 缺少新增字段时按默认值解释；同请求 ID 若试图改变策略则拒绝，既不改旧 Task，也不自动新建替代执行。没有数据库表结构迁移。回归覆盖任意 owner、Source 编译、真实 SQLite/任务队列、嵌套约束、无人工等待、累计恢复/重启、总时限和购物车强制检查。fixture 不代表外部网站或付费模型实时验收；测试与开发启用记录见发布账本 NXR-TASK-EXECUTION-BUDGETS-20261024。
