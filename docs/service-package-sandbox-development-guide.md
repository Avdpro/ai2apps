# AI2Apps Service/Package 运行模式与 Sandbox 开发指南

状态：当前实现说明（macOS `sandbox-exec` / Linux `bubblewrap`）
受众：Service Package、Model Worker Package 和本地模型开发者

本文是开发期的操作入口。安全目标和未来 XPC/App Sandbox 设计见
[Package Runtime Isolation on macOS v1](ai2apps-package-runtime-isolation-macos-v1.md)，
Model Worker 协议和 Adapter API 见
[Model Worker Package 开发手册](model-worker-package-manual.md)。

## 1. 最重要的规则

> 是否进入 Sandbox 由 **runtime 运行方式** 决定，不由 Package 的来源决定。

从 Discover 下载、从本地文件安装、由 AI2Apps 发布者签名、第三方签名或开发模式
接受的 Package，只要是非 built-in 且由 AI2Apps 以 `process`/
`managed_process` 启动，就使用相同的 Managed Service Sandbox。

签名只证明发布者和字节完整性，不会把 Package 变成 built-in，也不会放宽运行权限。
当前产品不允许可安装 Package 使用 `in_process`。

## 2. 运行模式对照表

| 开发/运行方式 | AI2Apps 是否启动进程 | Managed Service Sandbox | 适用场景 |
|---|---:|---:|---|
| Built-in Service | 由 Host 内部管理 | 否；属于受信任 Host 代码 | 随 AI2Apps App 构建、不能通过 Package 替换的系统能力 |
| `runtime.mode: process`（内部名 `managed_process`） | 是 | 是 | 可安装 Service Package；`process` 是 manifest 别名 |
| Model Worker `ai2apps-model-worker/v1` | 是，启动命令完全由系统生成 | 是 | 新的本地模型 Package；推荐方式 |
| `runtime.mode: external` | 否；AI2Apps 只检查固定 loopback endpoint | 否 | 开发者自己启动、调试或由其他系统托管的本机 Service |
| Model Worker `harness` | 由开发者命令启动 | **否** | 快速验证导入、生命周期和协议；不代表安装后的 Sandbox |
| 终端直接运行任意 Service | 否 | 否 | 单元调试；不代表 Package 安装后的权限 |

`embedded` 是 `in_process` 的旧别名，安装时同样会被拒绝。外部 Service endpoint
必须是带显式端口的 `http://127.0.0.1`、`http://localhost` 或 `http://[::1]`；
不能指向远端地址。

## 3. 当前 Managed Service Sandbox

### 3.1 文件系统

Managed Service 应只依赖以下根目录：

| 路径/资源 | 权限 | 获取方式 |
|---|---:|---|
| Package payload | 只读 | `AI2APPS_PACKAGE_ROOT` 或 `{package}` |
| Package 私有持久数据 | 读写 | `AI2APPS_DATA_ROOT`、`HOME` 或 `{data}` |
| Package 私有临时目录 | 读写 | `TMPDIR` 或 `{temporary}` |
| 系统/AI2Apps Python runtime | 只读 | 由 Host 授权；不是稳定的 Package API |
| 指定的模型 checkpoint/repository cache | 只读 | 仅在 manifest 授权并由 Host 解析后 |
| 其他 Package、Host 数据库、用户目录 | 无 | 不得探测或依赖 |

Package 安装目录不可写。配置、编译产物、数据库、下载内容和运行缓存必须写入
`AI2APPS_DATA_ROOT`；临时文件写入 `TMPDIR`。不要使用源码相对路径写文件，也不要
假设 `~` 是用户真实 Home——Managed Service 中 `HOME` 被重定向到 Package 私有数据目录。

Model Worker 只能读取 Host 分配给其模型的固定 Hugging Face repository cache 根，
不能枚举整个共享 HF cache，也不能把 manifest 中的任意绝对路径变成权限。普通
Managed Service 只有声明 `model_weights.huggingface_cache: read` 后，才会获得当前
实现中的只读 HF hub cache，并通过 `AI2APPS_HF_CACHE_ROOT` 得到路径。新模型 Package
应优先使用 Model Worker 的 `context.checkpoint_for()`，而不是依赖整个 cache。

### 3.2 环境变量和依赖

Host 会创建最小环境；开发者 shell 中的环境变量通常不会继承。当前稳定可用的变量：

- `PATH`
- `HOME`
- `TMPDIR`
- `AI2APPS_SERVICE_ID`
- `AI2APPS_SERVICE_PORT`
- `AI2APPS_PACKAGE_ROOT`
- `AI2APPS_DATA_ROOT`
- 普通 Managed Service 获准读取 HF cache 时的 `AI2APPS_HF_CACHE_ROOT`

Model Worker 的内部令牌和受信任 framework 路径属于系统私有协议，Package 不得读取、
记录或依赖其格式。不要依赖 `PYTHONPATH`、当前登录 shell、Conda、Homebrew 环境变量、
用户 Home 中的 site-packages，或开发机上“碰巧可 import”的模块。

普通 Service 必须把自己的依赖放入 Package/所选 variant，或只使用正式声明为
AI2Apps runtime API 的模块。Model Worker 可使用系统提供的 Worker framework；模型
专属代码和依赖仍应随 Package 提供。入口使用 `{python}`，不要硬编码开发机解释器路径。

### 3.3 网络和端口

`permissions.network.outbound: false` 是推荐默认值：

- Service 仍可在 Host 分配的 loopback 端口监听并接受 Host 请求；
- 不能访问 Internet、局域网或任意 localhost 服务；
- 大模型下载应由可信 Host 根据固定 repository/revision 完成。

