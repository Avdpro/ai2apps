# AI2Apps 测试工具可编辑 Test Case 开发计划 v1

状态：Phase 1–5 已实现，待真实 UI 使用反馈继续迭代
目标仓库：`omlx-moe-cache`
目标工具：AI2Apps Test Center / `ai2apps-test`
范围边界：只改测试系统，不改 AI2Apps 产品功能代码
建议实施方式：建立独立 Codex 项目，按本文阶段逐项实现与验收

实施记录（2026-09-09）：Schema/模型/兼容 loader、原子 Catalog Store、CLI、Test Center 管理页、Diff/CRUD/归档恢复、结构化 trial run、升级覆盖诊断和生成 Case 复制流程已经落地。现有 P0–P3 Manifest 通过逐 ID 等价测试；`base.json` 保持只读兼容，尚未执行实际迁移。

当前测试系统的实际目录、概念和运行流程见 `docs/current-architecture.md`。Harness、Skill、文档、自测和新 Run 产物已经集中到本项目；本文后续实现以当前目录为准。

## 1. 结论与当前目录边界

当前测试机制并不全部位于 `tests/`。`tests/` 主要保存人工维护的测试目录数据和测试系统自身的回归测试，完整机制分布如下：

| 目录或文件 | 当前职责 |
| --- | --- |
| `../tests/ats/catalog/base.json` | 人工维护的基础 Test Case 定义 |
| `../tests/ats/test-accounts.json` | 测试账号 Broker 的非秘密配置 |
| `tests/test_system.py` | 测试系统自身的自动化回归测试 |
| `src/ai2apps_test/` | Catalog、选择器页面、Run 状态、执行器、报告、测试账号和 Codex 驱动的主要实现 |
| `bin/ai2apps-test` | 主命令行入口；父仓库 `scripts/ai2apps-test` 为兼容 wrapper |
| `.agents/skills/ai2apps-test/SKILL.md` | Codex 接管及执行 UI Case 的操作约定 |
| `docs/automated-test-system-v1.md` | 测试系统总体设计 |
| `docs/quickstart.md` | 使用说明 |
| `artifacts/runs/<run-id>/` | 每次 Run 的状态、日志、截图和报告；不是测试定义源 |

本计划仍将可编辑的测试定义放在 `../tests/ats/catalog/`，但编辑器、校验、选择和运行逻辑继续属于 `src/ai2apps_test/`。不应为了让目录“看起来集中”而把实现代码搬入 `tests/`。

## 2. 要解决的问题

当前 Catalog 有三个结构性限制：

1. `Case.priority` 必须是 `P0`、`P1`、`P2` 或 `P3`，所有 Case 都被迫属于优先级体系。
2. Group 只是 Case 上的一个字符串，不是可编辑、可描述、可启停的实体。
3. Test Center 只能选择已有 Case，不能创建、编辑、复制、停用或校验 Case/Group。

目标是支持两条彼此独立的测试组织轴：

- 常规优先级：P0–P3，继续用于每次发布或日常回归，保持目前的累计选择语义。
- 按需测试组：例如 `WebAgent Corner Cases`，不属于任何 P，只在用户显式勾选该组或其中 Case 时运行。

“按需”不是新的优先级，也不能偷偷进入 P0–P3 Run。

## 3. v1 目标

v1 完成后，用户应能在 Test Center 中：

- 新建、编辑、复制、停用和归档一个 Test Group。
- 将 Group 定义为“常规”或“按需”。
- 在 Group 中新建、编辑、复制、停用和归档 Test Case。
- 对常规 Case 选择 P0–P3；对按需 Case 不设置 P。
- 在启动 Run 前按整组或单 Case 勾选/取消。
- 同时选择一个优先级范围和若干按需组，最终执行二者并集。
- 保存前实时看到字段错误、ID 冲突、无效依赖和不安全配置。
- 对草稿 Case 做一次隔离的试运行，通过后再启用。
- 在运行报告中看到 Case 来源、Group、优先级或“按需”标记，以及实际 Catalog 版本摘要。

