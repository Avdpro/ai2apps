# AaAT：待办、情报、语音、素材、购物和知识库

本文记录 2026-10-19 的接入范围与验收。当前所有权和执行流程以 [AaAT 声明与 Context 契约](aaat-declaration-context-v1.md) 为准；后续 Todo 定位/层级统计与通用执行验收见 [架构审计](agentic-app-constraints-audit-20261020.md) 和 [流程验收](aaat-execution-flow-acceptance-20261020.md)。业务规则必须由所属 App/Mini-App 提供，新增业务不得通过 General Agent 的专用分支接入。

本次提供以下能力，统一进入 CapabilityRouter、app.describe、参数表单和工具进度，结果带实际 App/Mini-App 身份。现有业务服务继续负责权限、数据存储和执行，不复制 HTTP API 或浏览器控制协议。

| App / Mini-App | AaAT 入口 | 行为 |
|---|---|---|
| 待办 | todo.search / todo.get / todo.create | 查询与读取自有任务；确认目录、标题后创建。创建凭证与任务在同一 SQLite 事务写入，重试、并发和重新打开 Store 不重复创建。创建不启动执行器或计划任务。 |
| 情报中心 | intelligence.channels / intelligence.search / intelligence.read | 频道目录、文章分页查询、正文读取。创建频道沿用 app.interact 的 intelligence.create_channel，保留原有 App 交接和收集流程。 |
| 快速朗读 | voice.quick_read | 模型、文本、音色、角色、语速参数；复用 Quick Read 的持久后台任务和共享输出。 |
| 基础语音识别 | voice.transcribe | 保留既有音频材料和模型选择表单；识别文本同时发布到语音工坊共享输出。 |
| 详细转写 Mini-App | voice.detailed_transcription | 解析实际安装的 ai2apps.media-voice.transcription；选择会话音频/视频素材、compact/quality、语言、词级时间戳、分说话人及 JSON/Markdown/SRT。复用 voice-media 持久任务、冻结输入、重启中断处理、发布重试和共享输出；完整结果在 Artifact，返回正文预览至多24000字符。 |
| 素材库 | gallery.search / gallery.get | 按名称、类型、集合查找自有素材，返回稳定素材 ID 与元数据。文件路径和存储 locator 不交给模型。 |
| Shopping Pro | shopping.history / shopping.recommend / shopping.gift_recommend | 参数直接来自已安装 Mini-App 声明，沿用 Browser Task、Profile、隐私模型、来源任务与站点限制。购物车审核仍在 Shopping Pro。 |
| 知识库 | knowledge.search / knowledge.get / knowledge.add_text | 在原有工具上增加 AaAT Provider 与表单；保留原有读写能力、效果、可见性、检索器与 citation identity。 |

所有新执行入口要求真实用户、Installation 和可访问的 Session。Shopping 和语音生成还要求持久 Tool invocation。取消、失败、中断和缺模型不冒充成功，也不会在已提交操作后静默换 Provider。

本次没有将所有 App 的全部管理操作开放成工具：例如待办执行器启动、素材删除和支付结账仍不在本次新入口中。新的“继续在 App 中编辑并取回结果”适配器也未泛化；现有情报中心交接与其他已有 continuation 保持原合同。

## 验证

- 135项：新适配器8项、参数表单/模型参数、待办及语音输出回归。
- 68项：Shopping Pro 与共享语音输出；含现有隐私、Profile、来源任务和购物限制。
- 29项：已有 AaAT App continuation、App interaction、Provider 路由与禁用检查。
- 19项 JavaScript：共享语音输出、跨 Mini-App 选择保留和项目隔离。
- 一次组合运行中的交接并发用例出现完成/重新绑定次序竞争；单例复跑及29项整组复跑均通过，未改动其守卫。

## App-Dev 实际验收

2026-10-19，标准 Helper 在无 queued/running/publishing 任务时重启 Local；PID 69151，端口52723。固定 App 和 Helper 的 bundle ID、app-dev 实例及 DevelopmentSourceRoot 指向当前 Git checkout。运行日志确认 builtin_apps.py、background_page.py、search_workflow.py 从本仓库导入，原生窗口标题为 AI2Apps-App-Dev: App-Dev 127.0.0.1:52723。

原生 Chat 的 General Agent Run：run_0676cfde0c3f4a5a8fd7c96dd8b09f28。实际完成 todo.search、intelligence.channels、gallery.search、knowledge.search 四个只读工具，以及对 voice.quick_read、voice.detailed_transcription、shopping.history 的三次 app.describe 调用。返回正确的 App/Mini-App 归属；未创建待办、写入知识库、生成音频或读取订单。语音推理与 Shopping 实际订单操作仍需用户选择具体输入后验收；上述夹具回归不冒充真实模型或订单执行成功。

真实知识库调用同时保留了既有环境诊断：缺少 ai2apps.model.multilingual-e5-small，检索使用 FTS5，查询无命中。该项不影响 AaAT 路由，但本次没有验收语义召回，也未安装或替换模型。
