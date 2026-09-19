# MLX-WhisperX 独立实验验证记录

验证日期：2026-09-04。代码基线：
`11b5b9ac537e42b1029d1f0148bbbe6a33307f8e`，叠加本目录尚未提交的实验实现。

## 隔离边界

- 未修改或启动 AI2Apps App、App-dev、Local Runtime、模型 Package 注册或实例模型库。
- checkpoint 仅下载至本目录被 `.gitignore` 排除的 `.models/`。
- 测试音频及 JSON 仅写入被排除的 `.artifacts/`。
- 九个 checkpoint 均为公开仓库，下载过程不需要账号、Token 或签名。

## 环境与固定依赖

- Apple M5 Max，18 CPU cores，128 GB unified memory
- macOS 26.6.1 (25G76)
- Python 3.13.1
- `mlx-audio==0.4.3`，`mlx==0.32.0`，`numpy==2.3.5`
- 模型 repository、immutable revision、大小和 SHA-256 见
  `models.lock.json`

## 已验证能力

### 单说话人：Whisper + word timestamps

输入是 macOS 离线系统音色生成的 3.785 秒、16 kHz mono PCM WAV。

```bash
/usr/bin/time -l .venv/bin/python -m experiments.mlx_whisperx \
  experiments/mlx_whisperx/.artifacts/english-smoke.wav \
  --model experiments/mlx_whisperx/.models/whisper-tiny-asr-6bit \
  --language en \
  --output experiments/mlx_whisperx/.artifacts/english-smoke.energy.result.json
```

结果：成功输出 segment 和逐词 `start`、`end`、`score`。冷启动进程总耗时
5.89 秒，最大 RSS 607,485,952 bytes（约 579 MiB），cold RTF 约 1.56。

### 双说话人：Whisper + Sortformer + speaker assignment

输入由两个不同 macOS 离线系统音色顺序拼接，共 6.140 秒。

```bash
/usr/bin/time -l .venv/bin/python -m experiments.mlx_whisperx \
  experiments/mlx_whisperx/.artifacts/two-speakers.wav \
  --model experiments/mlx_whisperx/.models/whisper-tiny-asr-6bit \
  --language en \
  --diarization-model \
    experiments/mlx_whisperx/.models/sortformer-4spk-v2.1-fp16 \
  --output experiments/mlx_whisperx/.artifacts/two-speakers.result.json
```

结果：两个 segment 分别标记为 `speaker_0`、`speaker_1`，所有 word 均获得
speaker。冷启动进程总耗时 6.93 秒，最大 RSS 860,405,760 bytes（约
821 MiB），cold RTF 约 1.13。

### 完整英文能力：Whisper + CTC forced alignment + Sortformer

英文 CTC 模型使用 `facebook/wav2vec2-base-960h` 的公开 safetensors；准备脚本只
下载模型、词表和 processor 配置，并把架构路由到 `mlx-audio` 已有的 MLX
Wav2Vec2/MMS CTC 层，不依赖 Torch 推理。运行时关闭 Whisper native word
timestamps，以证明词边界来自独立 CTC 模型：

```bash
/usr/bin/time -l .venv/bin/python -m experiments.mlx_whisperx \
  experiments/mlx_whisperx/.artifacts/two-speakers.wav \
  --model experiments/mlx_whisperx/.models/whisper-tiny-asr-6bit \
  --language en \
  --no-word-timestamps \
  --alignment-model \
    experiments/mlx_whisperx/.models/wav2vec2-base-960h-mlx-ctc \
  --diarization-model \
    experiments/mlx_whisperx/.models/sortformer-4spk-v2.1-fp16 \
  --output \
    experiments/mlx_whisperx/.artifacts/two-speakers.ctc-diarization.result.json
```

结果：两段文本分别得到 `speaker_0`、`speaker_1`，共 21 个 word 全部获得 CTC
边界、CTC score 和 speaker；所有边界位于 6.140 秒音频范围内。一次新进程测量总
耗时 3.97 秒、最大 RSS 1,236,647,936 bytes（约 1.15 GiB），RTF 约 0.65。
该数字受模型文件系统缓存影响，不能与前述首次冷下载后的进程数据直接比较。

### 训练型 VAD 与公开真人样本

