# 平台通用网页搜索 WebAgent

架构约束（2026-10-20）：Search All/Web Reader 的准备、确认、正文证据、引用绑定和报告预览由 Research/Mini-App 提供，通过 [AaAT 通用契约](aaat-declaration-context-v1.md) 的声明、invocation_policy 和作用域化结果策略接入。不得将搜索专用提示、确认凭证校验、工具名判断或引用处理重新写回 General Agent/共享 AS。下方早期直接搜索入口的记录由后面的“共享搜索准备、确认与正文研究流程”更新；当前 AS 选择、声明复核和失败替代语义以 AaAT 契约为准。

平台搜索能力：`builtin:web:search` / `web.search`，generation 使用能力目录当前返回值（当前 `web-foundations/2`）。它是只读搜索 WebAgent，可以被其他 WebAgent 的 `agent.call`、可信 Local App 或后台定时任务复用，不依赖 AI 浏览器前台页面。

输入为 `query`（必填，1–2048 字符）和 `limit`（默认 10，1–50）。输出保留在 AgentRun 的 `output.result`：

```json
{"query":"机械腕表", "provider":"google", "count":1,
 "items":[{"title":"文章标题", "url":"https://example.org/article", "summary":"可用摘要"}],
 "page_url":"https://www.google.com/search?q=...", "page_title":"搜索页面标题"}
```

搜索返回网页文章链接列表，不自动阅读正文。搜索引擎结果并不保证每项都是新闻文章；调用方可以追加正文读取和业务过滤。标题及摘要是网页不可信输入。

默认先导航 Google 搜索页，通过常见结果区域与语义标题链接提取自然结果，过滤导航及可识别广告、解包 Google/Bing 跳转、去重。Google 导航超时、返回非搜索页、结果区域变化导致无有效链接时，转用免费 Bing 网页搜索。Bing 同样无可用结果则任务失败，不将空列表标为成功。不会求解验证码或绕过访问限制；回退只是改用另一公开搜索服务。完整动作和回退路径记录在共享 Task/AgentRun 中。

执行全部使用 compiled 步骤和 Local BiDi SDK，不调用 AI。所有参数/默认值经过共享 Agent 调用绑定；URL 查询词使用共享 URL 编码规则。搜索使用统一队列、独立任务 Tab、Profile、并发门控及 SSE 状态投影。HTTP 提交入口为 `POST /v1/platform/browser-workspace/tasks`，指定上述 `agent_id`、`capability`、`profile_key`、`input`；可信 Local 调用方也可以使用 `WebAgentInvocation.submit` 并提供自己的 session、caller_app_id 和幂等 key。

未来 API provider 可在相同能力和输出契约下替换浏览器步骤：配置 Google 搜索 API provider 后优先尝试 API，失败回到网页 provider 链。API 凭据必须放平台秘密存储，不进入 Agent Source、Task input、页面或日志。本次没有添加尚未可用的 API-Key 设置项，也没有接入付费/免费 API。现有 `research` 的 HTTP 搜索 Tool 是另一个调用入口，本次未改变它；使用本通用 WebAgent 的 App 应调用共享 Task 入口。

验证：编译与调用回归、Google 空结果/导航超时转 Bing、双引擎失败、中文查询编码、Google 语义标题回退及跳转去重、Bing 跳转还原。真实联网搜索质量与网站可用性仍受地区网络和搜索引擎页面变化影响，单元验证不替代真实网站验收。

## AaAT 系统搜索接入（2026-10-19）

系统 `web.search` / `web.fetch` 现在经 CapabilityRouter 路由：

- `ai2apps.search-all.search`（AI 浏览器中的 Search All Mini-App）：默认提交 Google、Bing 两个声明的搜索能力，复用统一 Browser Task 队列、批次并发和页面清理。合并按 URL 去重，返回 `results` / `items`、`source_id`、实际 `search_source` 和 `browser_task_id`；单源失败单独记录，全部无结果则失败。
- `ai2apps.web-reader.fetch`（Web Reader Mini-App）：从安装声明解析 article 程序，通过共享后台读取公开网页。执行前校验公开 URL，并把程序站点范围收窄到本次请求的 origin；正文按 `max_chars` 截断。返回来源 ID、正文和实际 Browser Task ID。

