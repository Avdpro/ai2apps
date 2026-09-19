# ModelScope Range 客户端兼容实现与验收 — 2026-09-17

## 结论

AI2Apps Local/Desktop 的 Package 与 Checkpoint 下载器已实现 ModelScope 严格
`200 + Content-Range` 兼容，并保留标准 `206` 行为。

兼容只在可信 ModelScope 固定 revision 来源上启用。响应必须同时满足精确 start/end/total、
精确 `Content-Length`、identity 编码、非 multipart 和精确 body 长度；普通 `200` 整文件响应
会被拒绝。每个 piece 和最终完整 SHA-256 校验保持不变。

本改动属于 Desktop/Local 控制面。Runtime 1.7.0 构建器只把 `ai2apps/model_worker` 放入 Runtime
DMG，不包含 Package Registry 或 Checkpoint acquisition 下载器，因此已经发布的 Runtime 1.7.0
不需要重建。

## 实现

- 新增 `ai2apps/http_range.py`：Package 与 Checkpoint 共用的严格单区间响应头验证。
- `ai2apps/packages/registry.py`：
  - 仅对 `kind=modelscope`、`modelscope.cn`、无 query、40 位固定 revision 的 Package URL
    允许严格 `200`；
  - 标准 `206` 对所有既有来源保持支持；
  - body 读取限制在请求长度加一个检测字节；
  - 继续验证 piece hash 和完整 artifact hash。
- `ai2apps/checkpoint_distribution.py`：
  - ModelScope source 可使用严格 `200`；
  - Hugging Face 和其他 source 的 `200` 仍拒绝；
  - probe 和 fetch 共用同一流式有界读取路径；
  - total 必须等于签名 manifest 中的文件 size；
  - 普通整文件 `200` 不进入内存。
- `ai2apps/checkpoint_acquisition.py`：把签名 manifest 的文件 size 传入 source adapter，绑定
  每次 `Content-Range` 的 total。

## 自动化验证

- Ruff：受影响实现和测试全部通过。
- Python compile：受影响实现全部通过。
- 定向回归：`75 passed`：
  - `tests/test_http_range.py`
  - `tests/test_checkpoint_distribution.py`
  - `tests/test_checkpoint_acquisition.py`
  - `tests/test_ai2apps_registry_v1.py`
- Package installer 扩展回归：`22 passed, 2 failed`。两个失败均为当前测试仍断言迁移前
  `mlx-community/Qwen3.6-35B-A3B-4bit`，而产品配置已经切换至
  `Avdpro/Qwen3.6-35B-A3B-4bit-SSD`；与 Range 客户端修改无关。本轮未改写该迁移测试。

## 真实 ModelScope 验收

### Runtime 1.7.0 Package

来源：

```text
https://modelscope.cn/models/ai2apps/desktop-releases/resolve/
18751703b53671cb2db926f9f8ed508a70df15b0/
ai2apps-runtime-omlx-1.7.0-production.ai2service
```

先使用正式客户端 piece 请求路径验证首段、中段和末段各 65,536 字节，三段均与本地正式制品
SHA-256 一致。随后执行 ModelScope 单源完整下载：

```text
piece size: 8 MiB
piece count: 45
resume start: verified piece 2
final size: 373748488
final sha256: b066700dcebec87012e93de01e6114db9f231b0a1c89642e97c50cd91a1ec3a7
result: passed
```

全程 source kind 为 `modelscope`，没有使用 Cloud 或 GitHub 回退。

### DS4.1 SSD Checkpoint

使用正式 `HubSourceResolver` 和 `HTTPRangePieceSource` 访问：

```text
repo: ai2apps/DeepSeek-V4.1-Flash-SSD
revision: f06bb1c499bf38694d84f8b5f3e345a84b8e44d3
path: experts/layer-0.bin
expected size: 7219445760
```

真实 probe 返回可用且支持 Range；读取首个 4,096 字节后与本地 SSD checkpoint 比较：

```text
sha256: bc6b186fe987478058b5fdc94c3cc26deb79e03f0ee8cb78fcd4e1dcc5c06278
result: passed
```

没有重新下载 7.2 GB 文件；单元和 acquisition 回归覆盖后续 piece 调度、hash 和失败回退。

## 正式 Cloud 验证与发布门

Cloud 已部署 OpenAPI 1.50.0 和 `package-single-range-v2`。2026-09-17 使用标准发布脚本和
明确授权的 `AI2Apps-dev` 管理员会话，正式登记 Runtime 1.7.0 ModelScope 固定 URL：

```text
source id: src_3125a4d0-27d8-4cfc-a9f2-43b0ec8ad3a2
validation id: val_9f67323e-596d-46ef-92bb-13ca61e2b53b
validation-time source revision: 7
validation-time source status: pending_approval
validation status: passed
validation digest: a453483dd89e5f719f47f7c81b1a05a1893ddf08e6726c77181598e00fd500d0
piece manifest digest: a6c012d3f558d9eb03433dbf30e24430c8edfb11bcc156554668abb08bbe3e02
```

正式验证完成完整文件 SHA-256、373,748,488 字节大小和 45-piece manifest 校验；Range
receipt 记录策略 `package-single-range-v2`、兼容类型
`modelscope-content-range-200`，48 次响应全部为 `http-200-content-range`。第一次验证
`val_4755e21e-af4a-4be2-9fb2-cda0d5b5b5a7` 因上游连接提前结束而报告
`range_body_short`；对同一 Source 执行恢复验证后完整通过，没有重复注册来源。

Dev 和 App-Dev 均通过固定 Development Source Root 加载当前兼容实现；App-Dev Local
已刷新。release-shaped Test App 已通过固定 `build-test-app.sh` 重建，包内
`http_range.py` 和 `registry.py` 与当前源码逐字节一致，嵌入式 CPython 导入和最终
`codesign --verify --deep --strict` 均通过。因此开发用客户端已经具备该下载能力，不要求先
发布 Desktop Release。

按用户指示直接激活时，Cloud 拒绝同一登记人的请求：

```text
ARTIFACT_SOURCE_SELF_APPROVAL_NOT_ALLOWED
ModelScope HTTP 200 compatibility requires a distinct approver
```

Cloud 于 2026-09-18 部署 `ai2apps-cloud:range-policy-20260918`，恢复既有管理员 step-up
自审语义且未改变 Range 验证器。客户端随后用原 Source、validation、digest、ETag 和幂等键
重试成功：

```text
source status: active
source revision / ETag: 8 / "sources-8"
repository metadata: 154
repository snapshot digest: 49d0748f75606adf61397106ebcf197316a5d2c1530d9d41a0ac0d7fede515c2
```

管理员列表确认 Cloud、GitHub、ModelScope 三源均 active。全新匿名客户端使用固定 Repository
公钥验证 Snapshot 154 签名，Runtime 1.7.0 的 size、SHA-256 与三源 URL 均正确。正式
ModelScope Package 来源发布完成。
