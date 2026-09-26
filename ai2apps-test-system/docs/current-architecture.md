# AI2Apps 自动测试系统：当前架构、运行机制与目录说明

状态：当前实现说明
基准日期：2026-09-08
工具名称：AI2Apps Test Center / `ai2apps-test`
测试对象：固定的 `AI2Apps-test.app` 及 AI2Apps 仓库中的静态、模块、Package 和 UI 测试面

## 1. 本文用途

本文描述当前仓库中已经存在并正在使用的自动测试系统，而不是远期设想。它回答以下问题：

- AI2Apps 自动测试系统由哪些概念组成。
- CLI、Test Center、Catalog、Inventory、执行器、Codex 和测试账号如何协作。
- 当前实现分布在哪些目录和文件中。
- 一次测试从选择到报告经历什么过程。
- 哪些安全和隔离边界已经实现。
- 当前版本已经支持什么、尚未完整支持什么。
- 测试系统集中后的工程边界和兼容入口。

更完整的目标设计见 `docs/automated-test-system-v1.md`；日常命令见 `docs/quickstart.md`；可编辑 Test Case 的后续计划见 `docs/editable-catalog-development-plan-v1.md`。

## 2. 系统定位

AI2Apps 自动测试系统是一个测试编排器，不是一个新的测试框架。它统一调用已有的语法检查、Python 测试、Swift Test、Release App 校验、WebDriver BiDi、Computer Use 和 Codex，并把不同执行方式归一化成同一种 Case、状态和报告格式。

系统的基本原则是：

- 使用固定 Test App，不操作用户正在使用的生产实例。
- 从当前产品注册表和 Package manifest 动态发现测试对象。
- 以 P0–P3 选择测试范围；当前语义是累计包含。
- 能自动执行的 Case 由本地执行器完成，需要复杂 UI 判断的 Case 交给 Codex。
- 单个 Case 失败、阻断或超时后继续运行其他独立 Case。
- 页面实时显示进度、问题和执行器状态，并允许中止。
- 每次 Run 固化计划、状态、结果、证据和报告。
- 缺少证据、缺少 UI 执行或依赖不可用时不得伪装为通过。

## 3. 核心概念

### 3.1 Test App

`AI2Apps-test.app` 是专门用于发布形态验收的桌面实例：

- App：`apps/ai2apps-acefox/.build/AI2Apps-test.app`
- Bundle ID：`com.ai2apps.desktop.test`
- Instance ID：`test`
- Runtime profile：`cloud`
- Support data：`~/Library/Application Support/AI2Apps/instances/test`
- Instance cache：`~/Library/Caches/AI2Apps/instances/test`

它和生产 `default`、开发 `dev`、固定开发 `app-dev` 相互隔离。测试重置不应删除用户的 Hugging Face 缓存。

### 3.2 Component / Inventory

Component 是被测试的产品对象，例如：

- System App
- Main App
- Built-in Mini-Entry
- Package
- Packaged Mini-App

Inventory 是当前仓库实际存在的 Component 集合。它不是人工维护的第二份产品列表，而是从以下事实源动态发现：

- `ai2apps/apps/system.py` 中的系统 App manifest。
- `packages/*/ai2apps.json` 中的 Package manifest。
- `packages/*/app.yaml` 中的 Packaged Mini-App 定义。

### 3.3 Catalog

Catalog 是全部可运行 Test Case 的集合，由两部分合并产生：

1. `../tests/ats/catalog/base.json` 中人工定义的固定 Case。
2. 根据 Inventory 和组件类型模板动态生成的 Case。

当前每个 Case 至少包含：

- 稳定 ID
- 名称
- P0–P3 优先级
- Group 名称
- Executor 类型
- 超时
- 能力依赖
- 标签
- 是否为当前优先级范围的 required Case

Group 现在是一等实体，分为 `regular` 与 `on-demand`。常规 Case 必须属于 P0–P3；按需 Case 的 priority 为 `null`，不会被任何优先级 Run 隐式选中。

### 3.4 Priority

P 表示本轮测试深度，不表示缺陷严重度。当前为累计选择：

- P0：基础阻断检查和最小启动面。
- P1：包含 P0，并增加主要用户流程与核心交互。
- P2：包含 P0–P1，并增加视觉、语言、可访问性、异常和恢复矩阵。
- P3：包含 P0–P2，并增加真实能力、升级回滚和长程稳定性。