可信 Local 调用通过 `WebAgentMiniAppBroker.registered` 解析当前可访问的安装声明，验证 origin Session、启动对应 owner App instance，再复用 `submit_declared`。不要求前台挂载 HTML，不创建第二套浏览器执行循环。前台原 mount-bound 调用继续使用相同实现。模型不能提供程序、Package 路径或任意 caller 身份。

两项能力保留 Mini-App 身份和可查看的源任务。公开网页正文、搜索摘要始终是不可信数据。Search All 的 `sources` 可指定已声明搜索源，默认不包含需要独立配置的搜索 API。参数表单由 Provider 动态给出源选项。

旧 HTTP 实现保留为独立 Provider；Mini-App 未安装且未提交任务时可按 AaAT 规则回退，已提交后的失败不会静默切换到 HTTP。模型或用户也可以显式选择 Provider。超时/取消会请求共享任务树取消本次执行叶子，不绕过后台资源清理。需要登录或验证码的任务提供原 Task ID，交由 AI 浏览器已有人工协助入口处理。

## 共享搜索准备、确认与正文研究流程（2026-10-19，替代上述直接搜索门面）

Agentic 的 `web.search` 与 Search All Mini-App 现在复用
`research/search_preparation.py` 和 `research/search_workflow.py`。
先提交仅含 `ai.transform` 的 plan Task，优化搜索词并建议来源；此时没有搜索源任务。
用户看到可编辑搜索词，再选择快速、优选或自定义。优选预选 AI 建议的来源，用户可增减；
自定义直接编辑来源；快速使用当前配置的搜索 API，否则使用 Google。

只有点击“搜索”才创建不可变的确认回执并启动研究 Run。回执在 SQLite 中按
actor/Installation、App 或 interaction、Session、原 Run、Profile、Package digest 绑定。
模型不能声明确认成功，不能改写已确认参数；重复点击恢复同一个 Run。
Agentic 通过持久参数表单确认后调用原 Tool，Mini-App 通过 mount-bound Host channel
使用同一后端机制。搜索门面固定使用该已确认流程，旧 HTTP Provider 仅保留为可信兼容
适配器，不再作为未确认调用的自动绕过路径，也不会替换已提交的搜索或正文读取。

后台 Run 经原 Browser Task 队列提交来源，报告每源进度；搜索完成展示有任务来源的文章列表，
由 Web Reader Mini-App 逐篇读取最多五篇正文（每篇最多 12000 字符），显示序号和总数。
只将成功读取的正文交给 standard 任务模型总结；逐篇失败单独记录，全部失败不生成结论。
模型返回受限 source_ids，服务器将其绑定为实际已读文章的标题/URL，拒绝未知引用、空引用
或模型另造的链接。搜索摘要不能充当正文证据。

两边都展示搜索、阅读、总结阶段。Mini-App 的状态观察只读取持久 Run，不推进浏览器执行；
关闭或刷新页面后重新观察原 Run，不重新提交。保留原分身、来源任务、历史页面清理确认和
显式保留页面选项。后台中途失败会如实报告；不宣称对任意进程崩溃窗口自动无损重放。

Google 的 `/url`、签名 `/goto` 结果先通过无 Cookie 的 HTTP 跳转元数据解析：每跳先验证
公开 HTTP(S)、无凭据及 DNS 地址，限制四次跳转并拒绝循环、内网和未离开 Google 的地址。
此阶段不下载或提取文章正文。结果保留 `search_url` 和 `redirect_chain`，Google 组内优先
图文地址进入阅读队列，视频结果仍完整展示；解析失败保留 `resolution_error`，不读取旧跳转地址。
Web Reader 接收验证后的真实 URL，权限仍收窄到该 origin，返回其他 origin 也会拒绝。
正文只能来自原 BiDi Browser Task，不以元数据请求替代。失败记录保留 Task/Run ID、操作、
提取失败原因（包括 CSP/Readability 的 fallback_reason），不返回捕获的 HTML、页面正文或凭据。
