# Haru-4B MLX 全双工后端

日期：2026-11-18。状态：实验后端已实现，真实权重连续帧验证通过；尚未接入 Bot 语音界面。

## 选型与实现

选择 [Haru-4B](https://huggingface.co/higurashi-ai/Haru-4B)：原生连续全双工，
24 kHz 单声道，每 3200 samples（133.33ms）同时消费用户音频、生成模型音频及文字。
官方列出中文等九种语言，代码和权重为 Apache-2.0。它是预训练基础语音模型，
不能当作可靠任务指令模型；事实和指令遵循限制以官方模型卡为准。

复用[官方 MLX 实现](https://github.com/higurashi-ai/Haru/tree/7fe6b7665f8bf035998f401f8cb779fbe53f2751/haru_mlx)，
没有重新发明其模型移植。核心放在 `model_worker/haru_mlx/`，固定 commit
`7fe6b7665f8bf035998f401f8cb779fbe53f2751`；权重期望 revision
`8d6e83bcd3701a76fc27a764965665da1df7da78`。`UPSTREAM.json` 保存文件哈希，
只有包重定位和模板资源定位调整，保留许可证与第三方说明。没有修改 oMLX 原有
模型、router、attention 或 fused MoE kernels。

`model_worker/haru_duplex.py` 为 AI2Apps 提供异步帧后端：

- 模型加载、prefill、逐帧推理及释放在同一专用线程运行；只加载已有本地权重，
  不在进入会话时静默下载。支持原 BF16 和语言骨干 8-bit，codec/head 保持原精度。
- 一个后端持有一个会话，一次只允许一个待处理帧。积压拒绝并报告背压，避免旧麦克风
  音频排队后突然生效。输入检验声道形状、长度、有限值和幅度，限制会话帧预算。
- 每个输出带 session、帧序号、sample_start、playback_epoch 和 suppressed 标志。
  停止播放立即递增 epoch、静音待返回帧；恢复再递增 epoch，迟到帧不能重新播出。
  客户端仍须清空自己的播放队列。
- 原生模型没有离散 response cancel。停止播放不停止模型监听，也不取消 Bot 工作。
  主动取消一个推理 await 后，该会话标为不可继续；关闭时排空工作线程，不能把已消费
  的音频当作未执行而重放。

当前能力明确不包含工具调用、运行中正文/任务事实注入、图片/附件理解、用户语音 ASR
转写和精确到单词的播放对齐。能力声明仅标记帧级对齐，verification 保持 experimental。
后续 Bot 接入需要并行 ASR 产生用户最终转写，由已有输入协调器准入；实际任务和审批
仍归原 Bot owner。重要任务结果先可视展示，口述须通过已验证的 TTS/上下文重建路线。
本轮未将不可靠的 Haru 自由口述作为任务完成证据。

## 本机实测

Apple M5 Max、128 GiB 统一内存、macOS 26.6.1、MLX 0.32.0，8-bit 骨干。
输入和声音参考均由本机 `say -v Tingting` 合成，未采集用户麦克风、未使用私人声音。
按真实帧节奏喂入中文录音，137 个输入帧、138 个连续输出帧：

| 指标 | 结果 |
| --- | ---: |
| 帧计算 p50 | 25.81ms |
| 帧计算 p95 | 29.42ms |
| 超过 133.33ms 的帧 | 0 |
| 非静音输入/输出重叠帧 | 25 |
| MLX 峰值内存 | 7,597,967,136 bytes（约 7.08 GiB） |
| 权重加载 | 0.612s |
| 角色及声音参考 prefill | 0.095s |

这些是录音驱动的模型计算数据，不是实麦克风端到端时延。加载已受文件/系统缓存影响，
不能称为冷磁盘加载。MLX 峰值不是完整进程 RSS；尚未测试与 Bot 工作模型并发。
重叠帧以双方 RMS > 0.01 计数，仅证明同帧有输入和输出，不证明回声消除或插话体验。

模型已输出中文，但本次旅行问题中自由口述出现了用户没有指定的“日本”，因此不把
中文指令遵循、事实忠实度或助手质量标记为通过。真实麦克风/AEC、听感、长会话、
上下文保真、外部结果注入仍需后续验收。

实测权重 SHA-256：
`ad2c3534ef6bd88525e22e5da3ac4fb739368406bf3b1c852cbafbade647c0fa`。
完整设备/指标见 `acceptance/haru-mlx-20261118/benchmark.json`。

## 复现

以下命令从 Git 根执行。安装源码环境需要 `haru-duplex` 可选依赖（numpy、tokenizers、
scipy、soundfile），沿用项目既有 MLX 锁，不升级全局或已运行的 App Runtime。

```bash
.venv/bin/python -c 'from huggingface_hub import snapshot_download; snapshot_download("higurashi-ai/Haru-4B", revision="8d6e83bcd3701a76fc27a764965665da1df7da78", local_dir="/tmp/ai2apps-haru-4b-20261118", allow_patterns=["config.json","tokenizer.json","model.safetensors"], token=False)'

say -v Tingting -r 170 -o /tmp/ai2apps-haru-zh-input.aiff '你好，今天我想做一个简单的旅行计划。请用中文告诉我，去海边旅行应该准备什么？请说得简短一点。'
say -v Tingting -r 170 -o /tmp/ai2apps-haru-zh-reference.aiff '你好，我是一位中文语音助手，很高兴和你聊天。我们可以轻松地讨论工作和生活，也可以一起制定今天的计划。'

.venv/bin/python -m ai2apps.model_worker.haru_duplex_cli \
  --checkpoint /tmp/ai2apps-haru-4b-20261118 \
  --input /tmp/ai2apps-haru-zh-input.aiff \
  --reference-voice /tmp/ai2apps-haru-zh-reference.aiff \
  --input-seconds 12 --tail-seconds 8 --realtime \
  --output /tmp/ai2apps-haru-zh-reply.wav --report /tmp/haru-benchmark.json

HARU_MODEL=/tmp/ai2apps-haru-4b-20261118 MLX_ENABLE_TF32=0 \
  .venv/bin/python -m pytest ai2apps/tests/haru_mlx -q
```

## 验证与激活边界

- 真实权重及严格 float32 数值/流式编解码/采样/量化/映射/会话重现测试：35 passed，
  5 skipped（未提供独立 PyTorch reference dump），2.15s。不是跨框架 parity 全部通过。
- 默认 TF32 的首次严格测试有一项流式 codec 误差失败；按
  [MLX 官方精度说明](https://ml-explore.github.io/mlx/build/html/usage/precision.html)
  关闭 TF32 后维持原阈值通过。未改变模型计算或放宽误差标准。
- 后端线程/背压/取消/播放 fence、源哈希/资源打包声明、架构边界和原输入协调器回归：
  44 passed，18.25s。后端控制竞态使用确定性帧模型；真实权重测试另列，不能混报。
- 日志在 `/tmp/ai2apps-haru-full-model-tests.log`、
  `/tmp/ai2apps-haru-integration-tests.log`、`/tmp/ai2apps-haru-zh-benchmark-paced.log`。

已在 Runtime 1.8.18 签名候选内，以随包 Python 3.11 和标准 Managed Service Sandbox
启动私有 Worker，禁网并显式授权 Metal；真实 Haru WebSocket 25 帧、认证拒绝、
停止/恢复播放及断线清理通过，往返 p95 24.45ms。该证据为隔离候选测试，
正式 Runtime 发布状态见发布台账；不是已安装 Haru 模型 Package 或用户麦克风验收。

尚未注册生产 Haru Model Package，未部署面向用户的模型网络服务。没有重启/替换
Dev 或 App-Dev。由于包含 Runtime 代码/依赖，后续激活必须走标准 builder 重建固定
App-Dev，再核验 source root、实际模块及资源；只重启 Local 不足以更新内嵌 Runtime。