例如 `--priority P1` 会选择 P0 和 P1 Case。

### 3.5 Plan

Plan 是一次 Run 启动前编译出的不可歧义测试清单。当前 Plan 包含：

- Schema version
- 创建时间
- 选择的优先级与 Driver
- Git revision
- Inventory digest
- Catalog digest
- 发现的 Component 数量
- Catalog Case 总数
- 本轮 required Case ID
- 本轮实际 Case 快照

Plan 会保存为 Run 目录里的 `plan.json`。运行过程不应回头使用其他 Run 的结果，也不应因 Catalog 后续变化而改变本次计划。

### 3.6 Run

Run 是一次具体测试执行，ID 格式类似：

```text
20260908T121748Z-12760
```

每个 Run 有独立目录、状态、结果和证据。Run 状态可能包括 created、running、awaiting_agent、ready_to_finalize、completed、cancelling 和 cancelled。

### 3.7 Executor

当前有四类 Executor：

- `builtin`：Python 内部实现的确定性检查。
- `command`：以受控子进程运行已有测试命令。
- `codex-ui`：需要页面理解、视觉判断、复杂指针或 macOS UI 的 Case。
- `pipeline-action`：只由已校验 Pipeline 生成，执行固定 Test 实例的生命周期动作。

`builtin` 当前包括 Python/JavaScript/JSON/YAML 语法检查、Test App 固定身份检查和发布形态校验。`command` 当前用于既有 Swift Test、pytest 等测试。`codex-ui` 进入可恢复的 UI Job 队列。

### 3.8 Codex Driver

当 Run 包含 `codex-ui` Case 且选择 Codex Driver 时，Harness 启动受限的 `codex exec` 子进程。Codex 按以下协议工作：

1. 用 `next --run` 领取当前 Case。
2. 每个实质 UI 操作前后重新检查取消状态。
3. 只操作固定 Test App。
   Computer Use 使用 `next` 返回的 `shellAppPath` 连接当前内层 Shell。Harness 校验固定外层 Test Bundle ID 和内层 `.test.shell` Bundle ID，只接受当前 Test App 内唯一且不逃逸的 Shell，不搜索归档。禁止外层启动器、显示名称及其他实例。缺少有效路径时阻断；超时只重试已校验路径并记录证据。
4. AI2Apps 特权 Shell chrome 本身不是 WebDriver BiDi browsing context；Shell 导航、App/Mini-Entry 启动、原生窗口、可见状态检查和跨上下文/macOS 拖拽使用 Computer Use。
5. 只有 Case 明确测试 AI Browser 网页，且 Harness 已提供并验证绑定 Test 实例的受保护 Gateway/context 时，才使用 AI2Apps WebDriver BiDi。通用 Chrome/Firefox BiDi 连接不能替代 Test Shell，也不应为 Shell Case 枚举通用浏览器 context。
6. 将截图、日志等证据写入当前 Run 目录。
7. 用 `record --run --case --result` 提交结构化结果。
8. 单 Case 失败后继续领取下一个独立 Case。

Codex 进程启动失败或提前退出时，Run 保持可接管，Test Center 会显示：

```text
接管并完成 Run `<run-id>`
```

### 3.9 Test Account Lease

需要登录的 UI Run 使用 `test1@ai2apps.com` 至 `test10@ai2apps.com` 的固定测试账号池。机制是：

- 测试 Mac 的 Broker Credential 只保存在 macOS Keychain。
- Harness 向 Cloud Broker 临时租用一个账号。
- Cloud 临时开放账号、轮换密码并处理设备/Installation 状态。
- 临时密码与 lease token 只进入 Keychain，不写入命令行、Codex prompt、state、结果或报告。
- Harness 自动启动 Test App 并通过 Test Shell 登录。
- 领取和提交 UI Case 时按需 heartbeat。
- 完成、失败或中止后先注销客户端，再释放租约。
- 异常崩溃由 Cloud TTL 兜底回收。

测试账号依赖失败时，需要账号的 Case 标为 BLOCKED，Codex 不应在账号前置检查失败后继续盲目操作登录页。

### 3.10 Pipeline