Sortformer 现在可同时提供训练型 speech activity 与 diarization：第一次推理的匿名
speaker spans 合并为 VAD regions，后续 speaker assignment 直接复用同一结果，不
重复运行 Sortformer。Energy VAD 只保留为低配 baseline。

另使用 Whisper 模型卡公开提供的 13.69 秒、16 kHz mono LibriSpeech FLAC 样本验证：

```bash
/usr/bin/time -l .venv/bin/python -m experiments.mlx_whisperx \
  experiments/mlx_whisperx/.artifacts/hf-sample1.flac \
  --model experiments/mlx_whisperx/.models/whisper-tiny-asr-6bit \
  --language en --vad sortformer --no-word-timestamps \
  --alignment-model \
    experiments/mlx_whisperx/.models/wav2vec2-base-960h-mlx-ctc \
  --alignment-min-word-score 0.01 --alignment-window-seconds 30 \
  --diarization-model \
    experiments/mlx_whisperx/.models/sortformer-4spk-v2.1-fp16
```

结果输出 4 个合法 segment、42 个 CTC word，全部分配为 `speaker_0`，最低保留
word score 约 0.50。已有模型/Metal 缓存的进程总耗时 3.50 秒，最大 RSS
1,237,434,368 bytes（约 1.15 GiB），RTF 约 0.26。同参数再次运行的 JSON 经
`cmp` 逐字节一致。

### 完整中文能力：简体转写 + 逐字 CTC 对齐 + Sortformer

中文对齐模型采用公开、Apache-2.0 的
`wbbbbb/wav2vec2-large-chinese-zh-cn` safetensors，固定 revision 与 SHA-256
见 `models.lock.json`。其上游 `config.json` 的 architecture 标注滞后，但权重实际
包含 `lm_head.weight`/`lm_head.bias`；准备脚本只修改本地架构路由和语言声明，权重
文件哈希保持不变。测试音频为 macOS 离线中文音色生成的 4.138 秒、16 kHz mono
PCM WAV：

```bash
/usr/bin/time -l .venv/bin/python -m experiments.mlx_whisperx \
  experiments/mlx_whisperx/.artifacts/chinese-smoke.wav \
  --model experiments/mlx_whisperx/.models/whisper-tiny-asr-6bit \
  --language zh --prompt '以下内容使用简体中文。' \
  --vad sortformer --no-word-timestamps \
  --alignment-model \
    experiments/mlx_whisperx/.models/wav2vec2-large-chinese-mlx-ctc \
  --alignment-window-seconds 30 \
  --diarization-model \
    experiments/mlx_whisperx/.models/sortformer-4spk-v2.1-fp16 \
  --output experiments/mlx_whisperx/.artifacts/chinese-smoke.full-mlx.result.json
```

结果为 1 个 segment、19 个有独立 `start`/`end`/CTC score 的汉字，全部分配为
`speaker_0`；所有边界位于原音频范围内。已有模型/Metal 缓存时进程总耗时 2.88 秒，
最大 RSS 2,154,348,544 bytes（约 2.01 GiB），RTF 约 0.70。同参数复跑 JSON 经
`cmp` 逐字节一致。英文 13.69 秒基线复跑仍为 4 个 segment、42 个词，且与修复前
JSON 逐字节一致。

这次验证同时修复了中文目标序列语义：中文按字输出 timestamp，但字与字之间不插入
英文词表使用的 `|` 分隔 token。Tiny Whisper 将预期的“识别”“对齐”误识别为
“时别”“对几”，相应字符的 CTC score 接近零，说明 score 可用于质量门控，但不能
把强制对齐置信度解释为 ASR 文本正确率。

### 中英文公开真人 mini-benchmark

新增两份可提交的固定清单，各包含 5 条 FLEURS test 真人语音。音频来自
`FluidInference/fleurs-full` 对 `google/fleurs` 的 soundfolder 重组，固定 revision
`1cca811bb8ea4d370345f108f00518167040282c`，沿用 CC-BY-4.0；清单记录逐文件
SHA-256，准备脚本只下载列出的 10 个 WAV。中文共 60.84 秒、195 个评分字符，英文
共 40.86 秒、103 个评分词。

同一套 `Sortformer VAD/diarization -> Whisper` 流水线、greedy 解码的筛选结果：

