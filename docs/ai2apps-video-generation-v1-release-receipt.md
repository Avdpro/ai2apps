# AI2Apps 视频生成 v1 签名与公证收据

日期：2026-08-24

状态：Runtime Apple 签名、公证、staple、Gatekeeper 验证，三份 Package 的
AI2Apps Publisher 签名，以及 Cloud Registry 提交、审核和 Discover 发布均已完成。

## Apple Runtime

- Runtime：`ai2apps.runtime.omlx` 1.4.0
- Developer ID：`Developer ID Application: Avdpro Pang (84XL5V265N)`
- Team ID：`84XL5V265N`
- Notary profile：`ai2apps-notary`
- Apple submission ID：`d5c6c0df-5265-4a40-bb36-7dd34219fb2e`
- Apple result：`Accepted`
- Stapler：`validate` 成功
- Gatekeeper：`accepted`，`source=Notarized Developer ID`
- Stapled DMG SHA-256：
  `40a2e4b458de518afeba2b097501532743d884fd7a7ca974ddb210f4665f163b`
- DMG：`packages/ai2apps-runtime-omlx/dist/AI2AppsOmlxRuntime-1.4.0.dmg`

## AI2Apps Publisher

- Publisher ID：`229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Ed25519 public-key fingerprint：
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

私钥只从 macOS Keychain 的既有生产 Secret 读取，没有写入命令行、日志或发布物。

## 正式 Package

| Package | Version | SHA-256 | Size |
|---|---:|---|---:|
| `ai2apps/runtime-omlx` | 1.4.0 | `fc682b45c5636950a4d8ea9a193ed1c45a077dc318693e81a78694d854909e83` | 455,041,289 |
| `ai2apps/model-minimax-h3` | 0.7.0 | `c56915a2b6703942ed316b8976adfc2a15ccab4765ee5f1330a766dd0eba4b27` | 94,844 |
| `ai2apps/model-echomimic-v3-mlx` | 0.1.0 | `19b4bd23e4e15b379de1dbe8c183b30d8c6e8923cf909f61a1e1443b9b337ce5` | 99,951 |

每份 `.ai2service` 都有同路径的 `.envelope.json`。已使用对应生产公钥调用
`verify_signed_package`，完成 Ed25519 signature、artifact digest/size、manifest digest、
Package ID/type/version 的离线一致性验证。

## Cloud Registry / Discover 发布

已按 Runtime → 模型 Package 的依赖顺序发布，并在发布后重新查询 Cloud submission：

| Package | Submission ID | Release status |
|---|---|---|
| `ai2apps/runtime-omlx` 1.4.0 | `df088689-efb2-43a8-8dfb-a8f98e2715a4` | `published` |
| `ai2apps/model-minimax-h3` 0.7.0 | `60d16912-cec2-4247-8787-5d68f8a7fb6c` | `published` |
| `ai2apps/model-echomimic-v3-mlx` 0.1.0 | `d60f49ff-f35e-416d-98ca-0658902de288` | `published` |

最终 Repository metadata version 为 `52`。管理员浏览器会话 Cookie 的读取授权仅用于
这三个指定版本的本次发布，发布后验证完成时已终止，不得复用于其它任务。
