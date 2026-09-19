# AI2Apps Test Center 界面改造 v1

状态：已实现第一版，等待实际使用反馈
实施日期：2026-09-09
范围：只修改 `ai2apps-test-system`，不修改 AI2Apps 产品与 Cloud

## 目标

本轮改造把 Test Center 从单页工具表单升级为面向日常测试运营的控制台。重点解决三类问题：大量 Case 难以浏览，Group/Case 维护依赖原始 JSON，以及 Catalog 覆盖诊断缺少独立的信息层级。

## 已实现的信息架构

顶层分为三个稳定入口：

- 运行测试：优先级、范围选择与 Run Manifest。
- 测试库：Group 导航、Case 表格和定义检查器。
- 覆盖诊断：新发现、未覆盖、失效引用、合同变化与归档统计。

测试库使用三栏布局：左栏按常规、按需和归档组织 Group；中栏提供 Case 搜索和来源/执行器筛选；右栏用于查看与编辑具体定义。自动生成和内置对象保持只读，Case 可以通过“复制为自定义”进入安全编辑流程。

## 编辑体验

- Group 和 Case 使用结构化字段，不再要求用户直接编辑 JSON。
- 新建 Case 先填写自然语言测试描述并选择目标 Group，再由 Codex 生成
  Schema 约束的结构化草稿。生成过程不直接保存、启用或运行 Case。
- Case 的 instructions、expectations、cleanup 以逐行列表编辑。
- 生命周期以 `draft → valid → trial-passed → enabled → archived` 步进条显示。
- 保存前显示字段错误与仓库文件 Diff。
- 原始 JSON 降级到高级折叠区，仅用于审阅。
- 复制使用明确的本地弹窗；归档可恢复，不提供硬删除。
- 没有自定义 Group 时，新建 Case 会先引导用户建立 Group。
- 从编辑器发起隔离试运行后，结束页提供“返回编辑 Case”。系统按稳定
  Case ID 重新读取测试库、恢复原 Group 并打开该 Case；试运行的本地服务
  会继续存活，因此返回后可以保存修改或再次试运行。普通测试 Run 不显示该入口。
- 通过、失败或阻断的试运行还提供“让 Codex 改进 Case”。复盘明确分开展示
  自动修订、需要用户补充和非 Case 问题；必需材料未满足时不能应用最终修订。
  图片由用户选择后进入 Case 专属的受管理 fixture 目录，并可同时补充图片事实或
  判断标准。Codex 候选只回填编辑器并展示 Diff，不自动保存或弱化失败断言。

## 视觉规则

- 采用低饱和灰蓝背景、白色工作面板和单一蓝色主操作色。
- 状态使用绿色、琥珀色和红色语义色，避免只依赖文字。
- 运行页与管理页共用按钮、卡片、徽标、表格和提示组件。
- Test Center 保持桌面管理工具密度；最小页面宽度为 980px。

## 工程结构

页面资源从 `selector.py` 的增量字符串替换中拆出：

```text
src/ai2apps_test/web/
  test_center.html
  test_center.css
  test_center.js
```

`web_assets.py` 在服务启动时把资源组合为自包含 HTML，因此现有 loopback 服务、随机 Token、写请求 Origin 校验和 API 路径保持不变。Setuptools package data 已包含这些资源。

Case 草稿生成由 `case_generator.py` 封装。它调用本机 Codex CLI 的临时会话，
使用只读沙箱、固定输出 Schema、180 秒超时和最小环境变量集合；最终返回值仍会
经过 Harness 的 Case 语义校验。API 只返回草稿，不执行 Catalog 写入。

## 验收

- P0–P3 选择和按需选择语义保持不变。
- 管理页能浏览全部 Group/Case，并能打开结构化详情。
- CRUD、校验、Diff、复制、试运行、归档和恢复继续使用原 API。
- 覆盖诊断具有独立页面和可展开的问题清单。
- 页面不读取或显示 Credential、密码、lease token、Cookie 或 Bearer。
- Codex 生成使用只读沙箱和临时会话；Harness 强制草稿为 `codex-ui`、
  `enabled: false`、`lifecycle: draft`，并按 Group 类型强制优先级语义。
- JavaScript 静态检查与 Harness 全量测试通过。

## 后续反馈重点

真实使用后重点观察：三栏宽度是否适合当前屏幕、282+ Case 下的滚动性能、Group 数量继续增长后的导航密度，以及表单字段帮助是否足以让非开发人员安全编写 `codex-ui` Case。
