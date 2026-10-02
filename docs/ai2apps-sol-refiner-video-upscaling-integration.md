# SoL-Refiner：Video App / Mini-App 对接指南

更新：2026-10-02。本文描述已发布的 `ai2apps/model-sol-refiner-mlx@0.1.1` 接口。Runtime 继续使用已发布的 `ai2apps/runtime-omlx@1.8.7`。0.1.1 需要包含本次能力解析及资源调度改动的 Host；Package 已发布，配套 Desktop Host 发布仍待完成。

## 1. 当前可用范围

这是独立的视频 2× 放大能力。模型类型和 Worker operation 均为 `video_upscaling`，不要放入视频生成模型列表。

已完成：Package 和两份权重 Distribution 发布；匿名下载与签名验证；签名安装后两种模型的真实 GPU 推理、音频保留、取消、重启及卸载验收。

当前仓库已有 Host 模型目录识别、调度和 Worker 路由支持。**Video App 的放大任务、Mini-App 的 capability/bridge、ACPF 能力解析和 UI 仍需接入。** `/v1/videos/upscalings` 是内部 Worker 路径，不是已经开放给 Mini-App 的 Host HTTP 路由。旧 Desktop 也需要包含这些 Host 改动的版本，单独安装 Runtime 不会更新 Host。

## 2. 模型选择与安装

| 用途 | 公共 model ID | 下载量 |
| --- | --- | --- |
| 标准放大，默认推荐 | `ai2apps.model.sol-refiner-mlx/ltx23-one-step` | 28,705,240,872 bytes，约 28.71 GB |
| 自定义提示词 | `ai2apps.model.sol-refiner-mlx/ltx23-custom-prompt` | 57,037,306,792 bytes，约 57.04 GB |

二者属于同一个 Package；共享缓存保留时，安装标准版后再安装自定义版只增加约 28.33 GB。下载量不是运行内存需求。平台为 Apple Silicon、macOS >=26.2；Package 声明最低内存 24 GiB。

Host 应从模型目录筛选 `model_type == "video_upscaling"` 且 capabilities 包含 `video_upscaling` 的模型，读取 `video_upscaling_capabilities`。0.1.1 声明 `resolution_policy: resource_limited`、`maximum_output_pixels: null`，表示没有固定像素上限；不要将 null 当成 0，也不要在 UI 回填 512/1024/4K 上限。实际接纳由资源调度决定。公共 ID 用于 Host 调用；`ai2apps-sol-refiner-default/custom` 是内部 upstream ID，由 Host 自动转换。

安装交给现有 Discover / ACPF。接入方需补充放大能力的 provisioning 映射，并提供“安装模型…”入口；取消安装保留之前的选择。LTX/Gemma 许可由安装用户在 ACPF/Discover 确认，Mini-App 不自动确认、不伪造 consent，不直接下载权重。

## 3. 请求与结果

Worker 内部协议：`POST /v1/videos/upscalings`，`multipart/form-data`。

| 字段 | 内容 |
| --- | --- |
| `model` | 所选模型 ID；Host 会转换为 upstream ID |
| `video` | 上传视频文件，媒体类型 `video/*` 或 `application/octet-stream` |
| `parameters` | 可选 JSON 对象；multipart 传输时序列化为 JSON 文本 |

```json
{"scale": 2, "seed": 0}
```

- `scale` 只支持整数 2，默认 2。没有任意目标分辨率或 4× 选项。
- `seed` 为 0..4294967295 的整数，默认 0。
- `prompt` 可选，最长 2048 字符；不传或空白时使用固定默认提示词。
- 标准版通常不要展示提示词输入。自定义版才展示可选提示词；标准版收到不同的提示词会返回 `prompt_configuration_required`，不能静默忽略。
- 不支持 steps、negative_prompt、插帧等未声明参数；UI 不提供这些控制项。

成功返回 **HTTP 200、`video/mp4` 二进制**，附件名 `upscaled.mp4`，不是 JSON URL、base64 或任务 ID。Host 持久化结果后，才返回自己的任务/Artifact 描述。

