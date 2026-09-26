# VoxCPM2 与 IndexTTS 2.5 MLX 实现报告

日期：2026-09-22  
源码基线：`61da0fc6a87d4f743d312c8ae1987d1d1b7babb8`（含未提交的本次实现）  
状态：本地实现与候选 Runtime 验收完成；等待 checkpoint 双源发布和生产签名发布

## 1. 交付状态

| 组件 | 候选版本 | 状态 |
| --- | --- | --- |
| oMLX Runtime | `ai2apps/runtime-omlx` 1.7.9 | 本地临时签名 Package 已构建并通过最终 DMG 内 Bundle 验签 |
| VoxCPM2 | `ai2apps/model-voxcpm2` 0.1.0 | 4-bit 真实 MLX 推理通过；8-bit 固定 revision 已声明，待双源 distribution 与正式 Package |
| IndexTTS 2.5 | `ai2apps/model-indextts25` 0.1.0 | 纯 MLX FP16 checkpoint 可复现转换，真实推理通过；待双源上传后回填不可变 revision 和 distribution |

两套模型均复用 `ai2apps-model-worker/v1`、`audio_speech` 和
`ai2apps.audio-capabilities/v1`，不增加 Voice Studio 私有推理 API。

## 2. Runtime 1.7.9

- Python 3.11.10、MLX 0.32.0、MLX-Audio 0.5.5、Transformers 5.15.1、
  WeText 0.1.8。
- MLX-Audio 固定源码 commit：
  `cd605ecfcc266ccf6ea3077586c373101be982c6`。
- IndexTTS 路径基于 WIndexTTS commit
  `eafb98c1b2ba46f6a608f29d8831208b89047681`，以 Torch-free 方式 vendoring；
  Runtime 不包含 `torch` 或 `torchaudio`。
- 新增 Runtime capabilities：`voxcpm2`、`indextts25`。
- 本地候选：`/private/tmp/ai2apps-runtime-omlx-1.7.9-dev.ai2service`，
  SHA-256 `0827d7a2188d5e2b4946de95bd29e6882360cb545e4ab1c5787718416460ea76`，
  369,672,409 bytes。该文件仅供开发验收，不可作为生产发布件。

## 3. VoxCPM2 0.1.0

首发模型 ID：

- `ai2apps.model.voxcpm2/4bit`：HF revision
  `dc9e5c187858da5f4a13dc4c247e297339216381`。
- `ai2apps.model.voxcpm2/8bit`：HF revision
  `d52725898a0675703f7f9ddc5a4d1a3cdbb99032`。

两个 Hugging Face revision 与现有 ModelScope 公共镜像的选定推理文件逐字节一致；
固定的 ModelScope revisions 分别为
`c523466da1ff69acd148625cb011a552d580cb85` 和
`788aabb3d03770d46dab583643b204aef7ceae44`。因此 VoxCPM2 无需重复上传权重，
只需签名、审核并发布 AI2Apps checkpoint distributions。

两份本地开发签名 envelope 已通过 `metadata_verified` 双源校验：4-bit 为 5 个文件、
2,300,904,017 bytes、275 pieces，manifest digest
`sha256:b0a05bd664ec3376c21d63aac5dcf3e8c51a1a372a73ab281f05f433f03651d6`；
8-bit 为 5 个文件、3,225,461,623 bytes、385 pieces，manifest digest
`sha256:0164fa2a2d812cb61546e2b5c805617573512a0dba8bb9a07f01f5760908803d`。
生产发布时必须用已注册 Publisher 密钥重新构建，不能复用开发签名。

P0 支持中文、英文和中英混合文本、单段参考音色克隆、无需参考转写、自然语言
声音设计及指令式情绪/语速。`speed` 是定性指令控制，不承诺精确时长倍率；标准
`emotion`/`speed` 生成的强制指令置于用户 `instructions` 之后，因此冲突时标准字段
优先。流式、单次多说话人和预设演员均声明为不支持。

## 4. IndexTTS 2.5 0.1.0

