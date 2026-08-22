# AI2Apps macOS 客户端瘦身架构与开发计划

状态：Draft v5（Phase A、B 与首轮 C/D 开发实现已落地）
基线版本：AI2Apps `0.1.0` build `2226`（Developer ID 签名并已公证）
适用平台：macOS arm64
相关项目：AI2Apps Local、AI2Apps AceFox Client、AI2Apps Service/Model Package

## 0. 实施状态（2026-08-19）

Phase A“独立 Cloud Base App”已经完成首个可运行版本：

- Core Local 新增 `cloud` Runtime Profile，启动 Server 时不导入 MLX、模型 Engine、
  Cached-MoE 或本地推理 Adapter；
- 新增独立 `framework-control-plane` venvstacks 层，Base App 不再携带
  `framework-mlx-base`；
- Base App 的 Cloud 模型、账户、Package 管理、Helper、Browser Agent、Remote Access
  和 Local 数据库仍由内置控制面提供；
- Checkpoint 下载器与模型 Worker 的所有权已经从 Base App 进程边界移出，后续由
  Runtime Package 和对应 Model Package 接管；
- Release Builder、Runtime Manifest 和成品验证器均已支持并强制校验
  `RUNTIME_PROFILE=cloud`；
- Cloud Base App 的专项测试会在禁止任何 `mlx` 导入的子进程中导入 Server，并验证
  空 Engine Pool 状态。

首个开发成品为 `AI2Apps 0.1.0 build 2228`（ad-hoc 签名，未制作 DMG、未公证）：

| 检查项 | 结果 |
|---|---:|
| Base App 展开体积 | 901 MB |
| 内置 Core Local / Control Plane | 333 MB |
| 其中 Python Runtime | 271 MB |
| 产品源码 | 62 MB |
| `omlx` 控制面源码 | 14 MB |
| MLX Python Package / 原生库 / Kernel | 0 |
| `/health` | healthy |
| `/admin` | HTTP 200 |

与 1.8 GB 基线相比，第一阶段已经减少约 900 MB（约 50%）。当前剩余最大项仍是
Shell 与 Browser Agent 的两份 AceFox 载荷；因此 450–700 MB 的最终目标需要继续完成
第 7 节的共享 AceFox Engine 原型，不能仅靠抽离 MLX 达成。

这个版本是架构切分检查点，不是最终发布版：未安装 `ai2apps/runtime-omlx` 时，本地
模型应显示“缺少 Runtime 依赖”并引导安装，不能回退到 Base App 进程内执行模型。

首轮 Runtime Package 与模型迁移也已完成开发验证：

- 新增标准 Service Package `ai2apps/runtime-omlx@1.0.0`，协议为
  `ai2apps-inference-runtime/v1`，角色为 `inference_provider`；
- Runtime 内含独立 CPython、MLX/oMLX、Model Worker framework 与 Cached-MoE 实现，
  不含 Checkpoint；开发版 `.ai2service` 约 378 MB，安装后的 Runtime 约 1.2 GB；
- Execution Runtime Resolver 会校验 Runtime version、capability、dependency lock、
  descriptor 和不可变路径，并使用 Runtime 自己的 Python/launcher 启动模型 Worker；
- Discover/Registry 安装模型时会先自动解析、下载并安装必需 Runtime，选择满足范围的最高
  已发布版本；同一实例的后续模型复用同一 Runtime；
- Qwen3.8、Qwen3.6、DeepSeek V4 Flash 和 2-bit Package 已迁移到 `0.3.0`，生产
  Python dependencies 不再包含 MLX；
- 已用实际开发 Runtime DMG 完成安装和 Worker 启停冒烟，并通过 119 项 Package、依赖、
  沙箱、Registry 和模型 Adapter 回归测试。

上述 Runtime 成品仅为 ad-hoc 开发验证物。进入 Discover 前仍必须完成 Developer ID
签名、公证与 staple，并用官方 AI2Apps Publisher key 签署外层 `.ai2service`。

## 1. 背景与目标

当前自包含的 AI2Apps macOS App 安装后约为 `1.8 GB`，压缩 DMG 约为
`590 MB`。体积的主要来源不是 AI2Apps 业务逻辑，而是：

1. App 内包含两份完整 AceFox：App Shell 和 Browser Agent 各约 `281 MB`；
2. App 内嵌完整的 Python/MLX 本地推理环境，Local Runtime 约 `1.2 GB`；
3. Runtime 同时包含本地模型、VLM、音频、文档、语法约束、评测等广泛依赖；
4. 发布包还包含与当前平台或生产运行无关的评测数据、测试目录、静态库和
   Intel FRP 二进制。

AI2Apps 的大量用户只使用云模型。如果所有用户都必须下载本地 MLX 推理环境，
会带来以下问题：

- 首次下载与安装成本过高；
- UI、账户、Cloud、Package 管理等普通更新也必须重新分发完整推理 Runtime；
- MLX/oMLX 更新与 App 更新相互绑定；
- 每次更新的下载、签名、公证、验证和回滚成本都过高；
- 本地模型能力不能按需安装。

本方案的目标是：

