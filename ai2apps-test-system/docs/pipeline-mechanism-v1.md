# Pipeline 机制 v1

## 目标

Pipeline 是保存在测试 Catalog 中的一条有序、可复用测试轨迹。它把多个 Case 与 Test-only 生命周期动作编排为一个不可变 Run，并保留每一步的实际结果、期待结果、证据和顺序。

Pipeline 适合复现跨重启、跨 Local 生命周期、首次安装和异常恢复场景；它不替代 Case。Case 仍描述一个独立测试合同，Pipeline 只描述这些合同与环境动作如何组合。

## 资产模型

Pipeline 使用一对象一 YAML，存放在父产品仓库：

```text
tests/ats/catalog/pipelines/<pipeline-id>.yaml
```

Schema 位于 `tests/ats/catalog/schemas/pipeline.schema.json`。稳定字段包括：

```yaml
schemaVersion: 1
id: chat-recovery
name: Chat recovery
description: 验证 Chat 在 Local 重启前后的恢复行为
enabled: true
steps:
  - id: step-1
    type: case
    caseId: chat.send-message
    expectedStatus: passed
  - id: step-2
    type: action
    action: restart-local
  - id: step-3
    type: case
    caseId: chat.pending-request
    expectedStatus: failed
```

步骤 ID 在一条 Pipeline 内必须唯一。相同 Case 可以被加入多次；编译 Run 时每一步会得到 `pipeline.<step-id>` 形式的独立 ID，所属 Pipeline 单独记录在不可变 Plan 中，因此不会互相覆盖结果，也不会因两个最长合法 ID 拼接而超过文件名限制。

Pipeline 只能引用当前可运行的 Case。被归档、停用或不可运行的引用会在校验阶段被拒绝，避免运行时静默跳过。

## Test Center 编辑体验

顶部 **Pipeline** 页面提供：

- 新建、编辑、校验、Diff 预览、保存和运行；
- 先选择 Group，再多选其中的 Case，一次追加或插入到当前步骤之前；
- 为每个 Case 选择期待 `passed`、`failed` 或 `blocked`；
- 添加“重启 App”“重启 Local”“全部退出再启动”“重置数据”动作；
- 选中步骤后上移、下移或删除。

运行只接受已经保存且没有未保存修改的 Pipeline。开始后进入统一运行状态页，按轨迹顺序显示 Case/动作、期待状态、实际状态、Codex 输出、问题和报告。

Pipeline 完成、失败或中止后，控制台继续保留。“返回编辑 Pipeline”在账号清理和执行器收尾完成后启用，返回本次 Pipeline 的编辑界面；可以修改、保存并再次运行，无须退出测试工具。收尾期间继续刷新状态，避免过早返回造成两轮 Run 重叠。

## 严格顺序语义

Pipeline 是严格串行屏障，不是普通 Case 集合：

1. Harness 从第一步开始推进。
2. 确定性 Case 和动作在 Harness 内执行。
3. 遇到 `codex-ui` Case 时暂停后续步骤，只暴露这一条 Job。
4. Codex 提交该 Case 的实际结果后，Harness 才继续下一步。
5. 单步失败或阻断不会自动终止 Pipeline；后续步骤仍按定义执行。用户中止则是整条 Run 的终态。

这一规则保证“发送消息 → 重启 Local → 检查恢复”不会被普通执行器提前越过。

UI 结果提交后的生命周期动作只交接为 `waiting_controller`，由宿主 CLI/Test Center
控制器执行，不在 Codex 的沙箱 `record` 子进程里调用 LaunchServices。
`next` 返回该状态时应等待并轮询，不得执行动作或 finalize；控制器完成动作后
才放行下一项。`restart-local` 直接连接现有认证 Test Helper，不调用 `open`；
Helper 不可用时记录 blocked，需要启动时显式添加 `start-helper`。
更新此逻辑后需重启 Test Center 后端，新 Run 生效；不会修改历史结果。

## 期待结果

## 引入其他 Pipeline

在“添加动作”选择“引入 Pipeline”，然后选择已保存且启用的目标 Pipeline。
存储为 `type: action`、`action: include-pipeline`、`pipelineId: <目标 ID>`。
启动时按引用位置递归展开，严格顺序执行；允许重复引用，每次生成独立步骤 ID。
来源 Pipeline、原步骤 ID、完整引用路径和所有定义快照保存在 Run 计划中。
之后修改子 Pipeline 不影响已启动的 Run。禁用引用步骤会跳过它展开的全部步骤。

直接/间接循环、缺失或停用的引用会在保存和运行编译时拒绝；最多嵌套 16 层、
展开 1000 步。引入不是独立子 Run：共用 Test 实例、账号租约、报告和取消状态，
不会隐式清理或重置。子 Pipeline 中显式的重置、启动、人工动作仍按原合同执行；
不同账号的切换仍被禁止。条件停止命中时停止整个组合 Run，而非仅当前子 Pipeline。

