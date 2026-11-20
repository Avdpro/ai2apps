# H3-Image 参考图接入与验收（2026-11-21）

## 本地模型

原 H3-Image 0.1.0 已有 `image_edit` 和最多 16 张参考图的原生管线，外层适配器和能力声明限制为 1 张。原源码没有出现在当前 checkout；已从原始签名制品恢复维护源，制品 SHA-256 为 `b9dec1ceb5ce52ef6d2bc8aeca0a454273c728074bb570c45f3388b3d5525b19`，保留许可证、SBOM 和来源。

0.1.1 扩展外层适配器与能力声明到 1–16 张，保持顺序与单参考缓存行为。继续使用 `MiniMaxAI/MiniMax-H3-Image@5f90473023975e6271b0ed1dd84c4e88e4bbc6d3` 和原 distribution `dist_ai2apps_minimax_h3_image_5f904730_v1`；共享 H3 4-bit 编码器与依赖保持不变。

不需要新 checkpoint 或格式转换。调查中曾准备下载另一套转换权重，但请求在许可检查阶段返回 403，未下载该大模型，随后停止这条不必要的路径。

真实原生 MLX 双参考实测：图 1 红圆、图 2 蓝方块，512×512、seed 42、6 steps，59.63 秒；结果符合左右顺序及颜色要求。证据在 `artifacts/acceptance/h3-multi-reference-20261121/`。签名包受管 Worker 和 Registry 安装证据另行记录，原生直接调用不冒充完整安装验收。

## BYOK 范围

按用户最终要求，本次不接入 MiniMax 图片 BYOK API，已移除本轮新增的图片 Provider、目录和请求适配分支。现有视频 BYOK 配置不变；以后接入图片 API 时，应复用同一用户已有的 MiniMax BYOK 凭据，不要求另配一份。未执行真实图片 BYOK 请求。

## Studio / AaAT

参考图创作最多 16 个输入，Slot 数量按当前模型真实上限决定。AaAT `image.reference_creation.artifact_ids` 的 effective schema 同样按模型上限调整。旧 GPT 路由仍限制 4 张；本地模型描述符不再丢失 `inputs.reference_images`。单图修图和其它 Mini-App 保留自己的业务输入数量。

本地适配器、数量/顺序、AaAT 参数协商、旧 BYOK 分辨率契约和签名完整性检查共 34 项通过；前端 Slot、既有 BYOK 目录和视频分辨率检查通过。真实模型验收为双参考图，16 张上限使用夹具验证。

## 离线候选验收

签名候选通过真正的 Ed25519 验签、兼容检查、用户批准的 Package 审查后，使用独立 `publisher-signed-contract-v1` 类型安装。安装后重新校验原始签名、已信任且未撤销的 Publisher/key 以及全部展开文件；不伪称候选已有 Repository 发布记录，不按旧版 archive 解析。正式 Registry 安装链路保持原有信任类型。

## 发布结果

`ai2apps/model-minimax-h3-image` 0.1.1 已发布，Registry 元数据版本 410。发布后从公开 Registry 完整下载、签名与依赖验证、干净实例安装、能力发现、受管 Worker 真实双参考推理及卸载全部通过。回执见 `artifacts/acceptance/h3-multi-reference-20261121/package-release-receipt.json` 与 `registry-install-receipt.json`。
