# AI Browser 工作台

三栏分别为 Domain/能力和 Profile 导航、能力调用或编辑、全部 Domain 的任务队列与最近记录。
编辑使用原有 Agent Mini-Entry；每份编辑内容使用独立 iframe，切换导航仅隐藏，不销毁。
运行也使用同一执行器，每任务绑定专用 BiDi context。任务完成时销毁执行 iframe，结果仍在 Local。

## 任务准入

`browser_tasks` 保存运行参数、编译 generation、Profile、运行 ID 与状态；
`browser_task_settings` 保存当前账号的全局和 Profile 上限。默认全局 4、每 Profile 1，上限 16。
队列 FIFO，但允许跳过被占用的 Profile。SQLite `BEGIN IMMEDIATE` 原子检查与占位，多个工作台窗口共享限制。
排队时固定 generation，后续编辑不会悄悄替换队列中的版本。任务入队前验证参数 Schema。

侧栏和 API 的 WebAgent 根运行通过 `create_ir_run` 使用同一准入机制和任务记录；达到上限会返回错误，
工作台发起的任务可排队。嵌套能力共享根任务名额，不重复计数。
Agent Mini-Entry 通过原生 Profile bootstrap 与当前 BiDi userContext 对应关系填写 `browser_context.profile_key`；旧调用方未提供时保守计入 default Profile。
情报中心直接调用页面 SDK 的采集操作不是 WebAgent 根运行，暂不在这套队列内。

工作台需要保持打开来执行浏览器动作。它不依赖浏览器侧栏，但不是脱离所有 UI 的后台浏览器 worker。
90 秒租约、15 秒续约；执行器失联后，下一次队列查询/准入时暂停任务并标记中断。
中断仍占名额，避免自动重放结果不明的发布动作。用户检查后可在原 context 仍存在时继续，或取消。
等待用户协助仍占名额。降低上限不终止已在执行的任务。

## Profile 绑定

原生 Shell 启动交接返回 opaque BiDi `user_context`；`bind` 交接仅解析 Profile 绑定，不打开网页。
这是浏览器 UI 负责的受保护 Profile bootstrap，不是 DOM/点击语义 API。
工作台用原生 `browsingContext.getTree/create/navigate` 创建专用任务 Tab、读取 Tab 数量。
已有窗口仅被聚焦时，SDK 使用确切 userContext 创建页面，不依赖焦点、枚举顺序或碰巧相同 URL。

AceFox 对应源码：SDK `moz/acefox-firefox-153/browser/components/ai2apps/content/shell.mjs`。
AppDev 必须通过固定构建脚本采用该资源，生产采用 AceFox 快照时也必须包含此改动。
