# Knowledge RAG Runtime 发布通道支持需求

状态：阻塞正式发布；2026-10-30。

## 现状与复现

当前 Registry 中没有 `ai2apps/runtime-knowledge-rag` 与 `ai2apps/service-knowledge-lancedb` 的可安装版本。Dev 历史本地安装不等于 App-Dev 可从 Registry 安装。

已准备同一既有 AI2Apps Publisher/key 签名的候选：

- `ai2apps/runtime-knowledge-rag` 0.1.1，203710397 字节，SHA-256 `1baaef1c2cd5571ffddd4d059ce15f98598ec6bbfade2560016a90e725c0c986`。复用既有不可变 Runtime 内容；内层 Developer ID DMG 的 staple 与 Gatekeeper assessment 已通过。
- `ai2apps/service-knowledge-lancedb` 0.1.0，10047 字节，SHA-256 `557ef524af63adad412f358a1b3fc3f28a667629ed12b0e934ddba2290163317`。Contract 与 Service 均声明 Runtime >=0.1.1,<1.0.0，Python >=3.11,<3.12，与内置 Python 3.11 对齐。

当前 Local 标准 RegistryPackageManager.submit 对前者抛出 `artifact_size_limit: Package submissions are limited to 25 MiB`。`PLATFORM_RUNTIME_PACKAGE_IDS` 目前仅含 runtime-omlx/runtime-cuda-torch；不能通过改包名、拆分工件或移除依赖规避。预检未提交网络请求，无新 submission ID，LanceDB 未提前发布。

## Cloud 需要的支持

1. 核对生产 Runtime 上传能力 API 与 `/v1/platform-runtime-submissions` 支持范围，显式支持官方 `ai2apps/runtime-knowledge-rag` service Runtime，允许当前约194.3MiB候选上传。沿用既有 Runtime 大包上限与严格有界分块 IO。
2. 继续强制官方 Publisher/key 授权、管理员 step-up、envelope/完整 SHA-256/size 校验、审核、不可变 package/version 规则。Apple 原生载荷的 Developer ID/公证/平台约束不可放宽。
3. 更新生产 `/v1/registry/runtime-upload-capabilities`，使 Local 能按已部署能力对齐路由。普通 Package 的25MiB上传上限不变。
4. 新发布依然生成签名 Repository Snapshot，允许 LanceDB 与已发布 E5 Package 按版本依赖解析此 Runtime；不直接写 Release 表或手工改签名元数据。

## Local 后续与验收

Cloud 部署后，Local 同步此精确官方 Runtime ID 的标准上传支持与测试，不添加第二条发布实现。继续使用 scripts/publish_signed_registry_artifact.py。先发布 Runtime 并匿名验证，再发布 LanceDB。实际发布前仍需完成最终工件干净安装/managed-service smoke；当前8项Runtime单元回归不替代这些验收。发布后通过真实 Registry 下载、验签、审计、依赖安装、LanceDB upsert/search/delete、E5真实Embedding、已有知识补建索引验收，并补充Runtime多源发布。

候选与证据目录：`ai2apps/.build/knowledge-rag-release/`。没有读取、输出或保存 Cookie/私钥；标准脚本仅在内存使用 Dev 在线会话。
