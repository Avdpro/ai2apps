# AaAT 通用执行流程检查与验收（2026-10-20）

本轮按“任务 → 能力发现/候选选择 → 所选声明复核 → 组织调用 → 持久化交互/执行 → 结果解释与后续规划”检查。业务声明、领域定位、业务统计和证据仍由 App/Mini-App 提供。

## 发现和修复

| 环节 | 原缺口 | 修复 |
| --- | --- | --- |
| 发现 | app.describe 只有表单/交接，漏掉无表单 Provider | 接入通用 Router 清单，含归属、状态和版本；无筛选先给摘要 |
| 选择后读取声明 | 首轮把所有已启用 App 声明一起投影，不能保证调用决策已见过所选声明 | 依据本 Run 的实际选择、定向发现及交互目标按需加载；调用前对照决策模型请求中的声明和 Provider 版本；未见过则暂停该调用、返回准备状态，让模型重规划，绝不先执行 |
| 切换目标 | 表单可能切换 capability/provider，原决策只见过旧合同 | 按交互真实返回目标继续投影/复核；已在 App 执行的结果仍禁止重复操作 |
| 返回结果 | 大正文 JSON 预览可能截掉 aaat_context 和交互状态 | 单独保留有界结构化 Context、status、Provider 版本及交互执行标识；正文继续按需分页 |
| 候选与失败 | 通用指令对跨 capability 替代规划和失败状态解释不足 | 比较范围/输入/副作用/产物；允许提交前明确拒绝后的新方案；禁止通过换 Tool 绕过权限、取消、登录和确认 |

`tool_declaration_required` 是未提交的声明准备步骤，持久化成可恢复的调用前记录，不消耗业务失败重试次数，但仍受总步数/Token 预算限制。它不激活 App 的执行后结果策略。声明暴露并不能保证模型理解正确，所以 Provider 的 schema/prepare 和真实业务授权校验仍是必要的。

执行中的表单和 App handoff 已有持久化、actor/Installation/Session/Run 归属、版本、重复提交、取消、continuation 守卫，本轮不另造交互实现。只读 effects 声明现在正确地与有副作用操作区分；不扩大浏览器或任何业务权限。

## 多 Tool 与替代执行

同一 capability 多 Provider 的选择仍使用实际启用/冷却、历史成功、优先级以及用户显式选择。不同 capability 的可替代方案由 AS 对照声明规划，并遵守原用户授权；有实质目标差异才向用户澄清。不会为了比较而把每个有副作用的 Tool 都执行一次。

例如发布 Tool 明确不支持微博且提交前拒绝，AS 可以考虑已注册且兼容的浏览器方案。若失败发生在提交之后、结果未知，则宿主会阻断第二次有副作用调用（包括声明为写操作的浏览器方案），先查只读状态或交用户决定。本轮不向真实社交账号发帖，发布路径使用受控夹具。

## 自动验收

- 91项组合通过：声明、Todo、路由、表单、App handoff、Provider 参数、通用错误恢复和原始结果读取。
- 42项组合通过：选定声明与无表单发现、Search All 共享确认/正文总结/最终引用、App continuation。搜索夹具改为先接受准备复核，再模拟真实调用，没有绕过确认。
- 37项补充通过：完整 General 调度 → 声明复核 → 表单等待 → Runtime stop/start → API 修改提交 → 业务执行一次 → partial Context 保留 → 最终回答；交互/API/结果预览回归。
- 最终40项组合通过：新增无效选择保护、分组声明与 Provider 版本复核、未知发布结果拦截，以及通用错误恢复。各组合有重叠，不合并为唯一测试总数。

模型决策和外部发布/读取在自动路径中是测试替身；Runtime、SQLite、表单 API、ToolGateway 和路由为真实代码。测试退出后有 Metal 设备不可用的 atexit 警告，不影响 pytest 退出码0；不把它当成真实模型验收。

## App-Dev 实际验收

最终代码由空闲检查后的标准 Helper Local restart 激活。固定 app-dev App/Helper 源码根仍为当前 checkout，Local PID90719、端口65443；日志确认 Todo、组合 Service 和 Search workflow 的实际导入路径。

新建干净 General Agent 对话，使用已配置 DeepSeek V4.1 Flash，原样提交：`当前Video Studio有几项任务？A级的有几个？完成了几个？`。未指定 Tool、未补全项目名。

真实 Run **run_e0c8e8be6e924290bcd441031b50170f** completed。持久步骤为：

1. 首次模型请求没有 selected AaAT 完整声明；模型选择 todo.project_stats。
2. 宿主记录 tool_declaration_required，phase=prepare，未调用业务入口。
3. 第二次模型请求包含当前 Todo 注册声明与 Provider 版本；模型重新规划 `{"query":"Video Studio","scope":"recursive"}`。
4. todo.project_stats 实际成功执行一次，定位真实 ID `2c499668374445adb81263097231b43c`，结果 Context 为 complete，统计 total=2 / A=1 / completed=0；coverage.complete=true，范围明确不含父项目本身。
5. 第三次模型请求继续带 Todo 声明与实际结果，最终正确回答2/1/0，并说明包含已完成、排除删除/归档、直接子项与递归口径相同。没有 app.describe 绕行或要求用户补充项目全名，也没有待办写操作。

原生 Chat AX 可见完成态、真实项目名称、2/1/0及口径；最终 Message msg_e4051271b5134cbf9b1e2df3fd204e6a 文本与 Run 输出相同。共3轮模型、累计47733 tokens，包含声明复核额外一轮；无需用户重复确认。首次准备记录是未执行而非业务失败。

本轮未执行真实发帖，也未声称真实 Web Use 发帖链路已验收。跨能力替代和未知结果拦截由上述通用调度/API测试覆盖。