- 让不使用本地模型的用户只安装轻量基础 App；
- 将本地推理能力改为独立、可更新、可回滚的 Runtime Package；
- 让所有本地模型 Package 显式依赖该 Runtime Package；
- 为未来纯 Python 与 Node.js Service/Agent 提供统一、按需安装的 Runtime Resolver；
- 允许纯 Python/JavaScript 依赖在受控、锁定、可验证的实例私有环境中安装；
- 只保留一份 AceFox 引擎载荷，同时继续维持 Shell 与 Agent 的安全隔离；
- 不降低多实例隔离、Package 完整性校验、浏览器 Profile 隔离和更新安全性；
- 将基础 App 的目标安装体积降低到 `450–700 MB`，目标 DMG 降低到
  `180–300 MB`。

## 2. 当前体积基线

AI2Apps `0.1.0` build `2226` 的主要组成如下：

| 组成 | 当前大小 | 说明 |
|---|---:|---|
| AI2Apps App | 约 1.8 GB | Finder 展开后的安装体积 |
| 压缩 DMG | 约 590 MB | 下载体积 |
| AceFox App Shell | 约 281 MB | 完整 Gecko/AceFox Bundle |
| AceFox Browser Agent | 约 281 MB | 第二份完整 Gecko/AceFox Bundle |
| AI2Apps Local Runtime | 约 1.2 GB | Python、推理依赖与产品源码 |
| Python framework layer | 约 1.0 GB | MLX 及第三方依赖 |
| CPython | 约 41 MB | Python 3.11 Runtime |
| AI2Apps 源码与资源 | 约 48 MB | 其中包含两种架构的 FRP |
| oMLX 源码与资源 | 约 90 MB | 其中评测数据约 63 MB |

Python Runtime 中较大的依赖包括 MLX、llvmlite、SciPy、ONNX Runtime、
xgrammar、Transformers、ModelScope、spaCy、Numba、音频和文档处理组件。

## 3. 总体设计

瘦身后的系统分为四个可独立演进的层：

```text
AI2Apps Base App
  ├── AceFox Shell Role
  ├── AceFox Agent Role
  ├── AI2Apps Core Local / Control Plane
  ├── Helper / Launcher / Updater
  ├── Cloud Model Providers
  └── Package Manager
          │
          ├── cloud-only：不安装任何本地推理 Runtime
          └── Execution Runtime Resolver
                 ├── local inference
                 │      ↓
                 │  oMLX Runtime Package
                 │      ↓
                 │  Instance-private Model Workers
                 │      ↓
                 │  Model Service Packages
                 │      ↓
                 │  Instance-private Checkpoints / Derived Files
                 │      ↑
                 │  Shared Verified Download Cache（可选）
                 └── general Service/Agent
                        ↓
                    Python / Node Runtime Package（按需）
                        ↓
                    Verified Private Dependency Environment
```

独立更新关系：

| 变化类型 | 需要更新的组件 |
|---|---|
| UI、账户、Cloud、Package 管理 | Base App |
| CPython、MLX、oMLX、Cached-MoE、Worker Framework | oMLX Runtime Package |
| 单个模型 Adapter、配置或下载策略 | 对应 Model Package |
| 模型权重 | Checkpoint，不更新 App 或 Package |
| Gecko/AceFox 安全更新 | Base App 中的共享 AceFox Engine |
| Node.js 安全更新 | 独立 Node Runtime Package，不更新 Base App |
| 纯 Python/JavaScript 依赖 | 对应 Package 的锁定私有环境 |

## 4. Base App 的职责边界

基础 App 必须在未安装本地推理 Runtime 时完整支持：

- AceFox App Shell；
- AI2Apps 账户、成员与设备管理；
- Cloud 模型调用；
- App、Agent、Service 和 Package 管理；
- Package 签名、Digest、Publisher 和内容审计；
- Runtime 依赖解析、原生载荷验证和纯语言依赖环境管理；
- Local 数据库、设置、Secrets 与实例身份；
- Helper、托盘菜单、端口配置与 Local 生命周期；
- Remote Access、FRP Device Credential 和配对；
- Browser Agent 管理；
- Upstream/Sharing 模型调用；
- 本地 Runtime 与模型的安装入口和状态展示。

基础 App 不再包含：

- MLX、mlx-lm 和 oMLX 推理实现；
- 模型 Adapter 和 Cached-MoE 实现；
- SciPy、ONNX Runtime、llvmlite、xgrammar、ModelScope；
- VLM、音频、TTS/STT、spaCy 等可选推理依赖；
- 模型评测数据；
- Checkpoint。

Base App 也不固定内置通用 Node.js Runtime。纯 HTML/CSS/浏览器 JavaScript App 直接
在 AceFox 内容进程中运行，不获得 Node API；只有声明本地 Node Service/Agent 的
Package 才按需安装官方 Node Runtime。

Core Local 仍然随 App 安装，但必须成为一个最小“控制面 Runtime”，不能在模块加载或
Server 启动阶段无条件导入 MLX/oMLX。所有本地推理调用都由 Host 解析 Runtime，随后
转发给实例私有、模型私有的 Model Worker。Core Local 不直接导入 Model Adapter，
也不把可安装 Package 代码加载进自己的进程。

## 5. oMLX Runtime Package

### 5.0 当前平台基线

Base App 与本地推理解耦后采用两条独立系统基线：AI2Apps Base App 支持
macOS 15+；当前 oMLX Runtime Package 及依赖它的模型 Package 要求 Apple
Silicon 和 macOS 26.2+。未满足本地推理基线的设备仍可安装并使用 Base App 和
云端模型，但 Discover 会在下载前明确阻止安装不兼容的本地 Runtime/模型。