输出为 H.264 MP4，宽高分别乘 2，帧数保持不变；输入有受支持音轨时直接复用压缩音频。Worker 内部 Artifact metadata 不作为 HTTP JSON 返回；Host 需要显示宽高、帧数、时长时可探测保存后的文件。

## 4. 输入限制与分段

- 恒定帧率（CFR）1–60 fps；VFR 明确拒绝。
- 输入宽、高至少 32 像素，0.1.1 不再设置固定边长/像素上限；输出宽高分别乘 2。无需调用方补齐 32 倍数，Worker 内部补齐并裁回。4K 已做真实运行验证；更大尺寸仍取决于设备内存和编码器能力，不承诺无限分辨率。
- 同时满足最多 1500 帧、最多 60 秒。例如 60 fps 实际最多 25 秒。
- 音频编码支持 AAC、MP3、ALAC、AC3、EAC3；其他音轨需 Host 明确转换，不能静默丢弃声音。
- 视频时间戳缺失、过程中尺寸变化等输入会拒绝。

Package 内部根据补齐后的输入像素选择 41/33/25/17/9 帧窗口；41 帧时重叠 17 帧，17–33 帧时重叠 9 帧，9 帧时重叠 1 帧；使用 1–2 帧融合。窗口步长保持 8 帧对齐，相邻窗口复用对应噪声。**单个视频直接提交，不要在 Mini-App 再切成这些小窗口。** Host 在调度前从实际输入文件探测尺寸和帧数，预留所选窗口的内存；不信任前端提交的尺寸或内存估计。

超过 60 秒或 1500 帧的长视频编排尚未提供。若 Video App 扩展长视频，需要由 Host 设计分段、跨请求重叠合成、音轨和时间戳处理，再做时序质量验收；不能假设多个独立请求拼接后与单次请求完全一致。0.1.1 不应为通过旧的 512 门槛而将输入降采样；源视频按原始尺寸进入放大流程。

### 尺寸验证与版本区别（2026-10-02）

512 是 0.1.0 封装的保守上限，不是模型架构的硬限制。隔离实验仅将输入校验放宽到 1024，使用相同 BF16 权重与 Runtime 1.8.7：

- 9 帧 1024² → 2048²，输出 9 帧，约 20.14 秒。
- 65 帧 1024² → 2048²，输出 65 帧，两个 41 帧窗口，约 168.82 秒；MLX 分配峰值 32,047,088,150 bytes（约 29.85 GiB），不是整个进程的总内存。
- 此为单个人像素材运行探针，不代表普适画质验收或稳定性能基准。原素材缩放后用于尺寸测试。
- 以上 1024 测试是旧 41 帧窗口的隔离探针。0.1.1 已移除固定尺寸上限并新增自适应窗口；1920×1080 的 17 帧输入输出为 3840×2160、17 帧，9 帧窗口/1 帧重叠，103.53 秒，MLX 峰值约 14.07 GiB。该素材是为尺寸测试缩放的输入，不能作为细节恢复质量基准。
- 旧版 0.1.0 仍限制每边 512；0.1.1 已发布，App 必须按已安装版本的能力声明呈现。切勿覆写 0.1.0 的缓存能力来伪装升级。
- 测试记录位于 `ai2apps/.build/sol-refiner/compact-engine-smoke-{9,65}-1024.json`。

## 5. 推荐 Host 调用方式

长任务优先使用现有 `runtime.model_invocations.invoke_background_to_file`。它支持路径上传、输出流落盘、调度、Worker 身份认证、进度和取消，避免前端持有大视频或内部凭据。

以下为 **Host 侧调用示例**。`principal`、Session、App 身份和路径均须由已认证、校验归属后的 Host 上下文提供；并非前端可直接运行的 SDK：