| Whisper checkpoint | 中文 CER | 中文 RTF | 英文 WER | 英文 RTF |
|---|---:|---:|---:|---:|
| tiny ASR 6-bit | 155.38% | 0.077 | 15.53% | 0.103 |
| small ASR 6-bit | 40.51% | 0.120 | 18.45% | 0.178 |
| large-v3-turbo ASR 4-bit | **6.67%** | **0.056** | **6.80%** | **0.073** |

Small 将本组中文 CER 显著降至 tiny 的约四分之一，但仍未达到发布质量。英文 small
在 4/5 条上与 tiny 接近或更好，却因一条局部重复使聚合 WER 略差；五条样本不足以
据此判断模型总体优劣。裸 Whisper 和简单 Energy VAD 都出现过尾部重复、过切或漏掉
完整样本，因此正式基线必须包含训练型 VAD，且仍需扩展到完整测试集。

评测还发现 BCP-47 兼容缺陷：`zh-CN`/`en-US` 曾被原样传给只接受主语言码的 Whisper
tokenizer，造成乱码或空输出。公共后端现在统一映射为 `zh`/`en`，并覆盖连字符、
下划线和大小写输入。`mlx-audio 0.4.3` 虽接受 `beam_size` 参数，但实际 beam decoder
尚未实现，因此当前不能把 beam search 写入能力声明或质量方案。

Large V3 Turbo 4-bit 在这组样本上同时取得最佳中英文错误率与 RTF；包含 Sortformer
的两个独立进程最大 RSS 分别为 1,302,495,232 和 1,301,970,944 bytes（约 1.21
GiB）。因此它是当前 M5 Max/高性能档首选技术候选。其转换仓库没有声明 license
元数据，虽然上游 Whisper 有独立许可证，正式 Package 仍必须先完成转换产物的来源、
许可证、NOTICE 和再分发审查；在此之前模型锁明确标为 `license_review_required`。
Tiny 和 small 均未通过本组中文质量门槛，当前不能声称已有合格的低内存中文方案。

为兼顾上下文与长音频内存，CTC 不再处理整份录音，也不直接依赖单个 Whisper
segment 的不稳定边界；相邻 segment 会组合进默认最长 30 秒的窗口。Whisper 输出
先裁剪到所属 VAD region，最终公共时间轴再次裁剪到原音频范围。

### 中英文完整 FLEURS test split

使用与 mini-set 相同的公开 soundfolder、固定 revision 和 Turbo 4-bit + Sortformer
配置，完成全部 945 条中文与 647 条英文测试音频。评测器每 10 条原子保存检查点并支持
`--resume`，本次两组均为 `status=complete`：

| 语言 | 样本数 | 音频时长 | 错误率 | 推理时间 | RTF | 最大 RSS |
|---|---:|---:|---:|---:|---:|---:|
| 简体中文 | 945 | 11,065.18 s（3.07 h） | CER 16.48% | 293.75 s | 0.02655 | 1,318,715,392 B |
| 美式英文 | 647 | 6,387.90 s（1.77 h） | WER 7.82% | 181.74 s | 0.02845 | 1,317,093,376 B |

中文逐条 CER 中位数 10.26%、P90 33.87%、P95 43.97%、P99 68.33%；151 条完全
正确。5 条超过 100%，主要是 `并且`、`再次` 等尾部重复；另有 1 条 VAD 完全漏检。
英文逐条 WER 中位数 5.56%、P90 18.73%、P95 25.00%、P99 41.44%；216 条完全
正确，没有超过 100% 或空输出。mini-set 的中文 6.67% 明显过于乐观，完整集
16.48% 才是当前候选的有效质量基线。

### Qwen3-ASR 0.6B 4-bit 同集对照

独立实验复用已发布 Package 锁定的公开 MLX checkpoint
`mlx-community/Qwen3-ASR-0.6B-4bit`，revision
`313d850181767edf09f00a9c289becca70e58cd0`；实验目录独立下载，没有读取或改动
App-dev 模型状态。评测器新增 `--backend qwen3-asr`，将 BCP-47 语言标签映射为
Qwen 所需的完整语言名，并把 `prompt` 映射到原生 `system_prompt`。

Qwen 强制 `Chinese` 已足够输出简体中文，不注入 Whisper 专用的“以下内容使用简体
中文”提示。五条中文 mini-set 的 CER 为 13.33%，不如 Whisper Turbo 的 6.67%；
但完整集结论相反：

