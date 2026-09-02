# AI2Apps 本地视频生成 v1 实现与验收

状态：核心链路已实现并完成 H3、EchoMimic V3 真机验收。

Video Studio 后续的按操作模型配置、设备推荐、下载编排和重启恢复统一遵循
[AI2Apps Capability Provisioning Framework（ACPF）v1](ai2apps-capability-provisioning-framework-v1.md)，
不在 Video Studio 内维护独立安装向导。

## 1. 架构与版本

本实现让文本视频模型和数字人模型共用同一套 AI2Apps 能力：

```text
AI2Apps API
  -> durable video task queue
  -> Package Supervisor / Model Worker Host
  -> ai2apps.runtime.omlx 1.4.0
  -> H3 0.8.0 或 EchoMimic V3 MLX 0.1.0
  -> Workspace Artifact (MP4)
```

- Runtime Package：`ai2apps.runtime.omlx` 1.4.0，提供 MLX、PyAV、H.264/AAC、
  Worker artifact/progress/cancel 协议。
- H3 Package：`ai2apps.model.minimax-h3` 0.8.0，提供 FL2VA BF16/Q8/Q4 和
  Ref2VA Q8/Q4 分阶段驻留，
  以及 strict、fast、fast_max 三种质量/速度档位。BF16/FP16 当前因输出质量问题被
  Host 临时禁用；Video Studio 和 ACPF 仅允许 Q8/Q4。
- 数字人 Package：`ai2apps.model.echomimic-v3-mlx` 0.1.0，模型代码随 Package
  分发，权重由 Host 按固定 Hugging Face revision 管理。
- 两个模型都声明严格的 `ai2apps.video-capabilities/v1`，Host 在排队前校验
  content 组合、分辨率、帧率、时长和 preset。

模型 Package 不包含 Python/MLX Runtime，也不自行启动 HTTP 服务；它们通过锁定到
具体 digest 的 Runtime Package 执行。

## 2. 公共异步 API

创建任务：

```http
POST /v1/videos/generations
Idempotency-Key: optional-client-key
Content-Type: application/json
```

`POST /v1/videos` 是等价别名。成功时返回 `202 Accepted`、任务对象和指向任务的
`Location`。查询与取消接口：

```text
GET    /v1/videos/generations
GET    /v1/videos/generations/{task_id}
DELETE /v1/videos/generations/{task_id}
```

请求示例：

```json
{
  "model": "ai2apps.model.minimax-h3/fl2va-4bit",
  "content": [
    {"type": "text", "role": "prompt", "text": "A paper boat sailing at sunset"}
  ],
  "resolution": "512x288",
  "framespersecond": 24,
  "duration": 0.92,
  "preset": "fast_max",
  "seed": 7,
  "metadata": {"case": "preview"}
}
```

输入图像/音频可引用 `artifact://`、`multipart://`、base64 `data:` 或公网 HTTPS。
Host 会在任务入库时冻结输入并记录大小与 SHA-256；拒绝本地/私有网络 URL、超限输入
和不符合声明的媒体组合。Multipart 请求用 `request` 字段承载 JSON，其它命名 part
通过 `multipart://<name>` 引用。

Ref2VA 使用 `ai2apps.model.minimax-h3/ref2va-8bit` 或 `ref2va-4bit`。Host 按
`content` 数组顺序冻结重复的 `reference_image`、`reference_video` 和
`reference_audio`，再以有序 `reference_parts` 传给 Worker；顺序属于模型语义，不能按媒体类型
重排。单次最多九张图片、三个 2–15 秒视频、三个 2–15 秒音频且总文件数不超过十二，并且必须
至少包含图片或视频。视频内嵌音轨默认作为同一参考项的音频条件。

Video Studio 的“参考素材”功能使用独立 ACPF capability
`video.reference_generation`，128 GiB Apple Metal 默认推荐 Ref2VA Q8；64–95 GiB 推荐 Q4。
配置只安装 Runtime、0.8.0+ Service Package 和对应 checkpoint，不自动创建生成任务。

任务状态为 `queued`、`running`、`succeeded`、`failed`、`cancelled` 或 `expired`。
任务进度包含模型上报的 `phase/current/total/percent`。同一调用者的
`Idempotency-Key` 和相同规范化请求返回原任务；键相同但请求不同返回 409。

成功结果不把完整 MP4 放入 JSON 或进程内存，而是返回统一 Artifact：

```json
{
  "result": {
    "video": {
      "artifact_id": "art_...",
      "uri": "artifact://art_...",
      "media_type": "video/mp4",
      "download_url": "/v1/platform/sessions/.../artifacts/art_.../download"
    }
  }
}
```

当前业务队列仍按本机单设备串行取任务，但每个任务在真正执行前必须取得 Host
`WorkerJobScheduler` 的 `local_background` RequestLease，并通过统一 Resident/Transient
Memory Admission。任务等待全局准入时保持 `queued`，取得 Lease 后才进入 `running`；取消
queued 任务会同时取消 Scheduler waiter，生成结束、失败或取消后释放 Lease。Host 重启时，
`exact` 任务重新排队；近似快速档位的
中断任务显式失败，避免用不同缓存轨迹静默恢复。取消会传递到 Worker；已经提交给
Metal 的单个计算图不能被中途抢占。

## 3. Worker 文件输出协议

Adapter 通过 `ModelWorkerRequest.output_root` 获得每次调用独占的输出目录，并返回
`ModelWorkerArtifact`。Runtime 只接受该目录的直接子文件，使用目录文件描述符和
`O_NOFOLLOW` 打开，然后流式传给 Host；模型不能借此读取或返回任意路径。

Adapter 可调用 `request.progress({...})` 报告准备、编码、去噪、解码等阶段。Runtime
同时提供内部进度查询和取消端点，公共任务管理器负责轮询、持久化和转发。

## 4. 真机验收（2026-08-24）

验收机为 Apple Silicon Mac，均走安装后的 Model Package、锁定 Runtime、Managed
Worker、异步任务和 Workspace Artifact 完整链路。

| 模型 | 配置 | 结果 | 端到端时间 | 输出 |
|---|---|---|---:|---|
| H3 Q4 | 512x288, 24 fps, 0.92 s, fast_max | succeeded | 61.09 s | H.264/AAC, 22 帧, 109,339 bytes |
| EchoMimic V3 | 512x512, 25 fps, 约 3.30 s | succeeded | 168.55 s | H.264/AAC, 81 帧, 241,470 bytes |

H3 输出 SHA-256 为
`d764f077e1b15fcc769443c544cee545ff89b9dbac78fd4ef8471852e2f560ce`；
EchoMimic 输出 SHA-256 为
`d2dc677441d4de33eb1e4b97daa8f9c6b6e6eb7a77cae7cfb783315f6fe7b7b8`。

## 5. 发布前门槛

核心推理和集成已经完成。Runtime 1.4.0 已于 2026-08-24 完成 Developer ID
签名、Apple 公证、staple 和 Gatekeeper 验证，三份正式 Package 也已使用生产
AI2Apps Publisher key 签名并发布到 Discover；完整收据见
[视频生成 v1 签名与公证收据](ai2apps-video-generation-v1-release-receipt.md)。后续还需要：

1. 在确认模型许可证和发布权限后，把合并后的 EchoMimic MLX checkpoint 发布到声明的
   固定仓库/revision；当前只验证了本地等价 snapshot。
2. 如产品需要服务器主动通知，再单独实现带域名策略、签名、重试和防 SSRF 的
   `callback_url`；当前 Host 明确拒绝该字段。
