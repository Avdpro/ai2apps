# SoL-Refiner 图片放大对接

更新：2026-10-02。已发布版本为 `ai2apps/model-sol-refiner-mlx@0.1.2`，依赖 `ai2apps/runtime-omlx>=1.8.8,<2`。两个 Package 已正式发布并通过匿名完整下载/签名核验，Dev Discover 已显示新版本；Host 改动仍需纳入 Desktop Release。视频接口继续兼容，见[视频指南](ai2apps-sol-refiner-video-upscaling-integration.md)。

## 能力发现与安装

图片放大是独立核心 operation `image_upscaling`，ACPF 语义能力为 `image.upscaling`。Imagine Studio 与 Video Studio 对应 profile 已加入仓库。前端按模型 `capabilities` 是否包含 `image_upscaling` 筛选，并读取 `image_upscaling_capabilities`；**不要要求 `model_type == image_upscaling`**，SoL 共享模型的主类型仍为 `video_upscaling`。

复用以下模型 ID 和已发布的权重分发，不重复下载图片专用权重：

- 标准推荐：`ai2apps.model.sol-refiner-mlx/ltx23-one-step`，权重约 28.71 GB。
- 自定义提示词：`ai2apps.model.sol-refiner-mlx/ltx23-custom-prompt`，权重约 57.04 GB，与标准版共享缓存。

安装、修复、用户许可确认交给 Discover / ACPF。安装 Runtime 不会更新 Desktop Host；旧客户端须升级到包含图片能力发现、资源调度和对应 App 接入的版本。ACPF profile 不等于已完成 Mini-App bridge/UI。

## 输入、参数和输出

- 输入：单帧 PNG、JPEG、WebP，8-bit；动画和 HDR/16-bit 图像明确拒绝。
- 固定 2× 放大，输入无需补齐 32 倍数；内部补齐并裁回。没有 512/1024/4K 的固定边长上限，实际由资源决定。
- 先应用 EXIF 方向；有效受支持的 ICC 转为 sRGB，不支持的颜色配置明确报错。
- 透明通道独立以 Lanczos 放大，RGB 由模型处理；模型不会生成新的透明度细节。
- 输出：`image/png` 二进制，文件名 `upscaled.png`，sRGB，宽高分别为应用方向后的两倍。PNG 编码无损，不代表模型处理前后像素不变。
- 参数：`scale: 2`、`seed: 0..4294967295`、可选 `prompt`（最多 2048 字符）。标准版只接受默认提示词，自定义版可更改。无需 fps、steps 或视频编码参数。

## Host 调用

内部 Worker 为 `POST /v1/images/upscalings`，multipart 字段 `model`、`image`、`parameters`。这是 Worker 内部协议，不是 Mini-App 可直接访问的公开 HTTP 路径。

```python
from ai2apps.model_invocation import ModelInvocationContext

model_id = "ai2apps.model.sol-refiner-mlx/ltx23-one-step"
model = runtime.model_invocations.model(model_id)
if model is None or "image_upscaling" not in model.capabilities:
    raise ValueError("请选择已安装的图片放大模型")
context = ModelInvocationContext.from_principal(
    principal,
    session_id=session_id,
    app_instance_id=app_instance_id,
    consumer_app_id=consumer_app_id,
)
await runtime.model_invocations.invoke_background_to_file(
    model_id,
    "image_upscaling",
    {"parameters": {"scale": 2, "seed": 0}},
    output_path,
    files={"image": ("input.png", input_path, "image/png")},
    request_id=worker_request_id,
    cancel_requested=cancel_requested,
    progress=record_progress,
    context=context,
)
```

这些上下文、输入归属和原生路径由 Host 验证并提供。Host 从真实图片头部读取方向和尺寸以预留内存，不信任前端内存估计。Mini-App 使用绑定 actor/App/mount 的 bridge，不能接触内部 endpoint、认证头或 checkpoint 路径。

Host 负责持久任务、取消/失败状态以及结果去重。输出写入成功后注册现有 Studio Artifact / Preview & Output；不要为 Mini-App 新建一套输出历史或下载实现。

进度 `{"phase":"image_upscaling","current":0,"total":1}` 在推理前发出，完成后 current 为 1。它不是逐步百分比；以请求成功和文件保存完成为准。取消走现有 Host `cancel_request` / Worker request ID，取消后的推理 HTTP 状态为 499。无效图片返回 `invalid_image`，参数不合法返回 `invalid_request`；未装权重与提示词配置错误沿用视频指南的错误处理。

## 验证范围

真实单图探针：513×341 RGBA → 1026×682，约 4.49 秒、MLX 峰值 1.45 GiB；1920×1080 RGBA → 3840×2160，约 12.83 秒、MLX 峰值 2.99 GiB。两项透明通道均与预期 Lanczos 结果逐字节一致。MLX 分配峰值不是整个进程总内存，耗时也不是稳定性能承诺；素材用于尺寸和功能验证，不代表普适画质评测。

174 项相关测试通过（原 173 项及新增 Host 调用测试）。最终签名安装已验证标准版 4K PNG、自定义提示词 PNG、含音轨视频回归，以及取消、重启、停启和卸载。签名安装验收结果见[0.1.2 验收记录](ai2apps-sol-refiner-0.1.2-validation-2026-10-02.json)。接入方仍须验证图片选择、模型安装、任务取消、错误提示和公共输出的端到端 UI。

## 发布记录

[SoL 0.1.2 发布回执](ai2apps-sol-refiner-0.1.2-release-2026-10-02.json) · [Runtime 1.8.8 发布回执](ai2apps-runtime-1.8.8-release-2026-10-02.json)。Runtime 当前使用已验证的 Cloud 源，外部镜像补齐计划已记录。
