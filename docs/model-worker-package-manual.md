# AI2Apps Model Worker Package 开发手册（协议 v1）

状态：可开发、安装和测试；协议标识 `ai2apps-model-worker/v1`。

开始开发前请先阅读
[Service/Package 运行模式与 Sandbox 开发指南](service-package-sandbox-development-guide.md)。
特别注意：本地 Harness 不进入 Managed Service Sandbox；只有把真实 Package 安装并由
AI2Apps 激活，才是与 Discover 安装一致的运行权限验收。

### 平台和系统版本兼容性

依赖特定系统原生推理能力的 Runtime 或模型 Package，必须在签名的外层
`ai2apps.json` 声明要求，不能只等 Worker 启动后抛出 Python 或 Metal 错误。当前
oMLX 系列统一使用：

```json
"compatibility": {
  "ai2apps": ">=0.1.0 <2.0.0",
  "platforms": ["darwin"],
  "architectures": ["arm64"],
  "minimumOsVersion": "26.2"
}
```

系统版本约束必须只对应一个 `platforms` 项。`minimumOsVersion` 包含边界，
`maximumOsVersionExclusive` 不包含边界。Discover 保留不兼容条目供用户查看，但会
禁用安装；Package Manager 会在下载前和归档验签后各校验一次。Service 还必须在
`service.yaml` 通过 `compatibility.minimum_os_version` 重复声明，使本地导入和已经
下载的旧归档也按同一策略 fail closed。

AI2Apps Base App 仍支持 macOS 15+。macOS 26.2+ 仅是当前本地 oMLX Runtime 及其
模型 Package 的要求；旧系统仍可使用云端模型。

## 1. 设计目标

AI2Apps 的系统 Model Worker Host 负责统一的进程启动、沙箱、内部认证、健康检查、日志、重启、停止和 HTTP 路由。模型 Package 不再自带 FastAPI、Uvicorn 或端口管理代码，只提供：

- `service.yaml` 中的模型目录、权限和兼容性声明；
- 一个 Package 内的 Adapter 工厂；
- 实际模型引擎、checkpoint 解析和输入输出转换逻辑；
- 必要的 scope/cache/量化配置等模型专属资产。

“独立 Worker”指 Package 代码和模型状态不进入 `ai2apps-server` 主进程。v1 使用受系统监管的隔离 Python Worker；未来可在保持 Adapter 语义的基础上换成签名 XPC Worker。

## 2. Package 目录

最小目录如下：

```text
my-model/
├── service.yaml
├── src/
│   ├── adapter.py
│   └── ...                 # 模型专属 Python 模块
├── assets/                 # 可选，小型配置、模板、scope profile
└── META/
    └── sbom.spdx.json      # 构建/发布阶段需要
```

可直接参考 [`examples/model-worker-package`](../examples/model-worker-package)。权重不应放进 Package；声明只读 Hugging Face cache 后复用用户已有 checkpoint。

## 3. `service.yaml`

关键区别是 `runtime`。本地 MLX 模型必须显式选择官方 Runtime Provider：

```yaml
runtime:
  mode: process
  protocol: ai2apps-model-worker/v1
  provider: ai2apps.runtime.omlx
  adapter: src/adapter.py:create_adapter

requires:
  services:
    - id: ai2apps.runtime.omlx
      version: ">=1.0.0,<2.0.0"
      optional: false
      capabilities: [mlx, model-worker-v1]
```

禁止声明 `runtime.command`。Worker 的 Python、启动参数、端口和认证令牌全部由系统控制。`adapter` 必须是 Package 内相对路径和工厂函数，不能使用绝对路径或 `..`。

`runtime.provider` 必须同时出现在必需的 Service 依赖中，不能标记为可选。Host 会先安装并
验证 Runtime，再把所选 Runtime 的 version/digest 写入模型 Package 的 dependency lock；
每次启动 Worker 都从这个不可变 Runtime 读取 CPython、Worker launcher 和 framework，
不会回退到 Base App 的 Python/MLX 环境。`capabilities` 应只声明模型实际需要的能力，例如
VLM/NVFP4 模型可增加 `vlm`、`nvfp4`，Cached-MoE 模型增加 `cached-moe`。

