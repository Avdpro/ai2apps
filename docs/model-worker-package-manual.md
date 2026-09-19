# AI2Apps Model Worker Package 开发手册（协议 v1）

状态：可开发、安装和测试；协议标识 `ai2apps-model-worker/v1`。

如果模型能力需要由 Chat、Read Aloud、Video Studio 或第三方 App 按设备和用户操作进行
配置，还必须阅读
[AI2Apps Capability Provisioning Framework（ACPF）v1](ai2apps-capability-provisioning-framework-v1.md)。
App 推荐栈属于 ACPF，Package 的真实依赖和 checkpoint 声明仍以本文为准。

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

### Discover 模型分类元数据

新的模型 Package 必须在签名外层 `ai2apps.json` 声明 Discover 分类。该字段是目录事实，
会和 Package manifest 一起进入 Publisher 签名，不能只在 Cloud 管理后台填写：

```json
"discovery": {
  "kind": "model",
  "categories": ["multimodal"],
  "tasks": ["multimodal-conversation", "image-understanding"]
},
"modelProfile": {
  "sizeBytes": 12884901888,
  "minimumMemoryBytes": 17179869184,
  "scores": {
    "speed": 4,
    "capability": 4
  },
  "benchmark": {
    "label": "Publisher benchmark 2026-09",
    "device": "Apple M4 Max 64 GB"
  }
},
"modelInstall": {
  "serviceKey": "com.example.qwen",
  "models": [{
    "id": "com.example.qwen/qwen-local",
    "label": "Qwen Local",
    "recommended": true
  }]
}
```

`categories` 至少一个、不可重复，只能使用：`text`、`speech`、`multimodal`、`image`、
`video`、`embedding`。一个模型确实跨域时可以声明多个分类，但不要仅因底层包含文本编码器
就把绘图模型同时标成文本模型。`tasks` 至少一个、不可重复，使用最长 64 字符的
lower-kebab-case 稳定标识，例如 `text-generation`、`speech-recognition`、
`speech-synthesis`、`image-generation`、`image-edit`、`video-generation` 或
`text-embedding`。

`modelProfile` 是模型卡片的签名规格与评分资料，也必须随 `ai2apps.json` 一起签名：

- `sizeBytes`：固定 checkpoint 的预计完整下载字节数；不得填写 Package ZIP 大小。
- `minimumMemoryBytes`：能够完成该模型主要任务的最低 RAM/统一内存字节数。
- `scores.speed`、`scores.capability`：同一主要模态内的 1–5 整数相对等级，不是跨模态的
  统一排行榜。速度必须以 `benchmark.device` 所列设备为基准。
- `benchmark.label`、`benchmark.device`：非空、最长 120 字符，用于明确评分来源与测试设备。
  Publisher 提供的值在 Discover 标为“Publisher 基准”；平台以后可另行发布独立评测结果，
  不得悄悄覆盖签名值。

`modelInstall` 是 Discover 交给 ACPF 的签名安装索引：`serviceKey` 必须等于 Service
entrypoint 的 `id`；`models` 必须列出 1–32 个真实存在且声明 `weights` 的模型配置，模型
ID 必须以 `<serviceKey>/` 开头，标签最长 160 字符，并且恰好一个配置的 `recommended`
为 `true`。它只公开稳定模型 ID，不复制仓库 URL、revision 或许可条件；ACPF 安装 Package
后仍从已验签的 Service manifest 和 Checkpoint Distribution envelope 获取这些安全字段。
Discover 默认走完整的 Package → Checkpoint → Service 验证流程，详情页的“仅安装 Package”
仅用于高级维护场景。

构建器会检查 Service entrypoint：只要 `service.yaml`/JSON 中包含非空 `models`，新
Package 或现有 Package 的下一版本缺少合法 `discovery` 就会以
`model_discovery_required` 拒绝构建；声明模型分类但缺少 `modelProfile` 会以
`model_profile_required` 拒绝，缺少 `modelInstall` 会以 `model_install_required` 拒绝。
构建器还会逐项核对 `modelInstall` 与 Service entrypoint。已经发布的版本由客户端内置、带
版本上限的旧包对照表补齐分类、模型资料与安装索引，不要求为了目录功能重新构建或发布；
超过对照表版本上限后必须采用正式字段。

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

### Model Package 与 Runtime 的代码边界（强制）