最低系统版本是签名 Package 契约的一部分：外层 `ai2apps.json` 使用
`compatibility.minimumOsVersion`，内层 `service.yaml` 使用
`compatibility.minimum_os_version`。Cloud 将外层兼容性复制进签名 repository
snapshot，客户端先进行零字节下载预检，下载后再以归档 manifest 重复校验。

### 5.1 Package 身份

第一版建议复用现有 `service` Package 类型，并增加只有官方 Publisher 才能声明的
Runtime Provider 角色，避免同时引入一个全新的顶层 Package 类型：

```text
package.id: ai2apps/runtime-omlx
package.type: service
service.id: ai2apps.runtime.omlx
runtime.role: inference_provider
runtime.protocol: ai2apps-inference-runtime/v1
```

如果后续出现多个 Runtime Provider、跨平台解析或独立权限模型，再将该角色升级为新
Package 类型。第一版 Repository 必须限制只有 AI2Apps 官方 Publisher 可以发布或
更新 `inference_provider`。

它包含：

- 独立 CPython Runtime；
- MLX、mlx-lm、Transformers 与必要依赖；
- oMLX Worker Framework；
- Cached-MoE、量化、模型加载和推理实现；
- Host 控制的 Worker 启动入口；
- Runtime 健康检查、版本和能力查询；
- 与当前架构匹配的签名原生二进制。

它不包含：

- 具体模型 Checkpoint；
- 用户数据；
- AI2Apps Core 数据库；
- Browser Profile；
- Cloud 或设备凭据；
- 任意其他实例的模型目录。

### 5.2 macOS 分发、签名与公证契约

Runtime Package 包含从网络下载并在 App Bundle 外执行的 CPython、Mach-O、MLX、
Metal 和动态库，因此 Publisher 签名与 Package Digest 只是供应链校验的一部分，
不能替代 macOS 代码签名和公证。

正式 Runtime 发布物必须：

- 由 AI2Apps 官方发布者签名，Repository Metadata 固定其版本、Digest 和平台；
- 所有 Mach-O、Python 原生扩展、Framework 和 dylib 使用 AI2Apps Developer ID
  Application 身份签名，具有安全时间戳；
- 所有被同一 Hardened Runtime 进程加载的原生库使用相同 Team ID；
- 以 Apple 支持的容器独立提交公证；网络安装器不能只依赖 Base App 的公证票据；
- 公证成功后对可 staple 的发布载荷执行 staple，并保存 Apple submission ID；
- 安装前验证外层 Digest、逐文件清单、架构、Team ID、Designated Requirement、
  Hardened Runtime 和公证结果；
- 安装后再次验证最终不可变目录中的字节和签名；
- 不复用 AceFox Browser 的 `disable-library-validation` entitlement。Runtime Worker
  如确实需要该例外，必须单独评估、最小化并写入发布门禁。

开发版可使用本地签名或跳过在线公证，但必须明确标记为不可发布；开发模式不得污染
正式 Runtime 的 Active 指针或信任数据库。

### 5.3 Runtime Package 物理格式

Runtime 在产品和依赖系统中仍然是标准 AI2Apps Service Package，不建立平行的商店、
签名或安装系统。macOS 原生载荷作为平台 variant 放入 `.ai2service`：

```text
ai2apps-runtime-omlx-1.0.0.ai2service
├── ai2apps.json
├── service.yaml
├── META/
│   ├── sbom.spdx.json
│   └── runtime-manifest.json
└── variants/
    └── darwin-arm64/
        └── AI2AppsOmlxRuntime.dmg
```

外层 `.ai2service` 使用 AI2Apps Publisher 签名，固定 Package、variant 和内层 DMG
Digest。内层 DMG 及其 Runtime Bundle 使用 Developer ID 签名和 Apple 公证。DMG 在
外层归档中使用 store 模式，避免重复压缩。

第一版不把 CPython、Framework、dylib、软链接和可执行权限作为散装文件交给通用 ZIP
解压器恢复。安装器必须：

1. 验证外层 Publisher、Repository Metadata、Package Digest 和逐文件清单；
2. 根据平台与架构选择固定 variant；
3. 验证内层 DMG Digest、Developer ID、Team ID、公证票据和架构；
4. 只读挂载 DMG，并再次验证内部 Runtime Bundle；
5. 使用保留 Bundle 元数据的系统复制方式安装到新的不可变版本目录；
6. 验证安装后签名、文件清单和 Runtime Descriptor；
7. 自检成功后才原子切换 Active Runtime；
8. 任一步失败时卸载镜像、清理 staging，并保持旧 Active Runtime 不变。

相同容器规则可以复用于未来的 `ai2apps/runtime-node` 和其他包含原生代码的官方
Runtime Package。

### 5.4 Execution Runtime Resolver 与 Model Worker 边界

第一版不让 Runtime Provider 成为加载所有 Model Adapter 的常驻超级进程。继续沿用
当前已经实现的“每个模型一个受控 Worker”边界：