| 模型 | 中文 CER | 中文 RTF | 英文 WER | 英文 RTF |
|---|---:|---:|---:|---:|
| Whisper large-v3-turbo 4-bit | 16.48% | 0.02655 | **7.82%** | 0.02845 |
| Qwen3-ASR 0.6B 4-bit | **12.67%** | **0.01408** | 8.97% | **0.01630** |

Qwen 中文相对 Whisper 减少 23.1% 字符错误，253/945 条完全正确，逐条 CER 中位数
6.90%，P90 29.76%，P95 40.30%，P99 52.60%；没有空输出或超过 100% 的灾难性
重复。逐条比较中 Qwen 胜 465 条、持平 291 条、Whisper 胜 189 条。Qwen 处理
3.07 小时中文音频的模型推理时间为 155.78 秒，进程墙钟 156.62 秒，最大 RSS
1,545,797,632 B。

英文完整集上 Qwen 为 8.97%，略差于 Whisper 的 7.82%；逐条比较中 Qwen 胜
163 条、持平 292 条、Whisper 胜 192 条。Qwen 推理时间 104.13 秒，进程墙钟
106.48 秒，最大 RSS 1,564,442,624 B。当前质量优先路由应为中文 Qwen、英文
Whisper，而不是全语言固定一个模型。

标准 CER/WER 会把 `15` 与“十五”、`2011` 与“二零一一”计为不同字符，因此 Qwen
部分错误来自书写规范而非听错；本报告仍保留未做数字归一化的严格分数，避免为某个
模型定制评分。专名、中英混说和技术编号仍是 Qwen 0.6B 的主要失败类型。

### Qwen3-ASR 1.7B 与 Qwen3 ForcedAligner

新增公开 Apache-2.0 的 `Qwen3-ASR-1.7B-4bit` 和
`Qwen3-ForcedAligner-0.6B-8bit`，固定 revision、权重大小与 SHA-256 均写入
`models.lock.json`。1.7B 使用与 0.6B 完全相同的 FLEURS full split：

| 模型 | 中文 CER | 中文 RTF | 英文 WER | 英文 RTF | 峰值内存 |
|---|---:|---:|---:|---:|---:|
| Qwen3-ASR 0.6B 4-bit | 12.67% | 0.01408 | 8.97% | 0.01630 | 约 1.56 GB RSS |
| Qwen3-ASR 1.7B 4-bit | **11.99%** | 0.01888 | **7.04%** | 0.02362 | 3.95/4.13 GB footprint |
| Whisper large-v3-turbo 4-bit | 16.48% | 0.02655 | 7.82% | 0.02845 | 约 1.32 GB RSS |

1.7B 相对 0.6B 的中文字符错误减少约 5.4%，英文词错误减少约 21.5%；速度慢于
0.6B，但中英文都仍快于本机 Whisper Turbo 基线。因此 Detailed Transcription 的
推荐档位为 compact=Qwen 0.6B、quality=Qwen 1.7B。

ForcedAligner 的真实中文样本为 23/23 汉字有效对齐；同一英文样本成功对齐包括
`25`、`30` 在内的单位，但 20 个单位中 4 个得到零长度边界。流水线在
`features.alignment` 返回 `total_units`、`aligned_units` 和 `coverage`，不静默
宣称完整成功。10 分钟中文长测使用 Energy VAD 时，对齐覆盖率 98.93%，端到端
CER 8.44%；进程总耗时 13.66 秒，最大 RSS 4,164,206,592 B。

### 十分钟级完整流水线压力测试

`compose_long_audio` 从固定 full manifest 顺序拼接真人录音，并在相邻样本间插入
0.3 秒静音；sidecar 保存来源、边界、参考文本和最终 WAV SHA-256。中文输入
610.06 秒/55 条，英文输入 610.98 秒/62 条。最终采用敏感 Energy VAD 保证内容
覆盖，30 秒窗口 Sortformer 做局部说话人标注，30 秒窗口 CTC 强制对齐。Whisper
和 Qwen 使用完全相同的音频、VAD、aligner 与 diarizer：