```python
from ai2apps.model_invocation import ModelInvocationContext

model_id = "ai2apps.model.sol-refiner-mlx/ltx23-one-step"
model = runtime.model_invocations.model(model_id)
if (model is None or model.model_type != "video_upscaling"
        or "video_upscaling" not in model.capabilities):
    raise ValueError("请选择已安装的视频放大模型")

context = ModelInvocationContext.from_principal(
    principal,
    session_id=session_id,
    app_instance_id=app_instance_id,
    consumer_app_id=consumer_app_id,
)
await runtime.model_invocations.invoke_background_to_file(
    model_id,
    "video_upscaling",
    {"parameters": {"scale": 2, "seed": 0}},
    output_path,  # Host 分配的持久化任务工作目录下的 Path
    files={"video": ("input.mp4", input_path, "video/mp4")},
    request_id=worker_request_id,  # Host 生成、持久化的唯一 ID
    cancel_requested=cancel_requested,  # 同步 Callable[[], bool]
    progress=record_progress,           # 同步 Callable[[dict], None]
    context=context,
)
# 成功后：探测输出，注册到现有 Studio Artifacts / Preview & Output，
# 再将任务设为成功。失败/取消路径不得发布半成品。
```

该调用等待完成，**不会自动建立持久任务或发布 Studio Artifact**。接入方需用 Video App 现有任务管理器包装，保留任务/Worker request ID 的映射、归属校验、取消状态、失败记录和结果去重。不要让一个页面 HTTP 请求承担整个任务生命周期。

`invoke_background_to_file` 会在内部附带同一个 `x-request-id` 并轮询进度。普通 `invoke_foreground_multipart` 的 `request_id` 当前只用于调度，不能直接假定它也关联 Worker 进度。需要任务管理、取消的场景采用上面的文件后台调用。

## 6. 进度、取消与错误

Worker 内部控制接口（仅 Host 使用）：

- `GET /v1/requests/{request_id}`：查询状态及 progress。
- `DELETE /v1/requests/{request_id}`：请求取消；推理请求取消后返回 HTTP 499。
- Host 包装：`request_progress(model_id, request_id)` 和 `cancel_request(model_id, request_id)`。

进度样例：

```json
{"phase": "upscaling", "current": 24, "total": 65}
```

进度按窗口更新，不是逐帧实时更新；首次模型加载/首窗口推理期间可以暂时没有数值进度。`total` 来自容器帧数与已读帧数，缺少准确帧数时会调整；UI 不承诺 ETA，不将 `current == total` 当作成功，必须等待输出保存成功。取消要等 Host 任务结束确认，不能只关掉页面。

| 错误 | 接入建议 |
| --- | --- |
| `model_not_found` | 重新选择模型/刷新目录 |
| `model_unavailable`、`checkpoint_incomplete` | 引导 Discover/ACPF 安装或修复 |
| `prompt_configuration_required` | 清空提示词或选择自定义提示词版 |
| `invalid_request` | 检查参数类型、scale、seed、prompt |
| `invalid_video` | 展示格式/帧率/尺寸/长度等具体原因 |
| `generation_cancelled` | 任务呈现为已取消，不发布输出 |
| 调度资源不足 | 保持排队/可重试状态，不重复发起同一任务 |

Host 的 `ModelInvocationError` 可包裹 Worker 错误；不要只按 HTTP 状态给出同一个提示。

## 7. Video Mini-App 待接入清单

1. 在现有 capability registry / ACPF 中增加视频放大能力和模型选择规则；语义名称应在 Host 与 Mini-App manifest 之间统一。本文不声称 `video.upscaling` 已经注册。
2. 实现绑定当前 actor、App、Studio、mount 的 Host bridge：模型列表/安装、提交任务、查询/取消/重试。参照现有 Avatar 的任务接入，不暴露 Worker URL、Bearer、checkpoint 或任意原生路径。
3. UI 提供视频选择、预览输入、固定 2×、模型选择、进度及取消。标准版默认无提示词，自定义版可选提示词。
4. 接受已有 Gallery/Studio 视频时，交给 Host 校验素材归属并解析输入；不能信任前端提交的文件路径。
5. 结果只发布到 Host 统一 Studio Artifacts / Preview & Output；Mini-App 保留输入和任务状态，不另建输出播放器/历史/下载流程。结果可按现有机制交给 Composer。
6. App-Shell 开发使用固定 `AI2Apps-app-dev.app` 环境；依照 App Dev 文档选择刷新/重启/重建，不混用 general Dev 状态。

## 8. 对接验收