1. Core Local 验证 Model Package、Runtime 依赖和能力；
2. Execution Runtime Resolver 选择一个不可变、已验证的 Runtime 版本；
3. Host 使用该 Runtime 的 Python 和 Worker Framework 生成固定启动命令；
4. Host 为当前 Model Package 创建实例私有 Worker、随机 loopback 端口和短期令牌；
5. Adapter 只在该模型的 Worker 内导入，不进入 Core Local 或 Resolver；
6. Worker 只获得当前 Package、Data、临时目录和精确 Checkpoint 根；
7. Worker 的启动、健康检查、日志、停止和 Sandbox 继续由 Host Supervisor 管理。

Runtime Package 对 Host 暴露的是版本化描述符和能力，而不是任意命令接口：

- `runtime.info`：版本、Python ABI、架构、协议和能力；
- `runtime.resolve`：返回已验证的解释器、Framework 和 Worker Launcher；
- `runtime.self_test`：不依赖真实模型的内置 fixture 自检；
- `runtime.drain`：更新前阻止新 Worker 使用待替换版本；
- `runtime.references`：列出仍使用某版本的 Worker，防止提前删除旧版本。

Model Package 不得自行选择 Python，不得声明任意 `runtime.command`，也不得通过任意
文件路径绕过 Runtime Resolver。Base App 只依赖上述版本化契约，不依赖 Runtime 的
内部 site-packages 布局。

通用 Resolver 只负责版本、能力、平台、架构、信任状态和 Runtime Descriptor 解析。
oMLX 是 `inference_provider` 专用实现；未来 Node/Python 是 `service_runtime` 实现。
Package 类型专属的 Worker 协议仍然分离，不能因为共用 Resolver 而获得彼此权限。

### 5.5 Runtime 版本与更新

Runtime Package 使用独立版本，例如：

```text
AI2Apps App:       0.2.x
oMLX Runtime:      1.x
Model Package:     各自独立版本
Worker Protocol:   ai2apps-model-worker/v1
```

Runtime 更新事务必须执行：

1. 检查所有 Active Model Package 的版本范围和能力要求；
2. 阻止不兼容更新；
3. Drain 当前 Worker；
4. 安装新 Runtime 到不可变版本目录；
5. 验证签名、Digest、文件清单和原生架构；
6. 使用内置小型 fixture 执行不依赖 Checkpoint 的 Runtime 自检；
7. 如果存在兼容的已安装模型，再执行模型 canary 健康检查；
8. 原子切换 Active Runtime；
9. 重启模型 Worker；
10. 任一步失败则回滚到上一版本。

更新后至少保留一个已验证旧版本，直到新的 Runtime 通过稳定观察期。每个 Worker 在
启动时固定 Runtime version/digest；旧版本仍有活动引用时不得删除。Active Runtime
使用原子状态记录切换，不能依赖可被 Package 修改的路径或环境变量。

## 6. Model Package 改造

### 6.1 oMLX Model Package

每个本地模型 Package 只包含：

- 模型和能力元数据；
- Adapter；
- Checkpoint 下载、校验和准备规则；
- Cached-MoE/量化配置；
- Runtime 能力与版本要求；
- 模型级健康检查。

示例：

```yaml
schema: ai2apps.service/v1
id: ai2apps.model.qwen38
version: 0.3.0

requires:
  services:
    - id: ai2apps.runtime.omlx
      version: ">=1.0.0,<2.0.0"
      capabilities:
        - mlx
        - model-worker-v1
        - nvfp4

runtime:
  mode: process
  provider: ai2apps.runtime.omlx
  protocol: ai2apps-model-worker/v1
  adapter: src/worker_adapter.py:create_adapter
```

现有 Package Manager 已具备 Service 依赖、版本/Digest Lock、依赖优先顺序、循环
检测、依赖者保护和回滚基础。需要新增的是 Runtime Provider 角色、官方 Publisher
限制、能力匹配、Runtime Resolver 和自动依赖下载。现有
`process + ai2apps-model-worker/v1` 契约继续兼容。

当用户首次安装本地模型时，Discover 应显示：

- 模型 Package 大小；
- Checkpoint 预计大小；
- 需要额外安装的 oMLX Runtime 大小；
- 安装后的总磁盘占用；
- Runtime 已安装时不重复下载。

当前 Qwen3.8、Qwen3.6、DeepSeek V4 Flash 和 DeepSeek V4 Flash 2-bit Package
发布载荷均为纯 Python/JSON/YAML，不包含 Mach-O、`.so`、`.dylib` 或 wheel。它们的
`pyproject.toml` 当前把 `mlx` 写成 Python dependency；迁移时应改为 Runtime capability，
不能让模型 Package 再通过 pip 安装 MLX。源码开发依赖可放入 dev extra，不进入正式
Package 安装计划。

### 6.2 纯 Python/Node 依赖环境

第三方纯 Python 或纯 JavaScript Package 不需要 Apple Developer ID 签名，但进入
Discover 时仍必须具有 AI2Apps Publisher 签名。其依赖允许由 Host 安装到实例私有、
按 Package lock digest 隔离的环境：

```text
~/Library/Application Support/AI2Apps/instances/<instance>/environments/
  <package-id>/<lock-digest>/
```

依赖解析与下载不能由 Package Worker 自己执行。发布端生成完整锁文件，Host 根据锁
文件下载到验证缓存，安装阶段关闭网络，并在新的 staging 环境中完成安装、扫描和
验收后原子激活。Runtime 目录本身保持不可变，pip/npm 不能写入已签名 Runtime。