| 模型/语言 | 墙钟时间 | 长音频错误率 | 对齐单元 | 末段结束 | 最大 RSS |
|---|---:|---:|---:|---:|---:|
| Whisper/中文 | 17.57 s | CER 20.92% | 1,901 字 | 605.85/610.06 s | 3,682,025,472 B |
| Qwen/中文 | **12.76 s** | **CER 8.87%** | 1,756 字 | 605.84/610.06 s | 3,976,724,480 B |
| Whisper/英文 | 31.12 s | WER 18.65% | 1,319 词 | 609.26/610.98 s | 1,869,103,104 B |
| Qwen/英文 | **22.88 s** | **WER 16.59%** | 1,296 词 | 609.26/610.98 s | 2,119,630,848 B |

两份结果的 segment/word 均通过非负、单调、segment 包含 word、且不越过原音频
duration 的结构校验。长音频错误率不能与逐文件 full split 直接等同：合成压力样本
每几秒更换真人说话人，并引入跨样本上下文和 VAD 边界，难度更高。

压力测试暴露并修复两项问题：第一，中文 CTC 词表没有阿拉伯数字和少量拉丁/异体
字符，原实现遇到一个字符就终止整段。现在默认仅跳过这些字符的 timestamp，保留
segment 正文，并在 `features.alignment.skipped_characters` 逐字符计数；严格调用方可
选择 `reject`。第二，4-speaker Sortformer 直接处理几十名说话人拼接音频时会漏掉
后续新说话人。旧兼容模式仍可按窗口执行并使用窗口作用域 speaker ID。默认模式
现改为 Sortformer 原生 AOSC streaming state：speaker cache 与 FIFO 在 5 秒块之间
保持最多四个全局匿名 speaker slot，并返回 `speaker_identity=global_streaming`。

长音频对照也说明 Sortformer diarization 不应被无条件当作任意多人录音的 VAD。
120 秒/30 秒窗口直接作为 VAD 时英文 WER 分别为 49.78%/37.30%；敏感 Energy VAD
与 30 秒窗口 diarization 解耦后降至 18.65%。产品化仍应引入独立训练型 VAD，并把
阈值、窗口和 speaker 上限作为 capability/config，而不是隐藏常量。

Qwen 两份结果同样通过全部 segment/word 时间边界和单调性校验，证明现有 Qwen
正文可以直接进入同一 CTC 与 speaker assignment 能力层，生成相同的
`ai2apps.mlx-whisperx-result/v1` 结构。上述耗时已覆盖单进程长音频吞吐，但尚未
测量 warm steady-state 服务、并发或能耗。

### AMI 真实会议全局说话人、WER 与 cpWER 验收

从爱丁堡大学官方 AMI Corpus 下载 CC-BY-4.0 的 `IS1001a` 与 `IS1009a`
Mix-Headset 音频和人工 NXT 标注。SHA-256 分别为
`3630cc7415931e4dc91e3cd022cd7b6123057a055e8ac4114bdf010398ed89f0` 和
`6eb5a0ede0d9e72794f976ce7bea5b78133eae969f99b4c5418b43c2468d25b1`，时长
909.056/838.833 秒，均为 A/B/C/D 四人。DER 按 10 ms 帧、0.25 秒 collar 和最优
全局 speaker permutation；speaker-attributed WER 使用标准 permutation-aware
cpWER，避免把重叠语音的任意全局时间排序误当成唯一词序。

| 会议 | DER（含重叠） | miss / FA / confusion | 无重叠 DER | 全文 WER | 时间词 WER | 正确词 speaker accuracy | cpWER |
|---|---:|---:|---:|---:|---:|---:|---:|
| IS1001a | 34.23% | 30.05% / 2.66% / 1.52% | 28.14% | 32.63% | 33.24% | 92.66% | 37.29% |
| IS1009a | 20.26% | 13.05% / 5.35% / 1.85% | 18.03% | 32.95% | 44.55% | 84.73% | 52.53% |

Sortformer global-streaming 两场均产生恰好四个全局 slot；阈值 0.20 时 RTF
分别为 0.01188/0.01139。IS1001a 的 0.05～0.50 扫描中 0.20 最优，但相对 0.25
只改善约 0.10 个百分点，不能靠继续降阈值解决主要 miss。`MeetingEnergyVAD`
避免室内底噪把整场录音判成语音，并改善时间词覆盖与 cpWER；Sortformer 自身的
高 miss 仍表明弱语音和重叠语音未达到最终生产质量。

