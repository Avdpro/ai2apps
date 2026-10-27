# 社交点赞与只读访问恢复

普通只读访问默认允许仅在通用权限评估的内置兜底层生效：effects 包含 external_read 且仅含 external_read/network，capabilities 仅限 network.outbound/browser.read。本地明确拒绝或要求批准的策略优先；写操作、文件、密钥和其他能力不适用。地址访问限制、Profile 绑定和确认凭据独立执行。

Desktop Profile-bound 后端禁用旧 standalone browser service；社交任务仍通过 owner 原生 BiDi Gateway 运行。

帖子列表和详情提取 likes 的 count、display、status、reason。未观察到计数为 null，不能视为零；万/k 等标记 approximate，保留原标签。小红书详情计数未加载时在原 Task、原页面、原 Profile 内最多重新观察三次，不点击点赞；详情缺失但主页已观察到时保留主页计数与来源。失败保留原因。

Owner 通过现有 capability-scoped result policy 提供有界摘要，保留标题、日期、原链接、点赞和覆盖范围；完整媒体证据仍存储在原 Tool step。缺失字段应报告限制，不切换浏览器通道。AS 无站点或业务特例。

## Dev 实测

2026-10-26，在固定 Dev（Local 63155）输入原查询，使用当前 DeepSeek 模型。
Root run：`run_1116f4da98eb4222b2fcfca99c588afe`，completed，11 步。
账号解析：`btask_e1519eefc1eaa5cf543c00e8f5cb6844ab03ef81f1df47d25bef8e99f13c3a19`。
动态读取：`btask_ce3dec2e906ac20c8d3cc717f2ada8a871b6a11506d1b3107433e23d109610dc`。
二者均为 Default、同一原生 userContext，未创建独立浏览器实例。

只有一次账号与范围表单确认；工具授权 0 次、重复参数确认 0 次。
实际工具路径为 social.account → app.collect_parameters → social.account；无 web.fetch、
旧 browser 工具、agent.read_tool_result。存在声明加载及一次表单参数预检纠正，均未提交业务操作、未要求用户重复确认。

最近三帖（旧置顶单列，不算最近发布）：
- 2026-09-22：页面只显示“赞”，counter 无数字；原页面重新观察三次后仍为 unavailable，不能当作 0。
- 2026-08-22：1 赞。
- 2026-08-03：5 赞。

首帖额外只读诊断核实 `.like-wrapper .count` 为无数字空元素，未点击点赞，诊断页已关闭。
Chat 已可见最终 Markdown 表格；完整计数与缺失原因由摘要提供，无需分页媒体分析。

激活验证：固定 Dev App 与 Helper source-root 均为当前 Git checkout；运行 Local 的
Browser/owner SDK 导入日志来自该 checkout，新点赞字段及原页面恢复标记出现在实测持久结果，
旧 standalone service 状态为 disabled。未修改或重启 App-Dev、生产实例。

针对性 Python 回归 48 项通过，新增原页面恢复 2 项通过；跨站点 Chrome DOM 12 项通过。
最终架构门禁 358 项通过。未发布生产。