`ai2apps-model-worker/v1` Model Package 是**签名的纯 Python 策略层**，不是第二个推理
Runtime。Package 可以包含 Python Adapter、聊天模板、特殊 token 表、流式文本 codec、
scope/cache/量化配置和其他数据资产；可以导入并调用其必需依赖所提供的 Runtime API。
以下内容必须只由 Runtime Package 提供：

- MLX/oMLX、tokenizer 的原生实现、Metal kernel 和设备执行器；
- `.so`、`.dylib`、`.bundle`、`.node`、`.dll`、`.exe`、`.wasm`、`.a`、`.o`、
  `.metallib`、Framework、C/C++/Objective-C/Swift/Rust/CUDA/Metal 源码以及任何
  Mach-O/ELF/PE 可执行载荷；
- 自建 Worker 可执行程序、端口、认证和 Sandbox 逃逸路径。

Contract v1 构建和验包、旧 Service Archive 验包都会对 Model Worker 执行同一条
fail-closed 规则：即使 `native_artifacts` 已声明，Model Package 仍会以
`model_worker_native_payload_forbidden` 被拒绝。Package 可以调用 Runtime 已验签、已安装
的原生能力，但不能复制、vendoring 或动态下载自己的原生能力。Python 中直接使用
`ctypes`/`cffi` 加载 Package 或任意外部原生文件同样违反本边界。

该规则不追溯要求已发布的纯 Python Package 升版。未声明新扩展的旧 Adapter 继续走 Runtime
默认实现；以后新建或升级的 Model Package 必须遵循这一边界。

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
      reasoning:
        schema: ai2apps.reasoning/v1
        mode: optional
        format: think_tags
        default_enabled: true
```

公开 `id` 必须以 `<service-id>/` 开头。`upstream_id` 是 Worker Adapter 实际收到的 `payload.model`。支持的 `model_type`：

- `llm`、`vlm`
- `image_generation`
- `audio_stt`、`audio_tts`、`audio_processing`
- `audio_detailed_transcription`（字幕/会议转写专用，不参与 Chat STT 选型）
- `video_generation`

### 对话模型的 Reasoning 契约（必选）

新建或升级的 `llm`、`vlm` Package 必须在签名的模型 `metadata.reasoning`
中声明真实思考行为；App、Chat 和 Runtime 禁止按模型名称、family 或一次输出猜测：

- `mode: required`：模型强制思考。Runtime 必须覆盖客户端的 Thinking Off，模板必须在
  assistant generation prompt 中进入 `<think>`；App 应禁用 Off，而不是发送一个不会生效的
  假设置。
- `mode: optional`：模型可开关思考；`default_enabled` 必须表达 Auto 的 Package 默认值，
  显式 On/Off 通过 `chat_template_kwargs.enable_thinking` 传给模板。
- `mode: none`：模型没有思考通道；Runtime 强制关闭，App 隐藏或禁用 Thinking 控件。
- v1 的 `format` 为 `think_tags`。Worker 必须把 `<think>…</think>`，以及强制思考模型可能
  返回的 `reasoning…</think>answer`，拆成协议级 `reasoning_content` 与 `content`；不得依赖
  Chat 前端正则修复，也不得把标签或隐藏推理保存为可见答案。

声明只是语义契约，不会自动修好不兼容的 tokenizer 模板。若上游模板忽略
`enable_thinking`，或像 DeepSeek V4 Flash 的旧默认模板一样在 generation prompt 中错误放置
`</think>`，Package Adapter 必须携带并在引擎加载后安装 Package 自有模板。`required` 模型的
发布测试至少覆盖：Prompt 以 `<think>` 开启、客户端请求 Off 仍保持思考、正常成对标签、缺少
开标签但有 `</think>` 的恢复、流式与非流式结构化分流，以及多轮历史不把隐藏推理混入正文。

尚未升级的旧 Package 可暂时没有该字段，以保持已发布制品兼容；但只要发布新版本，就必须
完成声明与上述测试。Checkpoint 是否相同不构成豁免，因为这是 Package/Runtime 协议行为。

### 模型专属流式输出扩展（Runtime 1.7.7+）

模型的 token 到文本规则（例如是否保留 `<think>`/`</think>`、不完整 UTF-8 后缀、模型
专属特殊 token）属于 Model Package 策略；SSE、`reasoning_content`/`content` 分流、停止、
取消、计量和底层 tokenizer/推理执行仍属于 Runtime。Runtime 公开版本化的纯 Python 接口
`ai2apps.model-stream-codec/v1`：

```python
from ai2apps.model_worker.cache_moe import DeepseekV41ChatAdapter
from omlx.api.stream_codec import MODEL_STREAM_CODEC_API