模型 Package 的生产 `pyproject.toml` 不得把 `mlx`、`mlx-lm`、`omlx` 或其他 Runtime
原生库列入 `dependencies`。这些依赖由 Runtime Provider 提供；仅用于源码测试的依赖可放
入不进入发布物的 `dev` extra。权重和转换后的 Checkpoint 同样不属于 Runtime Package。

模型声明示例：

```yaml
models:
  - id: com.example.qwen/qwen-local
    display_name: Qwen Local
    model_type: vlm
    upstream_id: mlx-community/example-checkpoint
    capabilities: [work, conversation, image_recognition]
    context_window: 131072
    weights:
      provider: huggingface
      repo_id: mlx-community/example-checkpoint
      # 必须固定到不可变的 Hugging Face commit digest，不能写 main/tag。
      revision: 0123456789abcdef0123456789abcdef01234567
      preparation:
        recipe: native
    metadata:
      family: qwen
      quantization: 4bit
```

公开 `id` 必须以 `<service-id>/` 开头。`upstream_id` 是 Worker Adapter 实际收到的 `payload.model`。支持的 `model_type`：

- `llm`、`vlm`
- `image_generation`
- `audio_stt`、`audio_tts`、`audio_processing`
- `video_generation`

权限按最小集合声明：

```yaml
permissions:
  network:
    outbound: false
  model_weights:
    huggingface_cache: read
    reason: Reuse a checkpoint already downloaded by the user.
  accelerator:
    metal: true
    reason: Run this MLX model on Apple GPU.
```

模型 Worker 的权重来源必须写在对应模型的 `weights` 中。Host 只接受固定
commit 的 Hugging Face 仓库，并负责下载/准备；Worker 自己不应联网下载，
因此通常仍保持 `network.outbound: false`。Package 不会获得 AI2Apps 主 API
Key、Cloud Key 或其他 Package 的 Secret。

如果用户此前通过 Hugging Face `snapshot_download(local_dir=...)` 下载了同一
仓库的同一固定 commit，Host 可以复用其 local-dir checkout，而不再下载或复制
一份大模型。复用前，Host 必须读取该 checkout 的 Hugging Face tree 元数据，
逐文件核对路径、大小及 Git blob SHA-1/LFS SHA-256；随后只以硬链接把已验证内容
导入系统的标准 Hugging Face cache，并生成标准 snapshot 链接。元数据缺失、
revision 不一致、任一内容校验失败、已有 cache blob 损坏或跨文件系统无法硬链接
时，导入必须失败并回退到正常下载。Package 不能提供或选择任意本地源目录，
Worker 的授权范围也不会扩展到原 local-dir checkout。

## 4. Adapter API

Package 工厂接收只读 `ModelWorkerContext`：

```python
from ai2apps.model_worker import ModelWorkerRequest

def create_adapter(context):
    return MyAdapter(context)
```

Adapter 必须实现：

```python
class MyAdapter:
    async def start(self) -> None:
        # 创建引擎、解析 checkpoint、加载模型
        ...

    async def stop(self) -> None:
        # 停止引擎、释放模型资源
        ...

    async def invoke(self, request: ModelWorkerRequest):
        ...
```

`start` 和 `stop` 可省略；`invoke` 必须存在。工厂和三个方法都允许同步或异步实现，但模型引擎建议使用异步生命周期。

`context` 提供：

- `service_id`
- `package_root`（只读 Package 根目录）
- `data_root`（当前 AI2Apps 实例、当前 Package 独占的可写目录）
- `models`（已经过 Host 验证的模型声明）
- `checkpoints`（Host 解析的 checkpoint；包含模型 ID、固定 revision、准备声明
  及精确只读 snapshot 路径；尚未下载时 `path` 为 `None`）
- `context.checkpoint_for(model_id)`（可用公开 ID 或 `upstream_id` 查询）
- `huggingface_cache_root`（兼容字段；新 Model Worker 不应依赖，也不代表拥有
  整个共享 cache 的访问权）

