# Flash-Bot B1 首批：固定工作流与计算器

2026-11-05。本批完成 [开发计划](bot-types-development-plan-v1.md) 的 F1–F3、计算器参考工作流及相应故障检查。B1 的第二条“发票识别与归档”工作流仍待实施，未在目录中伪装为可用；本批不表示整个 B1 阶段已经完成。

## 用户可见行为

Desktop/Mobile 的既有新建菜单开放 Flash-Bot，ASC/Outlet/Mirror 继续灰显。选择 Flash 后可选固定工作流，当前只有“数学表达式计算”。名字、头像可配置，职责展示流程说明；职责文字不改变代码逻辑。创建不要求 AI 模型，不预授予 App 权限。

打开计算器后使用现有消息流，输入区提示表达式，隐藏不支持的附件与语音入口。每次输入独立处理，不进入普通 Bot 的模型判断或任务续接。错误返回具体拒绝原因，输入保留供修改；无效输入不创建消息、Todo Task 或执行 Run。合法输入先持久准入并反馈排队，结果作为新消息出现在信息流中，期间可继续输入下一条表达式。

## 类型和工作流所有权

- Flash 定义使用 `execution_mode=flash, audience=owner, location=local`，配置仅包含可信工作流 ID/version，不接受脚本、模块路径、任意参数对象或 Provider/权限指令。创建 API 同时检查菜单预设与底层维度一致。
- `messager/flash_workflows.py` 的宿主注册表保存可信代码校验器和执行回调。注册表不可原地修改，重复版本或非 callable 回调拒绝。创建/运行只解析已注册的精确 ID/version，缺失版本不改用其它流程。
- 当前计算器使用 AST 白名单和 Decimal，不使用 eval/exec，不允许调用、属性、变量、容器或任意代码。最多 512 字符、128 个 AST 节点、64 字符数字字面量；指数为 -100 至 100 的整数，十进制运算精度 28 位，数值量级受限。支持括号及 `+ - * / // % **`；除零和超限运算在准入前拒绝。
- 普通 Bot 的咨询、委派、固定协作和受管 Agent 执行入口保留 owner 类型检查，不能让模型冒充 Flash。通用 App Chat 提交也不能绕过固定输入入口。Flash 的跨 Bot 调用及 Event/定时入口留待独立的类型化合同，不因 Bot 可见或被授权使用就自动开放。

## 执行、版本和权限

`messager/flash.py` 是所属专用执行器，不修改 General Agent。真实链路为：代码验证 → 持久 Flash submission → 原 Todo managed Task/Run → `messager-bot:<bot_id>` 串行 lane → 原 AgentRuntime 的固定 executor → 原消息存储。系统 Task 仅观察同一 Agent Run 并传递取消，不重新执行计算、不另建调度时钟。

Calculator executor 不返回模型或 Tool 动作，manifest 为空 Tool 白名单。Todo 的 managed model 字段使用内部非模型标记，不做模型选择或模型调用。创建拒绝携带模型/App 授权的此类无模型流程；工作流目录明确声明不需要模型和 App。未来需 AaAT 的流程须声明必要能力，复用 Bot Access、版本和原 Interaction 审批，不可直接绕过授权调用业务服务。

每次提交冻结工作流定义、输入、语言和 Bot 授权 revision。Task binding 绑定 actor/Bot/submission 和 Todo 执行字段摘要；执行时复查当前 Bot/主会话归属、类型、权限 revision 和精确工作流版本。配置的后续变化不能替换已排队任务的原快照；旧工作流被移除或权限撤销则明确阻断，不以新流程补跑。当前没有公开配置更新/类型转换接口。

## 幂等、取消和恢复

Session + request_id 唯一准入，输入/配置摘要冲突拒绝；同一次重试只返回原请求。Task creation key、Todo launch receipt、Agent Run idempotency key 和结果消息 key 各自复用既有持久回执。跨数据库在“已入队但 acknowledgement 未写回”处中断时，恢复原 Task/Run，不产生第二次执行。

同 Bot 的新输入与普通后台任务共用原 lane，排队不占据聊天输入区。取消通过 Todo 停止原 Agent Run；尚未开始的取消从真实 Todo 终态回写 Flash 状态。恢复逻辑只恢复原关联，不重新提交已取消/完成请求。

删除/清除对话沿用已有清理合同：Flash 所有后台 Task 被识别为 Bot 自有任务。删除 Bot 会软删除并停止它们，恢复 Bot 仅恢复暂停的 Task 记录。原对话归档后，不把迟到结果写入新对话；已完成结果的重复读取不重复回写。收敛状态来源是原 Todo/Agent 回执，而非模型描述。

## 验证与加载

- 原 Bot/对话/清理/咨询/委派/Mobile 关联检查：74 passed（78.89s）。
- 扩展 Flash、协作、Todo owner 和通用架构行为检查：47 passed（160.09s）。
- 最终 Flash 文件增加 Mobile 无模型输入、取消/删除恢复、旧配置快照等验证后：29 passed（10.51s）。
- JavaScript 输入/对话检查：10 passed；隔离 Chrome 创建流程 2 passed，原加载/历史 2 passed，Flash 无模型发送与消息流结果 1 passed。浏览器数据与模型均为夹具；Python 执行链路使用真实 SQLite、Todo、AgentRuntime 和系统任务观察，模型绑定为禁止调用以证明零模型执行。
- 没有改共享 Agentic、AaAT 发现/声明、交互协议或结果策略；本轮运行所属模块和通用架构行为检查，没有重复完整 AaAT gate。未修改图片消息组件、Cloud 或发布流程。

已通过标准 Helper 空闲检查加载固定 App-Dev；核对 App/Helper 源根、Local `messager/flash.py` 实际导入、`messager_flash_submissions` 表，以及变更脚本实际提供字节。原生界面检查确认 Flash 菜单可选、其它三类灰显；打开创建草稿显示数学表达式工作流且无需模型，随后取消草稿。未提交真实 Bot 创建、业务任务或对外操作。

## 接下来

发票流程需要独立的模型/图片输入合同、字段校验、重复材料识别和幂等归档服务；归档范围与数据保留由所属 owner 定义。不能把图像识别文字直接当成已核实的归档记录。固定模型步骤、费用/敏感确认及 ACPF 回接应先通过这条第二工作流验证，再扩展第三方 Package 工作流。

最终加载记录见 [App-Dev 源码与资源核对](acceptance/flash-bot-b1-20261105/source-verification.jsonl)。原生 UI 检查只打开并取消创建草稿；没有创建真实计算器 Bot。
