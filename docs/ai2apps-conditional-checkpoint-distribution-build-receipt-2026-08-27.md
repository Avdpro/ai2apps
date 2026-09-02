# Fish S2 Pro / Ideogram 4 条件式 Checkpoint 构建收据

日期：2026-08-27  
状态：Cloud 生产已发布并完成公网信任校验

## Cloud 前置条件

Cloud 生产已部署 OpenAPI `1.25.0`，支持 Publisher 签名的
`redistributionPolicy=conditional`、`redistributionConditions`、`downloadConsent`、
`termsText` 校验以及条件式 distribution 的 P2P 禁止规则。

## Publisher

- Publisher ID：`229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Public-key fingerprint：
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`
- 私钥仅在 macOS Keychain 内部用于签名，未导出、打印或写入发布物。

## Fish Audio S2 Pro BF16

- Distribution ID：`dist_ai2apps_fish_s2_pro_bf16_eccd57bf_v1`
- Manifest digest：
  `sha256:3cc468c4825aed9d65f61dc51929e37d316b793f0d550d6cc73d9ea1b79d2489`
- 总字节数：`11,007,899,848`
- 文件数：`10`
- Piece size：`8 MiB`
- Piece 数：`1,313`
- Builder：`ai2apps-local/checkpoint-metadata-verified-v1`
- Envelope：
  `packages/omlx-model-fish-s2-pro/dist/dist_ai2apps_fish_s2_pro_bf16_eccd57bf_v1.envelope.json`
- Submission ID：`45f072a0-536b-4393-bcf1-3b56477bf600`
- Review ID：`a96cc2d5-4959-4397-9f6e-435a0ba1f4c5`
- Published at：`2026-08-27T08:26:32.497Z`

## Ideogram 4 FP8

- Distribution ID：`dist_ai2apps_ideogram4_fp8_bbee2ab2_v1`
- Manifest digest：
  `sha256:72cfd9249e45740e3a2d3903f6cf1be46456068086887f2aec7f84bc7cc13800`
- 总字节数：`29,486,331,382`
- 文件数：`4`
- Piece size：`8 MiB`
- Piece 数：`3,516`
- Builder：`ai2apps-local/checkpoint-metadata-verified-v1`
- Envelope：
  `packages/ai2apps-model-ideogram4-mlx/dist/dist_ai2apps_ideogram4_fp8_bbee2ab2_v1.envelope.json`
- Submission ID：`57c2c0f9-deb0-44d7-a58b-1880e0fa4a92`
- Review ID：`c54eb6af-acc8-4053-8769-33a13354e863`
- Published at：`2026-08-27T08:26:26.352Z`

## 验证结论

两项构建均复用已有固定 Hugging Face revision 快照。Builder 读取本地 HF 字节生成全局
piece hashes，并从 ModelScope 固定 revision 获取权威文件元数据；选中文件集合、大小和逐文件
SHA-256 完全一致，因此没有重新下载 ModelScope 权重。两份 envelope 均携带签名的许可 URL、
terms hash、用途与再分发限制、署名要求以及下载前用户确认声明；P2P 为关闭状态。

## Cloud 发布与公网回读

两项 submission 均通过审核并达到 `published`。最终不携带 Cookie 的公网验证结果：

- Checkpoint Index version：`28`
- Index record count：`27`
- 两项 Index 记录的 Publisher ID、Publisher key ID 和 manifest digest 均与本地发布物一致；
- 两个公网 distribution envelope 均通过 Publisher 签名验证；
- 两个公网 envelope 与本地正式 envelope 的 JSON 完全一致。

dev App scoped Cloud session Cookie 仅用于本次两项 distribution 的查询、提交、审核、发布和
最终状态回读；Cookie 值未输出、复制或持久化。公网信任验证不使用 Cookie，完成最终回读后
本次 Cookie 授权即终止。

## Package 0.1.1 升级

两个模型 Package 已升至 `0.1.1`，分别绑定上述已发布 distribution。Ideogram Package 同时
把 ModelScope mirror 从可变的 `master` 改为 distribution 已验证的不可变 revision。

| Package | Version | Artifact SHA-256 | Size | 状态 |
| --- | --- | --- | ---: | --- |
| `ai2apps/model-fish-s2-pro` | `0.1.1` | `c7c4b14b0bf5533571d00b51eabf9568765be1dd30f3be90fa7209b6b9d6bfca` | 10,587 | published |
| `ai2apps/model-ideogram4-mlx` | `0.1.1` | `d2ca21e446186d289e11ec52bef34101557846cef79f5239dd70e283b7a0dead` | 3,803,338 | published |

Package、Checkpoint policy 与 Contract 回归测试共 51 项通过；两个归档内的版本、
`distribution_id` 和 Ideogram resolved ModelScope revision 已回读确认。

生产发布结果：

- Fish submission：`8ff4ebe2-f9eb-4f9e-a06e-8887f3677c23`；review：
  `4eb1ec96-ed66-47b4-a20c-449116af220d`；
- Ideogram submission：`7a87a34e-e2f0-45fc-9ba1-90ceb3838aa6`；review：
  `69079479-c6e4-49ee-9c2c-1c058cc250e5`；
- 最终 Repository metadata version：`82`；
- 空 session store 的公开 Registry 路径重新下载了两个 artifact，并验证 Repository 签名、
  Publisher identity/envelope、artifact 大小和 SHA-256，结果均与本地正式发布物一致。

dev App scoped Cloud session Cookie 仅用于这两个 Package/version 的查询、提交、审核、发布和
最终状态回读；Cookie 值未输出、复制或持久化。无 Cookie 公网验证完成且最终状态回读后，
本次授权即终止。
