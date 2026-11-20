# Cloud 语音双工模型兼容需求

日期：2026-11-18。交付对象：AI2Apps Cloud 开发项目。
本文件为需求交接，不表示 Cloud 已实现或部署；本仓库不修改 Cloud 后端。

## 本地合同与分阶段范围

本地新增模型类型 `audio_realtime`、默认 capability `speech_duplex`，区别于
`audio_stt`、`audio_tts` 和 `audio_generation`。Runtime 候选为
`ai2apps/runtime-omlx 1.8.18`，新增 Runtime capability `audio-duplex-v1`。
Package 发布状态以正式发布收据为准，不能只因本文写出版本就认定已上线。

第一阶段仅要求 Registry/Discover/安装依赖能够承载并原样分发签名声明。
本机麦克风与本机模型之间的音频留在 Local，不需要经 Cloud 转发。
第二阶段才考虑 Mobile 远程接入、Cloud 中继或云端推理，不能将第二阶段
作为第一阶段本地运行的前置条件。

## 第一阶段：模型与 Runtime 目录

请核对并补齐以下兼容点：

1. Package 提交、manifest 校验、模型目录投影、搜索/筛选及详情支持
   `audio_realtime` 和 `speech_duplex`，不强制转换成 TTS/普通 LLM。
2. 保留 `audio_capabilities` 的 `schema: ai2apps.audio-capabilities/v1`、
   `operations: [audio_realtime]`、`formats: {input: [pcm], output: [pcm]}`、
   `streaming: {mode: native|pipeline, formats: [pcm]}` 及 `duplex` 子合同。
3. 签名 `duplex` 字段为：`protocol: ai2apps-audio-duplex/v1`、`mode`、
   `sample_rate`、`frame_samples`、`text_output`、`text_input`、
   `async_result_injection`、`response_cancel`、`voice_reference`、
   `maximum_session_seconds`。能力以签名声明为准，不从模型名推断。
4. 当前 Runtime 协议只实现持续音频输入、音频/文字输出及播放控制。
   `text_input`、`async_result_injection`、`response_cancel` 必须为 false，
   不把停止播放解释为取消模型响应或 Bot Task。native 与 pipeline 必须区分展示。
5. Runtime 包的 `audio-duplex-v1` 能力可发现，模型 Package 可以声明
   对同一官方 Runtime 的最低版本和能力依赖，不创建第二个 Runtime 身份。
6. 旧客户端不支持新模型类型/会话协议时，明确返回需要升级宿主；不能仅升级
   Runtime 就假称旧 Desktop 已有语音入口。Runtime capability、Host 功能版本
   与 Package compatibility 契约版本分别核对。
7. 新模型权重依旧遵循固定 HF/MS revision、Registry distribution、piece/文件
   校验、许可/审查和安装协议；无需把权重打入 Runtime。Haru 模型 Package
   的独立发布不在本次 Runtime Cookie 授权范围内。

验收需要：正常与错误声明、未知字段/版本、旧客户端、新旧模型并存、原始签名
字段回读一致、最低 Runtime 依赖解析、未安装实例的发现/下载/验签/安装。
先确认现有 Cloud 是否已经以开放元数据支持这些字段；已兼容的部分无需重复开发。

可供 Cloud schema/投影测试的模型条目示例（仅为合同夹具，不是已发布 Haru Package）：

```json
{
  "id": "example.realtime/haru",
  "model_type": "audio_realtime",
  "upstream_id": "higurashi-ai/Haru-4B",
  "capabilities": ["speech_duplex"],
  "audio_capabilities": {
    "schema": "ai2apps.audio-capabilities/v1",
    "operations": ["audio_realtime"],
    "languages": ["zh", "en"],
    "formats": {"input": ["pcm"], "output": ["pcm"]},
    "streaming": {"mode": "native", "formats": ["pcm"]},
    "duplex": {
      "protocol": "ai2apps-audio-duplex/v1",
      "mode": "native",
      "sample_rate": 24000,
      "frame_samples": 3200,
      "text_output": true,
      "text_input": false,
      "async_result_injection": false,
      "response_cancel": false,
      "voice_reference": true,
      "maximum_session_seconds": 600
    }
  }
}
```

`duplex` 为严格字段集合，数值不能接受 boolean。通用 Runtime 允许 sample_rate
8000–48000、frame_samples 80–48000，单帧时长还需在 10ms–1s；会话上限为
1–3600 秒，模型声明继续收窄。Haru 当前值如上。PCM 格式固定单声道 f32le，
语音参考为 3–30 秒；Worker 单消息上限 4 MiB、待处理队列最多两帧、空闲上限
30 秒。Cloud Gateway 若后续实现，至少保持同等约束，不能扩大为无界媒体代理。

## 第二阶段：可选实时 Gateway/云端推理

若产品要让 Mobile 远程使用 Local 模型或使用 Cloud 托管推理，再定义并部署：

- 绑定 actor、Installation/Profile、Bot 主对话及 VoiceSession 的短期连接授权。
  Gateway 验证当前权限、控制者租约与 epoch；不可暴露 Worker bearer、提供商
  长期密钥或原始 Worker 端口给 HTML/Mobile。
- 双向媒体传输、协议协商、帧大小/速率限制、有界背压、空闲/总时限、断线清理。
  重连不重放旧音频或旧 Task 指令；模型连接与持久 Bot 任务分别恢复。
- Worker 内层 `/v1/audio/realtime` 是可信 Host 的私有 WebSocket 接口。
  当前拒绝带 Origin 的浏览器直连；Cloud 不能把它直接作为公开模型 URL。
  对外 Gateway 的版本与路由须另行设计，不能把本内层路由误标为已部署 Cloud API。
- 音频进入云端前说明处理位置；默认不落盘，日志不含原始音频、参考声音、
  凭证或完整敏感上下文。录音留存单独征得用户选择并支持期限/删除。
- 并发、配额和计费合同明确“已接受、正在连接、正在推理、已停止”；按真实
  用量结算，不以模型生成过或客户端未听到作为完成/成功依据。
- Cloud 不替 Bot 执行器授权、回答审批或重试未知效果。任务事实仍来自原 Bot。

第二阶段验收另覆盖跨实例拒绝、撤权、过期/旧 epoch、双窗口接管、流量积压、
限额、离线/超时、实际手机网络及费用回执。未实现之前，本地模式应保持可用，
界面不能展示可用的 Cloud 双工入口。

## 本地证据与待交付

Haru 官方 MLX 核心及本地后端已完成真实权重连续帧测试，见
`bot-haru-mlx-20261118.md`。共享 Worker 双工协议、鉴权、控制和清理正在随
Runtime 1.8.18 构建/验收。后续需由 Cloud 项目返回受影响 schema/API 清单、
部署版本、目录/安装验收结果及第二阶段是否纳入当前产品范围。
