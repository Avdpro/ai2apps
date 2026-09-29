# AI2Apps oMLX Runtime 1.8.1 / Ornith 0.1.5 发布需求

状态：`published_acceptance_pending`。Runtime 1.8.1 与 Ornith 0.1.5 已于 2026-09-28
按本文顺序发布；正式事实与制品摘要见
`docs/ai2apps-mlx-runtime-1.8.1-boost-release.md`。本文继续保留为原始执行 handoff 和
未完成的六后端真实 checkpoint 验收清单，不作为发布收据。

发布必须遵循 `docs/ai2apps-package-publication-runbook.md`，不得使用浏览器自动化、临时
`curl`、直接写 Cloud 数据库或另一套签名/发布实现。

## 1. 发布目标与顺序

本次只需要发布两个 Package，并严格按依赖拓扑执行：

| 顺序 | Package | 当前版本 | 目标版本 | 类型 |
| --- | --- | --- | --- | --- |
| 1 | `ai2apps/runtime-omlx` | `1.8.0` | `1.8.1` | 含原生代码的 Runtime |
| 2 | `ai2apps/model-ornith15-35b-a3b-4bit-vision` | `0.1.4` | `0.1.5` | 纯 Python 模型 Service |

必须先完成 Runtime 1.8.1 的公证、发布、多源激活和安装验证，再构建、发布 Ornith
0.1.5。不得先发 Ornith，也不得用临时 Package ID、Publisher、Publisher key 或另一个
版本绕过失败。

## 2. 发布范围

### 2.1 Runtime 1.8.1

Runtime 1.8.1 应包含当前源码中的完整 Engine Boost 生产链：

- DeepSeek V4.1 接入会话级 Decode Burst：Natural 为精确 Top-6，Turbo 保护 Top-4，
  Blast 保护 Top-2；Prefill 始终精确。
- Qwen3.8 Flash Next Cached-MoE 使用带会话控制器的 Qwen4 动态 VLM Engine；既有产品
  策略保持 Natural 精确、Turbo Top-5、Blast Top-3。
- Qwen3.6、Ornith 1.5 和兼容的 Qwen3.5-MoE VLM 路径使用 Qwen3.6 动态 VLM Engine，
  不再静默忽略 `flesh_boost_mode`。
- DeepSeek V4、Qwen3.6 文本版和 GLM-5.3 的既有 Boost 控制链保持兼容，并纳入统一
  请求/下一 Token 边界切换契约。
- Worker 最终 usage 返回实际 `ai2apps_engine_boost`；空闲状态端点返回
  `engine_boost_supported` 和 `engine_stats`，包括实际模式、路由、替换、miss 和命中率。
- Boost 切换不能为了读取统计而在生成中额外同步 Metal；生成中的状态读取必须保持现有
  安全边界。

主要源码范围：

- `omlx/patches/deepseek_v41/boost.py`
- `omlx/patches/deepseek_v41/engine.py`
- `omlx/patches/deepseek_v41/model.py`
- `omlx/engine/qwen36_dynamic.py`
- `omlx/engine/qwen4_dynamic.py`
- `omlx/patches/qwen3_6_flesh/boost.py`
- `omlx/patches/qwen38_next_cache/boost.py`
- `omlx/engine_pool.py`
- `ai2apps/model_worker/cache_moe.py`
- `ai2apps/model_worker/omlx_chat.py`
- `ai2apps/model_worker/server.py`

发布准备时把 Runtime 版本从 1.8.0 一致提升到 1.8.1，至少核对：

- `packages/ai2apps-runtime-omlx/ai2apps.json`
- `packages/ai2apps-runtime-omlx/service.yaml`
- `packages/ai2apps-runtime-omlx/META/runtime-manifest.json`
- `packages/ai2apps-runtime-omlx/META/sbom.spdx.json`
- `packages/ai2apps-runtime-omlx/README.md`

版本、SBOM 名称/namespace、Runtime manifest 和最终制品元数据必须一致。

### 2.2 Ornith 0.1.5

Ornith 0.1.5 只包含 Package 自己必须携带的 Adapter 改动：Cached-MoE/VLM 创建路径从普通
`VLMBatchedEngine` 改为 Runtime 1.8.1 提供的 `Qwen36DynamicVLMEngine`。Package 不得携带
Native 代码，也不得复制 Runtime 模块。

发布准备时必须完成：

