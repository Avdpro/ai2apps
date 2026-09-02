# Qwen Image 2512 Checkpoint Distribution 发布记录

日期：2026-08-27  
状态：**Cloud 生产已发布并完成公网信任校验**

## Distribution 身份

- Distribution ID：`dist_ai2apps_qwen_image_2512_25468b98_v1`
- Model ID：`ai2apps.model.qwen-image-mlx/2512`
- Hugging Face repo/revision：
  `Qwen/Qwen-Image-2512@25468b98e3276ca6700de15c6628e51b7de54a26`
- ModelScope repo/revision：
  `Qwen/Qwen-Image-2512@ee3f7563eefa997af5a07dbe54a57e5babd3768b`
- Manifest digest：
  `sha256:f52dc0316d06a55585aa9f4b5a58a008a4f6b78227ef3c0841b4fb6f7824cbf5`

## 双源验证收据

- Builder：`ai2apps-local/checkpoint-builder-v1`
- 文件数：28
- Piece size：8 MiB
- Piece 数：6,879
- 总字节数：57,704,574,910
- 已验证来源：Hugging Face、ModelScope
- 结果：选中文件集合、文件大小和逐文件 SHA-256 完全一致；全局规范文件流的
  piece hashes 已生成。

ModelScope 固定 revision 快照保存于本机缓存：

```text
/Users/avdpropang/.cache/modelscope/pinned/Qwen/Qwen-Image-2512/ee3f7563eefa997af5a07dbe54a57e5babd3768b
```

## Publisher 签名

- Publisher ID：`229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Public-key fingerprint：
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`
- Envelope：
  `packages/ai2apps-model-qwen-image-mlx/dist/dist_ai2apps_qwen_image_2512_25468b98_v1.envelope.json`
- Manifest：
  `packages/ai2apps-model-qwen-image-mlx/dist/dist_ai2apps_qwen_image_2512_25468b98_v1.envelope.manifest.json`

签名由现有 macOS Keychain 中的 AI2Apps Production Publisher Ed25519 key 完成；私钥
没有导出、打印或写入发布物。构建器对生成的 envelope 完成了本地自验。

## Cloud 发布结果

Cloud OpenAPI `1.23.0` 已具备 checkpoint submission/review/publication API。Local 发布工具
`scripts/publish_checkpoint_distribution.py` 通过 `dev` App 的临时授权、scoped user session
完成了现有 Cloud 状态机：

- Submission ID：`e5ab2cf1-b045-4177-9aa2-bbbe6d189c93`
- Review ID：`6592620b-57c2-4051-a94d-5d37b8d81bf0`
- 最终状态：`published`
- Published at：`2026-08-27T01:05:48.752Z`
- Checkpoint Index version：2

不携带 Cookie 的公网回读随后通过 Local pinned Repository key 完成验证：Index 签名、
Publisher/key、manifest digest 均有效，Index 只包含本 distribution，公网 envelope 与本地正式
envelope JSON 完全一致。

临时 Cookie 授权仅用于本 distribution 的身份核对、提交、审核、发布和最终状态检查；公网回读
不使用 Cookie。上述步骤完成后授权终止，Cookie 值未打印、复制或持久化。

Qwen Image Model Package 同时包含 Image-2512 与 Edit-2511。只有 Edit-2511 的独立
distribution 也完成同等级验证和发布后，才能为 Package 的全部 `models[].weights` 写入真实
`distribution_id` 并整体升版；本次没有用占位值或发布半绑定 Package。