Pipeline 是 `tests/ats/catalog/pipelines/` 中的一对象一 YAML 资产。它把 Case 和固定生命周期动作编译为严格串行的不可变 Run。Case 可以重复出现，每个步骤使用独立合成 ID；遇到 `codex-ui` 步骤时形成顺序屏障，结果提交前不会执行后续动作。

Case 步骤可声明期待 `passed`、`failed` 或 `blocked`。执行器和 Codex 只提交实际观察状态，Harness 保存 `observedStatus` / `expectedStatus` 并完成比较。期待失败并不修改原 Case，也不允许弱化断言。

动作包括重启 Test App、通过认证 Helper 重启 Test Local、只退出并重启固定 Test 实例，以及复用 Helper `InstanceDataReset` 重置数据。它们不能接受自定义身份或路径，不能触及 `default`、`dev`、`app-dev`。详细合同见 `docs/pipeline-mechanism-v1.md`。

## 4. 当前目录和文件职责

当前系统并不全部位于 `tests/`。实际分布如下。

### 4.1 CLI 入口

```text
ai2apps-test-system/bin/ai2apps-test
```

这是主 CLI 入口：定位测试系统与父仓库根目录，优先选择父仓库 `.venv/bin/python`，设置 Python package 路径，然后执行：

```text
python -m ai2apps_test.cli
```

父仓库的 `scripts/ai2apps-test` 是兼容 wrapper，只转发到主入口。

### 4.2 Harness 核心实现

```text
ai2apps-test-system/src/ai2apps_test/
```

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | Python package 标记 |
| `cli.py` | 命令解析、选择器控制、Run 编排、Codex Driver 生命周期 |
| `model.py` | `Component`、`Case`、Priority 和终态定义 |
| `inventory.py` | 从 System App 和 Package manifest 动态发现 Component |
| `catalog.py` | 读取基础 Catalog、生成组件 Case、去重、排序和选择 |
| `runner.py` | Doctor、Plan 编译、Run 启动、执行、UI Job 队列、record、finalize、cancel |
| `pipeline_actions.py` | Pipeline 的固定 Test App/Local 生命周期动作与身份约束 |
| `state.py` | Run ID、原子 JSON 状态写入、timeline 和 Run 查找 |
| `selector.py` | Test Center 本地页面、API、实时进度和中止交互 |
| `executors/builtin.py` | 内建检查和 command 子进程执行器 |
| `codex_driver.py` | Codex prompt、CLI 命令、子进程组、日志和停止逻辑 |
| `accounts.py` | 测试账号配置、Broker 调用、Keychain、租约、登录、heartbeat 和清理 |
| `native_login.swift` | Test Shell 原生登录自动化辅助程序 |
| `redact.py` | 输出和错误中的敏感信息脱敏 |
| `report.py` | 结论计算及 JSON、Markdown、HTML、JUnit 报告 |

### 4.3 Catalog 与测试配置

```text
../tests/ats/
  catalog/base.json
  test-accounts.json
```

- `catalog/base.json`：固定 Test Case 定义。
- `test-accounts.json`：账号池 ID、Broker origin、TTL 和十个允许账号；不包含 Credential 或临时密码。

### 4.4 测试系统自身的测试

```text
ai2apps-test-system/tests/test_system.py
```

它覆盖 Priority、Inventory、Catalog、Plan、Run 状态、报告、选择器、账号租约和安全边界等 Harness 行为。Catalog 中的 command Case 还会调用仓库中其他既有测试文件和 Swift Tests；这些产品测试不属于 Harness 源码。

### 4.5 Codex Skill

```text
ai2apps-test-system/.agents/skills/ai2apps-test/SKILL.md
```

这是 Codex 可发现的运行规范，定义 Run 的领取、执行、证据、取消、账号秘密和实例隔离规则。它不是普通说明文档；位置受 Codex Skill 发现机制约束。

### 4.6 设计和运维文档

```text
docs/automated-test-system-v1.md
docs/quickstart.md
docs/test-app.md
docs/cloud-test-account-leases-requirements-v1.md
docs/editable-catalog-development-plan-v1.md
docs/current-architecture.md
```

