# AI2Apps oMLX Runtime 1.7.9、VoxCPM2 与 IndexTTS 2.5 发布收据

日期：2026-09-22（Asia/Shanghai）

## 发布范围

- 源码基线：`61da0fc6a87d4f743d312c8ae1987d1d1b7babb8`
- Publisher：`229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher key fingerprint：
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

本次按依赖顺序发布 Runtime、三份 checkpoint distribution、VoxCPM2 Package 和
IndexTTS 2.5 Package。生产 Cookie 只用于这里列出的精确版本，最终公开回读完成后授权
失效；收据未保存 Cookie、token、私钥或 Apple 凭据。

## Runtime 1.7.9

- Package：`ai2apps/runtime-omlx 1.7.9`
- Artifact SHA-256：
  `cb241db96d4d2b55aecda18359ae9dbc2567246d7120ff2e3b3b3d7d576cfb85`
- Artifact size：`381837318` bytes
- Cloud submission：`79e41c74-d0f0-46fc-84e7-209028d01b97`
- Apple notarization：`46a461c9-495f-4ca4-88d8-b56f14af4a0b`，`Accepted`
- Stapler 与 Gatekeeper：通过
- 内嵌公证 DMG SHA-256：
  `8a8085cf4ce3701a0bacc44831a05aff3e0182ad75cf546bce93037e80faf41f`
- 内嵌公证 DMG size：`384501033` bytes

不可变外部源：

- GitHub tag：`package-runtime-omlx-v1.7.9`
- GitHub source：`src_2a750e8e-3bda-4e8a-9afc-7382eced248d`
- GitHub validation：`val_d4bb400c-b2be-4b0d-b6e3-dbb5757ade24`
- GitHub validation digest：
  `3866674650c591daedecff61b4ddbcd3f100344578e5a724583f33fb903f7450`
- ModelScope revision：`59b3ff1991caa329dde4ef0b56145a23f9cb27ae`
- ModelScope source：`src_fc06141a-b4a6-47b6-8f69-91159bf767a1`
- ModelScope validation：`val_83cfcf57-669f-4334-bf5b-59761c531954`
- ModelScope validation digest：
  `725660a5abfaf59c1621dddc163d6ddaa69bdbe5547565342fa371a307cac6cc`
- 最终 source revision / ETag：`6` / `"sources-6"`
- 激活 ModelScope 后的 Repository Snapshot digest：
  `fcb66b0df6b9dca271e746a2c203167eb886533b6e2ee0fa1954ff01eaa6c443`

Cloud、GitHub、ModelScope 三个源最终均为 `active`。两个外部源均通过完整大小、
SHA-256、Range 和 46-piece manifest 校验。

## Checkpoint distributions

| 模型 | Distribution | Revision | 文件/分片 | 字节数 | Manifest digest | Submission |
| --- | --- | --- | ---: | ---: | --- | --- |
| VoxCPM2 4-bit | `dist_ai2apps_voxcpm2_4bit_dc9e5c1_v1` | `dc9e5c187858da5f4a13dc4c247e297339216381` | 5 / 275 | 2300904017 | `sha256:b0a05bd664ec3376c21d63aac5dcf3e8c51a1a372a73ab281f05f433f03651d6` | `c39763d5-1a15-4e9a-8987-309d1e24373d` |
| VoxCPM2 8-bit | `dist_ai2apps_voxcpm2_8bit_d5272589_v1` | `d52725898a0675703f7f9ddc5a4d1a3cdbb99032` | 5 / 385 | 3225461623 | `sha256:0164fa2a2d812cb61546e2b5c805617573512a0dba8bb9a07f01f5760908803d` | `c1e7e1c9-650c-4241-b199-6ede8fd2bb07` |
| IndexTTS 2.5 FP16 | `dist_ai2apps_mlx_indextts25_01d27e6d_v1` | `01d27e6d8a0c628859abe2142a0fd431b91e79af` | 15 / 398 | 3338231798 | `sha256:da5b7bcef6351700539cad9a904c2d42481218602364a6469a6fda03e7a032d8` | `5d5e162b-38bf-455f-b25e-4d06586ee581` |

三份 distribution 的公开 envelope 均与本地签名 JSON 完全一致。IndexTTS checkpoint
双源为 Hugging Face `Avdpro/MLX-IndexTTS-2.5` revision
`01d27e6d8a0c628859abe2142a0fd431b91e79af` 与 ModelScope
`ai2apps/MLX-IndexTTS-2.5` revision
`3d0db294644a2d4d6a140c52f1582b69a85e7b83`；15 个文件逐字节一致。IndexTTS 的条件
许可、下载确认和下游条款随 distribution 发布，未被降级或省略。

## 模型 Packages

| Package | Artifact SHA-256 | Size | Submission | Repository metadata |
| --- | --- | ---: | --- | ---: |
| `ai2apps/model-voxcpm2 0.1.0` | `46544e2441362bed78bb704b54db5c7d0ec7ea123e3562f62a41b477c7f4f757` | 8176 | `90217e03-03ff-4dc5-b473-254bb4e14cdf` | 189 |
| `ai2apps/model-indextts25 0.1.0` | `459e3c4680534335de65a68def52e725666e194ee59381bccbc6c6e47a454083` | 16688 | `c0a7a8bf-59f7-49b1-9bcf-37a252e49ae7` | 190 |

生产 Cloud 当前尚未接受可选顶层 `modelInstall` 投影，因此正式构建使用 runbook 的
`--omit-model-install-catalog` 兼容模式。源码仍包含完整签名声明，客户端 fallback 仅映射
上述两个 Package 的 `0.1.0`，后续版本不会继承该例外。

## 验收

- Package 契约、音频 Package 与 checkpoint distribution 定向回归：`65 passed`；
  此前 Runtime/Adapter/模型定向回归：`38 passed`。
- Runtime 候选内嵌 Python 已完成 VoxCPM2 4-bit、8-bit 与 IndexTTS 2.5 FP16 真实
  MLX/Metal 推理；输出分别为 48 kHz 与 22.05 kHz 单声道 WAV。
- M5 Max 代表性结果：VoxCPM2 4-bit RTF `0.51`；IndexTTS 2.5 中英文 RTF
  `0.72–0.94`。
- 空会话公开回读 Repository metadata v190，Runtime 与两个模型 Package 的
  `artifactExactBytes`、`envelopeExactJson` 全部为 `true`。
- Runtime 公开源最终为 Cloud、GitHub、ModelScope 三源 active；公开 Runtime 完整
  SHA-256 和本地正式制品一致。
- App-Dev Local 在发布后按标准 Helper 接口重启至端口 `52754`，确认旧进程造成的
  `This Package does not declare a trusted model installation plan` 提示消失。IndexTTS
  安装对话框正确列出 FP16；VoxCPM2 正确列出推荐 4-bit 与可选 8-bit。两次均在下载前
  取消，没有修改本地 Package 或 checkpoint 状态。
