# 音乐／音效 Model Package 发布记录（2026-10-05）

## 状态

- `ai2apps/model-ace-step-mlx` **0.1.0 已发布**，依赖 Runtime `>=1.8.9 <2.0.0`。
- `ai2apps/model-stable-audio-mlx` **0.1.0 已发布**：Music/SFX 两个独立双源分发，许可门禁、真实签名包安装和推理验收通过。
- 本次未发布 Desktop。新增 Host 模型类型、NPZ 安装校验和资源预留须随下一版 Desktop 发出；当前真实安装验收由包含这些改动的源码 Host 驱动，不能视为现有生产 Desktop 的升级验收。

## ACE-Step 发布身份

| 字段 | 值 |
| --- | --- |
| Package | `ai2apps/model-ace-step-mlx@0.1.0` |
| Service / Model | `ai2apps.model.ace-step-mlx` / `ai2apps.model.ace-step-mlx/turbo` |
| Package SHA-256 | `c31672d7842b621d8409075c08957085943f0e3864736f618c0e103dcec94eff` |
| Package bytes | 75,942（纯 Python 代码与声明，不含权重） |
| Package submission | `eccb9f9c-da2c-4081-9c1e-9535d3fed7b4` |
| Submission / Release 状态 | `verified` / `published` |
| Repository metadata | 253 |
| Distribution | `dist_ai2apps_ace_step15_turbo_mlx_v1` |
| Distribution submission | `add317ac-5bfc-4641-b8ac-71a3e5e2ff60` |
| Distribution digest | `sha256:b7591efa19758fa74f37dd1beb693af7086991a11893139e95acd5b72eb7be0f` |
| Checkpoint Index | 103，匿名验签及 envelope 精确回读通过 |
| Checkpoint bytes / files / pieces | 10,090,327,160 / 27 / 1,203 |
| Piece size | 8 MiB |
| 权重核验 | `ai2apps-local/checkpoint-full-dual-download-v1` |

固定权重源：