`permissions.network.outbound: true` 在当前过渡实现中是较粗粒度的出站网络授权，
不是域名 allowlist。只有确有必要并说明 reason 时才启用；未来会迁移到 Host Broker
的按 origin 授权。

Service 必须监听 `127.0.0.1` 和 `AI2APPS_SERVICE_PORT`/`{port}`，不要扫描端口、
绑定公网接口或把内部端口作为持久配置。endpoint 也必须保持 loopback HTTP。

### 3.4 Metal、进程和资源

模型需要 Metal 时必须显式声明：

```yaml
permissions:
  accelerator:
    metal: true
    reason: Run this model on Apple GPU.
```

不要假设任意 IOKit/Mach service 都可访问。当前过渡 Sandbox 允许受限进程操作，但
Package 不应依赖任意 subprocess tree、调试器或系统 daemon；这些不是稳定能力，未来
XPC Runner 会进一步收紧。Managed Service 还受到 CPU 时间和文件描述符上限约束。

## 4. Manifest 示例

### 4.1 普通 Managed Service

```yaml
runtime:
  mode: process
  protocol: http-json
  command:
    - "{python}"
    - "{package}/src/server.py"
    - "--host"
    - "127.0.0.1"
    - "--port"
    - "{port}"
  endpoint: "http://127.0.0.1:{port}"

permissions:
  network:
    outbound: false
```

可在 `runtime.command` 中使用：`{python}`、`{package}`、`{data}`、
`{temporary}`、`{port}`、`{variant}` 和 `{variant_root}`。可执行文件相对路径不得
逃出 Package 根目录。

### 4.2 Model Worker

```yaml
runtime:
  mode: process
  protocol: ai2apps-model-worker/v1
  adapter: src/adapter.py:create_adapter
```

Model Worker 禁止声明 `runtime.command`。Python、端口、内部认证、健康检查和路由都由
Host 管理。权重、权限和 Adapter API 请按 Model Worker 开发手册声明。

### 4.3 External Service

```yaml
runtime:
  mode: external
  protocol: http-json
  endpoint: "http://127.0.0.1:9100"
```

AI2Apps 不会启动、停止或 Sandbox 这个进程，只会检查健康状态并绑定 endpoint。
External 模式适合开发调试和已有本机服务集成，不应用来让从 Discover 安装的可执行
Package 绕过隔离。当前也不能把它当作自动获得 AI2Apps Secret 的通道。

## 5. 推荐开发流程

### 5.1 快速循环：不带 Sandbox

Model Worker 可先运行：

```bash
.venv/bin/python -m ai2apps.model_worker.harness \
  --package /absolute/path/to/my-model \
  --check
```

再用完整 harness 验证 HTTP 协议。普通 Service 可在终端直接启动，或暂时用
`external` 连接固定 loopback 端口。此阶段适合断点、热重载和观察完整 traceback。

**上述方式都不能证明 Package 能在生产 Sandbox 中运行。**

### 5.2 安装等价验收：必须带 Sandbox

在认为开发完成前，必须：

1. 构建真实 `.ai2service` 归档；
2. 通过本地 Package 安装路径装入独立测试实例；
3. 让 AI2Apps 以 `process` 激活，而不是从终端另起同一程序；
4. 验证启动、健康检查、调用、取消、停止、重启、升级和卸载；
5. 在 `network.outbound: false` 下验证不会意外下载；
6. 验证只写 `AI2APPS_DATA_ROOT`/`TMPDIR`，不会读其他 Package 或用户文件；
7. 对模型验证 Metal、checkpoint 授权、内存释放及缺失 checkpoint 的错误；
8. 检查 stdout/stderr，确保不记录 prompt、Secret、内部 token 或用户文件内容。

从 Discover 下载的正式归档和本地安装的同一归档，在 Managed Service 阶段应表现一致。
本地开发 Package 如果安装后成功、从 Discover 安装后失败，应优先调查归档、签名、
variant 或发布元数据差异，而不是假定两者使用不同 Sandbox。

## 6. 常见故障

### `ModuleNotFoundError`

通常表示依赖只存在于开发 shell/Conda/Homebrew，未进入 Package 或正式 runtime layer；
也可能是入口使用隔离 Python 后不再读取 `PYTHONPATH`。不要通过开放用户 site-packages
修复，应把依赖打包或声明为受支持的系统 framework 依赖。

### `PermissionError: Operation not permitted`

先检查访问路径是否位于 Package（只读）、私有 data/tmp（可写）或 Host 授权的精确
checkpoint 根。`Path.resolve()`、扫描用户 Home、跟随越界 symlink 也可能在真正打开
文件前触发拒绝。

### `Managed Service exited before readiness`

这是上层结果，不是根因。查看该 Service 的 stderr 和退出码，常见原因是缺依赖、
写 Package 目录、访问未授权路径、端口未使用 `{port}`、健康路径不匹配或启动超时。

### 禁网后模型尝试下载

Model Worker 不应自行 `snapshot_download()`。在 manifest 中固定 repository commit，
声明只读模型权限，并让 Host 下载/准备；Adapter 从 `checkpoint_for()` 获取路径。

### Harness 成功但安装失败

这是预期可能发生的差异，因为 Harness 不套 Managed Service Sandbox。以本地安装后的
真实激活结果作为发布门槛。

## 7. 当前边界与未来变化

当前 macOS Managed Service 使用 `sandbox-exec`/Seatbelt 作为过渡性 containment；Linux
使用 `bubblewrap`。它们不是 macOS App Sandbox，也不是 Firefox 内容进程 Sandbox。

计划中的签名 XPC Runner/App Sandbox 会提供更强、可发布承诺的边界。Package 应只依赖
本文列出的最小能力，不依赖当前 profile 的偶然宽松行为，这样迁移时通常无需改业务代码。