## 步骤结果

每个步骤的复选框默认勾选（旧配置缺少 `enabled` 时等同 true）。取消勾选后
保存 `enabled: false`；运行保留该步骤并记录 skipped / step-disabled，耗时零，
不执行动作、不登录、不交给 Codex，也不触发条件停止。此类主动跳过不导致 BLOCKED。
取消勾选启动动作不会隐式启动或恢复登录；后续启用的 Case 仍按自身前置条件执行。

点击 Pipeline 内的 Case 标题可打开共享内容编辑表单，编辑显示名称、说明、操作步骤、预期结果和清理动作。点击“保存共享 Case”立即保存，不需要再保存 Pipeline；所属 Group 和所有 Pipeline 中同 ID 的 Case 引用统一读取更新后的内容。用户自建 Case 直接更新 Catalog 原文件；自动生成及内置 Case 的内容修改按 ID 保存到 `catalog/case-content/`，由 Catalog 统一加载，不是步骤级副本。ID、Group、执行器、能力依赖等结构字段不可编辑，服务端也拒绝修改。Pipeline 仅保存 Case 引用、顺序及本步骤的结果策略，不允许 `caseContent` 覆盖。已有 Run 的不可变快照和结果保持不变；历史结果会标识内容变化，不能作为修改后的验收证据。

编辑页从持久化 Run 中读取最近一次已结束的运行，显示总体结论、Run ID、时间和每个步骤的状态、实际结果及摘要；重启工具后仍可查看。步骤通过稳定 ID 匹配，重复 Case 各自独立。步骤顺序、期待结果或 Case revision 改变时提示重新验证；新加入的步骤显示未执行。

Case 的结果选项另外支持 `stop when failed`（存储值 `stop-when-failed`）和 `stop when succeed`（`stop-when-succeed`）。实际结果分别为 `failed` / `passed` 时，立即结束当前 Pipeline，后续 Case 和动作统一标记为 `skipped`，原因是 `pipeline-stop`；未命中则继续。`blocked` 不触发这两种策略。触发步骤保留实际结果，常规账号释放和报告生成仍会执行。按策略跳过的步骤不导致 BLOCKED；实际失败仍导致 FAIL。停止原因同时写入状态页、报告和 timeline。

Codex 和确定性执行器始终提交实际观察状态。Harness 再与步骤的 `expectedStatus` 比较：

- 实际与期待相同：Pipeline 步骤判定为通过，同时保存 `observedStatus` 与 `expectedStatus`。
- 期待 `failed` 或 `blocked`，但实际不是该状态：步骤判定为失败。
- 期待 `passed`：沿用普通 Case 的通过、失败或阻断语义。

因此“期待失败”表达的是一个明确的负向场景合同，不允许 Codex 为了让 Pipeline 通过而把实际失败改写成通过，也不允许弱化原 Case 的断言。

## 动作合同与安全边界

Pipeline 不再隐式启动或租用账号。需要启动时显式加入 `start-helper` 动作；
`loginMode: none`（默认）只启动，不登录、不退出已有 Session；`auto` 自动分配；
`selected` 配合 `accountEmail: test3@ai2apps.com` 精确选择池内账号。
指定账号忙碌时阻断，不回退。一个 Run 不允许隐式更换已租用账号。
带登录的 start-helper 先完成权限/租约检查及旧身份准备，再由登录流程启动实例；
不得先启动 App 再为登录而退出。登录后复用已存活的 Test Local/Shell，只检查就绪。
若测试开始前已有实例，身份准备仍需正常退出它，不绕过退出确认或强制丢弃状态。
旧 Pipeline 不自动添加启动步骤；环境缺失时 Codex 应记录 blocked，不自行启动或登录。
例外：当前 Case 安装模型或 Runtime 时，Test 界面明确要求的安装收尾重启允许由
Codex 在 UI 中确认，无须额外 Pipeline 动作。重启前后检查 next，记录提示和进度；
重启后丢弃旧 Computer Use 句柄和元素 ID，以 next 新提供的 shellAppPath 重新连接。
核验 Test 身份、Session、安装完成状态后继续同一 Case。取消立即停止；重启失败、
循环或需要重新登录时阻断，不自行登录、强杀进程或清数据，重启成功不能代替安装/对话验收。
登录权限失败归属于启动动作，后续独立步骤继续。macOS 辅助功能权限须由用户授权，
此功能不会自动授权或绕过权限。

登录前先通过原生程序请求 macOS 辅助功能授权并校验权限；未授权时不领取租约、
不重置登录数据。授权后须从原启动入口重试。启动/登录失败后，后续 UI Case
直接记录前置依赖阻断（未执行、耗时零），确定性检查及恢复动作继续；下一次
成功的 start-helper 清除该阻断。权限属于原生登录调用链，不沿用 Codex 的授权。

