# 平台通用网页搜索 WebAgent

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
