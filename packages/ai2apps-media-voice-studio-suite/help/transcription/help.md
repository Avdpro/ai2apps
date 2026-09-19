# 录音文本记录

选择音频或视频后，设置语言和预计角色数量。模型执行阶段会先生成匿名说话人标签与逐字时间戳；
角色姓名必须由用户确认，不会从声音自动推断真实身份。

当前 MVP 已通过可信 mount 调用 Host Capability Broker，并使用本机安装的 Detailed
Transcription Compact 或 Quality Package。若能力尚未就绪，请先在 Models/ACPF 配置模型。