所有编辑必须持久化为仓库中的可审查文件，能够通过 Git diff 查看，不使用只存在浏览器 Local Storage 中的隐藏配置。

## 4. 非目标

以下内容不进入 v1：

- 修改 AI2Apps 客户端、Cloud、Mini-App 或 Package 的产品实现。
- 在网页中提供任意 Shell 命令编辑器。
- 允许页面读取或显示 Broker Credential、租约密码、用户 Session 或其他秘密。
- 自动启用 Codex 临时生成的测试。
- 多用户云端协同编辑、权限系统或远程 Catalog 服务。
- 嵌套 Group、Group 继承、条件表达式语言。
- 在 Catalog 编辑期间修改已经启动的 Run。
- 将自动发现的 App/Package/Mini-App Case 当成人工文件直接编辑。

## 5. 核心数据模型

### 5.1 Test Group 成为一等实体

建议新增 `TestGroup`：

```yaml
schemaVersion: 1
id: webagent-corner-cases
name: WebAgent Corner Cases
description: WebAgent 的低频、边界和恢复场景。
kind: on-demand
enabled: true
defaultSelected: false
order: 500
tags:
  - webagent
  - corner-case
```

字段约束：

- `id`：全局稳定、不可因改名自动改变；只允许小写字母、数字、点和连字符。
- `name`：页面显示名称，可修改。
- `kind`：仅允许 `regular` 或 `on-demand`。
- `enabled`：关闭后不出现在普通选择区，也不能被常规 Run 隐式选中。
- `defaultSelected`：按需组 v1 必须默认为 `false`，防止新增昂贵或破坏性测试被自动执行。
- `order`：只影响页面显示顺序，不影响结果。

### 5.2 Test Case

建议扩展当前 `Case` 模型：

```yaml
schemaVersion: 1
id: webagent.corner.drag-image-to-composer
name: Drag gallery image into Video Composer
groupId: webagent-corner-cases
priority: null
enabled: true
required: false
executor: codex-ui
timeoutSeconds: 600
requires:
  - test-account
tags:
  - drag-drop
  - gallery
componentId: null
description: 验证从 Gallery 向 Video Composer 指定输入区域拖入图片。
instructions:
  - 打开 Gallery，选择测试素材。
  - 将素材拖到 Video Composer 的目标 Clip 区域。
  - 调整 Clip 在轨道中的位置和长度。
expectations:
  - 目标区域在拖入时显示明确反馈。
  - Clip 出现在正确轨道和时间位置。
  - 拖动后预览和最终状态一致。
cleanup:
  - 删除本 Case 创建的临时工程。
```

关键规则：

- `regular` Group 中的 Case 必须有 `P0`–`P3` 优先级。
- `on-demand` Group 中的 Case 必须为 `priority: null`。
- `groupId` 必须引用存在且启用状态合法的 Group。
- `executor` 必须来自允许列表；v1 页面不接受任意可执行文件路径。
- `timeoutSeconds` 必须在系统设定的安全上下限内。
- `instructions`、`expectations` 和 `cleanup` 是 Codex UI Case 的结构化执行合同，不直接当作 Shell 执行。
- `required` 表示该 Case 被选入本次 Run 后是否影响本次 Run 的结论，不表示按需 Case会进入发布优先级集合。

### 5.3 来源与可编辑性

Catalog 合并后，每个对象都应有只读运行时字段：

- `sourceType`: `generated`、`built-in` 或 `user-authored`
- `sourcePath`: 来源文件或生成器名称
- `editable`: 是否允许从页面编辑

规则：

- 自动发现生成的 Case 为 `generated`，页面只读。
- 现有 `base.json` 迁移后的官方 Case 为 `built-in`，默认可复制，不建议直接删除。
- 用户新增的 Group/Case 为 `user-authored`，可以编辑、停用和归档。
- 全局 ID 冲突必须报错，禁止沿用当前字典覆盖导致的静默替换行为。

## 6. 文件存储方案

建议采用“一对象一文件”的 YAML 存储，降低冲突范围并方便 Git 审查：

