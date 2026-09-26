# AI2Apps Test System Project Instructions

本目录是 AI2Apps 自动测试系统的实现边界。

## Scope

- Harness 源码：`src/ai2apps_test/`
- Harness 自测：`tests/`
- 专属文档：`docs/`
- Codex Skill：`.agents/skills/ai2apps-test/`
- Run 产物：`artifacts/runs/`
- Catalog 与测试配置：父仓库 `../tests/ats/`
- 根 CLI 兼容入口：父仓库 `../scripts/ai2apps-test`

除非用户明确要求修复产品可测试性缺口，不修改父仓库中的 AI2Apps 产品、Mini-App、Package、Cloud 或发布代码。

## Cloud change boundary

- Cloud 工程目录可以用于只读诊断、代码追踪和契约核对，但不得从本项目直接修改 Cloud 源码、测试、数据库迁移、配置或部署状态，即使该目录在当前工作区中可写。
- 凡是诊断结论需要 AI2Apps Cloud API、数据模型、认证授权、测试账号或其他服务端行为发生变化，必须在本项目 `docs/` 下编写 Cloud 修改需求文档并交给用户，由用户转交 Cloud 工程实施、测试、部署和升级。
- Cloud 修改需求文档至少说明：问题与影响、为什么需要修改、当前根因和代码证据、所需 API/数据/行为变化、安全与兼容边界、回归测试、部署顺序、验收标准及客户端后续动作。
- 不得用直接编辑 Cloud、直接操作 Cloud 数据库、临时生产热改或绕过正式发布流程来替代需求交接。

## Required workflow

1. 阅读 `README.md`、`docs/current-architecture.md` 和相关计划。
2. 修改前检查父仓库工作树，保留无关改动。
3. 使用 `./bin/ai2apps-test` 作为主 CLI；根 `../scripts/ai2apps-test` 仅用于兼容验收。
4. 运行 `python -m pytest -q` 验证 Harness 改动；真实 UI 测试只有在任务明确要求时才运行。
5. 不把历史 Run 当作当前测试证据。

## Safety

- 只允许 `com.ai2apps.desktop.test` / instance `test`。
- Computer Use 使用 `next` 返回的已校验 `shellAppPath` 完整内层 Shell 路径连接。路径必须位于当前固定 Test App 内且 Bundle ID 为 `com.ai2apps.desktop.test.shell`；禁止归档、显示名称及外层启动器。没有有效路径时阻断。
- Computer Use 超时或歧义时重新读取 next，只重试已校验 shellAppPath；保留调用目标、错误与重试结果，不得切换实例。
- 禁止操作 `default`、`dev` 或 `app-dev` 数据。
- 禁止读取、打印或保存 Broker Credential、临时密码、lease token、Cookie 或 Bearer。
- 验证 Broker Credential 是否已配置或已授权时，必须在宿主机环境（沙箱外）执行 `./bin/ai2apps-test account doctor`。macOS Keychain 对沙箱不可见，因此不得使用沙箱内的 `credentialConfigured` / `credentialAuthorized` 结果判断 Credential 缺失、无效或未授权，也不得据此要求用户重新配置。
- 禁止删除用户 Hugging Face 缓存。
- Case 失败或 blocked 后继续独立 Case；只有 Harness 状态无法持久化等系统错误才能停止整轮。
- 中止是终态，不得把取消后的 Case 改写为通过或失败。
