# AI2Apps MiniMax H3 Q4 扩展发布收据

日期：2026-09-07
状态：四个 Checkpoint Distribution 与 `ai2apps/model-minimax-h3 0.9.0`
均已发布，并完成匿名公网信任回读。

## Checkpoint distributions

| 模型 | Distribution ID | Manifest digest | 文件 | 8 MiB pieces | 字节数 | Submission / Review |
| --- | --- | --- | ---: | ---: | ---: | --- |
| LightX2V 4-step Q4 | `dist_ai2apps_minimax_h3_lightx2v_4step_overlay_2f015e66_v1` | `sha256:a708e7099c065964e10275ff49386373601424e3ea0f822b93dee113971621f1` | 2 | 165 | 1,383,679,204 | `1ac54d4b-1250-4757-a4c8-b286ff26a3bf` / `9e0aa793-39db-4b93-89d9-27df9e8454e8` |
| LightX2V 8-step Q4 | `dist_ai2apps_minimax_h3_lightx2v_8step_overlay_2f015e66_v1` | `sha256:88aae9c55a9696f8e78e52e28fd7fb15002aee7efa89fe380459e726902df787` | 2 | 165 | 1,383,679,204 | `b45bfe29-ef71-408b-b09c-886cf86dc086` / `762031db-f6d1-486f-91c1-51adce13af85` |
| OpenVDN DMD8 Q4 | `dist_ai2apps_minimax_h3_openvdn_dmd8_overlay_751739ee_v1` | `sha256:d7dcfb49607453f9ebb293a4d9ed2f2804a24dfb13d04a7a2dcf736b984a28d8` | 10 | 652 | 5,464,981,575 | `c4f5e9ba-cecc-4f60-bc86-28ed849ed115` / `1e484d61-6d39-4dcc-a96e-e2c6f1354668` |
| OpenVDN Stage-B 50 Q4 | `dist_ai2apps_minimax_h3_openvdn_stageb50_overlay_751739ee_v1` | `sha256:32c332c24a09a6f06e62fa6c15013819fb0b1fb9d6061c030ac9a44b42e1eaac` | 8 | 550 | 4,613,482,149 | `cf47c670-c3bd-4ba8-8f60-51d9bba305e8` / `abb4dcb7-da54-4700-96c5-bb8721b5c4a3` |

LightX2V 固定 Hugging Face revision
`2f015e66b37c585cea9dc4ae6f1850ea8788e742` 与 ModelScope revision
`64c400e5c883491d01b353317e122c8aa5a49ae9`。OpenVDN 固定 Hugging Face
revision `751739ee5b9e3ac802dca5d5111075fdaeb47885` 与 ModelScope revision
`6fa438b20876d27b8b54617062236c12ce993bfd`。

四份 distribution 均由
`ai2apps-local/checkpoint-metadata-verified-v1` 构建；选中文件在两个 Hub 的
路径、大小和逐文件 SHA-256 完全一致。LightX2V 按 Apache-2.0 公开分发；OpenVDN
携带 MiniMax H3 Community License 条件式再分发、条款交付、地域/单独许可确认与署名要求，
且禁用 P2P。最终 Checkpoint Index 为 v59，四份匿名回读均为
`envelopeExactJson: true`。

## Package 0.9.0

- Package：`ai2apps/model-minimax-h3 0.9.0`
- Runtime dependency：`ai2apps/runtime-omlx >=1.4.1,<2.0.0`
- Artifact：
  `/Users/avdpropang/sdk/minimaxh3/ai2apps-package/dist/ai2apps-model-minimax-h3-0.9.0-production.ai2service`
- Artifact SHA-256：
  `a9650eb388052e6df0e6f745d53ec8bf852f89979c24c95f1502016d66bede44`
- Artifact size：141,000 bytes
- Manifest SHA-256：
  `b329c27a9adab5b9e019840f592ec4dcf4160875033c65989336ae54ed2de9e9`
- Envelope SHA-256：
  `7d16b3fc4a26c20eacc423885059b4d4b721c6da062b9bb9d0c4aebc4b4647e2`
- Submission：`bef373aa-d11a-4175-876a-dfa33c62a6d8`
- Review：`f1c9a47b-7de8-45d4-8116-bb24dd94bc65`, approved
- Release status：`published`
- Repository metadata version：123

Package 保留 FL2VA/Ref2VA Q4 与 Q8，并增加四个独立可选的 Q4 overlay 模型。
每个 overlay 通过 `required_model_ids` 复用 FL2VA Q4；权重不进入 Service Package。
Worker 在 DiT 加载阶段动态合并 LoRA，并按模型挂接 OpenVDN branch，随后继续沿用分阶段驻留。

源码携带完整的 discovery、modelProfile 与 modelInstall 声明；正式 artifact 签名覆盖
discovery/modelProfile。生产 Cloud 当前尚不接受顶层 modelInstall，因此正式 artifact 通过标准构建器的
`--omit-model-install-catalog` 兼容选项省略该可选投影；客户端使用精确到 0.9.0 的显式
legacy install map。Cloud 支持该字段后应恢复默认构建。

## ACPF 与验证

- Video Studio 新增四个显式 profile：LightX2V 4-step、LightX2V 8-step、OpenVDN
  DMD8、OpenVDN Stage-B 50；均要求 Package `>=0.9.0,<1.0.0`。
- 原 H3 Q8/Q4 推荐优先级保持不变，新 profile 仅在用户选择相应模型时触发独立下载。
- H3 MLX/Worker：35 tests passed。
- ACPF、Discover、Package Contract 与发布工具：74 tests passed。
- Cloud 兼容构建器专项：30 tests passed（包含在上述回归执行记录中）。
- Ruff 与发布范围 `git diff --check`：通过。
- 动态 LightX2V 与 OpenVDN smoke 均输出有效 H.264/AAC MP4 和 32 kHz stereo audio；
  LightX2V 512x288、5 秒、4-step 的模型时间为 44.29 秒。
- 干净匿名 Registry client 验证 Repository v123、Publisher 签名与固定制品摘要；公网
  artifact 与本地制品逐字节一致，envelope JSON 完全一致。

Publisher ID 为 `229d6350-cd0e-408a-9905-41367385ae5c`，Publisher key ID 为
`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`，公钥指纹为
`216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`。
本次授权的当前 AI2Apps dev app-shell Cookie 仅用于上述四个 distribution 与该精确
Package/version 的查询、提交、审核和发布；没有输出、复制或持久化 Cookie、Cloud token、
管理员密码或 Publisher 私钥。匿名验证完成后，本次 Cookie 使用授权终止。