Python 安装策略：

- 所有直接和间接依赖使用精确版本及 SHA-256；
- 使用 `--require-hashes`、`--no-index`、`--no-deps` 和 Host 验证缓存；
- 禁止 sdist、editable install、VCS/URL/本地路径依赖和用户 site-packages；
- 禁止在客户端执行 setuptools、CMake、Rust、clang 等本地构建；
- 安装前后扫描 Mach-O、`.so`、`.dylib`、`.framework`、`.bundle` 和可执行文件。

Node 安装策略：

- 使用与 `package.json` 一致的固定 `package-lock.json`；
- 使用 `npm ci --ignore-scripts --omit=dev` 的等价受控流程；
- 禁止 `preinstall/install/postinstall/prepare`、`npx`、Git/URL/本地路径依赖；
- 禁止 `node-gyp`、现场编译、下载预编译 addon 和 `.node` Native Addon；
- 优先要求发布者提交已 bundle 的 `dist/*.mjs`，本地 node_modules 安装作为兼容路径。

如果依赖扫描发现原生代码：

1. 官方 Runtime 已提供相应 capability 时改用 Runtime 能力；
2. 通用原生依赖经审核进入下一版官方 Runtime；
3. 独立第三方原生 Service 使用发布者自己的 Developer ID 签名和公证，并作为独立
   进程通信；
4. 其余情况拒绝正式安装，只允许在隔离的 Developer Mode 中调试。

Node 自身不进入 Base App。未来提供 `ai2apps/runtime-node`，由 AI2Apps Developer ID
签名、公证并按需安装；纯前端 App 永远不因使用浏览器 JavaScript 而获得 Node Runtime
或 Node 系统权限。

## 7. 合并两份 AceFox 的方案

### 7.1 “合并”的准确含义

本方案不把 App Shell 与 Browser Agent 合并成同一个进程或同一个 Profile。

必须继续保持：

- Shell 和 Agent 是不同进程；
- Shell 与每个用户 Agent 使用不同 Profile；
- Agent Profile 继续绑定实例与用户；
- Shell 不开放 Remote Agent；
- Agent 使用独立随机 BiDi 端口和 Bearer Credential；
- Shell/Agent 角色不能由网页内容或普通命令行参数伪造；
- Shell 退出不影响 Local；
- Agent 生命周期仍由 Helper 管理。

需要合并的是磁盘中的只读 Gecko/AceFox 引擎载荷。目前两个 `.app` 分别携带完整
的 `XUL`、`omni.ja`、Framework、Helper 和资源，因此重复约 `281 MB`。

### 7.2 实验候选：共享 Engine + 两个薄角色 Launcher

用于原型验证的候选 Bundle 结构：

```text
AI2Apps.app/
  Contents/
    MacOS/AI2Apps
    Frameworks/
      AceFoxEngine/
        MacOS/
          acefox-bin
          XUL
          *.dylib
        Resources/
          omni.ja
          browser/omni.ja
          ...
        Frameworks/
          ChannelPrefs.framework
    Applications/
      AI2AppsShell.app/
        Contents/MacOS/AI2AppsShellLauncher
        Contents/Info.plist
    Library/LoginItems/AI2AppsHelper.app/
      Contents/Resources/
        AI2AppsAgent.app/
          Contents/MacOS/AI2AppsAgentLauncher
          Contents/Info.plist
```

两个 Launcher 都由 AI2Apps 签名，且分别具有固定 Bundle Identifier 和签名角色：

```text
com.ai2apps.desktop.shell
com.ai2apps.desktop.agent
```

Launcher 负责：

1. 验证自己位于受信任 AI2Apps App 内；
2. 验证共享 Engine 的 Team ID、签名 Identifier 和 CodeDirectory；
3. 从自身签名 Info.plist 读取不可变角色；
4. 生成严格受控的 Gecko 启动参数；
5. 设置 Profile、实例目录和角色 Bootstrap；
6. 启动同一份共享 `acefox-bin`。

不能预先假定 `exec` 后仍保留 Launcher 的 macOS Bundle 身份。原型必须实际验证
`NSBundle.mainBundle`、LaunchServices、Dock、菜单栏、Crash Reporter、Updater 和
Gecko Runtime Directory 的行为，不能只验证浏览器窗口能够打开。

共享 Engine 必须是只读签名资源，不能在首次启动时写入 App Bundle。Gecko 缓存、
Profile、Crash 数据、更新状态和临时文件全部写入实例私有目录。

### 7.3 需要解决的 Gecko 技术问题

Firefox 通常根据可执行文件相对路径寻找 `omni.ja`、`XUL`、Framework 和其他资源。
实施共享 Engine 前必须验证：

- 共享可执行路径下的资源发现是否稳定；
- Helper 子进程是否继承正确的 Runtime Directory；
- plugin-container、GPU Helper、Media Plugin Helper 的相对路径；
- `NSBundle`、Dock、菜单栏和 Crash Reporter 显示名称；
- 多个同时运行进程不会写入共享 Engine；
- Hardened Runtime、JIT 与 Library Validation Entitlement；
- Developer ID 签名的嵌套顺序和最终资源封印；
- DMG 复制到 `/Applications` 后路径仍然正确；
- App 更新后正在运行的旧 Engine 不被原地覆盖。

