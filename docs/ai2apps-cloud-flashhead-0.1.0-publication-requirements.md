# FlashHead 0.1.0 Cloud 发布阻塞与变更需求

日期：2026-10-01。**已完成**：Cloud OpenAPI 1.55.0 已生产部署，FlashHead 0.1.0 已按原始归档发布，Snapshot 227。本仓库未修改 Cloud 代码。

生产结果见 [本地发布记录](ai2apps-flashhead-mlx-0.1.0-release-2026-10-01.md)；下文保留原始交接需求，不再是当前阻塞。

## 已验证的阻塞

标准 `scripts/publish_signed_registry_artifact.py` 提交 `ai2apps/model-flashhead-mlx` 0.1.0 时，生产 Cloud 返回：

> Package manifest schema validation failed: / must NOT have additional properties

失败发生在 `manager.submit()`；随后标准 `--list-only` 查询未发现该 Package submission。错误未列出具体额外属性。完整签名归档包含 `discovery`、`modelProfile`、`modelInstall`；与既有 Cloud discovery schema 缺口一致，应由 Cloud 校验器确认并返回具体 JSON Pointer。Local Contract 校验、签名、16 项测试、真实 Sandbox 安装与两版推理均通过。

FlashHead 没有已向客户端下发的版本有界 legacy install map，因此不能仅删去 `modelInstall` 以通过当前 Cloud。保留完整声明、Package ID 和 0.1.0 版本；没有提交成功或覆盖已发布模型归档。

## 待 Cloud 完成

1. 按 `docs/ai2apps-cloud-package-discovery-schema-requirements.md` 支持完整模型投影，具体以本次归档 manifest 为验收夹具。
2. 接收并原样保留已签 `modelInstall`：serviceKey 为 `ai2apps.model.flashhead-mlx`，models 为 `/lite` 和 `/pro`，仅 Lite 的 recommended 为 true。核对每个模型都存在于签名 service.yaml 并绑定已发布权重 Distribution。
3. 保持签名、文件索引、摘要、依赖和平台校验；拒绝未知额外字段，错误返回具体字段路径。
4. 在提交、审核、发布、公开详情及签名 Repository Snapshot 全链路保留三个投影字段，不重写 Publisher 签名内容。
5. 返回部署版本及 schema 验收证据；用本次原始字节重试标准发布链路。

## 固定发布物

- Package：`ai2apps/model-flashhead-mlx` 0.1.0。
- 归档：`packages/ai2apps-model-flashhead-mlx/dist/0.1.0/ai2apps-model-flashhead-mlx-0.1.0.ai2service`。
- SHA-256：`9441a6f06dc0a3175f858be678e8eb13d53993fed4ba2c946a220d666a051e69`；59,293 字节。
- 同目录 `.envelope.json` 是既有 AI2Apps Publisher 签名。
- Runtime 依赖：`ai2apps/runtime-omlx >=1.8.5 <2.0.0`；1.8.5 已发布。
- Lite Distribution：`dist_ai2apps_flashhead_lite_mlx_2f96aeee_v1`，已发布。
- Pro Distribution：`dist_ai2apps_flashhead_pro_mlx_f1909ebd_v1`，已发布。

## 恢复步骤

先用标准脚本查询已有 submission；如出现 submission，使用其 ID 恢复，禁止重复提交。若仍无 submission，使用以上原始 artifact/envelope 提交。发布后验证公网原始字节及签名、Discover 两版模型安装选择、依赖解析和实际安装。当前 Cookie 授权只覆盖本次 FlashHead 发布；会话过期时由用户在 Dev 中重新登录或管理员验证，不读取其他实例。
