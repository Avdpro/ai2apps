# AI2Apps Cloud GPT Image 2 灵活尺寸支持需求 v1

状态：待 Cloud 项目实现  
提出方：AI2Apps Local / Imagine Studio  
目标模型：`openai/gpt-image-2`  
协议版本：向后兼容现有 Provider-neutral Image API

## 1. 背景

AI2Apps Cloud 当前图片协议只接受三种固定尺寸：

- `1024x1024`
- `1536x1024`
- `1024x1536`

这属于 AI2Apps Cloud 首版协议限制，不是 GPT Image 2 的模型限制。OpenAI 当前官方文档说明，`gpt-image-2` 的 `size` 参数可以接受满足约束的任意分辨率，并列出 2K、4K 等常用尺寸。

Imagine Studio 需要提供常用画幅预设、1K/2K/4K 档位和自定义尺寸，因此 Cloud 项目需要先放开并正式声明图片输出尺寸能力，Local UI 才能安全跟进。

官方依据：

- <https://developers.openai.com/api/docs/models/gpt-image-2>
- <https://developers.openai.com/api/docs/guides/image-generation#size-and-quality-options>

## 2. 目标

Cloud 项目应做到：

1. `generations` 和 `edits` 接口接受符合 GPT Image 2 约束的自定义尺寸。
2. 继续支持现有三个固定尺寸，现有客户端无需修改即可工作。
3. 通过模型目录下发机器可读的尺寸约束与推荐预设，避免 Local 硬编码供应商规则。
4. 在调用上游、预留点数前完成确定性校验。
5. 按实际请求尺寸正确预留和结算点数，并在响应中保留现有计费字段。
6. 不增加 Prompt、输入图片或输出图片正文的持久化与日志暴露。

## 3. 范围

### 3.1 本期必须支持

- `POST /v1/ai/images/generations`
- `POST /v1/ai/images/edits`
- 模型目录中的 `openai/gpt-image-2` capability 描述
- 自定义尺寸校验
- 尺寸相关错误码
- 对应计费、幂等、隐私与自动化测试

Local 转发端点保持不变：

- `POST /v1/platform/cloud/ai/images/generations`
- `POST /v1/platform/cloud/ai/images/edits`

### 3.2 本期不包含

- 批量生成，继续保持 `n=1`
- 异步图片任务或图片流式返回
- Cloud 端图片资产保存
- Imagine Studio 前端改造
- 本地绘图模型的尺寸能力
- 图片超分辨率 Pipeline

## 4. 尺寸规则

`size` 接受以下两种形式：

- 字符串 `auto`
- 字符串 `<width>x<height>`，例如 `2048x1152`

自定义尺寸必须同时满足：

| 规则 | 要求 |
| --- | --- |
| 数值类型 | 宽和高均为十进制正整数 |
| 最大边长 | `width <= 3840` 且 `height <= 3840` |
| 对齐 | 宽和高均为 16 的倍数 |
| 最大长宽比 | `max(width, height) / min(width, height) <= 3` |
| 最小总像素 | `width * height >= 655360` |
| 最大总像素 | `width * height <= 8294400` |

`size` 缺失时保持当前默认行为。Cloud 可以向上游传递 `auto`，但不得自行将有效的自定义尺寸静默改写为旧三种尺寸之一。

### 4.1 推荐预设

模型目录至少应声明以下预设；它们是 UI 建议值，不是 allowlist：

- `1024x1024`：1K 方形
- `1536x1024`：1K 横向
- `1024x1536`：1K 纵向
- `2048x2048`：2K 方形
- `2048x1152`：2K 16:9 横向
- `1152x2048`：2K 9:16 纵向
- `3840x2160`：4K 16:9 横向
- `2160x3840`：4K 9:16 纵向

总像素超过 `2560x1440`（3,686,400）的请求属于上游实验性输出。Cloud 不应拒绝，但应通过 capability 元数据让客户端标注 `experimental`。

### 4.2 示例

有效值：

```text
auto
1024x1024
1280x720
1536x1024
1920x1088
2048x1152
2048x2048
3840x2160
2160x3840
```

无效值：

```text
1920x1080   # 高不是 16 的倍数
4000x2000   # 单边超过 3840
3200x1024   # 长宽比超过 3:1
512x512     # 总像素不足 655360
3840x3840   # 总像素超过 8294400
foo         # 格式错误
```

## 5. API 请求兼容

现有 JSON 字段和 camelCase 命名保持不变。