class MyCodec:
    api_version = MODEL_STREAM_CODEC_API

    def decode_prefix(self, tokenizer, token_ids, *, eos_token_id):
        # 返回截至当前 token 的稳定完整前缀；需要结构化思考时必须保留标签。
        return tokenizer.decode(token_ids, skip_special_tokens=False)

    def append_delta(self, previous, current):
        # 只能返回 append-only 新后缀；解码回退时必须 fail closed，不能重放全文。
        if current.startswith(previous):
            return current, current[len(previous):]
        return previous, ""


class Adapter(DeepseekV41ChatAdapter):
    def create_stream_codec(self, checkpoint, runtime_options=None):
        return MyCodec()


def create_adapter(context):
    return Adapter(context)
```

优先使用 Runtime 提供的 `PrefixTextStreamCodec` 配置默认前缀解码；只有模型确有不同的
tokenizer 行为时才自定义类。Runtime 会校验 `api_version`、`decode_prefix` 和
`append_delta`，未知版本直接拒绝。未覆盖 `create_stream_codec()` 或返回 `None` 时使用
Runtime 默认 codec，因此现有 Package 不需要升级。当前专用 DeepSeek V4.1 引擎已接入该
扩展点；新增专用 Runtime 引擎也必须通过同一 hook 接入，禁止再发明模型私有的未版本化接口。

Package codec 必须是无 I/O 的请求内纯 Python 状态转换，不得访问网络、启动进程、加载
原生库或改写 Runtime 全局状态。发布测试至少覆盖特殊 token 保留、中文/emoji 跨 token
解码、EOS、stop string、解码前缀暂时回退、流式/非流式一致性，以及 reasoning 不进入正文。

`audio_processing` 是稳定的模型类型，具体任务通过签名
`audio_capabilities.processing` 声明。音轨分离模型使用
`processing.separation`，必须分别列出模型真正原生输出的 `native_stems` 与对外
`profiles`；例如四声部模型可以原生声明 `drums/bass/other/vocals`，同时把
`dialogue/background` 声明为 `pipeline` profile，并在 `derivation` 中说明
`dialogue <- vocals`、`background <- mixture_minus_dialogue`。调用方不能根据模型名称
猜测 stem，也不能把 pipeline 派生结果宣传成原生对话分离。

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

`scope_asset` 与 `scope_pack` 是一组强制字段，不能只声明其中之一；两者都必须是
Package 根目录内的相对路径并被 `files` 索引和 Publisher 签名覆盖。`scope_pack`
必须绑定 profile SHA-256、模型 ID 与固定 source revision。发布回归不能只读取 YAML，
必须用解包后的真实 Package 记录调用 `installed_model_preparation_recipes()`，确认 Host
可把两个字段解析为包内文件；否则安装会在 checkpoint 下载前失败。

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
| `audio_detailed_transcription` | `/v1/audio/transcriptions/detailed` |
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

视频等大文件不应先整体读入 Python 内存。Adapter 应写入本次请求独占的
`request.output_root`，然后返回文件 Artifact：

```python
from ai2apps.model_worker import ModelWorkerArtifact

output = request.output_root / "output.mp4"
# 由模型流水线写入 output
return ModelWorkerArtifact(output, media_type="video/mp4", filename="output.mp4")
```

只允许返回 `output_root` 的直接子文件。Runtime 会防符号链接地打开文件并流式传给
Host；调用结束后路径失效。生成期间可通过 `await request.progress(...)` 报告阶段，
Host 的取消信号会取消当前 `invoke`。公共视频 API 是持久化异步任务接口，详见
[本地视频生成 v1 实现与验收](ai2apps-video-generation-v1-implementation.md)。

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
仓库 cache 之外的 snapshot 符号链接。只有配置而缺少 safetensors，或 index 中任一
shard 缺失的 snapshot 会被视为“尚未下载完成”，不会交给 Worker 尝试加载。除根
`config.json/config.yaml` 外，Host 也接受与根 safetensors 同 basename 的明确配对配置，
例如 `htdemucs.safetensors` + `htdemucs_config.json`；不匹配的任意
`*_config.json` 不会放宽完整性判断。

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
