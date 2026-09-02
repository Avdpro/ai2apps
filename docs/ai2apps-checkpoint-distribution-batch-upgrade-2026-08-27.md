# AI2Apps Checkpoint Distribution 批量升级记录

日期：2026-08-27  
状态：**6 个 distribution 与 6 个升级 Package 均已发布并完成最终回读**

## 范围判定

本批次只纳入同时满足以下条件的 checkpoint：

1. 本机存在与 Package 固定 Hugging Face revision 对应的完整运行快照；
2. ModelScope 存在公开镜像，且已解析为不可变 Git commit；
3. 运行文件的路径、大小和 SHA-256 与 Hugging Face 快照一致；
4. 许可允许按原条款分享模型文件。

ModelScope 自动增加的 `.gitattributes`、`configuration.json` 或不同的
`README.md` 不进入运行文件清单。Qwen3.6 35B 的本机快照只有配置与索引、没有实际
权重分片，因此不属于本批次，不能把“存在 snapshot 目录”误当成完整缓存。

## 已生成的 distribution

| Package / model | Distribution ID | Manifest digest | 文件 | 8 MiB pieces | 字节数 |
| --- | --- | --- | ---: | ---: | ---: |
| Qwen Image Edit 2511 | `dist_ai2apps_qwen_image_edit_2511_6f3ccc0b_v1` | `sha256:5e5d1759dc612c1695889683cec7c609e1b14984a8a819bab79bee9cb4705fde` | 33 | 6,881 | 57,720,454,694 |
| DeepSeek V4 Flash | `dist_ai2apps_deepseek_v4_flash_60d8d707_v1` | `sha256:f6d820f29faf91bbcb25d6ebd9bbc339c93cdbb81291920ddc38757da784d5b3` | 68 | 19,030 | 159,630,016,721 |
| DeepSeek V4 Flash 2bit DQ | `dist_ai2apps_deepseek_v4_flash_2bit_dq_722bf559_v1` | `sha256:36467481b77f0ce2cb417cc4e93f0087476fdd187a08fec3d145ab742703235a` | 25 | 11,508 | 96,531,101,948 |
| Qwen3 TTS 0.6B CustomVoice 6bit | `dist_ai2apps_qwen3_tts_0_6b_custom_voice_6bit_7dc92af1_v1` | `sha256:b481df3b3cbd790d1ab48756ee496eb8f7b275388745c89a01a6455224a6d90c` | 12 | 219 | 1,833,587,721 |
| Qwen3.8 27B NVFP4 | `dist_ai2apps_qwen3_8_27b_nvfp4_16b6615a_v1` | `sha256:17f3284c174cb3de0cc66eacb891cbfeb5d0f53ce8fce1900dd52b91e4041fb6` | 11 | 2,795 | 23,444,503,536 |
| SenseVoice Small | `dist_ai2apps_sensevoice_small_8ddd966b_v1` | `sha256:c0fca7db819750fec981206c0a847fa897e37d2d1a8c08d5dad10fae7ceb5e3c` | 4 | 112 | 936,489,185 |

所有 envelope 均使用
`ai2apps-local/checkpoint-metadata-verified-v1`：只读取一份本地 Hugging Face
checkpoint 来生成文件和 piece hashes，再以固定 ModelScope commit 提供的逐文件
SHA-256 元数据验证第二来源，不重新下载第二份权重。

## Package 升级顺序

1. 使用当前 dev App 的 scoped Cloud session 提交以上 6 个 envelope 并申请审核；
2. 管理员审核通过后逐个发布；
3. 使用无 Cookie 的公网信任路径逐个回读，验证签名 Index 和 envelope 完全一致；
4. 给对应 `service.yaml` 的 `weights` 增加 `distribution_id` 和固定 ModelScope 来源；
5. 同步提升 `service.yaml`、`ai2apps.json` 版本；
6. 构建、审计并发布 6 个模型 Package。Qwen Image Package 同时绑定已经发布的
   Image 2512 distribution 和本批次的 Edit 2511 distribution。

根据发布手册，在 distribution 公网发布并回读成功前，不得提前把 Package 指向尚未
存在的 Registry ID。

## Cloud distribution 发布收据

最终签名 Checkpoint Index 为版本 8，共 7 条记录（含此前发布的 Qwen Image 2512）。
以下 6 个 submission 均为 `published`，无 Cookie 公网回读均返回
`envelopeExactJson: true`：