```text
../tests/ats/catalog/
  base.json                         # 兼容期只读，后续迁移
  groups/
    built-in-mini-entries.yaml
    webagent-corner-cases.yaml
  cases/
    builtin-agents-discover.yaml
    webagent-corner-drag-image.yaml
  schemas/
    group.schema.json
    case.schema.json
  archived/
    groups/
    cases/
```

持久化要求：

- 只允许写入父仓库的 `tests/ats/catalog/`，即相对本项目的 `../tests/ats/catalog/`。
- 校验真实路径，拒绝 `..`、绝对路径、符号链接逃逸和文件名注入。
- 使用临时文件加原子替换，避免进程中断留下半个 YAML。
- 写入前比较 `revision` 或内容摘要，发现并发修改时返回冲突，不覆盖磁盘新版本。
- 归档优先于硬删除；归档操作可恢复。
- 保存后的文件应稳定排序，避免无意义 Git diff。
- 密码、Token、Cookie、租约响应和本机绝对运行路径不得进入 Catalog。

现有 `base.json` 应先继续被读取，再通过明确的迁移命令转为新格式。迁移不能改变 Case ID、优先级、执行器、超时和 `required` 语义。

## 7. Catalog 构建与选择语义

### 7.1 Catalog 分层

构建顺序建议为：

1. 读取并校验人工维护的 Group/Case 文件。
2. 兼容读取尚未迁移的 `base.json`。
3. 从当前 AI2Apps 内容动态发现 App、内置 Mini-Entry、Package 和 Packaged Mini-App。
4. 生成只读的标准 Case。
5. 检查全局 ID、引用、选择模式和执行器合法性。
6. 生成稳定排序的最终 Catalog 和 `catalogDigest`。

任何冲突都应使 Catalog 校验失败并指出两个来源，不能选择“最后一个获胜”。

### 7.2 选择规则

建议将选择器输入建模为：

```json
{
  "priority": "P1",
  "groupIds": ["webagent-corner-cases"],
  "caseIds": [],
  "excludedCaseIds": []
}
```

确定性规则如下：

1. `priority: P1` 选择所有启用的常规 P0 和 P1 Case。
2. 优先级选择永远不包含 `on-demand` Case。
3. 显式选择按需 Group 时，加入该组所有启用 Case。
4. 显式选择单个 Case 时加入该 Case，但仍需通过依赖和安全校验。
5. 多种选择来源取并集，以 Case ID 去重。
6. `excludedCaseIds` 最后应用，用于页面中从整组或优先级集合里取消个别 Case。
7. 页面在提交前显示最终 Run Manifest，而不只显示过滤后的 Catalog。
8. Run 创建时保存完整 Case 快照和 `catalogDigest`；后续编辑不影响正在运行或已经结束的 Run。

若只选择按需组，则允许 `priority: null`。为了兼容现有行为，不带任何筛选参数的 CLI 仍可默认使用当前默认优先级。

## 8. Test Center 页面设计

页面建议分为两个主模式：`选择并运行` 和 `管理测试`。

### 8.1 选择并运行

显示三个区域：

1. 常规测试：选择 P0–P3，解释累计包含关系。
2. 按需测试组：默认全部未选中，可按整组或单 Case 勾选。
3. 本次 Run Manifest：显示最终 Case 数、预计时长、所需能力、账号需求和排除项。

Group 使用三态复选框：全选、部分选择、未选择。搜索只改变可见项，不改变隐藏项的选择状态。每个 Case 显示来源徽标和 `P0`–`P3` 或“按需”徽标。

### 8.2 管理测试

管理页需要提供：

- Group 列表：常规、按需、停用、归档和只读生成组分区。
- Group 操作：新建、编辑、复制、启停、归档和恢复。
- Case 列表：按 Group、来源、执行器、要求、标签和状态过滤。
- Case 操作：新建、编辑、复制、启停、归档、恢复和试运行。
- 结构化表单：字段级帮助、即时校验和保存前预览。
- Diff 预览：明确展示将创建或修改哪个仓库文件。
- 只读提示：自动生成对象解释其来源，并提供“复制为自定义 Case”。