- `automated-test-system-v1.md`：完整目标、分层、UE 和复杂拖拽合同。
- `quickstart.md`：当前可执行命令和日常操作。
- `test-app.md`：固定 Test App 的构建、身份和数据隔离。
- `cloud-test-account-leases-requirements-v1.md`：Cloud 测试账号租约要求。
- `editable-catalog-development-plan-v1.md`：可编辑 Group/Case 的后续开发计划。
- 本文：当前实际架构和目录地图。

### 4.7 Test App 构建与产品事实源

Harness 依赖但不拥有以下文件：

```text
apps/ai2apps-acefox/scripts/build-test-app.sh
apps/ai2apps-acefox/scripts/verify-release-app.sh
apps/ai2apps-acefox/.build/AI2Apps-test.app
ai2apps/apps/system.py
packages/*/ai2apps.json
packages/*/app.yaml
```

这些属于产品、构建或 Package 事实源，不应搬进测试工具目录。

### 4.8 Run 产物

```text
ai2apps-test-system/artifacts/runs/<run-id>/
```

典型文件：

| 文件或目录 | 内容 |
| --- | --- |
| `plan.json` | 本次 Run 的不可变计划快照 |
| `state.json` | 当前状态、Case 结果、账号和 Driver 状态 |
| `timeline.jsonl` | 按时间追加的状态事件 |
| `result.json` | 机器可读最终或阶段性结果 |
| `report.md` | Markdown 报告 |
| `report.html` | Test Center 和人工查看的 HTML 报告 |
| `junit.xml` | CI/JUnit 消费格式 |
| `logs/` | command、异常和 Codex Driver 日志 |
| `screenshots/` | UI Case 截图证据 |
| `*-result.json` | Codex UI Case 提交的结构化结果文件 |

Run 目录是证据和结果，不是 Catalog。不能从旧 Run 拷贝 Case 结果到新 Run，也不能把 Run 目录当作可编辑测试定义。

## 5. 一次 Run 的完整流程

```text
CLI / Test Center
        |
        v
doctor 与身份前置检查
        |
        v
Inventory 发现 + Catalog 构建
        |
        v
Priority / Group / Case 选择
        |
        v
编译并固化 plan.json
        |
        v
执行 builtin 与 command Case
        |
        +---- 无 UI Case ----> finalize -> reports
        |
        v
租用测试账号并自动登录 Test App
        |
        v
Codex Driver 循环 next -> UI 操作 -> evidence -> record
        |
        v
注销并释放测试账号
        |
        v
finalize -> JSON / Markdown / HTML / JUnit
```

更具体地说：

1. `doctor` 检查仓库、Catalog、Python、Inventory 和 Test App 是否存在。
2. `compile_plan` 动态发现组件、构建 Catalog、按 P/Group/ID 选择 Case，并记录 Git 与摘要。
3. `create_run` 创建独立 Run 目录，原子写入 `plan.json` 和 `state.json`。
4. `start_run` 顺序执行 `builtin` 和 `command` Case；每个异常被限制在当前 Case。
5. 存在 UI Case 时，Harness 完成测试账号租约和 Test App 登录。
6. unattended Codex Driver 自动启动；手动模式则返回 `awaiting_agent`。
7. Codex 通过 `next`/`record` 完成 UI 队列，passed/failed 必须带 Run 内实际证据文件。
8. 最后一个 UI Case 提交后自动或显式 finalize。
9. finalize 补齐未完成状态、释放账号并生成全部报告。

当命令带 `--fresh-install` 时，Harness 在执行任何 Case、租用测试账号之前，通过 Test Helper 的认证 loopback 控制通道请求 `instance.reset`。Helper 仅在签名 reset capability、固定 `com.ai2apps.desktop.test`、instance `test`、Harness actor 和显式 `confirm_instance_id=test` 全部匹配时接受请求，然后复用托盘“重置数据…”所调用的 `InstanceDataReset`。Harness 不直接递归删除 UserData；重置失败时选定 Case 全部标记为 blocked。

## 6. CLI 说明

从 `ai2apps-test-system/` 项目根目录运行。

### 6.1 环境检查

```bash
./bin/ai2apps-test doctor
./bin/ai2apps-test account doctor
```

- `doctor`：检查本地 Harness 和 Test App 基础条件。
- `account doctor`：确认账号池配置、Keychain Credential 存在并被生产 Broker 接受；不会真实租用账号。

### 6.2 查看计划