1. 将下列版本字段从 0.1.4 一致提升到 0.1.5：
   - `packages/omlx-model-ornith15-35b-a3b-4bit-vision/ai2apps.json`
   - `packages/omlx-model-ornith15-35b-a3b-4bit-vision/service.yaml`
   - `packages/omlx-model-ornith15-35b-a3b-4bit-vision/pyproject.toml`
   - `packages/omlx-model-ornith15-35b-a3b-4bit-vision/release-checkpoints.json`
   - `packages/omlx-model-ornith15-35b-a3b-4bit-vision/META/sbom.spdx.json`
   - `packages/omlx-model-ornith15-35b-a3b-4bit-vision/README.md`
   - 版本断言测试。
2. 把 `ai2apps.json` 和 `service.yaml` 中 Runtime 依赖同时提升为
   `>=1.8.1,<2.0.0`。这是硬性门禁：0.1.5 会导入 1.8.1 新增的动态引擎，不能继续声明
   兼容 1.8.0。
3. 将 `ai2apps/packages/discovery.py` 中 Ornith 的 profile/install legacy 映射版本更新为
   0.1.5，保持旧 Cloud catalog 兼容路径有界；该客户端源码变更进入下一版 Desktop，
   不属于 `.ai2service` 制品本身。
4. 保持现有 checkpoint ID、固定 revision、`distribution_id`、模型字节和准备格式不变。
   本次不重新上传权重，也不重新发布 checkpoint distribution。

## 3. 明确不需要重发的模型 Package

以下模型不含本次必须更新的 Package 自有代码，不得仅为重新锁定 Runtime 而升版：

- `ai2apps/model-deepseek-v4-flash`
- `ai2apps/model-deepseek-v4-flash-2bit`
- `ai2apps/model-deepseek-v41-flash`
- `ai2apps/model-qwen36-35b`
- `ai2apps/model-qwen38-flash-next-4bit`
- `ai2apps/model-glm5-3-flash-4bit-mtp`
- 使用相同 Runtime 公共 Qwen3.6 动态路径的 Qwen3.5-MoE Package。

这些 Package 当前的 Runtime 依赖范围已覆盖 1.8.1。Registry 中出现新版本不会自动改变
本机状态；用户安装 Runtime 1.8.1 并重启 Local 后，Package Manager 应把所有兼容的活动
模型依赖锁原子迁移到新的 Runtime digest。必须验证该迁移，但不应为此重发模型 Package。

Qwen3.8 27B NVFP4 不是 Cached-MoE，Rush/Engine Boost 不适用，也不在本次发布范围。

## 4. 发布前验证门禁

### 4.1 已有源码证据

当前实现已有以下回归证据，发布负责人应在最终 release commit 上重新执行，而不是直接复用
旧日志：

- MoE Boost 专项矩阵：85 passed；覆盖 DeepSeek V4/V4.1、Qwen3.6 文本/VLM、Ornith、
  Qwen3.8 Flash Next、GLM-5.3。
- Engine Pool 与 Model Worker：154 passed。
- `git diff --check` 通过。
- DeepSeek V4.1 同一真实 checkpoint 对照：Blast 实际
  `protected_top=2`、`omitted_tail_routes=220`；Natural 实际
  `protected_top=6`、`omitted_tail_routes=0`。

至少重跑：

```bash
./.venv/bin/python -m pytest -q \
  tests/test_qwen38_boost.py \
  tests/test_qwen36_flesh_model_patch.py \
  tests/test_glm5_boost.py \
  tests/test_adaptive_l1.py \
  tests/test_deepseek_v41_stream_decode.py \
  tests/test_ai2apps_cache_moe_worker.py \
  packages/omlx-model-ornith15-35b-a3b-4bit-vision/tests/test_package.py

./.venv/bin/python -m pytest -q \
  tests/test_engine_pool.py \
  tests/test_ai2apps_model_worker.py
```

还必须运行 Runtime Package、Ornith Package 审计和安装真实 `.ai2service` 后的 managed
Worker smoke；源码可导入不等于正式制品通过。

### 4.2 真实模型验收

发布完成前，应按不同后端至少各做一次真实 checkpoint 的 Natural/Blast 对照，而不是只看
Chat 按钮状态：

1. DeepSeek V4；
2. DeepSeek V4.1；
3. Qwen3.6 文本；
4. Ornith 1.5 VLM；
5. Qwen3.8 Flash Next；
6. GLM-5.3。

若某一后端没有可用 checkpoint，应在发布收据中明确列为未完成门禁，不得写成已经真机
确认。每次对照至少核对：