```http
POST /v1/ai/images/generations
Idempotency-Key: image-generation-uuid
Content-Type: application/json

{
  "model": "openai/gpt-image-2",
  "prompt": "Premium product photo of a wristwatch",
  "size": "2048x1152",
  "quality": "high",
  "outputFormat": "png",
  "n": 1
}
```

编辑接口使用同一套尺寸规则：

```http
POST /v1/ai/images/edits
Idempotency-Key: image-edit-uuid
Content-Type: application/json

{
  "model": "openai/gpt-image-2",
  "prompt": "Place the product in a premium studio scene",
  "imageDataUrls": ["data:image/png;base64,..."],
  "size": "2048x2048",
  "quality": "high",
  "outputFormat": "webp"
}
```

Cloud 转发 OpenAI 时应将 Provider-neutral 字段转换为上游 snake_case，例如：

- `outputFormat` → `output_format`
- `outputCompression` → `output_compression`
- `imageDataUrls` → 上游编辑接口所需图片输入

## 6. 模型目录能力声明

Cloud 模型目录应在保持现有 capability 布尔字段的基础上，增加可选的 `imageOptions`：

```json
{
  "id": "openai/gpt-image-2",
  "capabilities": {
    "textInput": true,
    "imageInput": true,
    "imageOutput": true,
    "imageGeneration": true,
    "imageEdit": true
  },
  "imageOptions": {
    "size": {
      "mode": "bounded-custom",
      "default": "auto",
      "auto": true,
      "width": {"min": 16, "max": 3840, "multipleOf": 16},
      "height": {"min": 16, "max": 3840, "multipleOf": 16},
      "minPixels": 655360,
      "maxPixels": 8294400,
      "maxAspectRatio": 3,
      "experimentalAbovePixels": 3686400,
      "presets": [
        "1024x1024",
        "1536x1024",
        "1024x1536",
        "2048x2048",
        "2048x1152",
        "1152x2048",
        "3840x2160",
        "2160x3840"
      ]
    },
    "quality": ["auto", "low", "medium", "high"],
    "outputFormat": ["png", "jpeg", "webp"]
  }
}
```

说明：

- `width.min` 和 `height.min` 只表达单边的基础数值域；真正的最小输出由 `minPixels` 共同约束。
- 未返回 `imageOptions` 的旧 Cloud 服务应继续被 Local 视为旧版三尺寸能力。
- 后续接入其他图片模型时，每个模型可以返回自己的 `mode`、边界和预设。
- Local 不应根据模型名称猜测能力。

## 7. 错误协议

尺寸错误必须在调用上游和预留点数之前返回 HTTP `400`。建议沿用统一错误对象：

```json
{
  "error": {
    "type": "image_generation_user_error",
    "code": "invalid_image_size",
    "message": "Image size must be two multiples of 16 within the supported pixel and aspect-ratio limits.",
    "param": "size",
    "retryable": false,
    "details": {
      "received": "1920x1080",
      "constraints": {
        "maxEdge": 3840,
        "multipleOf": 16,
        "minPixels": 655360,
        "maxPixels": 8294400,
        "maxAspectRatio": 3
      }
    }
  }
}
```

稳定错误码：

| code | 条件 |
| --- | --- |
| `invalid_image_size_format` | 不是 `auto` 或 `<width>x<height>` |
| `image_size_alignment_error` | 任一边不是 16 的倍数 |
| `image_size_edge_limit_exceeded` | 任一边超过 3840 |
| `image_size_pixel_count_out_of_range` | 总像素低于最小值或超过最大值 |
| `image_size_aspect_ratio_exceeded` | 长短边比例超过 3:1 |
| `unsupported_image_size` | 上游实际不接受一个通过本地规则的尺寸；应告警并视为 Cloud/上游能力漂移 |

错误响应不得回显 Prompt、输入 Data URL、认证信息或上游原始内部错误正文。

## 8. 点数与计费

1. 点数预留必须考虑 `size`、`quality`、模型和操作类型（生成/编辑）。
2. 自定义尺寸不得按最接近的旧尺寸低估预留量。
3. 同一 `Idempotency-Key` 不得因重试重复扣点或重复调用上游。
4. 校验失败不得产生点数流水。
5. 上游失败必须释放未使用预留点数。
6. 成功响应继续返回当前字段：`charged`、`balance`、`pricingVersion`（若当前端点已经提供）。
7. 如 Cloud 无法在请求前精确报价，应采用足额上限预留、完成后按实际用量结算并释放差额。
8. 2K/4K 实验性输出是否采用额外点数倍率，必须由定价版本明确决定，不能隐藏在客户端常量中。

