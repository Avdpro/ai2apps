# 音乐与音效 Mini-App 套件 0.1.0

同一 App Package `ai2apps/audio-generation-suite` 提供两个 Voice Studio Mini-App：

| Mini-App | ID | 基础功能 |
| --- | --- | --- |
| 音乐生成 | `ai2apps.audio-generation.music` | ACE-Step / Stable Audio 模型选择、描述、时长、ACE-Step 可选歌词、种子、采样步数、取消 |
| 音效生成 | `ai2apps.audio-generation.sfx` | Stable Audio SFX、描述、时长、种子、采样步数、取消 |

Package 版本为 0.1.0，两个组件同版本、同安装及启停生命周期。仅在 Voice Studio Mini-App 目录展示，App Launcher 不新增独立套件首页。英文为 fallback，包名、组件和 UI 提供中文。模型范围由签名能力声明约束：ACE-Step 为 10–120 秒，Stable 为 1–120 秒；歌词仅对支持的模型显示。

模型缺失时由 Host ACPF 选择和安装 Runtime 1.8.9 与已发布模型 Package；两个音乐模型是可选项，不强制同时安装。Stable 权重下载沿用绑定具体分发清单和条款哈希的用户许可确认。Frame 不接触 Cookie、Worker 地址、原生路径或权重下载地址。

生成结果由 Host 检查 WAV 格式后写入用户的 Voice Studio Artifact 会话。Mini-App 只显示输入和状态；播放、保存、拖拽及历史均使用已有共享 Preview & Output。切换 Mini-App 不过滤或清空输出。生成是受控的长请求，不是可重启恢复任务；点击取消或关闭 Frame 会请求取消 Worker。

## 签名候选

- 文件：`packages/ai2apps-audio-generation-suite/dist/0.1.0/ai2apps-audio-generation-suite-0.1.0.ai2app`
- SHA-256：`6e070e0f01e2900b9fc72262ed20049dcfd929463eae7738289109c5898dc658`
- 大小：12,892 bytes
- Publisher：`229d6350-cd0e-408a-9905-41367385ae5c`
- Key：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- 通过标准 `scripts/build_signed_registry_release.py` 构建；两次确定性 Contract 构建一致，文件索引、两项 Mini-App 投影及 detached Publisher 签名有效。

此候选**尚未发布 Cloud**。旧模型 Package 的 Cookie 授权没有用于此新 App Package。Host 增加了 Studio 音乐／音效 Broker 与 ACPF Profiles，需要纳入下一版 Desktop；当前生产 Desktop 不应被描述为已具有这些新能力。

## 验收

- 73 项相关回归通过；随后新增断开连接触发原生取消测试通过，套件专项共 6 项通过。覆盖权限、错误模型、时长、歌词、额外路径字段拒绝，以及取消时不发布输出。
- 共享输出契约与跨 Mini-App 选择 Node 测试通过。
- 实际套件源码的两个 Studio placement、热刷新、无 Package Store 安装记录，以及没有 Development 标志时拒绝源码挂载通过。
- 正式签名 App 候选安装到独立验收 Host，使用已签名 Runtime 1.8.9 / Stable Audio 0.1.0，两个真实 mount 各生成 10 秒音频。输出分别带正确 Mini-App 身份并进入同一个 Host Artifact 会话。
- 已安装包的资源摘要校验及生产 opaque-frame 静态资源内联通过；整包禁用、启用、卸载均同时作用于两个组件。
- 固定 App-Dev 已发现两个源码入口；使用认证 BiDi 分别等待正确资源及 Host 挂载完成，验证两个组件中英文名称、表单关联标签、无重复播放器，以及 Space 键展开高级选项均通过。实机 App-Dev 未安装这两个生成模型，推理证据来自上述隔离签名安装环境。

本轮只通过固定 App-Dev 的标准 Helper 重启 Local，没有重建 App、迁移实例数据或修改 Cloud。首次发布无旧版本可升级／回滚，版本升级闭环不在本候选验收范围。

证据位于 `artifacts/audio-generation-suite-0.1.0/`，包括构建、实际安装推理、生命周期、回归及 UI 检查记录。源码与其他进行中的工作共存；候选字节以上述摘要为准。

## 2026-10-06 模型下拉菜单增强

音乐和音效的模型下拉列表末尾均提供“安装模型…”（Install model…），调用各自能力的 Host ACPF `setup(installMore=true)`。操作前恢复已选模型，安装完成后刷新模型列表；取消或失败保持原选项。无模型时同样可使用。保留旁侧安装按钮。

16 项交互检查覆盖两个组件、中英文、有／无模型及成功／取消；7 项套件与 Host bridge 回归通过。新候选重新签名，并单独验证签名安装、两个组件资源、启停和卸载。此前真实推理记录属于上一候选摘要 `e079c0cf43c45025d7a53c0cce4d73c400a218fd3a694164a74b372f672076de`；本轮未重复模型推理，推理链路无修改。候选仍未发布 Cloud。