- [Hugging Face](https://huggingface.co/Avdpro/ACE-Step-1.5-Turbo-MLX/tree/ea6bb1523660feb518563f203314528294880d1f)：`ea6bb1523660feb518563f203314528294880d1f`。
- [ModelScope](https://modelscope.cn/models/ai2apps/ACE-Step-1.5-Turbo-MLX)：`ec33afedc08fa8ddc2a06b50c74130fc19626d0a`。

小型代码 Package 使用 Cloud 源；大型模型权重使用签名 HF/MS 分发。下载器沿用严格的 ModelScope `200 + Content-Range` 兼容验证、全局 piece SHA-256、逐文件 SHA-256 和不可变快照；未新增宽松状态码例外。

首次 MS 下载使用产品分片下载器，全程禁用 HF，完整回读后再以标准 full-dual-download 构建器核对两端文件。24 路下载遇到连接提前关闭和非合格 Range 响应，校验拒绝后复用分片缓存恢复；降至产品默认 8 路完成。最终会话下载 3,522,047,096 bytes，其余为此前已验证的 MS 分片；不能把最终会话计数误当作完整下载大小。全量构建结果与元数据候选 envelope 完全一致。

## 验收

- 78 项 Host／Worker／checkpoint 回归及 10 项多源 Range、坏片切换、混合来源、断点校验测试通过；包适配器清理后另重跑 5 项相关测试通过（不重复累计）。
- 三个分支在已签名 Runtime 1.8.9 Python 3.11 中实际生成 10 秒和 120 秒双声道 PCM16 WAV，未导入 PyTorch。
- 真实采样取消测试覆盖三个分支。取消异常 traceback 原会保留上游大张量，已在纯 Python wrapper 清除取消栈；调用／取消结束后 MLX active 为 18 或 44 bytes，cache 为 0。
- ACE 120 秒 MLX 峰值为 35,816,049,143 bytes，完整声明范围要求 48 GiB 统一内存。短样本数值不是 120 秒内存规格的替代。
- ACE 真实签名归档安装到隔离 Host，使用 Runtime 1.8.9 dependency lock，经 Managed Service `sandbox-exec`、出站网络禁止和声明 checkpoint 授权：health、10 秒生成、进度、取消返回 499、停止、重启和卸载均通过。
- 匿名重新下载公开 Package，通过 Registry Snapshot、完整 SHA-256 和 Publisher 签名校验。
- 测试机：Apple M5 Max 128 GiB；未完成第二台 Mac 验收。未新增 Voice Studio Mini-App，后续消费者必须使用 Host 共享 Preview & Output。

## Host 接入

模型类型为独立 `audio_generation`，不使用 TTS 类型。Host 可通过 `ModelInvocationService.invoke_background_to_file` 调用 `audio_generate`，传递 actor context、request ID、受控目标路径、进度和取消回调。

请求包含 `model`、`task: music|sound_effects`、`prompt`、`duration`，可选 `steps`、`seed`、`lyrics`、`language`；v1 输出 WAV，不接受调用方输出路径、参考音频或流式。ACE 支持歌词和 10–120 秒；Stable 支持 1–120 秒，Music/SFX 分离。

Host 新增的 NPZ 激活只接受完整、不可变、已验证 Registry 分发回执；普通 NPZ 文件目录仍不能激活。源码 Package 位于 `packages/ai2apps-model-ace-step-mlx/` 和 `packages/ai2apps-model-stable-audio-mlx/`。

## Stable Audio 许可确认

用户已确认 AI2Apps 为非商业安装体验用途。分发携带完整 Stability AI Community License、Gemma Terms、Notice 及 Powered by Stability AI 署名。ACPF/Discover 在下载任何字节前要求用户明确同意，记录绑定 distribution ID、manifest digest 和 terms hash；未同意、拒绝或过期条款均不能复用缓存绕过。用户后续用途仍须符合原许可，商业用途按原条款处理。发布 QA 的非商业同意不替代最终用户的同意。

## Stable Audio 发布身份与验收

| 字段 | 值 |
| --- | --- |
| Package | `ai2apps/model-stable-audio-mlx@0.1.0` |
| Package SHA-256 | `9a5622efb92316935d609164a1b943ff21e96422c2254f9cd4bf3f7505579826` |
| Package bytes | 199,759（纯 Python 代码与声明，不含权重） |
| Package submission | `88dde5e5-3021-446b-a321-cfa07224d428` |
| Public Release / Registry metadata | `published` / 254 |
| Music distribution | `dist_ai2apps_stable_audio3_small_music_mlx_v1` |
| Music manifest digest | `sha256:8a4b8f6e336f00e5d49156913e3eb795eee9dd899046f37ed3e16038939796af` |
| SFX distribution | `dist_ai2apps_stable_audio3_small_sfx_mlx_v1` |
| SFX manifest digest | `sha256:f5e4095cd7176aea33960639228e29758e9cd20e2eb683d186a7676d8eacc00f` |
| 每个配置 bytes / files / pieces | 1,704,751,891 / 8 / 204（8 MiB piece） |
| Anonymous Checkpoint Index | 104 / 105，签名及完整 envelope 回读一致 |

固定权重源：

- [Hugging Face](https://huggingface.co/Avdpro/Stable-Audio-3-Small-MLX/tree/1e17940bc4eeb91b840ba686b99a67e8e36a907f)：`1e17940bc4eeb91b840ba686b99a67e8e36a907f`。
- [ModelScope](https://modelscope.cn/models/ai2apps/Stable-Audio-3-Small-MLX)：`bca8407330633cb02e5ccc5aba4786ddb082406d`。

保持官方 NPZ 张量字节不变；额外包含 LICENSE.md、LICENSE_GEMMA.md、Notice、README 和来源记录。Music 首次强制 MS 下载 1,704,751,891 bytes，SFX 下载 922,746,880 bytes，其余复用同一缓存的已验证 piece。两个分发均通过标准 `checkpoint-full-dual-download-v1` 完整双端字节验证。候选到最终清单只澄清许可确认文案，所有源、文件及 piece 摘要均断言相同；最终清单重新验证许可拒绝门禁。

真实签名 Runtime 1.8.9 与 Stable Package 安装到隔离源码 Host，Worker 由 `sandbox-exec` 启动且禁止出站网络。Music/SFX 各生成 10 秒、44.1 kHz、双声道 PCM16 WAV（1,764,044 bytes）；进度完成、取消返回 499、停止、重启、卸载通过。已匿名重新下载生产 Package，完整 SHA-256 与 Publisher 签名通过。

许可回归覆盖 ACPF 同意持久化、下载前门禁和共享 UI（3 项）；最终两个实际清单各验证未同意、未勾选、错误条款哈希、错误清单哈希 4 种拒绝情况。QA 同意仅用于本次用户授权的非商业验收，不写入最终用户同意记录。包适配器 5 项及多源回归 10 项在本轮重跑通过。

## 证据

机器可读收据：`docs/ai2apps-audio-model-packages-2026-10-05.json`。完整构建、双源回读、发布、匿名验证和安装报告在 `artifacts/music-packages-0.1.0/`。来源 commit 为 `fa377dcb62875d5c82fc8177afd4277cd2357db9`，工作树含其他进行中修改；实际发布字节以 Publisher 签名和上述 SHA-256 为准。

两个模型 Package 的发布与验证均已完成，对应 Dev Cookie 授权随之结束。
