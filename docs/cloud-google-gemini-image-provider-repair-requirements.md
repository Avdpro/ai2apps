# AI2Apps Cloud：Google Gemini 图片 Provider 修复需求

状态：Cloud 生产已部署，Desktop 客户端对接已完成，待一次生产账号端到端生成验收
提出方：AI2Apps Local / Imagine Studio
目标模型：`google/gemini-3.1-flash-image`

## 1. 生产复现与结论

2026-09-04 20:23（Asia/Shanghai），Imagine Studio 通过已认证的标准接口提交：

```http
POST /v1/ai/images/generations
Idempotency-Key: imagine-run-<studio-run-id>
Content-Type: application/json

{
  "model": "google/gemini-3.1-flash-image",
  "prompt": "胖熊猫吃竹子",
  "size": "1536x1024",
  "quality": "auto",
  "outputFormat": "png"
}
```

Cloud 在约 0.5 秒内返回 HTTP `502`：

```json
{
  "error": {
    "code": "AI_PROVIDER_ERROR",
    "message": "AI image provider request failed"
  }
}
```

Local 已将该请求可靠记录为失败 Run；没有浏览器断线或 Artifact 落盘问题。作为对照，同一
AppInstance、账号、提示词、尺寸、质量和输出格式下，`openai/gpt-image-2` 在此前一分钟通过
同一后台 Run 链路返回 `200`，图片已落盘且 Run 为 `succeeded`。因此问题位于 Cloud 的 Google
图片 Provider、上游模型配置或 Provider-neutral 参数转换，不在 Desktop 请求、鉴权或后台 Run。

## 2. 必须修复的行为

1. `POST /v1/ai/images/generations` 对目录中标记为可用的
   `google/gemini-3.1-flash-image` 必须能够完成文本生成图片。
2. Cloud 必须将 Provider-neutral 参数转换为 Google 上游实际接受的字段：
   - 将 `1536x1024` 映射为模型支持的尺寸或画幅合同；
   - 正确处理 `quality: auto`，上游无对应参数时应安全省略，不得原样发送非法枚举；
   - 将 `outputFormat: png` 映射为上游支持的响应 MIME/格式配置；
   - 固定单张输出；当前 Local 不要求批量生成。
3. 若 Google 模型不支持当前目录隐含的三个旧版固定尺寸，Cloud 不得继续把这些尺寸作为可用
   合同下发。应在模型目录为该模型返回准确的 `imageOptions`，让 Local 按目录渲染，而不是根据
   模型名称猜测。
4. 模型配置、区域、项目权限、API 版本或上游模型名称失效时，应将该模型从可选目录中暂时标记
   为不可用；不得在必然失败时继续显示为 Ready。
5. Provider 失败不得扣除最终生成费用；同一 `Idempotency-Key` 重试不得重复预留或结算。

## 3. 模型目录合同

`GET /v1/ai/models` 中该模型应返回与生产适配器一致的机器可读能力，例如：

```json
{
  "id": "google/gemini-3.1-flash-image",
  "capabilities": {
    "textInput": true,
    "imageInput": true,
    "imageOutput": true,
    "imageGeneration": true,
    "imageEdit": true
  },
  "imageOptions": {
    "size": {
      "mode": "fixed",
      "default": "1024x1024",
      "auto": true,
      "presets": ["1024x1024", "1536x1024", "1024x1536"]
    },
    "quality": ["auto"],
    "outputFormat": ["png", "jpeg", "webp"]
  }
}
```

以上数值只是当前 Desktop 所使用的兼容合同。Cloud 项目必须依据实际 Google Provider 能力确认
并发布最终值；若采用画幅而非像素尺寸，也应由 Cloud 负责确定性映射，并在返回图片的 `size`
字段中报告实际输出尺寸。

## 4. 可诊断错误

Cloud 服务端日志必须用 Cloud Request ID、Provider、模型和错误阶段关联上游响应，但不得记录
Prompt、图片正文、API Key、Device Credential 或完整上游敏感响应。客户端错误至少应区分：

- `AI_MODEL_CONFIGURATION_ERROR`：模型名、API 版本、区域或项目配置错误；
- `AI_PROVIDER_AUTHORIZATION_ERROR`：Cloud 到 Google 的授权或配额配置错误；
- `AI_IMAGE_PARAMETER_UNSUPPORTED`：尺寸、画幅、质量或输出格式不支持，HTTP `400`；
- `AI_PROVIDER_UNAVAILABLE`：Google 暂时不可用，可重试；
- `AI_PROVIDER_ERROR`：仅作为未知错误兜底。

错误响应应提供安全、可操作的 `message` 和正确的 `retryable`，避免 Desktop 只能显示
“AI image provider request failed”。

## 5. 自动化与生产验收

- 对 `1024x1024`、`1536x1024`、`1024x1536` 逐一生成并验证返回 `200`。
- 验证 `quality=auto` 与 `outputFormat=png|jpeg|webp` 的转换；若目录不声明某格式，则必须在调用
  上游前返回确定性 `400`。
- 验证响应包含有效 `data:image/...;base64,...`、真实 `size`、`quality` 和 `format`。
- 验证同一幂等键重复提交只产生一个 Cloud Request 和至多一次结算。
- 验证 Provider 失败不产生成功费用，且模型配置故障会反映到目录可用状态。
- 使用生产账号从 Imagine Studio 完成一次 Google 文生图；Run 必须进入 `succeeded`，服务端创建
  Artifact，页面刷新后图片仍然存在。
- 与 `openai/gpt-image-2` 回归并行执行，确保修复 Google Provider 不改变现有 OpenAI 路由。

## 6. 上线顺序

1. 在 Cloud 测试环境复现并从内部关联日志确认 Google 上游失败阶段。
2. 修复 Provider 配置/参数转换并补齐模型目录 `imageOptions`。
3. 完成幂等、计费、隐私和错误映射测试。
4. 部署生产并执行三种尺寸的受控探测。
5. 最后在 App-Dev Imagine Studio 完成端到端验收；验收前无需继续让用户重复付费重试。

## 7. 实施进展（2026-09-04）

- Cloud 已部署镜像 `ai2apps-cloud:google-gemini-image-provider-repair-v1-20260904T124117Z-r2`，
  OpenAPI `1.41.0`，数据库迁移 47 → 48，Cloud 全量测试 `280/280` 通过。
- Cloud 生产实测三个兼容尺寸别名均成功；非方形实际返回为 `1264x848` 与 `848x1264`，
  当前编码为 JPEG。
- Desktop 已改为从模型顶层 `imageOptions` 读取固定画幅、质量与输出格式；固定尺寸 UI 明确标注
  实际像素由模型决定。
- 后台 Run 以响应 `image.size`、`image.format` 与 Data URL MIME 保存历史和 Artifact，同时保留
  `requestedSize` 与 `requestedFormat` 供诊断；声明格式与 MIME 不一致时拒绝保存。
- Desktop 专项回归 `18/18` 通过；固定 App-Dev 已在端口 `61299` 以 schema v70 重启，实机确认
  Google 目录只提供 Auto 质量及 Auto、1:1、3:2、2:3 四个尺寸选项。
- 尚未由 Agent 再次触发付费生成；最终生产 Run、Artifact 落盘及刷新恢复由用户授权后验收。
