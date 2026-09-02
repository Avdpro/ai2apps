# Ornith 1.5 35B A3B MLX 4-bit Vision 双源 Checkpoint 发布收据

日期：2026-08-29（Asia/Shanghai）  
状态：Hugging Face 与 ModelScope 均已发布，并完成固定 revision、文件树与逐文件哈希校验

## 发布身份

- Hugging Face：`Avdpro/Ornith-1.5-35B-A3B-MLX-4bit-Vision`
  - 固定 revision：`31428ce8829c277f9255c59662b8efab58898ecf`
  - URL：<https://huggingface.co/Avdpro/Ornith-1.5-35B-A3B-MLX-4bit-Vision>
- ModelScope：`avdpro/Ornith-1.5-35B-A3B-MLX-4bit-Vision`
  - 固定 revision：`2ceda9edec98ac813104d04f1fe05ca1b8fdae58`
  - URL：<https://modelscope.cn/models/avdpro/Ornith-1.5-35B-A3B-MLX-4bit-Vision>
- 可见性：public
- License：MIT
- ModelScope task：`image-text-to-text`
- 文件数：20
- 总字节数：`20,422,418,899`

本次按发布策略统一使用个人账号：Hugging Face 为 `Avdpro`，ModelScope
为 `avdpro`。没有创建或切换 AI2Apps Publisher、Package 或 Cloud 身份。

## Checkpoint 组成

- 语言模型：官方 MLX 4-bit checkpoint
  - 来源：`ornith-ai/Ornith-1.5-35B-A3B-MLX-4bit`
  - 固定 revision：`19504d912fa8fc7622bf6b1de3db5d5d890b1f02`
- 视觉塔与 processor 元数据：官方 BF16 checkpoint
  - 来源：`ornith-ai/Ornith-1.5-35B-A3B`
  - 固定 revision：`10fbf86fed7ecee4a061f8b499a618f46001cac1`
  - 视觉张量：333
- 视觉 sidecar：`ornith15_vision_bf16.safetensors`
  - 字节数：`893,179,584`
  - SHA-256：`157796de2eac84d96178fef487efa23d61b06222b0057b201b645aa5a445e158`

四个语言分片保持官方 MLX 4-bit 文件字节不变。视觉张量从官方 BF16
源流式提取为 MLX `vision_tower.*` 布局；具体来源、布局转换和 tensor
数量记录在 `VISION_SIDECAR.json`。

## Runtime 文件 SHA-256

| 文件 | SHA-256 |
| --- | --- |
| `VISION_SIDECAR.json` | `3a759dca80393bb84d4d7e8341cceca1ba7c7609f812a50a1ef226711bc8754f` |
| `chat_template.jinja` | `182e77dd83bd8e9ca818b240b82e28f243762cd5dda32e6eef327df7b1cd107e` |
| `config.json` | `2695087d75ba843d426fc7982d6fbe30f55103d44d1f434aaea4c1d7ec013418` |
| `generation_config.json` | `e70c136c1b78ddc1fb0905bac8e733a4dc448d4f852a5dd75143fffc70be550e` |
| `model-00001-of-00004.safetensors` | `f0b2b03fb3eecf84096ee5abb213c99e9c3725f9947004a01999dc5cc55ebdd9` |
| `model-00002-of-00004.safetensors` | `971b1935112c4221616ddab04ead15d50b3c489754e619d74304dc4f64d034dc` |
| `model-00003-of-00004.safetensors` | `041377369466c48cb486ce2911c3cce638b8702080bb39113a7cf190632f5529` |
| `model-00004-of-00004.safetensors` | `d1088c7f6e9d705a253d3049bf7308704ccf1f4099cf40678ff077da88f0184b` |
| `model.safetensors.index.json` | `c118f13c0dcb729e4ca2e3d653ab193067551eb1a6410badb5192eb426104f36` |
| `ornith15_vision_bf16.safetensors` | `157796de2eac84d96178fef487efa23d61b06222b0057b201b645aa5a445e158` |
| `preprocessor_config.json` | `27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516` |
| `processor_config.json` | `d89ef49ce9cd37fbf510158e13c1ef063d9286411c1ec9049932dbe0487143b1` |
| `tokenizer.json` | `06b9509352d2af50381ab2247e083b80d32d5c0aba91c272ca9ff729b6a0e523` |
| `tokenizer_config.json` | `386ba246ba3dfa4d3a21d8bc8712eba38de558e5ac94c2c90436d8f94d519d5e` |
| `video_preprocessor_config.json` | `7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13` |

仓库根目录的 `CHECKSUMS.sha256` 保存同一份 runtime 校验清单。

## 发布与校验结果

- Hugging Face 固定 revision 回读：20 个文件，文件总字节数与本地 staging 一致。
- Hugging Face 四个语言分片、视觉 sidecar 与 tokenizer 的 LFS SHA-256：全部匹配。
- ModelScope `master` 与本地发布 commit：均为
  `2ceda9edec98ac813104d04f1fe05ca1b8fdae58`。
- ModelScope Git LFS：6/6 对象、20 GB 上传完成，服务端 repository validation passed。
- ModelScope LFS OID：四个语言分片、视觉 sidecar 与 tokenizer 均与上表 SHA-256 一致。
- ModelScope staging checkpoint 与已提交工作树逐文件二进制比较：20/20，0 mismatch。
- ModelScope Git 工作树：clean；远端文件树正好包含 20 个目标文件。
- ModelScope 平台元数据回读：public、MIT、`library:mlx`、
  `model_type:qwen3_5_moe`、`task:image-text-to-text`。

因此两个公开源可视为同一个 checkpoint 的字节等价镜像。后续 Package 应固定
上述两个 immutable revision，不应依赖浮动的 `main`/`master`。

## 发布过程说明

ModelScope 的模型创建接口在同时提交 License/描述时发生超时；使用同一 repo ID
的最小必填创建成功后，平台异步初始化了 `master`。其 HTTP commit API 随后仍被
repository policy 拒绝，因此按 ModelScope 官方支持的 Git/Git LFS 路径完成发布。

上传主机缺少可用的系统 `git-lfs`，故仅在 staging 目录放置官方
`git-lfs 3.7.1` Darwin arm64 便携二进制。下载归档 SHA-256 为
`76260fb34f4ee622ff0a66b857e5954aa49c7e343a92e57a1ec4a760618c94b2`，
与官方 release 清单一致；未执行系统安装。

HF token、ModelScope token 和浏览器 Cookie 均未输出、复制或写入模型仓库。
Git remote 不含 token；认证仅由运行时 askpass 从上传主机现有标准凭据文件读取。
