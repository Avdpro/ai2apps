# Owner Mobile 三个 Studio：Cloud 对接要求（2026-10-08）

状态：客户端接入已实现；Cloud 已部署 owner-mobile-studios-20261008-v1，真实 Owner Chrome 入口已复测；此文不是生产部署回执。此前 mobile-iframe-r3 只解决图库/知识库/待办，不能覆盖 Studio。

## 客户端边界

- Imagine Studio、Voice Studio、Video Studio 注册 Mobile 入口，页面分别为 `/mobile/app-content/ai2apps.imagine-studio`、`/mobile/app-content/ai2apps.readaloud`、`/mobile/app-content/ai2apps.video-studio`。
- 公网 API 仅由 Owner 会话租约建立身份，使用独立 ASGI 应用，绝不把 Cookie/API Key 转成管理登录，也不转发到主服务器。
- 复用现有 actor、installation、AppInstance、session、Gallery handle、Package mount 的归属校验。每次请求检查 Host/Origin/租约，流式响应生命周期继续受租约约束。
- 固定 API 清单：`ai2apps/web/owner_studio_routes.json`。新增桌面路由不会自动进入清单。补充 API 在 `ai2apps/web/owner_studio_gateway.py` 的 `EXTRA` 中。
- 本机路径打开/保存、Browser transfer、管理/安装/凭据接口没有开放。JSON 中的 sourcePath/source_path、targetPath、outputRoot、localPath 被拒绝，素材须上传或使用归属当前 Owner 的 Gallery handle。
- Gallery/Artifact HTML、SVG 内容仅附件下载，并有 sandbox/default-src none 响应策略。

## Edge 转发

现有生产配置在 Mobile 以外默认返回 404，因此需要新增以下**精确方法与路径**转发规则：

1. 将上述 JSON 清单中的已声明方法和路径转发到该 Device Local。`{id}` 等参数只匹配一个路径段；`{mini_app_id:path}` 使用实际 Mini-App 标识的单段字符集即可（字母、数字、点、短横线、下划线），不开放任意子路由。
2. `/v1/platform/studios/{studio_id}/...` 的 studio_id 必须仅为这三个 Studio ID。
3. 补充：GET `/v1/models`；POST `/v1/chat/completions`；POST `/v1/images/generations`、`/v1/images/edits`；GET/POST `/v1/videos/generations`；GET/DELETE `/v1/videos/generations/{task_id}`；POST `/v1/videos/joins`；POST `/v1/audio/transcriptions`（已安装的 STT Model Package，服务端使用 Owner invocation context）。
4. **不要开放整个 `/v1/platform/*`、`/admin/*`、`/v1/*`**，也不修改 Owner/普通成员权限与租约期限。匿名与非 Owner 请求应仍拒绝。
5. 文件上传、Range 下载、SSE 保持正常，关闭请求/响应代理缓冲；沿用已有大小与超时上限，Local 继续执行各接口的内容大小校验。

请从源文件生成或逐项核对代理清单，不手工猜测路由。客户端清单是路由能力边界，不是绕过身份认证的依据。

## 三类页面 CSP 必须分开

### 受信任 Host Studio 页面

上述三个精确页面，以及 Gallery Mini-Entry `/mobile/app-content/ai2apps.gallery?surface=mini`，客户端已输出：

```
default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'none'; form-action 'none'
```

原因：现有受信任 Host 使用 Alpine 表达式、动态布局与本地媒体预览。不得把此策略扩大到普通页面、用户文件或 Package。脚本不需要 unsafe-inline。

当前 r3 的 app-content 分支隐藏上游 CSP 并重新写入 default-src self，会阻止 Alpine 表达式和 Blob/data 预览。请对上述精确路径使用匹配策略，或完整保留客户端同等策略，确保响应只有一条有效 CSP，无 XFO DENY。

### Package Mini-App

资源前缀：`/mobile/app-content/studio-resource/{instance_id}/resources/{resource}`，带 `mount_id`（和兼容的 `studio_id`）查询参数。Local 验证当前 actor 可访问 mount、父 Studio 实例和资源摘要。

**必须保留 Local 的 CSP，不隐藏/替换 sandbox 指令**；包括生产 opaque-origin sandbox（不含 allow-same-origin）及 frame-ancestors self。即使来源是 App-Dev source-mounted Package，Mobile 也不启用同源开发特权。不能套用 Host Studio 的 Alpine 策略。

