# 音频参数表单实机验收阻点（2026-10-18）

已激活 App-Dev，Local PID 86752、port 53519。App 与 Helper source root 均为当前 checkout；运行日志的 ModelInvocation 等模块路径、实际服务的参数表单/录音 JS 字节均匹配 checkout。

## 已验证

- 真实 General Agent 调用 Mini-App `voice-design.transcribe`，Chat 渲染表单，文件上传、预填语言覆盖、Qwen3 ASR 选择、真实转写和返回原 Agent 完成。
- 原 Session 为 `ses_e84d90c43d7941b398bf73a55a69f468`，完成 Run 为 `run_b8e5f704447f476bbbed4c4d213dd625`。
- 后续 App `voice.transcribe` 表单实际开始/停止麦克风录音，生成 WebM；Local 重启后草稿保留。
- 表单内发起真实 ACPF。失败后取消配置返回原表单，不取消 Agent，不丢失录音素材。
- Gallery Mini-Entry 实机暴露 Chat 默认 inline 与 Gallery sidebar-only 声明不匹配；修复挂载位置选择后实机打开侧栏成功，导入专用测试 WAV 成功。
- 13 Python 表单/交接测试、16 JS 表单/交接测试、52 项 ACPF 回归通过。ACPF 包含 Runtime 重启继续安装测试。没有在本次实机中执行 Runtime 升级，不能将这些回归写成实机 Runtime 升级验收。

## 未通过：SenseVoice 安装 ready

安装计划原先没有显式列出必需的标点 Checkpoint，现已采用已有组件栈列出 Runtime、SenseVoice 与标点 Provider、两个 Checkpoint、最终验证。没有改变 ACPF orchestrator 的重启实现。

实机两个 Checkpoint 均完成后仍失败：`Capability Service did not become ready after activation`。已安装签名 Package `ai2apps/model-sensevoice-small` 0.2.2 的模型 metadata 只有：

```json
{"required_model_ids":["ai2apps.model.punctuation-restorer/default"]}
```

当前隔离模型依赖机制要求同时明确声明：

```json
{"checkpoint_dependencies":[{"service_id":"ai2apps.model.punctuation-restorer","model_id":"ai2apps.model.punctuation-restorer/default"}]}
```

`list_package_models` 只在显式声明存在时，经 digest-locked required Package 解析依赖 Checkpoint；没有该声明，必需模型不在受信解析结果中，ready=false 是正确行为。不能靠忽略 required_model_ids、拼接任意缓存路径、修改已签名安装目录或伪造 ready 来通过。

后续应升级 SenseVoice 的 Package 契约，按 Package publication runbook 构建/签名/发布并安装修正版本，再跑“ACPF ready → acknowledge → 原表单选择模型 → 提交 → 原 Agent”实机流程。本轮没有修改签名 Package 或执行生产发布。

## 未完成：实际跨 frame 拖拽

原生自动化两次从 Gallery 测试 WAV 卡片拖入表单，没有观察到素材 ID 改变。Finder 与 Gallery 的 drop handler 单元测试通过，文件选择上传和 Gallery 侧栏导入实机通过，但不能据此宣称真实跨 frame 拖拽通过。需继续确认拖拽事件在 AceFox Shell 的传递。录音测试草稿保留为 waiting_input，可用于后续复验。
