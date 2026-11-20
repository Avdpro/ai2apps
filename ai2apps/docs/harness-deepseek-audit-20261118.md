# DeepSeek Harness 与 AI2Apps Harness 审查

日期：2026-11-18。本次只读源码和隔离注册盘点，未运行 DeepSeek、安装其依赖或修改产品代码。没有性能、质量或安全效果基准。

## 基线

DeepSeek 官方 HEAD 固定为 ca33fd6843b205e279c7ccb6cb73a472c78f5760。已核对工具目录及 PTY、jobs、LSP、MCP resources、Office、图片回读、PTC、子 Agent 控制、运行依赖等对应源文件。工具目录是可组合插件全集，不表示全部默认启用。

AI2Apps 当前源码在临时空目录启动核心 PlatformRuntime，实查 181 个 Service Tools、122 个 AaAT Providers，其中 Harness 34 个。临时实例没有 Dev 已安装 Package/MCP 配置，不将此数当作生产总数。外部 Coder CLI 自带能力不算内置 Harness。

## 能力对照

| 类别 | DeepSeek | AI2Apps 当前状态与差距 |
|---|---|---|
| 文件/搜索/补丁 | read/write/edit/apply_patch、glob/grep | 主体已有：workspace 读写、glob、regex、上下文行和有界扫描；另有目录保存、文件管理及 ZIP |
| 命令/进程 | bash/pwsh、持续 shell、PTY | 单次进程管理已有；process.write_stdin 已实现但未接 AaAT；PTY 有 backend，未注册模型工具 |
| 后台 jobs | job_list/output/kill、完成唤醒 | process status/wait/logs/cancel 和持久任务已有；缺统一 job 目录及跨类型完成/结果收取合同 |
| 提问/计划/目标 | ask_user_question、todo_write、goal、exit_plan_mode | 提问、持久计划和预算已有；独立计划模式/目标循环不是完全等价，非首要缺口 |
| Skills/依赖 | skill、load_workspace_dependencies | Skills 库、自动选择、准入和引用加载已有；缺统一的工作区运行依赖路径/版本查询入口 |
| 图片视觉回读 | read_image，按实际模型路由检查视觉能力 | 上传图像投影和视觉基础已有；缺执行中将自有 artifact/工作区图片重新送入模型的通用工具，base64 文本不等价 |
| 文档读取/PDF | Office 工具及文件技能 | PDF/DOCX 等解析和 document.read/info/search 已 AaAT；document.preview/create_pdf 底层已有，尚未 AaAT |
| Office 转换/渲染/重算 | office_convert/render/recalculate，需 Office kit | 无统一等价服务/工具；读取 XLSX 文本不是重算，提取 PPTX 文本不是页面渲染 |
| 正式交付 | present 及交付卡片 | Artifact、Studio 共享 Output、Gallery、导出已有；缺统一“本轮正式交付”标记，不应再建输出历史 |
| 会话历史/事件追踪 | session/event search/read/trace、工作区列表 | Bot history.search/get/attach 和原始结果/检查点读取已有；缺授权的通用跨 Session 事件检索与因果 trace |
| 子 Agent/Teams | spawn/fork、消息/中断/等待、实验任务板 | agent.delegate、Bot 委派/咨询/协作已有；通用持续后台子 Agent 控制未统一。App 开发专属控制不等价于普通 Bot 已开放 |
| 网页/浏览器 | web_search/fetch、实验 Stagehand | 已有 App-owned web 与 AI Browser AaAT；保持 BiDi 架构，不再暴露第二套语义浏览器协议 |
| 定时/插件发现安装 | schedule、plugin_market/manager | SystemTask/Todo 定时及 Messager task.propose、Discover/ACPF 已覆盖主要场景，不另建 scheduler |
| MCP | tools + resources/list、templates/list、resources/read | 动态 MCP Tools 进入 Service Registry，但此 adapter 不注册 App-owned AaAT；资源三接口在当前 adapter/manager 未实现，需连 backend 一起补 |
| LSP | definition/reference/implementation/hover | 未发现内置通用 LSP 服务/AaAT；文本搜索与外部 Coder 不等价 |
| Git worktree | enter/exit_worktree（实验） | 可用受控 git 命令，但缺 Harness-owned 工作区切换生命周期工具 |
| 程序式编排 | run_code + typed SDK、workflow/ralph | process.start 可运行程序，但没有程序内受守卫调用 AaAT 的 SDK；没有等价通用 PTC/workflow 入口 |
| 上下文/恢复 | 计量、溢出、压缩、结算、并发 | 当前已有路由测量、事务检查点、大结果回读和持久恢复；不沿用旧报告“只有字节预算”的判断。工具级受控并发仍有差距 |

