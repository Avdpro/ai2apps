# Agentic 的 App/Case 约束审计（2026-10-20）

## 范围

检查 Local 的 General Agent、App/参数交互、工具路由、结果预览、引用、预算，以及 Search workflow 和 Coding 子 Agent 的注册边界。不是对所有第三方 Package 或 Cloud 的全面安全审计。

## 发现与本次处理

| 原位置/行为 | 问题 | 现在的所有者/通用接口 |
|---|---|---|
| General Agent 全局提示直接描述 Search All 和研究/菜谱证据用法 | 业务语义混入通用提示 | Research 注册 agent_context；通用循环按可用能力投影 |
| General 执行循环判断 web.search、confirmation_id 并直接调用搜索确认模块 | 特定能力分支 | Research 提供 invocation_policy；原有 actor/Session/Run/确认凭证校验仍由 Research 执行 |
| General 直接调用网页 citation_instruction/bind_final | 最终回答绑定了网页业务策略 | Research 注册带 capability 范围的 AgentResultPolicy；核心只分发钩子 |
| agents/result_reference 根据 workflow_run_id 和 summary 特判搜索报告 | 结果裁剪依赖业务字段 | Research 提供 preview；核心只保留有界 App Context 和原始结果引用 |
| General 按 search-workflow、appdev.child/subagent 前缀限制可见性 | 核心理解业务命名空间 | 所属 Search/Coding 组件注册 executor 可见性；原先边界不放宽 |
| 通用参数/交接初始化直接导入 Voice 与 Intelligence | 业务引导依赖核心模块 | Service/App 注册组合层引导，泛型交互模块不再导入这些业务模块 |
| 通用历史图片投影提示“Use image.edit” | 绑定具体编辑能力名 | 改为使用接受该 Artifact ID 的已安装能力；保留图片内容投影这一媒体技术边界 |
| 预算结束提示固定称“搜索报告” | 对非搜索任务不准确 | 改为通用“已完成的结果” |
| agents/builtin_apps 承载 Todo 等业务适配 | 所有权/代码位置混淆 | 组合适配器移到 services/builtin_apps；Todo 定位、层级和统计在 todo/aaat |

agents/builtin_apps.py、agents/citations.py 保留纯兼容导出，避免破坏旧导入；没有保留业务实现。主循环不包含 Todo、Video Studio、Search All、web.search、image.edit 等业务名称分支。

设置中的能力参数预览还发现一项通用合同缺口：无模型的 Provider 可以不返回 models，但前端假定其存在。现在支持缺省/空 models，照常展示参数 schema；不是按 App 名修补。

## 仍保留且合理的约束

- General Agent 的平台规则：优先使用已安装能力、遵守参数声明/表单、按需询问用户、不编造资源 ID、取消不算成功。这些适用于所有 App。
- Tool 白名单、用户/Installation/Session/Run 归属、Provider 禁用、执行权限、副作用审批、预算、循环保护和恢复规则继续生效。声明和 next_actions 不能放宽它们。
- Search 的确认、正文证据、原始 URL 绑定；Shopping 的 Privacy/Profile；Voice 的共享输出；Coding 的父子角色/工作区隔离仍存在，但归属业务组件或专用执行器。
- Browser Builder、Research workflow、Coding parent/child 是显式专用 Agent/工作流。它们自身的领域合同不是 General Agent 的 Case 补丁。
- 媒体投影、Cloud/本地模型传输、通用附件 ID 保留属于技术协议边界，不是根据某个项目名推断业务。

## 验收

新对话原样输入：`当前Video Studio有几项任务？A级的有几个？完成了几个？`

App-Dev General Run `run_b16708ff2fd946e39b48e4efb5b2f864` 完成。实际仅调用一次 `todo.project_stats`，参数只有 `{"query":"Video Studio"}`。Todo 定位到项目 `2c499668374445adb81263097231b43c`（Video Studio 增强，路径 AI2Apps开发 / Video Studio 增强），返回总数2、A级1、完成0；直接子项和递归口径相同。

独立只读 Todo 数据核对结果相同。没有查询 App 能力目录、没有要求补充项目全名、没有写入待办。模型请求包含 Todo 注册的声明；最终回答与持久 Message 完全一致，并在原生 Chat 中展示。

初次激活：空闲检查后通过固定 App-Dev Helper 重启，Local PID 84582 / 端口60037。App/Helper 的 bundle ID、app-dev 实例及源码根正确；日志确认 todo/aaat.py、services/builtin_apps.py、background_page.py、search_workflow.py 从当前 checkout 导入。能力目录静态脚本实际提供内容与源码 SHA-256 一致。后续通用结果策略增加了显式 capability 作用域，防止 App 策略影响未调用其能力的任务；最终激活与回归记录见下方补充。

## 测试中发现的既有问题

更宽范围回归还出现以下失败，本次未修改其逻辑，也不将它们计作通过：

1. tests/test_ai2apps_agents.py 的 rich-input 用例提供 `data:image/png;base64,AA==`，不是有效 PNG，在现有图片校验中失败。
2. Coding 的实际 sandbox 子进程在当前工具沙箱下以71退出，日志为 Operation not permitted；不绕过沙箱保护。
3. Coding early-compaction 用例仍期待524288 bytes，但现有 General 默认上限已为2097152；本次未修改该默认值。

其余18项 Coding 用例单独组合通过，两个上述 Coding 用例明确 deselect。测试夹具/环境失败与真实 Todo 端到端结果分开记录。

## 最终补充记录

- 最终通用策略与交接声明合同完成后，空闲检查再次通过，标准 Helper 激活 Local PID **84958** / 端口 **61119**。日志中的 Todo、Service 组合适配器和 Search workflow 导入仍指向当前 checkout；固定 App/Helper 元数据未变。原生窗口实际标题更新到61119，最终端口提供的 capability_tree.js 与源码 SHA-256 一致。
- 107项主回归通过；最后的22项补充回归通过，包含独立 App handoff 声明、禁用 Provider 和图片投影；另18项 Coding 回归通过（上述2项明确 deselect），能力树3项 JavaScript 回归通过。各组合有重叠，不合并虚报总数。
- 端到端验收以上述已完成且持久化的 Run 为准。最终激活后原验收报告由新 Local 恢复显示；尝试追加独立新会话时原生控制器返回 noWindowsAvailable，未将旧报告记录成第二次新执行。后续作用域调整不改变 Todo 业务统计，已由通用策略隔离测试覆盖。
- 没有 App 重建、Cloud 改动、发布或待办内容修改。


## 选择后声明复核补充

后续按完整 AaAT 流程复查发现，前述“按可用能力投影”仍是首轮全量声明，并且 app.describe 漏掉无表单 Provider；已改为候选摘要与所选声明分离，首次调用前保证决定该调用的模型请求已包含对应可信声明/版本。大结果预览保留结构化 Context 和交互完成态。通用失败重规划不添加平台/App分支，未知副作用结果继续拦截替代提交。最终代码在 App-Dev 新真实 Run run_e0c8e8be6e924290bcd441031b50170f 验收2/1/0，完整记录见 [AaAT流程验收](aaat-execution-flow-acceptance-20261020.md)。