```bash
./bin/ai2apps-test plan --priority P0
./bin/ai2apps-test plan --priority P1 --group "Built-in Mini-Entries"
```

`plan` 不执行测试，只输出编译后的测试范围。

### 6.3 页面选择并运行

```bash
./bin/ai2apps-test
./bin/ai2apps-test select --priority P1
```

无参数时打开 Test Center。页面允许按优先级、Group、搜索和单 Case 选择，启动后显示实时进度、当前 Case、问题、账号、Codex Driver、报告路径和中止按钮。

### 6.4 无人值守运行

```bash
./bin/ai2apps-test run --priority P0 --driver codex --unattended
```

Harness 执行确定性 Case，并自动启动 Codex 完成 UI Case，随后生成最终报告。

### 6.5 手动或故障接管

```bash
./bin/ai2apps-test next --run <run-id>
./bin/ai2apps-test record --run <run-id> --case <case-id> --result <result-file>
./bin/ai2apps-test finalize --run <run-id>
```

这些命令构成可恢复 UI Job 协议。`next` 返回 `cancelled` 后必须立即停止；返回 `done` 后不得重复提交 Case。

### 6.6 报告

```bash
./bin/ai2apps-test report --run <run-id>
./bin/ai2apps-test report --run <run-id> --open
```

### 6.7 测试账号运维

```bash
./bin/ai2apps-test account configure
./bin/ai2apps-test account heartbeat --run <run-id>
./bin/ai2apps-test account cleanup --run <run-id>
./bin/ai2apps-test account clear
```

`configure` 输入的是 Cloud 管理方提供的 Broker Credential，不是用户自选密码，也不是测试账号密码。

### 6.8 Pipeline

```bash
./bin/ai2apps-test pipeline list
./bin/ai2apps-test pipeline plan --id <pipeline-id>
./bin/ai2apps-test pipeline run --id <pipeline-id> --driver codex --unattended
```

Pipeline 也可在 Test Center 的 **Pipeline** 页面创建、编辑和运行。页面采用 Group-first Case 多选，支持追加、插入、排序、删除及每个 Case 的期待结果。

## 7. 结果状态和 Run 结论

Case 终态：

- `passed`：Case 目标满足；UI Case 必须有证据。
- `failed`：执行完成但断言失败，或执行器发生可归属本 Case 的错误。
- `blocked`：依赖、权限、账号、环境或身份条件不满足，无法有效执行。
- `skipped`：因用户中止等明确原因未执行。

Run 结论：

- `PASS`：选定范围全部完成，且包含该优先级的全部 required Case。
- `SCOPED_PASS`：用户缩小范围后，所选 Case 全部完成，但不是完整 required 范围。
- `FAIL`：至少一个 Case failed。
- `BLOCKED`：没有 failed，但存在 blocked、skipped、pending 或账号清理失败。
- `CANCELLED`：用户中止。
- `RUNNING`：尚未满足终态条件。

普通 Case 问题不触发 fail-fast。只有 Harness 本身无法读取或持久化状态等系统级故障，才可能终止整个编排。

## 8. Test Center 实现

Test Center 由 `selector.py` 启动本机 loopback HTTP 服务，URL 带随机 Token。当前 API 包括：

- `GET /api/plan`
- `POST /api/submit`
- `GET /api/status`
- `POST /api/cancel`
- `GET /api/catalog` 与 Group/Case CRUD、校验、归档、恢复和试运行路由
- `POST /api/catalog/cases/generate`：用自然语言描述生成未保存的结构化草稿
- `POST /api/catalog/cases/<id>/trial-review`：基于当前隔离 Run 生成结构化复盘与候选修订
- `POST /api/catalog/cases/<id>/fixtures`：为当前试运行 Case 保存受管理的图片样本

当前页面使用“运行测试 / 测试库 / 覆盖诊断”三级导航。测试库采用 Group、
Case、检查器三栏布局，Group/Case 通过结构化表单维护，原始 JSON 只作为高级
审阅入口。HTML、CSS 和 JavaScript 位于 `src/ai2apps_test/web/`，由
`web_assets.py` 组合为自包含页面；服务边界和 API 安全机制不变。详细界面约定
见 `docs/test-center-ui-renovation-v1.md`。

