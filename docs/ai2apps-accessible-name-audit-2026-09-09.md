# Shell / App / Mini-App 可访问名称源码审查（2026-09-09）

结论：已有较好的局部实现，但尚未形成一致的控件命名覆盖，不能直接视为未来语义 UI
自动化测试的完整基础。缺少 `aria-label` 不一定是问题：可见按钮文字、正确关联的
`label`、有效的 `aria-labelledby` 都可以提供名称。真正需要整改的是无名称、名称含糊、
仅依赖 placeholder/title，以及动态渲染后无法明确区分目标的控件。

## 范围与限制

本次为当前混合工作区的静态源码审查，检查 Shell 模板及动态 Dock/Launcher 渲染，
Terminal/Coder 表单与工具栏，Voice/Video/Imagine Studio、Chat/Gallery Mini-Entry，
以及 media-voice Studio Package 的共享动态表单和角色编辑生成器。
不是所有页面、所有条件分支的逐控件认证；没有进行浏览器可访问树、屏幕阅读器或
键盘实机验收，也没有据此计算通过率。现有工作区的其他修改保持不变。

## 已确认的实现与缺口

文件路径均相对于仓库根目录；行号为本次审查时的位置。

| 页面/组件 | 源码证据 | 判断与后续动作 |
| --- | --- | --- |
| Shell 主界面 | `ai2apps/web/templates/shell.html`：Dock 按钮、Launcher 搜索框、关闭按钮；`ai2apps/web/static/js/shell.js:475`、`:516`、`:574` | 已有明确名称，动态模式切换和 Pin/Unpin 会更新名称；仍有硬编码英文，应补做多语言一致性检查，不能把局部正确推断为所有 Shell 控件通过。 |
| Terminal / Coder | `ai2apps/web/templates/system_apps/terminal.html:18`、`:40`；`coder.html:83` 起的表单 | Terminal 主要图标工具按钮已有 aria-label；Coder 所查表单使用包裹 label。此类无需仅为属性数量重复添加 aria-label。 |
| Chat Mini-Entry / Mini-App Chat | `ai2apps/web/templates/system_apps/chat_mini.html:11`；`ai2apps/web/static/js/mini_app_chat.js:258` | 消息 textarea 只有 placeholder，没有关联 label/ARIA 名称；Mini-App 模式只更新 placeholder。需提供随当前语言及用途一致的明确名称。模型选择器已有名称，发送按钮已有可见文字。 |
| Voice Studio | `ai2apps/web/templates/system_apps/readaloud.html:29`、`:31` | 项目标题 input 未关联 label；添加角色图标按钮没有名称；分段 speaker/emotion 等选择器需逐个补关联标签和行上下文。`:27` 的试听按钮只有动态 title，应提供明确操作名称并限定所属片段。 |
| Video Studio | `ai2apps/web/templates/system_apps/video_studio.html:13`、`:68`、`:75` | 通知关闭、清除首帧/尾帧按钮只有图标，缺少名称。`:9` 的侧栏按钮和 `:39` 的打开 Gallery 按钮只有 title；应补 aria-label，清除图片时区分首帧/尾帧。 |
| Imagine Studio | `ai2apps/web/templates/system_apps/imagine_studio.html:10`、`:12`、`:27` | 折叠和关闭通知已有动态 aria-label；打开 Gallery 按钮仍只有动态 title。已有改进但覆盖不一致。 |
| Gallery Mini-Entry | `ai2apps/web/templates/system_apps/gallery_mini.html:8` | 打开完整 Gallery 按钮只有 title；上传入口为含隐藏 file input 的图标 label，应提供有名称、可聚焦的键盘选择入口并实测。通知关闭按钮已有 aria-label。 |
| Package Mini-App 动态表单 | `packages/ai2apps-media-voice-studio-suite/web/mini-app.js:129`、`:162` | 文件选择器与 checkbox 使用包裹 label，普通字段用 htmlFor + id 正确关联；不能因为静态 HTML 中无控件或 aria-label 少就判定不合格。 |
| Package Mini-App 角色编辑 | 同上 `mini-app.js:223`、`:225` | 角色名称输入已有带序号 aria-label；删除按钮可见内容只有 `−`，title 为“删除角色”，名称缺少明确动作/对象语义。应加入角色上下文并验证增删后的名称。 |

## 整改与验收顺序

1. 优先补齐完全无名称的图标按钮、Chat 输入、Voice 项目标题及片段字段；复用现有本地化。
2. 再将仅靠 tooltip/title、符号和不明确重复名称的入口改为明确动作及对象上下文，补齐键盘入口。
3. 在固定 `AI2Apps-App-Dev` 的真实 Shell/App/Mini-App mount 中验证可访问树、焦点和状态，
   覆盖中英文、动态行、错误、运行状态及重挂载。Package Mini-App 必须检查 iframe 内部。
4. 将“正确 role + 非空且明确的 accessible name + 可操作状态”纳入新增/修改控件的回归要求。
   稳定 test ID 仅辅助定位，不代替语义验收。后续实际修改页面时同步维护 Desktop Release 台账。

本次只更新审查和开发规范，没有修改页面行为，也没有宣称上述缺口已修复。
统一要求见 [App 开发指南](ai2apps-app-development-guide.md#控件命名与自动化测试规范必选)、
[Studio 设计规范第 16 节](ai2apps-studio-app-ui-design-standard-v1.md#16-可访问性与交互一致性) 和
[Mini-App Package 合同](ai2apps-studio-mini-app-package-contract-v1.md#required-accessible-names-and-ui-test-contract)。