如果 Gecko 无法可靠从共享目录加载，可采用第二候选：保留一个完整
`AceFoxEngine.app`，Shell/Agent Launcher 都启动它的新进程，并通过由 Helper 签名
验证的一次性启动描述符确定角色。描述符必须绑定实例、用户、Profile、目标角色、
随机 nonce 和短有效期，并通过认证的 Helper IPC 交付。不得使用可由普通网页或
未认证本地进程伪造或重放的裸命令行角色参数。

不推荐使用符号链接或依赖 APFS Clone 作为发布格式：它们在 DMG、Finder 复制、ZIP、
更新器和不同文件系统间的保留行为不够稳定，也会增加 CodeResources 验证复杂度。

### 7.4 浏览器更新事务

AceFox Engine 仍随 Base App 更新。更新器必须：

1. 验证新 App、共享 Engine 和两个 Launcher；
2. 确认 Shell 与 Agent Launcher 都引用新 App 内的 Engine；
3. 请求 Helper Drain Agent；
4. 关闭旧 Shell；
5. 原子替换整个 AI2Apps.app；
6. 运行 `--post-update-health-only`；
7. 验证 Shell 与 Agent 两种角色均可启动；
8. 失败则恢复完整旧 App，而不是单独回滚 Engine。

## 8. 实例隔离、Checkpoint 与下载缓存

### 8.1 Runtime 和 Checkpoint

Runtime Package 默认属于单个 AI2Apps 实例：

```text
~/Library/Application Support/AI2Apps/instances/<instance>/packages/...
```

同一实例内的多个模型 Package 共用该实例的 Runtime Provider。不同实例不通过文件
路径共享 Runtime、Adapter、可写 Checkpoint 或派生模型文件。

如果其他实例需要模型能力，优先通过已定义的 Sharing/Upstream 网络接口调用模型主机
实例。确有需要时，另一个实例可独立安装自己的 Runtime 和模型，以磁盘空间换取隔离。

Cached-MoE、格式转换、量化、索引、编译缓存和其他会修改或派生 Checkpoint 的结果
必须写入实例私有目录。任何实例都不能原地修改共享下载缓存。

### 8.2 可选的共享验证下载缓存

允许多个实例复用 Hugging Face 等来源的已验证下载字节，但共享缓存不是某个实例的
活动 Checkpoint，也不授予实例管理其他实例模型的权限。

共享下载缓存必须：

- 按固定 repository、revision 和内容 Digest 寻址；
- 由 Host 下载、校验并原子提交，Model Worker 不自行下载；
- 对 Worker 只开放当前模型精确 repository/snapshot 根的只读访问；
- 不信任文件名、软链接或缓存索引本身，使用清单和 Digest 重新验证；
- 损坏时可删除并重新下载，不作为用户数据或唯一 Checkpoint；
- 激活模型时创建实例私有引用或准备目录；需要修改的文件必须复制到私有目录；
- 第一版可以关闭跨实例共享而不影响 Package/Runtime 协议。

未来若使用 APFS Clone 降低私有 Checkpoint 的物理占用，只能作为本机数据层优化，
不能成为 DMG 发布格式或安全边界；克隆后的可写文件仍属于单个实例。

## 9. 安全要求

Runtime Package 是可执行代码，必须满足：

- 官方 Publisher 签名与固定 Repository Metadata；
- Package Digest 和逐文件哈希验证；
- 独立 Developer ID、Hardened Runtime、Mach-O 架构、时间戳和公证验证；
- 安装到不可变版本目录；
- Active 指针原子切换；
- Runtime 不能访问其他实例目录；
- Worker 只获得当前模型所需的 Checkpoint、Package Data 和临时目录；
- 内部 API 使用短期、随机、仅 loopback 的认证令牌；
- 日志不得包含 Secrets、令牌、Prompt 原文或其他实例路径；
- Package 更新、回滚、启停和失败均写入审计事件；
- Runtime Package 不得替换 Base App、Helper 或 Package Manager；
- Model Package 不得提供任意 `runtime.command` 绕过 Provider。

当前阶段继续采用以下分层边界：

- Base App、Helper、AceFox 和独立 Runtime 载荷使用 Developer ID/Hardened Runtime；
- Firefox 网页内容继续使用 Gecko 内容进程 Sandbox；
- 所有可安装 `process` Service 和 Model Worker 继续使用当前 Managed Service Sandbox
  （macOS Seatbelt/sandbox-exec 过渡实现），不因 Package 来自官方 Publisher 而放宽；
- Package Publisher 签名、Digest、逐文件清单和内容审计构成供应链边界；
- 当前版本不承诺 macOS App Sandbox；未来签名 XPC Runner/App Sandbox 作为独立阶段。

Runtime/Worker Sandbox 的最终 profile 必须以真实 MLX、Metal、Checkpoint 和 Managed
Service 验收结果为准。Runtime 代码所在目录只读，Python bytecode、编译缓存和临时文件
必须重定向到实例私有 Data/TMP；不得在 Runtime Package 内生成 `__pycache__`。

## 10. 体积目标

### 10.1 第一阶段：无风险清理

移除：

