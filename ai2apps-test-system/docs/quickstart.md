# AI2Apps Test System Quickstart

The first test-only implementation lives outside AI2Apps product code. It discovers the current system App registry and Package manifests, generates cumulative P0-P3 cases, lets a user select grouped cases, runs deterministic executors, queues Codex UI jobs, and writes JSON, Markdown, HTML, JUnit, and timeline artifacts.

## Commands

From the `ai2apps-test-system/` project root:

```shell
./bin/ai2apps-test doctor
./bin/ai2apps-test account doctor
./bin/ai2apps-test plan --priority P0
./bin/ai2apps-test select --priority P1
./bin/ai2apps-test run --priority P0 --driver codex --unattended
```

UI 用例使用按 Run 临时租用的测试账号池。机器只需配置一次 Cloud 工作负载凭证，凭证通过隐藏输入进入 macOS Keychain：

```shell
./bin/ai2apps-test account configure
```

配置后必须执行 `account doctor`。它会向生产 Broker 发送一个故意无法通过业务校验的请求：HTTP 400 表示 Bearer 已通过授权，HTTP 401 表示 Keychain 有值但凭证不被生产环境接受。该检查不会租用账号、轮换密码或建立设备绑定。只有 `credentialConfigured` 和 `credentialAuthorized` 同时为 `true` 才能开始需要账号的测试。

需要账号的 Run 会自动租用 `test1@ai2apps.com` 至 `test10@ai2apps.com` 中的一个账号，启动固定 Test App，并通过 Test Local 的正式登录接口建立 Session。临时密码和 lease token 不进入 Codex、命令行、state 或报告。完成、失败和中止都会先注销客户端再释放账号；进程崩溃由 Cloud TTL 回收。Cloud 或 Keychain 凭证不可用、账号池耗尽或账号回收失败时，相关用例明确为 BLOCKED。接口契约见 `docs/cloud-test-account-leases-requirements-v1.md`。

Harness 会在 Codex 领取和提交 UI Case 时按需 heartbeat；长时间单 Case 也可以由执行器调用 `./bin/ai2apps-test account heartbeat --run <run-id>`，不会输出 lease capability。

异常退出后可对一个精确 Run 重试回收：

```shell
./bin/ai2apps-test account cleanup --run <run-id>
```

Running `./bin/ai2apps-test` without arguments opens the grouped selector. After **开始测试**, the Harness completes account setup and deterministic cases, then automatically launches a restricted `codex exec` process for queued UI cases. The same page shows Codex process state, the current case, completed/passed/failed/blocked/skipped/remaining counts, group details, report path, and a **中止测试** action. A live Codex CLI panel shows a bounded, redacted stream of recent messages, commands, tool calls, results, failures, and last-activity time. A live problem panel shows each failed or blocked case, its group, summary, available output tail, and evidence paths. Closing the page does not cancel the run.

Use **管理测试** to maintain repository-backed Group/Case YAML files. New definitions begin as drafts, validation shows a Git-style diff, and revision conflicts are rejected rather than overwritten. Generated objects are read-only and can be copied into a user-authored Group. Archiving a Group preserves and archives its child Cases; restore recovers the complete set. A `codex-ui` draft must use structured instructions/expectations/cleanup and pass an isolated trial run before it can be treated as trial-passed.

Catalog commands:

```bash
./bin/ai2apps-test catalog list
./bin/ai2apps-test catalog list --archived
./bin/ai2apps-test catalog validate
./bin/ai2apps-test catalog migrate --check
./bin/ai2apps-test catalog diagnostics
./bin/ai2apps-test catalog review-inventory
./bin/ai2apps-test catalog review-inventory --apply
./bin/ai2apps-test plan --priority P1 --group webagent-corner-cases
./bin/ai2apps-test run --priority P0 --case webagent.corner.drag-image-to-composer
./bin/ai2apps-test pipeline list
./bin/ai2apps-test pipeline plan --id <pipeline-id>
./bin/ai2apps-test pipeline run --id <pipeline-id> --driver codex --unattended
```

`review-inventory --apply` records only component contract digests, never credentials or runtime state. Later diagnostics classify newly discovered components, changed contracts, uncovered components, stale references, and archived content. Plans and reports include the diagnostic snapshot and immutable Case definitions used by that Run.

