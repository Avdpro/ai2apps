# AI2Apps Test System

这是 AI2Apps 自动测试 Harness、Test Center、Codex Skill、专属自测、文档和新 Run 产物的统一工程目录。

## 当前 Features

以下为已实现能力（更新于 2026-09-26），不代表所有产品 Case 已通过真实 UI 验收。

- **测试发现与选择**：基于产品注册表与 Package manifest 构建 Inventory，支持累计 P0–P3、按需 Group、单 Case 选择和覆盖诊断。
- **可编辑测试库**：Group/Case 创建、复制、停用、归档、恢复、Diff 校验与隔离试运行；Case 内容按稳定 ID 共享，运行计划保存不可变快照。
- **辅助编写与复盘**：自然语言生成结构化 Case 草稿；对试运行结果提出候选修订，支持受管理素材补充。候选需人工确认，不自动降低预期或改写测试结果。
- **Pipeline 编排**：Case 与动作严格串行，支持排序、插入、另存为、期待结果及条件停止；Case 可选择运行、跳过或人工。
- **组合 Pipeline**：“引入 Pipeline”按引用位置展开多个 Pipeline，支持嵌套和重复引用、独立步骤 ID、来源追踪及快照；拦截循环、缺失和停用引用。共用一个 Run、Test 实例与报告，不隐式重置环境。
- **人工辅助测试**：操作说明、Confirm Start、确认超时跳过、循环提示音和静音；开始后提交 Skip/Pass/Block/Failed，Block/Failed 必须填写原因。
- **Test 生命周期与账号**：启动 Helper、重启 App/Local、全部退出再启动、重置 Test 数据；可不登录、自动分配或指定测试账号。生命周期动作由宿主控制器执行，重启保留阶段日志与 PID 证据。
- **Codex UI 执行**：固定 Test Shell 身份校验，`next`/`record` 顺序屏障，可取消、可接管；实时输出限量脱敏，单 Case 失败或阻断后继续后续步骤。
- **TTS 音频证据**：macOS ScreenCaptureKit 捕获 Test 应用播放音频，使用本地 Qwen3-ASR 离线转写，对照实际朗读文本，保存音频统计、转写及原始证据；HTML 报告支持回放。
- **报告与审计**：JSON、Markdown、HTML、JUnit、timeline、截图和音频证据；保留实际/期待状态、耗时、最近一次 Pipeline 结果及账号收尾状态。

## 使用组合 Pipeline

在 Test Center 的 Pipeline 页面新建总 Pipeline，添加多个“引入 Pipeline”动作，
为每一步选择已经保存且启用的 Pipeline，保存后运行。子 Pipeline 内的重置、登录、
人工步骤仍按原配置执行；一个 Run 不允许隐式切换已租用的账号。
条件停止命中时结束整个组合 Run。当前限制为最多 16 层、展开最多 1000 步。

测试系统后端代码更新后，需重启 Test Center；不必因此重新构建 Test App。

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
- [TTS 捕获与本地 ASR 校验](docs/tts-audio-verification.md)
- [Cloud 测试账号租约要求](docs/cloud-test-account-leases-requirements-v1.md)
- [Cloud 首次登录 Session epoch 同步修复要求](docs/cloud-test-account-session-bootstrap-requirements-v1.md)

## 边界

- 只操作 `com.ai2apps.desktop.test` / instance `test`。
- 不操作 `default`、`dev` 或 `app-dev`。
- 不删除用户 HF 缓存。
- 测试账号 Credential、临时密码和 lease token 不进入代码、命令行、Codex prompt、state、证据或报告。
- 历史 `artifacts/ai2apps-test-runs/` 不迁移；新 Run 只写入本目录。
- 人工确认超时是 skipped，不是 passed；缺证据或未执行不得报告通过。
- 音频转写匹配不证明扬声器实际发声，也不评判音色、自然度或韵律；ASR 不一致需复听，不自动归因 TTS。
- 音频捕获需要 macOS 权限及 Swift 编译环境；ASR 需要本地 Qwen checkpoint 和音频依赖，不自动下载模型或上传音频。
- Run 产物、凭据、个人参考音频和模型权重不作为源码进度上传；Case 素材须另行准备，缺失时阻断。

## 开发与验证

```bash
# 在已配置项目依赖的 Python 环境中运行
python -m pytest -q
node --check src/ai2apps_test/web/test_center.js
./bin/ai2apps-test catalog validate
```

Harness 自测验证编排和安全边界；真实 UI、模型推理和 TTS 端到端测试需另行运行，
不能用自测或历史 Run 代替当前产品验收。构建 Dev/App-Dev/Test 的产品脚本由父仓库维护。