对同一 speaker 的 0.25/0.5/1/2 秒短缺口做了联合 DER/cpWER 扫描。1 秒桥接把
IS1001a/IS1009a DER 降至 24.67%/14.05%，但同一词时间轴联合重评分的 cpWER 从
37.89%/52.92% 退化到 39.17%/54.31%；0.25 秒也会让第二场 cpWER 退化。因此默认
仍为模型原生 0.12 秒，只把更长桥接保留成显式实验参数，不能为了较低 DER 损害
最终字幕的 speaker attribution。

IS1009a 首次运行出现一段重复幻觉，原始全文 WER 达 228.69%，而强制对齐后仅
1,228/5,761 token 有正时长。流水线现只允许正时长对齐单元进入字幕正文，明确报告
丢弃 4,533 个零时长单元和移除 25,652 个字符；复跑全文 WER 降至 32.95%。IS1001a
同一严格策略丢弃 200/1,575 个零时长单元，全文 WER 为 32.63%。该修复
不改变时间词 WER、speaker accuracy 或 DER，属于结果完整性保护而不是调分。

### 固定 SNR 噪声回归

`create_noisy_fixture.py` 用固定 seed 生成精确 10 dB/5 dB 白噪声并为派生 WAV 写入
SHA-256。同一组 5 条 FLEURS、Qwen3-ASR 1.7B 4-bit、FullAudioVAD 的结果如下：

| 语言 | 干净 | 10 dB | 5 dB |
|---|---:|---:|---:|
| 英文 WER | 5.83% | 8.74% | 8.74% |
| 中文 CER | 10.26% | 10.26% | 11.79% |

这是确定性回归门槛而非统计显著的鲁棒性结论；AMI 两场另行覆盖真实室内底噪和重叠。

### 独立 Detailed Transcription API

`experiments/mlx_whisperx/api.py` 已提供开发端点
`POST /v1/audio/transcriptions/detailed` 和能力查询端点。真实 multipart 中文调用
返回 `ai2apps.detailed-transcription-result/v1`、quality profile、逐字时间戳、
全局匿名 speaker、语速和逐项 provider/revision。情绪识别在 compatibility 策略下
明确返回固定 `neutral + status=fallback`；同一请求在 reject 策略下返回 HTTP 400
`unsupported_feature`。speaker recognition 始终拒绝，不伪造身份。能力文档明确
`chat_integration=false`、`streaming=unsupported`，且没有注册到 App/Runtime。

## 发现并修复的问题

1. `mlx-community/whisper-tiny-mlx` 是面向旧 `mlx-examples` 的 checkpoint，
   缺少当前 `mlx-audio` 所需的 processor/tokenizer 文件。后端现在会在模型分配前
   明确拒绝这类本地目录，而不是加载后才失败。
2. 当前 Whisper 实现可能返回空文本、零时长 segment。协议层现在剔除这些无效项。
3. 零时长 word 无法靠区间交集匹配 speaker。现在采用 segment speaker 作为确定性
   fallback，真实双说话人结果已确认不再出现空 speaker。
4. `mlx_audio.audio_io` 未能读取系统 `say` 生成的 AIFF-C；测试先规范化为 16 kHz
   mono PCM WAV。产品接入前需要独立的输入格式规范化层。
5. 完整链路曾在尾部产生只含 `¶` 且越过输入时长的 Whisper 幻觉 segment。英文
   CTC 词表无法对齐该字符；forced-alignment 层现在删除无可对齐字符的 word，并
   删除因此变空的 segment，复跑后所有边界均合法。
6. Tiny 模型曾因温度 fallback 导致同一音频文本变化。实验后端现在固定 greedy
   `temperature=0.0`；完整真人样本同参数复跑结果逐字节一致。
7. Whisper tiny 在未提示时对中文样本输出繁体字，而当前中文 CTC 词表是简体。
   明确的简体提示已通过本次样本，但它不是通用繁简转换；不在词表中的语义字符会
   默认跳过对齐并在结果中报告，严格模式可明确拒绝。
8. 标准 BCP-47 语言标签曾导致 Whisper tokenizer 选错语言；后端现在只把规范化后的
   主语言子标签传给模型，同时在公共结果和评测清单保留完整调用方标签。
9. 长音频中的单个 CTC 词表外字符曾导致整次任务失败。现在支持可审计的 `skip` 与
   `reject` 两种策略，默认兼容输出、严格模式拒绝。