Test Center 的 **Pipeline** 页面用于编排严格有序的跨生命周期轨迹。添加 Case 时先选择 Group，再一次多选 Case 进行追加或插入；Case 与动作都可排序和删除。Case 步骤可期待 `passed`、`failed` 或 `blocked`，但执行器必须提交实际状态，由 Harness 完成比较。生命周期动作只操作固定 Test 实例，包括重启 App、重启 Local、全部退出再启动，以及复用 Helper “重置数据…”能力。完整合同见 `docs/pipeline-mechanism-v1.md`。

Run `./bin/ai2apps-test --fresh-install` to open the default selector in fresh-install mode, or add `--fresh-install` to `run`, `select`, or `plan` when the scope must start from newly installed Test instance state. The Harness records `testDataMode: fresh-install`, validates the fixed Test bundle and signed reset capability, then asks the authenticated Test Helper to run the same `InstanceDataReset` used by its **重置数据…** menu. It never accepts a custom deletion path and never targets `default`, `dev`, `app-dev`, or the shared Hugging Face cache. A reset failure blocks the selected scope.

If Codex cannot start or exits before all UI cases are recorded, the Run stays resumable instead of being reported as complete. The page displays the instruction “接管并完成 Run `<run-id>`” with a copy button. If account preflight fails, Codex is not launched and the page explicitly labels the failure as an account preflight block.

A normal case failure, timeout, blocked dependency, or executor exception never enables fail-fast behavior. The Harness records that case and continues with independent cases. Only a Harness-level failure such as an unreadable run state or inability to persist results may stop the run.

The stop action is cooperative and fail-closed: the Harness terminates only the exact process group it started, marks the current and remaining cases `skipped`, writes the partial report, and gives the run a `CANCELLED` conclusion. A Codex UI case observes the same cancellation state through the queue.

`run` is non-interactive. With `--driver codex --unattended`, it automatically launches Codex and waits through final reporting. Without `--unattended`, a run that reaches a Codex UI case returns an `awaiting_agent` status and a command for reading the next job:

```shell
./bin/ai2apps-test next --run <run-id>
```

After Codex completes the UI case, save a result inside the run directory:

```json
{
  "status": "passed",
  "summary": "The Test App opened the expected Chat ready view.",
  "evidence": ["screenshots/chat-ready.png"],
  "details": {}
}
```

Record it and continue:

```shell
./bin/ai2apps-test record --run <run-id> --case <case-id> --result <result-json>
./bin/ai2apps-test finalize --run <run-id>
./bin/ai2apps-test report --run <run-id> --open
```

`passed` and `failed` UI results require an existing evidence file within the run directory. Missing UI work becomes BLOCKED during finalization and cannot be reported as PASS.

## First-version boundary

运行页中的证据和报告链接在新标签页打开。Test Center 仅提供当前 Run 的报告和结果中登记的证据文件，结束后继续提供浏览服务，按 Ctrl+C 关闭工具。HTML 报告按 Case 列出证据，使用相对路径，因此也可以从磁盘打开报告并查看同目录下的证据。

Implemented now:

- fixed Test App environment preflight;
- per-Run test-account lease lifecycle and Keychain-only temporary secrets;
- dynamic built-in App, Mini-Entry, Package, and Package Mini-App inventory;
- cumulative P0-P3 common-case generation;
- grouped three-state selector with priority presets and search;
- live in-page progress, current-case and per-group status;
- live failed/blocked case summaries, output tails, and evidence locations;
- per-case executor exception containment with continue-by-default behavior;
- cooperative cancellation of script and Codex UI work with a partial report;
- deterministic Python, JavaScript, JSON, YAML, Swift/Python test and release-bundle executors;
- resumable Codex UI job queue and evidence validation;
- automatic restricted Codex dispatch with visible process state and manual takeover fallback;
- PASS, SCOPED_PASS, FAIL, BLOCKED, and CANCELLED conclusions;
- redacted JSON, Markdown, HTML, JUnit, and timeline artifacts;
- Codex companion skill.

The first version does not yet implement the Phase B Test-only state snapshot/reset control or the Phase C full BiDi/Computer Use scenario library. Those cases are present in the generated P0-P3 plan as agent jobs and are never silently counted as passed.

All state-changing product execution remains restricted to the fixed `com.ai2apps.desktop.test` / `test` identity. The Harness must not target `default`, `dev`, or `app-dev`.