编辑器不得暴露 Broker Credential，也不得把测试账号的临时密码写入 Case 指令。

### 8.3 草稿和发布流程

建议生命周期为：

```text
draft -> valid -> trial-passed -> enabled -> archived
```

- 新建内容先作为草稿保存，不进入普通 Run。
- Schema 校验通过后标记 `valid`。
- 用户可执行单 Case 试运行；结果写入普通 Run artifact，不写入 Catalog。
- `trial-passed` 后可启用。若用户选择跳过试运行，应在 UI 中明确提示并记录该事实。
- 编辑已启用 Case 的执行步骤、预期结果或依赖后，应重新回到待试运行状态。

## 9. 本地 API 设计

Test Center 当前已经通过带随机 Token 的 loopback HTTP 服务提供 `/api/plan`、`/api/submit`、`/api/status` 和 `/api/cancel`。建议在同一安全边界内扩展：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/catalog` | 返回合并后的 Catalog、来源和可编辑性 |
| `GET` | `/api/catalog/groups/{id}` | 获取 Group 及 revision |
| `POST` | `/api/catalog/groups` | 新建 Group 草稿 |
| `PUT` | `/api/catalog/groups/{id}` | 校验 revision 后更新 Group |
| `POST` | `/api/catalog/groups/{id}/archive` | 归档 Group |
| `POST` | `/api/catalog/groups/{id}/restore` | 恢复 Group |
| `GET` | `/api/catalog/cases/{id}` | 获取 Case 及 revision |
| `POST` | `/api/catalog/cases` | 新建 Case 草稿 |
| `PUT` | `/api/catalog/cases/{id}` | 校验 revision 后更新 Case |
| `POST` | `/api/catalog/cases/{id}/archive` | 归档 Case |
| `POST` | `/api/catalog/cases/{id}/validate` | 返回 Schema 和语义校验结果 |
| `POST` | `/api/catalog/cases/{id}/trial-run` | 创建只包含该 Case 的试运行 |

安全要求：

- 所有接口只监听 loopback，并继续要求启动时随机 Token。
- 所有写接口只接受 JSON，限制请求体大小，并校验 `Origin`、Token 和 revision。
- API 不接受任意目标路径；文件路径只能由经过校验的对象 ID 推导。
- 写操作不能触碰产品代码、其他工作区、运行目录或 HF 缓存。
- 页面关闭或服务退出后不留下具备远程写权限的常驻服务。

## 10. CLI 演进

保留已有命令，并增加显式 Catalog 管理和按需选择能力：

```bash
./bin/ai2apps-test catalog list
./bin/ai2apps-test catalog validate
./bin/ai2apps-test catalog migrate --check
./bin/ai2apps-test plan --priority P1
./bin/ai2apps-test plan --group webagent-corner-cases
./bin/ai2apps-test plan --priority P1 --group webagent-corner-cases
./bin/ai2apps-test run --case webagent.corner.drag-image-to-composer
./bin/ai2apps-test select
```

兼容性要求：

- 现有 `--priority P0` 到 `--priority P3` 行为保持不变。
- `--group` 从按组过滤改为显式加入 Group，需在帮助和迁移说明中标明；如果担心脚本兼容，可新增 `--include-group` 并暂时保留旧参数。
- `plan` 输出必须标明常规与按需来源，以及最终去重后的 Case 数量。
- `run` 必须把解析后的最终 Manifest 固化到 Run 目录，而不是在每个 Case 开始前重新读 Catalog。
- `catalog validate` 应可在 CI 中运行，失败时返回非零退出码。

## 11. 与产品升级和自动发现的关系

产品增加 App、Package 或 Mini-App 后，仍由现有 Inventory 自动发现并生成标准 P0–P3 Case。编辑功能不能破坏这条自动覆盖链。

新增以下诊断视图：

- Newly discovered：本版本新发现、尚未有人审阅的组件及生成 Case。
- Uncovered：存在组件但没有适用标准或自定义 Case。
- Stale reference：自定义 Case 引用了当前不存在的组件。
- Changed contract：组件类型、发布状态或能力需求变化，可能使 Case 失效。
- Disabled/archived：停用内容，避免被误认为覆盖仍然存在。

诊断只提出候选项，不得自动修改或启用用户 Case。产品升级后的 P0–P3 仍可自动扩展；按需 Group 只有用户明确维护时才改变。

## 12. 实施阶段

### Phase 1：Schema、模型和只读兼容

目标：先建立正确的数据边界，不改现有页面行为。

- 新增 `TestGroup` 和允许 `priority: null` 的 Case 模型。
- 定义 JSON Schema 和语义校验器。
- 增加 YAML Catalog loader、来源标记和冲突检查。
- 兼容读取 `base.json`。
- 重写选择函数，区分优先级集合与按需集合。
- 为现有 Catalog 生成完全等价的 Manifest，证明没有回归。

验收：当前 P0–P3 选择结果逐 ID 一致；按需 Case 不进入任何优先级 Run。

### Phase 2：持久化服务和 CLI

目标：具备安全、可测试的 CRUD 底座。

- 实现原子写入、revision 冲突、归档/恢复和路径限制。
- 增加 `catalog list/validate/migrate`。
- 支持 `plan/run --group`、`--case` 及组合选择。
- Run 固化 Catalog 快照与摘要。

验收：重启工具后编辑内容仍存在；运行中的 Run 不受后续编辑影响。

### Phase 3：Test Center 编辑器

目标：完成用户可操作的编辑体验。

- 增加“管理测试”模式。
- 完成 Group/Case 表单、复制、启停、归档、恢复和 Diff 预览。
- 在“选择并运行”中分离常规与按需区域。
- 增加最终 Run Manifest 预览。

验收：不编辑文件即可从页面建立 `WebAgent Corner Cases` 并选择运行。

### Phase 4：试运行和安全收口

目标：防止未经验证或不安全的 Case 进入无人值守执行。

- 实现单 Case trial run。
- 实现执行器允许列表和结构化 Codex UI 指令。
- 增加请求体、路径、符号链接、并发写和秘密扫描测试。
- 完成失败恢复、错误提示和审计信息。

验收：无效 Case 无法启用；页面不能借 Case 定义执行任意 Shell。

### Phase 5：升级覆盖诊断

目标：让 Catalog 能随 AI2Apps 产品升级持续演进。

- 增加 Newly discovered、Uncovered、Stale reference 和 Changed contract 视图。
- 报告 Catalog 覆盖变化。
- 提供从生成 Case 复制为自定义 Case 的流程。

验收：新增一个模拟 Mini-App 后可自动出现标准 Case 和待审阅提示，不污染按需 Group。

## 13. 预计代码变更范围

主要修改：

- `src/ai2apps_test/model.py`
- `src/ai2apps_test/catalog.py`
- `src/ai2apps_test/selector.py`
- `src/ai2apps_test/cli.py`
- `src/ai2apps_test/runner.py`
- `src/ai2apps_test/report.py`
- `tests/test_system.py`
- `../tests/ats/catalog/`
- `docs/quickstart.md`
- `.agents/skills/ai2apps-test/SKILL.md`

建议新增：

- `src/ai2apps_test/catalog_store.py`
- `src/ai2apps_test/catalog_validation.py`
- `tests/test_ai2apps_test_catalog_store.py`
- `tests/test_ai2apps_test_catalog_api.py`
- `../tests/ats/catalog/schemas/group.schema.json`
- `../tests/ats/catalog/schemas/case.schema.json`

除非实施时发现明确的测试可访问性缺口，本项目不得修改 AI2Apps 产品 App、Mini-App、Package 或 Cloud 代码。

## 14. 测试计划

### 单元测试

- Group/Case Schema 正确与错误输入。
- 常规 Case 必须有 P，按需 Case 必须无 P。
- P0–P3 累计选择保持现有语义。
- 只选按需组、只选单 Case，以及优先级与按需组并集。
- 排除 Case、去重、稳定排序和空选择。
- 全局 ID 冲突不再静默覆盖。
- 自动生成、内置和用户来源的可编辑权限。
- revision 冲突、原子写入和归档恢复。
- 路径穿越、符号链接逃逸、超大请求和未知执行器拒绝。

### 集成测试

- 页面创建 Group 和 Case，重启后仍可读取。
- 页面编辑后 Git diff 只包含预期 Catalog 文件。
- `catalog validate` 可被 CI 调用并正确设置退出码。
- `plan`、`run` 和选择器对同一选择生成相同 Manifest。
- 编辑 Catalog 时，已启动 Run 的 Case 快照不变化。
- 报告正确显示 Group、来源、P/按需状态和摘要。

### 端到端验收场景

1. 从页面新建 `WebAgent Corner Cases` 按需组。
2. 新建三个 `codex-ui` Case，不指定 P。
3. 运行 P0、P1、P2、P3，确认三个 Case 均未被隐式选中。
4. 勾选整个按需组，确认三个 Case 全部进入 Manifest。
5. 取消其中一个 Case，确认只执行其余两个。
6. 同时选择 P0 和该按需组，确认执行集合为二者并集。
7. Run 启动后编辑其中一个 Case，确认本次 Run 仍执行启动时快照。
8. 归档该组，确认普通选择页不再显示；恢复后内容完整。

端到端测试可使用测试系统自身的 fixture 和伪执行器完成。只有验证真实 UI Case 执行链时才启动 `AI2Apps-test`，并继续使用专用测试实例与租约账号。

## 15. 完成定义

全部满足以下条件才算 v1 完成：

- 用户可以完全通过 Test Center 创建、编辑、复制、停用、归档和恢复 Group/Case。
- `WebAgent Corner Cases` 这类 Group 可以明确不属于任何 P。
- P0–P3 不会隐式包含任何按需 Case。
- 优先级、按需 Group 和单 Case 可以组合选择，结果确定且可预览。
- 页面保存内容是仓库内可读、可审查、可恢复的文件。
- 自动发现生成的 Case 保持只读，并继续随产品内容扩展。
- 所有 ID 冲突和失效引用都有明确错误，不发生静默覆盖。
- 活跃 Run 使用不可变快照，Catalog 编辑不会污染运行结果。
- 页面无法访问秘密，也不能通过可编辑字段执行任意 Shell。
- 现有测试系统回归测试通过，并新增上述单元、集成和端到端测试。
- 文档、CLI `--help` 和 Codex skill 与最终实现一致。

## 16. 建议的独立 Codex 项目任务说明

建立后续 Codex 项目时，可以直接使用以下目标：

> 阅读 `docs/editable-catalog-development-plan-v1.md`，在当前 `ai2apps-test-system` 项目中实现 AI2Apps Test Center 可编辑 Test Group/Test Case，并仅在父仓库 `../tests/ats/` 保存 Catalog 与非秘密测试配置。先完成 Phase 1，并用回归测试证明当前 P0–P3 Manifest 没有变化；之后按 Phase 2–5 顺序推进。按需 Group 不属于任何 P，默认不选中。只修改测试工具、测试定义和相关文档，不修改 AI2Apps 产品代码，不触碰其他 AI2Apps 实例或 HF 缓存。保留工作区中与本任务无关的现有修改，每个阶段完成后给出测试结果和剩余风险。

建议每个 Phase 单独形成可审查提交或至少单独的变更清单，不要一次性重写 Catalog、选择器和运行器。Phase 1 的兼容性验证通过前，不应开始页面 CRUD。

## 17. 实施前需要确认的少量产品决策

本文给出以下默认选择，若没有新的产品意见，实施项目可直接采用：

- 存储格式：一对象一 YAML 文件。
- 删除策略：默认归档，不提供硬删除按钮。
- Group 层级：v1 只支持一级 Group。
- 按需默认状态：永不默认选中。
- 页面可编辑执行器：优先支持结构化 `codex-ui` 和已注册 builtin recipe；任意 command 编辑延期。
- 官方/生成内容：生成内容只读，官方内容优先复制后定制。
- 运行一致性：Run 创建时固化完整 Manifest。

这些默认值优先保证无人值守测试的可预测性、安全性和长期可维护性。