- oMLX 评测数据约 63 MB；
- macOS arm64 构建中的 Intel FRP 约 15 MB；
- 第三方 Package 测试目录约 44 MB；
- 不需要的头文件、静态库、构建元数据；
- `.DS_Store` 和其他开发资源。

目标：当前 App 从约 `1.8 GB` 降至 `1.55–1.65 GB`。

### 10.2 第二阶段：Runtime Package 化

从 Base App 移除完整推理 Framework、oMLX 推理源码和模型依赖。

目标：

- Base App：`650–850 MB`；
- Base DMG：`250–350 MB`；
- oMLX Runtime Package：`700 MB–1 GB`，仅本地模型用户下载；
- Model Package：通常为数 MB 到数十 MB，不含 Checkpoint。

### 10.3 第三阶段：共享 AceFox Engine

移除第二份 Gecko/AceFox 载荷，只保留两个薄角色 Launcher。

目标：

- Base App：`450–700 MB`；
- Base DMG：`180–300 MB`。

DMG 的下降比例可能小于安装体积，因为两份相同 AceFox 在压缩镜像中已有较高的重复
压缩收益。

## 11. 开发阶段

### Phase A：建立尺寸门禁

- 增加 Bundle Size Report；
- 分别记录 App、DMG、AceFox Engine、Core Local、Runtime Package；
- CI 对异常增长设置阈值；
- 生成最大的 Package/文件清单；
- 禁止评测数据、测试目录和错误架构二进制进入 Release。

### Phase B：精简 Core Local

状态：已完成。

- 审计 AI2Apps Server 的启动时 import；
- 移除对 MLX/oMLX 的无条件导入；
- 将 venvstacks 明确拆成最小 Control Plane Layer 与独立 Inference Layer；
- 定义通用 `ExecutionRuntimeResolver` 和不可变 `RuntimeDescriptor`；
- 保持当前每模型独立 Worker，不让 Core Local 或 Resolver 导入 Adapter；
- Cloud-only 环境在完全没有 MLX 时通过全部启动和 Cloud Chat 测试；
- CI 增加禁止 Control Plane 导入 MLX/oMLX/模型 Adapter 的 import 门禁；
- 模型列表能表达“需要安装本地 Runtime”。

### Phase C1：Runtime 发布物与信任链

状态：开发实现已完成；正式 Developer ID 签名、公证、staple 和 Discover 发布待执行。

- 复用 `service` Package 类型并增加官方 `inference_provider` 角色；
- 定义 `ai2apps-inference-runtime/v1` 描述符；
- 扩展 `.ai2service` variant，使其可携带 store 模式的已签名公证 Runtime DMG；
- 实现 DMG、内部 Runtime Bundle 和安装后目录的三阶段验证；
- 增加按架构选择发布物；
- 将当前 venvstacks 推理层构建为独立 Package；
- 对 Runtime 所有原生代码执行 Developer ID 签名、公证和发布验证；
- 增加 Runtime 安装前后签名、Team ID、Digest、架构和公证检查；
- Runtime 安装后不修改 Base App Bundle。

### Phase C2：Runtime 生命周期

状态：首个可运行切片已完成（安装、不可变解析、锁定启动和停止）；引用计数、Drain、自动
回滚与旧版本回收仍属后续工作。

- 实现安装、解析、引用计数、健康检查、Drain、更新和回滚；
- 使用内置 fixture 完成无模型 Runtime 自检；
- 由 Host 使用选定 Runtime 启动现有 `ai2apps-model-worker/v1` Worker；
- 保留 Managed Service Sandbox、随机端口和短期内部令牌；
- Active 切换、崩溃恢复和旧版本回收均使用事务状态机。

### Phase D：迁移模型 Package

状态：四个现有模型 Package 的 manifest、Cloud dependency 和 Python 依赖迁移已完成；
尚未发布到正式 Discover。

- Qwen3.8；
- Qwen3.6；
- DeepSeek V4 Flash；
- DeepSeek V4 Flash 2-bit；
- 所有 Model Package 声明 Runtime 版本与能力；
- 安装模型时自动规划 Runtime 依赖；
- 开发阶段现有模型由开发者手动迁移，不实现面向已发布用户的自动迁移；
- 手动迁移不得重新下载已验证 Checkpoint，派生文件仍进入实例私有目录。

### Phase E：受控依赖环境与 Node Runtime

- 实现 Package lock digest、验证下载缓存和实例私有环境；
- Python 只允许完整哈希、无 sdist、无本地构建的受控安装；
- Node 只允许固定 lock、禁用 lifecycle scripts 和无 Native Addon 的受控安装；
- 增加发布时与安装时原生代码双重扫描；
- 在通用 Resolver 上实现可选 `ai2apps/runtime-node`；
- Node Runtime 不作为第一版 oMLX 瘦身发布的阻塞项，但接口必须保持兼容。

### Phase F：共享 AceFox Engine 原型

- 建立共享 Engine Bundle；
- 建立 Shell/Agent 两个薄 Launcher；
- 验证 Gecko 资源定位和所有子进程；
- 保持 Profile、BiDi 和角色隔离；
- 完成 Developer ID 签名、公证和更新回滚测试；
- 原型未通过所有安全与稳定性门禁前，不替换当前双 Bundle 方案。

### Phase G：发布切换