本期不强制增加报价接口；如果 Cloud 已有模型定价/预估能力，建议使其接受 `size` 和 `quality`，供 Imagine Studio 在生成前显示预计点数。

## 9. 隐私、安全与日志

保持当前图片协议的隐私边界：

- 不持久化 Prompt。
- 不持久化 `imageDataUrls`、`maskDataUrl` 或输出 Data URL。
- 不在访问日志、错误日志、审计日志、追踪 span 中记录上述正文。
- 审计仅记录账户/组织主体、请求 ID、幂等键摘要、模型、操作类型、尺寸、质量、状态、点数和耗时。
- `size`、`quality` 等非敏感结构化元数据可以进入指标。
- 成功返回的图片 Data URL 仍由调用 App 立即保存；Cloud 不提供相同幂等键的图片正文重放。

## 10. 可观测性

Cloud 至少增加以下指标维度：

- `model`
- `operation`：`generation` / `edit`
- `size_bucket`：`1k` / `2k` / `4k` / `custom`
- `quality`
- `status`
- `upstream_error_code`

不要把完整 `size` 作为无限基数标签；具体宽高可以放入受控事件或日志结构中。

需要监控：

- 各尺寸成功率和 P50/P95/P99 延迟
- 预留点数与最终扣点偏差
- `unsupported_image_size` 数量
- 2K/4K 上游失败率
- 请求/响应正文大小与超时率

## 11. 兼容与发布顺序

1. Cloud 先实现服务端尺寸校验、上游转发和测试，但暂不要求客户端使用新尺寸。
2. Cloud 发布模型目录的 `imageOptions`。
3. Local 验证 capability 后再放开 Imagine Studio 的比例预设和自定义尺寸。
4. 未获得 `bounded-custom` capability 时，Local 继续只显示旧三个尺寸。
5. Cloud 回滚时必须同时回滚 capability，避免客户端继续提交自定义尺寸。

禁止仅在 Imagine Studio 前端增加尺寸选项而不升级 Cloud 协议。

## 12. 验收标准

以下条件全部满足才视为完成：

### 12.1 功能

- 生成与编辑接口均接受八个推荐预设。
- 至少验证三个非预设但合法的自定义尺寸。
- `auto` 和旧三个尺寸行为不变。
- 成功响应返回实际 `size`，并与生成图片文件头中的尺寸一致。
- 模型目录准确返回 `bounded-custom` 能力。

### 12.2 校验

- 每一类非法尺寸都有独立测试。
- 校验发生在点数预留和上游调用之前。
- 边界值测试覆盖 3840、16 倍数、3:1 和像素上下限。
- 使用整数运算验证比例，避免浮点边界误判，例如：

```text
max(width, height) <= 3 * min(width, height)
```

### 12.3 计费与幂等

- 不同尺寸/质量组合的预留与结算测试通过。
- 相同幂等键并发或重试只产生一次上游调用和一次扣点。
- 上游 4xx、5xx、超时和断线均正确释放预留点数。

### 12.4 隐私

- 自动化测试证明 Prompt 和三类 Data URL 不进入日志、数据库或错误响应。
- 2K/4K 大响应测试不产生截断日志或意外正文采样。

### 12.5 联调

- AI2Apps Local 能从模型目录读取 `imageOptions`。
- Local → Cloud → OpenAI 的 `size` 值保持不变。
- Imagine Studio 使用推荐预设和至少一个自定义尺寸完成端到端生成。
- 生成结果可被 Local 保存并加入 Gallery。

## 13. Cloud 交付物

Cloud 项目完成时应提交：

1. 服务端实现与数据库/定价配置变更。
2. 更新后的 OpenAPI 或接口 schema。
3. 模型目录 `imageOptions` 示例响应。
4. 自动化测试和边界测试报告。
5. 点数预留/结算测试记录。
6. 隐私日志审计结果。
7. staging 联调地址、版本号与发布日期。
8. 回滚方案及 capability 回滚验证。

## 14. Local 后续工作

Cloud 验收完成后，Imagine Studio 将实施：

- 常用比例与 1K/2K/4K 预设。
- 自定义宽高输入。
- 16 像素对齐与边界即时提示。
- 2K 以上实验性与成本提示。
- 根据模型目录动态切换固定尺寸或灵活尺寸 UI。
- 后续对本地绘图 Pipeline 复用同一 capability 驱动机制。