“新建 Case”先收集自然语言测试描述和目标自定义 Group，再通过临时、只读的
Codex CLI 调用与固定 JSON Schema 生成草稿。Harness 会覆盖模型不能决定的安全
字段：执行器固定为 `codex-ui`，状态固定为停用草稿，Group ID 固定为用户选择，
按需 Group 的 priority 固定为 `null`。只有用户检查表单并完成原有校验、Diff 和
保存动作后，定义才会写入 Catalog。

管理 API 的 Case 列表包含全部未归档定义，包括 `draft`、`valid`、停用和待
试运行 Case；每项同时标记是否 `runnable`。运行计划仍只从启用且生命周期为
`trial-passed` 或 `enabled` 的集合编译，管理可见性不会放宽运行准入条件。

隔离试运行结束后，本地控制服务保持存活。用户可以直接返回原 Group/Case，
也可以要求 Codex 复盘本次 Run。复盘输入只包含脱敏、限量的 Case 快照、结构化
结果和 Codex 过程事件，输出分为自动修订、用户补充项与产品/环境/Harness 问题。
缺少图片时，页面必须明确显示所需样本、原因和验收标准，并允许用户上传不超过
10 MB 的 PNG、JPEG、WebP 或 GIF。文件以内容摘要命名，仅能写入
`tests/ats/fixtures/<case-id>/`；Case 通过 `fixtures` 字段引用它们。复盘候选保持
Case ID、Group 和 Executor 不变，实质修改会停用并回退到草稿，只有用户确认、
校验 Diff 并保存后才修改 Catalog。取消的 Run 不生成复盘，产品缺陷不得通过降低
Case 预期来消除。

页面以轮询方式读取进度。Codex Driver 运行时，状态接口还会从当前 Run 的
`logs/codex-driver.jsonl` 读取有大小和条数上限的最近事件，在页面显示 Codex
消息、命令、工具调用、结果状态和最近活动时间。该输出在返回页面前统一脱敏，
并且只允许读取当前 Run 的 `logs/` 目录。关闭浏览器页面不会中止 Run；只有点击
“中止测试”或对应控制路径才触发 cooperative cancellation。

中止时 Harness 只终止自己启动的精确进程组，把当前及剩余 Case 标为 skipped，保留已经完成的结果并生成部分报告。它不应扫描或终止其他 AI2Apps 实例。

## 9. 隔离与安全边界

当前强制边界：

- 只允许 `com.ai2apps.desktop.test` / `test`。
- 不操作 `default`、`dev` 或 `app-dev`。
- Test App 数据和缓存使用独立 instance root。
- 不删除 `~/.cache/huggingface/hub`。
- Broker Credential 和租约秘密只存 Keychain。
- 秘密不得进入 Codex prompt、CLI 参数、state、证据或报告。
- passed/failed UI 证据必须是当前 Run 目录内已存在的文件。
- Run ID 和证据路径进行范围校验。
- 子进程使用独立进程组，超时和中止针对精确进程组。
- 报告前对外部输出和异常信息脱敏。
- 身份或权限不确定时 fail closed，并报告 blocked。

## 10. 当前已实现能力

- 固定 Test App 身份和环境 preflight。
- 动态发现 System/Main App、Built-in Mini-Entry、Package 和 Packaged Mini-App。
- 固定 Case 与动态 Case 合并。
- 累计 P0–P3 计划。
- Group 三态选择、搜索和单 Case 选择。
- 静态语法、manifest、Swift、pytest 和 Release App 验证执行。
- Test Center 实时进度、实时问题、账号状态和中止。
- Test Center 中经过脱敏和限量处理的 Codex CLI 实时输出。
- Case 级异常隔离，默认继续。
- 测试账号租约、自动登录、heartbeat、注销和释放。
- Codex 自动派发、可恢复队列和人工接管提示。
- UI 证据校验。
- JSON、Markdown、HTML、JUnit 和 timeline 产物。
- PASS、SCOPED_PASS、FAIL、BLOCKED、CANCELLED 结论。
- 一对象一 YAML 的可编辑 Group/Case Catalog、Schema 与语义校验。
- 原子保存、revision 冲突检测、归档/恢复、Diff 预览和生成 Case 复制。
- P0–P3、按需 Group、单 Case与排除项的确定性组合选择。
- Test Center“管理测试”、结构化 `codex-ui` 合同和隔离 trial run。
- 试运行 Codex 复盘、显式用户补充项、受管理图片 fixture 与候选修订 Diff。
- Newly discovered、Uncovered、Stale reference、Changed contract 与归档诊断。

