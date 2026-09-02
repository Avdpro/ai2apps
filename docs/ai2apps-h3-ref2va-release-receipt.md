# AI2Apps H3 Ref2VA 发布收据

日期：2026-08-26

状态：Runtime 1.4.1 与 MiniMax H3 0.8.0 已完成生产签名、Cloud
审核及 Discover 发布。Runtime DMG 已完成 Developer ID 签名、Apple 公证、
staple 与 Gatekeeper 验证。

## Runtime 1.4.1

- Package：`ai2apps/runtime-omlx` 1.4.1
- 变更范围：在已发布的 1.4.0 视频 Runtime 上最小回移 Ref2VA multipart
  支持，将 Worker multipart part 上限由 8 提升到 12；未包含 1.5.x 的 2D
  绘图能力。
- Developer ID：`Developer ID Application: Avdpro Pang (84XL5V265N)`
- Apple submission ID：`11866578-5f9c-4689-8900-fb70ba2aba72`
- Apple result：`Accepted`
- Stapler：验证成功
- Gatekeeper：`accepted`，`source=Notarized Developer ID`
- Stapled DMG SHA-256：
  `9bc745ccd3e3dd8eef9a3f870255d79aa34d5cdcfaaffd6fbdb8ddf5bbdba200`
- Package SHA-256：
  `ef1eea6a648f99b1d1bf51677f900e18d0c9109147241b465e78cfb4d6f0db26`
- Package size：451,928,283 bytes
- Submission ID：`b1518ee0-2609-4726-99b2-9c06d3696720`
- Release status：`published`

## MiniMax H3 0.8.0

- Package：`ai2apps/model-minimax-h3` 0.8.0
- Runtime dependency：`ai2apps/runtime-omlx >=1.4.1,<2.0.0`
- 能力：保留 FL2VA，并加入 Ref2VA 参考图像/视频生成与同步音频；Ref2VA
  checkpoint 提供 Q8 与 Q4 分阶段驻留版本。
- Package SHA-256：
  `08df42e27601551dd245dfea957da7e0df0e18050a5f5f3dbeca71d45438e4b2`
- Package size：102,840 bytes
- Submission ID：`0344cf73-fbca-4a3d-85dc-9294ea9ea712`
- Release status：`published`

## Publisher 与验证

- Publisher ID：`229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Ed25519 public-key fingerprint：
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`
- Runtime：79 个针对性平台测试通过；干净临时环境中的 Runtime/H3 managed
  service 安装与 12-part Worker 边界 smoke 通过。
- H3：14 个针对性测试通过；真实 Q4/Q8 Ref2VA managed-service smoke 与
  Mac/Spark 性能对比通过。
- 发布后 Cloud 回读确认两份 release 均为 `published`。
- 最终 Repository metadata version：55。

管理员浏览器会话 Cookie 的读取授权仅用于上述两个精确 Package/version；
发布后回读完成即终止使用，不得复用于其它任务。