10. Sortformer 的四说话人槽位不适合直接覆盖无限人数的长拼接录音。默认使用原生
    AOSC speaker cache 保持最多四个全局 speaker slot；超过四人时必须显式使用
    window-local 兼容模式，不能宣称全局身份。
11. Qwen ASR 在会议静音/低信息片段会产生大量重复 token。Qwen ForcedAligner 对
    这些 token 返回零时长；流水线现在将其从 word 与正文同时删除，并报告完整计数。

## 质量结论与未通过项

本轮证明的是“MLX 原生能力流水线可运行”，不是模型质量验收。Tiny 6-bit 在合成样本
上出现了 `morning -> mourning`、`replies that -> applies at` 等错误，也出现过尾部低置信度
重复词；因此小模型只能作为低内存/开发 smoke 方案，不能据此承诺正式识别质量。

以下能力仍明确标记为未实现或未验收：

- 英文逐词与简体中文逐字的独立 CTC forced alignment 已通过；繁体中文仍需版本化
  文本规范化，其他语言仍需各自的公开 CTC 模型和评测，未配置时默认拒绝，可由
  调用方显式选择 native fallback；
- 两场 AMI 的 DER、WER、正确词 speaker accuracy 与 cpWER 已建立基线，但高 miss
  和第二场 52.53% cpWER 尚未达到生产门槛；
- 固定 10/5 dB 白噪声与 AMI 真实底噪/重叠已覆盖；多语混说仍未验收；
- 最多四人的跨块全局 speaker identity 已通过；超过四人的 embedding clustering
  尚未实现；
- 流式增量 ASR、稳定 partial/final 事件、取消和背压；
- ACPF manifest、Worker Adapter 和自包含 staging 已完成；Host schema 与 Runtime
  1.6.0 已接受 dedicated model type/route，且该类型不进入 Chat STT；
- 四个 checkpoint distribution 已完成 Publisher 签名的双源 metadata-verified
  构建、Registry 发布与匿名回读；生产 Package 的签名门禁已经解除；
- 流水线当前可生成 Package Contract v1 的无权重测试归档，正式 Registry Package
  可使用这四个已验证 distribution 进行签署。

四个 checkpoint 的 ModelScope `mlx-community` 镜像已通过 Git HEAD 与 LFS 指针
审计。运行必需文件的逐文件 SHA-256 与固定 HF 快照完全一致；MS 仅额外增加
`configuration.json`，候选 manifest 用 `allow_patterns` 排除。Qwen3-ASR 0.6B、
Qwen3-ASR 1.7B、Qwen3 ForcedAligner 和 Sortformer 均有匹配本 Package model identity
的真实、非占位签名 distribution envelope，并已发布和匿名回读验证。

Runtime 1.6.0、四个 checkpoint distribution 与 Package 0.1.1 均已发布。0.1.1 的
真实 managed-service 安装成功，但首次推理暴露 macOS Worker 沙箱中的上传路径问题：
`Path.resolve()` 会把 `/tmp` 规范化为 `/private/tmp` 并遍历未授权父目录，最终返回 500。
0.1.2 已移除上传路径 canonicalization，并接受 multipart 的 `true`/`false` 布尔值；
0.1.2 已用注册 Publisher 私钥签署并发布，submission 为
`ab93f656-e5e9-4360-bdc5-a11d2ccce717`，Repository Snapshot 为 v109；匿名完整下载、
envelope 等值及公共 artifact 的中英文真实推理均通过。英文 smoke 文本完整正确且 9/9
对齐；中文 smoke 遗漏参考中的“我”一字，18/19 对齐。会议弱语音/重叠召回则作为后续
质量迭代。无论是否安装，Detailed Transcription 都不作为 Chat 的 STT 后端。

首次 Package 生产提交已经通过 artifact 验签和人工批准，但 Cloud 的发布期一致性
门禁发现 compact model identity 不能复用原 Qwen3-ASR Package 的 distribution。权重
内容可以复用，Registry distribution identity 不能跨模型声明复用。因此需要为
`ai2apps.model.detailed-transcription-mlx/compact` 生成并发布一份指向相同 HF/MS 固定
快照的新 distribution，然后替换不可发布的首次提交；不得绕过该门禁。新增 compact
distribution 已发布并通过公共索引 v46 匿名回读；0.1.1 已发布，沙箱路径修正版为 0.1.2。
