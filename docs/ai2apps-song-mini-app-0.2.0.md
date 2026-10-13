# 歌曲创作 Mini-App 0.2.0 实现与验收

日期：2026-10-06。状态：0.2.0 已发布，YuE2 模型及双源亦已发布；Host 仍待 Desktop 交付。最终制品与本次验收见 `docs/ai2apps-yue2-audio-packages-release-2026-10-06.md`。下方初始验收保留历史范围。

## 功能与边界

`ai2apps/audio-generation-suite` 0.2.0 在原音乐、音效入口之外增加
`ai2apps.audio-generation.song`，同一 Package 原子安装、启用、禁用及卸载。

歌曲创作提供音乐方向、歌词段落按钮、完整/仅旋律/关闭规划、可编辑 UTF-8 ABC 导入
（128 KiB）、最长时长、种子、合成步数、引导强度、草稿保存、实际阶段进度和取消。
最长时长是生成上限，不是精确时长；到达上限会提示结尾可能截断。
中英文界面、表单标签和键盘操作均有支持。阶段保存、断点恢复、局部重跑和转写不属于本版。

Host 使用 `audio.song_generation`，只显示签名模型声明中带有
`audio_generation.workflow: ai2apps.song-generation/v1` 的模型；普通音乐与歌曲模型列表分离。
调用 Runtime 1.8.10 的 `ai2apps.audio-generation/v2`，由 Host 校验自动时长、规划模式与 token 上限。
阶段状态通过现有 mount/actor 绑定的 invocation SSE 返回，不显示虚构的整体完成百分比。
取消/断开连接会停止调用；最终 WAV 由 Host 验证并保存到 Voice Studio 共享 Preview & Output。
Mini-App 没有自己的播放器、下载、拖拽或输出历史。

模型下拉菜单与按钮均触发歌曲专用 ACPF；配置绑定 `ai2apps/model-yue2-mlx >=0.1.0,<1.0.0`
和 `ai2apps/runtime-omlx >=1.8.10,<2.0.0`。YuE2 模型现已发布，下载前仍需用户确认原始许可。
Runtime 1.8.10 已满足协议要求，本次不需要再次修改 Runtime；Host 改动仍须随 Desktop 后续版本交付。

## 验证

- 109 项 Python 回归通过：歌曲 Host/协议、模型声明、原音乐/SFX、共享输出和跨生产者保留。
- 18 项中英文 Mini-App 交互检查通过：工作流参数、ABC 导入/上限、草稿恢复、安装失败选择保留、取消和阶段进度。
- Host JavaScript 消息链测试通过：SSE、共享输出事件、普通取消和能力探测期间的提前取消。
- Voice Studio 跨 Mini-App 输出选择测试通过，覆盖音乐、音效、歌曲及其他 Package 入口。
- 本地签名制品验证通过；真实安装发现三个入口，资源内联与沙箱文档验证通过。
- 在已安装 Runtime 1.8.10 上用本地 QA YuE2 适配器执行真实推理，再经真实 Host 输出持久化：
  46.5986667 秒立体声 WAV，规划、音乐生成、合成、解码、保存五阶段均观测到。
  共享输出记录归属 `ai2apps.audio-generation.song`；未达时长上限。
- 安装包禁用/启用/卸载原子性通过，卸载 Package 不删除共享输出。
- QA 模型绑定是隔离验收注入，不是已发布 YuE2 模型 Package，也不代表模型多源安装验收完成。
- 固定 App-Dev 原生窗口确认歌曲入口、中文界面、歌词输入、草稿保存和下拉菜单安装选项；
  安装选项实际打开仅含 YuE2 的 ACPF 选择器，取消后恢复表单并保留草稿；
  共享右侧输出保持已有选择。Helper BiDi 的 getTree 返回空列表，实机观察改用精确嵌入 Shell 路径的原生辅助功能；未读取 Cookie。

证据位于 `artifacts/song-mini-app-0.2.0/`；自动测试为
`tests/song_mini_app.test.cjs`、`tests/song_studio_bridge.test.cjs`、`tests/test_audio_generation_suite.py`，
以及已有 Voice Studio/Runtime/Provider 回归。

## 初始签名候选（已被最终发布制品取代）

- Package：`ai2apps/audio-generation-suite` 0.2.0。
- 制品：`packages/ai2apps-audio-generation-suite/dist/0.2.0/ai2apps-audio-generation-suite-0.2.0.ai2app`。
- SHA-256：`f7013d8551c96b778aff966f86f452724094b3556c5a2c37f8f12092a26d6dc5`。
- 大小：23041 bytes。
- Publisher：`229d6350-cd0e-408a-9905-41367385ae5c`。
- Publisher key：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`。
- 通过标准 `build_signed_registry_release.py` 构建；未读取发布 Cookie，未提交或发布 Cloud。