- 请求的模式与 `engine_stats.mode/requested_mode` 一致；
- Natural 不省略要求保持精确的路由；
- Blast 的 `protected_top`/省略路由符合该模型策略；
- `required_misses`、cache hit/miss、executed/required routes 有实际计数；
- 最终 usage 含 `ai2apps_engine_boost`；
- 生成结束、取消、失败和下一轮请求不会遗留错误会话模式；
- 模型输出正常且没有 Metal 资源、上下文或 Worker 崩溃错误。

## 5. 构建、签名与发布要求

### 5.1 Runtime 1.8.1

Runtime 含原生代码，必须使用以下固定入口：

- `scripts/build_omlx_runtime_dmg.py`
- Apple Developer ID + Hardened Runtime
- `notarytool` 已配置的 Keychain profile 完成公证
- `stapler staple`、`stapler validate` 和 Gatekeeper 验证
- `scripts/build_omlx_runtime_package.py`
- `scripts/publish_signed_registry_artifact.py`

不得关闭 staple、Team ID、签名或 Runtime 结构检查。Runtime 是大型 Package，发布 Cloud
后必须把同一个 `.ai2service` 原字节上传 GitHub immutable Release tag 和 ModelScope
immutable revision，完成 Cloud + GitHub + ModelScope 三源激活。三源必须通过完整 SHA-256、
size、Range 和逐 piece 校验。

### 5.2 Ornith 0.1.5

Ornith 是不含 Native 载荷的普通 Package，使用：

- `scripts/build_signed_registry_release.py`
- `scripts/publish_signed_registry_artifact.py`

模型 checkpoint distribution 沿用现有已发布记录，不新建 distribution。模型 Service
Package 本身较小，可保留 Cloud 单源；若发布负责人增加外部源，也必须上传与 Cloud 制品
逐字节相同的文件并完成标准预检，不能把 checkpoint URL 当成 Package 外部源。

### 5.3 授权边界

- 发布人员必须为本次 `ai2apps/runtime-omlx 1.8.1` 单独取得 Apple 公证授权。
- 如标准脚本确实需要当前管理员浏览器会话，必须取得明确的 Cookie 授权，授权文字应精确
  写明 `ai2apps/runtime-omlx 1.8.1` 和
  `ai2apps/model-ornith15-35b-a3b-4bit-vision 0.1.5`。既往版本授权不得复用。
- 优先使用 `--browser-live`；不得扫描、复制、导出或打印 Cookie，也不得把退出 App 当成
  正常发布前置条件。
- 管理员密码只能由用户在 Account → Security → Administrator verification 中自行输入。

## 6. 发布后验收

Runtime 1.8.1 发布和三源激活后，先在干净 Test/Dev 实例安装并重启 Local，确认：

- Runtime 1.8.1 成为 active provider；
- 既有兼容模型的 immutable dependency lock 原子迁移到 1.8.1 digest；
- Worker startup/readiness/health/stop/restart 正常；
- DeepSeek V4.1 的真实 Natural/Blast 对照仍满足第 4.2 节。

然后发布并安装 Ornith 0.1.5，确认：

- Resolver 选择 Runtime 1.8.1，不能解析到 1.8.0；
- Package 内没有 Mach-O、`.dylib`、`.so` 或其他 Native 载荷；
- Cached-MoE 模式实际实例化 `Qwen36DynamicVLMEngine`；
- 文本和带图请求均正常；Rush Off/On 分别产生 Natural/Blast 的实际引擎统计；
- 卸载、重装和重启后不破坏 checkpoint 与 prepared expert store。

最终发布收据必须分别记录：release commit、Package ID/version、制品 SHA-256/size、Publisher
key ID、submission ID、发布时间和真实安装/推理结果。Runtime 还必须记录 Apple 公证 ID、
DMG 摘要、GitHub/ModelScope source/validation ID、最终 Repository Snapshot digest 与三源
匿名回读结果。

## 7. 完成标准

只有同时满足以下条件，才能把本 handoff 改写为正式发布回执：

- Runtime 1.8.1 已签名、公证、staple、Cloud 发布并完成三源激活；
- Runtime 在干净实例完成安装、重启和兼容模型依赖锁迁移；
- Ornith 0.1.5 在 Runtime 1.8.1 之后发布，依赖下限正确；
- 第 4 节回归和真实模型门禁有可审计结果；
- Cloud/Discover 中两个版本均可解析，Ornith 不会安装到 Runtime 1.8.0；
- 发布收据不包含 Cookie、token、Publisher 私钥或 Apple 密钥材料。