Worker 只获准读取被分配模型的仓库 cache 根，以支持 Hugging Face snapshot
指向同仓库 `blobs/` 的链接；它不能枚举或读取其他仓库。Package 提交的原始
路径不构成授权，Adapter 必须使用 `checkpoint_for()` 返回的 Host 路径。

需要 Host 转换的 Cached-MoE Package 使用 `recipe: ai2apps/cache-moe/v1`，
并在 `preparation` 内静态声明 `install_id`、`execution_modes`、
`storage_policies`、`conversion`、`memory_tiers` 以及 Package 相对的
`engine.scope_asset`/`engine.scope_pack`。这些字段由 Host 白名单解析，不能
填写 Python callable。Model Config 保存的全量/Cached 模式和内存档位由 Host
在内部认证请求中覆盖传递，外部请求不能自行指定。

不得把全局模型对象放在模块 import 顶层。模型应在 `start()` 或首次调用时加载，并在 `stop()` 中释放。

## 5. 操作与返回值

`request.operation` 取值及入口：

| operation | Host 路径 |
|---|---|
| `chat_completions` | `/v1/chat/completions` |
| `responses` | `/v1/responses` |
| `image_generation` | `/v1/images/generations` |
| `image_edit` | `/v1/images/edits` |
| `audio_transcription` | `/v1/audio/transcriptions` |
| `audio_speech` | `/v1/audio/speech` |
| `audio_process` | `/v1/audio/process` |
| `video_generation` | `/v1/videos/generations` |

普通 JSON 结果直接返回 `dict`。需要统一错误状态时抛出：

```python
from ai2apps.model_worker import ModelWorkerError

raise ModelWorkerError(
    "Checkpoint is not installed",
    code="model_unavailable",
    status_code=503,
)
```

二进制结果使用：

```python
from ai2apps.model_worker import ModelWorkerResponse

return ModelWorkerResponse(png_bytes, media_type="image/png")
```

流式结果使用：

```python
from ai2apps.model_worker import ModelWorkerStream

async def chunks():
    yield b'data: {"...":"..."}\n\n'
    yield b'data: [DONE]\n\n'

return ModelWorkerStream(chunks())
```

对话流必须保持 OpenAI SSE 结构，并以 `data: [DONE]` 结束。客户端断开时 Host 会取消流式响应；Adapter 的异步生成器必须正确响应 `CancelledError`，不要吞掉取消信号。

v1 Host 默认把同一 Worker 的请求串行化。下一个请求会等到当前普通响应完成，或当前流结束/取消后才进入 Adapter，避免多个生成任务同时争用统一内存。Package 不应自行启动绕开此队列的后台生成任务。

## 6. 模型选择与生命周期

AI2Apps 把公开模型 ID 改写成 `upstream_id` 后再交给 Worker。一个 Package 可以声明多个模型；Adapter 可采用：

- 单模型常驻；
- 收到不同 `payload.model` 时卸载并切换；
- 多小模型同时驻留。

模型加载失败应返回结构化错误，不得静默回退到另一个 checkpoint。Package 更新、禁用、系统退出或 Worker 重启时都会调用 `stop()`。Worker 异常退出由系统按 `restart` 策略监管。

## 7. 本地开发测试

