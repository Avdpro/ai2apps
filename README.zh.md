# AI2Apps

**面向个人 AI 节点的本地优先 AI 应用与 Agent 平台。**

AI2Apps 将本地及已连接的模型运行时组织为可持续运行的 App、Agent 和版本化
Service。它在一个或多个模型后端之上提供服务端 Agent Harness、应用 Shell、工具与
能力网关、软件包信任体系、多用户身份和远程访问。

Apple Silicon 与内嵌的 [oMLX](https://github.com/jundot/omlx) runtime 是第一套
实现。AI2Apps 的平台契约保持硬件中立，使外部 Provider 以及未来的 NVIDIA/CUDA、
AMD/ROCm 节点也可以暴露相同的模型与 Service 能力。

> AI2Apps 与 oMLX 项目及其维护者不存在隶属、合作、赞助、认证或背书关系。
> oMLX 名称仅用于说明内嵌 runtime 的来源，完整归属见 [NOTICE](NOTICE)。

[English](README.md) ·
[平台架构](docs/ai2apps-platform-architecture.md) ·
[后端计划](docs/ai2apps-backend-development-plan.md) ·
[本地 Knowledge/RAG](docs/ai2apps-local-knowledge-rag-architecture.md) ·
[安全基线](docs/security-authority-baseline.md) ·
[发布门槛](docs/release-gate.md)

## 产品模型

AI2Apps 围绕四类产品对象和一层可替换 runtime 构建：

```text
用户 / API 客户端
        ↓
App      交互、UI、实例、Session、文件与 Artifact
        ↓
Agent    目标、指令、模型策略、工具与持久执行
        ↓
Service  稳定、版本化、可审计的能力
        ↓
Runtime  本地 oMLX/Fusion、Cloud、外部或未来联邦 Provider
```

- **App** 持有用户交互与持久应用状态。当前内置 App 包括 Chat、Coder、Account、
  Agents、Models、Trust Center、Terminal、设置、日志和 Benchmark。
- **Agent** 由服务端权威 Harness 执行。Run、Step、状态、交互、审批、Event、重试、
  委派、暂停、恢复、取消与最终输出均可持久化，并支持进程重启后的恢复。
- **Service** 通过稳定身份而不是固定物理 URL，为模型、工具、Workspace、进程、
  Browser、文档、图片、Research、Terminal 和外部能力提供统一调用面。
- **AI 节点** 将 App 与 Session 数据保留在本地，同时支持 Cloud 模型、远程/移动端
  访问、installation 成员体系，并以受控 Service 联邦作为下一层节点协作机制。
- **模型 Runtime** 是可替换后端。Cache-MoE 和 Fusion 是重要的本地推理优化，但
  不是 AI2Apps 的产品边界。

## 已实现的平台能力

当前 Alpha 已包括：

- 基于 SQLite 的 App、AppInstance、Session、Message、AgentRun、Step、Event、
  Workspace、Artifact、Service、Tool、Capability、Package 与身份控制面；
- 支持 Tool 调用、用户交互、能力审批、有界子 Agent、恢复和可重放 Event 的持久异步
  Agent Runtime；
- 面向内嵌 Service、沙箱托管进程和 External Service 的 Service Registry 与 Tool
  Gateway；
- 签名且按内容寻址的 `.ai2service`、`.ai2agent`、`.ai2app` 和本地 `.ai2patch`
  流程，包括验证、生命周期、回滚与 Safe Mode；
- Session 隔离的 Workspace、ResourceHandle、Artifact、文档解析与带来源位置的读取、
  进程资源限制、Secret 注入和审计 Event；
- 作为每用户 singleton App 的 Chat，其每条 thread 都是独立隔离的 Session；
- 面向 Codex、OpenCode 和 Claude CLI 的 Coder Project/Thread，包括源码验证、测试、
  浏览器预览、开发 Bundle、TestFlight 和有界文件编辑器；
- 本地 installation 身份、多成员角色、按用户所有权、Cloud 设备绑定、统一计费身份、
  可撤销本地 Session 和按角色控制的 App 访问；
- Desktop Shell、Mobile-ready App 契约、托管 Remote Access 和 Cloud 模型桥接；
- 由现有 oMLX runtime 提供的 OpenAI 兼容模型 API。

项目仍处于积极开发阶段。节点间 Service 联邦、完整的操作系统级沙箱覆盖、第一类本地
Knowledge/Retrieval Service 以及更多硬件后端仍在推进。设计文档会区分已经实现的行为
和目标架构。

## 本地推理与 Fusion

内嵌 oMLX 后端继续提供模型加载、attention、融合 MoE kernel、连续批处理、分页 KV
cache、音频/VLM、embedding、reranker 和 MCP 集成。AI2Apps 为 DeepSeek V4 Flesh
等超大 MoE 模型增加：

- 可配置的扁平或树形 scope catalog；
- shared-expert scope probe 与每个 scope 独立的静态专家 bank；
- 设备端 Top-K 路由，以及必须显式启用的 exact/有损策略；
- expert-major SSD 存储与 cache-aware fallback；
- Session 安全的 KV/prefix-cache namespace 和自适应 L1 专家驻留；
- 可复现的内存、质量、prefill、decode、miss 与 I/O 发布门槛。

进一步阅读：[Flesh 引擎](docs/deepseek-v4-flesh-engine.md)、
[Fusion 设计](docs/fusion-engine-design.md) 和
[MoE Benchmark](docs/moe-cache-benchmark-2026-08-08.md)。

## 仓库结构

```text
ai2apps/                 平台、App、Agent、Service 与产品代码
  agents/                持久 Agent Runtime 与内置 Agent
  api/                   版本化平台 API
  apps/                  App 定义、访问策略与生命周期
  packages/              签名包信任与 Service 生命周期
  services/              Service Registry、适配器与 Tool Gateway
  storage/               SQLite schema、migration 与 repository
  workspace/ documents/  Session 资源、Artifact 与文档工具
  web/                    Desktop/Mobile Shell 与内置 App UI
apps/omlx-mac/            原生 macOS 应用 Shell
omlx/                     内嵌并经过修改的 oMLX 模型 runtime
  engine/flesh.py         DeepSeek V4 Flesh 请求编排
  cache/                  KV 与路由专家存储
  patches/deepseek_v4/    scope 路由、专家 bank 与 kernel
configs/                  scope catalog 与模型 profile
scripts/                  转换、profile、打包与 benchmark 工具
docs/                     架构、产品契约与实验记录
tests/                    平台、安全、API 与推理测试
```

`omlx` Python namespace 与 `OMLX_*` 变量继续作为内嵌 runtime 的兼容接口。新集成
应使用 `ai2apps` 命令，并在可用时使用 `AI2APPS_*` 配置。运行数据暂时保留在
`~/.omlx`，确保产品迁移不会遗失已有模型和设置。

## 安装

当前内置本地模型后端需要 Apple Silicon Mac、Python 3.11–3.13 及支持 Metal 的
macOS。

```bash
brew install uv
uv sync --dev
source .venv/bin/activate

ai2apps --version
ai2apps info
```

也可以自行创建 Python 3.11–3.13 虚拟环境，然后运行：

```bash
python -m pip install -e '.[dev]'
```

## 启动 AI2Apps

```bash
ai2apps serve --model-dir ~/models --port 8000
```

- App Shell / 管理面板：<http://127.0.0.1:8000/admin/dashboard>
- Chat：<http://127.0.0.1:8000/admin/chat>
- OpenAI Base URL：<http://127.0.0.1:8000/v1>
- Platform API Root：<http://127.0.0.1:8000/v1/platform>
- 对话：`POST /v1/chat/completions`
- 模型列表：`GET /v1/models`

如果配置了 API Key，请通过 Bearer Token 发送。旧的 `omlx` executable 暂时保留为
兼容别名；新文档与集成应统一使用 `ai2apps`。

## DeepSeek V4 Flesh 研究覆盖项

由 AI2Apps 准备的模型会自动使用经过验证的 Scope Pack。手工研究环境可以覆盖专家
存储和 profile：

```bash
export AI2APPS_DEEPSEEK_V4_EXPERT_STORE=/path/to/expert-store
export AI2APPS_DEEPSEEK_V4_SCOPE_PROFILE=/path/to/scope-profile.json
export AI2APPS_DEEPSEEK_V4_SCOPE_NAME=general
export AI2APPS_DEEPSEEK_V4_SCOPE_PROBE_DEPTH=16
export AI2APPS_DEEPSEEK_V4_SCOPE_LOSSY_MODE=exact

ai2apps serve --model-dir /path/to/models
```

有损模式必须显式启用。质量敏感场景使用 `exact`；部署其他策略前，应使用有代表性的
真实 Prompt 完成评估。

## 开发与发布门槛

开发可安装 Service 或模型 Package 前，请先阅读
[Service/Package 运行模式与 Sandbox 开发指南](docs/service-package-sandbox-development-guide.md)；
Model Worker 的协议、Adapter 和 checkpoint 约定见
[Model Worker Package 开发手册](docs/model-worker-package-manual.md)。本地 Harness/终端
运行不代表安装后的 Sandbox 权限，发布前必须用真实 `.ai2service` 安装激活验收。

当前实验分支为 `experiment/moe-cache`。除非 AI2Apps 功能确实需要小而隔离的兼容
Patch，否则应保留 oMLX 现有模型、attention、router、scheduler 和融合 kernel 行为。
平台代码应位于 `ai2apps`，并通过适配器依赖模型 runtime。

```bash
pytest -q
python scripts/bench_scope_once.py --help
python scripts/bench_moe_expert_store.py --help
ai2apps-release-gate --mode preflight --run-tests
```

推理对比必须使用相同 Prompt 与生成 Token，并记录源码 commit、常驻/峰值内存、cold
TPS 和 steady TPS。最初的静态 oracle gate 要求 Top-10 完全一致、运行期零 miss、
常驻内存下降，并至少保留 full-resident steady-state TPS 的 85%。

平台变更还必须保持所有权隔离、Capability 执行、Package 验证、重启恢复、API 兼容和
有界资源行为。

## 来源、许可证和品牌声明

AI2Apps 基于 oMLX commit
[`49ec271`](https://github.com/jundot/omlx/commit/49ec271676ba9c14bbebb75da1912e3fcb5fb0f4)
开发，并保留上游版权与归属信息。AI2Apps 的修改由文件内容和 Git 历史标识。

本项目采用 [Apache License 2.0](LICENSE)：Copyright 2025 oMLX contributors；
Copyright 2026 AI2Apps contributors。Apache-2.0 不授予对上游商品名或标识的广泛
使用权，因此 AI2Apps 不使用 oMLX 名称或 Logo 作为产品标识，也不声称获得 oMLX
项目或维护者的合作、认证或背书。