| Distribution | Submission ID | Review ID |
| --- | --- | --- |
| Qwen Image Edit 2511 | `4eb135bd-7e57-4385-8022-9f53db143cde` | `803a2c64-ef82-4316-a7ed-40ab944cd4e8` |
| DeepSeek V4 Flash | `a039f3ce-a4b5-40aa-a3a3-877f976b73ac` | `09af7fb5-fe58-47a2-b88c-c454edc4ac87` |
| DeepSeek V4 Flash 2bit DQ | `7aaa4d89-a418-46da-89e7-1b34e6f95215` | `5c5ee4ab-d74f-4b23-a5ab-f3774809ce20` |
| Qwen3 TTS 0.6B CustomVoice 6bit | `e346fe25-1f9a-49d0-b306-e492185b71aa` | `ed7ad518-4c21-49e8-9995-9df9340d9003` |
| Qwen3.8 27B NVFP4 | `cd55bd38-e88e-4700-9f86-4963f4b25375` | `212a3d44-bbd3-4ec4-b31b-e7c16bfc6afc` |
| SenseVoice Small | `b07f47a6-b6c9-4b6c-91c6-c1c2283d58f2` | `ec3600e8-8ec1-4723-bd11-7d28bdb31d0c` |

## Package 构建收据

| Package | 版本 | Artifact SHA-256 | 字节数 |
| --- | --- | --- | ---: |
| `ai2apps/model-qwen-image-mlx` | `0.1.1` | `7ea94db188934ce4fa0a4b754a4a1d2579561fcf722a7e96a99caa9025cac4dc` | 19,100 |
| `ai2apps/model-deepseek-v4-flash` | `0.3.2` | `78856a1a857c413e3b08a3e4ced8a144d83c86be3dbf314ea275f461709319ef` | 50,153 |
| `ai2apps/model-deepseek-v4-flash-2bit` | `0.3.2` | `170e382c4f3d466113787dbdb4ff8cf429c06b657650fb19d05398c80c9f77fd` | 50,337 |
| `ai2apps/model-qwen3-tts-06b` | `0.2.1` | `3333d5ca0b30053d79e4a55a84527f323b10c637693e7a73d92bb4594c3b070e` | 4,826 |
| `ai2apps/model-qwen38` | `0.3.2` | `5bc6724c220e71b407c871db6988f11bf080906169794962bebd6315e1352f9f` | 14,284 |
| `ai2apps/model-sensevoice-small` | `0.2.2` | `21dc66df0ec482aae29c49a8479a19865e61307b00274e40aae51cdf221e9d5d` | 9,338 |

每个 artifact 的 Package/service/SBOM 版本一致，签名 envelope digest 与 artifact
字节一致，Package policy 通过，且 archive 中不包含模型权重。

## Cloud Package 发布收据

以下 6 个 Package submission 均已通过审核并发布。最终回读确认
`releaseStatus: published`，Artifact SHA-256、Publisher
`229d6350-cd0e-408a-9905-41367385ae5c` 和 Publisher key
`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc` 均与本地构建收据一致。该批次完成后，Package
Repository Metadata 最新版本为 67。

| Package / version | Submission ID | Review ID |
| --- | --- | --- |
| `ai2apps/model-qwen-image-mlx 0.1.1` | `59368bc2-87c7-4df8-a544-c34c032a91ec` | `a73861f3-424f-4cc1-95be-a0293ca51385` |
| `ai2apps/model-deepseek-v4-flash 0.3.2` | `3ca28b09-44bd-43eb-a85a-79ba94974409` | `a8719ec2-3165-4d84-866c-8d24cca68a82` |
| `ai2apps/model-deepseek-v4-flash-2bit 0.3.2` | `f00a09e1-58a2-43a3-a7e9-06751f0baa89` | `d687a86e-4645-425f-89e9-43bc30db86b9` |
| `ai2apps/model-qwen3-tts-06b 0.2.1` | `24c2a8bf-aeb9-40fa-921a-c7eccb4006f9` | `2d0ac9a1-a9b3-4314-b686-83862cb22ecd` |
| `ai2apps/model-qwen38 0.3.2` | `5c3fe8c9-bb76-4396-a379-6e65dd12954d` | `2b363de7-5248-44be-a4d1-9490d1b26ef9` |
| `ai2apps/model-sensevoice-small 0.2.2` | `b84a55d2-3b3e-4124-b23f-ca0231c82016` | `f80cbcb0-059e-447f-b042-9a4aa6fd5e55` |

最终回读使用用户仅为上述 6 个 Package/version 授权的当前 dev App scoped Cloud
session Cookie。回读完成后该次授权立即失效，未复制、输出或保存 Cookie。

为兼容已有缓存，安装器会先按 Registry manifest 验证固定 HF snapshot，再使用 APFS
copy-on-write clone 导入可信 distribution cache；匹配时不访问 Hub，也不会改变原 HF
文件权限。只有缺失或不匹配时才进入双源下载。

## 本地验证

- checkpoint distribution / acquisition / installer / Package policy：32 项测试通过；
- Package、模型适配器、音频、Runtime dependency：99 项测试通过；
- Ruff：通过；
- `git diff --check`：通过；
- headless 环境退出时的 Metal device 提示与 checkpoint 流程无关。