本节命令用于快速开发循环，**不提供生产 Sandbox 等价性**。Harness 直接由当前开发
环境启动，因此可能看见开发 shell 的依赖、环境变量和文件。发布前必须按
[安装等价验收](service-package-sandbox-development-guide.md#52-安装等价验收必须带-sandbox)
构建 `.ai2service`，通过本地安装路径激活，并在真实 Managed Service Sandbox 中复测。

先做不启动端口的加载/生命周期检查：

```bash
.venv/bin/python -m ai2apps.model_worker.harness \
  --package /absolute/path/to/my-model \
  --check
```

`--check` 不解析或授权开发机上的真实 checkpoint；它只验证清单、Package
导入和 Adapter 生命周期。完整启动模式才会解析固定 revision，并会拒绝指向
仓库 cache 之外的 snapshot 符号链接。只有 `config.json` 且缺少 safetensors，
或 index 中任一 shard 缺失的 snapshot 会被视为“尚未下载完成”，不会交给
Worker 尝试加载。

再启动完整的系统 Host 协议测试：

```bash
.venv/bin/python -m ai2apps.model_worker.harness \
  --package /absolute/path/to/my-model \
  --port 9100 \
  --token dev-token
```

另一个终端验证：

```bash
curl -H 'Authorization: Bearer dev-token' http://127.0.0.1:9100/health

curl -N -H 'Authorization: Bearer dev-token' \
  -H 'Content-Type: application/json' \
  http://127.0.0.1:9100/v1/chat/completions \
  -d '{"model":"checkpoint-id","messages":[{"role":"user","content":"hi"}],"stream":true}'
```

必须额外验证：

1. 无 Authorization 返回 401；
2. 非流式和流式输出均兼容 OpenAI 客户端；
3. 客户端中断后 GPU 任务停止；
4. 切换模型后旧模型资源释放；
5. `stop()` 后 MLX/GPU 峰值内存回落；
6. 禁网模式下不会意外下载，且不能读取未声明的 Hugging Face 仓库；
7. checkpoint 不存在时错误明确；
8. Package 安装、启用、禁用、重启和升级均正常；
9. Models App 能看到声明的模型；
10. Package 日志不包含 prompt、Secret、认证令牌或用户文件内容。

项目级回归命令：

```bash
.venv/bin/python -m pytest -q \
  tests/test_ai2apps_model_worker.py \
  tests/test_ai2apps_model_providers.py \
  tests/test_ai2apps_packages.py
```

### 7.1 发布归档与签名

可发布的 Model Worker 必须包含 `META/sbom.spdx.json`，并使用 Package
发布者的 Ed25519 密钥生成 `.ai2service`。AI2Apps 自有 Package 可让构建工具
从 Host 的 namespaced macOS Keychain 读取现有发布密钥：

```bash
.venv/bin/python scripts/build_model_provider_package.py \
  /absolute/path/to/model-package \
  --output /absolute/path/to/model.ai2service \
  --keychain-secret '<secret-record-id>' \
  --keychain-namespace '<local-security-instance-id>' \
  --key-id '<publisher-key-id>'
```

该路径只供受信任的发布构建进程使用。私钥只在构建进程内存中加载，不写入
Package、sidecar 或临时 PEM；Package Worker 仍不获得任何 Keychain 或
SecretBackend 权限。构建器会排除 `__pycache__`、`.pyc`、`.pyo` 和 `dist/`
内容，并在写入后重新执行 Package 结构与 canonical digest 检查。发布前还应
使用 sidecar 中的公钥独立验证 `signatures/publisher.sig`，并从最终归档解包后
再次运行 Adapter lifecycle 检查。

## 8. 从自带 HTTP Provider 迁移

旧 Package 中以下代码应删除：

- FastAPI/Uvicorn App 和 `/health`；
- 端口参数、Server 启停和 signal handler；
- OpenAI 路径注册；
- Package 自己实现的认证；
- `runtime.command` 和 `runtime.endpoint`。

保留并迁入 Adapter：

- checkpoint 定位和模型白名单；
- 引擎创建/销毁；
- messages、图片、音频等模型专属预处理；
- sampling 参数转换；
- OpenAI JSON/SSE 输出格式；
- scope/cache/Boost/L1 等模型专属控制。

## 9. v1 边界与后续兼容

v1 已经把 Package 代码、MLX 状态和模型权重移出主 Server，并提供沙箱及短期内部认证。当前仍是 Python Worker + loopback HTTP，不等价于最终的签名 XPC 安全边界。后续替换传输层时，系统将尽量保持 `service.yaml`、`ModelWorkerContext`、`ModelWorkerRequest` 和 Adapter 返回类型兼容。

音频上传、图片编辑等大二进制请求目前仍以 JSON/data URL 为主要交换格式；真正的 multipart/共享内存通道属于协议后续版本。模型 Package 不应依赖 Worker 的实际端口、启动命令或内部令牌格式。
