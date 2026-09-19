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

## 期待结果

点击 Pipeline 内的 Case 标题可打开共享内容编辑表单，编辑显示名称、说明、操作步骤、预期结果和清理动作。点击“保存共享 Case”立即保存，不需要再保存 Pipeline；所属 Group 和所有 Pipeline 中同 ID 的 Case 引用统一读取更新后的内容。用户自建 Case 直接更新 Catalog 原文件；自动生成及内置 Case 的内容修改按 ID 保存到 `catalog/case-content/`，由 Catalog 统一加载，不是步骤级副本。ID、Group、执行器、能力依赖等结构字段不可编辑，服务端也拒绝修改。Pipeline 仅保存 Case 引用、顺序及本步骤的结果策略，不允许 `caseContent` 覆盖。已有 Run 的不可变快照和结果保持不变；历史结果会标识内容变化，不能作为修改后的验收证据。

编辑页从持久化 Run 中读取最近一次已结束的运行，显示总体结论、Run ID、时间和每个步骤的状态、实际结果及摘要；重启工具后仍可查看。步骤通过稳定 ID 匹配，重复 Case 各自独立。步骤顺序、期待结果或 Case revision 改变时提示重新验证；新加入的步骤显示未执行。

Case 的结果选项另外支持 `stop when failed`（存储值 `stop-when-failed`）和 `stop when succeed`（`stop-when-succeed`）。实际结果分别为 `failed` / `passed` 时，立即结束当前 Pipeline，后续 Case 和动作统一标记为 `skipped`，原因是 `pipeline-stop`；未命中则继续。`blocked` 不触发这两种策略。触发步骤保留实际结果，常规账号释放和报告生成仍会执行。按策略跳过的步骤不导致 BLOCKED；实际失败仍导致 FAIL。停止原因同时写入状态页、报告和 timeline。

Codex 和确定性执行器始终提交实际观察状态。Harness 再与步骤的 `expectedStatus` 比较：

- 实际与期待相同：Pipeline 步骤判定为通过，同时保存 `observedStatus` 与 `expectedStatus`。
- 期待 `failed` 或 `blocked`，但实际不是该状态：步骤判定为失败。
- 期待 `passed`：沿用普通 Case 的通过、失败或阻断语义。

因此“期待失败”表达的是一个明确的负向场景合同，不允许 Codex 为了让 Pipeline 通过而把实际失败改写成通过，也不允许弱化原 Case 的断言。

## 动作合同与安全边界

所有动作只能面向固定 Test 身份 `com.ai2apps.desktop.test` / instance `test`：

- `restart-app`：退出并重新启动 Test Shell，保留 Local 与数据。
- `restart-local`：通过 Test Helper 的认证控制通道重启 Test Local，并等待新的 Local PID/Origin 就绪。
- `quit-all-relaunch`：只退出 Test Shell、Launcher、Helper 与 Local，再从固定 Test App 路径启动。
- `reset-data`：复用 Helper “重置数据…”的 `InstanceDataReset`，绝不由 Harness 自行删除 UserData；随后重新启动，并在已有账号租约时恢复 Harness 管理的登录 Session。

动作不接受自定义 bundle ID、instance ID、App 路径或删除路径。不得接触 `default`、`dev`、`app-dev` 或共享 Hugging Face 缓存。动作失败会记录为当前步骤 `blocked`，并保留在 Run 报告中。

## CLI 与恢复

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