所有动作只能面向固定 Test 身份 `com.ai2apps.desktop.test` / instance `test`：

- `restart-app`：退出并重新启动 Test Shell，保留 Local 与数据。
- `restart-local`：通过 Test Helper 的认证控制通道重启 Test Local，并等待新的 Local PID/Origin 就绪。
- `quit-all-relaunch`：只退出 Test Shell、Launcher、Helper 与 Local，再从固定 Test App 路径启动。
- `reset-data`：直接启动固定 Test App 内经过身份校验的 Helper，复用其 `InstanceDataReset`，不启动外层 Launcher/Shell。重置后保持停止，由显式 start-helper 步骤启动；已有账号租约时由认证流程启动并恢复 Session。绝不由 Harness 自行删除 UserData。

动作不接受自定义 bundle ID、instance ID、App 路径或删除路径。不得接触 `default`、`dev`、`app-dev` 或共享 Hugging Face 缓存。动作失败会记录为当前步骤 `blocked`，并保留在 Run 报告中。

## CLI 与恢复

从 Helper 等图形入口启动时，Codex Driver 在继承的绝对 PATH 目录之外补查
`~/.local/bin`、`/opt/homebrew/bin`、`/usr/local/bin` 和系统目录，并把同一 PATH
传给 Codex 子进程。Node.js 脚本入口会检查 Node.js 是否存在；不会执行用户
shell 初始化脚本，也不会自动安装 CLI 或改变系统 PATH。
Case 草稿生成、试运行复盘与 UI 执行器共用上述路径发现逻辑；草稿和复盘
子进程仍保留原有环境变量白名单，只替换解析后的 PATH。

```bash
./bin/ai2apps-test pipeline list
./bin/ai2apps-test pipeline plan --id <pipeline-id>
./bin/ai2apps-test pipeline run --id <pipeline-id> --driver codex --unattended
```

`plan` 输出包含 Pipeline revision 和展开后的不可变步骤。UI Job 仍使用统一的 `next` / `record` 协议，因此 Codex Driver 中断后可以按 Run ID 接管，且恢复时不会跳过当前屏障或重复已经完成的动作。

## 验收重点

- Group-first 多选、追加/插入、排序和删除能稳定保存并重开。
- 重复 Case 的结果互不覆盖。
- UI Case 未提交前，后续动作绝不执行。
- 期待失败与实际失败匹配时步骤通过；实际意外通过时步骤失败。
- 重置数据只调用固定 Test Helper 能力。
- Run、报告和状态页同时保留期待与实际状态。
- Pipeline 中止、Codex 退出和动作异常均可追踪，不被误报为通过。
# 用户辅助测试动作

自动 Case 的 `record` 遇到人工步骤时立即返回，状态为 `waiting_human`，不在
Codex 子进程里等待。Test Center 控制器负责人工确认、超时和后续推进；`next`
此时返回 `waiting_human` 而不是 `done`。运行页的 Pipeline 卡片按计划顺序
排列，不再按 Group 重新聚合。普通非 Pipeline 测试仍按 Group 展示。

自动收尾必须检查整个计划的未完成步骤，不能只检查 Codex UI Case。
人工步骤等待确认或执行期间保持 Run 与账号租约；显式 finalize 也不得
把仍未完成的启用人工步骤转成 `case was not executed`。用户提交、确认超时
或中止之后再按正常流程推进和清理。

Case 步骤也可通过 `executionMode: run | skip | manual` 选择执行方式。缺失此字段时，
旧 `enabled: false` 对应跳过，其余对应运行；显式 executionMode 优先。
人工模式仍引用原共享 Case，不修改 Case ID、Group 或内容。运行快照包含其说明、
操作步骤、预期结果、清理和素材，交由现有人工流程执行；默认确认超时 120 秒，
可在卡片修改。结果仍遵循该步骤的预期状态和停止策略。生命周期动作继续使用原勾选框。

`human-test` 是严格顺序屏障，不启动实例，不让 Codex 代操作或代提交。
参数 `humanInstructions` 为操作说明（1–12000 字符），`confirmTimeoutSeconds`
为等待 Confirm Start 的秒数（1–86400，编辑器默认 120）。

到达时 Test Center 滚动并聚焦用户辅助卡片；后端每 3 秒播放 macOS Ping 提醒，
不受网页自动播放策略影响。可静音，系统静音或音量为零时无法保证听见。
未确认而超时记为 skipped；确认后停止提醒并显示 Skip、Pass、Block、Failed。
Block 和 Failed 必须填写原因。确认后的执行无此超时限制，可用中止测试退出。
页面刷新后从后端恢复状态，过期卡片、重复提交、确认前提交结果均被拒绝。
后端记录用户结果、原因、等待和执行耗时及 JSON 证据；不声称这是自动验证的结果。

修改后需要重启 Test Center 后端并刷新页面，无需重建 Test App。