## 已有但未向普通 Bot 提供 AaAT

### 三项明确漏接

| Tool | 已有实现 | 缺少部分 |
|---|---|---|
| process.write_stdin | processes/service.py 已注册并绑定，限制 Session/Run 的输入 | processes/harness_app.py 的 TOOLS 未包含 |
| document.preview | documents/service.py 已注册并绑定，返回短文本 | Harness TOOLS 未包含；不是页面图像预览 |
| document.create_pdf | Markdown/文本排版为 PDF Artifact，复用 PdfGenerator | Harness TOOLS 未包含 |

三项在隔离实例均 enabled、bound 且 ServiceRegistry 对 app-chat 可见，但没有 CapabilityProvider。因此旧 Service Tool 表有它们，不等于普通 Bot 能通过 app.describe 找到。

document.preview 还应完善覆盖度：现有实现只取前 20 块，truncated 只检查已取文本长度，可能不能反映后续块仍未返回。接入时应一并处理。

### 有 backend，但需要设计适配

- PTY：TerminalManager 有创建、输入、输出订阅、调整尺寸、关闭等能力；terminal/service.py 只有 Service/Instance，无模型 Tool。应增加 Task/Session/owner 范围，不能原样开放 UI host-shell。
- MCP Tool：适配器动态 ensure_tool/bind_tool，但没有相应 AaAT Provider；应补连接身份和权限归属。临时实例没配 MCP，不能据此声称 Dev 没有 MCP。
- 图像视觉基础已存在，但没有独立通用图片回读 Tool。
- Skills 已通过 owner 上下文选择提供；缺 skill.* 名称不代表功能不可用。

### 不应当作漏接而批量暴露

- agent.ask_user/current_time/delegate/read_plan/update_plan/read_tool_result/read_context_checkpoint/read_session_memory，以及 app.describe/collect_parameters/interact：共享内部控制协议，已向模型提供。
- browser.*：低层工具属于专用执行器及受保护 BiDi；普通 Bot 使用 AI Browser owner AaAT。
- appdev.child.*、subagent_*：App 开发专属项目隔离工具，不应直接变成跨 App 的 Harness 权限。
- system.echo、明确隐藏的 search-workflow 步骤：诊断/内部工具，不是产品缺口。

## 建议顺序

1. 补接三项：process.write_stdin、document.create_pdf、document.preview，并修正文档预览覆盖度。
2. 通用图片回读、受控 PTY/jobs、运行依赖查询。
3. MCP Tools 的 AaAT owner、MCP resources、Office 转换/渲染/重算。
4. LSP、worktree、通用子 Agent 控制；PTC/workflow/Teams 单独设计，避免替换全部执行循环。

## 源码依据

上游固定提交：
https://github.com/deepseek-ai/deepseek-harness/tree/ca33fd6843b205e279c7ccb6cb73a472c78f5760

对应文件：
- docs/tool-catalog.md
- packages/experimental/tool-terminal/src/index.ts
- packages/jobs/tool-jobs/src/index.ts
- packages/document/tool-office/src/index.ts
- packages/mcp/mcp-resources/src/tools.ts
- packages/lsp/tool-lsp/src/index.ts
- packages/core/tool-executor-ptc/src/index.ts
- packages/skill/tool-workspace-dependencies/src/index.ts
- packages/fs/tool-fs/src/read-image.ts
- packages/subagent/tool-subagent-control/src/index.ts

本地依据：processes/harness_app.py、processes/service.py、documents/service.py、terminal/service.py、terminal/manager.py、services/adapters.py、skills/selection.py、messager/history_tools.py、agents/general.py、agents/image_inputs.py、context_engine/core.py。

## 后续实施说明

本报告之后已补接 process.write_stdin、document.preview、document.create_pdf，并完善 preview 的字符/块截断回执。上面的 34 项盘点及 JSON 是修复前快照；当前 Harness 为 37 项。实现合同见 harness-file-utilities.md。