## 11. 当前限制

- `base.json` 仍通过兼容 loader 读取；`catalog migrate --check` 可预检迁移，但尚未对官方 Catalog 执行仓库转换。
- 自动发现依赖当前 System manifest 与 Package 文件布局。
- BiDi + Computer Use 的完整场景库仍未覆盖所有 App 和复杂交互。
- Test-only 状态 snapshot/reset 控制没有完整实现为统一 Phase B 机制。
- 视觉 rubric、基线和结构差异复核尚未全面自动化。
- 完整场景库和统一状态控制仍需继续建设。

## 12. 集中后的工程目录

当前测试系统已经集中在父仓库的 `ai2apps-test-system/`：

```text
ai2apps-test-system/
  README.md
  AGENTS.md
  pyproject.toml
  .agents/
    skills/
      ai2apps-test/
        SKILL.md
  bin/
    ai2apps-test
  src/
    ai2apps_test/
      cli.py
      model.py
      inventory.py
      catalog.py
      runner.py
      state.py
      selector.py
      pipeline_actions.py
      accounts.py
      codex_driver.py
      report.py
      redact.py
      native_login.swift
      executors/
  tests/
    conftest.py
    test_system.py
  docs/
    current-architecture.md
    quickstart.md
    editable-catalog-development-plan-v1.md
    test-app.md
    cloud-test-account-leases-requirements-v1.md
  artifacts/
    runs/
```

继续位于父仓库的事实源与兼容入口：

```text
../tests/ats/                           # Catalog 与非秘密测试配置
../scripts/ai2apps-test                 # 转发到新 bin 的兼容入口
```

`ai2apps-test-system/` 不应成为嵌套 Git 仓库。它仍属于 `omlx-moe-cache` 的同一个 Git 工作树，这样 Inventory、Test App、Package 和 Catalog 的 revision 能保持一致。

`skills/` 与 `skill/` 本身都只是普通目录名。对本地 Codex 项目，真正有发现意义的是项目根目录下的 `.agents/skills/<skill-name>/SKILL.md` 完整路径。因此本项目不再设置额外的 `skill/` 或裸 `skills/` 目录，直接把 Skill 放在 `ai2apps-test-system/.agents/skills/ai2apps-test/SKILL.md`。每个 Skill 使用独立子目录，是因为该目录以后还可能包含脚本、参考资料和资源文件。

Codex Driver 已使用 `ai2apps-test-system/` 作为工作目录，因此可以发现本项目的 Skill。仓库根目录不再保留第二份 Skill。

## 13. 兼容与事实源

- `ai2apps-test-system/bin/ai2apps-test` 是主 CLI。
- `scripts/ai2apps-test` 是旧调用方式的兼容 wrapper。
- `ai2apps-test-system/src/ai2apps_test/` 是 Harness Python 实现的唯一事实源，不再保留 `tools.ai2apps_test` 副本。
- `ai2apps-test-system/.agents/skills/ai2apps-test/SKILL.md` 是 Skill 唯一事实源。
- `ai2apps-test-system/docs/` 是测试系统专属文档唯一事实源。
- `ai2apps-test-system/artifacts/runs/` 是新 Run 唯一输出位置。
- `../tests/ats/` 继续是 Catalog 和非秘密测试配置唯一事实源。
- 历史 `artifacts/ai2apps-test-runs/` 不迁移，也不由新 CLI 兼容查找。

## 14. 建立独立 Codex 项目

Codex 项目目录可以选择：

```text
/Users/avdpropang/sdk/omlx-moe-cache/ai2apps-test-system
```

该项目通过父仓库读取产品 manifest、Package、Test App 和 `tests/ats`（相对本项目为 `../tests/ats/`）。如果项目沙箱只允许写当前目录，编辑 Catalog 时还需要将父仓库的 `tests/ats/` 配置为额外可写目录；普通运行和只读 Inventory 发现不需要移动这些事实源。

“测试工具可编辑 Test Case”已按 `docs/editable-catalog-development-plan-v1.md` 的 Phase 1–5 实现；该文档继续作为验收与演进依据。
