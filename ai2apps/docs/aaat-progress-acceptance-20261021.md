# AaAT 状态与进度契约验收（2026-10-21）

## 实现

先更新 `aaat-declaration-context-v1.md` 与集成指南，再实现既有 `report_progress`
通道上的 `content.task_progress` v1。业务阶段和计数由 owner 适配，AS 不认识
购物或新闻业务名词。校验有限百分比、计数、等待语义、字段及大小；保留旧协议。

宿主持久状态行 revision、当前快照与既有更新通知保持使用；终态 Run 不接受
迟到状态行更新，Chat 忽略旧版本读取响应。Chat 以纯文本通用展示计数与等待原因。

浏览器等待器去掉“非 Search All 就是 Web Reader”的身份猜测，转发真实任务名、
Mini-App 身份及 owner 投影，结束前也发送实际终态快照。Shopping owner 将订单
列表、详情（当前/总数）和分析计数映射为标准结构，不改购买和购物车行为。

用户进一步要求复用现有系统任务机制后，已移除 AaAT 独立读取情报业务进度的循环。
System Task 仍只通过原有 `TaskContext.report` 上报；handler 的同一个 `progress_view`
供任务中心/App/AaAT 读取，`SystemTaskService.follow` 只观察，不重试或取消业务工作。
标准 schema 收敛为 `ai2apps.task-progress/v1`，避免命名为另一套 AaAT 执行协议。
Shopping 也在 Browser Task 原有发布点产生一次公共快照，AaAT 不再接购物专属回调。

情报中心新增确认式 `intelligence.refresh`，复用现有频道采集器和权限；原有
`intelligence.news` 只查已存新闻，不能冒充刷新。刷新请求键在 owner store 的
事务中绑定实际 collection run，完成后重放仍返回同一任务；不同参数拒绝复用，
其他活动刷新不被抢占。取消只传递给本次调用创建的采集。完成、部分、失败明确返回。

## 自动验证

- 强制 AaAT 架构/行为门禁：152通过，71.90秒。已有 headless Metal 退出警告不影响通过。
- 系统任务、情报后台与进度：95通过，22.51秒，涵盖原采集器回归和新增 owner 刷新测试。
- 隔离 Chrome UI：1通过，验证任意计数更新，以及重新挂载后等待原因恢复。
- 新用例包含两种任意 Provider 身份下的真实调度进度持久化、终态保护；两种任意
  Mini-App 身份下的等待器转发；owner 阶段映射；刷新请求完成后重放/跨用户和改参
  拒绝；新闻 collector 复用及 partial 状态转发。模型/网络采用 fixture，未冒充真实采集。
- Python 编译及所改跟踪文件 whitespace 检查通过。

新增系统任务共用观察测试覆盖不同 App 身份、任务中心与对话快照一致、资源/人工
等待区别、观察取消不影响任务、越权拒绝及展示异常不阻断状态读取/取消。

## Dev 激活和实际网络验收（首次尝试，后续已获授权）

尚未激活，也未声称新的购物/新闻进度通过 Dev 实测。当前 Dev 端口62512。
无关的新闻后台采集已自然结束，但之前军事验收的 BBC 阅读任务
`run_15c6d55dd9d045a8852fc4bf07aa8312` 仍等待 Cookie 协助。

自动审批拒绝取消该旧任务，理由为未获得用户明确取消授权；已向用户询问。
未通过命令行或其他接口绕过取消拒绝，未在此等待状态下重启 Local。
后续须在获得授权、正常取消该任务且确认当前任务空闲后，用标准 Dev Helper
重启，核实 App/Helper source root 和当前 Local 导入路径/页面，再分别重跑
购物记录刷新与新闻频道刷新，检查 Chat 阶段计数、等待原因、刷新恢复和实际终态。

补货推荐能力选择与日期档位计算属于前次另行提出的业务问题，本轮状态契约变更
没有声称修复它们，也没有修改通用 Agent 提示来绕过所属业务能力。

## 获得授权后的实际验收（2026-10-21）

用户明确授权取消旧 BBC 任务后，通过 Dev 原生界面的取消按钮完成取消；数据库确认
无活动 Agent Run/System Task，使用标准 Helper 重启 Local。首次 PID88082 / port56351，
App/Helper 元数据均绑定当前 checkout，运行日志中的 builtin adapters、System Task service
导入路径也来自当前 checkout；原生 Chat 的新 metrics 组件实际显示。

购物：General Run `run_9f1b325773f7418da826a84e9372dbdc`，Browser Task
`btask_4d597355d9ecc367f3714ce2fceb86fd621fb6ffd06262effdac6099d8b9374c`。
Chat 原生界面实际显示订单详情 1/10、4/10、6/10、7/10；页面刷新后恢复4/10并继续推进。
Tool 返回20个商品、1页、35条购买日期记录，子任务及父任务 completed；最终回复报告
读取1页/35条记录，未操作购物车或生成补货单。模型调用曾先遇402和一次SSL错误，均在
业务执行前失败；换用已配置GPT-6.1 Sol并重试后才真正执行，不计为进度链路失败。

新闻：General Run `run_6cec5343dec341438d138b67e9a65daa`，同一System Task
`stask_f6d50ba0eb414051ae2237d73b57e401`，collection
`3b8f7336672944c4bdfc0c753935d8e4`，腕表频道。Chat显示后台来源阶段和已读取页面计数，
系统任务有pages_read/sources_completed推进。最终Task与Tool均明确partial、新增0；
Agent完成整理的回复也明确“部分完成，不能视为全部采集成功”。业务日志显示跳过已采集/
重复180条，Fratello单篇遇captcha，其余来源继续；未绕过验证码。

实测同时发现并修复两个收尾缺口：Browser等待器相同快照重复转发，新增跨Mini-App
去重断言；Intelligence Task清理阶段丢失累计计数、终态残留清理提示，改为保留owner
进度并在结束前同步真实业务总结。去重后强制门禁152通过（92.91秒）；后续owner修复
相关79项通过（19.77秒），编译及本轮文件whitespace检查通过。

两项任务结束且空闲后第二次标准Helper重启，PID89531 / port58231；最终复验继续记录如下。

新闻最终复验：General Run `run_87b932040fba4512b608c0ae8c80c583`，System Task
`stask_d3ee7de676614f36b41b1395b231373a`，collection `b621e94ad3bb4b9a8f87b7f3653ea629`。
实际终态partial；公共任务最终progress保留pages_read=6、sources_completed=6、articles_saved=0、
phase=finalizing，message为业务总结而非清理提示。Chat最终回复明确partial、0篇、跳过180条。
没有把无新内容/单源验证码冒充全部采集成功；原有采集权限未放宽。

购物最终复验：General Run `run_5c1b384c70f7462ab4b43a8de64feb1c`，Browser Task
`btask_25f06e3f0e693cc42c5b6734e713545c6d43523aaa398b95f11395c8bec78ac6`。
Chat观察2/10，页面刷新后恢复8/10，后台继续9/10并完成。最终同为1页、20商品、35条
购买日期记录，父Run completed，Chat显示Completed及35条同步结果；最终status revision=58，
不再因相同快照自唤醒产生数千次重复更新。两项复验结束后活动Run/System Task均为0。
最终Dev端口58231，运行模块导入路径及原生Chat新进度组件已确认；无App重建、发布或Cloud修改。

最终全部修改后的强制架构/行为门禁：152通过，81.21秒。