### JSON/媒体 API

这些不需要被 iframe 嵌入，不放宽 frame-ancestors。保留 Local 对 HTML/SVG 附件的 sandbox/default-src none/nosniff，不把 Gallery 用户文件转成可执行的同源网页。

## 验收与回执

- 生产生效配置与仓库模板同时更新；通过 nginx -T 确认真实 include，再做语法校验和可回滚 reload。
- Owner：Apps 显示三个 Studio；列表→Mini-App→Output→返回→重开；草稿保留；真实生成结果进入原有 Output；素材上传/Gallery 选择/下载/加入 Gallery。
- Voice 所有 Mini-App 共享原有 host-owned Output，不增加第二套 history、播放或删除逻辑。
- Package：opaque sandbox、Host bridge、取消/重开、Output 发布；不可访问管理 API。
- 安全：匿名、普通成员、过期/撤销租约、错误 Host/Origin、跨 Owner 资源 ID 拒绝；桌面路径和新添未知路由拒绝；跨源 iframe 阻断。
- 分别记录 Chrome 与 iPhone Safari；不以单元测试或桌面窗口缩窄代替 iPhone 实机。
- 不记录 Cookie、handoff、租约 token 或私有原始请求。

## 当前明确未接入的桌面能力

手机 Studio 隐藏依赖桌面 Chat mount 的 Mini-App Chat 标签；独立 Mobile Chat 不受影响。手机不执行本机路径保存、原生目录批处理或依赖安装。三个 Studio 的核心列表、草稿、任务、共享 Output 与 Gallery 接入不依赖这些桌面功能。

## 客户端验证记录

- 2026-10-08：Owner Studio/租约边界/原 Mobile Library 共 60 项 Python 通过；Voice Studio 与 Studio bridge 原有 14 项通过；Mobile 导航、Gallery 长按/拖动与 Voice scope 共 14 项 Node 通过。
- 覆盖匿名/非 Owner/错误 Origin/撤销租约拒绝、原生路径拒绝、冻结路由与实际 Router 一致、三份真实 Mobile 模板及静态清单、Gallery 跨用户隔离与 Range、图片/语音 invocation 的 Owner 身份。生成调用使用隔离测试替身，不代表真实模型验收。
- 固定 AI2Apps-app-dev.app 已通过标准脚本重建，verify-release-app 与 codesign 严格校验通过；保持 app-dev、cloud Runtime、Development source-root、未启用生产更新合同。原生标题验证为 AI2Apps-App-Dev: App-Dev 127.0.0.1:50664。没有重启或替换 dev/Test。
- 真实公网 Studio 生成、Package 操作和 iPhone Safari 实机验收仍待本需求的 Edge 配置部署后补齐。

## Cloud 部署后的客户端复测（2026-10-08）

- Cloud 生产回执：`/Users/avdpropang/sdk/ai2apps-cloud/docs/owner-mobile-studios-production-2026-10-08.md`，140 个精确方法/路径组合；Cloud 记录 828 个隔离探针与 22 项 Remote 测试通过。
- 公网目标确认为 dev。旧 Local 进程尚未加载 Studio 注册；通过该实例官方 Helper 控制接口重启后，Local PID 96063、端口 55673。未操作 app-dev 或 Test；未复制实例数据。
- 使用既有 Chrome Owner 账号正常重新授权后，Apps 出现语音工坊、视频工坊、创意画坊，三者实际页面均加载成功。
- Chrome 390×844 布局：三个 Studio 均首先显示 Mini-App 列表；文生图、快速朗读、文生视频可进入编辑器。Imagine/Video 右上角输出可打开，既有 Run 历史正常加载；Video 返回 Home 后重开仍保留输出页。
- 真实生成未通过：Quick Read 选择本地 Qwen3 TTS CustomVoice 8-bit 后显示“配置语音生成”，未发起生成；模型就绪依赖仍需核对。未调用付费 Cloud 生成。
- Package bridge、真实生成闭环、上传与素材交互、iPhone Safari、非 Owner/过期/撤销租约的真实浏览器验收仍待补齐；不将 Cloud 隔离探针或 Chrome 窄窗口视为这些实机验收。