- 标准模型：不传 prompt，输入 9 帧 128×128 含 AAC 的视频，输出 9 帧 256×256 且含音频。
- 自定义模型：明确选择 custom ID 并传不同提示词；标准模型同样请求应给出安装/切换提示。
- 65 帧视频经过内部多个窗口，输出帧数不增不减；观看窗口连接处。增加 1920×1080 → 3840×2160 横屏、竖屏以及非 32 倍数尺寸验收；验证资源不足会排队/报资源错误，而不是拒绝固定边长。
- 参数非法、VFR、超限、未装权重、许可未确认时有明确提示；不自动代替用户确认。
- 任务等待、运行、取消、失败、重试以及刷新页面后的状态一致；成功结果只进入公共输出一次。
- Mini-App 收不到内部凭据/路径；切换 Mini-App 后输出仍归 Host 管理。

已发布包通过前两类真实推理及取消/重启/卸载验证；Mini-App bridge、端到端任务 UI 验收由本次对接实现补齐。MS 权重采用固定版本文件大小/SHA-256 元数据验证，完整 MS 回读按发布授权延期；不要将其描述为已完成全量双源下载验收。

## 9. 代码与文档入口

- [Package README](../packages/ai2apps-model-sol-refiner-mlx/README.md)、[签名能力声明源](../packages/ai2apps-model-sol-refiner-mlx/service.yaml)
- [Worker adapter](../packages/ai2apps-model-sol-refiner-mlx/src/worker_adapter.py)、[分段引擎](../packages/ai2apps-model-sol-refiner-mlx/src/upscale_engine.py)
- [Host 模型调用](../ai2apps/model_invocation.py)、[模型目录/调度代理](../ai2apps/model_providers.py)
- [Studio Mini-App 契约](ai2apps-studio-mini-app-package-contract-v1.md)、[ACPF](ai2apps-capability-provisioning-framework-v1.md)
- [App Dev 环境](ai2apps-app-dev-environment.md)
- [发布回执](ai2apps-sol-refiner-0.1.0-release-2026-10-01.json)

### 0.1.1 候选验收补充

165 项相关测试通过；标准版签名安装后完成 4K 17 帧含音频输出，自定义提示词、取消、重启、卸载均通过。65 帧 2K 自适应窗口运行峰值约 13.04 GiB，耗时约 325.45 秒；较小窗口增加重叠计算，且测试存在并行负载，不承诺提速。

[完整候选验收记录](ai2apps-sol-refiner-0.1.1-validation-2026-10-02.json)。0.1.1 已在线发布并通过匿名下载/签名验证，Dev Discover 已显示新版本；Host 更新仍需进入 Desktop Release。

[0.1.1 发布回执](ai2apps-sol-refiner-0.1.1-release-2026-10-02.json)。

### 图片放大 0.1.2 已发布

0.1.2 增加独立的 `image_upscaling`，直接读写图片并共享上述权重；依赖 Runtime 1.8.8。0.1.2 与 Runtime 1.8.8 均已发布并验签。详见[图片放大对接指南](ai2apps-sol-refiner-image-upscaling-integration.md)。图片模型选择按 capabilities 筛选，不能仅按主 model_type。

## 0.1.3: whole-clip temporal contract

- Runtime minimum stays 1.8.8; checkpoint distributions and model IDs are unchanged.
- Submit the complete clip in one request. `segmented: false` and
  `temporal_policy: whole_clip` prohibit caller-side automatic independent splitting.
- VAE encoding, latent upsampling and DiT see the entire clip. Only VAE decoding
  is windowed; this can still introduce small decode transitions.
- Up to 1500 frames / 60 seconds, subject to memory admission. Memory grows with
  duration and resolution. A 503 `resource_exhausted` explains the estimate and
  available memory; no independent-refinement fallback is used.
- New result metadata: `inference_frames`, `decode_window_frames`,
  `estimated_memory_bytes`, `temporal_policy`. `overlap_frames` and `blend_frames`
  now describe decoding only.
- Desktop Host also needs the whole-clip resource estimate and Studio capability
  handling. Package availability alone does not upgrade the installed Host.
- Published 2026-10-02; trusted repository snapshot 242. Host Desktop update remains pending.
