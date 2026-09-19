# AI2Apps Test System

这是 AI2Apps 自动测试 Harness、Test Center、Codex Skill、专属自测、文档和新 Run 产物的统一工程目录。

## 快速入口

在本目录运行：

```bash
./bin/ai2apps-test doctor
./bin/ai2apps-test account doctor
./bin/ai2apps-test plan --priority P0
./bin/ai2apps-test select --priority P1
./bin/ai2apps-test --fresh-install
./bin/ai2apps-test run --priority P0 --driver codex --unattended
./bin/ai2apps-test run --priority P0 --fresh-install
./bin/ai2apps-test catalog validate
./bin/ai2apps-test catalog diagnostics
./bin/ai2apps-test pipeline list
./bin/ai2apps-test pipeline run --id <pipeline-id> --driver codex --unattended
```

仓库根目录原命令 `./scripts/ai2apps-test` 仍可使用，它只负责转发到本目录的 CLI。

## 目录

```text
.agents/skills/ai2apps-test/  Codex 自动测试 Skill
bin/                         CLI 主入口
src/ai2apps_test/            Harness 和 Test Center 实现
tests/                       测试系统自身的回归测试
docs/                        测试系统专属文档
artifacts/runs/               新 Run 的状态、日志、证据和报告
```

Catalog 和非秘密测试配置继续由产品仓库根目录的 `tests/ats/` 管理。Test App、产品 manifest、Package 和产品测试仍属于父仓库，不能复制到这里形成第二份事实源。

测试启动后，Test Center 会显示经过限量和脱敏处理的 Codex CLI 实时输出，便于区分正在分析、执行工具、重试与真正停滞。

Test Center 的“管理测试”可以创建、编辑、复制、停用、归档、恢复和试运行自定义 Group/Case。自定义定义以一对象一 YAML 的形式保存在父仓库 `tests/ats/catalog/`；自动生成 Case 的结构只读，可以复制为自定义草稿，也可以在 Pipeline 的共享 Case 表单中修改内容（按 ID 全局保存到 `catalog/case-content/`）。同 ID 的所有 Pipeline 引用共享内容，历史 Run 快照不变。按需 Group 不属于 P0–P3，只有显式选择时才进入 Run。

新建 Case 时先用自然语言描述测试目标，再选择自定义 Group。Test Center 会通过只读、临时的 Codex CLI 调用生成符合固定 Schema 的结构化草稿；草稿不会自动保存、启用或执行，仍需人工检查、校验、查看 Diff、保存和试运行。

隔离试运行无论通过、失败或阻断，结束页都可以让 Codex 复盘执行过程。复盘会把结果分为可自动修订、需要用户补充和非 Case 问题；图片样本通过受管理上传保存到 `tests/ats/fixtures/<case-id>/`。Codex 只生成候选修订和 Diff，不自动保存，也不得通过弱化预期掩盖产品失败。

Test Center 的 **Pipeline** 页面可以把 Case 和 Test-only 生命周期动作编成严格有序的可复用轨迹。添加 Case 时先选 Group、再多选 Case，并可追加或插入；步骤可排序、删除，并可声明期待通过、失败或阻断。支持重启 App、重启 Local、全部退出再启动和通过固定 Helper 重置 Test 数据。Codex 只记录实际结果，由 Harness 对照期待状态判定。

需要在选择页面中模拟首次安装时，可直接运行 `./bin/ai2apps-test --fresh-install`；也可以对 `run`、`select` 或 `plan` 子命令增加该参数。Harness 会通过固定 Test Helper 的认证控制通道调用与托盘“重置数据…”相同的 `InstanceDataReset`，不会自行删除目录；该能力只接受 `com.ai2apps.desktop.test` / instance `test`。

## 文档

- [当前架构与运行机制](docs/current-architecture.md)
- [快速使用](docs/quickstart.md)
- [自动测试总体设计](docs/automated-test-system-v1.md)
- [可编辑 Test Case 开发计划](docs/editable-catalog-development-plan-v1.md)
- [Test Center 界面改造 v1](docs/test-center-ui-renovation-v1.md)
- [Pipeline 机制 v1](docs/pipeline-mechanism-v1.md)
- [Test App 环境](docs/test-app.md)
- [Cloud 测试账号租约要求](docs/cloud-test-account-leases-requirements-v1.md)
- [Cloud 首次登录 Session epoch 同步修复要求](docs/cloud-test-account-session-bootstrap-requirements-v1.md)

## 边界

- 只操作 `com.ai2apps.desktop.test` / instance `test`。
- 不操作 `default`、`dev` 或 `app-dev`。
- 不删除用户 HF 缓存。
- 测试账号 Credential、临时密码和 lease token 不进入代码、命令行、Codex prompt、state、证据或报告。
- 历史 `artifacts/ai2apps-test-runs/` 不迁移；新 Run 只写入本目录。