P0 支持中文和英文、单参考音色克隆、原生 `duration_factor` 语速和上游八维数值
情绪。统一速度按 `duration_factor = 1 / speed` 映射，允许 `speed` 0.5–2.0。
`neutral` 保留参考音频派生的表达，不等同于 `calm`。

首发只公布已验证的 `neutral`、`happy`、`sad`、`angry`、`calm`、`surprised`。
上游没有原生 `excited` 轴，因此首发拒绝该值，不用未经验证的组合向量兼容。
参考音频硬限制为 15 秒；超过限制在推理前明确拒绝。`ref_text` 兼容接收但不参与
基础克隆。P1 的 Qwen 文本转情绪与 P2 的独立情绪参考音频未包含在 0.1.0。

转换输入固定为：

- `IndexTeam/IndexTTS-2.5`：`d0aa86e75bb6f3437f3831e95056fa72842d89ef`
- `facebook/w2v-bert-2.0`：`da985ba0987f70aaeb84a80f2851cfac8c697a7b`
- `funasr/campplus`：`e4b6ede7ce16997aff4ae69fbca1f0175e2afede`
- `nvidia/bigvgan_v2_22khz_80band_256x`：`633ff708ed5b74903e86ff1298cf4a98e921c513`

`scripts/convert_indextts25_mlx_checkpoint.py` 可复现生成 FP16 safetensors；转换
manifest 记录每个输出文件的大小与 SHA-256。候选约 3.1 GB，不包含 Torch checkpoint、
优化器状态或可选 Qwen 情绪模型。

## 5. 实测

设备：Apple M5 Max、128 GB，macOS 26.6.1；两套模型均确认使用
`Device(gpu, 0)`。

| 模型 | 量化 | 代表性结果 | 峰值内存 |
| --- | --- | --- | --- |
| VoxCPM2 | 4-bit | 生成 6.40 秒音频耗时 3.27 秒，RTF 0.51 | RSS 约 2.73 GiB；Apple peak footprint 约 8.67 GiB |
| VoxCPM2 | 8-bit | 候选 Runtime 冷启动加生成共 2.12 秒，输出 3.36 秒，端到端比率 0.63 | 待正式安装验收记录峰值 |
| IndexTTS 2.5 | FP16 | 多组中英文 RTF 0.72–0.94；可复现候选 4.42 秒音频耗时 3.48 秒，RTF 0.79 | RSS 约 3.72 GiB；Apple peak footprint 约 4.55 GiB |

RTF 为“生成耗时 / 输出音频时长”，小于 1 表示快于实时。候选 Runtime 自身的
嵌入式 Python 再次完成端到端生成：IndexTTS 输出 22.05 kHz 单声道 WAV，VoxCPM2
4-bit 与 8-bit 均输出 48 kHz 单声道 WAV，证明推理没有借用仓库 `.venv`。

## 6. 验证结果与正式发布

- 定向 Adapter、Package、Runtime 回归：38 项通过。
- `uv lock --check`、wheel 构建、Python compile、`git diff --check` 通过。
- wheel 含 IndexTTS Python、license、NOTICE 与两份 `.npz` 前端数据。
- Runtime 最终 DMG 内 Bundle 通过 `codesign --verify --deep --strict`、Developer ID
  签名、Apple 公证、staple 与 Gatekeeper。
- IndexTTS checkpoint 已上传 HF/MS 不可变双源并完成 15 文件逐字节校验；VoxCPM2
  两个既有 checkpoint 双源也已固定到不可变 revision。
- 三份 checkpoint distribution、`ai2apps/runtime-omlx 1.7.9`、
  `ai2apps/model-voxcpm2 0.1.0` 和 `ai2apps/model-indextts25 0.1.0` 均已签名、审核并发布。
- 空会话公开回读 Repository metadata v190，三个 Package 的正式 artifact 和 envelope
  均与本地候选完全一致；Runtime 的 Cloud、GitHub、ModelScope 三源均为 active。

完整生产发布标识、摘要、submission、不可变 revision 与 source validation 收据见
`docs/ai2apps-mlx-runtime-1.7.9-voxcpm2-indextts25-release.md`。