- 发布新的轻量 Base App；
- 首次使用本地模型时提示安装 Runtime；
- 当前产品尚未发布，不提供旧公开版本的自动迁移工具；
- 验证删除开发版 App 内 Runtime 不会影响实例数据、共享下载缓存和私有 Checkpoint；
- 建立 Base App、Runtime Package 和 Model Package 的独立发布节奏。

## 12. 验收标准

### 12.1 Cloud-only

- 没有 MLX、oMLX Runtime Package 和 Checkpoint 时 App 正常启动；
- 登录、Cloud Chat、Apps、Agents、Discover、账户和远程访问正常；
- 不出现本地推理 ImportError；
- Base App 和 DMG 达到阶段尺寸目标。

### 12.2 Runtime 安装

- 第一次安装本地模型会明确显示 Runtime 和 Checkpoint 大小；
- Runtime 只下载一次；
- 第二个模型复用同一 Runtime；
- Runtime 的 Developer ID、Team ID、架构、Digest 和公证验证全部通过；
- 无任何模型时，内置 fixture 自检仍能独立通过；
- Runtime 安装失败不影响 Base App 和 Cloud Chat；
- Runtime 更新失败可自动回滚。

### 12.3 Runtime Package 容器

- `.ai2service` 外层 Publisher 签名、Digest 和文件清单验证通过；
- 只选择与当前 OS/架构匹配的 Runtime DMG variant；
- DMG 和内部 Runtime Bundle 的 Developer ID、公证与 Team ID 验证通过；
- Bundle 权限、Framework、相对链接和签名封印在安装后保持有效；
- staging 失败不会修改 Active Runtime；挂载点和临时文件能够完整清理。

### 12.4 Model Package

- 版本范围、能力和 Digest Lock 正确执行；
- 不兼容模型不能激活；
- Runtime 有依赖模型时不能被卸载或禁用；
- Model Package 更新不要求更新 Base App；
- Checkpoint 不因 Runtime/App 更新而重复下载。
- Adapter 仅在对应的实例私有 Worker 中加载；
- Worker 继续使用 Managed Service Sandbox、随机端口和短期令牌。

### 12.5 纯语言依赖环境

- 纯 Python/JavaScript Package 无需 Developer ID 即可在官方 Runtime 上运行；
- 安装只使用完整锁文件、固定哈希和 Host 验证缓存；
- 安装期间禁网，不执行 sdist、本地编译或 npm lifecycle scripts；
- 发现原生代码时不会进入纯语言环境；
- 环境按实例、Package 和 lock digest 隔离，失败或升级不会破坏旧 Active 环境；
- Package Worker 无法修改官方 Runtime 或其他 Package 的环境。

### 12.6 AceFox

- 磁盘中只有一份完整 Engine 载荷；
- Shell 与 Agent 仍是不同进程、Bundle Role 和 Profile；
- Shell 不能开启 Agent BiDi；
- Agent Bearer Credential、端口和用户绑定保持不变；
- 多用户、多实例和并发 Agent 测试通过；
- `NSBundle`、LaunchServices、Dock、菜单栏、Crash Reporter 和 Gecko Runtime
  Directory 均按目标角色工作；
- 菜单栏名称、Dock、图标、窗口标题和 Crash 信息正确显示 AI2Apps；
- Developer ID、Hardened Runtime、JIT、Library Validation、Notarization 和 Staple
  全部通过。

### 12.7 更新与恢复

- Base App 更新不触碰 Runtime、Model Package 和 Checkpoint；
- Runtime 更新不替换 Base App；
- Model Package 更新不重装 Runtime；
- 活动 Worker 固定 Runtime version/digest，旧版本有引用时不会被删除；
- 每层均具有独立版本、状态、日志、审计和回滚记录；
- 断电、进程崩溃或更新中断后不会出现半激活状态。

## 13. 关键决策

1. Base App 默认以 Cloud-only 能力完整可用；
2. 本地推理是按需安装能力，不再是 Base App 的固定组成；
3. Runtime 复用现有 Service Package 基础，第一版只有官方 Publisher 可发布；
4. Runtime 使用标准 `.ai2service`；macOS variant 内嵌已签名公证的 Runtime DMG；
5. Runtime 原生代码具有独立 Developer ID、公证和安装验证链路；
6. 所有本地模型 Package 依赖官方 Runtime Provider，但 Adapter 仍运行在独立 Worker；
7. 模型 Package 不能通过任意路径或命令绕过 Execution Runtime Resolver；
8. 纯 Python/JavaScript 依赖可进入受控私有环境，不需要 Developer ID；
9. pip/npm 不能直接面向公网解析、运行安装脚本或在客户端构建原生代码；
10. Node Runtime 按需安装，不进入 Cloud-only Base App；
11. Runtime 在实例内共享，不跨实例共享可执行 Runtime 或可写模型文件；
12. Checkpoint 和派生文件保持实例私有，跨实例优先通过网络共享模型能力；
13. 可选共享缓存只复用已验证下载字节，不构成跨实例模型管理或信任关系；
14. AceFox 只尝试合并只读引擎载荷，不合并进程、Profile 或权限边界；
15. 共享 AceFox Engine 是实验候选，通过完整身份、签名、安全和更新验收前不得进入
    正式版本；失败时继续使用当前双 Bundle；
16. 当前产品未发布，现有开发模型只做手动迁移，不为不存在的公开旧版本增加自动迁移。
