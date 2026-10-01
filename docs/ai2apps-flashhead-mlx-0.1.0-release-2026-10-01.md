# FlashHead MLX 0.1.0 发布记录（2026-10-01）

状态：FlashHead 0.1.0 已正式发布；Lite/Pro 双源权重及 Distribution 已发布。Cloud 阻塞已解决，原始归档与签名保持不变。

## 固定来源

### Lite

Distribution：`dist_ai2apps_flashhead_lite_mlx_2f96aeee_v1`（已发布）。
文件数 11，总字节 8161965386，逐文件 SHA-256 与 ModelScope 固定版本一致。

- huggingface：`Avdpro/FlashHead-Lite-MLX`，revision `2f96aeeeb08795d2a21c4837f5df4e810cc39da2`。
- modelscope：`ai2apps/FlashHead-Lite-MLX`，revision `32f984e38940b07df0ed603de7376941799c1133`。

### Pro

Distribution：`dist_ai2apps_flashhead_pro_mlx_f1909ebd_v1`（已发布）。
文件数 10，总字节 6916079998，逐文件 SHA-256 与 ModelScope 固定版本一致。

- huggingface：`Avdpro/FlashHead-Pro-MLX`，revision `f1909ebd943017292d82249de0c1221f26a08a6b`。
- modelscope：`ai2apps/FlashHead-Pro-MLX`，revision `a207948724e6b4af00a86752572b90c246b11e39`。

## 验证

16 项 Worker/Package 定向测试通过。导出的共享 Runtime Python 3.11.10 / MLX 0.32.0，Apple M5 Max 128 GiB，MLX_ENABLE_TF32=0，未导入 Torch。

| 模型 | 输出帧数 | 总耗时 | MLX 峰值字节 |
| --- | ---: | ---: | ---: |
| Lite | 1500（60 秒） | 99.70988 秒 | 9162855688 |
| Pro | 250（10 秒） | 132.59213 秒 | 11301933802 |

耗时包括加载、生成、编码和媒体回读；峰值仅为 MLX 分配。音频重复至边界前一个采样，验证非整数帧尾部。已检查首秒画面，尚未做跨人物质量评估。

## 正式 Distribution 收据

| 版本 | submission ID | manifest digest | 签名 Index |
| --- | --- | --- | --- |
| Lite | 91607304-d74c-46ec-825a-501db56e41d9 | sha256:a0b70b5fe31537a41a20ae7920213b9c169db1ac274a6f08a3726b0f4e023f99 | 94 |
| Pro | ad69167c-51f7-4b02-a137-dbdbf5aa7c41 | sha256:cfb919ab4baa7b1ec1d7e364412798e35143d899cd1979ec338e51e9f06fd909 | 95 |

两者已审核发布，匿名公网 envelope 与本地签名 JSON 完全一致。验证模式为 metadata_verified：实际下载 HF 固定快照，逐文件大小/SHA-256 与 MS 权威元数据比较；没有宣称双端完整下载或网络故障切换验收。

## 模型归档及 Sandbox 验收

- SHA-256：`9441a6f06dc0a3175f858be678e8eb13d53993fed4ba2c946a220d666a051e69`；59,293 字节。
- Publisher：`229d6350-cd0e-408a-9905-41367385ae5c`；key：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`。派生公钥指纹与 Cloud 一致。
- 源码基线：`e8d5f699202607835010fef1b74614b2181885ba` 加本次未提交工作区改动；归档 SHA 是不可变字节依据。
- 独立实例安装正式签名 Runtime 1.8.5 和本模型归档，Host 校验已发布 Distribution 后导入本地 HF 快照并激活，Sandbox 保持禁网。
- Lite/Pro 都通过真实 multipart Worker HTTP 返回 200，分别生成 50 帧、512×512、25 FPS、含 H.264/AAC 的 2 秒视频；已检查画面。
- 生成中取消返回 409；健康、停止、再次启动、重启和卸载通过，未删除权重。
- 最初 Sandbox 父目录 resolve 探测失败已修复，未扩大权限。16 项回归、Ruff、标准 harness 通过。
- 收据保存在 `packages/ai2apps-model-flashhead-mlx/dist/0.1.0/`；未修改用户 Dev/App-Dev Package 状态。

## 生产发布完成

- submission ID：`9bdace9a-a530-4055-b2d1-a1fd73bd86be`；review ID：`31370848-9b10-4c67-8ccb-c3033ee728e8`。
- 发布时间：2026-10-01 01:09:04（Asia/Shanghai）；Repository Snapshot **227**。
- Cloud OpenAPI 1.55.0 已部署，完整 modelInstall 被接收并投影；Lite/Pro 可选，Lite 默认推荐。没有新增 legacy map。
- 本任务匿名回读公共 catalog，下载归档与本地 59,293 字节完全相同；公网 envelope JSON 与原签名 envelope 完全一致。证据：Package `dist/0.1.0/public-verification.json`。
- Cloud 生产回执记录：370 passed / 0 failed / 2 skipped；旧客户端回归 130/130；Snapshot 227 验签通过；独立客户端可信下载、解析 Runtime 1.8.5、实际安装并激活通过。此次 Cloud 安装验收未下载权重、未重跑推理。
- 本任务保留前述模型推理与 Sandbox 生命周期证据，本轮仅核验发布结果和更新记录，没有重复跑模型推理。
- 本次发布 Cookie 授权已经随发布完成而结束；本轮公网核验没有使用 Cookie。

[Cloud 完整生产回执](/Users/avdpropang/sdk/ai2apps-cloud/docs/flashhead-production-2026-10-01.md) · [客户端对接说明](/Users/avdpropang/sdk/ai2apps-cloud/docs/flashhead-publication-v1.md)
