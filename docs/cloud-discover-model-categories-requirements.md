# Cloud Registry：Discover 模型分类支持需求

状态：待 Cloud 项目实现、部署与生产验收

2026-09-04 生产实测：提交 `ai2apps/model-detailed-transcription-mlx 0.1.0`
时，Cloud 对 `discovery` 与 `modelProfile` 两个顶层字段均返回 additional properties
校验错误。为不阻塞模型能力发布，修正版 0.1.1 临时使用 Desktop 中严格限定到该版本的
legacy mapping；Cloud 完成本需求后，后续 Package 版本恢复签名字段。

## 目标

让 Desktop Discover 能在完整 Registry 数据集上按“模型”以及文本、语音、多模态、图像、
视频、向量六个子分类查询。客户端已经支持签名 `manifest.discovery`，并对当前旧模型版本提供
带版本上限的内部对照表；Cloud 不需要要求旧 Package 重新提交。

## 数据合同

Cloud 在 Package 提交和发布时读取已经验签的 `ai2apps.json`：

```json
{
  "discovery": {
    "kind": "model",
    "categories": ["speech"],
    "tasks": ["speech-recognition"]
  },
  "modelProfile": {
    "sizeBytes": 1073741824,
    "minimumMemoryBytes": 4294967296,
    "scores": {"speed": 5, "capability": 4},
    "benchmark": {
      "label": "Publisher benchmark 2026-09",
      "device": "Apple M4 Max 64 GB"
    }
  },
  "modelInstall": {
    "serviceKey": "ai2apps.model.example",
    "models": [
      {"id": "ai2apps.model.example/default", "label": "Default", "recommended": true}
    ]
  }
}
```

- `kind` 当前只允许 `model`。
- `categories` 为 1–6 个唯一值：`text|speech|multimodal|image|video|embedding`。
- `tasks` 为 1–32 个唯一 lower-kebab-case 标识，每项不超过 64 字符。
- `kind=model` 只允许 `package.type=service`。
- 新模型 Release 必须同时提供完整 `modelProfile`：两个字节数字段为正整数，两个评分为
  1–5 整数，benchmark 的 label/device 为 1–120 字符非空字符串。
- 新模型 Release 必须提供 `modelInstall`：Service Key 必须与入口一致，1–32 个模型配置必须
  对应入口中带权重的真实模型，模型 ID 唯一且必须以 Service Key 开头，并恰好一个推荐项。
- Cloud 必须保存并返回原始签名 manifest；不得把后台人工标签伪装成签名字段。
- 对缺少字段的旧 Release，Cloud 可复制 Desktop 对照表生成派生目录字段，但必须标记
  `source=legacy-map`，并遵守每个 Package 的 `throughVersion` 上限。

## 查询接口

扩展以下两个现有接口：

- `GET /v1/registry/recommendations`
- `GET /v1/registry/search`

新增可选参数：

- `content=model|service`：`model` 仅返回模型 Service；`service` 返回排除模型后的普通 Service。
- `model_category=text|speech|multimodal|image|video|embedding`：仅与
  `content=model` 一起使用，否则返回 `422`。
- `model_task=<lower-kebab-case>`：按签名或旧版对照表中的 `discovery.tasks` 精确匹配；例如
  `speech-synthesis`（TTS）和 `speech-recognition`（ASR）。仅与 `content=model` 一起使用，
  否则返回 `422`。

过滤必须发生在排序、`limit` 和 cursor 分页之前，不能只过滤当前页。响应中的每个模型条目
应提供：

```json
"discovery": {
  "kind": "model",
  "categories": ["speech"],
  "tasks": ["speech-recognition"],
  "source": "manifest"
},
"modelProfile": {
  "sizeBytes": 1073741824,
  "minimumMemoryBytes": 4294967296,
  "scores": {"speed": 5, "capability": 4},
  "benchmark": {
    "label": "Publisher benchmark 2026-09",
    "device": "Apple M4 Max 64 GB"
  },
  "source": "manifest"
},
"modelInstall": {
  "serviceKey": "ai2apps.model.example",
  "models": [
    {"id": "ai2apps.model.example/default", "label": "Default", "recommended": true}
  ],
  "source": "manifest"
}
```

`source` 只允许 `manifest|legacy-map`，是 Cloud 派生的响应字段，不进入签名 manifest。

## 兼容与上线顺序

1. 先部署读取、索引和查询支持，并回填旧版本派生索引。
2. 验证匿名 recommendations/search 的完整分页和分类计数。
3. 再将提交校验切换为接受 `manifest.discovery`。旧版本不可因此失效。
4. Desktop 在 Cloud 尚未升级时会对单次最多 100 个 Service 结果进行本地兼容过滤；Cloud
   上线后应使用服务端过滤，解除该过渡期上限。

## 验收

- 当前已发布模型无需重发即可全部进入正确分类。
- 当前已发布模型无需重发即可获得带 `source=legacy-map` 的版本受限估算资料；超过
  `throughVersion` 的 Release 不得继续继承旧值。
- 当前已发布模型无需重发即可获得版本受限的 ACPF 安装索引；新版本必须使用签名
  `modelInstall`，Cloud 不得从名称猜测模型 ID。
- 普通 Runtime/Service 不出现在模型分类，模型不再出现在普通“服务”分类。
- 多分类 Package 在任一对应子分类均可查询，且同一页不重复。
- `speech + speech-synthesis` 只返回 TTS，`speech + speech-recognition` 只返回 ASR；同时具备
  某项附加任务（例如 `voice-cloning`）不影响其主任务查询。
- 搜索词、分类、排序和 cursor 组合稳定，无漏项或跨页重复。
- 非法分类、重复分类、空 tasks、非 Service 模型声明均在提交阶段拒绝。
- 返回的 manifest、Package 签名和 Repository Snapshot 验证保持不变。
