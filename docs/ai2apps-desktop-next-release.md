# AI2Apps Desktop 下一版 Release 台账

### NXR-RELEASE-2259-20261009：Desktop 0.1.5 Build 2259

- 状态：`released_pending_target_mac`。2026-10-09 11:27（北京时间）完成 Apple 公证、GitHub/ModelScope 双源发布、Cloud 完整下载/Range/摘要预检、0% 登记及 100% 扩灰。当前生产基线为 0.1.5 / 2259。
- 源码 `0c318c71b5eadd99fe61db395da5a90da4801cd7`，clean worktree 构建并已推送 main；GitHub tag `v0.1.5-build2259`，MS 不可变 revision `3e1bf46de8c02aaf9dbd23015458c03a5c722569`。
- 最终 DMG 268922700 bytes（约 256.5 MiB），SHA-256 `fcfaef3675d39151d34d6a71cefa97bd091d2fff7a7392757a8258e87511f6b7`。Apple submission `22f9c7eb-40f9-49e2-a0d4-d32d6c8cc14a` Accepted；签名/staple/Gatekeeper/metadata 配对通过。
- 生产清单摘要 `9ea49e72e57215baaa63d5489394c97c5daa417661dde9784530932c2783da74`，同一 rollout ID `build2259-test`，10000 basis points。GET/HEAD 200、条件请求 304、无 Set-Cookie、六个既有 API 200；容器 healthy/restart 0、最近 15 分钟 error/fatal 0。审计记录 26/27，2258 回退点保留。
- 范围以 `docs/ai2apps-desktop-2259-scope-audit.json` 的构建前快照、源码提交和回执中的实际 Bundle 比较为准。完整纳入 Desktop 的情报中心/后台 WebAgent、Todo/Codex、音乐音效歌曲 Host、H3 分段任务、Mobile/访客客户端与脱机/BYOK；不含新 Spark/CUDA 部署和未发布模型实验。模型 Runtime/权重仍独立下载，就绪开关与用户启用策略不变。
- 回执：`docs/ai2apps-desktop-0.1.5-build2259-release-2026-10-09.json`。该回执列出的源码实现为 included；本台账后续旧“未发布”等文字属于历史。实机/真实模型/权限期限等剩余验收不自动关闭，目标 Mac 升级闭环仍待验收；仅 2258→2259 资格检查为 eligible。
- 本轮未重建 Dev/App-Dev/Test，未读取 Dev Cookie。只清理服务器本次内存盘临时工件，正式双源、本地制品、审计与历史保留。
- 已知发布工程问题继续延期：GitHub CI runner 缺少 av，PyPI 工作流拒绝 Desktop tag 与 Package 版本格式不匹配；均与前版一致，不能称 GitHub CI 全绿。Homebrew/Dependency Graph 成功；完整本机回归与各日志见回执。

### NXR-RELEASE-2259-PREFLIGHT-20261009：发布回归合同核对

- 状态：发布前检查已完成，2259 已发布；以下保留发布前调查与修复历史，以本文件顶部发布回执为准。
- 用户选择先修复回归、发布完整 2259；独立候选位于 /private/tmp/ai2apps-release-2258 的 codex/release-2259 分支。Spark/CUDA 与未发布模型实验不纳入；候选源码版本为 0.1.5，尚未提交/构建。初始及增量文件清单保存在 /private/tmp/ai2apps-2259-source-inventory-initial.json 与 /private/tmp/ai2apps-2259-source-inventory.json。
- 本轮修复：情报中心测试改用真实后台 Runtime，并独立验证前端 finish/progress 对 Local 拥有任务返回 409；旧 finish 合同仅用 legacy 记录测试。浏览器/Studio 测试补齐页面稳定等待、语言化 URL、DOM 和隔离 Tab 身份。服务器测试明确回环 Host，不放宽公网路由边界。数据库清单补齐 78–87；保留迁移账本完整性和 2258 SDPA provider reset 修复。
- 产品补丁：Mobile App 内容路由先校验角色/可用性，再访问设备开放策略；补齐 ACPF 音乐/音效/歌曲/放大中英文提示以及首页公网入口七种语言与状态文案。
- 后续产品修复：带附件 WebAgent 的参数重推断原先引用未定义 runtime，现从已验证 runtime_store 获取；15 项附件/参数回归通过，保留附件归属和未使用参数清理合同。
- 发布测试门禁完成：全量历史失败的 17 个在范围内测试文件集中完整复验 466 passed、2 deselected；结合完整候选已通过用例与最终 Core 分片，当前范围 11552 个不同 Python 用例通过、69 skipped、74 deselected（分批完成，非宣称单次全量全绿）。Swift 77 + 2 XCTest、Node 346 + 44、原生后台 BiDi 1 项通过。日志 /private/tmp/ai2apps-2259-all-failed-files-final.log 和 /private/tmp/ai2apps-2259-runtime-final.log。开始冻结源码并构建，生产仍为 2258。
- 最终索引检查补充：首次 staged diff 检查发现新文件的行尾空白，8 个第一方文件已做仅空白格式化；第一方 scoped diff 检查通过。保留 4 个第三方 vendor/原始许可证文件的上游空白，不声称全提交原始 diff --check 零诊断，不改写已发布 Package 的许可证字节。通用 Worker 的按后端延迟导入适配属于共享 Host 兼容代码，不包含新 CUDA 模型包、推理环境或 Spark 部署。
- 最终分片进度：Core 8924 passed、68 skipped、19 deselected；Desktop 的 Imagine/存储/Shell 151 passed；后台 Agent/扩展/文档转换 72 passed；音频/Cloud Runtime 131 passed。此前全量进程收集了修复前模块，128 failed、11431 passed、69 skipped、74 deselected、4 errors，不能直接称全绿；所有仍在候选内的失败文件正在集中完整复验。415 个改动 Python 文件关键 Ruff 与 132 个 JS/CJS/MJS 语法检查通过。
- 源码范围逐项索引：docs/ai2apps-desktop-2259-scope-audit.json，475 条历史/开放记录；不把 source inclusion 等同于 UI/真实模型验收。未新增 Spark/CUDA/未发布 AVTR 实验，候选中误收集的五个相关测试副本已移除，原开发目录保留。GitHub main 的 Runtime 1.8.9/1.8.10 配方提交已 fast-forward 保留。
- 已验证：Node 346 + 44 项通过；情报中心 Python 42 项通过；正常主机上的 Local/Shell 等合并复测为 804 passed、1 skipped、4 failed（四项后续合同修复正在重验）。原生后台 BiDi 独立验收 1 passed/30.55s：临时隔离 Profile、20 万字符、上传、提取、关闭 HTTP 客户端后继续后台任务与重新连接均通过；未读取用户网页或模型缓存。
- 受限环境 MLX/Metal 导入崩溃与默认 testserver Host 被公网边界拒绝不能记为成功；完整候选改用正常主机环境运行。当前日志 /private/tmp/ai2apps-2259-candidate-full-r2.log、/private/tmp/ai2apps-2259-candidate-focused.log、/private/tmp/ai2apps-2259-native-acceptance.log。未替代最终签名 App 的目标 Mac 升级验收。
- 用户授权 0.1.5 / 2259 发布、公证及必要的 Dev Cookie 使用；Todo 修复后恢复准备。
- Todo 定向 Python 103 项、前端 46 项通过；Swift 77 项 Swift Testing 通过。首次完整 Python 收集 12329 项，达到 20 个失败门限停止（441 passed、1 skipped、74 deselected），不视为全量通过。
- 首批测试合同修正：展示 JSON 修复预算为两次修复（三次调用）、独立能力命名使用 work_simple、身份替身补齐 local_principal_for、个人空间替身补齐 owner_home。未放宽产品验证或移除失败用例；情报中心后台迁移等剩余回归继续核对。
- 日志：/private/tmp/ai2apps-2259-python-preflight.log、/private/tmp/ai2apps-2259-focused-failures.log、/private/tmp/ai2apps-2259-todo-node-correct-cwd.log、/private/tmp/ai2apps-2259-swift-preflight.log。正式候选范围、clean-tree 和最终回归尚未完成。

### NXR-VISITOR-SESSION-LEASE-20261009：匿名访客持续浏览

- 状态：implemented_dev_chromium_10min_verified。接入 personal-space-anonymous-session-v1，独立8小时/30分钟会话与120秒短租约，server-only proof、single-flight、幂等与版本检查，前台阅读POST心跳、后台不延长闲置，同版本不重绘。旧协议不升级，开关与内容未改变。
- 76项Python、8项Node通过，新增HTTP专项后7项会话测试通过；最终Dev PID80116/60039真实Chromium连续10分27秒、同会话10次续租200、0失败、1次交接，页面未中断。详细记录 ai2apps/docs/anonymous-visitor-session-local-2026-10-09.md。iPhone/opaque sandbox/真实关闭与完整8小时期限未验收。


### NXR-ANONYMOUS-VISITOR-20261009：匿名访客协议 Local 接入

- 最新状态：implemented_dev_anonymous_text_verified。Cloud 1.64.1 published boolean 已接入，纯文字空间零 App 数量保持真实。Dev 单实例就绪配置启用，通过标准 Helper 重启到 PID 73190/55625，用户空间开关和内容未改变。真实内置浏览器免登录显示已发布文字；独立空 Cookie 客户端交接/匿名 bootstrap 成功、重放401、Owner/private API 403/404。69 项 Python 回归及新增 readiness 后 16 项空间测试通过。原 Cloud 文本阻塞已解决；iPhone/opaque sandbox/真实过期关闭矩阵仍待测，120秒上限未变。


- 状态：implemented_tests_passed_cloud_text_status_blocked，未启用就绪标志或重启。匿名完成页、独立 Cloud 断言验证、一次性 opaque 会话、发布/开关能力同步与旧快照撤销；Owner 协议不变，无匿名 Local principal。
- 68 项 Python、6 项 Node 与 scoped diff 检查通过。Cloud publishedAppCount=0 判为 unpublished 阻断文字/链接主页，已形成修复需求；不虚报 App 数量。记录 ai2apps/docs/anonymous-visitor-local-integration-2026-10-09.md，Cloud 交接 ai2apps/docs/cloud-anonymous-text-space-fix-2026-10-09.md。
- 真实匿名浏览器、过期/撤销安全矩阵、opaque sandbox Cookie Chrome/iPhone 验收仍待完成。现有三环境构建未加载本轮 Python 更新。


### NXR-VISITOR-EDITOR-ENABLE-20261009：首次开启流程与管理页提示

- 状态：implemented。首次按钮明确标为“发布并开启访客空间”，顺序保存修改、发布快照、开启；任一步失败停止。已发布空间开启保留原有已发布版本，不自动发布后续草稿。
- 读取平台标准 error.message，保留 detail 兼容；成功/错误/普通提示分别采用 Account 的绿色/红色/中性灰色。管理页文字、边框、输入与主按钮统一中性色，访客预览保留选定主题。保存和发布合并状态，保留 App 通道就绪元数据。
- 6 项 Node 测试与编辑器 JS 语法检查通过，覆盖首次保存/发布/开启版本顺序及发布失败不执行开启。静态版本更新；未刷新用户带未保存修改的页面，未代用户发布或开启空间。Test 需后续重新构建才包含此变更。


### NXR-VISITOR-RECOVERY-ROOT-20261009：恢复链接禁止退回 Cloud 根路径

- 状态：implemented，待 iPhone 原路径复测。移除访客空间模板中 coder.ai2apps.com 根地址兜底；仅在持有严格校验的固定 /u/ 用户 URL 时显示重新进入链接。首次交换/Bootstrap 失败且无有效 URL 时提示重新扫码，不暴露错误导航。拒绝凭证、查询、fragment 和异域 URL。
- 4 项 Node 测试与 JS 语法检查通过，含无缓存/非法缓存/有效用户链接的失败恢复。静态脚本版本更新；Dev/App-Dev 刷新即可加载，Test 已有构建不包含此后续变更。截图与生产 Cloud 根路径 JSON 完全一致，具体触发操作尚未复现；不宣称所有 Owner 恢复链路已验证。


### NXR-VISITOR-SPACE-20261009：内置访客空间 MVP

- 2026-10-09：用户要求的 Dev / App-Dev / Test 标准构建全部成功，严格签名与实例身份通过，三实例首页启动通过。Test 输入 AceFox 通过原有 mach build faster/package 刷新；未修改安全补丁。详见 ai2apps/docs/dev-app-dev-test-build-2026-10-09.md。

- 状态：implemented_local_appdev_verified，Cloud 端到端待完成。开发计划 ai2apps/docs/visitor-space-development-plan-2026-10-09.md；Cloud 交接 ai2apps/docs/cloud-visitor-space-requirements-2026-10-09.md。
- 内置管理 App、安装绑定草稿/发布快照/撤销代次，默认关闭；独立零权限 sandbox Open-Entry 资源通道，Cloud 就绪标志默认关闭。数据库 schema 86。不得将 Owner Mobile App 自动开放为访客 App。
- 55 项 Python、2 项共享预览 Node 测试通过。固定 App-Dev 已标准重建并通过 release verifier/codesign，窗口标题与身份合同已验收；管理页面打开、编辑保存草稿和手机预览实测通过。空间保持关闭，未发布 Desktop；公网 Dev 已在 2026-10-09 三环境构建中重启。Cloud 资源通道/访客长会话、贪吃蛇 1.0.2 签名发布、非 Owner/iPhone 验收待完成。详见 ai2apps/docs/visitor-space-implementation-2026-10-09.md。

### NXR-MOBILE-PACKAGE-BRIDGE-JSON-20261009：Sandbox App 加载 500

- 状态：implemented。Dev 日志确认蛇来运转加载握手后 /v1/mobile/app-mounts/{id}/bridge 收到非 JSON 请求体并抛 JSONDecodeError。Mobile Shell 的 context POST 现在显式 JSON.stringify 并声明 application/json；更新静态缓存版本。
- 7 项 Mobile 导航测试通过，新增测试走真实 request 与 message handler，验证请求体、Content-Type、context 回传和加载状态。无需重启或 Package 升版；iPhone 刷新复测待完成。

### NXR-MOBILE-RECONNECT-20261009：失效会话重连恢复

- 状态：implemented。已知设备 Host 上 GET /mobile 的 HTML 导航在 Owner Cookie 缺失或失效时，303 返回严格校验的 Cloud 用户 URL；无可信 URL 时回公开 member complete。API、资源、未知 Host、非 GET 不放行、不重定向。恢复按钮不再刷新受保护页面。
- 23 项 Owner gateway、7 项会话前端测试通过；手机原报错地址确认为 /mobile#app=ai2apps.general-chat。已通过官方 Helper 重启公网 Dev Local（端口 52100）；本地及公网匿名 HTML GET /mobile 均实测 303 到固定账户 URL，匿名 /v1/mobile/apps 保持 403；真实 iPhone 重连待复测。

### NXR-MOBILE-STALE-MOUNT-20261008：App 旧实例 404 恢复

- 状态：`implemented`。Mobile 复用挂载 focus 返回 404 时，清除该 App 的失效 Frame/挂载引用，按目录中的 App ID 通过现有授权 open 路由重开一次。401/403/500 不重试，首次 open 404 不循环，导航序列过期不再恢复。
- 6 项 Mobile 导航测试通过，JS 语法及 scoped diff 检查通过；模板缓存版本更新，静态刷新生效，无重启或 Cloud 改动。用户截图是绘图 App 打开请求 404，尚未捕获该次实际失败 URL，不能将旧实例失效认定为已证实的唯一根因；公网手机恢复待复测。

### NXR-STUDIOS-MOBILE-AUTO-OUTPUT-20261008：所有 Studio 新素材自动打开 Output

- 状态：`implemented`。共享 studio_mobile 导航监听三个 Host 的输出刷新：Imagine runs、Voice 唯一 studioOutputs、Video tasks/提取音轨/合成/放大/Package runs，以及通过宿主发布的 Package 素材事件和视频合并结果。新成功结果自动选中并打开共享 Output，返回保留原工作区；首次历史刷新、失败/取消、重复刷新及桌面宽度不自动跳转。
- Voice 不新增输出历史/播放器、不按 Mini-App 过滤或重置共享输出、不触碰 Line 私有缓存。三个模板缓存版本同步更新，静态刷新生效，无重启或 Cloud 改动。
- 10 项共享导航测试、Voice 跨 Mini-App scope 测试通过，JS 语法与 scoped diff 检查通过。真实手机各类模型/Package 生成完成后切换仍待实机复测，未为此次导航改动执行付费生成。

### NXR-IMAGINE-MOBILE-AUTO-OUTPUT-20261008：绘图完成自动查看输出

- 状态：`implemented`。Imagine 成功完成 Cloud/BYOK 轮询、本地绘图和图片调整导出后自动打开共享 Mobile Output；放大图片沿用成功轮询。先选中本次 Run，再切换输出；失败/取消不触发，初始历史刷新不触发。统一共享导航与 Imagine 的 openMobileOutput，重复完成通知不覆盖返回位置，返回保留编辑器草稿。
- 6 项 Studio Mobile 导航/拖动/自动输出测试通过，Imagine JS 语法及 scoped diff 检查通过。更新脚本缓存版本；静态刷新生效，无重启、无 Cloud 改动。未为视觉验收调用付费绘图，手机真实生成完成后切换待复测。

### NXR-MOBILE-MODEL-CATALOG-20261008：Owner Mobile 对话模型目录

- 状态：`implemented`。Owner /v1/mobile/models 在现有租约内将公开目录与桌面管理目录合并，仅返回显式展示字段；合并 Cloud/Fusion、规范别名稳定 ID、去重并携带收藏/就绪标志，不返回 settings、密钥、路径或 Fusion 配置，不开放 /admin 路由。
- Mobile 补齐 Fusion 与 work-only LLM、收藏排序、API Default 路由，并先读取默认模型再构建列表；保留音频/图片/视频/嵌入模型排除和不可用模型过滤。会话模型继承及温度默认策略不变。
- 18 项 Python、11 项 Node 通过，JS 语法及 scoped diff 检查通过。通过官方 Helper 单独重启公网 dev Local（PID 44700）；未重启 app-dev，未重建、未修改 Cloud。真实 Chrome Owner 重新授权后模型选择器正常加载，新增此前缺失的 (BYOK) DeepSeek · DeepSeek-V4.1-Flash，既有 Cloud 对话模型保留；未列出语音模型。状态为 `implemented_owner_chrome_verified`，iPhone 刷新复测待确认。

### NXR-MOBILE-CHAT-STREAM-20261008：Chat 空回复与流错误显示

- 状态：`implemented`，未发布。Mobile Chat 接受带/不带空格 SSE data、分块 UTF-8 与末尾无换行数据，兼容 JSON completion；流中 error 不再被解析 catch 吞掉，无正文不再保存空 assistant 消息。失败移除临时空气泡，刷新历史后再显示错误，避免错误被重绘清除。更新脚本缓存版本。
- 7 项 Chat 流解析/模型记忆 Node 测试通过，JS 语法和 scoped diff 检查通过。未更改 Cloud 或模型参数；截图这次 gpt 6 luna 的上游响应尚未捕获，不宣称真实模型已恢复。手机刷新后需重发验证，既有空历史不自动删除。

- 2026-10-08 真实公网续验：同一 Owner Chrome、同一 gpt 6 luna，旧 Mobile 默认 temperature=0.7 返回 Cloud lifecycle failed/provider request failed。Mobile 请求显式 temperature=null，令现有网关采用模型默认温度（与桌面一致），重新加载后同对话发送 hi 得到“Hi! How can I help you today?”。未修改 Cloud、未重启实例。
- 补齐 ai2apps_cloud failed 事件真实错误显示及结构化文本 content；共 10 项流解析/模型记忆/请求参数 Node 测试通过，语法及 scoped diff 检查通过。状态更新为 `implemented_owner_chrome_verified`；iPhone 刷新后复测仍待用户确认。

### NXR-GALLERY-MINI-BOOTSTRAP-20261008：图库 Mini-Entry 加载修复

- 状态：`implemented_mobile_owner_verified`。Gallery Mini-Entry 改为遵循 app_base_template，Mobile 使用 mobile_app_base.html，避免错误加载 /admin/static Alpine/Lucide 和被 CSP 拒绝的桌面内联启动脚本。图库头图标使用已有 images 图标，更新 Mini-Entry 脚本版本。
- 共享 galleryApp.init 增加幂等保护：Alpine 自动 init 与遗留 x-init 不再重复加载或注册窗口事件，覆盖桌面及 Mobile。保留权限边界，无 Cloud 改动。
- 30 项 Owner Studio Python、6 项 Gallery Node 通过，JS 语法及 scoped diff 检查通过。真实公网 dev Chrome Owner 的 Imagine 素材内嵌 Gallery 已加载 6 个目录、34 个素材、88 个 SVG 图标。未重启或重建；静态页面刷新生效。iPhone Safari 及桌面偶发空白实机复现仍待验证，不宣称桌面全部根因已消除。

### NXR-OWNER-MOBILE-RECOVERY-20261008：Mobile 会话恢复页面

- 状态：`implemented`，未发布 Desktop。Owner 会话结束时清除私有 Frame 并显示手机友好的连接卡片；按钮返回严格限定的 coder.ai2apps.com 固定用户 URL。经过服务端有效状态返回的 URL 保存到当前标签页 sessionStorage，供刷新后首次校验失败恢复使用；仅作导航提示，不作为权限凭证。无 URL 时显示重试和重新扫码提示，不推测账号、不自动循环跳转。
- owner_session.js 缓存版本已更新；7 项会话前端测试通过，包含首次校验失败的恢复与恶意 URL 拒绝，JS 语法和 scoped diff 检查通过。静态变更无需重启，现有旧错误页需刷新一次加载新脚本。iPhone Safari 真实过期恢复待复测。

- 2026-10-08 样式修复：移除动态内联 style，改由已允许的 mobile_app.css 外部加载恢复页样式，避免公网 CSP 拦截。加入浅色渐变背景、品牌图标、圆角卡片、深色主按钮、安全区和矮屏适配；连接结束时 blur 当前及子 Frame 输入，标题接收非输入焦点以收起键盘。缓存版本更新，7 项会话测试及语法/diff 检查通过；无需重启或 Cloud 改动，iPhone 实机视觉/键盘复测待确认。

### NXR-INTELLIGENCE-ENTITIES-20261008：跨频道实体与机会线索
- 状态：`app_dev_verified`。已增加按用户隔离、跨频道共享实体档案、逐条引用与历史版本、人工归属纠正、自然语言关注规则、机会线索和单轮实体问答。26 项 Python、9 项 Node 定向测试通过。App Dev 62009 实测已有微博文章生成两个实体/六条引用事实，关注规则保存、无充分证据时不生成机会、重复检查跳过、其他频道共享查看均通过。有机会时的反馈分支由定向测试覆盖。提醒为 App 内数量；每轮最多评估五个变化实体，依赖 Shell 采集后接续处理。详见 ai2apps/docs/intelligence-center-v1.md。未重建、未发布。

### NXR-INTELLIGENCE-WEIBO-IMAGES-20261008：微博正文图片显示
- 状态：`app_dev_verified`，未发布。排除 tvax 头像 CDN 和头像节点，提取 video poster；历史卡片/标题图/详情缩略图/大图统一跳过头像。对已保存的 wx1–4.sinaimg.cn 公开正文图片提供按文章所有权校验的本地加载入口，带微博 Referer，禁止跳转，限 8 MiB、校验图片签名、私有缓存，不读取 Profile Cookie。正文采集和图库导入仍沿用源 Profile。20 项 Node、2 项 Python 检查通过，语法及 diff 检查通过。App Dev 标准 Helper 重启至 53202，实际 RADO 帖子的列表图片和详情标题图均正确显示腕表照片，旧头像被排除；无需重新生成文章。无重建、无发布。

### NXR-OWNER-MOBILE-STUDIOS-20261008：三个 Studio 的 Owner Mobile 接入

- 状态：cloud_deployed_owner_entry_verified。注册 Imagine / Voice / Video Mobile 入口，增加带 Owner 租约的独立 Studio API 应用，冻结可公开路由清单并复用现有 actor/AppInstance/mount 归属检查；不使用管理员 Cookie/API Key 转发，不暴露整个 Platform/Admin。
- Package Mini-App 使用专用 Mobile resource 路径并验证 Studio 父实例、live mount、资源摘要及原 sandbox。补齐静态依赖、Gallery Mini-Entry 路径和 Mobile locale。
- Cloud 已部署 owner-mobile-studios-20261008-v1，140 个精确方法/路径组合与分层 CSP；客户端复测记录：ai2apps/docs/cloud-owner-mobile-studios-20261008.md。
- 验证：60 项 Owner/Studio/Library Python、14 项既有 Voice/bridge Python、14 项 Mobile/Voice Node 通过；真实 Mobile 模板依赖清单、Gallery Range/跨用户隔离、原生路径拒绝、图片/语音 Owner invocation context 均覆盖。生成调用使用隔离替身，不等于真实模型验收。
- 固定 App-Dev 已标准重建，verify-release-app 与 codesign --verify --deep --strict 通过；原生标题 AI2Apps-App-Dev: App-Dev 127.0.0.1:50664，保持 app-dev/cloud/Development/source-root 与禁用生产更新合同。首次构建未操作 dev/Test；本次 Cloud 部署后已通过官方 Helper 单独重启公网 dev（PID 96063、端口 55673），使 Studio 注册生效，未操作 app-dev/Test。清单 JSON 已加入 package-data。
- Mobile 隐藏尚依赖桌面挂载的 Mini-App Chat；模型安装仍在 Mac 完成（允许只读能力 probe，不开放 ensure/confirm）。真实 Chrome Owner 重新授权后 Apps 已显示三个 Studio，390×844 下列表和编辑器均加载，Imagine/Video 输出历史加载、Video 返回 Home 后重开通过。Quick Read 所选本地 TTS 显示需配置，未生成；真实生成、Package bridge、素材交互、iPhone Safari 和负向权限实机验收仍待补齐。


### NXR-INTELLIGENCE-POST-FILTER-20261008：帖子质量过滤与恢复
- 状态：`in_progress`。频道配置宽松/标准/精选与保留偏好；微博列表初筛、帖子详情复筛结合频道兴趣和顶踩偏好，模型结构化决策逐条校验。过滤记录按用户/频道保存原因、阶段和原始证据，支持恢复；完整正文恢复后下一轮进入整理，列表记录恢复后允许后续重新发现和读取。历史过滤避免重复打开，人工恢复不再被质量筛选拦截。
- 24 项 Python、18 项 Node 定向检查通过，语法与 diff 检查通过。App Dev 标准 Helper 重启至 49322，默认标准配置保存、更新记录入口和空记录面板已验证。实现完成；实际微博采集仍沿用既有冷却及待验收状态，真实内容过滤质量尚待端到端复测，不标记完整 app_dev_verified。无重建、无发布。

### NXR-INTELLIGENCE-FORMAT-CARDS-20261008：六类内容卡片与筛选
- 状态：`app_dev_verified`，未发布。网页文章、帖子、视频、音频、图片/图集、文档/报告采用独立列表布局，新增类型筛选；历史来源按平台/URL 识别，明确 AI 摘要/综合，混合来源保留多类型筛选。引用证据增加可选类型/时长/页数，缺失不补造。
- 验证：25 项 Python、41 项 Node 检查通过，JS 语法及 diff 检查通过；1440px/390px 六类隔离样例验证，App Dev 标准 Helper 重启至 63948，实际 YouTube 视频卡片、25 篇历史网页文章及类型筛选通过。无重建、无发布。本轮是展示适配；微博自动采集仍按下项待验收。

### NXR-INTELLIGENCE-WEIBO-20261007：微博账号与话题点击采集
- 状态：`in_progress`。账号 UID 主页及话题来源、站内搜索输入提交、可见正文链接原生点击、新标签绑定与关闭返回、微博正文与图片提取已实现；沿用每源 Profile、去重及平台共享冷却。无直接导航详情 URL 回退。YouTube 导航流程本轮未改变。
- 增加 not_started 预约释放：只在 browser session 未创建时恢复此前预约，不对已开始访问的网站清除冷却；过期 token 不能释放后续租约。
- 20 项 Python、24 项 Node 定向检查通过。App Dev 标准 Helper 重启至 62242，建立“微博腕表测试”，保存 RADO 官方 UID 1938210792 与 #腕表# 来源。手动站内输入/点击搜索、点击正文新页成功；自动首轮初始化失败未访问网站，核对精确日志后恢复该次误写预约。第二轮话题目标确认失败、0 篇；补充输入可见性与值核对、导航等待和保留页面，修正后尚待复测，话题源仍冷却至 10 月 8 日 05:41。账号自动正文采集未验收，不能标记 app_dev_verified。无重建或发布。
- 文件：`ai2apps/intelligence/social.py`、`models.py`、`store.py`、`api/intelligence.py`、共享 BiDi SDK、情报中心 JS/模板及测试。详见 `ai2apps/docs/intelligence-center-v1.md`。

### NXR-INTELLIGENCE-YOUTUBE-SEARCH-20261007：YouTube 搜索与话题来源
- 状态：`app_dev_verified`。新增关键词搜索、话题标签来源创建与编辑，生成标准结果页/hashtag 地址，保留用户搜索筛选 sp 参数；原链接添加仍可用。复用每源 Profile、平台冷却、有限滚动及详情前按视频 ID 去重，搜索页不整页入库。
- 18 项 Python、6 项 Node 定向检查通过，覆盖中文编码、筛选条件、非法来源、搜索结果去重和旧版社交采集路径。标准 Helper 重启后的 App Dev 端口 58566。解锁后建立“YouTube 腕表搜索测试”频道，验证关键词“腕表”创建及编辑回显，Default Profile 实际检查 30 个视频、读取 2 个、成功生成 2 篇简报（1 个网页文字稿、1 个仅标题简介）；封面、正文与引用截图确认。连续第二次更新读取/变化/生成均 0，日志显示冷却至 10 月 8 日 05:12，没有启动新采集页。关键词主流程实机通过；话题标签与筛选参数仍由定向测试覆盖。未重建或发布。
- 文件：`ai2apps/intelligence/social.py`、`web/static/js/intelligence_social.js`、`web/static/js/intelligence.js`、情报中心模板、社交来源测试及 `ai2apps/docs/intelligence-center-v1.md`。

### NXR-INTELLIGENCE-YOUTUBE-20261007：YouTube 社交来源与低频采集
- 状态：`in_progress`。实现已落地，58 项 Python、28 项 Node 定向检查通过；真实站点修正后复测仍待完成。
- YouTube 频道/视频 URL 归一化，专用 DOM 列表和详情提取、封面与可见网页文字稿/简介覆盖标注；打开详情前排除已收录视频，每轮最多 2 个新视频。
- 社交来源默认 6 小时间隔，持久化源冷却、跨频道/Profile 平台共享租约、失败退避、验证码暂停及人工恢复；有限滚动、串行停顿，无指纹伪装或验证绕过。浏览器仍使用原生 BiDi Gateway 和每源 Profile。
- App Dev Local 通过标准 Helper 重启，端口 54907。建立 YouTube 测试频道及官方 OpenAI 来源；首轮 empty_page、生成 0 篇，手动页面检查可见正常视频列表。随后补充新版卡片选择器与不重新导航的 SPA 等待，相关检查通过。实机已确认下次采集时间为 10 月 8 日 00:17，未清除冷却反复访问；修正后的真实详情/生成文章链路待复测，不能标为 app_dev_verified。未重建或发布。
- 文件：`ai2apps/intelligence/social.py`、`models.py`、`store.py`、`service.py`、`api/intelligence.py`、共享 `browser_bidi_client.js`、`intelligence_social.js`、`intelligence.js`、情报中心模板及测试。完整说明见 `ai2apps/docs/intelligence-center-v1.md`。

### NXR-INTELLIGENCE-WRITING-20261007：按情报范围撰稿与对话修改

- 状态：`app_dev_verified`。文章、栏目、频道、热点新增撰写入口，支持短 Post、长文、视频稿、播客稿、简报及内容指导；资料限定在所选范围（最多 20 篇/80000 字符），冻结引用证据，对话修改保存最新版与沟通记录。新增频道稿件列表、复制、引用跳转、请求去重、版本并发保护和 owner 隔离；失败保留原稿。
- 56 项 Python、24 项 Node 定向检查通过。App Dev 从浪琴文章生成短 Post、对话修改保存第 2 版，刷新后从稿件页恢复完整稿件、引用和对话；其他范围以隔离测试验证。标准 Helper 重启 app-dev Local（端口 53016），未重建或发布。详见 ai2apps/docs/intelligence-center-v1.md。

### NXR-INTELLIGENCE-IMAGES-20261007：文章多图与 Gallery 收藏

- 状态：`app_dev_verified`。共享 BiDi SDK 提取封面和相关正文图片（每源 24 张、每篇 48 张），详情底部缩略图支持放大与前后切换；通过原信息源 Profile、共享资源传输 helper 和现有 Gallery 导入 API 保存图片、去重并记录来源。已有文章支持手动补图。共享 helper 新增可选 preferExact，避免将懒加载占位图作为选中图片导入；其他调用默认不变。
- 52 项 Python、23 项 Node 定向检查通过。App Dev 实机为浪琴文章补齐 13 张图片，验证大图并成功加入 Gallery，刷新后确认 L3.809.4.93.9_FACEtiff.jpg（316.4 KB）；早期测试占位图已移入废纸篓。标准 Helper 重启 app-dev Local（端口 51185）并刷新页面，未重建或发布。详见 ai2apps/docs/intelligence-center-v1.md。

### NXR-INTELLIGENCE-FEEDBACK-20261007：文章顶踩与偏好记录

- 状态：`app_dev_verified`。文章支持顶/踩和撤销；踩理由由 Standard 模型依据当前频道、文章生成，至少选择一项后保存。按 owner 保存结构化当前偏好，验证理由与当前上下文一致，支持修改、缓存与过期保护；文章更新保留理由，撤销清除有效偏好，频道删除级联清理。
- 51 项 Python、19 项 Node 定向检查通过。固定 App Dev 腕表文章实测生成 5 项理由、选择保存、详情回显、修改恢复选项与撤销；测试反馈已清除。标准 Helper 重启 app-dev Local（端口 49679），未重建或发布。详见 ai2apps/docs/intelligence-center-v1.md。

### NXR-INTELLIGENCE-TOPICS-20261007：频道热点话题

- 状态：`app_dev_verified`。近 7 天最多 60 篇情报按具体事件/产品聚合为最多 8 个热点，每个热点至少 2 篇相关文章；显示摘要、相关文章与封面，支持手动整理与采集后自动更新。服务端逐篇核对具体对象 anchor 和文章引用，避免同品牌不同型号宽泛合并；具备版本签名缓存、owner 隔离、并发和过期结果保护。
- 47 项 Python、18 项 Node 定向检查通过，最终 anchor 版本相关 Python 16 项复验通过。固定 App Dev 使用腕表频道 25 篇文章生成朗格 TRIPLE SPLIT 铂金镀铑盘版本热点及 2 篇相关文章，确认右侧文章跳转和标准样式；仅标准 Helper 重启 app-dev Local（端口 64826），未重建或发布。采集后自动触发未额外运行整轮采集实测。详见 ai2apps/docs/intelligence-center-v1.md。

### NXR-INTELLIGENCE-COVER-20261007：原文标题图采集和展示

- 状态：`app_dev_verified`。共享 BiDi SDK 提取原文封面元数据或正文大图，通用/编译采集统一接入；仅从引用证据选图，列表和详情显示，旧文章支持按原信息源 Profile 补图，失败回退文字布局。情报中心桌面/移动 HTML 的 CSP 仅增加 HTTPS 图片来源；其他页面、脚本与 connect-src 限制不变，已有路由 CSP 保留。图片使用原站 URL、no-referrer，不代理下载，原站链接失效时回退文字。
- 55 项 Python、40 项 Node 通过。实机从 Fratello 浪琴 Spirit Pilot 原文通过原 Profile 补图，确认列表封面、详情大图、出处链接及 Local 重启后保留；仅标准 Helper 重启 app-dev（端口 62502），未重建或发布。详见 ai2apps/docs/intelligence-center-v1.md。

### NXR-INTELLIGENCE-CHAT-20261007：频道右侧栏对话

- 状态：`app_dev_verified`。右侧栏对话/文章详情切换，基于本频道文章与上下文追问并显示可跳转引用；按用户及频道持久保存对话，提交幂等，失败可重试。首版通过有界词匹配选取文章，不实时浏览网页或检索关联库内其他内容。
- 39 项 Python、13 项 Node 通过，覆盖隔离、持久化、重试、引用校验、选文预算、频道切换和文本转义。标准 Helper 仅重启 app-dev Local；实机完成朗格与浪琴动力储存对比问答、引用跳转、文章上下文入口和刷新后历史保留，未重建或发布。详见 ai2apps/docs/intelligence-center-v1.md。



### NXR-INTELLIGENCE-KNOWLEDGE-20261007：频道关联多个系统知识库

- 状态：`app_dev_verified`。频道创建/设置可关联多个已有系统知识库或新建专用私有库，历史文章补录与新文章/更新自动同步；持久化队列、幂等条目和 revision 防止重复或旧确认覆盖新任务。每次同步校验写入范围，失败可重试，解除关联/删除频道保留已入库内容，用户删除知识条目不自动复活。
- 验证：66 项 Python、10 项 Node 通过（含真实 KnowledgeStore 多库、版本更新、断点重试、权限、删除与失败隔离）。固定 App Dev 仅标准 Helper 重启 Local，界面为现有腕表频道新建并关联私有“腕表情报”库，25 篇全部补录，待同步 0；系统知识资料库确认 25 项及来源。新生成文章和多库更新由集成测试覆盖，本次未额外触发外站采集。队列随页面打开推进，未发布。详见 ai2apps/docs/intelligence-center-v1.md。

### NXR-INTELLIGENCE-SITE-AGENT-20261007：网站采集 WebAgent 编译与复用

- 状态：`app_dev_partially_verified`。实现完成。复用 AgentBuilderRepository / compile_source 编译与版本仓库，规则仅从真实观察的 DOM 区域选择；列表与已确认文章链接比对、正文与通用提取的文本片段比对，通过后保存 evidence 并激活。App 管理规则不参与用户站点 Agent 自动选择/合并，避免覆盖其工作。
- 按 owner、规范化源 URL、列表/正文类型复用，继续使用每个源指定 Profile；未激活、失效和编译器旧版规则不复用。失效回退通用提取，每种规则每源每轮只学习一次。浏览器操作保留原生 BiDi SDK、稳定性、Cookie 和访问检查；不生成任意脚本。日志记录复用、学习请求、回退和耗时。此版不固化翻页/任意交互。
- 44 项 Python 与 40 项 Node 测试通过，涉及现有编译/执行、规则验证/激活、隔离、跨频道复用、回退与 Cookie 处理。仅标准 Helper 重启 app-dev Local，未重建或发布。
- 实测两个网站均保存列表与正文规则。Fratello 连续两次完整复用：每轮 4 次复用、0 学习请求、0 回退（18.7 秒、12.8 秒）；腕表之家正文复用 3 次且列表规则通过校验。最后一次腕表之家首页导航超时，整轮 partial，随后 Computer Use 读取/刷新持续超时，未完成追加复测或截图。腕表之家完整暖运行待复测；各轮页面不同且网络波动，未宣称稳定整体加速比例。详见 ai2apps/docs/intelligence-center-v1.md。

### NXR-INTELLIGENCE-SECTIONS-20261007：AI 频道栏目

- 状态：`app_dev_e2e_verified`。创建频道时由 Standard 模型按兴趣生成 4–8 个有明确范围的栏目；新情报按栏目 ID 归类、界面按栏目筛选。旧频道可创建栏目并对既有文章补分类，失败不提交部分结果。29 项 Python、7 项 Node 测试通过，涵盖失败事务性、栏目 ID 与完整分类校验、隔离、状态保留和组合筛选。App Dev 实测腕表生成 7 个栏目、12 篇历史情报全部归类，机芯与技术筛选显示 2 篇；仅重启 Local，未重建或发布。当前不含栏目手动编辑或重规划。

### NXR-INTELLIGENCE-ICON-20261007：Discover 与情报中心图标调整

- 状态：`app_dev_e2e_verified`。按最终选择，Discover 导航与页头使用原情报中心的 Lucide `radar` 雷达屏幕图标，情报中心导航与页头使用原 Discover 的 `satellite-dish` 卫星天线图标，沿用标准单色线条样式。两个 App 的 Dock 与页头均已实机截图验证；仅重启 app-dev Local，无需重建，未发布。

### NXR-INTELLIGENCE-PREFILTER-20261007：采集前排除已收录文章

- 状态：`app_dev_e2e_verified`。列表候选在详情导航前对照 owner/频道隔离的成功 pages 历史，过滤后取前 3 条未处理文章；已有历史直接适用。URL 忽略跟踪参数与 fragment，保留功能查询参数；记录原始请求 URL 以识别重定向别名，同轮跨源已读 URL 也排除。
- 全部候选已处理时只读列表，不再打开文章、不回退生成列表摘要。没有文章列表的页面型源继续正文比较。失败/未提交指纹的页面仍可重试；普通刷新不再复查同 URL 已收录文章的正文改动。日志显示跳过数。
- 23 项 Python 与 6 项情报浏览器测试通过，覆盖连续采集排除已读、补下一批、全部命中零详情导航、失败重试、频道隔离、参数规范化和重定向。固定 App Dev 实测腕表之家与 Fratello 各检查 20 条、跳过 3 条历史文章、读取 3 篇未采集文章；整轮 completed，共跳过 6 条并生成 6 篇新情报，总文章数 6 → 12。仅通过标准 Helper 重启 app-dev Local，无需重建，未发布。

### NXR-INTELLIGENCE-STYLE-CONSENT-20261007：标准 App 样式与 Cookie 对话框

- 状态：`app_dev_e2e_verified`。情报中心改用共享 dashboard 主题变量与语言字体、标准中性色按钮/频道/分段标签，去掉独立紫蓝配色与装饰性英文标题。
- Fratello Cookiebot 真实弹窗提供 Deny，旧共享 PageAccess 未识别。修复位于 BiDi 客户端 SDK：在可见 Cookie/隐私面板内识别 Deny/拒绝等安全动作，通过原生指针点击、检查遮挡、等待稳定并复查；最多三次，未关闭则保留 Profile 页面请求协助，不将其当作已读取。
- 生成失败保留已验证的各信息源日志与具体错误，仍不提交页面指纹，允许重试。
- 真实生成失败诊断定位为证据全局编号与文章局部编号混用：模型输入、evidence_ids 和正文统一从 1 开始的全局编号，验证来源后由服务端按文章来源顺序映射局部引用。仍拒绝越界、未声明、缺失与重复来源；新增重排引用回归。诊断仅记录校验类型与字段，不记录正文。
- 22 项 Python、23 项 Node 定向测试通过；固定 App Dev 标准主题实机显示正常，Fratello 默认 Profile 成功读 3 篇并生成 3 篇带正确来源的新情报，总文章数由 3 增至 6。最后一轮腕表之家发生导航超时，来源失败日志与 partial 状态正常保留，不影响 Fratello 成果提交；此前两轮该源采集成功，外站超时未宣称解决。仅通过标准 Helper 重启 app-dev Local 加载 Python/静态资源变更，未重建或发布 Desktop。

### NXR-INTELLIGENCE-CENTER-20261007：情报中心首版

- 状态：`app_dev_e2e_verified_preview`。新增用户隔离的频道、信息源、采集记录和情报文章本机存储，以及独立三栏 App；AI 根据真实搜索结果推荐信息源，复用 BiDi Gateway/共享 SDK 采集公开网页与社交话题。
- 每个信息源保存 AI Browser `profile_key`，可独立选择；推荐搜索也先选择 Profile。复用现有 Profile launch 生命周期，以本轮唯一页面 URL 精确绑定 BiDi context，只关闭本轮页面；非默认 Profile 保存校验 actor 所有权，已删除 Profile 不静默回退。
- 首版边界：页面与 AceFox 保持打开时按间隔更新，重开补一次；每源每轮最多读取列表前 3 项，无列表时比较当前页面。不会操作社交平台关注按钮。没有 Cloud 代码变更。
- 同频道原子运行认领、失联回收、源级失败记录、正文指纹增量、模型输出/引用约束；生成成功后原子提交，失败不吞掉新内容。按事件合并/更新由模型完成，文章保留引用与最近历史版本、兴趣反馈。
- 系统 App 注册和 omlx Admin 三处 host/template/tab 映射已接入。固定 App Dev 通过 build-app-dev-environment.sh 重建，verify-release-app、codesign deep/strict 与身份/源码根/禁用生产更新/实时原生标题核验通过。21 项 Python 与 2 项 Node 定向测试通过。
- 实机验证：默认 Profile 真实搜索返回推荐；专用“情报中心”Profile 采集腕表之家 3 篇正文、生成 3 篇带来源文章并阅读。重启 Local 后数据与绑定保留，再次更新读取 3 篇、变化 0 篇、生成/更新 0 篇。需登录站点会话复用与定时跨睡眠/长周期运行仍待验收；未发布 Desktop。


### NXR-STUDIO-TASK-MODEL-ERROR-20261007：任务模型错误操作指引

- 状态：`test_build_verified`。Studio Host 将翻译缺省模型/调用失败错误转换为中英文操作提示，缺配置明确指出 模型 → 默认模型 → 标准/简单任务 → 保存默认设置；401/403 区分密钥权限与聊天正常但流程失败的系统故障，429 提示额度/限流，其余提示聊天检查、连接/本地运行状态及换用模型。兼容旧版字符串化错误字典；后端新增 purpose/upstream_status 结构字段，不暴露供应商原始诊断。9 种提示测试、21 项 Python 回归通过；固定 Test 重建、verify-release-app 和严格签名验证通过，已启动，保留配置/数据。

### NXR-STUDIO-TRANSLATION-HOST-20261007：内部翻译请求 403

- 状态：`test_build_verified`。Studio 翻译通过 ASGITransport 调用聊天接口时使用 ai2apps.internal，触发 PublicDeviceBoundary 未知公网 Host 拒绝；改为固定 loopback Host，仍在进程内执行，保留会话认证及公网边界。新增真实边界中间件回归，覆盖 BYOK 模型路由、会话传递与未知 Host 仍拒绝。21 项定向回归通过；固定 Test 已重建、verify-release-app 与 codesign --deep --strict 通过并启动，未重置数据。未自动重跑用户的视频/BYOK 付费请求，端到端翻译待用户重试。

### NXR-OFFLINE-ACCOUNT-UI-20261007：脱机帐号页布局

- 状态：`test_visual_verified`。将贴边的三行说明改为有边距的居中状态页：设备标识、脱机标题、配置模型/聊天入口、BYOK/本地模型/本机数据三张能力卡片及低强调帐号服务说明。沿用 Account 中性配色与圆角，适配窄屏，中英文文案齐全。
- 不新增帐号切换或 Cloud 操作，按钮通过 Shell 打开现有 App。JS/JSON 与 scoped diff 检查通过；固定 Test 已标准重建，verify-release-app/严格签名通过；原生截图检查布局、图标和文案通过，配置模型/聊天入口均可跳转，页面留在新版帐号页。现有数据未重置。

### NXR-BYOK-VISION-IMAGINE-20261007：BYOK 视觉与绘图目录

- 状态：`test_verified`。修复 GPT-6 BYOK 视觉能力漏识别，以及 Imagine Studio 未纳入 BYOK 图像目录。使用共同能力归一化，保留供应商直连身份，不回退到 AI2Apps Cloud；脱机不展示虚构 Cloud 默认项。67 项 Python 通过，新 Node BYOK 目录/后台路由与现有 11 个 Imagine 脚本通过；1 项既有移动端模板 is-mobile-nav 断言失败（模板未改）。固定 Test 已标准重建并通过 verify-release-app 与 codesign 严格验证；原生视觉下拉可选 GPT-6.1 Sol/GPT-6 Luna/Astra，绘图可选 Image 2.5 Sunburst/日期版/Flare。BYOK 直连说明已实机确认，未执行收费绘图。详见 ai2apps/docs/byok-vision-imagine-20261007.md。

### NXR-OFFLINE-CHECKPOINT-20261007：脱机权重 Registry 403

- 状态：`test_verified_local_inference_passed`。用户 Test Qwen3.8 安装已完成 Runtime/Package，但权重索引仍经过帐号通道而被本地脱机门禁 403。匿名读取实测仓库 key 与 checkpoint index 均 200。
- CheckpointRegistryClient 脱机只读请求改用无 Cookie/Authorization 的公共通道，保留签名、发行者、摘要、有效期和防回滚检查；帐号与写操作仍禁用。45 项脱机/Checkpoint 联合回归通过；固定 Test 已标准重建并通过 verify-release-app/严格签名校验。原生 UI 重试越过 403，进入 21.83 GB 权重验证；原生安装向导最终四步全部完成并显示安装成功，Chat 可选 Qwen3.8 本地模型，真实本地对话返回“本地模型测试成功。”（15.44s 含首次加载，20.9 token/s，23.1 GiB 峰值）。详见 ai2apps/docs/offline-test-20261007.md。

### NXR-MOBILE-BLANK-ICON-20261007：非 Chat App 白屏与图库图标

- 状态：owner_chrome_verified_phone_security_matrix_pending。Mobile Shell 将旧 Gallery 图标名映射到现有 Images，并对未知图标兜底；恢复被错误写成 JavaScript 的 mobile_library.css；iframe 被 CSP 阻止/无有效 HTML 时显示明确错误而非白屏，保留正常已加载 iframe 重开行为。
- 真实公网 Owner 验证：Home 图库图标已出现；Knowledge 的 iframe src=/mobile/knowledge 被拒绝，但同会话顶层直接打开正常显示页面并加载 4 项、无 notice 错误。公网 HEAD 对照：Chat CSP frame-ancestors self，Knowledge none。只读核对 Cloud 两份 edge nginx 模板，嵌入 location 仅包含 chat/app-content。
- Cloud 已独立部署实际 Edge 配置 mobile-iframe-20261007-r3，回执：/Users/avdpropang/sdk/ai2apps-cloud/docs/mobile-iframe-production-2026-10-07.md。本项目未修改 Cloud 代码/配置。上述拒绝嵌入证据为修复前记录。
- 2026-10-07 客户端复测：刷新既有真实公网 Owner Chrome Mobile Shell，Knowledge iframe 显示 4 项、Gallery 显示 20 项、Todo 显示页面与任务控件；三个页面各完成 Home → 重开，均正常，无白屏，最后恢复 Home。图库图标存在。未创建/修改业务数据，未重启实例。
- 待验收：iPhone Safari 三页及重开、独立非 Owner、过期/撤销租约及续租周期、跨源父页面实际阻断、有效 Owner 请求网络面 200/唯一 CSP 抓包。不得以 Chrome 页面成功替代这些项目。
- 验证：9 项 Node 检查通过（iframe 复用/加载失败提示、真实 bundled icon、图库触控回归）；真实公网客户端热更新已生效，未重建或重启实例。


### NXR-STUDIO-MOBILE-GALLERY-DRAG-20261007：Gallery 拖动切换到 Mini-App

- 状态：implemented_phone_e2e_pending。Studio 手机页接收当前 Gallery iframe 的同源、source 绑定拖动事件，开始拖动切回当前 Mini-App，保留原 Gallery iframe 以维持拖动/指针捕获；取消或无槽命中恢复原 Gallery 页面。Mini-Entry 新增触屏拖动把手，卡片长按仍是菜单、列表滑动不触发拖动。
- Touch/Pen 拖动超过 8 px 后启动，拖动提示与兼容素材槽高亮，松手后通过既有 Gallery 受权 content 接口读取并复用目标 file input change 校验/缩略图流程。无新增 API 权限；仅 DOM 可访问的同源 Package 槽可回填，不改变 sandbox。桌面路径不自动切换。
- 验证：来源伪造拒绝、导航与输入保留、取消恢复、触屏启动阈值/连续事件、原长按兼容等 10 项定向 Node 检查通过。iPhone Safari 连续指针捕获与跨 iframe 实机拖拽尚待验收。


### NXR-DEEPSEEK-BYOK-VISION-20261007：Flash 图像输入能力修正

- 状态：`implemented_and_tested`。BYOK DeepSeek 模型读取时补齐 deepseek-flash 及官方兼容别名 deepseek-v4-flash、deepseek-v4-flash-vision-exp 的 imageInput 能力；已有缓存（包括字符串模型记录）直接受益，不需重填 Key 或重新同步。保留其他能力字段，不将 Pro/Reasoner 一概标记为视觉模型。
- 依据：https://api-docs.deepseek.com/guides/vision/ 与官方首次调用文档中的 Flash 别名路由说明。现有 Admin 能力归一化、Chat/Agent 图像入口使用该声明；OpenAI 兼容代理保留 image_url 内容块。
- 验证：新增五个缓存型号能力场景及 DeepSeek Flash 图片消息代理测试，相关 Model Manager/Cloud Gateway 共 50 项通过；使用模拟上游，未作真实付费图像推理。Python 变更需 Dev/App-Dev Local 重启；本轮未重启实例，未构建/发布 Desktop。

### NXR-GALLERY-TOUCH-CONTEXT-20261007：Gallery 长按菜单

- 状态：implemented_phone_e2e_pending。Gallery 完整页和 Mini-Entry 的文件卡片支持 Touch/Pen 550 ms 长按，复用现有右键菜单；移动超过 10 px、滚动、取消或离开卡片会中止。长按后的合成点击被消耗，后续正常点击不受影响；触控时避免原生拖动抢走长按，鼠标拖动/右键保持原行为。Owner 独立 Mobile Gallery 添加同样长按手势，菜单仅提供既有预览/保存权限，不扩展 API。
- 验证：长按触发、点击抑制、短按、滑动取消、鼠标/交互控件排除等新增测试，加 Gallery picker/result viewer/Todo Gallery 回归，共 13 项 Node 检查通过；JS 语法及 diff 检查通过。真实 iPhone Safari 长按手势待验收。仅前端改动，无需重建 App。


### NXR-STUDIO-MOBILE-MEDIA-20261007：三个 Studio 手机导航与素材菜单

- 状态：implemented_preview_verified_phone_e2e_pending。Voice/Video 复用列表→工作区→共享输出导航；三个 Studio 统一输出动作菜单和素材来源菜单，复用现有文件 change/import 与 Gallery 归属校验。Voice 保持 host-owned 唯一输出历史/选择/播放。当前为响应式界面接入，Owner 公网 API 尚未开放。


- 验证：18 项 Node 检查通过（共享手机导航/桌面兼容/素材类型过滤、Imagine 回归、Voice 跨 Mini-App 输出选择）；Voice shared_output_history_across_producers_and_retention 通过。390×844 本机隔离预览验证 Voice/Video 列表与编辑/输出切换、测试音频菜单播放、Voice Gallery 导入回执、Imagine Gallery 测试素材回填与尺寸更新。Python 退出时有沙箱 Metal 无设备告警，测试 exit 0。
- 范围：内置素材槽及 DOM 可访问的同源 Package iframe 复用 file change 处理；不弱化 sandbox，opaque-origin Package 需通过既有桥另行接入。音频槽的照片选项禁用，图片输出提供查看大图。真实 iPhone 照片/系统下载、生成、Owner 公网 API、完整 Package 实机验收待完成；本轮不发布、不重建、不更改公网开关。

### NXR-IMAGINE-MOBILE-NAV-20261007：Imagine Studio 手机导航预览

- 状态：implemented（手机交互预览已验收，公网接入未完成）。按用户指定交互改造现有Imagine Studio窄屏布局：启动Mini-App列表，选择后进入工作区，右上角共享Output，返回恢复原页面。保留DOM/输入/任务/Output，移动布局忽略桌面折叠状态；当前运行Mini-App可从列表重新进入而不重置。先验收手机交互效果，尚未开放Owner公网Studio生成API。


- 验证：新增手机导航/输入与任务保留检查，加现有 Imagine Node 回归共 13 项通过；390×844 浏览器验证列表→文生图→共享输出→返回，提示词完整保留。修复基础 Studio 窄屏 `display: block !important` 覆盖 Alpine 隐藏的问题；手机左右面板采用 `x-show.important`。预览未提交生成请求，真实手机图片上传、生成、下载及 Owner 公网入口仍待验收。

### NXR-MOBILE-LIBRARIES-20261007：Owner Knowledge 与 Gallery

- 状态：implemented_dev_enabled_phone_e2e_pending。高优先级Mobile App补齐知识搜索/阅读/私有手机收藏，以及图库图片视频列表/预览/原文件保存。专用入口与窄API，复用知识可见性及图库owner校验；媒体仅固定安全图片/视频MIME，no-store、Range由FileResponse处理，仍受Owner租约控制。未开放任意文件、导入执行、管理和永久资源句柄。
- 验证：44项通过（含14项新Library API/权限/Range测试、17项Owner网关、7项图库及6项Knowledge存储）；另1项旧桌面图库模板断言gallery-context-menu-1失败，相关桌面模板未修改。中文短词兜底限定最近500条可见知识并在UI明示。390×844隔离临时页面验证搜索/阅读/收藏/筛选/图片预览，全屏弹窗也已验证；视频Range206及下载attachment由接口测试覆盖。真实iPhone视频播放与公网全链路待用户复测。
- App-Dev固定脚本重建完成，verify-release-app和codesign deep/strict通过，固定身份/Development/cloud/source-root/无更新URL核对；原生标题AI2Apps-App-Dev: App-Dev 127.0.0.1:51419。普通Dev已通过专属Helper重启；不复制实例数据、不改公网开关、未发布Desktop。


### NXR-MOBILE-TODO-20261007：Owner Mobile Todo

- 状态：implemented_dev_enabled_mobile_e2e_pending。新增手机专用Todo入口、目录/任务列表、编辑/创建/完成/文本执行结果；仅开放窄数据接口，按验证后的actor_user_id访问既有TodoStore，保留revision冲突与父子/目录归属检查。不开放运行、计划配置、Codex绑定、文件系统和桌面接口。Owner App名单加入Todo，Chat不变。90项Todo/Owner/API测试通过；390×844临时隔离页面实测创建/编辑保存/完成/返回列表成功。固定App-Dev按标准脚本重建，verify-release-app与codesign deep/strict通过，Development/cloud/source-root/禁用更新配置核对；原生标题AI2Apps-App-Dev: App-Dev 127.0.0.1:49870。普通Dev已通过专属Helper重启加载；未复制实例数据、未改变公网开关。真实手机公网扫码后的Todo闭环仍待验收，未发布Desktop。


### NXR-QWEN35-WITHDRAWAL-20261007：移除旧 Qwen3.5 安装推荐

- 状态：`client_updated_cloud_handoff_pending`。用户批准下架 `ai2apps/model-qwen35`；移除 Chat 向导的 0.8B/2B 两个旧包配置，8–15 GiB 暂无本地聊天推荐，保留 BYOK。
- 不删除既有安装/权重，不修改上游模型或其他 Qwen 包。Cloud 下架由 Cloud 项目按 `ai2apps/docs/cloud-qwen35-package-withdrawal-20261007.md` 执行，本轮未修改 Cloud。
- 客户端源码更新；Test/生产 Desktop 尚未重建发布。Provisioning 回归 52 passed，scoped diff 检查通过；沙箱退出时 MLX 报无 Metal 设备的清理警告，测试退出码为 0，本次没有运行模型推理。

### NXR-OFFLINE-MODE-20261007：未绑定设备脱机使用

- 状态：`test_built_offline_byok_verified_local_package_blocked`。用户确认首版只支持未绑定设备；登录页增加“脱机使用”，要求本机原生 Shell 证明与同源检查签发独立本机会话，不创建 Cloud 安装或成员登记；有安装绑定或旧设备登记记录时禁止启用。
- 独立 offline 主体、实例专属 HttpOnly Cookie、仅存会话摘要的原子 0600 状态文件；持久化/撤销/跨实例/损坏状态拒绝。后台任务解析使用独立 local_principal_for，原 Cloud 成员解析器不接纳 offline 主体。
- Cloud 帐号请求在发送前统一 403，直接认证传输也拒绝；关闭 Cloud defaults、设备/消息轮询与 Provider 启动。BYOK 共用 cloud/ 网关入口时不请求 Cloud 认证，继续直连供应商；本地模型工作流保持本机身份。匿名 Registry 浏览与已发布模型/Runtime 下载保留，所有匿名请求去除 Cookie/Authorization，继续校验签名/Range/SHA；需要帐号的功能不可用。脱机不再继承缓存 Cloud 默认模型。
- 回归 112 passed：14 项脱机、14 项身份、9 项桌面引导、42 项 Cloud Client、8 项 Local Auth、13 项 BYOK/Cloud Gateway、12 项 Worker Scheduler。真实 Server 认证依赖、重启、Cloud 零发送、BYOK 模拟直连均覆盖；JS/JSON/scoped diff 检查通过。沙箱 MLX 导入需在批准的非沙箱测试环境运行；不进行真实付费推理。
- 标准 build-app-dev-environment.sh 已重建固定 App 并归档旧包；verify-release-app.sh、codesign --verify --deep --strict 通过，固定 bundle ID/instance/development/cloud Runtime/source-root 合同与禁用更新配置已检查。使用标准 Helper 控制通道重启 Local，health/新 bootstrap 200；已绑定 app-dev 保持 offline_mode=false。原生窗口标题已核验包含 AI2Apps-App-Dev、设备名和 loopback 端口。
- Test 已通过标准 Helper 重置私有数据并用固定脚本重建，verify-release-app 与严格签名通过；原生脱机入口、帐号/公网禁用、模拟 BYOK SSE、重启后配置和对话保留通过。安装/成员/远程设备表为 0。新增匿名 Registry 与默认项回归后相关测试 150 passed。
- 本地包匿名下载已通过（key/metadata/envelope 200、artifact 206），真实推理仍被推荐 Qwen3.5 0.1.1 旧包缺少 uvicorn/Runtime 合同阻塞；未修改签名包或 Cloud。临时模拟 Provider 已清理，Test 保持脱机。详见 ai2apps/docs/offline-test-20261007.md。
- 当前长期 app-dev 已绑定帐号，未为本功能重置/解绑/复制其数据；新设备上点选脱机并完成真实本地/BYOK 模型推理的端到端验收仍待进行。未修改 Cloud 后端，未发布 Desktop。设计与限制见 ai2apps/docs/offline-mode.md。


### NXR-DEEPSEEK-BYOK-20261007：内置 DeepSeek Provider

- 状态：`implemented_and_tested`。ModelManagerStore 内置 DeepSeek（deepseek，https://api.deepseek.com，OpenAI 兼容协议）；复用动态 BYOK UI、现有密钥保护、/models 同步、模型启用与 Chat Completions 代理。不预置易过期的型号，不修改 Cloud 后端。
- 官方协议依据：https://api-docs.deepseek.com/guides/codex 的首次 API 调用说明；使用 Bearer 认证和 /chat/completions。模型清单继续由用户配置 Key 后同步。
- 验证：Model Manager、Cloud Gateway、Model Identity 共 51 passed，新增 DeepSeek 默认 URL 的模型同步、非流式和 SSE 流式代理场景，使用模拟传输，无真实付费请求；scoped diff check 通过。
- 生效：Python 配置变更，Dev/App-Dev 需重启 Local；本轮未重启实例或重建/发布 Test、Release。Test/Release 下次打包包含。

### NXR-OWNER-OPEN-HOME-20261007：Owner 成员授权接收与长会话 Cloud 交接

- Mobile Chat 默认模型：选择立即保存至对话session_metadata.mobile_model_id，打开时恢复；新对话继承上个活跃选择，否则使用现有Cloud API Default。Chat state只返回默认模型ID，不开放管理路由；按已筛选目录验证可用性，旧记录没有模型信息时回退默认。生成/保存期间禁止切换以避免模型记录与实际请求不一致。32项Chat/Owner gateway测试、3项模型筛选/优先级/对话恢复Node测试通过；普通Dev通过专属Helper重启，手机实机验收待用户复测，App-Dev未重建。

- Fish Audio S2 Pro 混入 Mobile Chat：实机配置为 fish_qwen3_omni，补齐模型发现器固定TTS类型以兼容缺失/旧mlx-audio；前端明确非聊天类型优先于宽泛text/conversation能力，排除隐藏/辅助模型，更新脚本版本。174项模型发现测试、Mobile模型筛选测试通过，实际Fish配置检测为audio_tts。已通过dev专属Helper重启生效；App-Dev和发布包未升级。

- 2026-10-07 手机 Home→Chat 重入修复：已加载 iframe 复用时依据 loaded 状态关闭加载遮罩，未加载帧继续等待 load。Owner 前端旧租约定时器到期改为在线确认，恢复前台主动确认，避免后台节流后依据过时期限误锁；服务端租约与请求鉴权不变。8项Node测试通过（含暖帧重入、未加载帧、旧定时器再确认、真正拒绝锁页、活动隔离），语法/diff检查通过。资源版本已更新，无需重启；手机实机复测待完成，无法断言此前会话结束完全由定时器导致。

- 手机第二次截图是接收页缺失 handoff 的恢复状态，新增已验证 Cloud 授权地址的返回按钮，修正 CSS 覆盖 hidden 导致失败后仍显示 Ready 卡片；更新资源缓存版本。12项个人空间测试通过，Dev标准Helper重启。原401原因仍待带新交接凭证的复现，未宣称修复。

- 手机失败定位续记：接收路径为 /mobile/member/complete；设备日志 05:54:12 Cloud exchange/JWKS 均200，Local 接收接口返回401。公网无效凭证探针401证实路由可达。补充无凭证的校验阶段日志与 OpenAI 格式错误解析；未放宽验证。31项Owner/个人空间测试通过，Dev按标准Helper重启加载诊断，真实失败项待用户重新授权复现。

- 手机截图故障跟进（2026-10-07）：修正交接页错误显示 Local 已连接、目录失败后点击 Chat 误报不支持 Mobile；接收页显示正在验证，丢失 handoff 时明确要求从账户入口重新授权，HTTP 错误保留状态码。Mobile 脚本增加缓存版本以避开旧脚本；不放宽任何访问权限。JS 语法检查通过，手机实际失败原因及复测仍待当前页面路径确认，不能视为授权链路已修复。

- 本轮最终状态：`implemented_dev_e2e_verified`。北京时间2026-10-07 05:15:19首次续租的同一Chrome Owner会话，05:30:46仍成功发送并得到“Long session OK.”，期间无重登；固定用户URL→Cloud授权→Mobile Home→Chat、真实DeepSeek调用、消息保存/刷新恢复通过。首个原生浏览器会话也持续续租超过20分钟。
- 流式退出实测：出现“Streaming from this Mac”后退出，05:31:44 Cloud revoke200，iframe清除并要求重新授权；刷新不能恢复旧会话。公网内部账户API仍边缘404拒绝；普通用户/跨App等隔离另有专项测试。未执行真实断网、30分钟闲置及8小时等待，边界由单测覆盖。
- 最终相关验证为114项Python及4项Node通过；修正模型能力列表/对象兼容、非聊天能力优先和显式模型选择，修正隐藏Agent/附件与手机顶部退出按钮。390×844视口核对后恢复默认。旧Local发现器仍有语音模型被标为llm，未在本轮扩大修改范围。
- 原生AI2Apps浏览器自动化控件树异常，实际对话/15分钟/流式退出在Chrome完成；无Cookie拷贝或后台Owner会话替代。仅通用dev已激活，App-Dev需后续按固定脚本重建，生产Desktop未发布。详细回执：ai2apps/docs/owner-open-home-client-integration-2026-10-07.md。下方为实施阶段历史记录。

- 2026-10-07 后续：用户明确批准实现与启用后，完成隔离 Chat 适配，不修改通用认证依赖。Owner Home 目录/实例/挂载只允许 Chat；内部 Chat API 在独立 ASGI App 中按显式方法与路径调用，模型目录/对话仅通过两个类型化回调，拒绝 API Key 回退。Cloud AI 明确带入验证后的 Owner 主体。Cookie 无通用 Local 权限，client_scope 固定 owner-home 保持会话间数据连续。
- 相关 Python 112 项、前端3项通过，包括真实 Chat 数据库创建/读取/保存、跨 App/方法/Origin 拒绝、活动与轮询区分、流式撤销。扩大测试有未改 shell.js 的桌面麦克风旧断言失败，独立记录。Python/JS 语法与 scoped diff 通过。
- 状态：`implemented_dev_activated_e2e_in_progress`。模块默认关闭，仅完整服务端配置后启用；自动审批两次阻止激活后，用户明确批准“启用并进行实机验收”，启用操作成功。仅通过标准 Helper 通道重启 dev（PID88485、53256），health200；公开Host未认证管理路径403。App-Dev boot未变，未重建/发布Desktop。
- 固定链接实际打开Cloud已出现“进入我的应用”按钮；真实授权点击及Chat/长会话验收正在进行。首批仅文本Chat，附件和Agent后台任务隐藏/拒绝。见 ai2apps/docs/owner-open-home-client-integration-2026-10-07.md；下方 blocked 与 pending 为历史阶段。

- 2026-10-07 Cloud 1.62.0 对接进行中（`in_progress_runtime_integration_blocked`）：新增独立 Owner lease 管理，不再把 Owner handoff 换成通用 Local Session。严格签名/scope/绑定检查，服务端保存 refreshToken，不透明 Cookie，60 秒租约/30 秒续租/8 小时绝对及 30 分钟闲置上限；后台刷新不制造活动，断网不延长租约，撤销与续租竞争不能复活会话。
- 新增流式响应租约护栏及关闭生产者测试，Home 独立授权链接仅在能力就绪后显示。READY 保持 false，接收端拒绝未就绪的新交换，未声明新能力。旧 personal-space-v1 的 120 秒期限不变。
- 验证：17 项新 Owner 租约/流式测试、12 项个人空间/接收/公网隔离测试、42 项 Remote 回归及 8 项 Mobile/路由回归通过，共 79 项。Python/JS 语法通过；测试退出有沙箱 Metal 不可用提示。尚未实机 App 操作或长会话验收，未重启/重建/发布客户端。
- 自动审批拒绝 sibling omlx 通用认证和内部代理批量修改（新特权身份与隔离边界风险）；被拒命令未执行。需继续完成受限 App 适配接入，不得将当前基础实现描述为上线可用。范围与后续验收见 ai2apps/docs/owner-open-home-client-integration-2026-10-07.md。Cloud 代码未修改。以下为 1.62 合同上线前的历史记录。

- 状态：local_receiver_ready_cloud_contract_pending。独立 /mobile/member/complete 与 /v1/mobile/member-session/exchange 复用 Mobile Home，但只接受 Installation member handoff；验证 Owner/device/installation/current epoch，错误成员撤销临时 Local Session，浏览器只获得既有 15 分钟 HttpOnly Mobile Cookie。个人空间 visit 断言不能转换为成员权限。
- 现有 Cloud remote_mobile handoff 回调与 Local pairing exchange 不匹配，Cloud 缺少从固定个人空间入口进入 Owner 授权的完整 UI/续期合同。未猜测 Cloud 登录 URL，未把 120 秒 JWT 放宽，也未把已有 15 分钟 Mobile 会话无限延长。
- Cloud 需求文档：ai2apps/docs/owner-open-home-cloud-requirements.md。要求独立 Owner 授权入口、版本化回调/能力协商，以及可撤销的使用会话租约与续期；待 Cloud 确认/实现/部署后再接实际按钮和完整 App 操作。
- 14 项个人空间/成员接收/公网边界测试、42 项 Remote 回归、8 项 Mobile/路由专项通过，JS 语法和 scoped diff 检查通过。本轮没有重启/重建运行实例，新增接收路由尚未实机激活；现有个人空间 120 秒会话仍然生效，不宣称 Owner 长会话或完整应用运行验收完成。


### NXR-PERSONAL-SPACE-20261007：设备个人空间接入与 Owner 入口

- 2026-10-07 后续实机纠正：账户固定 URL 的主设备实际为通用 Dev “MacIntel · AI2Apps”（cedeacbd…e2f2c3），不是 App-Dev。只正常重启已核对的 dev Local PID 50766，保留设备/主设备选择/URL/公网启用状态；新端口 56842。
- 真实 Owner 端到端通过：从账户固定 URL 经 Cloud 已登录会话跳转设备 /mobile/space/home，浏览器实际显示 Home、已验证你的 Owner 身份。真实公网无 Cookie 探针：/mobile/space/complete 200，/admin 404（边缘拒绝），/v1/mobile/space/bootstrap 401。本机同公开 Host /admin 403。
- 当前状态：activated_dev_owner_e2e_verified。访客真实账号端到端仍待验收（隔离单测通过）；Open-Entry 发布目录仍为空。此前“general Dev 未升级、Owner 公网未验收”是本次修复前历史状态。

- 状态：`implemented_activated_app_dev_public_e2e_pending`。用户确认 Home Open-Entry（非 Mini-Entry），管理操作另走 Owner/成员授权。独立 personal-space-v1 验签、120 秒会话、Host/Origin 绑定、重放与停止/epoch 拒绝；访客凭证不得成为 Local/Mobile 管理身份。
- Owner 显示 Home Open-Entry，访客显示个人空间；当前公开应用目录为空，不自动暴露已安装 App，完整 Open Publication/应用发布框架仍未实现。Cloud 固定 URL、登录、handoff/exchange 沿用既有合同，无 Cloud 代码修改。
- 生命周期已接入启动、启动开关、轮换、周期声明、停止和退出；只有安装了公网边界与个人空间路由的运行时才声明支持。公开 Host 默认拒绝内部管理、App、平台/模型/MCP/文档路径；旧 Mobile 必须验证其自身会话，个人空间 Cookie 不授予这些权限。局域网沿用原认证策略。
- 11 项个人空间/公网边界测试、42 项 Remote 回归、8 项 Mobile/路由专项通过。完整 Shell 首项旧目录断言不含已有 Todo 而失败，未改该无关断言。测试进程退出另有沙箱无 Metal 提示，不影响上述通过结果。
- 自动审批曾拒绝父目录运行时编辑，用户明确批准后完成。固定 App Dev 已通过 build-app-dev-environment.sh 重建、verify-release-app.sh 与 codesign deep/strict 校验；bundle/instance/development/cloud/source-root 合同和原生标题 AI2Apps-App-Dev: App-Dev 127.0.0.1:56068 已核对，未修改其他实例。
- 发现 Helper 采用仍存活的旧 Local（57350），经 PID/工作目录/日志路径确认后仅正常终止 app-dev 旧 Local；新 Local 56068 health 200。真实新进程以模拟公网 Host 请求 /admin、/v1/platform/cloud/auth/me、/v1/chat/completions、/mcp、/openapi.json、/mobile 均 403。初次旧进程结果不得计入通过。
- App Dev 公网开关原为关闭，保持关闭。未完成真实公网 Owner/Visitor 扫码端到端；原截图中的 general Dev 未升级，未发布 Desktop。账户固定链接二维码弹窗在 App Dev 已实机展示。

### NXR-SPARK-MEDIA-20261006：媒体模型 CUDA 对齐

- 2026-10-09：新增OpenVDN真实CUDA内核合并预检check_openvdn_torch_kernels.py：分别在原2.13/cu129和主2.10/cu130环境调用固定官方Fp8Linear及设备实际选择的flex attention，对照BF16 Linear/SDPA，使用私有新Triton缓存和Runtime编译器/头文件，记录失败而不改上游实现。任务排于Fish wrapper47746后（session75648），要求Runtime通过及GPU空闲；尚未运行/通过，不以导入结果替代内核兼容。

- 2026-10-09：OpenVDN主Torch合并只读overlay预检完成：原2.13/cu129与主2.10/cu130+Triton3.6均能导入官方assemble/render及flash_attn.cute，证据artifacts/openvdn-core-torch-compatibility-r1.json。候选出现torchao要求torch>=2.11而跳过C++扩展的提示；导入成功不证明FP8/attention内核运行兼容，不能据此删cu129。需要CUDA原生kernel与官方固定输出验收，保留原环境。

- 2026-10-09：Fish统一Transformers4.57.6固定权重验收脚本已准备：使用优化Runtime内置固定加载器，保留生成WAV，与现有官方基线逐PCM及重复生成比较，finally释放engine；要求Runtime已通过且GPU空闲。任务排在E5 wrapper44604之后（session84710），未计真实推理通过，不删除旧依赖。脚本check_fish_consolidated_engine.py。

- 2026-10-09：修正FlashHead入口后的版本收敛r2预检全部通过：E5、Fish、FlashHead三个环境各自原版与Transformers4.57.6候选，真实分词、tiny CPU BERT前向、实际引擎/官方pipeline导入共六项通过。证据artifacts/runtime-version-consolidation-r2.json；尚非固定媒体权重推理，不删除旧版本。此前PyArrow整树共享子集3profile真实原生计算/IPC/Snappy和Zstd Parquet及生产解包通过，逻辑节省142771168字节，子集压缩83929946字节，回执artifacts/runtime-pyarrow-sharing-r1.json；未计整包下载节省或启用正式builder。

- 2026-10-09：优化Runtime r2的生产解包/构建源码摘要/30profile布局/关键依赖及引擎导入全部通过，回执artifacts/media-runtime-size-acceptance-r4.json，9,157,172,927字节；不计GPU回归/签名安装/发布。FlashHead版本统一探针已修正为Runtime实际固定官方flash_head.src.pipeline.flash_head_pipeline，独立r2预检session47672运行，原r1失败保留；E5后置推理补齐Runtime验收及GPU空闲门禁。

- 2026-10-09：按用户要求启动版本收敛，独立overlay将E5/Fish/FlashHead的Transformers4.57.3候选替换为既有4.57.6，未修改安装环境。E5/Fish两组原版/候选tiny CPU BERT前向、真实tokenizer和引擎导入通过；FlashHead两组均因探针误引用Runtime不包含的adapter路径失败，不计升级失败或通过，待修正。E5固定权重CUDA对官方FP32及取消恢复验收已排在wrapper35264之后（session81387），尚未推理通过。证据artifacts/runtime-version-consolidation-r1.json。

- 2026-10-09：优化r2标准完整构建exit0，实际压缩9,157,172,927字节；相对原始11,155,039,458减少1,997,866,531字节（17.91%），较首轮再少161,642,339字节。仅删除30个有源码Packaging/PyYAML缓存共511781字节；其余主要来自Transformer共享。生产解包验收PID39259已确认live，尚不计全验收或发布通过。证据evidence/media/runtime-size-second-full-build-20261009.json。

- 2026-10-09：补齐ACE-Step CUDA Package开发源码：10–120秒音乐/可选歌词、固定官方权重与许可、Runtime依赖。补齐必需modelProfile并在内存索引真实源码后manifest校验通过，Host音乐合同通过；Spark r3物化Runtime中无GPU无权重实际入口1模型/401/正常关闭/容器删除通过。首次远端通用探针缺失已补齐。评分及内存标为估计；未发布分发或签名安装，歌词质量问题保留。

- 2026-10-09：Seed-VC v2独立CUDA权重分发完成固定HF2122cee1/MSf1c5ab39元数据逐文件复核、标准builder签名和独立验签，16文件267pieces/2,236,581,603字节；manifest 5f249311。沿用已验证CUDA固定输入，不改精度/版本；metadata_verified非双源重新全下载，未读Cookie/发布/绑定service。证据evidence/media/seed-vc-v2-cuda-distribution-signed-20261009.json；既有质量差异和签名安装门槛保留。

- 2026-10-09：Klein9B HTTP探针支持显式原生回执及经确切runtime_root绑定的优化Runtime验收，避免继续读取r1失败结果；尚未启动的r2 Runtime验收脚本补齐该字段。HTTP r2排于SoL wrapper31336之后（session28023），要求原生生成/编辑通过及GPU空闲，保留旧失败，不计新推理通过。三脚本语法检查通过。

- 2026-10-09：SoL失败已定位为旧fixture缺新Custom引擎，Host probe新增固定META/sol-sources摘要及Standard/Custom两类预检。标准和自定义两模式重试改用完整media-runtime-size-materialized-r2，必须完整Runtime验收passed、GPU空闲，排于RVC Host wrapper30203后（session1152），保留两个旧失败目录；未宣称新推理通过。证据evidence/media/sol-host-complete-runtime-retry-20261009.json。

- 2026-10-09：RVC训练声音Host端到端脚本和独立源码快照已准备，覆盖当前audio_routes、真实调度/代理、归一化输入Worker逐PCM对照、默认恢复及非法ZIP422恢复，5次前台调用。等待Klein9B重试wrapper28126后执行，不并行占GPU；证据evidence/media/rvc-trained-voice-host-preparation-20261009.json，未计通过。优化Runtime构建19996仍live，未重启。

- 2026-10-09：Dev Host attempt2升级回执upgraded_health_integrity_passed/schema87，固定wheel迁移、健康和身份Package计数通过，完整备份保留。Klein9B探针新增阶段内存与OOM失败回执，保持BF16生成/编辑配置；run_flux9b_memory_retry.py排队于Runtime验收wrapper21970之后，必须验收passed且GPU空闲，只对明确已完成Runtime树大文件及逐SHA核验checkpoint用posix_fadvise，不全局drop_caches、不改权重，不将缓存假设计为已证实。尚未开始r2推理。

- 2026-10-09：RVC训练声音真实隔离HTTP通过：413760样本48kHz输出非空且不同于默认；上传后及非法ZIP422后默认PCM均最大LSB差0，active归零、容器删除。回执artifacts/rvc-trained-voice-http-r1-receipt.json；Host voice上传与签名安装仍待验收，未启用Package能力。SAM/Stable完整Host回执已收并更新清单。SoL旧fixture缺CudaCustomRefiner；Klein9B加载和InfiniteTalk VAE初始化均CUDA OOM，保留失败与约107GB文件缓存快照，不能断言唯一根因；下一轮大模型需等构建/备份结束并加内存证据，不盲目重跑。

- 2026-10-09：SAM/Stable Host实际调度代理验收均通过，待收取完整回执。Dev Host媒体候选升级误因脚本硬编码schema81拒绝已健康schema87，自动完整回滚至81且服务active。已核对固定29c3a0c6 wheel config常量87；新增安全AST解析候选schema并严格核对health实际/目标版本、独立--attempt备份及显式Package/安装身份表计数保护，7项测试通过。修正版attempt2已排队于RVC队列7836结束后，保留旧脚本/失败环境/原路径备份；未计升级成功。证据evidence/media/host-media-coverage-upgrade-retry-20261009.json。

- 2026-10-09：OpenVDN StageB50隔离HTTP124帧通过2368.60秒，active归零、容器删除，回执artifacts/openvdn-stageb-http-r1-receipt.json；不计正式Host/安装，清单同步。优化r2构建PID19996/wrapper19995仍live，磁盘余量1.6TB；accept_runtime_size_r2.py已排队于wrapper结束后，先生产物化/构建源逐SHA、固定server/builder摘要及删除缓存检查，再30profile布局和关键依赖/引擎导入，均使用-B禁写缓存。尚无r2构建或验收通过结果。

- 2026-10-09：不可变tar比较完成，302502基线文件中除精确builder/清单预期变化外，30差异全部为Packaging/PyYAML .pyc；其他逻辑文件字节/权限一致，原结果passed=false保留于artifacts/runtime-immutable-archive-comparison-r1.json。已冻结media-runtime-size-source-r2，仅相对r1更新builder和Worker server（摘要artifacts/media-runtime-size-build-r2-source-hashes.json），标准完整重建加入Transformer共享及--remove-source-bytecode、RVC声音上传协议；build_runtime_size_r2.py记录精确命令/进程，尚无结果。RVC固定分发标准签名并独立验签通过，19文件169pieces/1,410,906,582字节，manifest d3f64420，metadata_verified；evidence/media/rvc-cuda-distribution-signed-20261009.json，未读Cookie/未发布。

- 2026-10-09：RVC固定双源元数据已匿名复核，HF738acad9/MS643998a0的19文件1,410,906,582字节与本地固定输入一致；大文件LFS SHA256，小文件HF git blob SHA1结合本地SHA256，MS全部最终文件SHA256核对。证据evidence/media/rvc-cuda-fixed-metadata-20261009.json；未读Cookie/签名/发布，不声称双源重新全下载。归档比较工具新增7项真实tar回归通过（首次重复member测试误用未压缩tar已修正）；完整比较已读完343747个基线member，PID11761继续读取候选。

- 2026-10-09：新增compare_runtime_archives.py直接读取两个固定SHA归档，检查逐文件内容/权限、原有链接不变、共享目录链接逻辑解析及越界/循环，字节码不忽略；仅允许精确builder源码及其清单摘要变化。本地逻辑共享/改动传播/逃逸与循环检查通过，Spark任务session12704已启动；输出runtime-immutable-archive-comparison-r1.json尚未产生，不宣称整包等价。

- 2026-10-09：完整对照r3终止于PyYAML constructor.pyc差异，原始构建树也可能受构建/导入缓存影响；此轮不计通过，下一步直接以不可变原始tar核验而非继续改目录基线。标准builder新增候选--remove-source-bytecode，仅清理有对应普通.py源码的CPython/legacy缓存，保留无源码模块、软链接及独立H3清单树；75项测试通过，未默认启用或改已生成tar。OpenVDN依赖审计确认主机只有CUDA13，独立cu129 NVIDIA库不能直接改成主机链接。

- 2026-10-09：RVC独立CUDA checkpoint分发spec已准备，固定HF738acad9/MS643998a0，19文件1,410,906,582字节逐SHA/大小与既有固定输入回执一致，MIT termsHash核对通过；新distributionId绑定CUDA modelId，尚未签名/发布，service不提前绑定。证据evidence/media/rvc-cuda-distribution-preparation-20261009.json。RVC独立Runtime复制完成、新server cmp一致，GPU队列7836等待既有前驱4083021；未开始推理。

- 2026-10-09：RVC训练声音真实Worker验收脚本check_rvc_trained_voice_http.py完成，固定现有fp32训练声音，覆盖默认→上传→默认逐PCM恢复、非法ZIP422→默认恢复、48kHz非空输出和容器清理。独立Runtime复制wrapper6746/copy6747仍live，完成后精确cmp新server，再等待GPU队列4083021结束执行；不修改旧fixture或正式能力声明。回执evidence/media/rvc-trained-voice-http-preparation-20261009.json，未计实机通过。

- 2026-10-09：收齐媒体队列结果：Avatar FL2VA INT8固定音频56帧HTTP通过396.80秒；OpenVDN DMD8 124帧HTTP通过1045.30秒；ExOmni Teacher74帧实际Host调度/代理通过451.51秒。三者active归零/离线只读容器删除通过；不计签名安装/UI验收，不继承至其他变体，Avatar此前7776秒清理问题保留。回执artifacts/{h3-avatar-http-r1,openvdn-http-r2,exomni-host-r2}-receipt.json，MEDIA-INVENTORY同步。StageB GPU进程4178182仍运行，未并发启动新模型。Transformer同构建器压缩对照217,862,361→68,582,032字节，子集节省149,280,329字节；非整包更新值。

- 2026-10-09：按需层发布边界核查发现Registry仅允许官方保留inference_provider身份，不能借用其他role绕过；新增docs/spark-runtime-optional-layers-cloud-requirements-20261009.md，要求Cloud工程确认官方层身份/role、权限、能力发现及依赖合同，本工程未改Cloud。Transformer未共享压缩基线独立任务session44172已启动，使用相同逻辑树与标准_archive，结果待收。

- 2026-10-09：Transformer/Tokenizers独立子集生产解包、17profile原版/重定位真实Rust分词+FastTokenizer+配置/序列化对照全部通过，候选压缩68,582,032字节，逻辑副本节省702,376,780字节；未测未共享压缩基线，不能将逻辑节省当作下载节省。回执artifacts/runtime-transformer-sharing-r2.json。完整三项优化包生产解包及266688构建源文件对照通过；旧r3逻辑路径检查因嵌入builder源码及META/h3-toolchain.json的对应摘要变化失败。已精确固定旧/新builder SHA，只允许这两处预期差异，修正版r2从已有物化树继续逐文件检查（session5755），原失败保留；尚非完整通过。

- 2026-10-09：Transformer子集已完成去重/归档，逻辑副本减少702,376,780字节；随后PYTHONPATH指向仅Worker冻结源码遮蔽已安装Host，生产安装器import失败。保留r2失败日志，新增--resume-archive从已有tar恢复，移除该覆盖，session14963运行中，未重建tar或计验收通过。新增RUNTIME-OPTIONAL-LAYERS.md，明确OpenVDN按模型必需锁依赖、签名层、只读挂载和分离进程环境的设计及门槛；未改Cloud或安装合同。

- 2026-10-09：新增check_runtime_transformer_sharing.py，复制独立子集后走标准_archive及生产_copy_tar_archive，再以原版/重定位版本对照真实Rust分词、FastTokenizer包装、序列化回读和AutoConfig；CPU离线运行，不声称模型推理。首次r1因builder放在非仓库目录缺锁文件退出，保留日志；已从冻结源码复制独立runtime-transformer-builder-source-r1并替换builder，r2任务session71888已启动。不得重启仍运行的r2；待取得receipt后判断结果。

- 2026-10-09：标准builder新增显式候选开关--share-identical-transformer-libraries，复用整包内容/结构/权限一致共享，分别处理transformers、tokenizers并保留各profile dist-info和不同版本。74项builder测试通过（exit 0，退出期沙箱Metal提示）。未默认启用，尚未Spark真实tokenizer/native加载、生产解包或新整包测量。H3确认为私有Comfy main.py服务启动，frontend_management缺前端包会sys.exit，暂不直接删除前端资源。

- 2026-10-09：新增只读audit_runtime_remaining_size.py并在Spark优化构建树实跑，常规文件19,208,689,120字节（不遍历目录软链接）。最大项OpenVDN nvidia 4,470,515,932、torch 1,227,790,388、triton 676,989,572字节；测试命名路径约436MB、静态库约123MB，仅为审查候选，不授权删除。H3含前端/示例媒体资源，但固定ComfyUI frontend_management和server实际引用这些包，须验证服务启动链路后才能裁剪。完整解包验收PID4184188/4184189仍live，未重启。回执evidence/media/runtime-remaining-size-20261009.json。

- 2026-10-09：完整优化候选标准构建正常完成（exit 0）。实际压缩体积11,155,039,458 → 9,318,815,266字节，减少1,836,224,192字节（16.46%）；这是整包实测。生产解包、全逻辑路径SHA/权限对照及30profile布局验收仍运行，不计签名安装/GPU验收通过。仍超过4GiB，下一步继续裁剪和按需依赖设计；本冻结候选不含后续RVC训练声音协议。证据evidence/media/runtime-size-full-build-20261009.json。

- 2026-10-09 RVC上传训练声音链路代码完成并同步Package adapter：35项adapter/Worker +39项Host路由通过，4慢测试未运行。修正测试默认testserver被公共边界403拦截的问题为回环Host，不改生产认证。声音ZIP只允许固定manifest/safetensors/report文件，512MiB上限，加载后请求结束清空声音状态，模拟序列验证上传→默认声音无泄漏。真实Spark训练声音GPU推理仍待验收，Package trained_voice能力未启用，冻结中的体积候选不包含新协议。证据evidence/media/rvc-trained-voice-request-implementation-20261009.json。

- 2026-10-09 RVC训练声音回灌实现中：CUDA adapter新增有界固定文件ZIP解包、调用既有load_trained_voice、请求后清除上传声音状态；Host新增能力门控voice上传，Worker保留WAV规则同时识别audio_process专用voice ZIP，最大512MiB。首轮34项adapter/Worker测试通过，Host测试因沙箱Metal导入中止，已在正常本机环境重跑Host组。尚未实机GPU验证、未启用Package trained_voice能力；当前完整体积构建仍使用修改前冻结源码，不包含本次协议改动，正式候选必须重新冻结/验收。

- 2026-10-09 RVC CUDA Package开发源码补齐：固定Serena合成测试声音转换及WAV-ZIP训练/voice-bundle导出，adapter与现有CUDA实现一致，Host/manifest合同通过。发现并明确记录缺口：引擎load_trained_voice已有原生证据，但Worker/Host尚无导出声音选择入口；新Package不虚报trained_voice推理目标，仍保留该项为对齐必做。CUDA分发绑定、签名安装/发布待完成；完整r3无GPU无权重隔离入口93796退出0，发现/401/正常关闭/容器删除通过，回执artifacts/rvc-package-entrypoint-r1/receipt.json。源码回执artifacts/rvc-cuda-package-source-20261009.json。

- 2026-10-09补齐Seed-VC v2 CUDA Package开发源码，独立adapter与既有CUDA实现逐字节相同，三模式/参考音频/WAV Host合同与manifest校验通过，GPL及各组件署名保留；Runtime>=0.6.0，CUDA model-bound分发尚待签名发布，未复用Mac model_id分发。语音质量问题继续保留，源码/入口不代表正式模型验收。Spark完整r3无GPU无权重隔离入口96698退出0，模型发现/401/正常关闭/容器删除通过，回执artifacts/seed-vc-package-entrypoint-r1/receipt.json。Stable Audio清单修正遗留Metal权限说明及固定分发大小1,704,750,192字节。回执artifacts/seed-vc-cuda-package-source-20261009.json。

- 2026-10-09 Stable Audio CUDA两项固定分发标准签名和独立验签完成：music digest3994d989、sfx digest122b4529，分别6文件/204pieces/1,704,750,192字节。使用现有Mac权重的独立副本并与官方双源固定元数据核对；metadata_verified，非双端完整下载。签名保留安装者许可确认。未读取Cookie、发布或安装。回执evidence/media/stable-cuda-distributions-signed-20261009.json。

- 2026-10-09补齐Stable Audio CUDA music/sfx两个未签名固定分发spec：官方HF da6edc54、MS c5ae91a1，分别6文件1,704,750,192字节；所有选中文件两端SHA/大小完全一致。README两端差3字节、非推理依赖，显式不纳入分发并保留差异证据；许可正文与termsHash复核，安装者downloadConsent保持required，不代用户承诺。保留官方NOTICE和Package完整署名。未签名/读取Cookie/发布，不在service.yaml填未发布distribution_id。证据evidence/media/stable-cuda-distribution-specs-20261009.json。

- 2026-10-09完整体积候选启动：独立media-runtime-size-source-r1冻结当前builder摘要，沿用r3固定输入并启用llvmlite/scientific/PyAV三项候选开关；标准构建wrapper4168869、builder4168870。构建结束后的生产解包、r3所有逻辑文件SHA/权限和30profile布局验收已排队（check_runtime_size_candidate.py），缺失/改变任一原始路径即失败；仅允许新增三项共享报告。输入artifacts/media-runtime-size-build-r1-input.json。整包结果尚未产生，未签名/安装/发布，旧r3和GPU任务保持不变。

- 2026-10-09 PyAV/FFmpeg去重候选：标准builder新增--share-identical-pyav，av与av.libs整组SHA/结构/权限相同才共享，缺私有库布局保持不变；73项构建器测试通过。Spark runtime-pyav-sharing-r1生产解包及12环境原版/候选无损编码解码、48k→16k音频重采样全部通过；逐项确认候选av实际加载，逻辑副本减少781,751,440字节、子集压缩131,988,094字节，回执artifacts/runtime-pyav-sharing-r1.json；runtime-pyav-baseline-r1同构建器压缩对照完成：398,199,797降至131,988,094字节，节省266,211,703字节，回执evidence/media/runtime-pyav-size-comparison-20261009.json。尚非完整Runtime或模型验收，未发布。

- 2026-10-09科学库去重候选：将共享逻辑扩展为显式完整目录组，新增--share-identical-scientific-libraries，对NumPy/numpy.libs和SciPy/scipy.libs整组SHA、权限及结构相同才共享；避免单独替换ELF依赖，保留不同版本和每profile元数据。72项构建器测试通过；Spark runtime-scientific-sharing-r1生产解包及23环境实际求解/逆矩阵/FFT/重采样原版对照通过（已核对实际从候选加载SciPy），逻辑副本减少2,615,225,308字节，子集压缩130,095,730字节。首次验收脚本遗漏基础框架路径导致原版/候选均缺NumPy，修正后通过并保留失败记录；同构建器压缩对照完成：852,390,227降至130,095,730字节，实际减少722,294,497字节（仅科学库子集），回执evidence/media/runtime-scientific-size-comparison-20261009.json。仍未启用发布默认行为；完整Runtime及模型回归未完成。

- 2026-10-09 Runtime首项去重实现：标准CUDA builder增加显式候选开关--share-identical-llvmlite，逐目录SHA/权限/结构核对后以内部相对目录链接共享完全相同的llvmlite，保留dist-info与原profile搜索路径；不同版本/权限保留独立副本，拒绝源目录内部链接。构建器71项测试通过（退出0，既有Metal退出警告）。Spark独立目录runtime-llvmlite-sharing-r1生产解包及15环境真实LLVM 22.1.0 MCJIT通过，减少逻辑副本2,463,152,426字节；子集压缩从872,128,875降至58,140,338字节，实际减少813,988,537字节（仅此子集），回执artifacts/runtime-llvmlite-sharing-r1.json；未启用发布默认行为，完整Runtime缩减与全部模型回归尚未完成。

- 2026-10-09 Runtime体积优化：用户要求优先缩减。r3常规文件25,264,508,336字节，SHA256/大小/权限一致的冗余副本10,068,913,487字节（180,878文件）；压缩tar仍11,155,039,458字节，尚无优化制品。跨媒体profile重复存储及独立OpenVDN cu129环境是主要来源。r3保留为回归基线，先优化再评估发布容量；方案见spark/RUNTIME-SIZE-PLAN.md，证据spark/evidence/media/runtime-size-audit-20261009.json。未修改运行中环境或读取Cookie。

- 2026-10-09：补齐Stable Audio CUDA Package开发源码，音乐/音效双模型、1–120秒/WAV/无歌词合同，固定官方optimized NPZ身份，保留Stability/Gemma条款及安装者确认要求。manifest/Host合同与r3 Runtime下无GPU无权重实际入口73600 exit0，2模型发现/401/正常关闭/容器删除通过。两项固定分发与正式安装仍待完成。Cloud容量再次匿名复核仍4294967296字节，r3为11155039458字节，16GiB Cloud需求仍未满足；未绕过限制。回执artifacts/stable-audio-cuda-package-source-20261009.json、stable-package-entrypoint-r1/receipt.json、runtime-upload-capabilities-post-r3-20261009.json。

- 2026-10-09：VibeVoice官方主权重固定HF6bce5f06/MS6b26f5a3四文件摘要及大小一致；605张量真实BF16，Mac接收Spark原始权重后标准builder签名和独立验签通过（2035345525字节、243pieces、manifest e21f1359，metadata_verified非双端全下载）。Package内六声音缓存与tokenizer在r3实际加载器CPU验收92965 exit0，CUDA未初始化；保留上游Qwen2Tokenizer/VibeVoiceTextTokenizerFast类型提示，未替换tokenizer。尚未读取Cookie/发布/签名安装。回执evidence/media/vibevoice-distribution-signed-20261009.json。

- 2026-10-09：补齐VibeVoice CUDA Package源码与实际离线资源：固定tokenizer和6个安全safetensors声音预设逐SHA核对、许可及来源保留，原始29653827字节/逐文件deflate估算18186489字节（非正式制品）。manifest/Host语音合同通过；已验收完整Runtime r3下无GPU/无主权重隔离入口26938 exit0，模型发现/401/正常关闭及容器删除通过。官方主权重独立分发、签名安装和新Package实际合成仍待完成。回执artifacts/vibevoice-cuda-package-source-20261009.json、artifacts/vibevoice-package-entrypoint-r1/receipt.json。

- 2026-10-09：用户批准Dev Cookie后，经标准脚本对E5、SAM2.1、SenseVoice ASR/同Service VAD四项分别提交、审核、发布；匿名Registry Index126/91记录签名和四个envelope精确一致。三Package源码绑定已发布distribution_id，SenseVoice Host依赖回归2项通过。Cookie仅标准脚本内存使用，本批授权已消费。权重发布不等于模型Package签名安装。回执evidence/media/e5-sam-sensevoice-distributions-published-20261009.json。

- 2026-10-09：完整媒体Runtime r3生产tar解包验收通过：302503文件逐SHA匹配、2821个H3 inventory文件通过，修复后cuda_video SHA57c6dd13核对通过，30profile/30service/2stage重定位验证通过。最终tar SHA841c4728300006b51a0477c9f3bd98577a10e5b0d026ab9ee699bbde8912bb21；未签名安装/发布。回执artifacts/media-runtime-candidate-r3-acceptance.json及media-runtime-materialized-r3-receipt.json。

- 2026-10-09：E5官方固定HF权重与MS intfloat/multilingual-e5-small不可变c86aae44共10文件元数据逐SHA/大小一致；Spark复制到Mac后标准builder签名（493292828字节、59pieces、manifest adafc57e），独立签名及metadata_verified收据复核通过。补齐固定MIT全文摘要与来源。与SAM2.1、SenseVoice ASR及新同Service VAD共4项签名候选形成精确清单，Installation会话仍拒绝；已申请本批Dev Cookie授权，未读取Cookie/未发布。证据evidence/media/e5-distribution-signed-20261009.json及e5-sam-sensevoice-publication-batch-20261009.json。

- 2026-10-09：补齐Multilingual E5 Small CUDA Package开发源码（官方FP32、384维、query/passage前缀），保留Runtime-owned固定引擎和权重哈希，不复用Mac转换权重。manifest/Host embedding合同通过；Spark完整物化Runtime下无GPU/无权重实际入口24951 exit0，模型发现/401/正常关闭及容器删除通过。独立官方checkpoint分发、完整许可发布审查、签名安装与知识库实际配置仍待完成。回执artifacts/e5-cuda-package-source-20261009.json、artifacts/e5-package-entrypoint-r1/receipt.json。

- 2026-10-09：包含H3 Host metadata修复的完整Runtime r3标准构建已正常exit0，回执unsigned_source_ready（1074源码文件）；构建PID4115077/4115078已结束，后置验收PID4115625现为live Python，正在执行生产tar物化/摘要/重定位检查。尚未计后置验收、签名安装或发布通过。回执artifacts/media-runtime-candidate-build-r3-operation.json。

- 2026-10-09：补齐标点恢复Linux CUDA Runtime Package开发源码（实际CPU/sherpa-onnx，不请求GPU），保留跨平台Service/model身份和已发布分发；匿名Registry验签摘要687dbf60。Spark完整物化Runtime下真实Package源码推理54846 exit0，中英文/数字三例、401、active归零、应用正常关闭/容器删除通过。尚非签名安装发布。另新增SenseVoice真实Host recipe→Worker内部VAD依赖边界及旧跨Service身份拒绝回归，2项通过。证据evidence/media/punctuation-package-20261009.json。

- 2026-10-09：SenseVoice补齐CUDA Package源码并修正长音频VAD正式接入：Host要求model ID属于同一Service，旧fixture跨Service ID不能直接安装。声明内部/sensevoice-small-cuda/vad依赖，适配器按固定upstream身份解析；15项回归、manifest/Host依赖解析、Spark无GPU隔离实际入口两模型/401/正常关闭通过（70735）。新VAD distribution dist_ai2apps_sensevoice_small_cuda_vad_df20e6b3_v1经标准builder双源字节签名、独立验签，manifest 4df630a5；与旧候选文件/piece完全一致，旧签名保留。未读Cookie/未发布，正式GPU长音频和签名安装仍待验收。证据artifacts/sensevoice-cuda-package-source-20261009.json及evidence/media/sensevoice-vad-service-distribution-signed-20261009.json。

- 2026-10-09：按实际回执校正H3逐变体清单：Turbo4/8隔离HTTP已通过，OpenVDN两变体为原生通过/HTTP待验；Avatar仅FL2VA INT8固定音频原生通过，适配器输出已核验但清理未完成，其他Avatar变体不能继承通过。登记九个CUDA Package开发源码及验证回执，均不计签名安装。证据evidence/media/media-inventory-reconciled-20261009.json。

- 2026-10-09：SAM2.1固定官方原始权重分发通过标准builder签名与独立验签，ID dist_ai2apps_sam21_small_cuda_ee5bba1d_v1，manifest ed1260fd，1文件184416285字节22pieces；metadata_verified模式，不声称双源全下载，未读Cookie/未发布。SAM与停止保护更新后的Demucs实际GPU禁用隔离入口88048 exit0，两模型发现/401/应用shutdown/容器删除通过；非推理或签名安装。证据evidence/media/sam21-distribution-signed-20261009.json及artifacts/media-package-updates-entrypoints-r1/receipt.json。

- 2026-10-09：SAM2.1 CUDA Package源码与固定原始.pt分发spec已准备，HF ee5bba1d与现有MS官方镜像不可变6fabd5a3两源184416285字节/SHA6d1aa6f3元数据一致，无需新镜像。安装manifest、Host分割合同通过；修正Mac复制来的NOTICE/SBOM/source-lock为Runtime-owned Meta CUDA与官方原始权重。分发尚未签名/发布故不绑定ID，正式GPU/Host/签名安装仍待完成。证据artifacts/sam21-cuda-package-source-20261009.json和sam21-modelscope-fixed-files-20261009.json。

- 2026-10-09：SAM2官方原始权重从Mac补传完成后，Spark实际嵌入Runtime CPU验收46319 exit0：519张量/46060610参数与已验证safe转换逐dtype/逐值完全一致，官方SAM2模型strict load通过，CUDA未初始化。首次66623只因缺原始文件退出，未运行反序列化；已补输入而未替换权重。回执artifacts/sam21-original-checkpoint-acceptance-r1.json。可准备直接固定官方.pt的分发，无需另行公开转换权重镜像；GPU/签名安装待验收。

- 2026-10-09：SAM2.1 Package适配器新增原始官方sam2.1_hiera_small.pt受控加载：固定SHA6d1aa6f3验证后同一文件描述符seek+torch.load(weights_only=True,map_location=cpu)，限定519纯张量并交官方模型strict load；保留旧固定safe格式，拒绝HF Transformers model.safetensors误替换。坏摘要/格式在反序列化前拒绝等9项回归通过。Spark嵌入Runtime CPU逐张量对比与严格加载66623已启动，尚不计新GPU/安装通过；Package-owned代码，不修改正在构建Runtime。

- 2026-10-09：补上Demucs停止状态与重复request ID保护，stop先拒绝新请求并取消现有队列，重复ID返回409避免覆盖cancel event。受控native回归验证stop等待、active/queued取消499、停止后503、仅一次加载、清空资源和start恢复，2项通过；已同步Package源码，不改变正在构建Runtime（适配器由Package持有）。证据evidence/media/demucs-stop-guard-20261009.json；真实GPU生命周期仍待验收。

- 2026-10-09：新增H3 CUDA Package开发源码，固定既有已签名FL2VA/Ref2VA分发身份，variant置metadata；经过实际Host模型归一化后两变体解析正确，manifest合同通过。声明当前真实4图/1视频/1音频上限，仅standard preset；Mac更高参考数量、快速/续接和其他Turbo/OpenVDN/Avatar仍是待补能力，不由基础模型推断完成。保留模型许可/NOTICE；分发未发布故不绑定ID，依赖含metadata修复的新Runtime。证据artifacts/h3-cuda-package-source-20261009.json，尚未签名安装。

- 2026-10-09：含H3 Host metadata修复的r5冻结源码1074文件/4,084,479字节已完整传输并核对修复SHA。新r3标准完整构建36885/PID4115077→4115078确认live；同一未发布0.6.0-dev.1、新目录保留r2。首次启动因scp未结束被完整性预检拦截且未创建候选，传输exit0后才重试。后置物化/302k逐文件核对/修复SHA/重定位检查54149/PID4115625已排队，未计通过。记录evidence/media/full-media-runtime-r3-started-20261009.json。

- 2026-10-09：发现并修复H3正式Host接入缺口：validate_package_models会丢弃顶层h3_variant/h3_turbo/h3_lora_model_id，Runtime此前只读顶层。Worker现从保留的metadata解析，兼容旧fixture但拒绝冲突，不修改Host输入；真实Host归一化回归及既有用例22项通过。已构建r2 Runtime不含此修复，后续必须刷新源码并重新构建，不可直接用于H3正式发布；原始tar验收证据保留。证据evidence/media/h3-host-metadata-fix-20261009.json。生产容量再次匿名确认仍4GiB；Avatar4055348仍live，未重启。

- 2026-10-09：补齐Demucs CUDA独立Package 0.1.0开发源码，带固定安全权重映射、CUDA backend和共享分离媒体代码及许可证；三profile合同与Host模型解析、manifest临时文件索引通过（20源码文件）。保留对白近似人声限制，已签名分发未发布故不绑定ID；未签名安装。源码回执artifacts/demucs-cuda-package-source-20261009.json；独立无GPU入口验收71000 exit0，模型发现/401/应用正常关闭/容器删除通过，回执artifacts/demucs-package-entrypoint-r1/receipt.json。

- 2026-10-09：六个新媒体Package源码在Spark正式物化Runtime下、GPU禁用/无权重Docker实际启动，9个模型发现、401鉴权、active归零和容器删除通过。初始脚本误把Uvicorn SIGTERM退出143判失败；已核对Runtime实际capture_signals源码和六份Application shutdown complete/Finished日志，另存corrected回执，首轮原始失败保留，不改Runtime退出行为。证据artifacts/media-package-entrypoints-r1/receipt-corrected.json；仅入口与无权重生命周期，未计实机推理/签名安装。

- 2026-10-09：补齐Qwen Image 2512/Edit2511及Z-Image Turbo两个CUDA Package源码。新增Qwen统一分派入口，严格模型/operation对应，串行请求且切换先释放上一pipeline；取消排队编辑不会加载第二模型。22项适配器回归通过（测试进程退出0，退出期有沙箱Metal不可用提示）。Z默认9steps按CUDA实现，不照抄Mac8steps。源码manifest/Host模型解析通过；独立分发候选未发布故不绑定ID，未构建正式Package，统一分派Spark实机切换待验证。证据artifacts/next-image-package-sources-20261009.json。

- 2026-10-09：完整媒体Runtime生产tar物化49808 exit0，302503文件与构建源逐SHA一致，H3 inventory2821文件通过；新路径嵌入Python、30profile/30service/2stage解析及contained symlink检查通过。四个新TTS/Klein Package经实际Host validate_package_models和适配器无权重start/stop通过（共6模型）。证据artifacts/media-runtime-materialized-r2-receipt.json、media-runtime-materialized-layout-r1.json、media-package-host-loading-20261009.json；尚非签名安装或全部模型GPU验收。

- 2026-10-09：补齐Qwen3-TTS 0.6B/1.7B两个CUDA Package开发源码，覆盖CustomVoice、Base、VoiceDesign四个固定BF16候选，复用Runtime cuda_audio。manifest与audio合同通过；按实际官方实现声明0.6B无instructions、Base需参考音频，未宣称speed/emotion已对齐。候选权重分发五项（含Klein4B）签名及verification receipt复核通过，Installation会话拒绝，精确Cookie授权待答；未发布/构建正式Package。回执artifacts/qwen3-tts-cuda-package-sources-20261009.json。

- 2026-10-09：补齐Klein4B独立CUDA Package 0.1.0源码，复用Runtime图像适配器，固定现有CUDA模型ID/revision，BF16及1–4参考图合同，移除Mac专用缓存/量化能力声明。源码manifest临时文件索引与图像合同验证通过；已签名分发未发布，weights.distribution_id刻意缺省，未构建/签名/发布Package。回执artifacts/flux4b-cuda-package-source-20261009.json；完整Runtime解包校验4099479仍live。

- 2026-10-09：完整媒体Runtime 0.6.0-dev.1标准构建81628 exit0，最终tar11,154,994,245字节/SHA053b66d6；22组实际引擎入口导入90705全部通过，Klein9B标准隔离HTTP健康93385通过（401、active归零、容器删除）。生产tar物化逐文件比较49808仍运行，未签名/安装/发布。容量Cloud需求补最终内层tar实测，保持仅官方CUDA16GiB提案；无Cloud代码改动。回执evidence/media/full-media-runtime-built-20261009.json。

- 2026-10-09：Klein9B CUDA固定权重分发已通过标准脚本审核发布（submission 52374163-b68f-4436-a2d1-81d2591289f1），匿名验证RegistryIndex122/87记录、签名和envelope精确一致；manifest 2e107b93，21文件34,722,772,164字节。按用户本项精确授权使用Dev会话，发布完成后该授权已消费。Package源码已绑定独立CUDA distribution_id；安装者仍须本人确认许可。仅权重分发完成，Runtime/模型Package发布、GPU推理和签名安装未完成。回执evidence/media/flux9b-cuda-distribution-published-20261009.json。

- 2026-10-09：完整Runtime r2实际嵌入Python逐层关键依赖导入99902完成，30/31首轮通过；GhostV2探针误要求未使用的onnxruntime，代码核对仅需onnx/onnx2torch，精确重测85352 exit0，31组所选关键模块均通过。路径限定Runtime内、CUDA禁用、无权重加载；不扩大为全部动态依赖或模型推理已通过。原始失败与修正回执分别artifacts/media-runtime-imports-r2.json、media-runtime-imports-ghostv2-r3.json。

- 2026-10-09：完整Runtime r2组装树实际嵌入Python只读检查69914 exit0：30 profile/30 service/详细转录2 stage解析正常、路径及符号链接不越界，9B scheduler固定SHA通过。-I -B禁写字节码，不改变压缩中的树。回执artifacts/media-runtime-layout-r2.json；仅结构与解释器验证，不计全部依赖import/GPU/最终tar/签名安装。压缩4080529仍live临时tar约5.99GB，权重LAN传输70408继续。

- 2026-10-09：Klein9B独立CUDA分发准备：Mac无固定快照，局域网rsync70408正在复制Spark已签名校验的34.72GB缓存到artifacts/flux9b-signing-input-r1，当前2.7G；来源明确为ModelScope经既有Mac distribution校验，不声称新HF下载。标准签名所需精确keyRef/namespace仍需从既有发布上下文恢复，未读取Keychain/Cookie或生成新key。完整Runtime r2压缩4080529仍live、临时tar约4.24GB，非最终大小。

- 2026-10-09：新增Klein9B CUDA Package开发源码（0.1.0，运行依赖>=0.6.0），BF16图像生成/编辑合同及源码manifest临时文件索引校验通过。发现Host安装器严格绑定distribution.modelId，已有Mac envelope不可直接给CUDA模型复用；准备独立CUDA distribution spec，保持固定repo/revision/许可，service.weights.distribution_id刻意留空以禁止提前构建发布。正式分发签名发布、GPU/安装仍待完成；证据artifacts/flux9b-cuda-package-source-20261009.json。

- 2026-10-09：Klein9B获取进程4041806已正常结束，最终回执signed_checkpoint_acquired，固定签名manifest 6e9cfa02、ModelScope实际34,722,772,164字节；回执artifacts/flux9b-checkpoint-acquired-20261009.json。原生队列4044450仍等待GPU前驱，未计推理通过。完整Runtime r2已进入tar压缩，构建4080529仍live。

- 2026-10-09：完整Runtime生产tar物化/逐文件SHA验收已排队49808/PID4084113等待构建4080526，并要求unsigned_source_ready回执；nice19、新目录、不改64GiB展开上限。9B清单更新为开发许可已确认、适配器已实现、下载进行中，原生/HTTP仍false；不将构建中候选计为已支持。

- 2026-10-09：新增Klein9B标准Docker HTTP基础生成/编辑探针，直接挂载缺scheduler的签名缓存以验证Runtime离线补充，不使用原生手工视图；精确SDK模型身份，401/非空图像/active归零/容器清理回执。语法通过，尚未执行；健康93385/PID4082839等待完整构建4080526与获取4041806，实际推理61886/PID4083021排GPU队尾4058044并要求原生成功。无新Case矩阵，不计Host/签名安装完成。

- 2026-10-09：LivePortrait官方环境标准导出26802 exit0（11依赖记录），修正输入清单r2；完整Runtime同一未发布开发版本0.6.0-dev.1以新r2目录重建，session81628。r4源码快照1069文件/4,059,064字节包含9B代码与许可资源，旧失败现场保留；新构建尚未完成。

- 2026-10-09：Klein9B CUDA图像适配器增加精确上游repo/HF revision校验，随Worker保留官方scheduler原始486字节/SHA067afb01、来源记录及完整许可；推理显式注入本地scheduler，不改既有权重分发、不在线补文件、不代用户许可确认。4B/9B取消排队清理及错误身份回归11项通过；Spark Host wheel已构建且三资源逐字节包含（SHA161f5a77，23,067,505字节），未安装。正在运行的完整Runtime r1快照不含此后新增9B代码，后续候选必须刷新；9B实际推理尚未通过。

- 2026-10-09：完整Runtime r1在LivePortrait导出明确失败：旧liveportrait-venv缺onnxruntime。保留22G失败目录与日志，未降低closure校验；现有liveportrait-official-venv-r1有onnxruntime1.30.0，标准独立导出26802正在验证，成功后修正构建输入并以新目录重建。

- 2026-10-09：标准完整媒体Runtime未签名开发候选0.6.0-dev.1已启动，session78264/构建PID4076748；源快照1064文件与6个视频输入摘要预检通过，三份清单版本/能力同步仅写入独立candidate-source-r1，生产0.5.0源码未替换。新增29项构建能力声明，尚不证明可用；保留100GiB磁盘门禁/nice15，已组装3.9G进入audio层。完整命令及状态见artifacts/media-runtime-candidate-build-r1-operation.json，未签名/安装/发布。

- 2026-10-09：标准源码全量导出预检发现并修复快照缺AVTR辅助模块/共享许可证/E5与Fish固定输入JSON；OpenVDN和SoL探针补实际H3源码及隔离Diffusers前置。r3快照1064文件4,032,144字节，Spark标准导出24/24通过，回执artifacts/media-runtime-sources-audit-20261009-r2.json。19份依赖锁按importlib.metadata.version实际优先级复核无差异；首轮以重复包元数据末项覆盖的假差异已纠正。仅源码组装与版本预检，未计完整Runtime、GPU推理或签名安装通过；原失败回执保留。

- 2026-10-09：汇齐下一版标准Runtime的显式构建输入，Spark只读核验53个路径全部存在，31个解释器可读取版本/包元数据；未导入GPU模型。ExOmni/MuseTalk/InfiniteTalk固定源码与Quanto原生扩展集中到全新media-runtime-video-inputs-20261009-r1，6文件逐SHA一致，不改运行中候选。输入清单artifacts/media-runtime-build-inputs-20261009-r1.json及审计回执已保存；尚需新版本/capability核对、标准完整构建及安装验收，不计Runtime发布完成。Avatar4055348仍live清理未完成，Klein9B4041806仍live、获取目录26G；未重启或重复提交。

- 2026-10-09：新增prepare_media_runtime_build_source.py冻结标准构建器/Worker SDK/共享模型源与spark源码及依赖锁，实际生成1043文件3,944,659字节，逐SHA校验与builder --help通过；排除权重、制品、二进制和缓存。仅源码快照，未赋新发布版本/扩capabilities/构建Runtime；Linux解释器与固定归档参数仍需汇齐，不能替代完整签名制品。快照artifacts/media-runtime-build-source-20261009-r1。

- 2026-10-09：Avatar清理等待的有界只读sudo栈检查被现有密码要求阻止，未附加或修改ptrace权限。引擎补四阶段INFO日志（引用释放/Comfy卸载/GC/CUDA同步），标准r3导出236文件与尚未运行独立HTTP候选逐SHA一致；当前4055348进程源码不变，原输出与现场保留。完整清理仍未通过。

- 2026-10-09：MuseTalk Host基础调用12030 exit0，自动视频+音频25帧576×768/28.63秒；实际ModelInvocationService/调度/UDS转发completed1，failed/running/queued0，容器清理通过。取回SHA与独立HTTP逐字节相同，本地解码/有限非静音音频通过。仍是源码快照+fixture发现，非已安装Dev产品API/签名安装发布；证据evidence/media/musetalk-host-acceptance-20261009.json。

- 2026-10-09：InfiniteTalk HTTP r2首次Inductor缺C编译器失败，容器已退出。工厂绑定Runtime内CC/CPATH并校验路径，标准构建器要求H3工具链；全新Triton缓存离线只读容器92233 exit0，标准r2导出48文件逐SHA一致，83回归通过。预检首轮漏核心site路径已修正。完整HTTP原设置33333/PID4058044排在现有队尾4044450，尚未计推理通过。证据evidence/media/infinitetalk-compiler-fix-20261009.json。

- 2026-10-09：ExOmni隔离HTTP重试通过，74帧720×400/439.84秒，断网只读/401/active归零/容器移除通过。取回MP4摘要一致，本地解码及有限非静音音频通过，中帧无明显损坏。仍未计Host、口型质量、签名安装发布；证据evidence/media/exomni-http-acceptance-20261009.json。

- 2026-10-09：新增model_license_confirmation.test.cjs，对两安装入口的实际确认函数执行四例DOM桩行为测试：无默认许可选择、仅勾选或仅选择均禁用、无自动提交、显式提交精确绑定distribution/manifest/terms；4/4通过。未宣称真实浏览器视觉验证或部署完成。

- 2026-10-09：OpenVDN StageB50原生6541 exit0，124帧1344×768，总2273.00秒/去噪1764.44秒。官方tunedFP8实际363Linear/208LoRA/decomposed；取回视频SHA一致、解码及有限非静音音频通过，中帧无明显损坏。原始git_commit为空的归档限制保留；仍不计任意提示词HTTP/Host/签名安装发布通过。证据evidence/media/h3-openvdn-native-stageb50-acceptance-20261009.json。

- 2026-10-09：Klein9B已获用户非商业开发测试许可，标准签名权重获取17647/PID4041806进行中。固定MS版本调度器486字节/067afb01和LICENSE18158字节/468d9f43均SHA通过；作为独立补充不改已有发布分发。既有绘图环境diffusers0.41.0/Torch2.10cu130实际导入Flux2KleinPipeline通过。基础生成/编辑52284/PID4044450等待GPU队尾4039874及权重获取，成功签名回执与逐文件SHA门禁后才运行；未计9B推理或产品支持完成。

- 2026-10-09：按用户明确产品要求，模型安装许可声明由安装者本人作出。capability_provisioning.js与dashboard.js取消默认单选，要求主动选择已同意条款/另行授权且勾选确认后才能继续；文案改为“已阅读并同意”。保留既有manifest/terms摘要绑定及下载前门禁，不将开发者Klein9B同意转授其他安装。两JS语法与63项checkpoint分发/获取测试通过；待真实UI验证与未来构建，已排队29c3a0c6 wheel不包含此后续修改。

- 2026-10-09：SoL标准/自定义提示词补入一次基础video_upscaling Host探针；共享桥增加明确操作映射。两模式初始化、隔离Worker鉴权与退出清理65331 exit0，零推理不计Host完成；各一次60帧2x输出验证61763/PID4039874等待队尾4037988，保持串行GPU。未追加场景矩阵；证据evidence/media/sol-host-preparation-20261009.json。

- 2026-10-09：已通过隔离四阶段验证的29c3a0c6 Host候选加入既有事务升级脚本的固定参数，保留GPU空闲/磁盘/摘要/完整备份/原路径恢复门禁；备份后只释放本次大普通文件缓存，保留现有systemd缓存策略。升级43254/PID4037988等待媒体验收队尾4021667，尚未停服或安装。证据evidence/media/host-media-coverage-upgrade-queue-20261009.json。

- 2026-10-09：修复后的Host候选r3实机93871 exit0，旧Host→新候选→重启→原路径备份恢复四阶段通过，合成记录保持、SQLite完整性与恢复schema摘要正常。资源打包缺漏已实证修复；未更新实际Dev或发布。证据evidence/media/host-media-wheel-r3-20261009.json。

- 2026-10-09：r2候选实际隔离启动失败（缺ai2apps/browser/dom_helpers.json）；标准Spark wheel构建器补入该资源。r3产物23,049,625字节/SHA29c3a0c6e499695ca939e39f0623b61d9b0917758d10d08d86d4fff875a4f40a，归档内资源与源码逐字节一致；Spark四阶段合成升级/恢复93871运行中。保留失败回执，实际Dev未替换。

- 2026-10-09：标准Spark wheel构建候选r2完成（23,038,051字节，SHA a672ac057483a79717a5a8c5a0259135499f54aa7c20eebac6ab60984d498fad）；89项Host/调度/Provider相关测试通过，wheel内三核心模块与当前源码摘要一致，无缓存/本机动态库。共享脏工作区开发候选，尚未安装到实际Dev，非签名Runtime或发布。证据spark/evidence/media/host-media-wheel-candidate-20261009.json。

- 2026-10-09：视频新增层容量统计27541 exit0，共4892604066压缩字节；与既有估算相加10150248857字节约9.45GiB，非完整最终Package。Cloud需求文档从8GiB调整为仅官方CUDA16GiB提案；公开合同复核仍4GiB，未改本地或Cloud门禁、未发布。

- 2026-10-09：当前Mac manifest复核未见已列模型ID变更，发现标点恢复因旧model_type=llm未单列，实为非对话ONNX服务，已补入清单共36组。真实CPU Host4923 exit0：中英文与数字三例词汇保持、3次完成/0失败、queued/running0、断网只读/非root和容器清理通过；仍fixture discovery，未签名安装/发布，不将其当对话扩容。

- 2026-10-09：新增视频Runtime容量审计首轮发现OpenVDN开发候选缺sources/openvdn，而标准构建器已有完整保留源码。已从标准r4导出补齐128MiB源码归档/许可证/依赖锁，5文件逐SHA一致。新增audit_video_runtime_size.py以nice19只读流式压缩统计OpenVDN/InfiniteTalk/ExOmni/MuseTalk增量，27541运行中；未出最终容量，不能将未压缩13.11GB当外层Package大小。既有4GiB合同与Cloud需求保持不变。

- 2026-10-09：Stable Audio补基础Host music/sfx双模式调用入口，共享桥显式支持audio_generation。48987 exit0验证初始化/Worker鉴权/清理，零推理不计完成；两次10秒8步合成3376/PID4021667等待4020002，要求44.1k立体声/非静音、completed2及归零。保留fixture discovery和未签名安装限制，不扩展场景矩阵。

- 2026-10-09：共享Host探针显式支持video_segmentation，保留video_generation默认合同。新增SAM2.1一次基础Host分割探针；51142 exit0验证Host/调度初始化、Worker鉴权与清理，零推理不计Host调用通过。真实分割12987/PID4020002等待既有队尾4011741，将检查完整帧数、非空mask、调度completed1与空闲；无新增复杂Case或并发GPU。

- 2026-10-09：OpenVDN DMD8官方原生基础生成通过，124帧1344×768，总856.26秒、去噪302.32秒；取回MP4 SHA一致、解码/有限非静音音频通过。实际363 FP8 Linear、571LoRA、decomposed softmax，官方cached prompt；native归档无git导致记录git_commit空，固定源码来源依旧见准备证据，保留限制不改写原回执。仍未计任意提示词HTTP/Host/签名发布。Stage B原生4017437已按门禁启动。

- 2026-10-09：OpenVDN适配器将官方output.mp4.inference.json逐字节保留到diagnostics/inference.json，并返回其SHA；保留实际kernel/FP8/LoRA/timings字段，缺记录或关键字段拒绝成功。实际导出render_record fixture补timings检查证明清理源sidecar后诊断副本仍一致，空对象拒绝；不是模型实测。标准源码r4导出94文件与Spark未运行HTTP候选逐摘要一致，当前原生任务不受影响。

- 2026-10-09：InfiniteTalk探针加入显式Host源码快照模式，复用真实ModelInvocationService/调度器/Supervisor代理，multipart遵循bytes合同，等待上限14400秒。Host健康73167 exit0：初始化、标准断网只读Worker、401与清理通过；completed0/calls0，不能计真实Host推理。现有HTTP重试仍排队，暂不重复提交另一轮耗时GPU请求。OpenVDN4003815确认live，已组装800分支/571LoRA/363FP8 Linear。

- 2026-10-09：OpenVDN HTTP探针加入显式dmd8/stageb50选择，分别挂载固定阶段权重并记录variant；read等待上限14400秒。Stage B健康53484 exit0，禁网只读/401/active归零/退出清理通过。完整124帧50步HTTP31590/PID4011741串行等待4004864，必须先读取同变体原生成功回执，否则明确defer。未计Stage B实际生成通过；DMD原生4003815本轮确认仍live加载/组装中。

- 2026-10-09：基础Host调用发现固定300秒read超时不足覆盖ExOmni约440秒和InfiniteTalk约7638秒已验证生成。JSON/multipart视频生成改固定14400秒read，connect15/write300/pool300保留，其他操作仍300；25项请求ID/鉴权/调度结果/取消相关测试通过，包含两种编码下实际httpx request timeout验证。相同改动同步到排队Host源码快照，无运行中服务替换。未完成长请求实机Host验收；此改动属于后续Desktop发布评估内容。

- 2026-10-09：Avatar真实推理依赖预检揭示缺soundfile，健康检查不覆盖延迟加载。工厂补入可信Runtime内audio层，保持H3/core优先级并校验路径不越界。实际工厂加11模块CPU模式导入52909 exit0，全部路径属于独立Runtime，未占GPU推理；标准导出r2共236文件与候选一致。最初探针误用候选没有的framework_profile_for_service已改回其已有framework_profile接口。真实HTTP仍排队，不提升验收状态。

- 2026-10-09：标准CUDA构建器新增--h3-avatar-dependencies与h3-avatar显式capability，要求完整H3输入。固定依赖receipt SHA/逐文件SHA/路径与冲突检查，保留共享许可和依赖来源，输出源码清单及SBOM依赖条目。实际标准导出236文件与Spark候选逐摘要一致；69项既有构建器测试通过，退出有既有Metal提示、exit0。完整签名Runtime/HTTP生成仍未完成，不提升可用状态。

- 2026-10-09：Avatar独立Runtime标准Docker HTTP健康49928 exit0，断网/只读/鉴权401/active归零/容器清理通过，回执已归档artifacts/h3-avatar-runtime-preparation-r1。新增完整HTTP探针固定图片+2秒语音、56帧512²，实际推理61187/PID4004864等待既有队尾4000712，不计生成通过。Avatar原生进程3996778确认已自行退出；先前gdb只读attach被系统ptrace限制拒绝，未修改系统权限或强杀进程。

- 2026-10-09：Avatar独立Runtime组装65595已exit0，236个依赖/实现文件写入并记录摘要。隔离导入及真实HTTP仍待验收，未签名发布。

- 2026-10-09：新增prepare_h3_avatar_runtime.py独立候选组装，复制既有H3 Runtime且不使用硬链接；固定pyloudnorm0.1.1/future1.0.0逐摘要、冲突与路径检查，内置Avatar引擎/适配器/latent/共享媒体及许可，服务映射到h3 profile。Spark组装session65595仍运行，无GPU加载；语法检查通过。尚未隔离导入/HTTP推理/签名，不能计Runtime完成。Avatar原生PID3996778输出回执后仍live，futex等待，尚未判退出清理通过，后继OpenVDN继续等原进程。

- 2026-10-09：H3 Avatar原生固定音频画像基础生成通过：56帧512²/20步，208.56秒，audio latent最大误差1.19e-7；视频取回SHA一致，本地解码与有限非静音音频通过。尚非可复用适配器/独立HTTP/Host通过，后续仍优先补基础覆盖。ExOmni Host首轮失败确认是探针将BufferedReader传给声明bytes的接口；桥接层按Host合同转换并限制总fixture 64MiB，混合bytes/流及超限检查通过，已同步到尚未执行的MuseTalk Host探针；ExOmni修复重试PID4000712串行排在OpenVDN HTTP之后。

- 2026-10-09：按用户要求继续优先补缺失模型基础能力，复杂应用Case后置。H3 Turbo4/8隔离HTTP均通过：56帧768×512，分别63.44/75.70秒，断网只读非root；回执artifacts/h3-turbo-http-acceptance-r1。OpenVDN已生成视频但记录阶段缺git导致HTTP失败；标准源码构建器改为记录固定归档revision，保留实际kernel/FP8/LoRA字段。导出render_record无git fixture检查通过，94文件与Spark候选逐摘要一致；修复HTTP排队PID3998877，未计生成接口通过。H3 Avatar与OpenVDN各模式基础推理仍待完成；未签名安装或发布。

- 2026-10-09：H3 Avatar真实SDK适配器探针已准备，固定图片/2秒音频/56帧/512²/20步，验收输出解码、非静音音频、音频latent保持及引擎释放。首次完整导入39922因Comfy初始化CUDA在OpenVDN占用时OOM退出；--check改官方CPU模式后38344 exit0，实际生成仍CUDA且严格排队。不计真实适配器通过。证据h3-avatar-engine-preparation-20261009.json。

- 2026-10-09：H3 Avatar加入标准Worker工厂/请求适配器，固定Host checkpoint repo/revision、受控上传部件/输出目录、参数网格、SoL请求所有权、OOM释放和可信Comfy/工具链路径。Spark真实SDK合同检查exit0（渲染器为明确fixture，未加载模型）；尚待真实渲染、独立Runtime/HTTP及Host验收，不宣称模型可用。证据h3-avatar-engine-preparation-20261009.json。

- 2026-10-09：H3 Avatar原生流程整理为可复用cuda_h3_avatar_engine.py：完整音频窗口校验后再加载权重、固定20步Comfy配方、音频latent保持检查、共享MP4封装、明确close释放。输入frame/canvas/seed边界与checkpoint符号链接越界检查通过，尚无该引擎真实生成或Worker工厂，不提升模型可用状态。证据h3-avatar-engine-preparation-20261009.json。

- 2026-10-09：MuseTalk复用当前Host源码快照调用/调度/转发桥，92037 exit0验证声明/初始化/标准离线Worker/清理；完整一次视频音频请求12030/PID3981278串行等待3979781，要求调度completed1且归零。健康检查零生成，不判Host完成；正式安装/UI仍未验收。证据musetalk-host-preparation-20261009.json。

- 2026-10-09：MuseTalk预计算自动区域17.87秒、仅视频音频输入自动处理13.55秒、独立断网只读HTTP26.68秒均通过，25帧576×768。回执/视频取回，SHA/解码/有限非静音音频通过，中帧无明显损坏；引擎释放/active归零/容器移除通过。Host、口型质量与发布未通过，覆盖清单更新。证据musetalk-automatic-acceptance-20261009.json。

- 2026-10-09：Ex-Omni/InfiniteTalk首次HTTP探针在客户端裁剪阶段缺soundfile，未进入模型请求。协调venv补固定soundfile0.13.1（17997 exit0），两原音频3秒裁剪/重解码通过；Runtime未改，80719/PID3979781串行等待3977398重试。证据media-http-audio-preflight-20261009.json。

- 2026-10-09：OpenVDN适配器7922也在首次Triton编译退出1。开发解释器全新缓存重现Python.h缺失，确认先前CudaUtils成功只是缓存命中；新增openvdn_development_toolchain显式使用已有Runtime的CC/CPATH，原生与适配器探针接入，全新缓存复验exit0。两失败完整日志已取回；修复后DMD8及其通过后的Stage B原设置重试排到Avatar重试之后。未计视频生成通过。

- 2026-10-09：OpenVDN工具链入口修复已重新通过标准_copy_openvdn_sources导出r2；94源码/启动器/协调器文件逐摘要与Spark候选一致，META/openvdn-sources.json在核验后更新。源代码导出已收口；仍非完整签名Runtime构建或模型推理通过。证据h3-openvdn-standard-source-export-20261009.json toolchain_entry_refresh。

- 2026-10-09：OpenVDN双进程入口补上Runtime内可信CC/CPATH，复用H3已打包工具链/头文件并校验路径；新增全新临时Triton缓存编译预检。宿主检查通过，标准断网只读Docker20381 exit0；前两探针启动合同错误已修正。未运行候选入口已同步并保留旧版，标准源码导出需刷新，完整生成仍待验收；不将此推断为原生gcc失败确定根因。证据h3-openvdn-compiler-20261009.json。

- 2026-10-09：OpenVDN自定义文本经现有Comfy NVFP4编码器实际生成26×5120 BF16条件，编码子进程退出；临时缓存及原提示词已保留至prompt-encoder-acceptance-r1。官方weights_only读取器CPU验证57297 exit0：摘要一致、shape/有限数值/纯文本tag正确。保留非官方BF16精度参考声明，完整适配器视频仍在加载中，未计生成通过。回执artifacts/h3-openvdn-prompt-encoder-r1/verification.json。

- 2026-10-09：H3 Avatar缺失依赖修复：从已验证MuseTalk Runtime导出pyloudnorm0.1.1/future1.0.0，共231文件核对RECORD摘要，排除两开发CLI和无摘要pyc。首次导出因RECORD外部CLI/已去除pyc失败，规则显式修正后完成。97798 exit0，10项真实导入含共享封装器通过；新原生重试排在Ex-Omni Host之后，未宣称模型推理或正式Runtime发布完成。证据h3-avatar-dependencies-20261009.json。

- 2026-10-09：OpenVDN首轮原生失败：已完成800分支张量/571 LoRA合并/363 FP8 Linear组装，首次forward的Triton cuda_utils编译gcc退出1，日志无编译器原始原因。单独同venv CudaUtils复测exit0，根因未确认，不误报缺头文件。H3 Avatar随后在模型加载前缺pyloudnorm退出；两失败均不计能力完成，需后续修复/重试。证据h3-openvdn-native-failure-20261009.json。

- 2026-10-09：Ex-Omni加入当前Host调用/调度/UDS转发探针，显式源码快照与三模块摘要。74971 exit0验证初始化/离线Worker健康，零生成，不判Host推理通过；正式基础调用38972/PID3958708等待队尾3956474，要求完成一次调度且running/queued归零，退出错误使验收失败。保留fixture discovery/未签名安装与UI限制。证据exomni-host-preparation-20261009.json。

- 2026-10-09：补入OpenVDN Stage B 50步基础模式验收队列68172/PID3956474，等待既有队尾3948307；仅在共享DMD8原生回执通过后运行，避免共同路径失败时重复加载。继续固定官方tuned_fp8/124帧配方，不缩减为DMD8覆盖。当前DMD8 PID3952634仍在首次加载，无Stage B成功结论。

- 2026-10-09：Ex-Omni Teacher真实适配器调用35426 exit0，74帧720×400，440.07秒；视频/非静音有限音频/引擎释放通过。取回文件SHA一致、本地再解码通过，中帧无明显空白损坏；不宣称口型质量、HTTP/Host或签名发布通过。覆盖清单更新，证据exomni-adapter-acceptance-20261009.json。OpenVDN下一队列已加载权重，仍运行。

- 2026-10-09：H3四步独立候选标准Docker HTTP健康72353 exit0，非root/断网/只读/cap-drop/no-new-privileges、401鉴权、空闲及退出清理通过，回执已取回。探针新增--health-only，明确零推理cases，不将健康检查当成生成。实际四步/八步生成仍在既有串行队列，Ex-Omni适配器采样进程确认live。

- 2026-10-09：InfiniteTalk首次原生FP8单人视频完成，25帧896×448、7637.56秒。取回MP4摘要一致，本地视频解码/非静音有限音频/帧变化通过；中帧人工查看无明显空白或损坏。只证明一次基础原生生成，未证明口型质量、Worker/Host或发布完成。覆盖清单更新，证据infinitetalk-native-acceptance-20261009.json。

- 2026-10-09：H3 Turbo4独立未签名Runtime组装65447 exit0，未修改现有排队Runtime；HTTP探针增加解码与中帧证据。八步首轮HTTP在加载模型前失败：h3-venv缺ai2apps；media-image-venv探针导入预检通过。四步HTTP及八步修复重试12504/PID3948307串行等待3943014，无新增并发GPU；尚无Turbo HTTP通过结论。

- 2026-10-09：H3 Turbo4 v1.2接入标准CudaH3Adapter，固定独立LoRA文件/版本和FL2VA限制；缺省步数随配方选择4或8，显式错配拒绝。现有HTTP探针新增互斥--turbo4/--turbo8。23项适配器/子进程测试通过，语法/diff检查通过；测试退出有既有Metal不可用提示、退出码0。尚未修改排队Runtime或宣称Turbo4实机/发布完成。

- 2026-10-09：找到lightx2v Owner的v1.2发布公告（https://huggingface.co/lightx2v/Minimax-h3-Turbo/discussions/52），明确4步/Euler/视频shift6/音频3/最高768p，解除精确配方缺口。新增apply_lightx2v_4step，复用同一受限构图器且8步合同不变，Spark实际H3构图15168 exit0。现有v1.2权重无需重下，基础生成48302/PID3943014排队等待3936033。尚未计生成/Worker/发布通过；证据h3-turbo4-recipe-audit-20261009.json。

- 2026-10-09：OpenVDN标准构建专用解释器已就绪，使用明确普通wheel输入而非editable；在标准_profile_build_env下依赖锁/两wheel来源摘要/Torch2.13cu129均预检通过。构建专用.pth不进入交付Runtime。完整签名构建及实际生成仍待完成，证据h3-openvdn-standard-source-export-20261009.json。

- 2026-10-09：标准Runtime构建器加入OpenVDN双环境完整入口：固定源码/补丁Diffusers归档、指定普通wheel摘要、独立cu129依赖、协调profile/双启动器/工厂META；要求显式h3-openvdn及H3编码器capability。实际源码导出94文件逐摘要通过，H3仅为导出fixture，未重建完整Runtime或发布。源码入口与既有HTTP候选还需一致性收口。证据h3-openvdn-standard-source-export-20261009.json。

- 2026-10-09：OpenVDN协调profile/工厂与双进程META接入独立Runtime，标准离线HTTP健康76254 exit0，401/只读禁网/空闲状态/清理通过。自定义prompt→编码→DMD8/124帧完整请求17207/PID3936033排队等待3924023；未计实际HTTP生成或Host安装完成。证据h3-openvdn-dual-runtime-20261009.json。

- 2026-10-09：OpenVDN组装19969已exit0；双入口检查70166 exit0，inference实际Torch2.13cu129/FA4/官方assembler、encoder实际Torch2.10cu130/Comfy，路径全部属于独立Runtime。仍未加载权重或运行完整生成。

- 2026-10-09：OpenVDN固定双进程启动器openvdn_process_entry.py与独立Runtime组装脚本已实现，推理/编码使用不同明确模块路径并限定目标脚本；匹配工厂META清单。组装session19969仍运行，未重启；两端隔离导入/实际调用未验证，不计Runtime完成。证据h3-openvdn-dual-runtime-20261009.json。

- 2026-10-09：标准构建器新增独立OpenVDN cu129全环境导出，精确锁定全部已安装依赖与CUDA库，不与cu130核心去重。12266 exit0：77分发/24451文件/7,031,938,713字节。首轮隔离导入77044缺CUTLASS路径；显式添加Runtime内nvidia_cutlass_dsl/python_packages后37386 exit0，Torch2.13/FA4/官方assembler等9模块均来自导出目录，未借用开发site。固定启动器/双环境组装/模型推理仍待完成；torchao提示保留。证据h3-openvdn-process-export-20261009.json。

- 2026-10-09：OpenVDN与补丁Diffusers原为editable安装，不能依靠RECORD直接交付源码。离线普通wheel构建29763 exit0，独立目标安装1407 exit0，真实config/assembler/render与Diffusers导入41520 exit0且全部来自wheel目录；无.pth。保留torchao可选Tensor导入提示；全依赖/双Runtime导出及真实推理未完成。证据h3-openvdn-runtime-wheels-20261009.json。

- 2026-10-09：OpenVDN新增create_adapter工厂，从可信Runtime META/openvdn-processes.json解析五个相对路径，拒绝越界/外部符号链接。子进程移除父Worker PYTHONHOME/PYTHONPATH等，避免Torch2.13推理与2.10编码环境串用。Spark真实SDK工厂与子解释器探针79626 exit0；双Runtime实际导出/模型调用未完成，不计新模型通过。证据h3-openvdn-runtime-contract-20261009.json。

- 2026-10-09：InfiniteTalk正式标准构建器补齐源码/预编译Quanto/依赖三输入与显式capability门禁，固定补丁归档、CUDA库摘要和Torch/CUDA/Python/架构ABI。实际标准导出48文件逐摘要通过，保留官方/共享代码/Quanto许可；源码与原生库不再仅靠临时组装入口。语法与diff检查通过；尚无独立HTTP推理/签名安装/发布结论。证据infinitetalk-standard-source-export-20261009.json。

- 2026-10-09：InfiniteTalk补齐实际渲染路径所需musetalk_shared_media与许可，隔离导入/HTTP健康7135 exit0：12模块内部路径、46源码摘要，断网只读Docker、鉴权401/空闲/清理均通过。一次25帧40步HTTP生成77789/PID3924023排队等待3913077，未计完整推理通过。原生PID3835826观察30/40仍live。证据infinitetalk-runtime-preparation-20261009.json。

- 2026-10-09：InfiniteTalk独立开发Runtime组装后两次导入分别发现scikit-image/cv2缺失，已补精确锁与标准导出r3。29270 exit0：73依赖/8744文件逐摘要一致，11项关键模块均为Runtime内部，45个运行源码摘要通过，预编译Quanto在禁编译回调下重复加载通过。引擎按显式打包目录采用预编译库；源码/二进制仍是未签名开发组装，完整标准源码构建入口及HTTP/真实推理待完成。证据infinitetalk-runtime-preparation-20261009.json。

- 2026-10-09：InfiniteTalk标准依赖profile导出54493 exit0，70个分发/8153文件逐摘要一致，零缺失/额外，未导出开发.pth。源码准备器新增最终文件摘要（含追加attention覆盖和兼容helper），重新生成68文件并复验通过；活跃推理目录未修改。预编译Quanto、源码与依赖仍待合并独立Runtime，未签名发布。证据infinitetalk-runtime-preparation-20261009.json。

- 2026-10-09：Quanto默认在包内写build/并调用编译器，与只读Runtime不兼容。新增cuda_quanto_extensions.py显式ABI/摘要校验加载器；将本次开发已编译CUDA库复制到独立目录，8098 exit0，禁止编译回调时仍可直接加载并绑定Quanto扩展。未执行CUDA算子/模型，CPU扩展未打包，尚未接入引擎或正式构建器；不能计独立推理通过。证据infinitetalk-runtime-preparation-20261009.json。

- 2026-10-09：InfiniteTalk实际依赖导入审计96605 exit0，固定23项直接依赖版本及来源；确认Quanto另需Ninja、Python头文件、CUDA/C++工具链，正式封装不能借用开发机路径。保留Torch对SM12.1兼容性提示。首轮生成PID3835826确认28/40活跃，尚未计推理完成；独立Runtime导出未开始。证据infinitetalk-runtime-preparation-20261009.json。

- 2026-10-09：Ex-Omni独立未签名Runtime组装/隔离导入17018 exit0，15项关键模块均来自Runtime内部、103源码摘要一致。标准断网只读Docker HTTP健康43896 exit0，401鉴权/空闲状态/容器清理通过；完整短视频HTTP83151/PID3913077排队等待MuseTalk3906928，未计真实HTTP生成完成。证据exomni-runtime-preparation-20261009.json；正式安装/发布仍待完成。

- 2026-10-09：Ex-Omni独立构建输入准备19913 exit0，标准依赖导出47081 exit0：110个分发、17,108个文件逐摘要一致，零缺失/额外文件，未导出开发.pth。源码导出与依赖层现已各自完成，仍待合并独立Runtime及基础离线Worker推理；未签名/发布。回执exomni-runtime-preparation-20261009.json。

- 2026-10-09：标准CUDA Runtime构建器新增Ex-Omni Teacher profile、直接依赖锁检查与源码入口，显式capability/两项输入必须同时满足。固定57581cf源码归档SHA21e224ee…，实际导出103文件并逐摘要复验通过，官方Teacher配置路径齐全。源码导出及语法/diff检查通过；依赖profile导出、独立推理、签名安装/发布尚未完成，未启用生产manifest。证据exomni-runtime-source-export-20261009.json。

- 2026-10-09：Ex-Omni Teacher实际依赖与原生后端导入审计53903 exit0，记录25项直接依赖的版本和真实模块来源，新增exomni-cuda-requirements.lock。保留SoX可执行文件缺失/flash-attn缺失提示；已通过原生路径使用SDPA。当前仍借用多个开发目录，非独立Runtime、非完整传递依赖锁；下一步标准profile/源码导出。证据exomni-runtime-preparation-20261009.json。

- 2026-10-09：MuseTalk独立Runtime基础HTTP健康/鉴权/断网只读沙箱通过（79727 exit0）；首轮89834因遗留socket清理失败，已修复并保留记录。一次视频+音频自动生成HTTP验收29334/PID3906928排队等待3893750，无并发GPU。尚无完整HTTP推理或签名安装结论。InfiniteTalk确认25/40仍活跃；继续覆盖优先，不新增复杂场景矩阵。证据musetalk-http-preparation-20261009.json。

- 2026-10-09：MuseTalk独立未签名Runtime组装66709 exit0；首次隔离导入因base旧runtime_profiles缺当前接口失败，候选更新标准模块后32404 exit0。19项关键模块均来自Runtime内部，71源码摘要复验通过，未加载GPU模型。回执imports.json已取回；HTTP隔离推理/安装发布仍待完成。

- 2026-10-09：MuseTalk独立构建解释器准备38135 exit0，标准_copy_isolated_profile导出69446 exit0，75个依赖分发闭包验证通过，service→musetalk映射正确且未导出开发.pth。回执已取回。源码与profile尚待合并到独立Runtime及隔离实机验收，无签名/发布。

- 2026-10-09：标准build_cuda_torch_runtime_package.py新增MuseTalk profile与三项输入门禁，导出固定MuseTalk源码、固定GhostV2 BiSeNet、共享YuNet/媒体与适配器。首轮开发Package无通用LICENSE失败，按仓库许可政策修复并保留三方LICENSE后r2导出71文件且摘要复验通过；补pyloudnorm0.1.1。仅源码导出通过，依赖profile/完整Runtime/隔离推理/签名发布均待完成。

- 2026-10-09：完整读取Package发布手册后核对标准CUDA构建器，新增MuseTalk实际开发overlay直接依赖版本锁musetalk-cuda-requirements.lock。明确非完整传递依赖/轮子锁，Runtime尚未导出或签名；固定源码需同时收录MuseTalk、BiSeNet、共享YuNet与媒体writer。版本回执已取回，未访问Cookie或发布。

- 2026-10-09：MuseTalk仅视频/音频验收补齐run_musetalk_auto_adapter.py开发依赖入口，实际检测/分割/音频模块路径检查通过，沿用CPU预处理MKLDNN禁用配置；完整自动请求排队等待3889311结束，未启动并发GPU。正式Runtime profile仍待合并与签名，未计模型/Host完成。

- 2026-10-09：MuseTalk Worker新增省略regions时的自动预处理路径，Host必须提供detector/parser权重，原显式regions合同保留；NativeFaceParser提取为共享原生CPU组件并在session41523实际25帧验证通过（5.02秒）。新增--auto-preprocess验收入口，仅上传视频和音频；完整GPU调用尚未执行，Runtime依赖合并/Host待完成。

- 2026-10-09：MuseTalk adapter验收新增--auto-regions，将已通过的25帧自动人脸框/嘴部遮罩逐帧传入实际Worker合同；不使用人工框或椭圆mask。语法/实际环境CLI导入通过，视频生成session45208等待OpenVDN服务shell3883811退出后串行运行；尚未计自动视频通过。

- 2026-10-09：MuseTalk CPU自动区域重试43472 exit0，25帧真实YuNet检测和BiSeNet嘴部遮罩生成通过，5.08秒。回执已取回；自动遮罩接回CUDA视频、官方完整预处理比较与Host仍待完成。

- 2026-10-09：MuseTalk新增自动模板区域准备 cuda_musetalk_prepare.py，Mac产品裁框/嘴部遮罩合同通过注入原生detector/parser复用，不声称官方DWPose/SFD流程一致。真实CPU YuNet/BiSeNet探针session26418缺共享导入路径退出1，已修复并启动43472；未并发占用GPU，未计自动预处理或视频通过。

- 2026-10-09：FLUX.2 Klein9B新增离线基础探针check_flux2_klein_9b.py，固定官方ModelScope revision逐文件大小/SHA验证，包含scheduler与LICENSE共23文件34,722,790,808字节；准备BF16生成/单参考编辑两例及释放。CLI和metadata选择通过，未下载权重、未接受许可、未执行模型、未开放产品adapter。仍需已有Host许可确认与权重取得；其他模型继续推进。

- 2026-10-09：OpenVDN自定义提示词服务验收 check_openvdn_adapter.py已准备并同步，真实Runtime/三组Host权重路径检查通过。完整编码→DMD8生成→音视频解码→stop验收session7922排队等待H3数字人shell3878559结束。编码与推理诊断日志改存Worker私有data_root，临时prompt/cache仍自动清理；未计实际推理通过。

- 2026-10-09：OpenVDN新增 cuda_openvdn_adapter.py，将用户prompt经可信独立编码进程生成内部cache，再运行固定官方DMD8/StageB50程序；Host分别提供variant/base/text-encoder，Runtime路径显式注入，取消等待进程退出。Spark实际SDK导入与3项非法请求前置拒绝通过，无GPU加载。Runtime工厂/manifest、实际自定义prompt生成和Host验收未完成；不计新支持。证据h3-openvdn-worker-preparation-20261009.json。

- 2026-10-09：新增 cuda_openvdn_engine.py 官方推理子进程边界，Host解析后的权重/内部prompt cache/输出路径显式传入，保留DMD8与StageB50固定FP8配方。Spark官方配置加载器验证两变体及特殊字符路径通过；本地受控休眠子进程取消后确认回收通过。尚非实际模型取消/Worker/Host验收，原生GPU队列不变。

- 2026-10-09：H3数字人采样入口修复原生视频 VAE 的[B,T,H,W,C]展平，与标准VAEDecode一致。新增隔离 Runtime 入口 run_h3_avatar_native.py；首次缺soundfile，补现有audio profile后全部依赖路径检查通过（未加载GPU）。实机基础生成已排队等待OpenVDN shell3862440退出，仍未计生成通过。

- 2026-10-09：InfiniteTalk 真实服务适配器验收入口 check_infinitetalk_adapter.py 已同步，复用官方25帧/40步、Host checkpoint/上传 parts 与受控产物目录，检查音视频解码及 stop 释放。run_infinitetalk_native.sh 增加 adapter 分支，保留默认 native 行为；本地语法和 Spark 实际 SDK/adapter 导入通过。尚未执行真实 adapter 推理，原生 session9930/PID3835826确认仍运行13/40，已有串行队列保留。

- 2026-10-09：H3数字人基础采样入口 check_h3_avatar_native.py 已准备，固定输入音频 latent 并复用现有原生采样器；核对 H3Studio 基础设置后使用 res_multistep/simple/20步，不误用无 LoRA 的 Turbo8步。加入视频和音轨解码检查；仅语法通过，未运行，不计模型支持。现有 GPU 队列保持串行，InfiniteTalk 观察12/40。

- 2026-10-09（in_progress）：H3真实语音音频VAE CPU重试通过（禁用MKLDNN）：latent[1,32,2,93]、解码[1,74400,2]、固定音频构造保持原latent，32.73秒。保留CPU首轮失败；数字人采样/口型/服务接入仍未验收。

- 2026-10-09（in_progress）：H3真实音频VAE CPU验收脚本已运行，首轮ARM卷积报illegal immediate parameter；仅CPU探针禁用MKLDNN重试，尚未通过，不改变CUDA采样。

- 2026-10-09（in_progress）：核实H3导出Runtime已有TorchAudio2.10CPU匹配Torch2.10CUDA，实际隔离Python音频重采样规划通过；此前缺依赖仅裸h3-venv，无需改包依赖。VAE/数字人采样仍待验收。

- 2026-10-09（in_progress）：H3数字人补32kHz双声道/40Hz音频latent网格规划及官方VAE调用，首轮CPU检查缺TorchAudio，复用匹配音频层重试；VAE实机与固定音频采样仍待完成。

- 2026-10-09（in_progress）：OpenVDN完整基础29文件77.3GB与来源锁摘要全部匹配，官方DMD8实机验收排队等待Ex-Omni退出；尚未模型加载/成片。

- 2026-10-09（in_progress）：Ex-Omni固定启动脚本增加adapter入口，真实Worker生成排队在H3 HTTP验收之后（session35426等待PID3844318）；未计实际调用通过。

- 2026-10-09（in_progress）：H3数字人新增固定音频/续接上下文latent候选，复用Comfy原有联合遮罩与时间步/缩放路径；CPU合同验证通过，音频VAE规划、真实采样和服务接入待完成。

- 2026-10-09（in_progress）：OpenVDN新增现有Comfy H3文本编码器缓存导出候选，核对无模板/第50层/标签语义并保留NVFP4精度来源；尚未真实编码或质量比较。

- 2026-10-09（in_progress）：OpenVDN新增官方DMD8/StageB50实机入口，124帧短片、官方tuned FP8、原始缓存提示词；两配方官方配置加载验证通过，基础权重下载中，生成/自定义提示词编码/Worker待完成。

- 2026-10-09（in_progress）：OpenVDN Torch2.13/cu129安装成功，官方依赖安装session57322继续。Stage-B新增同摘要共享权重校验与复用脚本，保留原始张量，不进行格式近似转换。

- 2026-10-09（in_progress）：OpenVDN官方原始基础DiT/VAE 29文件77.3GB已锁定并启动下载，独立依赖脚本固定Torch2.13/cu129与Triton3.7.1、防止解析升级；脚本语法检查通过，执行待基础框架安装完成。

- 2026-10-09（in_progress）：OpenVDN Torch2.13/cu129 ARM64解析成功，独立安装session27837继续；固定源码与官方补丁Diffusers已同步Spark，尚未依赖导入或实机生成。

- 2026-10-09（in_progress）：OpenVDN 17份锁定文件5.47GB校验全部通过；固定Diffusers基线并应用官方补丁，独立Torch2.13 ARM64依赖解析继续，尚未实机推理。

- 2026-10-09（in_progress）：OpenVDN H3官方源码固定e262cb5，5.47GB DMD8/共享分支权重固定摘要并启动下载；核对StageB50共享权重及混合注意力需求，官方Torch2.13/补丁Diffusers依赖尚待准备，未计支持。

- 2026-10-09（in_progress）：H3 Turbo独立未签名Runtime副本已完成并更新Worker模块，导入通过；HTTP基础验收已排队等待InfiniteTalk PID3835826退出，未计通过。

- 2026-10-09（in_progress）：InfiniteTalk新增Host checkpoint/上传图音频Worker入口，官方音频条件、帧数/步数校验、共享媒体封装和请求所有权；语法及无效参数拒绝检查通过，真实服务调用尚未运行。

- 2026-10-09（in_progress）：H3隔离HTTP验收新增--turbo8，独立挂载overlay，单次基础生成、独立输出目录，语法检查通过，未运行；复杂生命周期矩阵后置。InfiniteTalk首步1/40耗时260.78秒，完整生成仍在运行，性能问题保留。

- 2026-10-09（in_progress）：H3 Worker接入显式lightx2v-8step-v1.0-768p配方，Host独立overlay身份、固定repo/revision、目录约束和进程缓存分离；20项相关回归通过。未启用正式manifest，Turbo实机待验收。

- 2026-10-09（in_progress）：H3Process增加Host解析的可选LoRA checkpoint目录映射，默认基础模型路径保持兼容，为独立Turbo叠加权重准备；尚未启用Turbo模型身份或宣称实机通过。

- 2026-10-09（in_progress）：Ex-Omni真实Worker三秒图音频验收脚本已准备并同步Spark，SDK导入通过，等待GPU；InfiniteTalk r4已越过扩展编译并进入CLIP/VAE，完整生成尚未通过。

- 2026-10-09（in_progress）：新增Ex-Omni Teacher Worker适配器，Host权重/上传图音频/共享请求生命周期接线，语法检查通过，真实适配器与HTTP/Host验收待完成。InfiniteTalk复用匹配Python开发头文件修复扩展编译，r4运行中。

- 2026-10-09（in_progress）：InfiniteTalk开发入口补齐独立Ninja1.11.1.4及CUDA编译路径；官方Quanto FP8扩展首次编译/生成r3运行中，保留r1图片ffprobe及r2缺Ninja失败证据。

- 2026-10-09（in_progress）：Ex-Omni官方Teacher基础视频+音轨实机通过（122帧720×400，834.64秒）；Worker/Host待接入。InfiniteTalk图片输入错误依赖ffprobe已在固定源码准备器修复，r2真实生成运行中，未发布。

- 2026-10-09（in_progress）：H3 Turbo8步图补丁接入官方LoRA及视频6/音频3偏移，固定后端构图通过，短视频实机脚本就绪但尚未运行。4步v1.2参数待确认，正式Worker/Host未启用。

- 2026-10-09（in_progress）：H3 LightX2V4/8步固定原始与Comfy格式输入；发现格式和采样偏移要求，独立准备权重中，未启用模型声明。H3数字人固定音频条件仍属缺口。证据 spark/evidence/media/h3-variant-gap-20261009.json。

- 2026-10-09（in_progress）：InfiniteTalk/Ex-Omni全部固定权重校验完成；Ex-Omni已匹配加载官方增量权重并进入50步真实采样，session31562仍运行，尚未计生成通过。InfiniteTalk基础推理待前一GPU任务结束。

- 2026-10-09（in_progress）：Ex-Omni 完整媒体加载器/tokenizer导入通过，新增官方50步基础实机脚本及两模型离线开发入口；复用匹配Torch2.10音频层。大文件下载继续，尚未视频生成/签名安装/发布。证据 spark/evidence/media/media-native-entrypoints-20261009.json。

- 2026-10-09（in_progress）：Ex-Omni 新增官方Teacher媒体独立入口 cuda_exomni_engine.py，固定18.96GB视频/音频tokenizer来源锁并下载校验；不加载对话模型。独立依赖安装及Teacher配置/入口导入已通过，尚未运行完整生成，未发布。

- 2026-10-09（in_progress）：新增 InfiniteTalk 官方音频编码和FP8基础生成入口、实机脚本；真实音频编码发现Transformers5隐藏层接口不兼容，已在独立4.49/ Diffusers0.35.1层通过音频编码（267帧/2.21秒）和整管线导入。31.94GB主权重下载仍进行；尚不声明视频生成通过。

- 2026-10-09（in_progress）：InfiniteTalk 新增可复现固定源码兼容准备器及单GPU SDPA后端；Spark真实注意力公式对照和官方管线导入通过，完整FP8模型推理仍待权重下载完成。保留padding/因果语义并拒绝未支持的分布式配置；未发布Runtime/Package。证据 spark/evidence/media/infinitetalk-compatibility-20261009.json。

- 2026-10-09（in_progress）：InfiniteTalk 固定官方源码及31.94GB官方单人FP8权重，新增公开固定版本下载校验器；下载进行中、尚未实机生成。Python3.12及注意力依赖兼容待处理。未改动现有Runtime，未发布，证据 spark/evidence/media/infinitetalk-preparation-20261009.json。

- 2026-10-09（in_progress）：MuseTalk 新增模板合成与 CUDA Worker 适配器；输入沿用显式逐帧人脸框/遮罩，输出复用 Mac 共享 MP4/AAC 编码器。Spark 576×768、25帧带音轨模板实机通过（11.90秒）；适配器基础CUDA调用已通过（9.46秒、stop后模型释放），HTTP隔离/Host发现/签名安装仍未完成。未改动 Mac 模型实现，未发布。

- 2026-10-09（in_progress）：按用户覆盖优先要求新增 MuseTalk 官方 CUDA 核心与固定权重下载器；固定官方源码 `0a89dec45a0192b824e3cf4daf96c239440c5ed8`，原始 UNet/VAE/Whisper 在 Spark 完整摘要校验通过。基础 CUDA 实机 25 帧人脸序列已通过（16.112 秒，见 spark/evidence/media/musetalk-native-20261009.json），模板合成/音轨/Worker/Host/签名安装未完成；未发布、未变更 Mac App 或现有 Runtime。

- 2026-10-09：Host新增调用者身份绑定的队列取消，运行中带context取消校验active lease；防止排队任务取消仍启动模型、或错误回收其他请求Worker，含活动request ID重用保护。43项测试及Spark真实协议Worker争用验收通过，未部署正式Host/Runtime。见 spark/evidence/media/ideogram4-queue-cancellation-20261009.json。

- 2026-10-09：Host checkpoint完整性校验新增Ideogram官方CUDA FP8四组件布局，沿用各组件必须存在和分片检查，不冒用MLX实现标识；21项checkpoint回归通过。真实Qwen/Ideogram标准权重解析、模型发现、48GiB/阶段常驻预算加临时准入、Supervisor回收实机通过：485.57秒，PNG完全匹配固定基线，process stopped×2/evict completed×2，无资源预留。仍是未签名记录/显式Runtime resolver/start注册fixture，尚未正式安装发布。见 spark/evidence/media/ideogram4-managed-model-workflow-20261009.json。

- 2026-10-09：上述回收保护已用Spark真实Supervisor/ServicePackageManager+一次性协议Worker通过两轮生命周期验证，进程/socket/proxy/数据库停止状态一致，busy/pin/reservation/stale generation拒绝正确。实际模型整合和签名安装仍待完成。见 spark/evidence/media/ideogram4-real-supervisor-lifecycle-20261009.json。

- 2026-10-09：统一Host idle回收入口，关闭回收期间的调度准入与pin竞态；取消等待实际回收结束。Supervisor停止前二次核对generation/managed identity，避免idle snapshot等待期间重启导致误停替代Worker。46项资源/调度/API/Supervisor测试通过；实机生产生命周期整合与打包发布待完成。见 spark/evidence/media/ideogram4-host-resource-eviction-20261009.json。

- 2026-10-09：SchedulerLease 支持已执行请求 cancelled 终态；Host JSON/multipart 的流式/非流式 HTTP499计取消，避免误入失败统计。81项 provider/scheduler/resource测试通过，含重复释放/后续准入。隔离Host与Runtime覆盖层实机绘图取消通过：2/48步取消后1.629秒退出回收，completed1/cancelled1/failed0、无任务/PNG残留。尚未打包部署。证据 spark/evidence/media/ideogram4-host-cancel-counter-20261009.json。

- 2026-10-09：修复系统 Model Worker 非流式请求 HTTP 499/任务取消被记录为 failed 的问题，现记录 cancelled；普通错误仍为 failed，保持清理输出和执行锁。22 项 Worker 协议测试通过；Spark 独立 Runtime 覆盖层实机已复现原失败并验证修复：扩写取消状态 cancelled、无后续绘图、Worker 回收；冷加载取消仍约158秒，Host scheduler将499计failed的统计问题待修。后续 Runtime/Desktop 候选需纳入，尚未发布。见 spark/evidence/media/ideogram4-two-stage-cancellation-20261009.json。

- 2026-10-09：新增 Spark Ideogram 双 Runtime Host 组合实机验收脚本；本地工作流测试增至 8 项（绘图取消等待、忙碌回收拒绝）。真实双阶段组合实机通过：扩写/回收/出图总 527.70 秒，1024 PNG 与质量基线一致，最终调度器清空。发现/身份/容器回收仍为 fixture，生产 Supervisor、实机组合取消和产品 API 未接入，不计正式签名安装通过。见 spark/evidence/media/ideogram4-two-stage-host-20261009.json。

- 2026-10-09 Ideogram Host两阶段原型实现：ideogram_host_workflow.py复用ModelInvocationService前台调用/取消，固定派生阶段request ID并沿用可信context；caption完成后要求Host idle-only释放，失败/截断/重复字段拒绝，取消重试至Worker注册且等待请求结束，回收中取消亦等待并阻止下一阶段。6项本地测试通过；尚未注册公开API，真实两阶段Supervisor/资源准入/签名资产及产品集成未验收。证据 spark/evidence/media/ideogram4-host-workflow-20261009.json。

- 2026-10-09 Ideogram三组实际扩写图44882 exit0：茶壶SHA与已目视通过1024控制一致；中文熊猫全身/坐姿/双前爪吃竹及竹林满足核心要求；海报准确OPEN 24 HOURS居中且无额外内容。固定三样例目视通过，不外推全部质量。图像暖52.26/51.26秒，首图255.71秒含加载，关闭9568256字节；与扩写暖60.99/63.24秒为独立常驻阶段测量，不等于产品端到端延迟。Host分阶段整合/更多种子/最大尺寸/签名发布仍待完成。证据 spark/evidence/media/ideogram4-caption-corpus-20261009.json。

- 2026-10-09 Ideogram三样例Qwen15547 exit0：三项finish_reason stop、官方归一化/schema通过；茶壶caption与前次d4933538摘要一致。中文熊猫核心语义及OPEN 24 HOURS原文保留，附加细节需图像检查。扩写冷238.19秒，暖60.99/63.24秒，延迟仍显著。44882真实caption批量1024同进程出图已启动，尚未质量判定。证据 spark/evidence/media/ideogram4-caption-corpus-20261009.json。

- 2026-10-09 Ideogram批量质量图像脚本准备完成：严格读取逐项真实caption及验证摘要，1024/12步/seed42同一常驻adapter输出三图，记录冷暖耗时/峰值分配及关闭分配；不把出图等同质量通过。15547扩写仍运行，未并行占用GPU。新增check_ideogram4_caption_corpus_images.py语法检查通过，待扩写完整且schema检查通过后执行。

- 2026-10-09 Ideogram最新源码69565标准HTTP/Host回归exit0：adapter986397f3/engine376fbe25摘要与当前源码一致，正常/取消恢复/drain-resume/Host交替图均基线SHA相同，取消0.212秒，身份传递/调度completed2 queued0 running0通过。仍unsigned fixture。三条caption tokenizer总预算8096/8097/8103均<8192；随后15547真实Qwen批量扩写启动，准备冷暖耗时和中文/文字质量，不计已通过。

- 2026-10-09 Ideogram最新源码标准HTTP/Host回归69565启动，独立http-host-sampler-fixed-r1，探针新增源码SHA和独立目录参数。另固定三项实际普通prompt语料（茶壶对照/中文熊猫/英文OPEN 24 HOURS海报），复用官方build_messages，Qwen探针支持批量保留逐项响应及cold/warm耗时；语料尚未执行，不计质量通过。当前GPU串行，先完成Host回归。

- 2026-10-09 Ideogram真实额度OOM53302 exit0：两轮resource_exhausted/503后同进程恢复，恢复图SHA均68934ced…eaa0，保留两个错误对象，停止后CUDA分配均9568256字节，无锁/events/临时输出残留。第一轮OOM后0、第二轮9568256字节，未见停止后递增。仅进程内额度/两轮，非HTTP OOM/系统级压力或长期稳定性；签名发布仍待完成。匿名生产容量复核仍4GiB，记录artifacts/runtime-upload-capabilities-recheck-ideogram.json。证据 spark/evidence/media/ideogram4-real-oom-20261008.json（测试始于10月8日，完成于9日）。

- 2026-10-08 Ideogram采样修复63270 exit0：12/20/48各与直接官方PRESETS管线完整PNG SHA一致，真实步数正确。512/seed42，20步30.43秒、48步72.07秒，峰值29.71GB，关闭后9568256字节；12步198.47秒含加载，直调暖态18.54秒。仅固定同权重桥接样例，不外推质量/最大尺寸/正式安装。随后53302两轮进程内额度OOM恢复启动，结果待定。证据 spark/evidence/media/ideogram4-sampler-presets-20261008.json。

- 2026-10-08 Ideogram官方采样档位实机63270启动：新引擎376fbe25，固定实际Qwen caption/512/seed42，12/20/48逐项核对真实进度步数、直接调用官方preset完整PNG SHA及显存/耗时。原HTTP fixture未替换，新源码结果待定；未据本地测试宣称实机通过。

- 2026-10-08 Ideogram实际扩写默认1024复验30402 exit0：完整红色陶瓷茶壶、主体大致居中、浅木桌/浅白背景且无多余文字，固定单样例目视通过，SHA8593429d…49e5，图像冷249.93秒/峰值32.20GB。同一实际Qwen输出和官方归一化，不是手写替换；512偏左失败保留。仅证明此样例可行，多样例/暖态caption延迟/Host分阶段编排/采样修复实机/签名发布仍未完成。证据 spark/evidence/media/ideogram4-caption-qwen-20261008.json。

- 2026-10-08 Ideogram4采样合同修复：20/48此前错误沿用Turbo schedule，现从固定官方PRESETS加载12/20/48对应guidance/mu/std；其他显式步数标记custom而不冒称官方档位。25测试通过，fixture切换至仓库固定官方源码后3引擎测试再通过。当前30402是旧源码12步质量复验，数值参数本就相同；新引擎实机及20/48资源质量待验。证据 spark/evidence/media/ideogram4-sampler-presets-20261008.json。

- 2026-10-08 实际Qwen扩写→Ideogram 25797 exit0：512/seed42生成完整红茶壶（壶嘴/把手可见）、浅木桌和浅背景，无额外字，但主体偏左，“居中”未通过。SHA088a5486…fb57；扩写冷234.20秒+图像冷253.32秒≈487.52秒（不含进程切换），不能称产品性能达标。已保留图与失败对照，同一caption产品默认1024复验30402运行中，未改描述或权重。证据 spark/evidence/media/ideogram4-caption-qwen-20261008.json。

- 2026-10-08 Qwen caption45025 exit0：实际输入6560/输出237 tokens，finish_reason stop；原始响应保留。初校验aspect_ratio失败定位为探针漏官方归一化，补用固定官方strip_aspect_ratio_and_bboxes默认行为（去aspect_ratio/bbox，不改描述文字）后schema通过，caption SHA d4933538…4034。实际描述保留红茶壶/浅橡木桌/白背景/居中；25797正以真实caption实图验收，不用手写替换。尚未判定图像成功。

- 2026-10-08 Ideogram caption首次Qwen23768 HTTP400终止，原脚本未保留响应body，不作精确错误文本推断。固定tokenizer input_ids计6560，加输出2048超过Worker8192合同；保留完整官方模板将输出限1536，45025以独立r2目录重试。脚本补充caption错误响应留证；图像脚本新增--caption-file以实际扩写文件作输入并记录SHA。未改上下文限制、产品API或宣称扩写成功。

- 2026-10-08 Ideogram4语义caption实验23768启动：复用现有Qwen3.8 27B NVFP4独立Runtime/标准隔离Worker，将固定官方Magic Prompt v1系统词与未修改build_messages函数构建请求。新增验收脚本--caption-request路径，不改产品API、不新增模型或读取Cookie。Qwen替代不是官方已验扩写路径；需先检查响应再实图验收，当前未完成。证据 spark/evidence/media/ideogram4-caption-qwen-20261008.json。

- 2026-10-08 Ideogram4普通prompt复验30121 exit0但质量再次失败：全场景obj替代空elements后仅左上角出现裁切红器皿及多余文字，不能认定修复；原图/回执保留quality-literal-r2。固定结构化布局像素诊断确认红圆/蓝方左右分离但bbox偏移，不声称精确坐标。核对固定官方prompting指南及Mac历史诊断：格式校验/模板包装不等于有效语义caption。后续需验证真正语义caption构建路径；当前普通prompt方案不可按成功修复发布。证据 spark/evidence/media/ideogram4-quality-20261008.json。

- 2026-10-08 Ideogram4质量41923 exit0但普通prompt失败：英文SPARK STUDIO与官方pipeline直调SHA完全一致，中文字形星火工作室准确，左右双色双形状相对布局正确；精确bbox未通过。普通茶壶prompt几乎灰色空白，不能视作功能完成。修复候选将原词写入单一全场景obj，替代空elements，不调用LLM也不称等价Magic Prompt；24测试通过，30121实机复验运行中。证据 spark/evidence/media/ideogram4-quality-20261008.json。

- 2026-10-08 Ideogram4固定质量语料实机41923启动：英文SPARK STUDIO、中文星火工作室1024²，双形状布局768²，普通prompt512²，固定seed42/12步。英文另直调未改官方pipeline对照；记录峰值CUDA分配与原始图。尚无结果，不以输出成功替代目视质量；仅Comfy固定权重桥接，不称原始官方checkpoint对照。

- 2026-10-08 Ideogram4已安装Host调用42935 exit0：Host/direct/Host三图完整SHA均68934ced…eaa0，耗时18.50/18.48/18.50秒；dataUrl/b64一致、Worker请求succeeded、actor/app/session/request传递和调度completed2/failed0/queued0/running0通过。相同独立隔离Worker HTTP回归仍通过；身份/发现为fixture，不能记作产品UI/签名安装。广泛质量与发布仍待完成。证据 spark/evidence/media/ideogram4-host-20261008.json。

- 2026-10-08 Ideogram4 Host调用桥接候选：使用实际已安装ModelInvocationService/WorkerJobScheduler及标准UDS代理，交替Host/direct/Host图像对照，验证actor/app/session/request身份、dataUrl与b64一致及调度归零。42935实机测试启动；发现/身份仍fixture，结果待定。

- 2026-10-08 Ideogram4标准HTTP沙箱79734 exit0：首图225.55秒含加载，取消后19.27秒、resume后18.52秒三图SHA均68934ced…eaa0。HTTP取消返回0.207秒，401鉴权/非法输入/499取消/503 drain/resume及active_requests归零通过。容器network none/read-only rootfs/cap-drop ALL/no-new-privileges/nonroot1000已检查；独立unsigned Runtime 72包依赖约束无冲突。仍非Host产品工作流、签名安装/发布或广泛质量验收。证据 spark/evidence/media/ideogram4-isolated-http-20261008.json。

- 2026-10-08 Ideogram4标准HTTP隔离验收推进：67707独立unsigned fixture装配完成，复用自包含Python、固定Torch2.11依赖与已安装Host代码，按依赖约束补充缺失Server库。标准Supervisor Docker网络关闭/只读Runtime和checkpoint验收79734启动，结果待定，不替换现有Runtime且不构成签名发布。

- 2026-10-08 Ideogram4真实CUDA adapter 39261 exit0：固定四权重/六tokenizer输入校验后，通过已安装Host协议调用。首图与显式取消、task取消后的两张恢复图SHA均68934ced…eaa0，恢复19.48/19.21秒；保留两个异常后stop CUDA分配9568256字节，锁/events/临时输出清空。首请求219.78秒含校验加载；取消3.30秒为整案例耗时而非取消响应延迟。仍非HTTP/Host调度/sandbox/签名安装或广泛质量验收。证据 spark/evidence/media/ideogram4-worker-candidate-20261008.json。

- 2026-10-08 Ideogram4固定输入接入：加载前完整校验四checkpoint与六tokenizer/config文件size/SHA，逐块可取消且仅释放已验证大文件页缓存；保留结构化prompt原文避免隐式JSON重排改变token。23测试通过，39261真实CUDA adapter已启动，尚待结果；非HTTP/签名安装验收。

- 2026-10-08 Ideogram4 Worker候选：增加image_generation合同、显式literal caption包装、请求去重、任务取消等待原生线程及清理、停止拒绝新任务；OOM关闭移入持锁线程，避免关闭下一请求引擎。19项本地测试通过（适配器为注入引擎）；未执行真实CUDA Worker/HTTP Host，固定checkpoint/tokenizer清单集成与质量门禁仍待完成。证据 spark/evidence/media/ideogram4-worker-candidate-20261008.json。

- 2026-10-08 Ideogram4常驻原生引擎18618 exit0：正常512²/12步及两次取消后恢复三图SHA均与原版pipeline首图68934ced…eaa0一致；真实第2/4去噪步取消、无残留输出/挂钩，保留两异常后close模型弱引用释放且CUDA分配9568256字节。暖态恢复19.00/18.74秒；取消案例总耗时3.24/6.18秒含取消前计算，不误称取消响应延迟。10回归通过。尚非HTTP/Host、transport取消、真实OOM或完整尺寸步数/质量验收。证据 spark/evidence/media/ideogram4-engine-20261008.json。

- 2026-10-08 Ideogram4常驻原生引擎实现：复用已验低分配官方加载，结构化caption和产品尺寸/步数/seed边界校验、前向边界取消、临时输出原子替换、异常帧释放及close；10项合同/取消恢复测试通过。18618真实normal/cancel/recover/close在途，未认定生命周期或Worker支持完成。见 spark/evidence/media/ideogram4-engine-20261008.json。

- 2026-10-08 Ideogram4完整原版CUDA管线61973 exit0：低分配加载四组件严格成功，加载约187.56秒，512²/12步/seed42生成21.05秒，结束Torch分配28.12GB；图像SHA/RGB全解码通过，目视红茶壶/浅木桌/白背景正确但壶偏左过大及裁切，未批准精确bbox或广泛质量。真实两个FP8最终层CPU F32/BF16与标量参考max0。仍为Comfy权重桥接而非原始官方checkpoint整图对照；Worker/取消生命周期/Host/签名安装未完成。证据 spark/evidence/media/ideogram4-native-image-20261008.json。

- 2026-10-08 Ideogram4原完整加载78517在条件FP8复制CUDA时OOM，未生成图像。低分配构造候选复用官方网络/量化/严格assign；首轮小模型87229发现rotary buffer遗漏官方BF16转换，修正后69195全42项状态、所有buffer及真实CUDA前向逐字节一致(max0)。完整检查61973以独立native-r2重新启动，文本编码器亦空参数构造；未改官方数值算法，不以小模型通过宣称完整可用。证据 spark/evidence/media/ideogram4-loading-memory-20261008.json。

- 2026-10-08 Ideogram4 Spark准备完成：51377传输完成、99551四文件29.49GB全SHA通过，文件级定向fadvise；独立venv安装官方SHA锁定Torch2.11.0+cu130 ARM64、Transformers5.12.1、bitsandbytes0.49.2，pip check/官方源码导入/GB10 sm121实算通过，完整依赖锁保存。现有Torch2.10 Runtime不变。78517官方原版pipeline+严格Comfy本地布局桥接基线已启动，完整四组件加载和512/12步图像结果尚待验证。证据 spark/evidence/media/ideogram4-spark-preparation-20261008.json。

- 2026-10-08 Ideogram4权重格式桥接候选完成：官方VAE的Diffusers转换器对Comfy原生命名拒绝，直接原生251项匹配；文本编码器初映射误将model.visual归入language_model，已分离，严格749项名称/形状通过。cuda_ideogram4_checkpoint.py不重新量化矩阵，仅校验描述/有限正scalar并扩展官方行scale、明确移除特征编码器无用lm_head，8测试与674组真实scale/descriptor检查通过。未做完整矩阵数值/实际CUDA推理，51377权重传输仍活跃。证据 spark/evidence/media/ideogram4-fp8-bridge-20261008.json。

- 2026-10-08 FlashHead取消清理最新适配器标准HTTP/Host回归20165 Lite、8530 Pro均exit0：源码摘要匹配99025251，两变体签名只读权重视图正常生成/取消恢复/auth-drain-resume与Host四组50帧逐像素精确，调度归零；Runtime及发现身份仍fixture，不代表签名安装。另固定官方Ideogram4源码990fe1c4归档SHA c2be5a5b…aad7并审计加载合同，官方逐行FP8与Mac Comfy标量缩放布局需验证，尚无CUDA推理。证据 spark/evidence/media/flashhead-cancel-fixed-host-20261008.json 与 ideogram4-official-source-audit-20261008.json。

- 2026-10-08 FlashHead任务中断泄漏修复实测通过：34201原候选保留asyncio取消异常后两轮stop分配4.42→8.84GB；新增CancelledError分支，在共享适配器等待原生线程后清理异常帧，16测试通过。32139 Lite两轮均10223616字节，37950 Pro均9568256字节，取消输出删除/锁与token释放/同进程恢复官方MP4 SHA通过，Package准备源码同步。未做真实socket断连、长期压力或签名安装，不据此宣称全部生命周期完成。证据 spark/evidence/media/flashhead-task-cancel-recovery-20261008.json。

- 2026-10-08 FlashHead任务中断清理候选：34201真实asyncio取消两轮显存增长，补CancelledError分支在共享适配器等待原生线程后断开异常帧引用；16项测试通过，Package准备源码同步。32139实机复验运行中。真实socket断连和签名安装不在当前证据范围，见 spark/evidence/media/flashhead-task-cancel-recovery-20261008.json。

- 2026-10-08 FlashHead真实取消泄漏修复完成实机验收：旧14734两轮保留异常后stop分配4.42→8.84GB；CUDA取消路径清理并断开原生traceback、保留文本诊断，15项测试通过。49905 Lite两轮停止后均10223616字节，18924 Pro均9568256字节，持有两异常时恢复MP4均与固定官方SHA完全一致。Package准备源码同步。仅显式请求取消/原生进程，两轮不代表长期压力或transport任务取消；签名安装发布仍未完成。证据 spark/evidence/media/flashhead-real-cancel-recovery-20261008.json。

- 2026-10-08 FlashHead真实取消泄漏修复候选：14734两轮持有取消异常后stop分配4.42→8.84GB，门禁失败；CUDA取消路径保留文本栈并断开原生traceback引用，15项测试含闭包弱引用释放通过。Package准备源码同步；49905实机复验运行中，不宣称修复已验收。见 spark/evidence/media/flashhead-real-cancel-recovery-20261008.json。

- 2026-10-08 FlashHead Pro真实OOM恢复36995 exit0：固定签名分发只读目录，两轮分配额度OOM均映射503，保留两异常对象后仍可同进程恢复，两MP4 SHA与官方2981d0d8…f5fa一致，停止后CUDA分配均9568256字节。适配器源码摘要与已验候选一致，补齐Pro独立额度恢复门禁；不代表系统压力预防、HTTP OOM或长期稳定性/质量/签名安装通过。生产上传合同匿名复核仍4GiB，完整媒体Runtime扩容仍未生效。证据 spark/evidence/media/flashhead-real-oom-recovery-20261008.json。

- 2026-10-08 部署后SenseVoice复验：51372首次OOM，保留失败；62433仅对本次备份35个大普通文件fsync/fadvise，MemFree6242724→13676044KiB，无全局清缓存；97728随后实际安装Host+签名只读权重通过九格式ASGI/Quick Read/长音频/取消恢复。支持文件缓存压力判断，非排他根因证明；更新开发升级脚本在未来备份后定向释放大文件缓存，未重复整次升级。身份/发现及Runtime仍fixture，正式安装发布未完成。证据 spark/evidence/media/spark-host-cache-policy-wheel-20261008.json。

- 2026-10-08 Spark开发Host缓存策略部署完成：0329ca07 wheel仅三个Python文件变化；82861独立启动重启、86888旧新Host及原路径备份恢复四轮通过。13163实际开发服务停机保留完整私有data/venv备份后更新，schema81/完整性/身份安装记录数量保持；62721安装字节与wheel一致、缓存开关生效及实际重启通过。76576 Pro自动缓存导入后2秒输出SHA与官方一致，取消恢复/Host四对50帧精确通过，无手工清缓存。115相关测试既有通过；并发性能/全面内存准入/签名Runtime和Package安装仍未完成。证据 spark/evidence/media/spark-host-cache-policy-wheel-20261008.json。

- 2026-10-08 Checkpoint文件页缓存候选实机通过：显式release_page_cache及Host环境开关AI2APPS_CHECKPOINT_RELEASE_PAGE_CACHE=1（默认关闭），仅已复制源/完整hash后的>=64MiB普通文件fsync+fadvise，best effort不影响验签。63缓存+52安装编排测试通过。49455独立候选完整导入FlashHead15.08GB，Cached仅增2304KiB，空闲保持约17.64GiB；22931随后无需手工处理即可Lite推理/取消恢复/Host四对精确通过。最初测试发现_snapshot_matches类方法不可访问实例策略，已改实例方法并回归。未部署实际Host，Pro自动导入后验证/并发性能/全面内存准入仍待完成。证据 spark/evidence/media/checkpoint-page-cache-policy-20261008.json。

- 2026-10-08 Checkpoint页缓存策略候选进行中：CheckpointCache新增release_page_cache显式参数，Host可通过AI2APPS_CHECKPOINT_RELEASE_PAGE_CACHE=1启用；默认关闭。大文件复制源及完整hash后执行文件级fsync/fadvise，保持全部验证，平台不支持时best effort。63项缓存回归通过，Spark独立候选15GB导入验收运行中；未部署Host，不能宣称已解决系统内存准入。

- 2026-10-08 FlashHead Pro签名快照33695 exit0：真实只读distribution目录2秒50帧输出与官方基线完整MP4 SHA一致，取消恢复/身份传递/调度空队列及Host四组逐像素对照通过；两变体签名缓存到Worker链路均完成开发验收。Runtime仍unsigned fixture，Registry下载/签名安装发布和广泛口型质量未完成。缓存代码核对定位import_local_snapshot复制源及promote/materialize多次完整读取，后续内存处理需同时覆盖源和缓存文件，不能全局drop_caches或跳过验签。证据 spark/evidence/media/flashhead-signed-cache-worker-20261008.json。

- 2026-10-08 FlashHead签名分发缓存验收：48495 Mac及15001 Spark完整21文件约15.08GB验签/哈希导入、只读Worker快照、Host Supervisor和Package布局通过，错误分发/变体拒绝。7764校验后缓存压力触发503；对本任务11个唯一tensor文件定向fadvise后恢复。39346发现Host探针旧upstream alias拒绝，改用实际分发元数据，无生产放宽；88848 Lite签名目录推理/取消恢复/Host四对50帧精确通过。Pro签名目录实推待做；正式内存策略、Registry下载、签名Package安装发布仍未完成。证据 spark/evidence/media/flashhead-signed-cache-worker-20261008.json。

- 2026-10-08 FlashHead发布准备推进：匿名当前Index121验证既有Publisher，精确Keychain公钥指纹一致；1121标准构建器metadata_verified签名Lite11文件8161965386字节与Pro10文件6916079998字节，两envelope独立验签通过。未读Cookie/未提交发布，既有精确批次授权仍待回复。新增packages/ai2apps-model-flashhead-cuda源码准备，适配器/共享文件SHA与最近实机回执一致，保留license与固定spec；无ai2apps.json/service.yaml，不冒充可安装Package。证据 spark/evidence/media/flashhead-distributions-signed-20261008.json。

- 2026-10-08 FlashHead CUDA OOM恢复修复通过：14项测试覆盖PyTorch OOM/明确AcceleratorError映射503及非OOM仍500。43571两轮真实进程内分配限额OOM，持有异常对象时恢复输出均与官方MP4摘要一致，stop后CUDA分配稳定10223616字节；29219当前源码标准禁网Worker正常推理/取消恢复/Host四组逐像素对照通过。不是文件缓存压力的预防修复，Pro限额恢复/签名安装发布仍待完成。证据 spark/evidence/media/flashhead-real-oom-recovery-20261008.json。

- 2026-10-08 FlashHead CUDA OOM恢复候选进行中：将包装后的真实PyTorch OOM/明确CUDA allocation AcceleratorError转为503 resource_exhausted，保留文本栈并释放异常帧及模型；其他错误仍500。14项回归通过，43571真实进程内分配限额OOM/恢复运行中；尚未发布。

- 2026-10-08 FlashHead固定官方对照53827/44458均exit0：Lite/Pro相同图片、PCM音频及推理前seed0，各2秒50帧，独立官方单GPUpipeline与CUDA Worker整个MP4 SHA完全一致（Lite ae768037…f3f1，Pro2981d0d8…f5fa）。保留既有optional-import/Pro安全权重加载准备，未改变上游kernel。45529首轮因探针共享依赖优先错误失败，修正为Worker一致profile优先后通过。不扩大为通用口型质量；多样样本/签名安装发布/内存准入仍待完成。证据 spark/evidence/media/flashhead-official-seeded-comparison-20261008.json。

- 2026-10-08 FlashHead请求RNG修复扩展实机验收：75779 Lite2/10/60秒通过，60秒73.07秒生成、取消0.397秒；96120 Pro2/10秒通过，10秒78.96秒生成、取消0.232秒。两变体各四组Host/直接暖态对照50帧逐像素一致，身份传递/调度空队列及drain-resume通过。全部50/250/1500帧解码、H264/AAC准确时长、音频相关性>0.9996；Lite末帧目视无明显破损，非口型质量声明。Pro有traceback诊断插桩，未签名安装，官方同seed质量基线及内存准入仍待完成。证据 spark/evidence/media/flashhead-seeded-long-20261008.json。

- 2026-10-08 FlashHead Lite请求随机源修复完成实机初验3458 exit0：此前71115相同暖态直接/Host交替四对均约1.7/255像素差；固定上游LTX VAE.sample未使用请求generator，CUDA包装现以fork_rng/manual_seed覆盖整次请求并恢复外部状态。11项测试通过，修复后四对50帧逐像素完全一致，取消恢复、请求身份/调度completed2及空队列通过。未改上游算法/精度；Pro、长视频、官方同seed质量基线、签名安装发布和内存准入仍待完成。证据 spark/evidence/media/flashhead-request-rng-host-20261008.json。

- 2026-10-08 FlashHead CUDA请求RNG修复进行中：官方LTX VAE posterior.sample()使用全局随机源，虽扩散generator固定seed，直接重复与Host重复仍产生约1.7/255平均像素差。候选以fork_rng绑定整个请求并恢复随机状态；11项回归通过，3458实机交替暖态对照运行中。未发布、未修改官方源码或改变模型精度。

- 2026-10-08 SenseVoice独立进程冷启动诊断17170 exit0：五个全新禁网Worker各自完成中英文/时间戳/非法输入/鉴权和生命周期验收，6.25–6.91秒/轮；保留内存数据，未清除系统文件缓存，不等同重启或磁盘冷加载，此前OOM根因仍未确定。61205真实签名缓存→Host Supervisor解析ASR/VAD固定revision、distribution ID及只读仓库根通过；首轮探针误把snapshot当挂载root已修正，无生产代码变更。32相关回归通过。正式签名安装发布保持未完成。证据 spark/evidence/media/sensevoice-cold-worker-series-20261008.json。

- 2026-10-08 SenseVoice真实分发快照→Spark Worker推进：61796在Spark导入并逐文件校验9文件938413143字节，ASR/VAD只读distribution视图及候选Host就绪检查通过。56175首次启动转录503 CUDA OOM，退出后GPU无其他进程，原因未定；47671诊断版、69661原样适配器两轮完整Host/API九格式、长音频、Quick Read、取消恢复及auth-drain-resume通过，原样适配器SHA与源码一致。未替换已安装Host，仍为unsigned Runtime/身份发现fixture；不宣称首次加载可靠性已修复或正式安装完成。证据 spark/evidence/media/sensevoice-checkpoint-worker-spark-20261008.json。

- 2026-10-08 SenseVoice checkpoint就绪缺口修复：官方ASR/FSMN的.pt此前被Host safetensors-only检查拒绝；仅audio_stt/audio_processing的完整不可变distribution回执允许.pt，不放宽普通目录检查。32项缓存及拒绝回归通过（exit0，非致命Metal退出警告）；17011真实938413143字节/9文件签名校验、缓存导入、Worker只读快照、错误distribution拒绝和缓存命中通过。r1失败保留，r2通过；修改尚未部署Spark Host，非Registry下载/正式Package安装验收。证据 spark/evidence/media/sensevoice-checkpoint-cache-20261008.json。

- 2026-10-08 Spark实际开发Host升级完成66533 exit0：同机私有完整data48G/venv备份位于~/ai2apps-spark-dev/host-media-live-upgrade-r1，安装04ff44d5候选wheel，pip check/schema81/SQLite完整性与身份安装记录数量保留通过；39781使用已安装Host（不overlay）九格式ASGI→CUDA Worker、长音频/取消恢复通过；11529实际systemd重启、login200、inode/schema保持与无MLX检查通过。仅开发Host，SenseVoice仍fixture模型发现/未签名Runtime，checkpoint发布与正式Package安装待完成。证据 spark/evidence/media/spark-host-media-live-upgrade-20261008.json。

- 2026-10-08 Host备份恢复演练52561 exit0：合成数据原路径schema79→81→81→79四阶段通过，记录保留、原schema摘要恢复、quick_check正常。52306曾瞬时malformed但停机后两库ok，根因未证实；探针改显式关闭连接/SQLite backup API。14509异路径恢复被安全身份绑定拒绝，最终原路径恢复不削弱检查。真实Host仍active未修改，data48G/venv534M/可用2.3T，探测时无GPU compute任务。实际升级须停服保存程序+数据并原路径回退。证据 spark/evidence/media/spark-host-media-rollback-20261008.json。

- 2026-10-08 新Spark Host wheel独立启动24882与合成升级46144均exit0：新数据2轮健康/login200/SQLite quick_check通过；旧Host schema79→新Host81→重启81三轮通过，合成sentinel保留、inode保持、升级后结构稳定。未复制账户数据，未重启/替换运行中Host。确认实际需要schema79→81迁移，下一步必须备份恢复演练，不能仅旧wheel覆盖回滚。证据 spark/evidence/media/spark-host-media-startup-20261008.json。

- 2026-10-08 Spark Host媒体升级候选：标准wheel构建器补入owner_studio_routes.json，避免新Owner Studio模块导入时缺少路由清单；8项Spark回归通过。标准构建wheel22920303字节/1328entries/SHA04ff44d5a62f7eb4c9feaa718405ae01e8a3a3090f1bf5b0f894b9b2c00597ac，关键4文件与源码逐字节一致；Spark49932独立解包目录导入Host/19条Owner路由成功，MLX显式阻断。尚未替换运行中Host，独立启动及数据库迁移/回退验收待做。证据 spark/evidence/media/spark-host-media-wheel-20261008.json。

- 2026-10-08 SenseVoice实际Host ASGI转录路由→CUDA Worker验收58785 exit0：9格式真实multipart上传/自动解码/模型转发/内容与词时间戳通过，非法音频415、stream400，上下文保持；20调度调用=19成功+1预期拒绝，queued/running0。77339首次因已安装Host缺少reference_audio_sample_rate失败，改为匹配的路由+capabilities源码快照，仅验收进程overlay，不代表正式Host已升级。身份/发现仍fixture，签名安装和Studio mount保持待验收。证据 spark/evidence/media/sensevoice-api-host-20261008.json。

- 2026-10-08 SenseVoice九格式实机Host primitives→ModelInvocationService→禁网CUDA Worker验收32530 exit0：WAV/PCM/MP3/M4A/AAC/FLAC/OGG/Opus/WebM内容及词时间戳边界通过；MP3/OGG/Opus为9,30，其余930，保留原始差异，不宣称逐字一致。长音频/取消恢复/auth-drain-resume通过。首轮60779因过严逐标点比较失败，未改生产适配器。源码摘要、PyAV18.0.0与回执固定；非完整Studio/API或签名安装。证据 spark/evidence/media/sensevoice-codec-host-20261008.json。

- 2026-10-08 SenseVoice双分发签名完成：标准构建器full_dual_download校验ASR936682164字节/5文件/112pieces、VAD1730979字节/4文件/1piece，既有Publisher密钥与新鲜公开Index121匹配，两envelope验签通过。ASR digest401115f89d7058e97fd9def7a4be1fdc73b063578664f78fe0e3528c16857188；VAD digest7a32d3642f54210b49fb2777abef74d11eb86dacbe541f8cdd0f3354c2ad255e。Installation查询仍active user session required；已请求本批两项Dev Cookie授权，尚未读取Cookie/提交/发布。见 spark/evidence/media/sensevoice-distributions-signed-20261008.json。

- 2026-10-08 FSMN VAD精确镜像完成：ai2apps/fsmn-vad固定commit dce94570fbc263aa692d8867b0f47bc03f6330b3，8文件1746044字节上传及匿名完整回下载SHA/size通过。原始4推理文件1730979字节双端标准构建器预检一致，24张量均FP32；新增SenseVoice Package META中的VAD分发spec、完整Apache许可及来源。未读Dev Cookie；未签名/Registry发布，不修改现有模型缓存。原CRLF镜像缺口已解决。证据 spark/evidence/media/fsmn-vad-mirror-verification-20261008.json。

- 2026-10-08 SenseVoice主权重发布源码准备：新增 packages/ai2apps-model-sensevoice-small-cuda 的固定distribution构建spec、许可证、NOTICE及来源；现有标准构建器字节预检完整读取936682164字节/5文件，112个8MiB分块通过；weights_only/mmap检查917张量均FP32。无签名/发布/可安装manifest声明。VAD另查HF六历史版本仍LF，双源精确镜像问题保留。证据 spark/evidence/media/sensevoice-distribution-preflight-20261008.json。

- 2026-10-08 SenseVoice真实取消显存修复：84107/65195引用链定位参数→SANM层→编码器→闭包cell，clear_frames仍因traceback存活保留函数闭包。原生异常调用栈改保留文本note并断开traceback引用；15项测试含闭包所有权回归通过。4424两种真实前向边界取消、保持两异常对象、原样恢复转录通过，停止后分配均9568256字节，替代旧909MB→1.81GB增长。43917标准Docker/Host回归运行中；历史首次OOM根因仍未证实。证据 spark/evidence/media/sensevoice-cancel-memory-fixed-20261008.json。

- 2026-10-08 SenseVoice取消清理候选：共用异常链帧清理覆盖499/transport/nonOOM，14项测试通过；85595真实Linear前向同步后取消/恢复转录都成功，但持有异常并stop后分配909366272→1808738304，内存门禁失败。4777/77540诊断根模型弱引用已释放，仍有920→1840 CUDA张量/参数字典存活，持有链未定位；不宣称取消内存已修复，候选不发布。证据 spark/evidence/media/sensevoice-cancel-memory-20261008.json。

- 2026-10-08 SenseVoice 61892标准禁网Docker/Host回归exit0：当前适配器摘要匹配，长短音频/时间戳/取消恢复/auth-drain-resume通过，补充回执 artifacts/sensevoice-real-oom-r1/host-receipt.json；仍未签名安装，历史首次OOM根因保持未解。

- 2026-10-08 SenseVoice OOM恢复修复：异常链已退出帧可持有半加载CUDA层，清理模型字段后追加traceback.clear_frames再回收缓存；12项测试含保持公开异常活跃时弱引用释放通过。4299内嵌Python真实进程分配额度OOM两轮503→恢复额度→同进程转录一致通过，OOM后分配0/9568256字节、停止后两轮9568256字节稳定；保留两异常对象不妨碍恢复。历史首次AcceleratorError根因仍未确定，不冒充已复现修复。61892 Docker/Host长短转录回归运行中。证据 spark/evidence/media/sensevoice-real-oom-recovery-20261008.json。

- 2026-10-08 GhostV2遮挡Host/Docker验收42491 exit0：r3 Runtime按第六canonical绑定只读挂载XSeg，真实HTTP图片/视频及ModelInvocationService调度图片/视频均通过；401/取消499/active0/drain503/resume通过，容器删除。取回三PNG及双MP4完整SHA/解码通过，视频60帧时序及AAC包与输入逐字节一致。身份上下文字段保持。仍隔离身份和未签名Runtime，HTTP取消非精确GPU阶段，自然遮挡质量、分发许可及正式安装发布待完成。证据 spark/evidence/media/ghostv2-occlusion-host-20261008.json。

- 2026-10-08 GhostV2遮挡Runtime导出完成：标准构建器新增occlusion源码与onnx1.16.1/onnx2torch1.5.15精确依赖，factory纳入模块来源检查；90项回归通过。1110标准profile导出35依赖/74源码，85066内嵌Python -I排除开发site-packages，两轮启用遮挡真实推理/释放重载通过，ONNX转换库来自导出profile，PNG SHA/解码通过。20759独立r3 Runtime树组装并两份74源码逐SHA验证通过。未签名安装/发布；Host HTTP遮挡回归、自然遮挡及许可门槛保留。证据 spark/evidence/media/ghostv2-occlusion-runtime-export-20261008.json。

- 2026-10-08 GhostV2遮挡精度策略修复：XSeg前向局部禁用TF32，成功/异常/取消均恢复原始两个标志，取消回调仍覆盖同步输出；明确依赖Worker串行所有权。54项本地回归通过，96738实机从TF32开启状态完成两轮各5帧官方CPU对照、取消恢复/释放，最大误差仍约2.003e-5；10npy及源码SHA验证通过，原始TF32状态恢复。正式Runtime依赖/源码导出和签名安装仍待完成。证据 spark/evidence/media/ghostv2-occlusion-fp32-policy-20261008.json。

- 2026-10-08 GhostV2可选遮挡Host合同与所有权：显式occlusion=true才要求第六canonical checkpoint绑定，严格布尔控制、固定SHA/大小，并将取消回调贯通至XSeg；构造失败逆序释放、重复close回归通过。46项本地测试exit0，18981实机两轮整套组件加载/图片推理/释放重载exit0，所有组件弱引用释放，取回两PNG SHA/解码通过。探针显式禁用TF32，正式Worker精度策略及新版Runtime导出尚待完成；自然遮挡/交叉/长时序、许可和签名安装门槛保留。证据 spark/evidence/media/ghostv2-occlusion-owner-20261008.json。

- 2026-10-08：GhostV2 官方组件流水线新增显式可选 occluder，在原始目标 crop 上推理并以目标坐标遮罩保护合成结果；默认仍为 None。遮罩形状/范围、矩阵有效性及目标像素保护测试通过，41 项回归及61618/1371完整 CUDA 视频普通/快模式通过，遮挡区约99.55–99.69% pre-encode像素原样，未选人保持；证据 `spark/evidence/media/ghostv2-occlusion-video-20261008.json`。Runtime/Host checkpoint 权限及许可尚未接入，不作已发布能力。

- 2026-10-08：新增候选 `spark/cuda_ghostv2_occlusion.py`，固定 xseg_1 大小/SHA，校验后仅解析已验证字节；封装六节点裁边改写、CUDA FP32 遮罩、取消及显式 close。两项权重负向/取消测试通过；37246 实机两轮 mask 对照、GPU边界取消恢复、弱引用释放与关闭拒绝通过，证据 `spark/evidence/media/ghostv2-occlusion-component-20261008.json`；尚未导出 Runtime、启用默认或新增 Package 权重依赖。

- 2026-10-08：XSeg 遮挡保护诊断合成改善，三模型 CUDA 转换对原 ONNX 15样本通过1e-4容差，六处非对称padding改写先经ONNX零误差验证。仅隔离原型，未新增生产依赖；自然遮挡、生命周期、许可及签名安装待验收。证据 `spark/evidence/media/ghostv2-xseg-composition-cuda-20261008.json`。

- 2026-10-08：GhostV2 两个不同身份的选人/未选人保留/完全丢失通过，但部分遮挡产生明显伪影；官方 FP32 组件基准也存在，CUDA 对官方 mixed 三帧像素一致。质量门槛明确未通过，不得把运行成功作为发布质量证据。详见 `spark/evidence/media/ghostv2-two-identities-occlusion-20261008.json`。

- 2026-10-08：GhostV2 像素修复已通过标准构建器重新导出到 r2 profile，并组装独立 r2 Runtime；两份 73 源文件清单全部验哈希，内嵌解释器两轮 CUDA 加载/推理/释放通过。当前仅未签名验收树，5595 Docker 持久双预设/重试/取消/关闭恢复通过，四输出 SHA/帧时间戳/AAC 校验通过。证据 `spark/evidence/media/ghostv2-runtime-pixel-fix-20261008.json`；不代表正式 Runtime 已更新。

- 2026-10-08：官方固定 RNG 对比发现 GhostV2 CUDA 像素量化四舍五入偏离上游截断。已按官方顺序对齐归一化/反归一化及截断；99995 实机五抽样帧逐像素等于官方 mixed 组件流程，40 项测试通过；证据 `spark/evidence/media/ghostv2-official-parity-20261008.json`。Runtime profile 需重新导出，先前 Runtime 树仍是旧版本，不得据旧证据发布。

- 2026-10-08：GhostV2 持久活动取消与任务管理器关闭/重建实机验收通过，恢复视频完整校验；非断点续帧或崩溃恢复。证据 `spark/evidence/media/ghostv2-durable-lifecycle-20261008.json`。当前通用调度计数把 HTTP 取消归到 failed；实际任务状态及资源释放正确。质量、真实用户安装及发布仍待完成。

- 2026-10-08：修复共享 VideoTaskManager 对 `source_video` 的冻结输入及重试映射；源视频不再错误套用参考素材的 2–15 秒限制（原参考素材限制保持）。GhostV2 CUDA Worker 增加持久任务 envelope、quality/fast_export、源尺寸/帧率冲突校验；54 项回归及短/16秒源视频测试通过；32852 实机双预设、Artifact、幂等、权限隔离、错误帧率拒绝、排队取消重试通过，三视频校验通过。证据 `spark/evidence/media/ghostv2-durable-tasks-20261008.json`；真实用户安装、活动任务关闭恢复及质量门槛仍保留。

- 2026-10-08：GhostV2 Worker 接受 Host 固定官方上游 ID `dimitribarbot/ghostv2`，checkpoint 仍按 canonical model ID 精确绑定；26 项合同/控制器/权重测试通过。新增 `spark/check_ghostv2_host.py` 验证真实 Host 调度及身份字段。5923实机Host图片/60帧视频通过，调度身份字段及音频包一致性通过；证据 `spark/evidence/media/ghostv2-host-20261008.json`。未签名发布，真实用户安装、持久任务及质量门槛保留。

- 2026-10-08 GhostV2标准Docker HTTP47768 exit0：修正multipart parameters/inputs JSON字符串与严格file marker解析，14合同测试通过。真实图片11.37秒/视频14.58秒返回正确MIME；取回SHA/两PNG解码及60帧25fps时间戳、AAC包与输入一致通过。401、运行请求499、active0、drain503/resume图片通过；实查禁网/只读root/capdropALL/no-new-privileges/UID1000，容器删除。仍未签名安装/认证Host/持久任务整链，HTTP取消不冒充GPU精确阶段；质量门槛保留。证据 spark/evidence/media/ghostv2-http-20261008.json。

- 2026-10-08 GhostV2正式create_adapter入口增加服务/profile/内嵌解释器/15模块来源检查，namespace全部搜索路径也须在Runtime profile内，拒绝Package遮蔽；7项控制器/factory专项通过。独立复制base+标准导出profile组装未签名Runtime，60534 exit0：内嵌Python -I经正式factory完成图片/60帧视频，取回SHA/完整解码及音频存在验证通过，stop503/start准入通过。尚非Docker HTTP/认证Host或签名安装发布。证据 spark/evidence/media/ghostv2-runtime-factory-20261008.json。

- 2026-10-08 GhostV2标准完整profile导出78888 exit0：32依赖记录/73源码，11项直接依赖精确锁检查生效。首次入口python3不存在保留启动失败，核对实际python3.12后34486 exit0：Runtime内嵌Python -I且排除开发site-packages，52模型模块来自导出profile，关键二进制依赖仅来自导出profile或既有base Runtime；两轮CUDA加载/推理/释放和取回PNG SHA/解码通过。仍为未签名profile+现有base组合，不等同新Runtime安装/发布；Worker factory/HTTP/Host、质量及Cloud容量门槛待完成。证据 spark/evidence/media/ghostv2-runtime-dependency-export-20261008.json。

- 2026-10-08 标准CUDA Runtime构建器加入GhostV2独立profile/11项精确依赖锁/成对python+sources参数与capability一致性检查，固定归档SHA、许可证及源码清单导出。83项回归通过。首次70499独立导出暴露CVLFace隐式ArcFace依赖，补齐官方源码后86852 exit0：73源码逐SHA重验，52已导入模块均来自导出profile，两轮CUDA加载/图片推理/释放通过。仍用开发解释器依赖，非依赖层完整导出或签名Runtime安装，未宣称已发布能力。证据 spark/evidence/media/ghostv2-runtime-source-export-20261008.json。

- 2026-10-08 GhostV2真实GPU取消发现资源保留：62107/91496/74400失败记录保留，诊断显示异常帧及视频flush闭包持有pipeline/参考状态。控制器清理已退出native异常帧局部引用，视频finally显式清空pending/identity/pipeline闭包；21回归通过。91556实机三种request_cancel/transport_cancel/stop在同步完成生成器forward边界触发均通过，组件弱引用释放、事件清空、锁释放、输出临时文件清空，stop/start后图片恢复SHA/解码通过。是协作式forward边界取消，非GPU内核抢占、HTTP/认证Host或长期无泄漏验收。证据 spark/evidence/media/ghostv2-worker-cancellation-20261008.json。

- 2026-10-08 GhostV2 Worker控制器完成串行执行/事件取消/stop503/start、重复409、排队499、transport取消等待底层清理后释放锁；每请求固定权重校验及组件释放，失败输出删除。20项测试通过。旧协议fixture路径导入失败保留，换当前四文件协议源码后52538 exit0：真实ModelWorker协议图片/60帧视频返回Artifact，取回SHA/PNG及MP4完整解码/音频存在通过，事件归零、stop/start通过。仍非HTTP/真实Host身份/签名Runtime，正式factory、任务envelope与upstream映射、GPU活动请求取消仍待验收。证据 spark/evidence/media/ghostv2-worker-native-20261008.json。

- 2026-10-08 GhostV2 Worker合同源码：cuda_ghostv2_contract提供精确五canonical Host绑定（拒绝缺失/重复/上游别名替代）及image_edit/video_generation multipart/严格控制解析，禁止payload路径。13合同+4checkpoint共17测试通过（非致命Metal退出警告）。该模块尚未接入Worker执行器，候选ID未发布，Host upstream映射/持久任务envelope、串行取消停止、签名Runtime代码绑定和实机Worker仍待完成；不计Host已支持。证据 spark/evidence/media/ghostv2-worker-contract-20261008.json。

- 2026-10-08 GhostV2固定checkpoint入口及所有权封装：精确五角色/文件大小/SHA256，1MiB分块取消检查，不从checkpoint导入代码；全部验证后加载，失败逆序释放全部组件，close断开pipeline。4项负向/清理测试通过，Metal atexit非致命。66894实机两轮五组件加载/推理/重复close/重载exit0，全部组件弱引用释放；取回两PNG SHA/解码通过。当前roots仍为原生fixture，正式Host checkpoint_for和Runtime源码绑定、Worker/HTTP/安装尚未完成。证据 spark/evidence/media/ghostv2-checkpoint-owner-20261008.json。

- 2026-10-08 GhostV2多脸实机发现并修复检测失踪仍生成：47388失败证实选中左脸消失后8–10帧黑区被生成脸覆盖。改为missed==0才渲染，仍保留轨迹用于关联；16865逐帧和71104间隔4均exit0，两段20帧取回SHA/完整解码通过，编码前未选中右半全像素不变，消失检测后不生成、过期不静默重绑、保留轨迹复检恢复和非法track清理通过。素材为同脸双位置，非异人交叉/部分遮挡验收。Mac worker_adapter.py:334同条件另记源码级问题，未执行Mac复现或修改已发布包。证据 spark/evidence/media/ghostv2-track-loss-20261008.json。

- 2026-10-08 GhostV2官方组件pipeline接入：新增CUDA RetinaFace/68点FAN生命周期封装、官方OpenCV对齐/Ghost遮罩；GhostIdentity按请求保存embedding/crop/68点，不共享来源状态。完整视频54618 exit0，normal14.38秒/fast6.91秒处理60帧；三输出取回SHA/完整解码/25fps逐时间验证，normal AAC包及PCM与输入相同，取消清理/恢复通过。抽帧面部表情连贯、眼细节较初版改善；仍非遮挡/多脸/身份/时序质量验收，未接正式Worker/Host、固定checkpoint绑定或签名Runtime。证据 spark/evidence/media/ghostv2-official-pipeline-20261008.json。

- 2026-10-08 GhostV2新增显式可选FP32官方GFPGAN增强组件及pipeline接入口，推理错误向上传递不静默降级；所有权由外层Worker负责。首轮35444跨运行逐像素断言因官方默认随机noise失败，保留记录；相同随机状态直接对照官方函数47966 exit0，五帧像素精确，前/后forward取消、恢复、异常传播、重复close/弱引用释放/关闭拒绝通过，关闭后Torch仍分配8519680字节。启用增强的视频56110 exit0，normal6.92秒/fast5.03秒处理60帧，取回SHA/完整解码/25fps逐时间验证通过，AAC包及PCM与输入精确一致，取消临时清理及60帧恢复通过。仍使用共享检测/几何，非完整官方68点接入、时序/身份质量、Worker/Host或签名安装验收。证据 spark/evidence/media/ghostv2-restoration-20261008.json。

- 2026-10-08 GhostV2官方组件基线：固定Release三个辅助权重共505906544字节，SHA为HTTPS实际下载观测值（上游未公布digest），非声称上游签名。官方RetinaFace/68点/Ghost遮罩/GFPGAN均直接导入；首轮21400因NumPy标量与Torch赋值兼容失败，探针仅把bbox输入转Python float列表后62955 exit0。5帧25PNG取回SHA/解码通过，无GFPGAN回退日志。官方原始生成仍有眼部伪影，增强后眼轮廓/细节改善但不能据此声称身份、表情或时序保真。尚非原始Lightning CLI/SDXL修补、完整视频、Worker/Host或签名安装；后续接入显式官方增强选项及生命周期后继续验证。证据 spark/evidence/media/ghostv2-official-components-20261008.json。

- 2026-10-08 GhostV2逐阶段质量诊断99121 exit0：5帧原始生成crop及组合图25PNG取回SHA全验。保留相同YuNet点位，精确抽取官方norm_crop_v2函数对照共享Pillow几何；FP32对mixed最大1/255，均值0.0473–0.0506/255，几何差异均值0.793–0.912/255。眼部伪影在贴回前原始crop即出现，官方OpenCV对齐+FP32同样可见，因此不能归咎于FP16或遮罩贴回；检测眼中心mask=1。仍非官方完整程序：官方RetinaFace、68点Ghost遮罩、GFPGAN增强尚未纳入对照，下一步补齐该基线，不擅自用增强掩盖未定位问题。证据 spark/evidence/media/ghostv2-geometry-diagnostic-20261008.json。

- 2026-10-08 GhostV2视频36978 exit0：normal/fast/recovery三输出完整解码均60帧、256x256、25fps，逐帧时间匹配，SHA与Spark回执一致；normal的114个AAC包及115712解码样本与输入逐字节一致（编码padding保留），其余无音频。写4帧后取消的临时清理及完整恢复通过。normal 2.739秒/fast 1.462秒仅短例计时；5时点抽帧可见眼周重影、面部偏软，质量未通过，需同输入官方完整链路对照；尚非Worker/Host或签名安装验收。证据 spark/evidence/media/ghostv2-video-native-20261008.json。

- 2026-10-08 GhostV2真实视频36978启动：固定LivePortrait官方d0前60帧运动人脸，合成AAC测试音频，覆盖batch2每帧检测保留音频、batch8间隔4无音频、写4帧后取消临时清理及60帧恢复。真实输出/帧数/音频存在验证在途，不称视频验收完成；合成音频明确不当作真实讲话。证据 spark/evidence/media/ghostv2-video-native-20261008.json。

- 2026-10-08 GhostV2图片视觉复核未见明显贴回边缘/背景破坏；新增cuda_ghostv2_video串行视频渲染，复用共享Track选择/EMA几何/1–8帧批次/检测间隔、音频auto/none/preserve及失败临时清理。控制范围核对Mac合同，velocity_smoothing保持0–1数值；6共享媒体/跟踪测试通过。新视频函数尚未真实执行，不把共享测试作为CUDA/取消/保留音频验收。证据 spark/evidence/media/ghostv2-video-implementation-20261008.json。

- 2026-10-08 GhostV2全图实机准备：新增CPU YuNet执行器复用Mac检测解码，组合真实检测/五点对齐/CUDA生成/ROI贴回，探针含原图/非方形背景/无脸拒绝。首轮Yue2开发环境缺cv2在导入前失败；现有LivePortrait官方开发环境重试8733运行中，保留旧日志。未声明正式Runtime依赖闭包或视频支持。证据 spark/evidence/media/ghostv2-full-image-native-20261008.json。

- 2026-10-08 GhostV2全图组合初版：新增cuda_ghostv2_pipeline复用共享五点对齐/ROI贴回，最大脸选择及批量检测结果处理；Mac包__init__/detector改为惰性MLX导入，独立导入阻断MLX测试通过。原几何/适配器16回归通过，Metal退出警告非失败。尚无真实检测全图实机验收；Mac Package源变更须纳入未来升版，已发布0.1.0不可覆盖。证据 spark/evidence/media/ghostv2-full-image-implementation-20261008.json。

- 2026-10-08 GhostV2核心实机14802 exit0：1/2/8帧批量11张PNG取回SHA/逐像素误差重验，当前engine摘要一致。单帧与官方mixed PNG完全一致；batch2最大2/255均值0.039/255，batch8最大1/255均值0.0404/255。计算前取消、后续恢复、重复close、关闭后拒绝调用及两模型弱引用释放通过；关闭Torch分配9568256字节，不称归零/长期无泄漏。仅重复对齐目标样例，不覆盖完整画面/视频或GPU批次中取消。证据 spark/evidence/media/ghostv2-engine-real-20261008.json。

- 2026-10-08 GhostV2复用核心cuda_ghostv2_engine.py完成初版：严格官方加载、FP32 identity/FP16 generator、BGR转换、批量生成、有限值与取消检查、close；内存语法/通道转换/非法输入检查通过。沿用Mac调用形状但不引入MLX数值实现，检测对齐贴回/视频尚未接入，新核心待单独实机复验，不复用旧探针作为验收。证据 spark/evidence/media/ghostv2-engine-20261008.json。

- 2026-10-08 GhostV2混合精度97908 exit0：身份编码保留官方FP32、生成器FP16，三轮真实CUDA输出取回SHA/有限张量/图像核验；相对官方FP32平均像素误差0.0626/255、最大1.7945/255，identity cosine1.0，暖生成约13.9ms，Torch峰值956743168字节非总统一内存。视觉未见明显损坏，仅单对齐人脸样例；采用为后续全图/视频候选，不能据此批准整体质量或安装支持。证据 spark/evidence/media/ghostv2-mixed-precision-20261008.json。

- 2026-10-08 GhostV2官方FP32 CUDA68871 exit0：两原始权重/全部源码重验，strict加载，source1→target1三轮256x256有限图像，暖生成24–25ms不含检测合成；取回PNG SHA/张量验证通过，视觉无明显空白严重损坏。重复输出不字节一致，最大0.114/255平均约0.0034/255差异，未承诺确定性/身份质量。FP16官方同路径候选63973已启动，尚未选产品精度。证据 spark/evidence/media/ghostv2-official-fp32-20261008.json。

- 2026-10-08 GhostV2两原始权重下载42801及传输98078 exit0，合计1196967612字节摘要匹配固定审计。新增官方FP32 aligned source1→target1探针：导入前逐文件源码对归档、完整权重SHA、strict state_dict，三次真实CUDA输出记录；暂复用已验证Torch开发环境，非正式Runtime。探针已启动ghostv2-official-r1.log，尚未判推理/质量通过。证据 spark/evidence/media/ghostv2-source-preparation-20261008.json。

- 2026-10-08 GhostV2启动官方CUDA基线准备：固定bc53ed086dbe8ea38e165aec7aaac90d1749a335官方源码归档SHA360153100bb7a8d2488bff6ddff164717e6a6c66ff1a6844f4b6635581818527，已提取查看生成器/CVLFace。两原始safetensors按Mac审计记录固定摘要下载42801，完成前不加载；未复制MLX转换权重冒充原始基线。图片/视频/跟踪/保留音频完整产品合同后续均需覆盖，尚无Spark推理。证据 spark/evidence/media/ghostv2-source-preparation-20261008.json。

- 2026-10-08 YuE2同产品配置官方CLI90858 exit0：未修改官方代码、3000token/32步、9文件子集生成3526976帧，与Host帧数相同；官方所有产物SHA/完整解码和generation配置核验通过。PCM24官方与PCM16 Host逐采样差异最大1 LSB、RMS0.577 LSB，落在输出量化范围，当前中文样例不支持接入引入可辨音频差异。非文件字节相等或广泛音质批准；先前中文ASR两字遗漏保留诊断。证据 spark/evidence/media/yue2-matched-official-20261008.json。

- 2026-10-08 YuE2歌词诊断2096 exit0：8音频输入摘要与回执一致，去段落标记/标点后三个英文Host模式及对应官方样例全部歌词精确；中文Host漏“晚”和末尾“来”，官方默认样例完整。ASR可误识别，尚不判音质通过或接入缺陷。已启动90858未修改官方CLI、正式9文件子集及产品3000token/32步配置对照official-off-product-r1，以区分配置差异；不以默认9000token样例替代。证据 spark/evidence/media/yue2-lyrics-diagnostic-20261008.json。

- 2026-10-08 YuE2八音频歌词诊断2096启动：四个Host模式与四个原始官方CLI样例逐一固定SHA，使用同一官方Qwen3-ASR1.7B版本重验权重且不给识别器歌词提示。用于排查内容差异，不代替听感/旋律评价，CLI与产品生成设置不同不声称严格数值对照。Cookie授权仍等待，未访问。证据 spark/evidence/media/yue2-lyrics-diagnostic-20261008.json。

- 2026-10-08 YuE2四模式Host29107 exit0：off/full/自动melody/外部ABC全部真实推理成功，四份WAV取回SHA及有限非静音48k双声道PCM16全解码通过；当前Host源码摘要一致，四次fixture身份转发和completed4/queued0/running0、取消恢复与正常停机通过。仅off有直接对照且字节精确，其余不宣称官方数值相等或旋律质量。尚需音质/歌词/ABC遵循、真实认证和签名安装。证据 spark/evidence/media/yue2-host-modes-20261008.json。

- 2026-10-08 YuE2 CUDA双分发候选已签名并独立验签：default f60d63b2bddeeff65e85d2522b296d889d005bf32bc7aa433550f8bcb59a5fbf；vae 0224b8fe2ca3df3da646b6ac91edf728b1d1340ca0ad2d1aecd1b511264eb31c。沿用原Publisher/key且精确指纹匹配，重验原始快照再由标准构建器对固定MS元数据核验；非双端完整下载。首轮非revision目录被拒后规范快照视图重试成功，历史失败保留。尚未发布/读取Cookie，CUDA Package绑定仍留空。Host29107仍运行。证据 spark/evidence/media/yue2-cuda-distributions-signed-20261008.json。

- 2026-10-08 YuE2安装身份核查发现前述分发复用结论过宽：model_installer两条路径要求manifest.model_id等于CUDA recipe，现有分发绑定MLX故不能直接安装。已从未发布CUDA候选移除错误distribution_id，准备default/vae两份CUDA模型ID专属spec（相同不可变权重/镜像），待签名发布公网验签后再填回；源码发布policy按预期拒绝。未降低安装校验，先前9文件推理证据仍有效但不代表Registry安装。证据 spark/evidence/media/yue2-distribution-identity-20261008.json。

- 2026-10-08 YuE2 CUDA Package源候选0.1.0准备完成：固定双checkpoint已发布distribution、Linux ARM64/CUDA权限、原始许可证、adapter与实测源码字节一致；要求Runtime显式yue2能力和framework-profiles-v1，当前发布Runtime不足不得先发模型。源Contract临时索引/双模型/分发policy校验通过，未构建签名制品或读取Cookie；评分及最低内存明确为估计。四模式Host29107仍在途。证据 spark/evidence/media/yue2-package-source-20261008.json。

- 2026-10-08 YuE2扩展当前Host探针：保留off对照，新增官方full/自动melody/外部ABC，逐请求摘要、PCM格式、Worker成功态、四次actor/App/session转发与调度归零校验；无直接对照的新模式比较字段为null，不伪称数值一致。内存编译通过，远端输入存在，29107已启动于yue2-host-modes-r1，Worker加载中；终态与质量仍待验收。证据 spark/evidence/media/yue2-host-modes-20261008.json。

- 2026-10-08 YuE2边界58899 exit0：1 token/1步、200 token/100步、200 token/32步恢复均生成有限非静音48k双声道PCM16，取回SHA/完整解码及当前engine摘要通过；三例close且模型弱引用释放。最低预算1856帧/0.038667秒且semantic截断，Studio歌曲合同明确允许1 token并跳过固定时长最小值，未填充或收窄参数。最高步数日志100/100通过；非最大token与最大步数组合，不代表质量批准。证据 spark/evidence/media/yue2-boundaries-20261008.json。

- 2026-10-08 YuE2原生边界探针58899已启动：正式9文件子集，依次覆盖1 token/1步、200 token/100步和32步恢复，记录失败及close/模型释放。已观察最低预算完成语义与1步声学合成，解码尚在途；不将启动当验收通过。探针内存语法检查通过，系统py_compile仅因写缓存越界失败。证据 spark/evidence/media/yue2-boundaries-20261008.json。

- 2026-10-08 YuE2仅正式分发9文件验收7979 exit0：Worker正常/取消恢复及当前Host调用均通过，三份73.479秒48k双声道PCM16 WAV取回SHA/全解码验证，与完整开发快照逐字节一致；Host98.582秒，取消3.409秒，调度completed1/queued0/running0，正常退出143无OOM。当前Host与adapter摘要一致。只证明已验文件子集足够运行，不代替Registry真实下载、用户认证、签名安装及听感质量。证据 spark/evidence/media/yue2-registry-host-20261008.json。

- 2026-10-08 YuE2当前Host31306 exit0：当前三Host源码SHA相同，真实ModelInvocation→调度→Worker成功，fixture actor/App/session/request正确传递，completed1/queued0/running0；73.479秒PCM16 WAV与直接调用逐字节一致，Host117.500秒，取消恢复/隔离/停机通过。尚非真实认证安装。已启动7979仅9个公开分发文件的Worker/Host复验yue2-registry-host-r1.log；不将开发快照通过等同正式文件集通过。证据 evidence/media/yue2-current-host-20261008.json。

- 2026-10-08 YuE2既有权重分发复用核查：标准脚本匿名验签default/vae成功Index121，两固定HF版本和本地原始文件一致；12742 Spark重验9个发布文件并构造registry-checkpoints-r1（仅hardlink已验9文件，原文件不改）。开发17文件中的README/examples/generation_config/weights_manifest等未在发布清单，后续必须使用9文件视图实推而非假定完整目录等价。Host31306仍运行；未Cookie读取、发布或真实Registry安装。证据 evidence/media/yue2-public-distribution-reuse-20261008.json。

- 2026-10-08 YuE2隔离HTTP79085 exit0：实际标准profile Runtime断网只读uid1000/capdrop/no-new-privileges，正常及恢复PCM16音频与原生桥接逐字节相同；401认证、400边界、DELETE499取消3.333秒、drain503/resume及active归零、正常SIGTERM清理退出通过，16源码SHA一致。当前Host快照验收31306已顺序启动yue2-host-r1.log，未认定Host成功；权重分发可复用Mac既有固定版本待公网验签，未签名安装/发布。证据 evidence/media/yue2-isolated-http-20261008.json。

- 2026-10-08 YuE2独立HTTP Runtime组装81303 exit0：从既有accepted核心复制独立yue2-worker-runtime-r1，合并标准38依赖profile和16源码SHA并核验，原Runtime未改。79085实际断网只读非root容器HTTP验收已启动，已完成权重检查并加载模型，yue2-worker-r1/worker.log；尚无推理/生命周期终态，不认定产品可用。证据 evidence/media/yue2-http-runtime-assembly-20261008.json。

- 2026-10-08 YuE2 stream修复完整61694 exit0：normal/真实VAE tile取消/recovery关闭分配均26,607,616字节，取消reserved暂增后恢复，三轮未再增长；两成功PCM16 WAV与修复前逐字节相同，SHA/解码通过，仍保留非零基线及短周期限制。标准依赖导出65612 exit0，八项直接依赖精确锁校验后导出38依赖+源码，不含无关Diffusers/Gradio/Qwen-TTS，67构建测试通过。尚未组装HTTP Runtime/签名安装，非全产品生命周期验收。证据 evidence/media/yue2-stream-fix-and-profile-20261008.json。

- 2026-10-08 YuE2标准Runtime构建接入：新增显式yue2 capability与成对--yue2-python/--yue2-sources，隔离服务profile映射、固定archive/graph patch双摘要、许可证/原归档/patch保留；标准_copy_yue2_sources实际导出16文件索引。原79构建/profile测试通过，新增两项后67构建测试通过无skip。只完成源码导出，依赖闭包/签名安装未做；完整模型stream候选61694仍运行，未晋级发布。证据 evidence/media/yue2-runtime-source-export-20261008.json。

- 2026-10-08 YuE2分配增长定位：92627小GEMM每新stream保留8,519,680字节，与真实请求增量一致，独立诊断清cuBLAS工作区归零。精确源码patch复用每设备warmup stream、保留原wait顺序；4877真实CUDA小模型原路径三轮持续增长，候选四轮52,505,600字节平台，logits与官方逐项精确；源码漂移/重复patch拒绝测试通过。私有clear仅诊断未入产品。完整歌曲/取消/恢复候选61694已启动于独立yue2-stream-reuse源码，尚未判真实模型稳定。证据 evidence/media/yue2-stream-retention-20261008.json。

- 2026-10-08 YuE2桥接实机87471 exit0：normal生成73.479秒PCM16 WAV，实际VAE首块后注入取消传播且无输出、模型弱引用释放，随后同进程recovery成功；取回两WAV SHA/完整PCM16解码通过。关闭后Torch分配26,607,616→35,127,296→43,646,976字节连续增长，内存门禁未通过，需查缓存/持有对象，不能把功能成功当生命周期全绿。适配器新增OOM映射resource_exhausted503和失败清理恢复，13测试通过但未实机制造OOM；HTTP/Host/签名发布仍待完成。证据 evidence/media/yue2-bridge-lifecycle-20261008.json。

- 2026-10-08 YuE2 Worker适配器初版：固定Host两模型ID/repo/revision绑定、串行原生owner、独立输出名、重复取消等待原生线程后清理文件；引擎与适配器12测试通过。真实桥接首轮因缺ai2apps导入失败未推理，改用既有Runtime实际协议模块后87471正在运行normal/真实VAE tile取消/recovery三例，日志yue2-preparation-r1/bridge-r1-retry.log；尚无结果，不认定Worker/Runtime支持完成。证据 evidence/media/yue2-adapter-implementation-20261008.json。

- 2026-10-08 YuE2自动melody规划1303 exit0：63.879秒48k双声道FLAC/156.252秒完整流程，无截断，产物SHA/全解码通过。四种官方基线full/off/自动melody/外部ABC均已有结构证据，非质量批准。新增cuda_yue2_engine桥接产品v2/3000token上限、官方原算法32默认步、PCM16 WAV和120秒界限，利用官方status逐块回调检查取消并finally close，10契约测试通过；桥接自身尚未实机验收/Worker接入，不套用CLI证据。证据 evidence/media/yue2-melody-and-bridge-20261008.json。

- 2026-10-08 YuE2外部ABC melody官方基线1997 exit0：44.799秒48k双声道FLAC/124.428秒端到端、32步BF16/FP32 VAE，无token截断；所有产物SHA/全解码通过，plan与导出score的ABC逐字节等于输入。仅保留输入不证明音频音高节奏遵循，质量未批准。官方VAE decode_tiled已有逐块on_progress且异常传播，Worker可通过该边界接入取消，不必重写数值算法。自动旋律规划样例另行启动，仍欠Worker/Host/签名发布。证据 evidence/media/yue2-official-external-abc-20261008.json。

- 2026-10-08 YuE2官方中文off模式17562 exit0：原始BF16/FP32 VAE、CFG1.01、完整32步，56.439秒音频/129.126秒端到端，无ABC/semantic截断。产物逐文件SHA、48k双声道PCM24 FLAC全解码/有限非静音通过，未判听感或歌词质量。外部ABC melody样例1997已启动，official-melody-external-r1.log；不能把在途任务认定完成。新增独立结果校验器并回验full；Worker需映射产品3000token上限及解码取消，不变更官方基线默认。证据 evidence/media/yue2-official-off-20261008.json。

- 2026-10-08 YuE2官方完整CUDA首例24347 exit0：17文件7,794,599,009字节Spark重验，独立环境官方doctor识别GB10；原始BF16 torch/CUDA graph、full规划、完整32步生成49.799秒48k双声道FLAC，端到端139.633秒，ABC/semantic均未截断。所有回执产物SHA取回重验，音频全解码有限非静音。开发环境无关依赖冲突保留，不作为正式Runtime；melody/off/外部ABC、质量、Worker WAV/生命周期/Host/签名安装发布仍待推进。证据 evidence/media/yue2-official-full-20261008.json。

- 2026-10-08 YuE2启动官方CUDA复用：固定干净源码3d21f8f5d31be867f4c3b2e6beafb0f2e52f8c10，原始3B c044757a011169583f363168348ae380946efff8及VAE152733a19ad43aa67e367f9b5503ef8075bb5126在Mac逐文件SHA及官方weights_manifest重验，合计7,794,599,009字节。传Spark独立yue2-preparation-r1，rsync34187仍运行；接收端验证器已同步，未声明Spark字节验收/推理。官方流水线覆盖规划/语义/声学/解码，先用BF16完整32步官方基线；全局后端和显存预算修改需隔离，ACE环境缺tiktoken不得视为现成环境。证据 evidence/media/yue2-source-preparation-20261008.json。

- 2026-10-08 ACE-Step停机修复Spark复验：标准导出620源码与前版相同，适配器摘要一致；两轮真实Worker/Host推理、取消恢复、drain与调度归零通过。首轮47845因--rm删除容器无法inspect；第二轮69846读取退出143/无OOM，日志Application shutdown complete，实际Runtime Uvicorn源码确认清理后重抛SIGTERM。原探针exit1保留，修正未来条件为正常终态+0/143+无OOM/error+清理日志，不冒称原探针全绿。音频取回SHA/PCM验证通过；未签名fixture不代替正式安装。证据 evidence/media/ace-step-stop-worker-20261008.json。

- 2026-10-08 ACE-Step停机恢复修复：adapter使用独立共享shield任务持有完整shutdown，取消stop等待者不再跳过环境恢复；原生release返回或抛错后finally恢复原cuBLAS配置。新增真实线程阻塞/取消等待者/重复stop/保留原配置及release异常回归，19相关测试通过，末尾保留sandbox Metal退出警告。仅本地源码修复，尚未重新导出Spark Runtime，旧GPU回执不覆盖此变更。证据 evidence/media/ace-step-stop-restoration-20261008.json。

- 2026-10-08 ACE-Step最新确定性候选歌词诊断73114 exit0：固定官方Qwen3-ASR权重重验，同一ASR处理当前Worker样本和既有官方样本；纯音乐为空，中文分别为“嗯，风轻轻吹过窗台。嗯，星火带你的肩奔跑。”和“嗯，风轻轻吹过窗台。嗯，星火带你的肩奔。”，均不匹配完整输入。取回回执对应三份音频SHA一致。官方样本后端设置早于确定性集成，不宣称全配置相同；ASR不能代替听感、不单独归因CUDA或上游缺陷，歌词质量仍未批准。证据 evidence/media/ace-step-current-lyrics-quality-20261008.json。

- 2026-10-08 ACE-Step加载状态对照42673 exit0：三轮四类模型完整state_dict摘要与planner编码均相同；确定性初始化两轮PCM精确，但三轮均不同于早期参考，未定位全部数值差异。关闭后分配68,159,488/保留675,282,944字节稳定且模型弱引用释放。seed合同不承诺任意重载跨进程字节一致，此项保留诊断、不直接判音质失败；生产构造器未改，不以两轮推断通用保证。继续以固定官方实现及歌词/音乐质量、认证Host和签名安装为验收重点。证据 evidence/media/ace-step-load-state-20261008.json。

- 2026-10-08 ACE-Step三轮重复装卸19419 exit1：各轮关闭后Torch分配68,159,488/保留675,282,944字节完全相同，四类模型弱引用均释放，三轮范围未观察增长。前两轮输出字节一致，第三轮不同，取回完整PCM重算RMSE26.715/max384 LSB；因此重新装卸确定性不判通过，后续查加载阶段状态。原探针assert失败后回执残留running，已明确记录终态exit1并修正未来失败回执写法，历史不覆盖。非零基线/三轮限制保留，不推断长期无泄漏。证据 evidence/media/ace-step-reload-memory-20261008.json。

- 2026-10-08 ACE-Step最大组合80306 exit0：120秒100步真实decoder次数准确、44.56秒完成，峰值Torch分配10,629,876,736字节；同进程后续10秒8步7.13秒完成并字节精确复现已验收参考。两WAV取回SHA/完整PCM解码/current引擎摘要通过，状态恢复通过。close后仍分配68,159,488/保留677,380,096字节，未宣称归零，需后续重复装卸检查是否稳定；Torch指标非总统一内存。仅native最大组合，不代替真实认证Host/签名安装/音乐质量。证据 evidence/media/ace-step-max-combination-20261008.json。

- 2026-10-08 ACE-Step官方公式步数边界10820 exit0：1/20/21/100实际CUDA decoder调用次数准确，观测时间步与原始公式按decoder dtype转换逐项一致，未被官方20步UI上限截断；四份10秒48k双声道PCM16取回SHA/全解码/current engine摘要通过。每次推理CPU/CUDA RNG及后端标志恢复，峰值Torch分配约10.63GB非总内存。仅边界native样例、非100种步数穷举或120秒100步最大组合；不判各步数音乐质量，默认8Worker/Host证据独立，正式安装发布仍待完成。证据 evidence/media/ace-step-official-step-bounds-20261008.json。

- 2026-10-08 ACE-Step确定性Worker集成：启动前固定cuBLAS workspace、拒绝冲突/过晚配置，正常stop恢复环境；每次串行推理隔离Torch RNG并在成功/异常恢复确定性/cuDNN标志。16测试通过。标准导出620 SHA实机一致；37329 exit0，10秒纯音乐/20秒歌词各四份初始/重复/Host WAV字节精确，完整PCM解码/current源码通过，纯音乐还精确复现独立native确定性实验；取消恢复/drain/身份调度通过。回执Host秒数包含两次直接对照，不能作为Host耗时，探针已修正后续计时。新默认8步通过；1–100完整GPU、歌词质量、真实认证和签名安装发布仍待完成。证据 evidence/media/ace-step-deterministic-worker-20261008.json。

- 2026-10-08 ACE-Step剩余差异定位：99220全Torch RNG隔离仍PCM RMSE36.53，规划编码摘要一致且CPU/CUDA状态恢复；5653在启动设CUBLAS_WORKSPACE_CONFIG=:4096:8后比较三路径，普通/全RNG仍不一致，确定性算法+cudnn固定路径两次WAV字节精确、PCM误差0。10份音频取回SHA/全解码/误差重算通过。仅原生单纯音乐样例，未定位单算子或证明跨进程配置一致；下一步Worker配置/状态恢复/歌词及步数门禁，未改变产品全局后端设置或发布。证据 evidence/media/ace-step-determinism-diagnostic-20261008.json。

- 2026-10-08 ACE-Step官方默认采样开发候选：从Mac shift3改为固定官方shift1公式，1–20步与原始分支逐项一致，21–100按同公式扩展并保留历史Mac helper；10测试通过。标准导出620实机SHA通过；38915实机Host/生命周期成功，但默认8步重复字节不一致，未晋级发布。独立PCM重复RMSE约25–26 LSB，对官方同歌词RMSE30.16/相关0.999965，远小于旧规划随机误差，但原因尚未隔离，不以相关系数判质量。21–100新公式仍欠实机完整门禁，下一步区分完整推理RNG与CUDA数值差异。证据 evidence/media/ace-step-official-schedule-20261008.json。

- 2026-10-08 ACE-Step歌词内容诊断：Qwen3-ASR官方1.7B固定权重重验，当前20秒中文歌词识别明显偏离两行输入，纯音乐识别为空。同prompt/lyrics/seed42官方默认采样基线51859 exit0，28权重文件重验、20秒48k双声道SHA通过；54394相同ASR对照中官方也未全文匹配，词句与当前不同。两例均不判歌词质量通过，不以ASR代替听感或认定单一采样因果。当前Mac来源timesteps/shift3与官方默认/shift1差异仍需官方优先评估，未擅改生产采样。证据 evidence/media/ace-step-lyrics-official-20261008.json。

- 2026-10-08 ACE-Step重复性修复：固定官方ca1e85规划器PT批量分支设置seed、单条分支遗漏；CUDA wrapper以fork_rng隔离并设置请求seed，不改原始源码，异常亦恢复状态。2测试+实机GPU13425状态恢复通过。标准构建器620源码实机摘要通过；独立Runtime Host20765 exit0，纯音乐10秒/中文歌词20秒各四次初始/相邻重复/Host WAV取回逐字节一致，48k双声道PCM16和当前源码SHA通过，取消恢复/drain/身份调度通过。同seed差异在两例消除，不代表全语料质量或跨设备确定性；签名安装发布仍待完成。证据 evidence/media/ace-step-planner-rng-20261008.json。

- 2026-10-08 ACE-Step当前Host接入：首轮36470暴露上游模型别名404，CUDA adapter仅增加既有ace-step-1.5-turbo到固定canonical ID映射，其他ID继续拒绝；20相关测试通过。16104精确输出比较失败；32112相邻直接调用诊断完成，10秒纯音乐/20秒中文歌词均48k双声道PCM16，身份/请求传递、调度completed2归零、取消恢复/drain通过。取回PCM确认直接重复RMSE6140/4358，同seed不稳定并非仅WAV头，Host一致性及质量不判通过；后续查固定官方planner/RNG。当前adapter和Host源码SHA通过。无签名安装发布；全媒体Runtime容量合同仍待Cloud。证据 evidence/media/ace-step-current-host-20261008.json。

- 2026-10-08 LivePortrait预设任务39523 exit0：Quality/Fast均经真实VideoTask生成并入库，各78帧全解码；Quality字节复现旧FP32，Fast字节精确匹配独立显式BF16，当前adapter匹配。25fps驱动请求30fps明确invalid_request失败且无Artifact，新增真实编码视频测试覆盖冲突/NaN/Inf/bool帧率，31测试通过。BF16对FP32全帧MAE0.3177仅诊断，不代替广泛质量门禁。仍fixture身份发现，真实认证/签名安装发布待完成。证据 evidence/media/liveportrait-task-presets-20261008.json。

- 2026-10-08 LivePortrait持久化生命周期29241 exit0：运行中+排队取消、管理器正常shutdown/recreate后恢复通过。独立只读数据库确认2成功/3取消；取消任务无Artifact/result.mp4/*.part，首尾视频各78帧完整解码且字节相同，当前adapter SHA匹配。取消约0.544秒；调度queued/running归零，但两个已执行中断计入failed，数据库正确cancelled，统计差异保留。首轮探针空progress异常已修正记录。仅正常管理器重启、fixture身份，非进程强杀/断电/认证API/签名安装。证据 evidence/media/liveportrait-durable-lifecycle-20261008.json。

- 2026-10-08 LivePortrait持久化任务接入修复：真实VideoTaskManager请求此前因reference_parts/preset/geometry等字段400，不能由旧multipart Host通过推断任务可用。CUDA新增严格转换，quality→FP32/fast→BF16，校验素材唯一性、预设冲突和保留驱动帧率；未知控制继续拒绝。30测试通过。最终45748 exit0，真实数据库/工作区冻结2素材、幂等提交、跨actor404、Artifact入库和调度归零通过；78帧全解码，当前adapter SHA匹配，输出字节精确复现直接Worker。首轮Host快照缺offline模块和第二轮400均记录；Mac共享adapter同类接入问题单列，未修改Mac。仍测试发现/身份，持久化取消重启、真实认证、质量及签名发布待完成。证据 evidence/media/liveportrait-durable-task-20261008.json。

- 2026-10-08 LivePortrait官方合成额外s8源图实机85718 exit0：四项Host/Worker输出字节一致，三视频各78帧完整解码，当前adapter/Host SHA、取消恢复/drain及调度completed4归零通过。对固定官方FP32，ROI MAE2.7299→2.5314、变化相关0.9862、均值0.7373 vs官方0.8187；六帧抽查转头/微笑对应，嘴眼及幅度差异仍在，不判广泛质量通过。后续验收脚本补记输入SHA和精度/控制参数，本次远端快照未改。真实认证VideoTask及签名安装发布待完成。证据 evidence/media/liveportrait-compositor-s8-host-20261008.json。

- 2026-10-08 LivePortrait官方合成标准Runtime/Host19434 exit0：44索引文件实机SHA通过，FP32预裁剪、BF16裁剪、auto视频及图片四项Host与直接Worker字节精确，三视频各78帧完整解码；crop-only与上一版字节不变。当前adapter/Host源码SHA、身份转发、调度completed4归零、取消恢复/drain通过，构建器65测试通过。s0官方FP32对照面部ROI MAE2.2929→1.9102，变化相关0.9811、均值0.2220 vs官方0.2448；仅诊断，不扩大为广泛质量通过。未签名Runtime/fixture身份，真实认证VideoTask、更多素材质量和安装发布仍待完成。证据 evidence/media/liveportrait-compositor-host-20261008.json。

- 2026-10-08 LivePortrait官方合成实现落地：共享Worker提取_paste_face钩子，Mac/v1行为不变；CUDA v2调用固定原始prepare_paste_back/paste_back并校验原始512遮罩摘要。标准Runtime导出43源码+1遮罩共44索引文件；三个旋转仿射对照逐像素精确，40测试通过含v1/v2分派。此前相关指标下降不能单独否定官方算法，本次以官方实现为正确性基线；仍需新Runtime完整视频/Host回归，不据局部测试判广泛质量或发布。证据 evidence/media/liveportrait-compositor-implementation-20261008.json。

- 2026-10-08 LivePortrait官方预处理修正标准导出/Host59625 exit0：43源码实机SHA通过，相比上版仅pipeline改变。FP32/BF16预裁剪、auto视频和图片四项Host输出与直接Worker字节精确，三视频78帧全解码；当前adapter/Host摘要、身份转发、调度completed4归零及取消恢复/drain通过。s0 ROI MAE2.2929、变化相关0.9807，源图裁剪和合成差异仍在，不扩大为质量通过。未签名Runtime、fixture身份，正式安装发布待完成。证据 evidence/media/liveportrait-preprocess-host-20261008.json。

- 2026-10-08 LivePortrait CUDA预处理正式修正：OpenCV linear缩放、CPU float32归一化、显式C-order batch副本对齐官方BCHW步长；Mac未改。前两轮98118/15780输入值虽相同但batch步长3/0造成appearance差，保留回执；31108实机五组输入张量/步长、appearance及同关键点uint8解码均逐元素精确。不能把推测的内核选择当已profile事实；34现有回归测试通过，最终布局改动以真实oracle验证。新pipeline尚未标准重导出Worker/Host或签名发布，下一步完整视频回归。证据 evidence/media/liveportrait-preprocess-fix-20261008.json。

- 2026-10-08 LivePortrait相对动作oracle89889 exit0：固定官方分支pose-friendly/all对两源三帧共6例、共同动作参数，stitch后关键点最大误差5.96e-8；当前pipeline SHA一致。首轮84602误导入保留旧源码产生常量偏差，保留失败并固定Runtime路径；上轮网络oracle也以78546/current Runtime补验5例全部精确。澄清此前直接InferenceConfig基线为pose-friendly，并非CLI默认expression-friendly，后续基线回执记录effective controls。尚未expression-friendly/归一化/完整质量或签名发布。证据 evidence/media/liveportrait-relative-oracle-20261008.json。

- 2026-10-08 LivePortrait网络oracle9605/36959 exit0：s0/s8及d0第0/30/60帧五个统一256输入，原始官方权重与safe转换在相同浮点张量下appearance、全部7项raw motion和同feature/keypoint解码逐元素精确。首轮同像素但CPU/GPU归一化差5.96e-8，导致小输出差，单列保留，不误判转换损坏。此证据排除五例原始网络转换差异，未覆盖相对动作完整链、BF16或全输入；下一步锁定同crop下relative motion及后处理。证据 evidence/media/liveportrait-network-oracle-20261008.json。

- 2026-10-08 LivePortrait预处理差异诊断：同一d0解码帧，Pillow bilinear与官方OpenCV linear像素MAE0.5968/max33；隔离单变量64064 exit0，两视频78帧/图片SHA完整解码、取消恢复/drain通过，原256图片输出字节不变。官方缩放后s0 ROI MAE2.2925→2.2971、变化相关0.9821→0.9796，剩余差异基本不变，因此不能把缩放认定为主要原因。未改生产源；下一步同一张量下网络中间值oracle，尚未质量/签名发布。证据 evidence/media/liveportrait-official-resize-20261008.json。

- 2026-10-08 LivePortrait合成单变量82878 exit0：隔离Worker用固定官方mask_template及原始prepare_paste_back/paste_back替换软椭圆合成，生产未改。两视频78帧及图片取回SHA/完整解码、取消恢复/drain通过；crop-only输出字节不变。s0手工ROI MAE2.2925→1.9462、变化均值0.1993→0.2225更接近官方0.2448，但相关0.9821→0.9341下降，记录混合结果，不判质量通过或直接晋级。后续分离同crop输入的网络/动作输出。证据 evidence/media/liveportrait-official-mask-20261008.json。

- 2026-10-08 LivePortrait额外侧向源图s8/d0：官方FP32基线99415、正式v2 Host24915、官方裁剪59940均exit0。官方/Host主视频78帧562x1000，Host四项媒体取回SHA/逐字节对照直接Worker及全解码通过；当前源码SHA、身份与调度completed4归零、取消恢复通过。官方嘴部比例0.00367不触发归一化；ffprobe缺失提示保留，独立确认d0无音轨。手工ROI MAE2.7299、变化相关0.9773、均值0.7277 vs官方0.8187；六帧抽查动作对应但嘴眼/幅度仍不同，未判质量通过。仅新增未参与调试的侧向绘画源，同一驱动；真实VideoTask/签名安装发布待完成。证据 evidence/media/liveportrait-heldout-s8-20261008.json。

- 2026-10-08 LivePortrait正式适配器支持v2 checkpoint：必须source_crop=yunet203且存在固定SHA landmark.onnx，v1仍保留旧source裁剪；stop释放关键点会话。33测试通过。Spark Host6678 exit0，预裁剪FP32/BF16、auto FP32及图片四项Host输出与直接Worker逐像素一致，三视频各78帧，取回SHA/全解码及当前adapter/Host源码摘要通过；身份转发、调度completed4归零、取消恢复/drain通过。开发v2清单补齐landmark摘要，未改旧快照。仍未真实认证VideoTask/广泛质量/签名安装发布。证据 evidence/media/liveportrait-dynamic203-host-20261008.json。

- 2026-10-08 LivePortrait动态203隔离Worker10474 exit0：标准依赖导出补齐onnxruntime1.30.0及闭包，43源码SHA一致；FP32/BF16两视频各78帧和图片取回SHA/全解码通过，字节精确复现先前固定203裁剪实验，401/取消499恢复/drain503/resume通过。构建器65回归测试通过（非203专项）；首次Worker缺ORT与导出探针源码布局失败均保留。仅动态source-image候选，未切换生产adapter，auto driving路径仍旧；Host/VideoTask、更多素材质量、签名安装发布仍待完成。证据 evidence/media/liveportrait-dynamic203-worker-20261008.json。

- 2026-10-08 LivePortrait203动态模块完成：新增liveportrait_landmark203.py，固定checkpoint SHA、BGR/检测框/有限203点检查，复用原始crop_image几何；六项输入/输出拒绝测试通过。Spark42214 exit0，六图动态crop像素与仿射矩阵逐元素精确复现上一官方203实验，未加载InsightFace模块；首轮14526源码命名空间遮蔽失败保留。标准Runtime exporter现导出43源码（新增原始crop/rprint、utils入口及动态模块），本地清单SHA匹配实机。尚未接入正式adapter或在导出Runtime Worker验收，不计签名安装/发布或额外质量通过。证据 evidence/media/liveportrait-dynamic203-20261008.json。

- 2026-10-08 LivePortrait替代关键点路径17396/70792 exit0：候选仅YuNet检测框固定1.5倍方形初始化+LivePortrait原始203点模型，未使用InsightFace权重（官方oracle仍使用）。六图SHA与前轮一致、关键点有限，尺度相对官方0.9808–1.0256；固定s0裁剪Worker两视频各78帧和图片SHA/完整解码通过，取消恢复/drain通过。手工ROI MAE2.2925、变化相关0.9821、变化均值0.1993 vs官方0.2448，仍非质量通过。203实际CPU，视频为预捕获crop，不计动态Runtime集成；后续实现动态路径并做额外姿态/遮挡验证。官方模型卡MIT及固定LICENSE已记录，发布仍需保留声明并检查精确资产；未发布。证据 evidence/media/liveportrait-yunet203-candidate-20261008.json。

- 2026-10-08 LivePortrait106裁剪诊断闭环：固定官方源码LICENSE明确InsightFace模型仅限非商业研究，未发现额外商业授权，因此106权重不纳入正式Runtime/Package；证据 liveportrait-crop-license-20261008.json。独立捕获30022/Worker98567均exit0，仅将固定s0的YuNet+106研究裁剪及仿射送入已有Worker，两视频各78帧和图片取回SHA/完整解码通过，取消恢复/401/drain503/resume通过。对官方FP32手工面部ROI MAE2.301、变化相关0.9789、变化均值0.1932 vs官方0.2448；六帧转头/微笑更接近但幅度仍有差异，不计广泛质量通过。没有动态106 Runtime集成或签名发布；继续评估具有合适资产许可的替代关键点路径。证据 evidence/media/liveportrait-yunet106-video-20261008.json。

- 2026-10-08 LivePortrait官方裁剪复用前六图几何门禁：65617 exit0证明直接五点+官方scale2.3会相对106点基线放大1.980–2.186倍，s0明显裁掉额头，因此拒绝直接加入Runtime。替代诊断94800 exit0保留YuNet检测框，再用固定官方2d106模型细化后调用原始crop_image；六图尺度倍率0.9881–1.0026，s0抽查看齐官方构图，源素材SHA跨两次一致。仍仅几何候选，未动画质量/通用场景/正式Runtime发布；新增106点依赖及分发条款需在Package发布前解决，尚未纳入生产。证据 evidence/media/liveportrait-crop-geometry-20261008.json。

- 2026-10-08 LivePortrait剩余幅度诊断：官方源图嘴部比例0.0049279<0.03，本例不触发lip normalization；相对旋转/表达/尺度/位移主公式核对一致。官方源图裁剪/对应仿射捕获40703、固定源图单变量Worker57654均exit0，视频78帧SHA/解码通过；面部ROI MAE2.9152→2.2965，时序均值当前0.1502→0.1953更接近官方0.2448，相关0.9829，仍不能当完整质量通过。已定位当前源图使用ArcFace五点模板，官方采用扩展landmark几何；固定官方crop.py原生支持5点，可在保持YuNet检测器的条件下验证复用，剩余合成mask差异亦待分离。仅固定样例实验，未硬编码到产品。证据 evidence/media/liveportrait-source-crop-ablation-20261008.json。

- 2026-10-08 LivePortrait正式裁剪合同38021 exit0：39标准导出源码下预裁剪FP32、预裁剪BF16裁剪、自动裁剪FP32及图片四项Worker/Host成功；取回三个视频各78帧及图片逐像素一致，预裁剪输出字节精确复现实验，auto输出字节精确保留旧自动流程。current adapter/Host SHA、请求身份、调度completed4归零、取消恢复及drain通过。driving_crop_mode默认pre_cropped，普通原始视频调用方必须显式auto；Mac默认不变。此为未签名Runtime/身份fixture，不代表广泛未裁剪视频质量、剩余动作幅度/源图裁剪差异、真实产品VideoTask或签名安装发布完成。证据 evidence/media/liveportrait-framing-contract-20261008.json。

- 2026-10-08 LivePortrait驱动输入合同正式实现：CUDA视频参数driving_crop_mode默认pre_cropped（已裁剪对齐的人脸驱动，原帧送网络，与官方默认一致），普通未裁剪视频显式auto保留逐帧检测/追踪/对齐；不猜测输入类型。图片编辑拒绝此视频参数，非法值400，metadata记录requested/applied。共享Mac Worker仅提取可重写_driving_crop钩子，默认行为不变；28测试通过含默认隔离、参数边界、原帧不重检测、metadata和自动路径分派。标准导出39文件实机逐SHA通过，38021正在独立Runtime进行双路径Worker/Host实机验收。尚未质量/签名安装发布。证据 evidence/media/liveportrait-framing-contract-20261008.json。

- 2026-10-08 LivePortrait驱动预处理单变量实验27520 exit0：独立实验Package仅将prepare_driving(driving_crop)改为prepare_driving(frame)，仍用固定来源、标准导出的未签名stitch修复Runtime，未修改正式源代码或Runtime。两种视频各78帧SHA/完整解码，图片/取消恢复/drain通过。对同一官方预裁剪d0素材，面部ROI时序变化相关0.5662→0.9767、MAE4.1624→2.9152，表明逐帧重新对齐是此样例的主要时序差异来源；运动变化均值仍官方0.2448 vs实验0.1502，不能把模式相关当幅度/质量通过。下一步明确区分预裁剪/普通驱动视频合同并保留自动裁剪能力，继续分离源图裁剪与动作公式差异。仅实验探针，未产品化/发布。证据 evidence/media/liveportrait-driving-ablation-20261008.json。

- 2026-10-08 LivePortrait官方stitch修复标准导出39源码逐SHA校验，相比旧导出仅CUDA pipeline变化；独立Runtime的Worker/Host86585 exit0，FP32视频、BF16裁剪视频、图片及取消/drain恢复通过。Host三个媒体取回独立逐像素一致，两视频各78帧，源码/请求身份/调度completed3归零通过。对照官方FP32手工面部ROI MAE4.3493→4.1624，但时序变化相关0.5640→0.5662基本不变；6帧放大抽查保留，不宣称质量通过，下一步独立驱动帧预处理实验。未正式签名安装发布。证据 evidence/media/liveportrait-stitch-host-20261008.json。

- 2026-10-08 LivePortrait CUDA独立override stitching，移除共享Mac公式额外减去source/source残差，按固定官方wrapper直接加预测exp与xy平移；未改Mac共享实现。Spark真实固定stitching权重+原始官方stitching方法50532 exit0，64组含identity/扰动关键点逐元素精确（max error0），原公式最大差0.150612。回执三方SHA核对当前pipeline、官方归档wrapper及无损权重通过。前两次导入src遮蔽/缺Host路径失败保留，补明确可信路径后通过；Torch12.1设备vs12.0构建范围警告记录。仅FP32局部算法oracle，未重导出Worker/全视频质量/签名发布；驱动裁剪仍待独立处理。证据 evidence/media/liveportrait-official-stitch-20261008.json。

- 2026-10-08 LivePortrait官方对照诊断：取同一s0/d0的官方FP16、补跑官方FP32（52277 exit0）及当前CUDA FP32三组78帧，全解码/官方FP32输出SHA通过。6帧面部放大抽查转头/微笑大致对应，无所抽查帧明显撕裂；固定手工ROI[220,20,430,280]官方FP16↔FP32变化相关0.9727、MAE0.9377，官方FP32↔当前FP32变化相关0.5640、MAE4.3493，排除单纯精度解释但不视为姿态精度指标。代码确认当前共享stitch减去network(source,source)，官方直接加network(source,driving)；当前驱动视频逐帧YuNet检测/平滑/对齐，官方默认不重新裁剪驱动。尚未分离两项贡献，质量不记通过；下一步CUDA独立官方stitch oracle及裁剪对照。对照图/逐帧指标 artifacts/liveportrait-official-comparison-r1；证据 evidence/media/liveportrait-official-comparison-20261008.json。

- 2026-10-08 LivePortrait官方端到端基线48096 exit0：固定官方commit9b294b3d、原始checkpoint82a4fa67及3辅助模型共8文件实机SHA通过，213官方源码/素材逐文件对照固定归档一致。未经替换的官方Pipeline默认半精度生成s0/d0共78帧，推理18.11秒；主视频600x704、拼接视频1536x512，取回SHA/字节及全帧解码复核。动画Torch CUDA，检测/106点/landmark三个ONNX会话实际CPU，已记录版本和pip freeze；不称全CUDA。首次缺Torch/tyro/ORT导入失败保留，独立环境显式依赖路径补齐。仅官方基线，尚未与现有Mac共享动作/合成CUDA路径进行质量对照；辅助InsightFace资产未纳入Package分发。证据 evidence/media/liveportrait-official-baseline-20261008.json。

- 2026-10-08 LivePortrait当前Host实机3257 exit0：ModelInvocationService/PackageModel/调度器经UDS代理使用上游KlingTeam/LivePortrait，FP32视频、BF16裁剪视频及图片编辑三例成功；本地独立逐帧解码两段各78帧，所有视频/图片像素与直接Worker一致，适配器及三份Host源码SHA匹配。actor/app/session/request-id、Worker成功记录与completed3/queued0/running0通过。仅发现/身份fixture及未签名Runtime；产品VideoTask、正式安装发布及官方端到端动作/合成质量基线尚未完成。已固定官方pipeline使用Cropper/FaceAnalysisDIY/HumanLandmark，与当前Mac共享动作/合成及YuNet路径有差别，不以此Host验收替代官方质量基线。证据 evidence/media/liveportrait-host-20261008.json。

- 2026-10-08 LivePortrait生命周期修复实机82738 exit0：FP32视频、BF16裁剪视频、FP32图片三例SHA取回校验及全帧解码通过；取消约0.106秒返回、随后图片恢复、401/drain503/resume通过，adapter SHA与本地一致。10项单测覆盖实际stop/start并发及重复ID；HTTP drain/resume不能替代该生命周期边界，未扩大声称。仍为未签名Runtime Worker，完整Host工作流、官方质量基线和发布待完成。证据 evidence/media/liveportrait-host-lifecycle-20261008.json。

- 2026-10-08 LivePortrait修复Host上游KlingTeam/LivePortrait→canonical映射、重复request ID覆盖取消event、stop后start无法恢复准入三个问题；start/stop独立生命周期锁保证原生owner退出前不重开。10项测试通过，含重复取消event保留、停止/启动并发及transport取消等待。Spark82738正在liveportrait-lifecycle-r3独立目录进行FP32/BF16视频、图片和取消恢复回归，未声明实机通过。证据 evidence/media/liveportrait-host-lifecycle-20261008.json。

- 2026-10-08 VoxCPM2官方BF16长文本29061及固定官方Qwen3-ASR内容85938均exit0：中文47.68秒/英文43.04秒音频，推理44.07/38.87秒，RTF0.924/0.903；峰值torch allocated6.49/6.36GiB，均非整机总显存。两段全文标点/大小写归一化后精确匹配，取回SHA/帧数/48kHz及内容独立复核通过，模型close完成。限两个自然段原生引擎证据，非长文Host/音色相似度/主观风格/正式签名安装发布。证据 evidence/media/voxcpm2-original-long-20261008.json。

- 2026-10-08 VoxCPM2混合Host87942 exit0：当前ModelInvocationService/PackageModel/调度器经UDS代理，4-bit→BF16→8-bit→BF16每档JSON合成及multipart参考克隆共8例；取回WAV与直接Worker对照全部逐采样一致，三份Host源码SHA核对当前checkout一致。8次actor/app/session/request-id调度参数及Worker成功记录通过，completed8/queued0/running0，容器已删除。仍为发现/身份fixture、未签名Runtime，非认证用户/签名安装发布。官方BF16中英文长文本29061正在独立目录推理。证据 evidence/media/voxcpm2-mixed-host-20261008.json。

- 2026-10-08 VoxCPM2混合HTTP Worker96943 exit0：同一隔离Worker原始BF16四例与官方基线精确，4-bit及8-bit后切回原始均与暖态对照逐采样一致；量化输出保持既有基线门限（4bit最大1LSB/RMSE0.0347，8bit精确）。取消499/恢复、drain503/resume精确、请求归零及容器删除通过。本地取回WAV独立复核，Runtime清单engine SHA匹配当前修复。完成CUDA设置泄漏修复及原生/HTTP门禁；仍未混合Host/认证用户整链、广泛音色质量、正式签名Runtime安装或发布。证据 evidence/media/voxcpm2-variant-switch-20261008.json。

- 2026-10-08 VoxCPM2量化引擎修复CUDA全局设置泄漏：正常close及构造失败均恢复原workspace、TF32、cudnn和确定性/warn-only设置，重复close幂等；33项测试通过。Spark原始→4-bit→原始92884及8-bit26871均exit0，全部设置恢复，取回两档WAV与未取消暖态对照逐采样一致；首冷输出已知11LSB漂移仍单列。标准导出44文件逐SHA通过，独立mixed Runtime保留旧制品；96943正在HTTP混合切换/取消/drain验收，未声明正式安装或发布。证据 evidence/media/voxcpm2-variant-switch-20261008.json。

- 2026-10-08 VoxCPM2同进程原始→4-bit→原始诊断86806 exit0，但质量门禁失败：量化close后CUBLAS workspace/确定性/TF32设置仍残留，BF16输出长度92160→99840。保留原始失败回执；43068正在独立目录验证恢复进程设置是否足够，未据此宣布修复或发布。证据 evidence/media/voxcpm2-variant-switch-20261008.json。

- 2026-10-08 VoxCPM2原始BF16隔离HTTP85810 exit0：独立Runtime合入44标准源码，四种输出与官方基线取回逐采样一致；401、HTTP-running取消499、暖态恢复精确、drain503/resume暖态精确、活动归零及容器删除通过。首轮继承量化探针CUBLAS_WORKSPACE_CONFIG导致长度差异，删除该额外环境后四例精确；次轮误将同进程恢复与首次冷输出比较产生已知11LSB差异，均保留。未签名Runtime/Host安装；同服务量化→原始切换可能继承CUDA全局设置，仍需进程隔离/切换验收。证据 evidence/media/voxcpm2-original-http-20261008.json。

- 2026-10-08 VoxCPM2原始BF16 Worker准备：同服务增加固定bf16身份与官方revision，上游别名沿既有映射；SpeechEngine按variant独立选择官方原始引擎，单测证明不会落入Mac量化loader。标准Runtime exporter加入原始engine及权重锁；82项适配器/构建器测试通过。Spark独立标准源码导出44文件逐SHA通过；初次导入缺ACE依赖锁的失败保留并补齐输入后恢复，未覆盖旧Runtime。尚未BF16 HTTP/Host推理、完整Runtime签名安装或发布。证据 evidence/media/voxcpm2-original-worker-preparation-20261008.json。

- 2026-10-08 VoxCPM2新增独立原始官方引擎，逐文件锁验证、官方from_pretrained、本地离线入口、无Mac padding转换；保留请求前向检查与输出独占/失败清理/资源释放。实机25272 exit0，四例PCM与官方基线逐采样一致；第3次真实forward hook取消清除partial，恢复与未取消暖态对照逐采样一致，close清模型与hooks。首次输出与未取消重复输出均存在相同最大11LSB/RMSE1.037漂移，初两轮严格失败保留；不是取消特有差异，不宣称冷暖完全确定性。取回WAV独立对照通过。尚未Worker/Host或签名Runtime接入。证据 evidence/media/voxcpm2-original-engine-20261008.json。

- 2026-10-08 VoxCPM2官方原始权重四例内容回转录18537 exit0：固定官方Qwen3-ASR1.7B@7278e1e7逐音频SHA核对，中英文/克隆/风格四例标点大小写归一化后全部匹配正文，style指令未被读出；本地独立重算匹配与WAV SHA通过。只证明短例内容，不证明音色相似度/自然度/风格遵从。代码核对确认当前量化loader修改VAE padding以复现Mac，官方原始Worker须单独沿用未经该修改的官方加载入口。证据 evidence/media/voxcpm2-official-content-20261008.json。

- 2026-10-08 VoxCPM2原始官方基线推进：匿名固定openbmb/VoxCPM2@32279effe8c19989596f05d353d1447f51d9e915，8文件4,960,730,347字节完整哈希/上游LFS SHA通过；传Spark后再次逐文件哈希，官方源码逐.py与已锁归档f0c787f0匹配。未经修改VoxCPM.from_pretrained本地离线入口96066 exit0，官方BF16主模型/FP32 VAE，中英文、reference克隆、style四例生成48kHz有限音频，2.38–3.09秒，模型加载7.16秒，GPU峰值allocated最高5,919,793,152字节。取回四WAV独立SHA/帧数/采样率验证。未使用Mac仿射解包器；这是官方原始权重基线，不是内容、音色质量或Worker/Host安装发布通过。证据 evidence/media/voxcpm2-official-baseline-20261008.json。

- 2026-10-08 VoxCPM2 Host18253 exit0：4-bit/8-bit各自JSON合成与multipart参考音频克隆四例全部成功，经当前ModelInvocationService/调度器/UDS代理；Host音频与对应直接Worker PCM差异均在1LSB、RMSE<0.1LSB门限内，请求ID在Worker记录成功，调度completed4/queued0/running0。两档取消恢复、drain/resume亦通过；本地取回核对adapter与三份Host源码SHA。仍为既有量化checkpoint、发现/身份fixture，未完成原始官方权重质量基线或签名安装。证据 evidence/media/voxcpm2-host-20261008.json。

- 2026-10-08 VoxCPM2 Host身份合同修复：Host代理发送上游ID而适配器仅接受canonical，现将两档固定mlx-community/VoxCPM2-4bit/8bit映射到对应canonical，未知上游404及固定checkpoint revision校验保留。14项测试通过。Spark 18253正在新voxcpm2-host-r1目录进行两档JSON TTS/参考音频multipart Host验收，尚未记实机通过。此为既有量化模型调用合同，不替代原始官方checkpoint质量基线或签名安装。证据 evidence/media/voxcpm2-host-20261008.json。

- 2026-10-08 SenseVoice OOM错误合同修复：识别torch.OutOfMemoryError及实际CUDA13 AcceleratorError精确OOM前缀，持有请求锁清空模型/VAD引用和缓存后返回503 resource_exhausted；不自动重试，499取消与其他错误不重分类。12项测试通过（分配器OOM、AcceleratorError OOM、非OOM拒绝重分类及下一请求恢复）；Spark正常中英文/长音频/静音/取消恢复/Host整链83867 exit0，源码SHA核对、身份与调度归零通过。错误路径为注入测试，未故意耗尽设备内存，首次真实OOM根因及真实OOM恢复仍未验证。证据 evidence/media/sensevoice-oom-handling-20261008.json。

- 2026-10-08 SenseVoice Host调用4667 exit0：当前ModelInvocationService/调度器/UDS代理到隔离CUDA Worker成功，完整Host结果与直接Worker结果取回逐对象一致，actor/app/session/request-id转发、请求成功记录、调度queued/running归零通过；三份Host源码SHA与当前本地一致。首轮67953在AutoModel加载GPU时CUDA OOM，保留日志，重跑成功但原因未确定；结束时114Gi可用且无GPU计算进程，不声明OOM已修复。仍为发现/身份fixture，非认证用户整链或签名安装。证据 evidence/media/sensevoice-host-20261008.json。

- 2026-10-08 SenseVoice生命周期缺口修复：stop先关闭准入并取消活动/排队请求，start/stop以独立生命周期锁串行；重复request ID在覆盖取消event前409拒绝。8项测试通过，含原event保留、排队取消、stop503及start恢复。Spark全新隔离目录实机64416 exit0，中英文5例、47秒8段长音频、长静音、取消后恢复、drain503/resume及活动请求归零通过，adapter SHA取回核对一致。仍是开发Runtime fixture，非正式Host/签名安装发布。证据 evidence/media/sensevoice-lifecycle-20261008.json。

- 2026-10-08 详细转录长音频签名源码压力验收5267 exit0：质量档处理180秒重复双声线音频耗时67.81秒，16段474词，五个36秒周期均覆盖、全部词时间边界与文本覆盖通过；排除69边界/静音词后，按全局标签置换405/405内部词符合已知声源。取回独立复核上述指标及13个签名源码SHA。活动请求事件清空、stop503和start准入恢复通过，结束后GPU进程查询为空。此为合成重复素材/原生适配器压力，非真实会议DER/准确率、长音频Host或正式签名Runtime安装。证据 evidence/media/detailed-transcription-long-audio-20261008.json。

- 2026-10-08 详细转录1.7B质量档签名代码实机：Spark先验签后解包0.1.0候选，13源码SHA与签名来源清单一致；官方Qwen/NeMo基线推理55.73秒，Studio→Host→隔离Worker重跑71007 exit0耗时54.38秒（36秒合成输入，4段94词）。取回独立对照原文/所有时间及speaker字段精确一致，仅官方基线开启而Studio合同关闭的speech_rate字段按选项区分。401/403、请求身份转发、调度/活动请求归零及容器删除通过。保留基线缺阶段路径、误用compact段数、语速选项比较三项探针失败；非真实会议质量/签名Runtime安装或发布。生产Runtime上限匿名重查仍4GiB。证据 evidence/media/detailed-transcription-package-quality-20261008.json。

- 2026-10-08 新增 packages/ai2apps-model-detailed-transcription-cuda 正式源码候选0.1.0：四个模型绑定已发布distribution，保留原始NVIDIA许可/下载同意，CUDA平台及双阶段Runtime能力依赖，13个源码文件记录逐SHA来源；未改旧Runtime能力声明。标准签名构建成功，制品115075字节SHA256 4547363ea6ebe7f2319ead55bc7f05be0970792e3c20052a7a5bef54fc24566f，独立验签、源码一致性和无原生/权重载荷检查通过，27项adapter/engine/process测试通过（Mac进程退出附带Metal环境警告）。模型卡内存/评分明确为估算；仅短合成样本冷启动计时。尚未真实Package审计安装/发布，需先完成并发布具备detailed-transcription能力的Runtime，不能以未签名Runtime fixture替代。证据 evidence/media/detailed-transcription-package-candidate-20261008.json。

- 2026-10-08 用户明确授权四项distribution的Dev Cookie后，标准脚本确认既有Publisher/key有效且无重复提交，逐项提交、审核、发布完成；Index 118–121。四项均通过无Cookie Local trust公网回读，签名Index 121、manifest摘要及envelope精确JSON一致。共27文件/8,894,997,200字节/1063pieces；本批Cookie授权已消耗完毕。仅完成权重分发，详细转录Runtime/模型Package签名安装、认证用户整链及广泛准确率验收仍待完成。证据 evidence/media/detailed-transcription-distributions-publication-20261008.json。

- 2026-10-08 详细转录四组checkpoint分发标准构建15233 exit0，既有Publisher精确Keychain记录派生指纹匹配，四envelope独立验签通过：27文件/8,894,997,200字节/1063pieces，含原始Qwen0.6B/1.7B/aligner和Sortformer固定双源。均未Registry发布；Installation查询exit1要求active user session，已发本批四个精确distribution ID的Dev --browser-live Cookie授权请求，尚未读取Cookie。摘要和receipt在 evidence/media/detailed-transcription-distributions-signed-20261008.json。

- 2026-10-08 Sortformer镜像全量回读33868 exit0：固定MS提交38b9adca四文件匿名下载SHA/size全部匹配，原始471,367,680字节nemo耗时243.40秒，LICENSE/NOTICE/README亦验证；生成真实双源固定版本distribution spec，未替代官方权重。四组详细转录distribution标准签名15233已启动，使用既有Publisher精确Keychain记录，无Cookie读取/Registry发布。证据 evidence/media/detailed-sortformer-mirror-verification-20261008.json。

- 2026-10-08 正式checkpoint目录传参实机84668 exit0：Studio经Host到隔离Worker成功从snapshot目录解析固定.nemo，36.72秒；取回后完整result与上一点词修复候选逐对象相同。13项控制层测试通过。镜像四文件已上传固定提交38b9adca，匿名全量回读33868仍运行，不能先记下载校验通过；尚未Registry distribution签名/发布或真实Package安装。证据 evidence/media/detailed-transcription-checkpoint-directory-20261008.json。

- 2026-10-08 Sortformer镜像：公开搜索15仓库及两个固定候选均未发现相同原始NeMo字节。按原始NVIDIA许可/署名准备4文件；首次创建上传被自动审批拒绝，随后用户明确批准确切目的地/载荷，59529 exit0创建并上传ai2apps/diar_streaming_sortformer_4spk-v2.1，固定提交38b9adca95005161033e9de177096b21a850b0e5，匿名全量回读33868进行中。另修复正式Host传checkpoint目录而NeMo要求archive文件的路径合同：目录内解析固定nemo文件，缺失503；13项控制层测试通过，尚未该增量安装实机验收。证据 evidence/media/detailed-sortformer-mirror-publication-20261008.json。

- 2026-10-08 详细转录发布准备：按发布手册先准备checkpoint distribution，不把未发布占位ID写入service。固定Qwen compact/quality/aligner官方ModelScope提交4ce9cc72/a04930db/cf1c5016，26文件元数据与HF锁一致；标准builder有界字节验证37230 exit0，重新读取8,423,629,520字节并生成1006全局pieces，全部文件SHA匹配，Safetensors头确认BF16。新增三个独立distribution spec，尚未签名/发布。Sortformer同名官方MS仓库404，镜像/原NVIDIA许可分发待解决，不伪造源。证据 evidence/media/detailed-transcription-distribution-sources-20261008.json 与 detailed-transcription-distribution-bytes-20261008.json。

- 2026-10-08 点词归属修复实机36443 exit0，Studio转录36.93秒。独立逐字段审计确认仅6.09/25.06秒两个零时长词speaker_1→speaker_0，其余全部文本、时间戳及segment/word字段不变；已知合成声音区域内部84词误归属2→0，另12边界/静音词排除。21项测试通过；不等于真实会议DER/准确率或签名安装发布。证据 evidence/media/detailed-transcription-point-speakers-20261008.json。

- 2026-10-08 详细转录质量诊断发现两个官方零时长词（6.09/25.06秒）错误继承整段多数speaker，而该时间点位于官方speaker_0区间。共享assign_speakers新增可选point_word_speakers，CUDA开启：仅唯一包含该点的说话人可覆盖，半开区间处理边界，歧义维持既有fallback；不伪造时长，Mac默认不变。21项测试通过；Studio实机36443运行中，尚未计修复验收完成。修复前已知合成声音区域内部84词中2词误归属，排除12边界/静音词；不是DER。证据 evidence/media/detailed-transcription-point-speakers-20261008.json。

- 2026-10-08 Studio组合76260 exit0：先建立相同meeting-energy VAD的官方阶段基线（96词，37.18秒），再完整重跑Studio broker→音频归一化→模型选择→Host调度/代理→隔离CUDA Worker（37.77秒）。文本、全部segment及词时间戳取回独立对照完全一致；未声明能力403、双speaker/词覆盖、服务器生成request/session身份、Worker成功记录和调度归零通过。前两轮失败保留；不同VAD分段造成的识别差异仍需质量评估，不能用一致性替代准确率。挂载、发现、principal为fixture，无真实用户会话API、签名安装/发布声明。证据 evidence/media/detailed-transcription-studio-20261008.json。

- 2026-10-08 Studio详细转录组合验收：首次4226因探针动态加载子模块触发循环导入而失败，改为完整当前Studio源码正常导入。90574真实调用完成，挂载能力403拒绝、音频归一化、模型选择及调度释放已有回执，但将默认meeting-energy VAD输出与none基线比较的断言失败；保留两次失败，不计整体验收通过。76260串行建立相同VAD设置的官方阶段组合基线并复跑Studio探针，避免把不同输入分段差异误判为CUDA实现错误。证据 evidence/media/detailed-transcription-studio-20261008.json。

- 2026-10-08 Host调用71207 exit0：当前ModelInvocationService、scheduler及Supervisor代理经真实Docker Worker完成36秒双声线转录，38.42秒，文本和全部segment/词时间戳与保留基线一致。固定官方ID映射实机生效；actor/app/session/request-id传递匹配，Worker请求记录succeeded；调度completed1/queued0/running0，容器清理确认。回执取回独立复核通过。模型发现与身份仍为fixture，无用户会话Studio整链、签名安装/发布或广泛质量声明。证据 evidence/media/detailed-transcription-host-invocation-20261008.json。

- 2026-10-08 详细转录Host集成发现并修复ID合同缺口：Host multipart代理将内部ID转为官方upstream_id，CUDA适配器仅接受canonical导致调用失败；现仅映射固定compact/quality官方ASR ID，内部helper和未知ID仍404，checkpoint版本校验保留。12项控制层测试通过。真实Host调用71207启动，覆盖当前ModelInvocationService/调度器/Supervisor代理及actor/app/session/request-id；仍未计实机通过。证据 evidence/media/detailed-transcription-host-invocation-20261008.json。

- 2026-10-08 详细转录标准Docker HTTP验收59797 exit0：内嵌Runtime+正式工厂经真实multipart上传36秒双声线音频，文本及全部segment/词时间戳与engine-r2一致，36.66秒。未认证401、运行请求取消499、active_requests归零、drain503及resume后完整恢复结果一致；容器清理确认。网络none、只读根、cap-drop ALL、no-new-privileges、UID1000均实查。取回结果独立复核通过。仍是未签名开发fixture，不等于用户会话Host整链/安装发布或广泛质量；取消观测为HTTP running，精确GPU阶段另有证据。证据 evidence/media/detailed-transcription-http-20261008.json。

- 2026-10-08 完整开发Runtime链路72949 exit0：独立复制既有Runtime并合并标准导出层，内嵌Python -I经正式stage_launcher执行Qwen/Sortformer，结果与官方阶段基线对象精确一致（29.11/6.55秒）。正式create_adapter组合验收77986 exit0，36秒双声线输入耗时36.43秒，文本/全部segment及94词时间戳与engine-r2一致；events清空、stop503、start准入恢复通过。首轮工厂探针漏加正式启动器提供的core路径而NumPy导入失败，修正探针后重跑，未改生产算法。独立回执复核通过；仍是未签名开发副本，非HTTP/Host整链、安装发布或广泛质量。证据 evidence/media/detailed-transcription-runtime-tree-20261008.json。

- 2026-10-08 导出层真实推理60652 exit0：-I -S隔离下Qwen中文文本/词时间及Sortformer双声线分段与原官方结果对象完全一致，取回后独立逐对象复核；含冷进程耗时29.64/6.34秒。证明标准导出依赖可推理，仍不等于完整Runtime stage launcher链路、签名安装或生产Host通过。证据 evidence/media/detailed-transcription-export-inference-20261008.json。

- 2026-10-08 导出层实际推理60652启动：Python -I -S只加入标准导出的Qwen/NeMo层与固定核心，执行导出的stage入口，逐例比较中文文本/词时间与双声线分段的原始官方基线。当前运行中，不计推理通过；仍不是完整Runtime、stage launcher整链或签名安装。证据 evidence/media/detailed-transcription-export-inference-20261008.json。

- 2026-10-08 标准双依赖导出81998 exit0（290分发条目），强化导入64690 exit0：Python -I -S禁用site初始化，仅显式导出profile与既有固定核心，Qwen/ForcedAligner及NeMo Sortformer类导入通过；独立检查sys.path无开发Qwen/NeMo或Host venv site。79项构建器/配置测试通过。仍是依赖层开发导出，尚无导出层实际推理、完整Runtime包/签名/安装或发布。证据 evidence/media/detailed-transcription-runtime-export-20261008.json。

- 2026-10-08 标准CUDA Runtime构建器加入详细转录双层导出：固定Qwen100/NeMo190完整依赖锁逐版本验证，使用既有_copy_framework/清单路径导出，两层成功后才写stage/profile/entrypoint映射，保持主service profile；capability需成对显式输入，当前发布清单未新增能力。79项构建器/配置测试通过。独立目录runtime-profile-export-r1真实导出81998运行中，不覆盖已有Runtime，不是包构建/签名或安装通过。证据 evidence/media/detailed-transcription-runtime-export-20261008.json。

- 2026-10-08 详细转录Runtime阶段绑定源码完成：framework-profiles/v1增加可选service/stage依赖层和entrypoint解析，均验证Runtime路径/符号链接边界；stage_launcher强制python -I，仅运行Runtime声明入口。适配器create_adapter通过执行Runtime定位两个必需阶段，不接受开发venv或payload目录。31项组合回归及新增工厂测试通过，最终19项专项通过，含真实隔离子进程抵御PYTHONPATH干扰。尚未导出依赖层、写构建元数据、构建/签名/安装Runtime；不能声明发布可用。证据 evidence/media/detailed-transcription-runtime-stages-20261008.json。

- 2026-10-08 九格式官方ASR/对齐11905 exit1（严格文本比较）：9例均词覆盖及时间结构通过，8例逐字匹配；MP3仅将nine thirty转为9:30，完整原文人工复核语义一致。保留失败断言及原始回执，不重写输出、不把8/9改称逐字全过；另存semantic-review。耗时32.43秒含单次冷加载。仅短英文样例，不替代广泛质量或认证HTTP/Host。证据 evidence/media/detailed-transcription-nine-formats-20261008.json。

- 2026-10-08 九格式识别内容验收11905启动：复用Spark已验证共享Host解码输出及逐SHA，官方Qwen compact/ForcedAligner一次加载处理9例，逐例检查参考文本、词覆盖和有限时间边界。当前运行中，尚未计通过；不替代认证Host/HTTP或广泛质量。证据 evidence/media/detailed-transcription-nine-formats-20261008.json。另确认签名Runtime现有framework profiles按service选择单层，详细转录双阶段依赖仍需标准机制接入，未用开发venv冒充发布Runtime。

- 2026-10-08 详细转录Host接入缺口修复：Studio原写死MLX profile ID，现按compact/quality选择已就绪的既有Mac或CUDA provider，并检查内部checkpoint；preferred profile同样支持CUDA，保留同时就绪时现有Mac优先顺序。50项Studio测试通过。确认九格式由Host既有PyAV解码，未重复Worker解码器；Spark共享源码9格式转16kHz单声道PCM16、损坏输入拒绝及时长限制通过。仍非9格式识别质量/认证Host整链，解码to_thread取消也未宣称受模型进程取消覆盖。证据 evidence/media/detailed-transcription-host-input-20261008.json。

- 2026-10-08 详细转录原生Worker控制层65426 exit0：真实ModelWorkerContext/Request调用36秒样例，输出文本/全部segment和词时间戳与engine-r2精确一致；事件清空、stop503拒绝、start准入恢复通过，耗时37.98秒含冷加载。实际候选SHA2e7e09bf已记录；输入类型校验后续增量17项单测通过。仍非HTTP/Host、多格式解码或签名安装通过。证据 evidence/media/detailed-transcription-adapter-20261008.json。

- 2026-10-08 详细转录Worker控制层cuda_detailed_adapter.py实现固定checkpoint校验、串行执行、重复409、停止503、活动/排队取消499、stop等待清理与start恢复；transport任务取消亦等待底层线程回收后释放锁。17项专项测试通过，参数错误提前拒绝。原生ModelWorkerContext/Request真实CUDA验收65426运行中；该候选仅早于最后输入类型校验，校验增量单测通过。尚需9格式解码、签名Runtime解释器绑定、HTTP/Host及安装发布；证据 evidence/media/detailed-transcription-adapter-20261008.json。

- 2026-10-08 词覆盖修复后完整组合引擎64280 exit0：36秒样例输出94词，两个片段规范化文本与词序列均完整一致，四个官方零时长点保留并计数，双speaker/时间界限/语速结构通过，含冷加载37.48秒。10项测试通过。此证明输出不再丢词，不等于人工标注对齐准确性或广泛质量；Worker/Host/签名发布仍待做。证据 evidence/media/detailed-transcription-word-coverage-20261008.json。

- 2026-10-08 词覆盖根因确认：原始官方Qwen两段75/19词均完整，四个the/the/a/the时间点相等（1.12/6.08/21.20及第二段1.36秒）；共享clip_segments删掉了这些词。新增可选preserve_point_words保留界内原始点，CUDA开启，Mac默认行为不变；不伪造时长、仍删除界外区间。10项测试通过，含固定官方输出回放及边界/默认行为回归。完整实机64280运行中。共享Mac逻辑风险已记录，尚未测Mac实际影响；证据 evidence/media/detailed-transcription-word-coverage-20261008.json。

- 2026-10-08 组合引擎34881 exit0，36秒合成双声线一次Qwen批量+全段Sortformer共37.06秒（含冷启动），产品schema/2段时间轴/双speaker/语速结构通过。但独立检查发现两段文本75/19词而保留词时间戳72/18，规范化文本覆盖均不一致，完整词级质量门禁失败。需保留原始官方阶段输出区分官方对齐缺词与共享clip_segments删除；不能按Mac裁剪逻辑判定正确。证据 evidence/media/detailed-transcription-engine-20261008.json；尚未Worker/Host/发布。

- 2026-10-08 详细转录新增cuda_detailed_engine.py组合引擎：复用现有VAD/30秒分段、时间轴裁剪、schema、全局speaker分配与语速逻辑；Qwen一次进程加载批量识别/对齐，Sortformer处理完整音频。支持compact/quality选择、word/segment、可选diarization及明确neutral兼容策略；8项专项测试通过。输入边界目前16kHz单声道PCM16，9格式Worker解码待接。实机组合34881运行中，非HTTP/Host/签名安装通过。证据 evidence/media/detailed-transcription-engine-20261008.json。

- 2026-10-08 Sortformer GPU阶段取消恢复40811 exit0：首次实际子模块计算后0.215秒取消，PID与临时目录回收；新进程双声线36秒分段与官方基线完全一致。首轮14406在已取消后因探针命令行变量覆盖而exit1，保留原回执并记录终态，修复后完整重跑。Qwen/Sortformer阶段分别已有取消恢复证据，完整Worker/Host准入、排空与签名安装仍未完成。证据 evidence/media/detailed-transcription-sortformer-cancel-20261008.json。

- 2026-10-08 详细转录Qwen真实GPU取消恢复26931 exit0：首次实际模型调用后0.215秒取消，子进程与临时目录回收；新进程中文识别及逐词时间戳与官方基线完全一致。首轮观测失败保留。此为Qwen阶段生命周期，尚不覆盖Sortformer取消、完整Worker准入/drain或Host/签名安装。回执 artifacts/detailed-transcription-preparation/gpu-cancel-r2/receipt.json。

- 2026-10-08 详细转录GPU取消首轮99153 exit1：顶层forward观测未触发，官方源码1353行实际转至self.thinker.generate；保留失败，不计通过。改为首次实际子模块调用一次性观测，r2/26931确认进入计算后0.215秒取消并回收PID和临时目录，中文恢复对照仍运行。证据 evidence/media/detailed-transcription-gpu-cancel-20261008.json。

- 2026-10-08 详细转录真实GPU取消探针99153已启动：通过官方Qwen首个forward pre-hook原子记录阶段，确认实际进入模型计算后取消进程组，验证PID消失/临时目录回收，再用中文短句恢复并对照官方输出。探针尚未完成，不计GPU生命周期通过。4项既有进程测试重跑通过；仅内部观测增加，不改精度、权重或推理参数。

- 2026-10-08 详细转录隔离阶段11929 exit0：Qwen中文文本/逐词时间与官方compact基线完全一致，Sortformer双声线分段与固定官方基线一致。进程及冷加载总耗时29.00/6.54秒，不能当稳态推理速度；尚未组合为完整产品Worker，真实GPU取消恢复待做。回执 artifacts/detailed-transcription-preparation/isolated-stages-r1/receipt.json。

- 2026-10-08 详细转录新增官方CUDA阶段入口cuda_detailed_stage.py及协调器cuda_detailed_process.py：Qwen BF16和NeMo FP32分开解释器运行，取消终止并等待进程组，临时目录回收，结果原子写入。4项真实子进程测试通过（成功/失败清理、活动取消回收、预取消不启动）；实机阶段输出对照11929运行中。尚未完成产品schema/Worker/Host、Runtime导出或签名安装。证据 evidence/media/detailed-transcription-process-20261008.json。

- 2026-10-08 Sortformer官方NeMo2.6/v2.1严格加载及36秒合成双声线交替实测15784 exit0：未关闭strict，FP32官方默认，固定模型卡streaming参数；0.660秒推理、峰值963,069,952字节，四段主要speaker为0/1/0/1。独立核验音频SHA/16kHz/36秒及[1,450,4]概率有限且在[0,1]。仅合成声线一致性诊断，非真实会议DER/重叠说话质量；集成Worker、压缩格式和生命周期/签名安装待做。证据 evidence/media/detailed-transcription-sortformer-official-20261008.json。

- 2026-10-08 官方Qwen ASR→ForcedAligner联合实测compact53352、quality66014均exit0：两档各自中英文短句识别内容及词时间戳结构通过，未给ASR注入参考文本。0.6B两例1.144/0.288秒、峰值约3.50GB；1.7B两例1.362/0.491秒、峰值约6.01GB。均官方BF16，非Mac数值对齐；不代表长音频、多语言、人工时间标注准确性、说话人分离、集成Worker或签名安装通过。回执及限制见 evidence/media/detailed-transcription-asr-official-20261008.json。AGENTS明确不同CUDA精度/内核按官方质量、性能和内存证据选择，不设通用逐数值一致要求。

- 2026-10-08 Base四场景3683 exit0：布局/文字/风景/人像官方BF16与候选适配器逐RGB一致；取回四适配器图片独立解码/尺寸/摘要核验，结合既有目视检查四例通过，仅限所列样例，非完整质量/签名安装/发布。NeMo2.6环境31460 exit0、ASR extras递归依赖闭包6586 exit0（190分发包）；Sortformer尚未加载推理，ffmpeg PATH警告及Qwen/NeMo依赖隔离需求保留。官方compact ASR→对齐联合53352已启动，未计通过。

- 2026-10-08 Base官方四场景视觉检查完成：layout/text/landscape/portrait均符合预声明标准，适配器对照3683仍运行，不计整个质量门禁完成。NeMo2.6固定归档4d313cf5/SHA0d95a5cd已准备，要求transformers4.53.x，与官方Qwen4.57.6需环境/进程隔离。独立环境首试56785因官方更名Speech导致归档目录假设错误失败，保留日志与回执，修正路径后同环境续装31460运行中；未改官方源码，未宣布Sortformer推理通过。证据 detailed-transcription-nemo-environment-20261008.json及Base visual-review.json。

- 2026-10-08 官方ASR→ForcedAligner联合探针已编译并同步：compact/quality分别固定原始checkpoint、BF16，不把预期文本传入ASR，实际识别后官方对齐，保存文本/全部时间戳并检查两项短句内容和结构。尚未运行；Quality1.7B原始7278e1e7权重下载58145运行中。Base四场景3683已进入official:layout，未完成；保持单GPU。

- 2026-10-08 Qwen Edit共享适配器回归71440 exit0：512 PNG/JPEG/WebP及1–3参考图协议、0/4参考拒绝、生成拒绝、取消恢复/drain/resume通过，独立解码摘要确认，三输出目视均绿色茶壶保留桌面蓝背景；参考是同一图不同编码，不算多源语义验收。ForcedAligner官方英中BF16基线11626 exit0：17英文词/21汉字时间戳结构与文本覆盖通过，推理1.058/0.053秒、峰值约1.93GB；非人工标注准确性/ASR/完整详细转录，释放后进程内仍9.57MB分配已记录。原始ASR/Sortformer传输16724及Spark全哈希78393均exit0。证据 detailed-transcription-aligner-official-20261008.json及shared-image-lifecycle-regression-20261008.json。随后顺序启动Base四场景官方/适配器对照3683，尚在运行，未发布。

- 2026-10-08 ForcedAligner官方英中基线脚本已编译并同步，固定已有两WAV摘要/供应文本，直接官方BF16调用，保存逐词时间戳并检查文本覆盖/有序/有限/音频边界（官方80ms量化）；仅结构验证，不计人工标注时间戳准确性或完整详细转录。尚未运行，等待唯一GPU任务Qwen Edit71440结束。

- 2026-10-08 详细转录官方Qwen独立开发环境95997 exit0：qwen-asr0.0.6/transformers4.57.6/accelerate1.12.0/nagisa0.2.11/soynlp0.0.493/tokenizers0.22.2，复用固定Torch2.10cu130，官方ASR/ForcedAligner类导入成功。标准构建器依赖闭包13120 exit0，100分发包精确锁；首次检查缺仓库相对ACE锁，补原始目录后通过。开发pth可见但未使用的Diffusers/HF Hub冲突已记录，不能称全环境pip check通过；未导出Runtime/未GPU对齐推理。证据 evidence/media/detailed-transcription-qwen-environment-20261008.json。Qwen Edit71440仍在第三组回归。

- 2026-10-08 Base多场景探针完善失败留痕：记录运行阶段、未捕获推理错误、Torch/Diffusers版本和源码摘要，预声明物体数量/空间顺序、文字内容与人像风景检查标准；数值比较通过后仍保持visual_review pending。脚本编译并同步完成，未启动；当前唯一GPU任务Qwen Edit71440仍活跃。

- 2026-10-08 Z-Image Base真实Host调用/调度/隔离Worker验收69110 exit0：1024 PNG/JPEG/WebP完整解码，PNG与固定官方negative基线RGB精确；取消恢复、drain拒绝/resume生成通过，5完成/2预期失败、运行排队0、计算槽位归还。仍为fixture发现，不含产品API认证或签名安装；原始receipt顶层HTTP scope标签由嵌套host_bridge及证据明确实际Host范围。证据 evidence/media/z-image-base-host-20261008.json。四例扩展质量脚本已准备未运行；顺序启动Qwen Edit共享适配器三格式/1–3参考图及生命周期回归71440，尚未通过。未发布。

- 2026-10-08 Base验收扩展：独立输出检查器新增官方receipt/参数/PNG RGB核对（不对JPEG/WebP要求无损精确）；新增固定官方与适配器四例布局/文字/横图/纵图质量探针，保存双方图片并将视觉审查独立标记pending。语法检查通过，四例尚未运行，不计质量通过；Host69110首图仍生成中。证据 evidence/media/z-image-base-quality-plan-20261008.json。

- 2026-10-08 Z-Image Base隔离HTTP71214 exit0：1024 PNG/JPEG/WebP完整生成并独立解码/摘要/尺寸通过，首请求195.06秒、后两次74.41/74.66秒；编辑拒绝400、取消恢复、drain503/resume实际生成通过，禁网/只读/non-root。PNG目视符合红茶壶/桌面/蓝背景，非广泛质量通过。证据 evidence/media/z-image-base-http-20261008.json。顺序启动Host69110（z-image-base-host-r1），使用官方相同prompt/negative/seed与准确生成能力声明；仍在运行，签名安装/发布未完成。

- 2026-10-08 图像Host验收桥接改为按family声明真实操作：Base/Turbo/Qwen生成仅image_generation，Qwen Edit仅image_edit且最多3参考图，FLUX保留生成/编辑及4参考图；回执记录family与操作。check_media_worker显式传family，语法编译通过。仅验收fixture修正，不改变生产发现；Base隔离HTTP71214仍加载中，Host实机尚未执行。

- 2026-10-08 Z-Image Base官方对照83734 exit0：候选默认与negative_prompt两例1024²/30步/CFG4/seed42解码RGB均与固定官方BF16基线精确一致；实际生成取消后恢复亦精确，stop释放pipeline。证据 evidence/media/z-image-base-official-adapter-20261008.json。随后启动隔离HTTP三格式与生命周期验收71214（z-image-base-http-r1），尚在运行；单提示对照不代表广泛质量，Host/签名安装/发布仍未完成。

- 2026-10-08 Z-Image Base正式分发缺口确认：既有Mac分发17文件不含scheduler/scheduler_config.json，不能直接作为CUDA完整checkpoint。已按固定MS 77e77d0c权威元数据核对本机已哈希HF18文件全部一致，新增 z-image-base-checkpoint-distribution.json 规格（CUDA专用ID，包含scheduler）；只准备规格，未签名、未发布、未在模型Package引用。官方适配器对照83734仍运行，首例去噪接近完成，尚未计通过。证据 evidence/media/z-image-base-preparation-20261008.json。

- 2026-10-08 Z-Image Base官方原始权重BF16基线74193 exit0：固定Diffusers0.41.0、Torch2.10cu130、Transformers5.18.0；1024²/30步/CFG4/cfg_normalization=False/seed42，空及非空negative_prompt两例75.52/74.61秒，模型加载103.16秒，峰值CUDA分配23.272GB。两图目视均符合红茶壶/木桌/蓝背景，构图不同；仅单提示，不计广泛质量通过。回执 artifacts/z-image-base-official-r1/receipt.json。候选逐RGB对照及取消恢复83734已启动，尚未通过；Worker/Host/签名发布仍待完成。

- 2026-10-08 Qwen Image共享适配器修改后隔离HTTP回归1583 exit0：512 PNG首请求342.73秒，生成外操作拒绝、取消恢复、drain/resume实际生成通过。慢加载期间保持原进程，未重复启动；不将首请求耗时当稳态性能。证据 artifacts/qwen-shared-adapter-r1/receipt.json。Base官方BF16基线已顺序启动74193，固定checkpoint重新完整校验、官方Pipeline加载完成，生成尚未返回；Qwen Edit回归/签名安装仍待完成。

- 2026-10-08 Z-Image Base原始权重传输42189 exit0，Spark全量集合/大小/SHA校验82177 exit0：18文件20,538,488,559字节，官方scheduler已包含。回执 artifacts/z-image-base-preparation/z-image-base-spark-verification.json。Qwen共享适配器回归1583仍活跃，PID2752870已加载pipeline组件、尚未返回生成；观察可用RAM69Gi，不据等待判失败或重启。Base官方基线继续等待唯一GPU任务结束，尚无Base推理通过声明。

- 2026-10-08 共享图像生命周期修改后Z-Image Turbo隔离HTTP回归通过（47642 exit0）：1024 PNG/JPEG/WebP、编辑拒绝、取消恢复、drain拒绝/resume实际生成，禁网/只读/非root。证据 evidence/media/shared-image-lifecycle-regression-20261008.json。顺序启动Qwen Image512单图+生命周期回归1583，尚未完成；Base权重42189持续传输已约13G，未启动Base推理。check_media_worker.py新增Base固定checkpoint入口和negative_prompt选项。

- 2026-10-08 共享CUDA图像候选补齐停止准入与重复ID保护：Base/Turbo/Qwen三个家族受控线程验证原取消事件保留、active/queued499、stop中新请求503、资源清理及start后重载；20项测试通过，Qwen Edit继承同一invoke生命周期。新增 check_z_image_base_adapter.py 准备对固定官方Base两例逐RGB摘要对照及取消后精确恢复；尚未执行。权重传输42189持续运行，未重启；所有受影响候选仍需实机/隔离Worker回归，既有已发布制品不变。

- 2026-10-08 Z-Image Base候选接入现有CUDA图像适配器：固定Base revision，32倍数画布、默认30步/CFG4；明确使用官方guidance_scale、negative_prompt、cfg_normalization=False，避免误走Qwen true_cfg_scale；Turbo既有约束保持。17项测试通过，新增完整invoke fake Pipeline验证实际参数/seed传递与非法几何拒绝，非GPU质量通过。原权重传输42189仍运行，远端已5.6G；官方/适配器数值与Worker/Host验收待传输及远端校验后执行。证据 evidence/media/z-image-base-preparation-20261008.json；未发布。

- 2026-10-08 开始Z-Image Base官方CUDA接入：固定04cc4abb原始权重，Mac本机18运行文件/20,538,488,559字节按官方摘要校验通过；补齐同提交scheduler配置。准备固定Diffusers0.41.0官方BF16基线（1024²/30步/CFG4/seed42，空和非空negative_prompt），尚未生成。传输42189仍运行，已观察远端2.0G；不可重复启动，完成后先远端全量哈希。证据 evidence/media/z-image-base-preparation-20261008.json、Z-IMAGE-BASE-REUSE.md；Worker/Host/签名发布均待做。

- 2026-10-08 H3持久化任务生命周期实机通过（83424 exit0）：运行中任务0.567秒取消，排队任务取消，均无Artifact/残缺result/part；运行中优雅关闭VideoTaskManager后旧任务正确cancelled，重建管理器后新任务生成并登记Artifact。恢复视频解码RGB/音频摘要与首次同seed精确一致，56帧/同步有限非静音音轨。调度2正常完成/2预期失败、queued/running0、槽位/GPU释放。证据 evidence/media/h3-durable-lifecycle-20261008.json；是管理器优雅关闭重建，不是进程崩溃或断点续算，API登录/签名安装和完整质量仍待完成。

- 2026-10-08 H3真实持久化视频任务通过（57131 exit0）：完整当前Host源码快照下VideoTaskManager/数据库/身份解析/后台调度/stream-to-file/Workspace产物登记完成文本及图音视频混合两例；3输入冻结摘要正确，幂等重试同ID、跨用户get404，2完成/0失败、队列归零/槽位释放。独立解码均56帧、同步非静音音轨；GPU进程清空。证据 evidence/media/h3-durable-tasks-20261008.json，保留此前3次验收环境失败和源码同步修正。仍为声明/测试身份fixture，不含产品API登录、签名安装；持久化任务取消/重启及完整质量待补。

- 2026-10-08 H3 生命周期修复后的Host/隔离HTTP回归通过（53088 exit0）：音频、视频含原音、忽略原音、图音视频混合参考四例均成功，解码RGB/音频摘要与修复前逐项一致；取消恢复、drain拒绝、resume真实生成通过，6完成/2预期失败，queued/running0、槽位归还。证据 artifacts/h3-host-lifecycle-r1 与 evidence/media/h3-worker-lifecycle-guards-20261008.json。另记录产品接入缺口 evidence/media/h3-product-integration-gap-20261008.json：现有foreground fixture不覆盖VideoTaskManager内容冻结、background-to-file、产物登记及API认证；H3精度禁用策略亦需按官方CUDA证据评估，未擅自放开。签名安装/发布仍未完成。

- 2026-10-08 H3 新生命周期保护实机通过（25771 exit0）：真实Comfy队列运行时重复ID409且原事件保留，stop中新请求503，活动/排队均499；3.110秒停止并回收旧子进程/临时目录，start后重新加载生成成功，最终事件与GPU进程清空。重启后与首次同seed输出解码RGB及音频SHA完全相同，均56帧、音视频时长同步。证据 evidence/media/h3-worker-lifecycle-guards-20261008.json、artifacts/h3-lifecycle-r1。此为候选适配器原生生命周期，更新版本的HTTP/Host及签名安装仍待完成，未发布。

- 2026-10-08 H3 Worker 修复重复request_id覆盖取消事件和stop期间接受新请求：重复409，stop先关闭准入并取消活动/排队请求，显式start恢复；15项测试通过，受控异步子进程fixture验证原事件保留、排队不进入生成、等待清理、子目录回收及重启。证据 evidence/media/h3-worker-lifecycle-guards-20261008.json；此前实机Host通过早于此次修改，新候选GPU/Host回归仍待完成，未构建发布Runtime/Package。pytest退出0，结束时有无Metal设备环境警告。

- 2026-10-08 H3 多媒体参考 Host 实机通过（40765 exit0）：音频/视频含原音/忽略视频原音/图音视频混合参考均经真实Host调用、调度和Supervisor代理至禁网Worker，耗时41.68/48.78/47.69/53.10秒。取消恢复、drain拒绝、resume实际生成通过；6完成/2预期失败，队列和运行归零、槽位释放、GPU进程清空。四视频各56帧/2.333秒，音频2.325秒/32kHz、有限非静音；新增解码RGB与音频摘要。证据 evidence/media/h3-host-media-20261008.json。忽略参考视频原音不等于输出静音；此为fixture发现下链路验收，不代表完整参考保持/听感、产品API/UI/签名安装或发布。

- 2026-10-08 H3 当前 Host 整链实机通过（58782 exit0）：canonical模型ID经ModelInvocationService/真实调度器/Supervisor转发为各变体upstream别名，文本JSON、首帧/参考图multipart均成功；取消恢复、drain拒绝和resume后真实生成通过。5完成/2预期失败，queued/running0，槽位归还。三项独立解码56帧且音轨有限非静音、时长同步。回执 artifacts/h3-host-identity-r1/receipt.json 与 media-inspection.json；模型发现/能力声明仍fixture，不含API/UI认证、签名安装及完整质量验收，音视频参考Host工作流仍待补。

- 2026-10-08 H3 唯一变体别名隔离 Worker 实机通过：文本/首帧/参考图分别63.67/24.32/27.37秒，取消恢复通过。三例完整解码56帧、视频2.333秒/音频2.325秒，音轨有限非静音。证据 artifacts/h3-identity-worker-r1/{receipt,media-inspection}.json；不替代完整视听质量、Host或签名安装。新增 Host JSON/multipart 调度转发探针及 resume 后实际生成断言，实机尚待运行。

- 2026-10-08 H3 Host 身份修复：FL2VA/Ref2VA 开发声明的调用 upstream_id 改为各自带变体后缀，checkpoint repo仍固定Comfy-Org/MiniMax-H3；适配器接受唯一声明别名并按canonical ID找checkpoint，共享仓库别名含糊时明确拒绝，不静默选首个变体。14项测试通过，实机/HTTP/Host复验待做。证据 evidence/media/h3-host-model-identity-20261008.json。另匿名复核生产 Runtime 上传合同仍4GiB，8GiB需求未生效，见 evidence/media/runtime-upload-capabilities-recheck-20261008.json。

- 2026-10-08 FLUX 当前 Host 整链 r2 通过（42567 exit0）：请求ID转发修复后取消恢复正常；生成/编辑和2–4参考均经ModelInvocationService→调度器→Supervisor代理→禁网Worker完成，恢复后再次生成成功。调度7完成/4预期失败，queued/running0，唯一槽位归还。六项请求ID专项测试覆盖显式、幂等及自动ticket ID的JSON/multipart路径。证据 evidence/media/flux-current-host-probe-20261008.json、artifacts/flux-host-lifecycle-r2/receipt.json。发现仍fixture，不含产品API/UI认证/签名安装；不计发布或9B支持。

- 2026-10-08 FLUX Host 首轮86216exit1揭示真实取消问题：request_id仅进入调度器未转发Worker，取消查询404。已修复JSON/multipart代理x-request-id，优先显式ID、再幂等ID、否则调度ticket ID，认证头保持，去除旧大小写变体。45项测试通过。多参考测试此前直连Worker，已改经Host并声明4参考能力。r2实机重跑中；证据 evidence/media/flux-current-host-probe-20261008.json。未声称整链通过或发布。

- 2026-10-08 FLUX 当前 Host 调用整链脚本已实现并启动86216（flux-host-lifecycle-r1）：ModelInvocationService、WorkerJobScheduler、Supervisor TCP/UDS代理转发至禁网CUDAWorker，复用生成/编辑/多参考/取消/drain/resume验收。仅模型发现fixture，不含API路由/登录UI/签名安装，当前运行中未计通过。证据 evidence/media/flux-current-host-probe-20261008.json。

- 2026-10-08 FLUX 4B 更新适配器隔离 HTTP Worker 验收通过（93256 exit0）：生成/编辑、多参考、非法输入、取消恢复、drain拒绝、resume后实际生成；禁网/只读/非root，结束GPU任务清空。证据 evidence/media/flux-http-lifecycle-20261008.json。候选适配器使用既有Runtime依赖，不代表新版签名Runtime安装、Host UI或9B完成。

- 2026-10-08 FLUX 4B CUDA 生命周期 r2 实机通过（18432 exit0）：真实去噪中重复请求409，stop后新请求503，活动/排队请求均499；stop等候0.211秒，显式start后重新加载生成512图像成功，事件清空/模型释放。生成红色茶壶图已目视确认符合本条提示。证据 evidence/media/flux-worker-lifecycle-guards-20261008.json、artifacts/flux-lifecycle-r2/receipt.json。仅候选适配器+既有Runtime依赖，不代表新版Runtime签名安装/HTTP/Host验收或9B支持。

- 2026-10-08 FLUX CUDA Worker 修复活动 request_id 重复覆盖取消事件，以及 stop 后仍接受请求的问题：重复返回409；stop 先设置 stopping、取消已注册请求并等待串行执行结束，新请求503；显式 start 恢复。7 项适配器测试通过，新增真实线程受控 fake pipeline 测试覆盖活动/排队取消、重复事件保留、资源清理和重启。证据 evidence/media/flux-worker-lifecycle-guards-20261008.json；此为并发单测，非 GPU 实机验收，Runtime/Package 未构建发布，9B 尚未开放。

- 2026-10-08 CosyVoice3 已签名原始分发通过真实 CheckpointCache.import_local_snapshot、CheckpointAcquisitionService.materialize_worker_snapshot 和 Host model_checkpoint_is_complete 路径：13 文件导入、只读 Worker view、缓存命中、错误 distribution ID 拒绝均通过（25471 exit0）。输入 envelope 摘要绑定先前独立验签回执。证据 evidence/media/cosyvoice3-original-cache-acceptance-20261008.json；不是 Registry 网络下载/签名模型安装验收。已请求本次精确分发使用 Dev --browser-live 的 Cookie 入口授权，回复前不执行该读取或发布。

- 2026-10-08 CosyVoice3 原始 checkpoint 分发已由标准构建器签署并按既有 Publisher 指纹验签：13 文件/5427029150 字节/647 pieces，manifestDigest sha256:3952f2573812adbb6ba32509f1d6ba1c83c2f8db37dc26194d1cc748de71cee6。HF 本机字节完整 SHA 校验且与固定 MS 权威元数据一致（metadata_verified，不是双端完整下载）。证据 evidence/media/cosyvoice3-original-distribution-signed-20261008.json。Installation 标准查询仍要求 active user session；未读 Cookie、未提交/发布，未在模型 Package 引用未发布 distribution。

- 2026-10-08 CosyVoice3 13 文件锁的标准 Runtime 导出 r8 完成（71868 exit0，103 依赖/14164 文件，106 源码文件，无缺失/多余）。准备 cosyvoice3-original-checkpoint-distribution.json，固定 HF 29e01c4e 和 MS 9f9c56f2、精确 13 文件、pytorch/fp32；仅构建规格，未在 Package 引用未发布 distribution。证据 evidence/media/cosyvoice3-original-distribution-preparation-20261008.json。本机固定快照传输会话 50027 运行中，完成后仍须逐文件哈希再标准签名；未签署/发布。

- 2026-10-08 CosyVoice3 13 文件运行快照官方实机验证通过（46437 exit0），中英文 WAV 与 15 文件完整基线逐字节一致。严格运行锁仅移出 HF 根 README.md/空 config.json 到 upstream_documentation_files 来源记录，13 个运行文件和官方源码哈希检查保留。证据 evidence/media/cosyvoice3-original-runtime-file-selection-20261008.json；CUDA 引擎五档语速复验 14563 exit0，5/5 WAV 与官方完全一致。修改后的锁尚未进入标准 Runtime 再导出/安装验收，未签署或发布 distribution/Package。

- 2026-10-08 CosyVoice3 更新后的官方原始引擎完成标准导出 r7（103 依赖、14164 依赖文件、106 源码文件，零缺失/多余），独立禁网 Worker fixture r2 的 Host 控制整链通过：五档数值语速及七种指令共 12 个输出均与官方 PCM 0 LSB；指令用例同时携带参考文字以验证优先级，另有中英文基线和 FLAC 无损回归。会话 84946 exit0。证据 evidence/media/cosyvoice3-original-host-controls-20261008.json。仍是 fixture 发现/未签名 Runtime，签名安装、产品 UI、资源准入、听感及发布不计完成；旧快速文字指令 ASR 差异保留。

- 2026-10-08 官方 CosyVoice3 原始 FP32 接入原生非流式数值语速（mel 插值），范围 0.5–2；原始版本适配器保留倍率，不再转文字指令，量化版本行为保持原样。Spark 五档 0.5/0.8/1/1.25/2 倍速 WAV 与独立官方基线逐字节一致，五档 ASR 内容诊断全通过（单条中文）；19 项适配器测试通过。证据 evidence/media/cosyvoice3-official-original-speed-20261008.json。旧快速文字指令差异未消除；新代码的标准 Runtime 导出、Worker/Host 控制整链、多语言/长文本、听感及签名安装发布仍待完成。

- 2026-10-08 官方 CosyVoice3 控制模式：补齐官方 helpful-assistant 指令前缀，指令与参考文字并存时按官方 instruct2 语义优先指令、不消费参考文字。Spark 七种控制及额外优先级用例共 8/8 WAV 与独立官方基线逐字节一致；ASR 内容检查 6/7，快速指令将“我们来介绍”转写为“我们要介绍”，保留失败，未判定合成或识别原因。情绪听感未验收。旧标准导出 r6、HTTP/Host 回执早于该修复，不能证明新修复的整链通过；数值 speed 尚未接入官方原生实现。证据 evidence/media/cosyvoice3-official-original-controls-20261008.json；签名安装/发布仍未完成。

- 2026-10-08 官方CosyVoice3原始FP32当前Host整链通过：当前语音API→ModelInvocationService multipart参考音频→真实WorkerJobScheduler→Supervisor loopback/UDS→禁网Worker。首轮15128暴露Host将内部ID改写为upstream_id但适配器白名单不接受，已只增加固定官方repo别名，canonical checkpoint id/repo/revision/path约束不放宽；14适配器测试通过。r2 22436exit0，中英文PCM与官方基线0LSB，九格式wav/pcm/mp3/m4a/aac/flac/ogg/opus/webm都通过类型/解码时长/有效信号检查，wav/pcm/flac精确。12任务完成、3非法控制预期failed，running/queued0、唯一重计算槽位归还，容器清理。证据cosyvoice3-official-original-host-20261008.json；发现仍fixture PackageModel、ASGI TestClient不含生产登录UI，不计签名安装/QuickRead/资源准入/感知质量/发布完成，指令情绪速度长参考功能仍待验证。

- 2026-10-08 官方CosyVoice3原始FP32禁网HTTP通过：标准export-r6组装独立未签名fixture，真实Worker launcher/UDS multipart，中英文与官方r9 WAV逐字节一致；未认证health401、非法seed/采样/stream/路径拒绝；观测running后DELETE取消499耗时0.0834秒，恢复及drain503/resume后PCM精确，active_requests归零。Docker实查断网/只读/uid1000:1000/capdropALL/no-new-privileges，finally清理容器并wait进程，99148exit0。首次探针误加局部Worker源码PYTHONPATH导致导入Host失败，尚未起容器；改用Spark完整Host安装后通过。证据cosyvoice3-official-original-http-20261008.json；未完成实际Host发现/gateway/scheduler、签名安装/权重分发/正式发布，声纹风格等完整功能仍待验证。

- 2026-10-08 CosyVoice共用Runtime profile升级：标准构建器固定官方Transformers4.51.3及103项闭包，补Matcha子模块固定归档/MIT与README/requirements、原始引擎/权重源码锁和完整依赖锁/NOTICE。r6导出14164依赖文件逐SHA匹配、0多余/缺失、无.pth；106运行源码与34保留文件校验。原4/8bit六例在共用依赖环境与历史输出逐字节一致（兼容回归，不作为正确性真值）。原始模型Python -I -S仅导出profile+固定core，中英文WAV与官方基线精确；70构建器/profile测试通过。r5缺matplotlib/rich已修复留证；r6首次CUDA stream分配OOM，GPU无其他任务，特定测试文件fadvise回收缓存后物理free约13→20GiB，复验通过，不断言精确内因。证据cosyvoice3-unified-runtime-export-20261008.json，53846exit0；尚未完整CLI封装/禁网HTTP/签名安装与发布，既有0.5.0签名候选不变。

- 2026-10-08 官方CosyVoice3原始FP32变体接入共享Worker适配器：复用现有WAV/串行锁/线程排空和Host参数契约，严格要求官方repo/revision及Host checkpoint，不新增远端下载。Spark实际ModelWorker请求91762 exit0：两种参考模式与官方WAV逐字节一致；6类非法控制拒绝；观测LLM运行后event取消0.00218秒/task.cancel0.00086秒，恢复音频精确；同时停止运行中/排队请求后engine/events清空，停止后503，restart输出精确。证据cosyvoice3-official-original-adapter-20261008.json。仍为fixture声明和开发Host快照的原生适配器；未验禁网HTTP/安装后Host。现有cosyvoice3 Runtime profile仍旧量化依赖闭包，必须合并官方依赖并重新验证旧变体后才能封装；指令/情绪/速度在本轮fixture明确未开放，完整功能对齐和发布未完成。

- 2026-10-08 官方CosyVoice3可复用引擎实现：cuda_cosyvoice_original_engine.py固定15权重文件/49官方Python源码摘要及Transformers4.51.3，以实例局部函数绑定明确CPU ONNX/SoundFile兼容，不全局改写上游模块；保留官方算法和非流式线程join，捕获producer异常并在解码前传回，finally清请求缓存。Spark原生78332 exit0：中英文WAV与官方r9逐字节一致，LLM/decode两个阶段取消无partial、线程退出、缓存清空，恢复音频精确；producer错误传播、已有文件保留、RNG恢复、close清model/hooks及关闭后拒绝通过。证据cosyvoice3-official-original-engine-20261008.json。尚未接Worker/profile/签名Host发布；新封装FP16、长请求取消、声纹风格与长参考音频尚待验证，原生官方参考上限30秒，Matcha及完整依赖闭包须在Runtime构建中继续固定。

- 2026-10-08 LanceDB真实Supervisor.start/restart/stop通过：独立Runtime快照与一次性PlatformDatabase/PackageRepository，显式host-unix服务自动选中knowledge profile、自动socket+Host loopback代理+health，真实存储重启保留。停止后CLI进程终止、代理不可访问、socket清除，两条managed_service_processes记录stopped；按测试mount检查无遗留容器。证据knowledge-real-supervisor-20261008.json，18565 exit0。Repository记录明确为未签名不受信测试fixture且Runtime resolver为fixture，不作为签名安装/依赖锁/Registry验收；发布仍未完成。

- 2026-10-08 正式Supervisor接入显式runtime.transport=host-unix：仅managed http-json及唯一--port {port}允许；Host分配私有socket并复用loopback代理、health与清理生命周期，CPU服务不授GPU。缺Docker/非Linux明确拒绝，避免退回不可达TCP；未改变现有Mac manifest。30合同/Runtime/profile回归通过，证据knowledge-host-unix-transport-20261008.json，文档补充声明契约。尚未在Spark真实PackageRepository走当前Supervisor.start整链，Linux候选manifest、签名安装/发布待完成。

- 2026-10-08 LanceDB新增--uds Unix HTTP入口（与--port互斥），socket0600且拒绝覆盖既有路径；标准Docker沙箱构造器增加显式cuda=False，默认CUDA行为不变。真实标准导出profile+core在network none/只读/UID1000/cap-drop ALL/no-new-privileges/无DeviceRequests容器通过upsert/search/private owner过滤、进程重启保留及删除重启保留，67166 exit0，23项Runtime/profile回归通过。证据knowledge-uds-sandbox-20261008.json。本轮显式测试启动，尚未接通正式Supervisor.start选择/已安装Service Host代理；无签名安装或发布，不能视为完整交付。

- 2026-10-08 普通Service独立Runtime profile选择已修复：提取framework_profile_for_service供模型launcher和Supervisor共用，由Host service_key查询Runtime元数据，保留绝对路径/父目录/符号链接越界拒绝；普通Service PYTHONPATH按选中profile→core排列。回归首轮50通过/8本地端口权限失败/1跳过，获准本地测试服务重跑8全通过。证据knowledge-generic-runtime-profile-20261008.json。另发现Linux普通无网络Service使用unshare-net，LanceDB现有TCP loopback无法据此保证Host可达；待受保护传输实作验收，不以开放外网权限绕过。尚未签名安装/发布。

- 2026-10-08 LanceDB标准Runtime接入推进：构建器新增knowledge独立profile/固定服务映射、--knowledge-python与lancedb能力声明双向约束，固定knowledge依赖锁。Spark标准导出16依赖、1052文件逐SHA一致、零缺失/多余/无.pth；python -I -S仅导出profile+固定core实测create/search/delete/reopen通过。69构建器/profile回归通过，证据knowledge-standard-runtime-export-20261008.json，42163/83677 exit0。初始环境缺PyYAML已固定补6.0.3，仅构建使用不进入闭包；尚未验证沙箱Service自动profile选择、完整CLI Runtime/签名安装与发布，既有0.5.0签名制品不变。

- 2026-10-08 E5生命周期补验通过：真实CUDA前向期间task.cancel传播后events/lock清空、恢复向量精确；stop同时处理运行中499与排队503请求并清空engine，新adapter重建后向量精确。独立禁网HTTP Worker观测running后DELETE取消返回499、active_requests归零、恢复精确，原鉴权/drain/resume继续通过。证据e5-lifecycle-20261008.json；11139/23079 exit0。首次开发探针缺少engine搜索路径在推理前失败，修正为已验标准导出profile，日志保留；本轮不代表已安装服务进程重启/卸载验收或签名发布。

- 2026-10-08 E5公开Knowledge接口与Tool实机通过：当前API router经ASGI和注册knowledge.search handler调用真实Host→隔离E5→LanceDB；Alice/Bob各自hybrid检索与私有权限结果一致。Worker drain503时两条入口均正常FTS回退且仍排除私有记录，resume恢复hybrid。证据e5-public-knowledge-20261008.json；首轮快照导入顺序导致循环导入（71664 exit1）已留痕，修复测试加载后39195 exit0，容器清理。身份依赖及模型发现仍fixture，未验真实登录中间件/签名安装自动发现；LanceDB Runtime与Package发布仍待完成。

- 2026-10-08 E5当前Host真实链路通过：独立源码快照的ModelInvocationService/Knowledge provider经Supervisor loopback→UDS代理调用禁网E5 Worker；真实WorkerJobScheduler限定1槽，5次后台sync每次仅1次准入，查询actor Alice/Bob正确。SQLite新增/更新/删除、持久游标与最终权限回查继续通过；错误凭据401后正常凭据恢复384维向量，最终running/queued均0。证据e5-real-host-gateway-20261008.json；47021/32084 exit0、容器清理。模型发现仍fixture，LanceDB开发环境；尚未覆盖公开Knowledge HTTP/Tool路由、签名安装自动发现、完整取消并发stop及发布。

- 2026-10-08 Knowledge CUDA Host调用桥已实现：query/passage通过ModelInvocationService，后台索引复用自身已准入ready model及内部鉴权，不重复申请租约；查询传递principal派生身份并走前台调度。同步桥拒绝事件循环线程调用，Knowledge Tool检索移到线程以免阻塞；后台callback取消后等待真实线程结束才释放租约。45项不同Knowledge/gateway回归通过（fixture传输），证据e5-host-gateway-implementation-20261008.json。尚未在Spark用新Host代码跑真实代理/调度验收，不能把之前fixture直连结果当作新链路通过；签名安装与发布仍待完成。

- 2026-10-08 E5真实SQLite索引链路验收通过：PlatformDatabase/KnowledgeVectorIndexer/HybridKnowledgeRetriever连接隔离E5 HTTP与开发LanceDB；新增两条文档、幂等增量、网页更新重嵌入、持久化游标重新构造、删除传播通过。刻意令向量预过滤返回Alice私有记录给Bob，SQLite最终回查仍排除；删除尚未同步向量时也不泄漏旧记录。证据e5-sqlite-index-20261008.json，exec35905 exit0、容器及服务清理。仅测试fixture持有鉴权传输；正式Knowledge provider当前无Worker鉴权，外层index租约与嵌套调用可能冲突，Host接入仍待修复，不能声称正式安装/发布通过。

- 2026-10-08 Spark Knowledge存储链路推进：独立knowledge-venv安装官方Linux ARM64 LanceDB0.37.1/PyArrow25.0.1并记录knowledge-cuda-requirements.lock，复用未修改LanceDB服务源码。禁网只读E5 HTTP真实向量接LanceDB loopback服务，五条受控记录验证中英日Top1、installation/私有owner/bucket过滤、Mac generation为空，两次进程重启后结果及删除持久化通过。证据e5-lancedb-storage-20261008.json。LanceDB仍开发进程而非签名沙箱Runtime，未覆盖Knowledge SQLite change-log/indexer/最终权限回查和大库性能，不改用户数据；32437/17293 exit0，容器与子进程清理。

- 2026-10-08 Knowledge Host修正硬编码Mac E5绑定：Linux默认CUDA E5、Mac沿用原MLX，构造器可显式指定；查询/文档provider与后台ModelInvocation资源准入统一使用self.embedding_model_id。CUDA独立generation lancedb_e5_small_cuda_614241f6_fp32_v1与检索profile防止384维相同而混用Mac旧索引。19项Knowledge runtime/indexer/retrieval回归通过，证据e5-knowledge-binding-20261008.json；未迁移用户索引/生产实例，Spark真实Host代理、LanceDB安装/持久化/删除/重启及签名发布仍待完成。

- 2026-10-08 E5禁网只读HTTP Worker通过：标准E5 profile/engine/checkpoint锁加固定core的独立未签快照，当前共享embeddings路由和适配器在UID1000运行。384维有限单位向量、实际token计数、中英日三对Top1正确，上游alias结果相同，未鉴权health401、4项非法参数400、drain503/resume精确、active_requests归零，Docker Network none/ReadonlyRootfs/CapDrop ALL/no-new-privileges核验通过。证据e5-isolated-http-worker-20261008.json；完整HTTP取消/并发stop/restart、Knowledge Host索引检索、正式签名安装发布未完成，旧原生数值对照不冒充本轮HTTP逐向量对照。42429/2510 exit0，容器清理完成。

- 2026-10-08 E5标准Runtime支持已实现：新增e5独立profile和明确服务映射、--e5-python与capability闭合校验、固定33依赖锁、两运行文件（engine+checkpoint锁）及requirements/NOTICE保留文件。实际导出3506个依赖文件逐SHA匹配、0缺失/0多余/无开发.pth；python -I -S仅profile+固定core实测官方向量对照/取消恢复/关闭通过。构建器与profile67项回归通过。证据e5-standard-runtime-export-20261008.json；仍未构建完整CLI Runtime、禁网Docker HTTP、签名安装或Knowledge Host，旧0.5.0候选不变，38733/56030进程exit0。

- 2026-10-08 E5 Worker适配器实现并通过原生异步实机验收：固定model/alias/checkpoint绑定、384维float输出与实际token计数、输入边界、串行请求、重复ID409、模型前向中cancel499、取消后结果精确恢复、stop清空并503；六项非法控制拒绝。共享Worker新增embeddings→/v1/embeddings路由，沿用鉴权/排空/请求生命周期，21项Worker回归exit0（沙箱Metal退出警告不计GPU证据）。证据e5-native-worker-adapter-20261008.json；传输测试为fixture adapter、GPU为原生调用，不能合并声称真实隔离HTTP通过；Runtime导出、Host Knowledge、签名安装发布、task.cancel/排队stop仍待完成，exec71143 exit0。

- 2026-10-08 E5新增cuda_e5_engine.py：加载前逐文件锁定官方原始权重字节、禁止远端代码，FP32 eager/官方mask均值池化/L2，最多256条、每条64KiB、16条分批、512token截断，返回实际token计数；串行锁保护encode/close，各BERT层取消hook在finally清理。实际Spark与官方FP32基准max_abs6.89179e-8，第5次检查中断后hook清理且恢复向量逐值精确，17条跨批执行、5项非法输入及close后拒绝通过。证据e5-native-engine-20261008.json；本轮仅原生模块，未完成Runtime声明/HTTP Worker/Knowledge Host/并发压力/签名发布，exec56248 exit0。

- 2026-10-08 Multilingual E5 Small官方原生基线完成：固定intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3，10文件493292828字节重哈希通过。Torch2.10.0+cu130/Transformers4.57.3官方BertModel、FP32 eager、masked mean pooling+L2，加载missing/unexpected/mismatched均0；CPU/CUDA最大绝对差1.86265e-7、relativeL2 8.06705e-7，中英日三对检索Top1正确，单条/批量及512token截断有限输出通过。BF16诊断min cosine0.999944/max relativeL2约1.09%，排序相同但不据此选择产品BF16。首次forward CPU0.106秒/CUDA0.310秒含初始化，不宣称吞吐优劣。证据e5-official-native-20261008.json；仅原生开发环境，后续FP32可复用engine/Runtime/Worker/Knowledge Host和签名发布尚未实现，两个进程exit0。

- 2026-10-08 Fish S2五角色六轮HTTP实测通过：speaker0/1/2/3/4/0跨官方分批边界，结构化dialogue与显式官方标签WAV逐字节一致；六个不同角色请求400，随后合法请求WAV精确恢复，active_requests归零。10.820秒音频独立ASR正文全文精确。证据fish-s2-five-speaker-20261008.json；ASR原始scope沿用多语言脚本旧说明，证据已明确本轮仅英文对话。未提供参考声纹，不能据此声称五声音听感区分或跨轮声纹稳定，也不是正式安装/Host/QuickRead/发布验收；HTTP与ASR进程exit0，容器已清理。

- 2026-10-08下一批媒体Runtime容量预检完成（exec62726 exit0）：完整已签0.5.0基线3906220347字节保持不变，九组标准导出profile+保留源码分别压缩增量1351424444字节，估算合计5257644791字节约4.90GiB，超过当前4GiB。此为估算而非完整最终ZIP；证据next-media-runtime-size-20261008.json。已写docs/ai2apps-spark-media-runtime-capacity-cloud-requirements-20261008.md供用户转交Cloud，建议仅官方CUDA Runtime升至8GiB，oMLX/普通限制及全部安全门禁保留；未改Cloud、未提前放开客户端上限、未改已签候选。发布会话及模型质量工作独立继续。

- 2026-10-08 Fish S2权重发布快照同步完成（exec87279 exit0），标准metadata_verified预检重新读取固定MS元数据并重哈希Mac完整原始字节，11文件/1313个全局8MiB分片/11008083526字节通过（exec12747 exit0）。证据fish-s2-distribution-preflight-20261008.json；未签分发规格可供标准构建器使用。Dev公开bootstrap确认当前installation local_a43644810f7b48bdcce578ca1db05416；Installation标准Publisher查询返回active user session required，已有授权下精确Profile Cookie标准查询仍database is locked（exec84964 exit1），未扫描/复制其他数据库，未提交。当前Cloud Publisher状态未重新核对，因此不宣称完成新签名/分发发布；继续独立Runtime/质量工作。

- 2026-10-08 Fish S2正式分发准备推进：匿名git解析ModelScope fishaudio/s2-pro固定revision25d17c7b8763aa4bab6ec86fd61e2a3f388f2d04，标准元数据读取器确认11文件大小/SHA与官方HF1de9996b既有实机校验清单全部一致，总11008083526字节。新增fish-s2-checkpoint-distribution.json未签规格，保留研究许可/下载同意/署名要求；正式service manifest未写入未发布distribution ID。证据fish-s2-distribution-metadata-20261008.json。Spark原始权重向Mac独立发布目录同步中，exec87279已重新确认仍运行（约4.8GiB），不能重复启动；完成后运行check_fish_s2_distribution_snapshot.py执行标准本地字节/全局piece预检，再核对Publisher并签署。Runtime导出596MiB仅解包增量，完整压缩候选4GiB门禁未验证，既有0.5.0签名候选未修改；未访问Cookie或发布。

- 2026-10-08 Fish S2中日英内容实机检查通过：固定官方源码/原始权重、未编译CUDA路径在禁网只读非root HTTP Worker生成中文8.777秒、日文7.384秒、英文段落29.164秒；独立ASR去标点/大小写后3/3全文精确，含英文末句，无削波样本。日文驻留请求18.379秒、英文75.827秒（RTF约2.60）；中文119.424秒含冷加载，不能当纯推理耗时。证据fish-s2-multilingual-content-20261008.json。仅三组内容样例，不等同多分钟/全语言/自然度/音色质量验收，本轮未做独立官方数值对照或签名发布。HTTP与ASR进程exit0，容器清理完成。

- 2026-10-08 Fish S2情绪控制传递通过：以固定官方源码与原始权重为基准，将结构化emotion映射为官方自然语言内联标签；修复多说话人全局instructions/emotion放在首speaker标记前被官方split_text_by_speaker丢弃的问题，改为每个turn标记后注入。隔离HTTP中happy/angry/whisper及双角色组合四组与显式内联标签生成的WAV逐字节相同，独立ASR正文4/4通过；未知emotion和非1数值strength返回400，35项回归通过。证据fish-s2-emotion-controls-20261008.json。此为同一CUDA实现内控制映射等价，不替代独立官方端到端数值对照；其他标签仅控制路径覆盖，情绪听感/音色/长时多语言、正式签名安装与发布仍未完成。实机进程已结束。

- 2026-10-08 Fish S2 Host变速流水线通过：显式tts.speed mode=pipeline/control=host_atempo时Worker按1倍生成，Host用共用atempo保音高后处理再编码，保持原生44.1kHz并返回pipeline状态；共用函数新增可选sample_rate，既有调用默认24k不变。24/44.1/48k音高时长及Host/codec47项回归通过。实机0.5/0.75/1/1.25/1.5/2六档时长符合预期，1倍原字节不变，独立ASR6/6正文通过；非法速度推理前400，流式变速拒绝；调度6成功0失败、队列归零。首轮旧快照边界状态失败保留，最终r2通过。证据fish-s2-host-tempo-20261008.json；仍为短英文fixture验收，不是模型原生变速或正式Package/Quick Read/长音频感知质量验收，生产manifest未改，语言/情绪等及签名发布继续推进，进程结束。 共享Host/codec改动纳入未来Desktop评估，尚未发布Desktop。

- 2026-10-08 Fish S2 Host工作流与九输出格式通过：真实Host路由/ModelInvocation/调度租约/代理接隔离Worker，普通、带文本参考、无文本参考、双角色对话均0 PCM16 LSB差；WAV/PCM/FLAC无损一致，MP3/M4A/AAC/OGG/Opus/WebM可解码，独立ASR九格式正文9/9通过。14次有效调用完成、3次非法控制按预期拒绝、队列/运行归零。修复共享Host：tts.voice_profiles.reference_sample_rate整数8000–192000、默认24000，Fish声明44100避免额外降采样；Package尊重reference_transcript=optional，旧接口默认要求文本保留。r1无文本拒绝证据保留；34项回归通过，其中旧Runtime能力测试改为解析YAML消除缩进假失败。证据fish-s2-host-formats-20261008.json；模型发现仍为fixture，正式安装/资源准入/Quick Read、其他参考输入格式、变速/语言、长音频及音色质量和发布仍未完成；进程均已结束。 共享Host改动须纳入未来Desktop Release，未构建或发布Desktop。

- 2026-10-08 Fish S2标准导出r3与隔离HTTP Worker通过：117依赖、26运行文件、6留存文件校验，独立fixture来自标准导出；首轮参考请求因multipart seed字符串被拒绝，已按有界ASCII整数正规化请求副本，布尔/浮点/非法值仍拒绝，38项回归通过。HTTP r2普通、带文本参考、无文本参考、双角色对话均0 PCM16 LSB差；鉴权、取消约0.0185秒、恢复、drain/resume、active_requests=0通过。容器NetworkMode=none、ReadonlyRootfs=true、CapDrop ALL、no-new-privileges、UID/GID1000确认；退出清理完成。证据fish-s2-isolated-http-worker-20261008.json；仍为未签名fixture，不等同正式安装/Host/音色及长音频质量，变速等控制和签名发布继续推进。

- 2026-10-08 Fish S2局部cuDNN codec策略已接入engine并通过冷启动与原生Worker复验：只在decode范围设deterministic=True/benchmark=False，其他设置保持，正常/异常恢复验证通过，不改变全局确定性策略。候选engine overlay+已导出加载器/依赖下，无参考文本重复与取消后恢复精确，普通/带文本参考仍匹配旧基准；取消约0.070秒，stop释放通过。普通/带文本/无文本参考/双角色对话ASR正文4/4通过。旧无文本非确定性波形仍不同，保留原证据，不声称音色质量或字节等价。75项回归通过；证据fish-s2-scoped-codec-worker-20261008.json。更新源码导出、HTTP隔离/Host、变速等功能及签名安装发布仍待完成，所有实机进程已结束。

- 2026-10-08 Fish S2无参考文本差异已定位codec：带文本重复全部一致；无文本在工作/主线程参考编码和语义codes均逐值精确，仅波形max_abs0.0078125。固定同一codes用官方codec解码复现；cuDNN deterministic=True/benchmark=False即可使后三次解码一致，无需全局use_deterministic_algorithms。此为切换后诊断，尚未改产品engine或通过冷启动/端到端新策略验收，数值漂移不等于内容错误，先前三项ASR仍有效。标准Runtime新增--fish-s2-python/--fish-s2-sources闭合能力校验与导出入口，64项回归通过，未构建新制品。证据fish-s2-reference-codec-determinism-20261008.json；下一步局部cuDNN策略及完整Worker复验，HTTP/Host/签名发布仍待完成，实机进程已结束。

- 2026-10-08 Fish S2共享语音Worker适配器已接入已验证加载器并实机诊断：普通/上游别名WAV精确，带参考文本与旧基准及重复均精确；取消约0.063秒退出、恢复WAV精确、stop释放通过。无参考文本与旧基准及重复均不一致，因此整体passed=false，保留r1失败和r2音频，继续以官方同输入重复运行定位；独立ASR对带文本/无文本参考和双角色对话正文3/3通过，不代表音色质量通过。修复共享OmlxTTSAdapter只对inline_speaker_tags跳过named_voices校验，其他模型预设检查保留；25项回归通过，影响未来Mac Desktop需纳入Release。证据fish-s2-native-worker-diagnostic-20261008.json；变速/指定语言/自定义采样尚未支持，HTTP/Host及签名安装发布未完成，所有实机进程结束。

- 2026-10-08 Fish S2正式可复用加载入口已实现并从标准导出r2实测：先按固定原始checkpoint清单校验全部字节，保留官方语义加载/键映射，通过局部类绑定检查358字段闭包，未替换进程全局torch加载器；codec541字段检查，仅允许六个已登记非持久缓存且逐值核对。导出26运行文件/6留存文件，python -I -S下加载95.03秒，短英文PCM16匹配此前稳定codec基准，重复float精确；66项回归通过。证据fish-s2-exported-verified-loading-20261008.json。本轮未重跑参考/取消生命周期，不宣称原始优化codec冷/热波形等价；共享Worker/Host、完整Runtime CLI、质量及签名安装发布仍待完成，既有Runtime0.5.0候选未改，实机进程已结束。

- 2026-10-08 Fish S2标准官方推理源码导出通过：固定源码摘要、显式24个运行文件、6个留存文件含完整源码/许可/Built with Fish Audio署名，排除训练datasets/lit_module；Spark逐SHA校验通过。使用python -I -S，仅导出profile与固定core路径，官方语义/DAC入口和engine导入通过，外部site模块0。构建器/profile60项回归通过(exit0，沙箱Metal atexit警告不计GPU证据)。证据fish-s2-standard-source-export-20261008.json；本轮未跑新GPU推理，完整Runtime CLI/加载factory/Worker/Host/签名安装发布仍待完成，Runtime0.5.0已签候选未修改。

- 2026-10-08 Fish S2标准Runtime依赖导出完成：新增fish-s2独立profile与ai2apps.model.fish-s2-cuda服务映射，导出前校验固定requirements.lock；Spark标准_copy_isolated_profile实际导出117分发包，16,975条RECORD对应16,974个唯一文件逐SHA核验，0缺失/0多余，不带开发.pth。新增服务隔离参数回归，构建器/profile58项通过(exit0，沙箱Metal atexit警告不计GPU证据)。证据fish-s2-standard-dependency-export-20261008.json；仅依赖profile，官方推理源码/包装器导出、完整Runtime CLI制品、Worker/Host/签名安装发布仍未完成；未修改Runtime0.5.0已签候选，进程结束。

- 2026-10-08 Fish S2推理依赖冲突已解决：独立探针验证protobuf3.19.6满足audiotools/TensorBoard声明且可导入官方两个推理入口，之后仅替换Fish独立环境protobuf；标准Runtime完整依赖约束检查117分发包通过，固定fish-s2-cuda-requirements.lock，未修改校验器或依赖元数据。官方>=3.20覆盖针对训练datasets生成protobuf，后续推理Runtime必须排除这部分训练模块，不宣称完整上游训练环境等价；Torch2.10偏差仍记录。变更后六组官方codes GPU解码WAV与先前ASR通过的稳定codec版本逐字节相同。证据fish-s2-inference-dependency-lock-20261008.json；尚未profile/source导出、Worker/Host/签名发布，进程结束。

- 2026-10-08 Fish S2稳定codec参考路径重新端到端实测：直接走engine参考PCM编码，中英带参考文本、无参考文本、双说话人四项均EOS正常、ASR正文4/4通过；带参考请求实际取消后float逐值恢复、CPU/CUDA RNG保持、hook清理、六参考拒绝通过。合成参考不代表音色克隆/说话人区分质量验收。并行标准Runtime依赖闭包预检明确失败：descript-audiotools要求protobuf>=3.9.2,<3.20，而开发环境按官方Fish override使用5.29.6；未绕过检查或导出假可用Runtime。证据fish-s2-stable-reference-preflight-20261008.json；后续解决固定依赖约束及Worker/Host、长时质量/签名发布，进程结束。

- 2026-10-08 Fish S2稳定codec方案通过有限验证并接入engine：局部torch.jit.optimized_execution(False)保留官方Snake公式，六组既有codes（中英/参考/情绪/双说话人）重复解码逐值一致，ASR正文6/6通过；相对旧PCM的relativeRMSE0.008805–0.016326，明确是BF16舍入变化，不宣称与旧官方冷/热波形等价或听感通过。引擎完整原生短句生命周期复验通过：匹配稳定codec基准PCM16、实际第10次回调取消后float精确恢复、CPU/CUDA RNG保持、hook清理、EOS超限失败后恢复、close拒绝新请求。原始两次失败保留；证据fish-s2-stable-codec-lifecycle-20261008.json。新参考编码JIT策略仍须端到端复验，长/并发生命周期、质量、Runtime导出/Worker/Host/签名发布仍待完成；进程结束。

- 2026-10-08 Fish S2 codec重复性定位推进：固定同一语义codes，默认首次/后续波形max_abs0.0078125、后两次精确；新进程首次即启用确定性CUDA仍有同差异，排除简单确定性开关修复。166次叶模块对照最早差异在Snake1d decoder.model.1.block.0；实际descript-audio-codec1.0.0使用TorchScript Snake。局部optimized_execution(False)三次解码逐值精确，但输出SHA与官方冷/热路径均不同，因此只作候选，尚不接入引擎或放行生命周期；需进一步波形/内容验证。fresh-deterministic回执第二行default标签实际仍保留确定性设置，证据明确限制仅首行证明冷启动对照。证据fish-s2-codec-jit-diagnostic-20261008.json；进程结束，整体生命周期/服务发布仍未完成。

- 2026-10-08 Fish S2新增可复用原生engine：固定官方采样路径、进程内串行/RNG作用域、参考PCM边界、实际模型层取消hook、局部EOS检查、关闭接口；接受已验证官方model/codec对象，尚无正式加载factory。实机首次PCM16与官方基准精确，但取消后float逐值恢复失败；显式请求前清KV后仍失败。进一步三次诊断确认普通重复/取消后语义codes全部精确、CPU/CUDA RNG恢复，波形最大绝对差均0.0068359375，定位为codec解码可重复性，不能归因取消采样漂移。完整脚本后续超限恢复/close断言未到达，不能声称通过。证据fish-s2-engine-lifecycle-diagnostic-20261008.json；保留两次失败，下一步固定codec输入检查CUDA确定性算法，不放宽门禁；本轮进程结束。

- 2026-10-08 Fish S2官方参考/表达控制实测：固定此前中英文合成音频作参考，经官方codec.encode→带参考文本语义生成→官方decode，中英参考、happy标签、双说话人四项均正常EOS，独立ASR正文4/4归一化全文匹配。输出2.14/3.44/2.37/4.50秒，未编译生成5.80/8.64/5.98/11.42秒。首轮因TorchAudio2.10缺TorchCodec文件读取失败；r2对已验PCM16/44.1kHz WAV直接读取并按/32768归一化，保持官方codec编码输入与数学路径，原始失败保留。证据fish-s2-official-reference-controls-20261008.json；合成参考不等同真实说话人克隆验收，情绪效果和双声音区分度未评估，变速/无参考文本/五说话人/长音频/生命周期/Runtime/Worker/Host/签名发布仍待完成；进程结束。

- 2026-10-08 Fish S2官方BF16端到端实际生成通过：固定源码/原始权重，语义模型及官方CLI codec均BF16，seed42/top_p0.9/top_k30/temperature1.0/未compile；英文2.0898秒/生成7.006秒，中文2.6935秒/生成6.655秒，EOS于46/59token正常结束，独立Qwen3-ASR两项全文归一化精确匹配。加载95.04秒，峰值CUDA分配19.371/19.407GB；目前短句慢于实时，尚非优化性能验收。新增EOS完整结束检查，触及上限不记截断成功；WAV、codes、SHA完整保留。证据fish-s2-official-generation-20261008.json；Torch2.10与官方2.8差异、参考克隆/情绪/变速/多说话人/长音频/生命周期/Runtime/Worker/Host/签名发布仍开放；本轮生成与ASR进程结束。

- 2026-10-08 Fish S2独立export-venv建立并补齐官方推理依赖：transformers4.57.3/einx0.2.2、Hydra/codec/audiotools/Lightning等，未修改共享环境；仍借用GB10 Torch2.10.0+cu130而非官方2.8.0，尚非正式Runtime锁。官方DualAR语义模型358字段完整匹配、4,561,852,416参数BF16 CUDA驻留，加载99.19秒/峰值10.269GB。codec首次严格检查发现六个非持久化RoPE/mask缓存多余；核对固定源码persistent=False后逐值验证checkpoint覆盖范围均精确，再允许仅这六字段，541字段无缺失、391,430,530参数FP32 CUDA驻留，16.45秒/峰值5.220GB。原始缺依赖及strict失败保留；证据fish-s2-official-loading-20261008.json。仅官方加载验收，尚未生成语音或完成质量/生命周期/Runtime导出/Worker/Host/发布；本轮进程结束。

- 2026-10-08 Fish S2 Pro开始官方CUDA接入：固定fishaudio/fish-speech源码214da3cd及归档SHA39385029、官方原始checkpoint1de9996b；源码归档与配置/许可/README/权重索引Git摘要已校验，Spark全部11个选定文件、11008083526字节已逐摘要校验完成。实机官方导入定位loralib/hydra缺失，codec依赖与官方Torch2.8/transformers上限/einx固定版本需独立环境处理，不修改共享模型环境。新增匿名固定版本校验下载器和实机导入探针，FISH-S2-REUSE.md记录37语言选项/参考音色/情绪指令/变速/最多五说话人待验合同及官方实现优先原则。证据fish-s2-official-preparation-20261008.json；尚未实际推理/Worker/Host/签名发布。

- 2026-10-08 VibeVoice长文本Host链路实机通过：258词连续故事、默认官方剩余context预算，Carter85.2秒/Emma95.07秒WAV与固定官方原生输出逐PCM16样本0LSB；95.07秒FLAC解码亦0LSB，MP3解码2,281,600样本时长完整，固定ASR全文归一化精确匹配。真实调度4正常完成、3非法controls预期失败，running/queued归零，禁网只读容器与进程清理。探针复用短/长语料和选定格式，无生产推理算法修改。证据vibevoice-host-long-content-20261008.json；仅fixture发现下的约90秒WAV/FLAC/MP3链路，不代表十分钟自然语料、其余格式长音频、音色听感、FA2、签名安装、QuickRead和发布已完成。

- 2026-10-08 VibeVoice实际Host九种产品格式全部复验：wav/pcm/mp3/m4a/aac/flac/ogg/opus/webm经路由→真实调度租约→禁网Worker→Host编码输出，MIME/解码/短句时长通过；WAV/PCM/FLAC与官方Emma基准逐PCM16样本0LSB，九格式固定Qwen3-ASR全部完整保留原文。12正常任务完成、3非法controls预期失败，running/queued归零、槽位释放；容器及进程结束。新增全格式探针与独立ASR脚本，未改生产Host编码逻辑。证据vibevoice-host-all-formats-20261008.json；仅2.8秒短句格式/内容验收，不代表长音频编码、音色听感、FA2、签名安装、资源准入、QuickRead或发布通过。

- 2026-10-08 VibeVoice真实十分钟资源边界通过：固定官方BF16/SDPA解码14,403,200样本（600.133秒）时明确超限失败、不返回音频；耗时292.51秒、峰值CUDA分配3.032GB，CPU/CUDA RNG保持、hook清理、随后短句恢复与官方PCM16精确。重复2340词仅作资源/保护验证，不作十分钟自然语音质量验收。最新limits经标准export-r3刷新（60依赖7913文件、29运行源码6保留文件），unsigned fixture-r2隔离HTTP六声音0LSB，取消0.110秒及恢复通过；Host-r3两WAV/FLAC解码0LSB，3正常完成、3非法请求预期失败、运行排队归零。原始Host回执multipart旧标签由证据更正为实际JSON路径。证据vibevoice-ten-minute-refreshed-host-20261008.json；FA2、听感/音色、签名安装/资源准入/QuickRead和发布仍待完成；本轮进程结束。

- 2026-10-08 VibeVoice固定官方依赖环境长段落复验：Carter85.2秒/Emma95.07秒WAV与此前ASR全文通过版本SHA完全一致，耗时44.38/45.85秒，峰值2.816/2.835GB。核对官方generate发现包装器默认4096偏小、文本token在shared new-token预算被重复计入；改为官方8192减voice prefix的剩余预算，显式预算内文本与语音共享，拒绝无语音容量。新增实际decoder累计样本十分钟保护，超限失败不返回截断成功；hook在finally清理。64定向测试通过；默认预算实际短句与官方基准精确，取消/长度失败恢复、RNG与hook清理通过，缩小音频阈值的故障注入恢复通过但不计真实十分钟验收。证据vibevoice-long-pinned-limits-20261008.json；既有export-r2/HTTP/Host早于此修改，需刷新重验，十分钟质量/FA2/签名发布仍待完成；进程结束。


- 2026-10-08 VibeVoice当前Host调用链实机通过：当前omlx音频路由→ModelInvocationService JSON请求→真实WorkerJobScheduler租约→Supervisor loopback/UDS→禁网只读Worker。Carter/Emma两WAV与官方基准0LSB，Host FLAC转换经Host自带解码后也0LSB；3正常任务完成、3非法speed/voice/language请求400并计预期failed，最终running/queued均0、槽位完全释放。r1仅测试脚本缺soundfile，r2改用Host原有解码helper通过；未改生产Host行为。原始回执scope误继承multipart字样，证据明确更正实际为JSON路径。模型发现仍fixture PackageModel，不是签名安装/资源管理器准入/QuickRead验收。证据vibevoice-host-invocation-20261008.json；容器与进程已清理，长时质量/FA2/签名发布仍待完成。


- 2026-10-08 VibeVoice隔离HTTP实机通过：最新engine checkpoint路径变更经标准export-r2刷新，60依赖7913文件/28运行源码6保留文件再次校验；独立unsigned fixture-r1经真实Worker launcher与UDS认证HTTP运行。六声音输出与官方基准逐PCM16样本0LSB，非法model/seed/speed/voice拒绝，未认证health401；取消0.1131秒返回499，恢复与drain/resume后音频精确，active_requests归零。Docker inspect确认network none、ReadonlyRootfs、CapDrop ALL、no-new-privileges、uid1000:1000；finally容器清理并等进程退出。证据vibevoice-http-worker-20261008.json；这不是签名安装或实际Host/QuickRead验收，固定环境长时质量、FA2和发布仍待完成。


- 2026-10-08 VibeVoice新增共享TTS Worker适配器：复用CudaQwenTTSAdapter/OmlxTTSAdapter串行请求、线程排空、WAV响应和Host格式转换契约；固定官方BF16 checkpoint由Host指定，tokenizer/安全voice从Package resources读取，engine新增checkpoint_path分离。原生真实请求对象输出与官方基准WAV逐字节相同，upstream别名/取消后恢复精确；seed布尔、零max_tokens、非法voice、speed、中文language、instructions六项拒绝通过，取消不返回音频，stop释放engine/events并拒绝新请求。证据vibevoice-native-worker-adapter-20261008.json。仍为fixture Package/native调用，不是HTTP/Host/签名安装；既有标准source export早于本次engine路径变更，须刷新后隔离HTTP验证，十分钟质量/FA2/发布仍待完成；本轮进程结束。


- 2026-10-08 VibeVoice标准源码导出完成：构建器固定Microsoft归档SHA cbd51f45，导出未修改vibevoice源码与3运行包装器，保留MIT/README/pyproject/完整归档/依赖锁/NOTICE；28运行文件、6保留文件逐摘要通过，不把开发pickle转换器或pt预设放入运行模块目录。CLI新增成对--vibevoice-python/--vibevoice-sources与capability一致性门禁，尚未执行完整制品封装或修改已签Runtime。Python -I清除开发site路径，仅导出profile+固定core执行实际官方短句，PCM16与官方基准精确，模块来源检查通过；仍非禁网容器HTTP。新增错误归档写入前拒绝和许可保留/转换器排除测试，构建器/profile57通过(exit0，有沙箱Metal atexit警告)。证据vibevoice-standard-source-export-20261008.json；Worker/Host/长时质量/签名发布待完成，进程已结束。


- 2026-10-08 VibeVoice固定依赖接入标准CUDA Runtime构建器：新增vibevoice独立profile与ai2apps.model.vibevoice-cuda服务映射，导出前校验vibevoice-cuda-requirements.lock。Spark调用标准_copy_isolated_profile导出60分发包，7913文件逐RECORD/SHA验证，0缺失/0多余，不导出开发.pth。构建器/profile回归55通过(exit0，沙箱Metal atexit警告不计GPU证据)。证据vibevoice-standard-dependency-export-20261008.json；仅依赖profile，官方源码/包装代码导出、CLI完整Runtime封装、HTTP/Host/签名发布仍未完成；没有修改Runtime0.5.0已签候选。所有本轮实机进程结束。


- 2026-10-08 VibeVoice创建独立export-venv，对齐官方streaming依赖transformers4.51.3与tokenizers0.21.4，未改其他共享环境。标准Runtime构建器_distribution_closure验证60个依赖版本闭包并固定vibevoice-cuda-requirements.lock；当前仍通过明确development-framework.pth借用底层包，不是已导出的独立Runtime。官方六声音BF16/SDPA短句重跑WAV与旧官方基准逐字节相同；实际取消/恢复、CPU/CUDA RNG、hook清理、长度失败与close拒绝全数复验通过。证据vibevoice-official-pinned-environment-20261008.json；FA2尚缺，既有85/95秒长文本证据使用4.57.6，不能自动提升为本环境长音频验收；profile/source导出、Worker/Host、10分钟质量和签名发布仍待完成，进程已结束。


- 2026-10-08 VibeVoice官方原生引擎连续英文长段落内容通过：同一258词四段原创故事，Carter/Emma分别生成85.2/95.07秒，耗时42.77/47.31秒，峰值分配2.816/2.815GB；无异常峰值或非有限值。固定Qwen3-ASR全文按预声明忽略标点大小写空白归一化两项均匹配，未调整阈值或截短输入。原始文本、完整WAV与SHA保留；这是官方BF16/SDPA/5步/seed1234路径，无Mac数值要求。证据vibevoice-official-long-content-20261008.json。尚非10分钟上限、音色/听感、长请求取消资源验收，Worker/Host/FA2/固定官方依赖profile及签名发布仍待完成；本轮生成和ASR进程均结束。


- 2026-10-08 VibeVoice新增官方CUDA原生引擎：固定官方模型/tokenizer摘要、六声音集合与安全缓存，串行调用官方BF16/SDPA/5步路径；请求seed通过fork_rng作用域恢复CPU及CUDA随机状态。利用官方stop_check_fn和扩散头pre-hook增加取消检查，无推理数学修改。实机短句PCM16与官方基准精确；第10次回调在实际扩散阶段取消后恢复float逐值精确，CPU/GPU RNG保持，取消及长度失败后hook清除。官方reach_max_step_sample明确转为失败，不返回截断音频；close后拒绝请求。证据vibevoice-official-engine-lifecycle-20261008.json。当前为原生引擎，不是Worker adapter/HTTP/Host或10分钟验收；FA2、官方依赖闭包、长音频与签名发布仍待完成，所有本轮进程结束。


- 2026-10-08 VibeVoice官方路径发布准备推进：六个官方声音各100tensor由固定摘要可信原件一次性转换为safetensors，往返逐tensor精确；运行加载器仅读safetensors，验证SHA/键集合/形状/BF16/有限值和32MiB上限，重建独立DynamicCache。六声音请求间缓存隔离通过，摘要错/缺tensor/形状错/NaN/精度错五项拒绝通过。新增官方权重闭包检查：仅允许完整缺失的276个声学encoder tensor（官方checkpoint未提供），0推理tensor缺失/0多余，并为encoder意外执行设置失败钩子。安全声音加载后六个官方BF16/SDPA短句WAV与上一轮原件路径逐字节相同，因此已有六项ASR内容证据仍适用。证据vibevoice-official-safe-assets-20261008.json；未放宽为Mac一致性门禁，本次比较同一官方实现的资产格式无损性。FA2/官方依赖profile、长音频音色生命周期、Worker/Host/签名发布仍待完成；本轮进程结束。


- 2026-10-08 VibeVoice官方基准已实际运行：直接使用固定Microsoft代码1541f590与原始checkpoint6bce5f06、官方六声音缓存、BF16/SDPA/5步/CFG1.5/seed1234，六声音均生成完整短句，独立Qwen3-ASR六项全文匹配。输出2.13–2.80秒，模型加载后生成0.874–1.828秒，峰值约2.82GB（短句观测，非完整性能基准）。先初始化CUDA再CPU加载权重后迁移解决本次加载失败；官方预设的BaseModelOutputWithPast在当前Torch restricted loader失败，开发探针仅对固定归档摘要验证的官方原件使用trusted pickle，不接受用户pickle，正式Runtime须转换为安全tensor资产。官方checkpoint缺少encoder权重，生成源码使用decoder；正式严格加载闭包仍须落实。FA2缺失、当前transformers4.57.6不同于官方streaming可选依赖4.51.3均已记录；SDPA回退下的短句内容通过不等于音色/长音频/官方FA2质量验收。证据vibevoice-official-bf16-baseline-20261008.json；所有本轮实机进程已结束，尚未签名发布。


- 2026-10-08 用户明确调整模型验收原则：官方固定版本实现与原始权重作为算法/质量主要基准；Mac只作为产品能力、接口和辅助数值诊断参考，不要求CUDA照搬Mac量化或精度。已写入spark/AGENTS.md与VIBEVOICE-REUSE.md，适用于后续非LLM模型。VibeVoice新增651tensor主干/桥接/EOS的30项Mac诊断与六声音×三文本18项全部通过；374tensor声学解码器六项辅助诊断通过，最大relativeRMSE1.7561e-5、分块1.3540e-5。仅辅助证据，未生成移植版完整语音。固定官方checkpoint6bce5f06044837fe6d2c5d7a71a84f0416bd57e4（约2.035GB原始权重）并下载逐摘要验证，官方CUDA demo为BF16/FA2优先/5步/CFG1.5，区别于Mac4bit/20步。当前开发环境transformers4.57.6可导入固定官方源码，但缺FA2，SDPA冒烟仍在排查加载兼容性；不声称官方质量、正式Runtime/Host/签名安装或发布完成。组件记录vibevoice-backbone-decoder-official-transition-20261008.json；不因Mac对照通过而推进质量发布。


- 2026-10-08 VibeVoice Realtime 0.5B开始CUDA对齐：固定Mac 4bit checkpoint550877a1，29文件732,671,870bytes在Mac逐项与公开Hub LFS/Git摘要核对，Spark全文件SHA再次通过；固定Microsoft源码1541f590与MIT许可及Mac Runtime1.8.10的7个模型源文件摘要。新增严格70tensor扩散头和请求局部DPM-Solver++，4bit数值展开FP32（非CUDA原生打包4bit）；六个真实voice正负condition×3时刻的18项head对照最大relativeRMSE1.37e-6，1/5/20步×六voice的18项采样对照最大5.54e-6，均通过预设1%；取消第3检查后恢复精确、全局CUDA RNG不变。只完成组件，未生成完整语音；tokenizer固定、两段主干/声学解码器、6声音/10分钟质量生命周期、Runtime/Worker/Host和签名发布都待完成。VIBEVOICE-REUSE.md列明完整范围，不把额外voice文件扩为产品语言/能力。证据vibevoice-components-20261008.json；本轮所有进程结束。

- 2026-10-08 Seed-VC分钟级缺失分段已补齐：81.76秒双语拼接实测旧voice模式Mac只输出3.61秒、CUDA7.79秒；按固定上游30秒HuBERT/5秒上下文、AR总条件1500token、参考前25秒补齐两端处理，CFM按30秒窗口/16frame重叠融合。AR生成token先拼接再CFM分窗，避免无语义重叠的AR边界丢帧；分段种子为请求seed+index。新voice输出Mac79.93秒/CUDA80.38秒；CUDA三档耗时22.20/52.51/86.01秒，峰值3.75/3.75/4.20GB。两端六项短输入PCM16均保持精确。实际分钟级扩散中cancel0.468秒/stop0.984秒，事件和锁释放、无残留输出、重启后短句精确；stop后仍9.57MB allocated，未声称GPU占用归零。标准export-r4/fixture-r3隔离HTTP-r5三档短句及81.76秒timbre_fast均0LSB，禁网只读容器已清理。9定向测试通过；完整混语ASR保留5/6转换失败；按已知语言边界分段后，两端timbre共8个语言片段全部匹配原文，说明混语识别存在干扰，但voice两端共4个语言片段仍错漏词，质量未通过。最新Host-r3三档0LSB、非法controls/调度通过，返回文件与此前ASR通过的Host-r2逐字节相同；模型发现仍fixture。音色/拼接听感、自然连续录音、voice内容和签名安装发布仍未验收。本轮实机进程均已结束。证据seed-vc-v2-minute-chunk-fix-20261008.json；不把时长恢复当作质量通过。

- 2026-10-08 Seed-VC ASTRAL token精度根因确认并修复Mac独立Worker：首个pwconv1相同输入对独立FP64参考，默认MLX误差0.003518，禁用TF32后2.81e-6，CUDA1.27e-6；只在Seed-VC adapter/package首次MLX运算前设置MLX_ENABLE_TF32=0，共享Runtime及其他Worker不变。wide/narrow×speech/sweep/silence×共享特征/完整HuBERT共12项token全部精确，完整编码relativeRMSE最高0.000114。Mac包源码需未来升版/签名发布，未改已发布制品。段落三档重验仍保留CUDA timbre两项A→The失败，不放宽质量门槛。新标准export-r3的59依赖/8405文件与39源码/20保留文件校验通过，最新Mel修复进入独立unsigned fixture-r2；HTTP-r4三档0LSB、取消0.02554秒、恢复/drain通过；Host-r2三档0LSB、3任务完成槽位释放、3非法controls拒绝及全部短句ASR通过。64定向测试通过(exit0，有沙箱Metal atexit警告)，实机进程及容器已结束。证据seed-vc-v2-fp32-token-fix-20261008.json与seed-vc-v2-refreshed-worker-host-20261008.json；音色/分钟级/段落内容/签名安装发布仍开放，formal_spark_host_acceptance保持false。

- 2026-10-08 Seed-VC Mel精度门禁修复：独立NumPy complex128参考确认Mac/CUDA FP32 FFT低能量log误差分别最高0.003379/0.002761；两端保留相同FP32加窗，再用FP64 FFT/幅度/mel/log、最后转FP32。Mac用CPU NumPy（MLX不提供FP64），Spark仍GPU运算；speech/sweep/silence跨端Mel最大误差全部0，原0.001门槛未放宽，fbank/style原门禁亦通过。8.5秒全链路回归正常，CUDA10/30/voice耗时2.26/3.72/7.61秒；原timbre两项A→The内容失败仍在，Mac三档和CUDAvoice通过，未把数值修复当作质量闭环。证据seed-vc-v2-mel-fp64-fix-20261008.json；Mac模型Package源码需升版评估，旧Spark r2导出/HTTP/Host证据早于本修复，必须更新导出后重验。ASTRAL token、内容/音色/分钟级/签名安装发布继续开放，所有本轮进程结束。

- 2026-10-08 Seed-VC当前Host调用链实机通过：当前omlx音频路由、ModelInvocationService、multipart代理、真实WorkerJobScheduler与Supervisor loopback→UDS连接禁网只读Worker；三profile参考音频随源音频经48k统一规范化后正确转发，与同一规范化输入直连Worker分别50944/50944/54784样本全部0LSB。3个local_foreground任务完成、0失败、槽位释放；3组非法controls在调用前400拒绝。Host最终返回三份音频固定ASR均完整保持Hello, welcome to the voice service.。模型发现仍是fixture PackageModel，未验签安装、资源管理器准入或QuickRead，不计formal_spark_host_acceptance。证据seed-vc-v2-host-{invocation,asr}-20261008.json；容器/进程结束，既有段落2/6内容失败和Mel/token/音色/分钟级/发布门禁仍开放。

- Seed-VC标准导出profile进入独立未签名Runtime fixture，隔离HTTP实机r3通过：三profile分别59392/63488/63488样本与原生Worker基线PCM16逐样本0LSB；取消0.02413秒，恢复及drain/resume后输出精确、active_requests归零。Docker inspect确认network=none、ReadonlyRootfs、CapDrop ALL、no-new-privileges、uid1000:1000；测试容器已清理。r1因脚本repo ID误写被固定checkpoint门禁拒绝，r2输出最大2282LSB偏差；修复adapter显式关闭matmul/cuDNN TF32、benchmark并启用deterministic，使正式Worker计算条件对齐既有探针后通过，未放宽0LSB门槛。9个adapter测试通过。证据seed-vc-v2-http-worker-20261007.json；这仍非签名安装/实际Host/发布，原段落质量2/6失败及Mel/token、音色/分钟级验收继续开放。下一步实际Host调用；本轮所有进程结束。

- Seed-VC BigVGAN缺失许可证已补齐：从官方NVIDIA/BigVGAN固定提交7d2b454564a6c7d014227f635b7423881f14bdac读取LICENSE及incl_licenses/LICENSE_1..8，保留NVIDIA、HiFiGAN、Snake、alias-free-torch等文本，逐文件SHA写入seed-vc-bigvgan-licenses.lock.json。该commit只标识许可文本来源，不冒充Seed-VC代码祖先。标准导出器在写任何目标前校验缺失/摘要/路径越界，并同时保留运行目录许可和sources来源快照。r2标准依赖8405文件及源码39运行文件/20保留文件全部字节校验通过；新增缺失/篡改/越界3负例，构建器/profile共55测试通过。未改模型、未发布，完整Runtime/隔离HTTP/Host及质量门禁仍待完成。证据seed-vc-v2-standard-source-export-r2-20261007.json；本轮进程结束。

- Seed-VC标准源码导出实现完成：校验固定51383efd归档SHA，BigVGAN搬入seed_vc_bigvgan独立命名空间，11个CUDA包装/共享speaker文件随profile导出；保留GPL归档、README、共享speaker确切来源及许可证，30运行文件/10保留文件逐字节校验通过。Python -I从导出profile加载pipeline和vocoder实机生成63488样本有限音频，证明无需开发源码目录，但仍用开发core，不是隔离HTTP。标准构建器新增成对--seed-vc-python/--seed-vc-sources和seed-vc capability一致性门禁，完整CLI封装尚未跑；既有52构建器/profile测试通过。发现固定上游BigVGAN引用incl_licenses但归档未含，第三方许可证闭包仍待补齐，不宣称可发布；旧质量失败保留。证据seed-vc-v2-standard-source-export-20261007.json；下一步许可证闭包、完整Runtime/隔离HTTP/Host，本轮进程结束。

- Seed-VC已接入标准CUDA Runtime构建器的独立依赖profile（service映射ai2apps.model.seed-vc-v2-cuda），导出前强制校验seed-vc-cuda-requirements.lock。Spark标准_copy_isolated_profile实机导出59个分发包，逐RECORD校验8405唯一文件，0缺失/0多余/no .pth；核心Runtime相同版本去重保持原规则。test_cuda_runtime_builder与test_cuda_runtime_profiles合计52项通过(exit0，atexit有沙箱Metal不可用提示)。已完整读取当前发布手册；本轮仅依赖profile，不包括固定源码/许可导出、完整Runtime封装、隔离HTTP或签名发布，旧质量失败继续开放。证据seed-vc-v2-standard-dependency-export-20261007.json；下一步固定源码命名空间/许可证、隔离Worker与Host。本轮实机导出进程结束。

- Seed-VC预先固定1234/1235/1236三种子、两档timbre、Mac/CUDA共12输出的8.5秒段落内容矩阵完成：Mac6/6通过，CUDA4/6通过，原种子1234两项A→The失败保留，新增1235/1236均通过；未选择成功种子替换默认或豁免质量。另创建独立开发export-venv并用标准构建器依赖闭包固定59分发包到seed-vc-cuda-requirements.lock；初次构建器导入因缺仓库目录中的ACE锁失败，校验复用既有venv/pth后补齐标准布局成功。此仅开发依赖环境，不是标准Runtime profile导出、签名包或隔离HTTP验收。证据seed-vc-v2-seed-sweep-export-prep-20261007.json；质量/分钟级/音色/Mel-token/Runtime/Host/发布仍未完成，本轮进程结束。

- Seed-VC新增8.4985秒英语段落+独立中文参考三profile实机对照（尚非分钟级长音频验收）。Mac三档与CUDA voice内容全部保持；CUDA timbre10/30的固定ASR将A little girl改成The little girl，两项严格内容门禁失败。模型加载后CUDA耗时2.18/3.72/7.49秒，输出无异常扩长。诊断仅替换扩散noise为Mac记录值后，CUDA两档内容恢复，Mac对照亦通过，说明此样例对随机noise敏感，非正式修复；未改变产品RNG/阈值，原始失败保留。后续需多种子/更多语料，既有Mel/token、音色、分钟级、Runtime/HTTP/Host/发布门禁仍开放。证据seed-vc-v2-paragraph-noise-diagnostic-20261007.json含所有原始结果及noise SHA；本轮全部进程结束。

- Seed-VC CUDA新增原生Worker adapter：固定model/upstream别名与checkpoint revision、三profile映射、参考输入、参数校验、GPU串行锁、取消线程排空及停止释放。实机共享Worker请求对象三profile均输出，别名重复/取消恢复逐字节一致，取消0.01893秒无残留输出，stop释放pipeline/events并拒绝后续请求；9个本地参数/版本门禁测试通过(exit0，atexit有沙箱Metal不可用提示，不作为GPU证据)。新增独立英语source(IndexTTS)与中文reference(VoxCPM设计音色)三profile Mac/CUDA对照，6输出固定ASR全部完整保留Hello, welcome to the voice service.；输入SHA固定，不将独立录音等同说话人身份/主观音质验证。首次ASR脚本缺soundfile，改为直接读取既有PCM16源文件后通过。证据seed-vc-v2-adapter-cross-reference-20261007.json；标准Runtime导出、隔离HTTP/Host、长音频、音色质量与签名发布未完成，既有Mel/token失败保持开放。本轮实机进程结束。

- Seed-VC voice采样修复已同时进入Mac Package源码及CUDA pipeline：沿固定上游top_p=.7/temperature=.7/repetition_penalty=1.5替换默认纯贪心，保留greedy供对照；请求局部RNG，满4000token未EOS明确报错，不返回异常截断音频。修复后同一短句自身参考，Mac62976样本(2.856秒)/CUDA58112样本(2.635秒)，取代旧1775872样本(80.54秒)异常扩长；两端固定ASR均完整保留原文。CUDA AR阶段取消后恢复重复输出逐值相同，输入/全局RNG保持；Mac最小10token、EOS、上限失败、非法controls、局部key不污染全局随机序列均通过。独立backend随机算法不同，不宣称采样token/波形跨端精确；跨音色/长音频、Mel/token旧门禁、Runtime/Worker/Host/签名发布仍待完成。Mac源码改动需下一模型Package版本评估，尚未构建发布。证据seed-vc-v2-voice-sampling-fix-20261007.json；所有本轮进程结束。

- Seed-VC AR CUDA及完整voice路径已实现：93tensor严格载入，12层GQA/RoPE/KV缓存、贪心EOS与逐token取消；pipeline懒加载narrow/AR，恢复voice length_adjust语义。共享真实特征prefill/缓存logits relativeRMSE 0.001307/0.001263通过1%，512token与Mac精确一致，但重复464触及上限，不能视为质量通过。两端完整voice把约2.88秒输入扩至1775872样本（80.54秒），Mac/Spark耗时51.68/136.39秒。固定上游使用top_p=.7、temperature=.7、repetition_penalty=1.5，而当前Mac纯贪心；独立CUDA上游采样诊断三种子1234/1235/1236于136/135/134token正常EOS，缩小故障到采样策略，尚未验证采样后音频或修改产品默认。下一步两端采样修复及音频内容/音色验收；此前Mel/token门禁与Runtime/Worker/Host/发布仍未完成。证据seed-vc-v2-ar-cuda-20261007.json；本轮全部Mac/Spark探针结束。

- Seed-VC BigVGAN严格783张量逆布局加载及CUDA实测通过：相同真实/生成Mel的波形relativeRMSE 0.011884/0.007744，均小于预设5%。新增完整timbre链路，10/30步各生成63488样本（22.05kHz，约2.88秒），Spark模型加载后耗时1.27/1.53秒；Mac同输入0.43/0.57秒，非系统性能基准。短句自身作参考，Mac/CUDA两档输出固定ASR均完整保留原文；原生取消后重复输出精确，输入与全局CUDA RNG不变。仅短句内容/生命周期通过，不代表跨说话人音色质量或完整模型对齐。AR voice路径明确拒绝、尚待实现；此前Mel/token数值门禁失败仍开放，Runtime/Worker/Host/签名发布未完成。补齐开发环境matplotlib3.10.7及传递依赖，正式导出仍须锁定。证据seed-vc-v2-vocoder-cuda-20261007.json和seed-vc-v2-timbre-pipeline-20261007.json；本轮所有实机进程已结束。

- Seed-VC v2新增CUDA双guidance Euler采样器（cosine sway时间网格、prompt区每步归零、每步取消检查）。实际DiT固定31frames/7promptframes、相同noise/condition/style：10步无guidance/仅speaker/仅content/双guidance与30步双guidance relativeRMSE 0.002082/0.002429/0.002535/0.002972/0.003995均通过1%；第4步前取消后重跑逐张量精确，输入及全局CUDA RNG保持。此仅短采样器链路，不是完整长音频/声码器/质量验收；random_voice与zero_prompt_condition可选分支尚未实测。下一步BigVGAN及完整转换，既有Mel/token失败保留。证据seed-vc-v2-flow-cuda-20261007.json；本轮探针结束。

- Seed-VC固定13层DiT CUDA已实现并通过单步对照：140tensor严格键/形状/有限值完整加载，保留与Mac一致的未使用checkpoint字段，实际推理时间嵌入/style token/RoPE/长度mask/自适应RMSNorm/attention/MLP全CUDA。相同真实mel/style/condition与固定noise，time0有效31frames、time0.5有效23frames relativeRMSE 0.000949/0.001256均通过1%门槛。此只单步估计器，不是多步Euler/声码器或完整音频质量通过；下一步双guidance flow采样与BigVGAN。Mel和ASTRAL token此前失败仍开放。证据seed-vc-v2-dit-cuda-20261007.json；本轮Mac/CUDA探针结束。

- Seed-VC新增CUDA音频前处理：Kaldi fbank的分帧/DC/preemphasis/Povey/FFT/mel/log/中心化和22.05k Slaney Mel的反射padding/Hann/FFT/log均GPU执行，滤波器常量由NumPy构造。原音频→fbank→CAMPPlus三例style relativeRMSE 4.42e-6/2.81e-4/6.95e-6通过1%；fbank最大绝对误差0.000605/0.000757/0通过0.001门槛。Mel语音0.002544/扫频0.004603超出预设0.001，静音0，保留失败不调整门槛；完整音频前端整体1/3通过。下一步定位Mel误差并在实际生成链路评估，ASTRAL token门禁仍开放；不宣称完整模型/Host/发布支持。证据seed-vc-v2-audio-cuda-20261007.json；本轮Mac/Spark探针结束。

- Seed-VC CAMPPlus音色编码器已通过组件实机对照：复用cuda_cosyvoice_speaker架构，新增Seed专属未补零尾段平均及显式长度无偏统计池化；固定815tensor完整严格键/形状/有限值载入，神经参数全部CUDA。相同Mac fbank下speech/sweep/silence relativeRMSE 1.98e-6/1.69e-5/6.95e-6，cosine均>=0.99999976，通过1%/0.999组件门禁。未验证当前Seed的CUDA音频预处理或完整参考音色转换，不将组件相似度称为声音质量。标准Runtime导出需包含共享speaker源码与其原来源许可；未改动CosyVoice实现。证据seed-vc-v2-speaker-cuda-20261007.json；本轮Mac/Spark进程结束，ASTRAL token失败仍开放。

- Seed-VC token阈值诊断完成：相同Mac encoded输入下六例CUDA projection符号均无差异；编码路径后wide speech两bit、wide silence一bit、narrow silence一bit在接近零处翻转（最小Mac margin0.000109）。此仅缩小累计编码/投影误差范围，未证明根因或豁免token精确失败。新增严格CUDA AR/CFM discrete length regulators，固定全部张量与词表范围，原长/73/287frames六例实机全通过：AR和未变长CFM逐值相同，CFM缩短/扩展relativeRMSE约1.10e-6/1.06e-6，负数/越界token拒绝。证据seed-vc-v2-quantizer-diagnostics及seed-vc-v2-regulator-cuda-20261007.json；完整模型/Worker/Host/发布尚未完成，所有本轮探针结束。

- Seed-VC ASTRAL wide(11bits)/narrow(5bits) CUDA已实现并实测：各127tensor严格键/形状/有限值与binary mask检查，神经张量全CUDA。六例共享HuBERT特征的编码relativeRMSE均<1%(0.001563–0.006522)，但token精确门槛未全通过：wide语音/静音及narrow静音共享特征token有差异；完整HuBERT→ASTRAL wide语音2/143、静音1/49，narrow扫频3/49不一致。结果2/6完整门禁通过，不能将低连续误差当作离散内容对齐。下一步量化零阈值margin及逐层误差诊断；不调整门槛、不宣称完整转换可用。证据seed-vc-v2-astral-cuda-20261007.json；Mac/CUDA探针已结束。

- 开始Seed-VC v2 CUDA对齐：固定Mac checkpoint2122cee1、上游commit51383efd，16文件2,236,581,603bytes全部Hub摘要与Spark SHA通过。新增cuda_seed_vc_hubert.py严格MLX卷积布局转换/完整325tensor加载，保持HuBERT18输出在末层LayerNorm之前的Mac语义；实机speech/sweep/silence relativeRMSE 0.002027/0.007525/0.001569均通过预设1%门槛，全部神经参数CUDA。首次probe因Hubert feature_projection返回单Tensor而非Wav2Vec tuple失败，按实际合约修正后r2通过。SEED-VC-V2-REUSE.md列明wide/narrow量化器、CFM/AR、三profiles与Host/Runtime/发布完整门禁；只完成前端，不宣称整个Seed-VC已可用。证据seed-vc-v2-{fixed-inputs,hubert-cuda}-20261007.json；本轮下载/传输/Mac与Spark探针均结束。

- RVC预声明种子1234/1235/1236与held-out英文诊断完成：30epoch同短训练缓存，CUDA1235/1236训练中文短句ASR完整匹配，默认1234仍空；同Mac1234声音作为参照。四份声音在未参与训练的英文短句全部失败（Mac与CUDA1235误识别为日文，其余空），两条source基线均全文正确。此为10项中5通过/5失败（含2source），保留全部结果，不择种子发布。结合共享Mac噪声单变量结果，当前证据支持短重复语料/随机敏感性限制，不能把某个训练句成功称为泛化通过或直接归为CUDA架构故障。下一步较完整同音色语料与保留测试集；现有默认种子失败未解决，训练质量门禁开放。证据rvc-training-seeds-heldout-20261007.json；本轮训练/推理/ASR全部结束。

- RVC共享后验噪声受控训练通过固定ASR：保持CUDA训练/data/config不变，仅将30次训练posterior noise替换为Mac实际float16噪声张量（提升float32输入），30epoch/30step后原文完整匹配；原生CUDA噪声同配置失败保留。说明这个极短重复语料案例对随机输入（含噪声量化）敏感，尚不能排除其他数值差异或证明默认CUDA训练可靠。噪声仅诊断钩子、未进入生产adapter/trainer；不把录制噪声作为修复，不替换原失败结果。证据rvc-shared-noise-{training,asr}-20261007.json含噪声SHA；下一步独立语料和多种子质量评估，避免以一个成功seed宣称对齐。本轮进程全部结束。

- RVC同缓存Mac默认训练与交叉推理完成：实际Mac MLXRVCVoiceTrainer、FP16/batch4/30epoch/30step在相同三记录CUDA缓存上12.63秒完成；Mac训练→Mac推理ASR全文通过，Mac训练权重→CUDA推理也全文通过，而CUDA训练→CUDA推理仍为空。全部使用相同zero-noise/retrieval0.5内容探针与同一个固定ASR。证据优先指向CUDA训练差异，不能据此宣称全部推理或训练语料问题已排除；下一步共享随机输入/精度/逐步梯度更新对照。Mac/cache摘要与配置在rvc-default-training-mac-20261007.json；三向结果rvc-default-training-cross-asr-20261007.json。未放宽门禁、未发布；本轮训练、交叉推理与ASR进程均已结束。

- RVC默认30epoch safe训练实机完成但内容仍失败：FP16/FP32 master、batch4、36frames、lr1e-4、seed1234，在现有三条重复诊断缓存上30steps共27.30秒；所有训练有限值门禁通过，导出353tensors/918vectors，137280samples非零输出peak0.73739。固定ASR仍为空，与预期“你好，欢迎使用语音工作室。”不匹配，因此不能将此前2epoch失败简单归因于轮数。30epoch样本并非独立充分语料，不宣称训练收敛、音色或整体质量通过；下一步相同数据/config的Mac训练对照，定位数据/训练/导出差异。证据rvc-default-training-20261007.json与rvc-default-training-asr-20261007.json；训练和ASR均已结束（ASR因门禁失败exit1），不重试掩盖失败。

- RVC固定ASR内容验收完成但整体未通过：统一PCM16后，原文“你好，欢迎使用语音工作室。”在Mac/CUDA普通变声、retrieval0.5、升调12半音及CUDA默认路径均归一全文一致，两端静音均空；仅两epoch/6step导出声音在Mac和CUDA原生加载后的输出均ASR为空，edit distance=11。保留该质量失败，不把跨框架波形0.4%误差/声音包互通当成训练质量。证据rvc-content-roundtrip-20261007.json，12项中10项通过/2项失败（含source基线），仅一条短语的ASR内容门禁，不代表身份/听感或广泛语料。下一步按Mac默认30epoch safe训练验证内容保持与收敛，仍需充分独立数据/声音质量验收。源码复查Mac当前Worker也是返回训练Voice ZIP，没有现成通用声音库导入路径；不虚构该能力已存在。本轮ASR进程已结束。

- RVC实际Host调用层实机验收通过：用当前未改写ModelInvocationService/proxy_package_multipart、真实WorkerJobScheduler和Supervisor loopback→UDS代理替换前一轮自定义invocation桥接；仅PackageModel发现为fixture。变声/训练分别进入local_foreground/local_background，actor=local、app=ai2apps.audio-api；两项完成、0失败，结束queued/running均0、槽位全部释放。相同归一化输入变声413760samples为0LSB差异，后台训练3step声音ZIP摘要通过。未覆盖正式签名安装发现、resource manager内存准入、Quick Read、训练声音导入和听感；formal Host验收仍false。证据rvc-host-invocation-20261007.json，当前调用层源码SHA匹配，本轮进程与容器均结束。

- RVC共享Host音频路由实机r2通过：实际FastAPI路由/音频归一化/参数验证连接断网只读非root Worker，413760samples与相同归一化输入的直接Worker输出0LSB差异；训练3step返回五文件声音ZIP且SHA通过，六项无效输入在调用Worker前拒绝。检查Host proxy发现model字段实际发送upstream_id，已修正CUDA adapter同时接受固定Package ID及固定upstream ID，保留固定revision检查；6项身份/错误checkpoint单测通过。r1只用Package ID的路由桥接结果保留，r2按真实upstream转发语义复验。模型发现和invocation transport仍是fixture，尚未覆盖正式签名安装、真实资源调度、Quick Read输出、训练声音导入或听感；不计为formal Host验收。证据rvc-host-routes-http-r2-20261007.json；本轮实机进程/容器已结束。

- RVC隔离HTTP r4通过（export-r3/fixture-r3）：NetworkMode none、ReadonlyRootfs true、uid1000:1000、CapDrop ALL/no-new-privileges；同PCM16输入输出413760samples，与原生基准0LSB差异；鉴权/参数拒绝、请求取消0.00442秒、恢复及drain/resume输出精确；真实训练3step并返回五文件Voice ZIP，权重/索引SHA通过。隔离暴露并修复两处：标准source缺infer.module.transforms（最终21src/4retained），训练进度缺current/total。另保留FLOAT WAV协议拒绝证据并改用相同PCM16原生基准，未放宽任何校验。最终50依赖/7345RECORD全SHA一致、零缺失/额外/无.pth；52项builder/profile回归通过。此仍unsigned fixture，不是正式签名Runtime/Package安装Host、声音质量或发布完成。证据rvc-http-worker及rvc-standard-{dependency,source}-export-r3-20261007.json，本轮进程/容器已结束。

- RVC新增prepare_rvc_worker_fixture.py/check_rvc_worker.py，以已校验标准profile及相同core distribution inventory创建独立unsigned隔离fixture，计划覆盖network=none/read-only/nonroot、鉴权、真实HTTP变声与3step训练ZIP、请求取消、恢复及drain/resume。r1 FLOAT WAV被协议拒绝，改PCM16并生成同字节原生基准；r2暴露标准源码导出遗漏infer.module.transforms，已补入标准builder并创建export-r2/fixture-r2/http-r3重验。52项builder/profile回归通过，HTTP尚待完成；既有Runtime0.5.0不变。

- RVC标准Runtime导出已完成：既有build_cuda_torch_runtime_package.py新增rvc独立profile、精确依赖锁、成对CLI/capability门禁，以及固定81eed5e源码archive SHA门禁。仅复制六个上游必要模块、三个明确package边界和11个wrapper/lock文件，保留原archive/LICENSE/README/AI2AppsNOTICE。52项builder/profile测试通过。Spark export-r1依赖50项、7345个RECORD文件SHA逐一一致，零额外/缺失且无.pth；20源码和4来源文件摘要与固定输入一致。未构建最终签名Runtime，既有0.5.0字节不变；下一步独立断网HTTP fixture，Host/安装/质量/发布仍未完成。证据rvc-standard-{dependency,source}-export-20261007.json，本轮进程已结束。

- RVC原生Worker生命周期48954实测通过：预处理后和epoch1结束取消均无完成Voice ZIP/训练报告，恢复变声字节精确；调用方async取消等待底层线程退出，恢复精确；重复request_id拒绝、排队取消和五类错误参数拒绝通过。新增prepare_rvc_export_env.py，独立开发export-venv引用已验证开发依赖路径，使用既有标准builder._distribution_closure得到50项精确依赖锁rvc-cuda-requirements.lock；这是导出准备，不是Runtime payload，尚未执行profile源码/license导出、RECORD逐文件校验或断网HTTP。证据rvc-adapter-lifecycle-20261007.json、rvc-export-environment-20261007.json。本轮进程均已结束。

- RVC新增cuda_rvc_adapter.py和固定weights lock，接共享audio_process/audio_voice_training：严格Host checkpoint绑定、数值参数、串行GPU执行、重复请求所有权、取消/停止门禁；WAV ZIP按500files/2GiB展开上限读取并生成固定文件名，训练后只输出声音权重/索引/清单/训练报告ZIP。原生协议实机3060通过：重复变声WAV字节精确、该测试取消响应0.000365秒且无部分结果、恢复与stop/start后输出精确；训练请求3step完成，返回ZIP五文件集合和两个权重SHA一致。此仅native shared Worker协议，尚非断网HTTP/正式Host安装；训练取消各阶段、输入边界回归、标准依赖导出/完整Runtime/Package及质量仍需完成。证据rvc-adapter-cuda-20261007.json，本轮进程已结束。

- RVC Spark训练声音已通过Mac实际加载/转换：导出权重与index回传SHA一致，Mac原生pipeline输出137280samples有限波形。新增CudaRVCPipeline.load_trained_voice，先验证固定文件名/摘要/架构/全部权重与索引，再替换idle pipeline声音；CUDA同一零noise+retrieval0.5输出relativeRMSE0.0039915，长度相同，通过5%门槛。无效speaker_count拒绝后原声音恢复逐采样精确，完整架构声明验证已补齐。此为原生声音权重/索引互通，尚非正式VoiceBundle Host安装、相似度/听感或训练收敛验收；Worker/Host/export发布仍需推进。证据rvc-trained-voice-{mac,cuda}-20261007.json。

- RVC混合精度r1先完成首轮，复查修正log_mel_l1_loss禁用autocast，保证mel矩阵乘法及STFT损失FP32（r1证据保留）。r2 FP16/BF16各三真实片段两epoch/6step完成，跨epoch恢复模型和optimizer全部状态、元数据、最终loss精确一致，取消无完成报告；仅短训练数值/生命周期，非收敛或质量验收。新增cuda_rvc_voice_export.py，验证断点绑定cache后导出Mac既有tensor布局：FP32两epoch声音353tensors、918检索向量，modelSHA0f5550ab8b4251939c7b38ced2ebdd17cee6e417a7c8fb56e4b9a2a553b586be、indexSHAc637f6e78bf52141657160f2aa9649dd3a93825cc9a3aad8258ff4d067f697eb。Mac实际加载/转换、正式VoiceBundle/Worker/Host和质量发布仍待验收。证据precision-{float16,bfloat16}-resume-r2.json、rvc-voice-export-cuda-20261007.json；本轮进程均结束。

- RVC新增cuda_rvc_trainer.py，按epoch随机打乱、随机裁剪、每步局部噪声种子，cache摘要/config绑定断点，有限梯度/参数检查及取消不写完成报告。首轮恢复机制通过后查到MLX AdamW默认bias_correction=False而Torch默认开启；保留r1证据但不视为优化语义对齐。新增cuda_rvc_optimizer.py显式匹配Mac未修正偏差的AdamW，三步固定梯度与真实Mac优化器逐位一致（最大绝对误差0）。重跑两轮共6step，r2连续与恢复的最终loss、完整模型和optimizer状态树逐张量精确一致，epoch元数据精确、取消无完成报告；两轮G211.32→195.64、D62.30→203.62，不以小样本损失波动宣称收敛。证据rvc-epoch-trainer-cuda-r2及rvc-optimizer-cuda-20261007.json，本轮进程已结束。FP16/BF16仅有实现路径尚未验收；声音导出/质量/Worker/Host/发布仍待完成。

- RVC新增cuda_rvc_checkpoint.py：非可执行safetensors+typed JSON树保存模型/AdamW状态，SHA256校验、有限值校验、暂存目录完成后原子改名、拒绝覆盖已有断点。CUDA optimizer schema独立于Mac MLX schema，不宣称跨框架optimizer兼容。真实语音36frames FP32 safe-adaptation保存step1后恢复，step2与连续训练loss精确一致（G119.200233459/D14.967311859），generator/discriminator全部state tensors逐张量精确。配置不匹配与覆盖拒绝通过；独立CPU测试roundtrip、损坏摘要、NaN、任意object拒绝及失败暂存清理通过。尚需完整epoch trainer/数据shuffle及噪声续跑/混合精度/VoiceBundle，未宣称完整训练或发布完成。证据rvc-resume-cuda-20261007.json、rvc-checkpoint-format-20261007.json；本轮实机进程已结束。

- RVC新增cuda_rvc_preprocess.py，真实24kHz语音重采样、高通、3.7秒/0.3秒重叠分段和75%峰值归一化生成与Mac相同v2训练缓存。三个片段368/368/182frames，manifest及pitch bins精确相同，phone相对RMSE0.001924/0.002736/0.002381，其余连续张量<0.000009；取消不写完成manifest。抽取pipeline共享extract_content/extract_pitch后，原四例转换与默认噪声重复/取消恢复全部回归通过。使用真实缓存36frames完成两步FP32 GAN更新，G169.48→119.20，D4.24→14.97，权重确实更新且参数/梯度有限、冻结encoder保持不变；仅短更新验证，不宣称训练收敛。下一步完整trainer/断点恢复/FP16-BF16/VoiceBundle互通，Worker/Host/质量/发布仍待完成。证据rvc-preprocess-{mac,cuda}及rvc-real-training-updates-cuda-20261007.json；本轮进程均已结束。

- RVC新增cuda_rvc_losses.py，按已发布Mac实现FP32 Slaney mel/STFT、KL、LSGAN及feature matching损失。固定共享输入下六项loss相对误差全部<0.4%（generator0.1587%、mel0.3895%、其余更低）。Spark两步真实FP32 AdamW更新均完成，generator/discriminator参数确实改变、梯度及参数有限、冻结encoder逐张量不变。固定合成输入下D loss由6.94升至435.09，G loss154.94→117.75；明确只验证计算/更新，不宣称收敛或语音质量。仍需真实WAV预处理、完整trainer、混合精度、断点恢复、VoiceBundle互通和Worker/Host/发布。证据rvc-training-losses-{mac,cuda}-20261007.json；所有本轮进程已结束。

- RVC新增24秒含静音间隔的三段检索变声实测：整体波形relativeRMSE0.035513，两接缝窗口0.012547/0.013830，均通过预设5%数值门槛，1151040输出samples与Mac一致；不将接缝数值匹配称为听感验收。新增cuda_rvc_training.py，严格加载固定训练generator423/discriminator110 tensors，后验编码器按Mac的2**layer dilation而非上游默认1实现；同输入/noise下波形relativeRMSE0.005877，中间张量和9个判别器分支全部<1%。安全适配冻结enc_p/flow，所有可训练参数反向梯度有限、冻结参数无梯度、神经参数全CUDA。仅组件与backward验证，尚非完整训练；数据预处理/GAN optimizer/FP16-BF16/断点恢复/VoiceBundle互通及Worker/Host/发布仍待完成。证据rvc-long-{mac,cuda}和rvc-training-components-cuda-20261007.json。

- RVC原生完整转换r2通过：固定真实语音普通/检索0.5/升调12半音与静音四例，零latent-noise波形相对RMSE为0.011552/0.015894/0.017636/0.024748，输出长度与Mac一致，均通过预设5%门槛。新增cuda_rvc_pipeline.py严格固定输入加载、Mac高通/音高插值/protect和长音频拼接，默认噪声使用请求局部CUDA Generator。r1重复最大差0.00022067且RNG状态未变，保留失败证据；关闭cuDNN benchmark并开启deterministic后r2重复及阶段取消恢复逐采样精确，RNG状态保持。此结果仅四个native样本，长音频方法尚未实测、声音/内容质量与训练、Worker/Host、签名Runtime/发布仍待完成；原ContentVec非语音1%门槛失败不豁免。证据rvc-pipeline-{mac,cuda-r1,cuda-r2}-20261007.json；本轮所有进程已结束。

- RVC合成器Mac语义对齐28683完成：保留同一权重/输入/latent noise后，原13/31frames波形relativeRMSE由0.040403/0.040959降为0.001329/0.002370；新增31frames有声无声交替为0.003383、peak归一误差0.008027，全部原门槛通过。差异修正在CUDA生成器，未修改Mac或固定checkpoint；仍只是短组件样本，不宣称完整变声音质/实时性能/训练对齐。下一步组合已验证RMVPE、retrieval和generator，保留ContentVec非语音1%门槛未通过项并量化端到端影响。所有本轮进程已结束。

- RVC CUDA精确检索61470通过：38,924向量、19queries（语音/精确匹配/近邻），Top8索引集合19/19与Mac一致，合成特征相对RMSE0.001430；输出全CUDA，并列结果确定性、分块取消及恢复精确通过。代码复查发现Mac NSFGenerator的确定性激励（含unvoiced相位）与末层leaky-ReLU slope0.1不同于上游Torch（噪声/UV处理、末层默认0.01）。新增cuda_rvc_generator.py显式对齐Mac语义，保持固定神经权重；原始上游4%波形结果保留，正在补三例voiced/mixed复验，不先宣称误差改善。

- RVC固定Serena声音合成器CUDA7982通过两例：353tensors全覆盖严格匹配，flatten原weight-norm结构后载入，无随机缺失权重。13/31frames下encoder/flow中间相对RMSE均<1%，波形相对RMSE0.040403/0.040959、peak误差0.041588/0.047572，满足Mac既有5%波形门槛。此测试仅全voiced、共享显式latent noise、关闭上游source noise；无声激励/完整audio/训练仍待验证。新增分块精确CUDA检索cuda_rvc_retrieval.py，保持Mac逆距离平方权重，stable并列顺序和取消回调；固定38,924向量/19queries检索实测正在运行。

- RVC ContentVec逐层18953诊断完成：三例layer0相对误差约0.000215–0.000275；真实语音最终0.001812，扫频/静音逐层增长至0.024579/0.027440，未发现单次形状/键映射错误。此证据只定位累积趋势，不能证明根因或豁免原门槛；两项失败保持开放。下一步在保留该门禁的同时验证固定voice synthesizer、retrieval与完整音频路径，评估特征误差的实际影响。所有本轮下载、传输和GPU探针已结束。

- RVC ContentVec CUDA初次严格加载210tensors成功，单独保留2个v1 projection tensor；神经参数全CUDA。真实语音relativeRMSE0.001812通过1%门槛，但扫频0.024579、静音0.027440失败，原始回执rvc-contentvec-cuda-r1保留。查到Mac旧实验采用3%/cosine0.999门槛且已有约2.76%累积偏差记录；本次不以旧阈值重分类原1%失败，先采集逐层诊断。所有训练与转换集成门禁仍开放。

- RVC RMVPE CUDA79299通过全部三例：salience相对RMSE分别0.000639/0.000889/0.002153，voiced mask全部精确，最大F0误差0.06419cents；全部神经参数位于CUDA。仅恢复发布converter刻意省略的118个BatchNorm训练计数器为0，其余权重严格匹配。Mac ContentVec v2三个特征oracle已完成(143/49/49frames)，CUDA特征校验正在运行；完整转换/训练/Runtime/Host/发布仍未完成。

- 开始RVC对齐（含变声和声音训练，不缩减为仅推理）。固定已发布Mac复合checkpoint738acad9及上游81eed5e：19files/1,410,906,582bytes，公开Hub摘要及Spark传输SHA全部通过。Mac生产Package RMVPE三例oracle已生成；Spark原生CUDA严格加载及pitch门禁79299运行中，预设salience相对RMSE<1%、voiced mask精确、音高最大误差<10cents。RVC-REUSE.md记录完整训练/转换/Runtime/Host/发布门禁，未宣称已支持RVC。

- IndexTTS Host工作流长文复验通过：当前共享invoke_speech针对CUDA身份按120加权字符分成5段，断网HTTP调用保留全部原文，合并音频经同一固定ASR全文匹配（含此前错误的傍晚与结尾）。证据 indextts25-host-workflow-http-20261007.json、indextts25-host-long-roundtrip-20261007.json。此工作流使用PCM16参考；旧原生两段失败使用FLOAT参考，因此不把改善全部归因于分段的单变量因果，旧失败保留。当前仅证明这个固定Host工作流内容通过，声音相似度/情绪听感、完整签名Runtime、正式Package安装/Host与发布仍待完成。所有本轮测试进程已结束；50项builder/profile、9项adapter、50项speech/readaloud回归均通过。

- IndexTTS 断网HTTP61113通过：NetworkMode=none、readonly root、uid1000、cap-drop ALL/no-new-privileges；54528sample参考克隆与直接引擎PCM零差异，鉴权/参数拒绝、取消0.02383秒、恢复、drain/resume生成通过。发现Host ai2apps/readaloud/speech.py仅识别Mac模型ID，已加入CUDA精确服务前缀共用120加权字符分段和空长音频恢复。扩展原有Mac分段、ASR/no-ASR恢复、失败回退、深度限制及取消测试到CUDA身份，50项speech/readaloud测试通过。当前Host共享函数经隔离HTTP跑同一失败长文本，内容复验尚未完成；不是正式安装Host验收。

- IndexTTS 标准 export 终验：38项依赖、3395个RECORD文件全SHA一致，零缺失/额外文件、无.pth导出；25源码/资产、5保留来源文件与固定源逐字节一致。新增archive与frontend数据篡改门禁，50项builder/profile测试通过。发现并修正adapter资产路径：从Runtime实现模块的位置读取indextts25-data，而非Package适配器目录；9项adapter测试复验通过。独立unsigned fixture已创建，断网/只读/非root HTTP实测启动；尚未标记正式Runtime或Host发布完成。

- 开始 IndexTTS 标准 Runtime profile export：在既有 build_cuda_torch_runtime_package.py 增加 indextts25 独立 profile 与成对 CLI/capability 校验；固定 WIndexTTS commit/archive SHA、前处理数据 SHA，保留原始 archive/LICENSE/README/pyproject 和 AI2Apps 修改说明。两份前处理NPZ与固定上游逐字节相同。独立 export-venv 生成38项精确依赖锁，现有47项 builder/profile 测试通过；实际依赖导出及 RECORD 全文件校验88659正在进行。未构建最终Runtime制品，既有0.5.0字节不变。

- IndexTTS 共享语音协议实机28221完成：使用PCM16参考音频的 adapter 输出与直接引擎逐采样一致；取消信号到请求结束0.02055秒；同引擎恢复及 stop/start 后真实生成均与首次WAV字节一致。已保存 indextts25-adapter-20261007.json。engine 支持 Mac 四项采样参数，实机本轮验证默认值；其他采样组合未单独验收。慢/快样本3.460/1.730秒仅证明本例时长变化，不宣称普遍精确倍率；五种情绪内容通过不等于听感通过。下一步标准 Runtime 依赖/源码/license export 和 offline HTTP，长文本傍晚/棒篮严格失败及完整Host/发布仍开放。所有本轮实机进程已结束。

- IndexTTS 八例控制生成全部完成：语速慢/快及五种情绪共7例 ASR 全文匹配；两段长文本535098samples(24.27秒)末尾完整，但 ASR 将傍晚识别为棒篮，严格内容门禁未通过，保留失败，不以生成成功替代质量。共享 CUDA speech adapter 已实现固定 Host checkpoint、必需 reference part、请求所有权、停止门禁、Mac 情绪/语言映射和请求seed；9项针对性测试通过（退出0，Metal退出诊断不影响结果）。正式协议实测已启动；隔离HTTP/export/Host/发布待完成。

- IndexTTS 常驻引擎 resident-r1 和正式取消回调 resident-r2 均通过：首条57088sample/22.05kHz 输出与已通过 ASR 的归一化 native baseline PCM 精确相同，重复生成一致；GPT、S2Mel、BigVGAN 三阶段取消均删除部分文件，恢复逐采样一致；CPU/CUDA RNG 每次成功或取消后均恢复，已有输出不覆盖，close 清空模型与钩子。证据 indextts25-resident-{engine,callback}-20261007.json。当前语速/五种情绪/长文本八例正在 Spark 单 GPU 实测，尚无内容/听感验收结论；Worker/Host/export/发布仍未完成。

- 新增 cuda_indextts_engine.py 与固定权重/前处理 SHA lock：六个 FP32 CUDA 组件常驻、完整 wetext 归一化、Mac 120token 分段/200ms 间隔/语言 token cap、参考音频截取15秒、8轴情绪强度和 duration_factor=1/speed；非阻塞请求锁、独占输出、模块级取消检查、失败删部分文件、请求 RNG 恢复和 close 清理。check_indextts_engine.py 已在 Spark 启动真实 baseline/repeat/GPT-CFM-vocoder 取消恢复验收，结果尚未确认；不标记 Worker/Host/发布完成。

- IndexTTS 正式前处理诊断完成：Mac TextNormalizer 归一化同一三条中文文本后，CUDA/Mac 六段音频全部 ASR 全文匹配，双方 CER 0/89；seed42、参考与生成参数保持不变。证据 indextts25-normalized-{cuda,mac,roundtrip,content-metrics}-20261007.json。Spark 独立 normalizer-deps 安装与 Mac 一致的 wetext0.1.8/kaldifst1.8.0/contractions0.1.73，使用固定 upstream 原生 TextNormalizer 对十例（含日期、金额、术语、发音标注）与 Mac 输出精确一致，见 normalizer-{cuda,mac} 回执。原始关闭归一化的失败结果保留；这修正了测试前处理差异，不代表完整 Worker/Host、情绪/音色或发布验收通过。下一步将已验证前处理和六个 CUDA 组件接入 resident engine，验证取消与恢复。所有本轮进程已结束。

- IndexTTS 固定六例原始文本对照已完成：Mac/CUDA 英文各 3/3 全文匹配、WER 0；中文各 0/3 全文匹配，CUDA CER 9/89 (10.11%)、Mac 12/89 (13.48%)。仅为固定参考音频上的 ASR 内容指标，不代表听感或通用质量通过。发现原始探针禁用了正式 Mac 默认启用的 TextNormalizer；该归一化器将中文标点映射为 ASCII。下一步保持文本语义、参考、seed 与生成参数不变，单独验证正式前处理。原始失败保留。证据：evidence/media/indextts25-corpus-content-metrics-20261007.json。

- IndexTTS broadercorpus preregistered indextts-parity-corpus.json (SHA in corpus-contract receipt):3ZH/3EN includingoriginalfailure,workflow/storymulti-sentence. SameFP32/reference/seed42/beam3/topp0.8/topk30/temp0.8/repetition10/15CFMstep,caps14xtoken+8 bothbackends;normalizationseparate. CUDA24526 andMac98356 runningindependentGPUs. Preservealloutputs/errors;aftergeneration run sameASR andreport exactmatch plus per-language editrates,not inferparityfromsinglephrase.

- IndexTTS nativeMac95301/ASR79184 completed:ZH80tokens/70400samples but transcript你好，欢迎使用语音服务。行。 fails;EN fullcontentpasses. CUDAZH also80tokens but only1positionequal,consistentbackendRNGdifference(noexactsequenceclaim). Macsame-token acousticreplacement also retains extra-wordfailure. Therefore issueisnotCUDA-exclusive,butdifferenterrorsdonotprovequalityparity. Preserve allstrictfailures;next preregister broaderfixedZH/ENcorpus underbothbackends,measurefullcontent/speakerquality andcontinue residentWorker/lifecycle ratherthanfitonephrase. Alljobs terminal;formalRuntime/Host/publication remainsopen.

- IndexTTS Macsame-tokenacousticprobecompleted:codec latentrelativeRMSE0.001211,mel0.000646,fullwave0.04782(fixedmelvocoder0.009074). ASR18714 stillfailsbothMacoutputs:fullsame-token你好，既欢迎使用语音服务先。;fixedmelvocoder你好，即欢迎使用语音服务线。 SameerrorpersistsafterMacacousticreplacement,socannotattributetoCUDA-vocoderalone. Originalfailedtokens/reference/noise retained. NativeMac95301 nowrunningbothZH/EN withsamefixedcheckpoint/reference/FP32settings,seed42,beam3,samplingparams,archivingitsowncodes. RNGstreamsarebackenddifferent;notexacttokenexpectation. Noqualityacceptanceyet.

- IndexTTS trace96423 completed:ZH/EN diagnosticWAVs reproduceoriginalbytesexactly;allintermediatetensors+initialCFMnoise retained. ZHtrace downloadedforMacsame-token/same-noiseoracle. Alljobs terminal;qualityfailure remainsopen.

- IndexTTS fullnative9589 completed:ZH80codes/70400samples3.193s audio generated3.096s;EN60codes/52736samples2.392s generated2.253s,allneuralCUDA,belowcaps218/148. StrictASR84868 passesEN butfailsZH:expected你好，欢迎使用语音服务。 transcript你好，即欢迎使用语音服务线。 No acceptancereclassification. Newtrace96423 runsidenticalseed/params,archivescodes/spk/style/refmel/latent/mel/wave/exactCFMnoise andrequiresbyteidenticalWAV tooriginal;next Macsame-token/same-noise acousticdiagnosis. Pureconformer neutral path preserved. Fullresidentengine/Worker/Host/publication remainsunimplemented.

- IndexTTS first complete native CUDA probe9589 running:strictfixedsixcomponents,realreference24k resampledonCUDA,mean/variance-normalizedW2V17,CAM++,reference-derivedneutralemotion (notcalmmatrix),fixedZH/ENtokenizer,beam3/topk30/topp0.8/temp0.8/repetition10,15stepCFMcfg0.7,BigVGAN22.05k. Seed42,uncaptured/eagerGPU,checksboundednonemptycodecount<cap,finitewaveform andallneuralCUDA. This is diagnosticscript only,notresidentWorker/Host/qualityacceptance. Mustinspectterminalresult then ASR;no publicationclaim.

- IndexTTS realfrontend62519 passes fixedMacreference24k audio:16k/22.05kresamplerrelativeRMSE0.000263/0.000853,W2Vfeatures0.002067,mel0.000630,fbank0.000712;fixedMacresampledinputfeatures2.074e-6,mel0.000122. Masks andZH/EN rawtexttokenIDs/languageIDs exact. Firstprobe45790 failedmissing tiktoken;installedMacmatching0.14.0 onlyintoindependent extra-deps (7461),acceptedRuntime unchanged. CoefficientNPZ files copiedfromexactMacvendoreddata andhashesrecorded. Notnormalizer/fullreferenceconditioning orfullsynthesis acceptance. Nextassemble strictfixedcheckpointpipeline,preserveMacneutral/reference-derived emotion semantics (upstream Torch defaults calm differs),boundedgeneration andrealtext/cache comparison. Alljobs terminal.

- IndexTTS GPT strictCPU45289 passesall456tensors includingemotionconditioner,noextra transposeonconvertedLinears. MacFP32oracle2casescovers emotion/condition,prefill,leftpad,andcachedone-token. CUDA41282 numericalerrorpasses<1% (emotion0.001036,condition0.000249,logits0.006475/0.008024,cached0.003853/0.005023),but all-positionprefillTop1gatefails. Diagnostic4481 pinpointsonepositionpercase:thirdconditiontoken (positions2/4 afterleftpad),5683CUDA vs5078Mac. SameMacembeddingstillreproducesdifference;not explainedbyinputconditioningdrift. Bothlastprefillpositions andcachednextpositionsTop1exact;rawfailurepreserved,nofullGPTacceptanceclaimed. Next realtext/referencefrontend andgenerated-position teacherforcing,plusmargin/layerdiagnosis asneeded. Alljobs terminal.

- IndexTTS BigVGAN CUDA10281 completed:all667fixedtensors,allneuralparametersCUDA. Random17frame andMacCFM25frame mel inputs produce4352/6400samples withrelativeRMSE0.008479/0.005157 againstMac (<predeclared1%). This is fixed-mel componentwaveformonly,not fulltext/referencevoice acceptance. Alljobs terminal. Next GPT strictmapping+conditioning/cachedteacherforcing,thenfullfrontend/nativepipeline. Remaining nonLLMgoal unchanged.

- IndexTTS S2Mel strictCPU55587 passes259combinedDiT/lengthregulatortensors afterexplicitweightnormflattening. CUDA92407 passes2cases(single33/double48maskedframes):conditionrelativeRMSE0.000251/0.000238,velocity0.001375/0.002691,fixedMacconditionvelocity0.001375/0.002693. Full25stepCFM48572 withfixednoise passesCFG0/0.7 atrelativeRMSE0.001094/0.003883 andexactzero promptregion. Mac CFM oracle uses eager DiT (WINDEXTTS_NO_O1_COMPILE=1),not performanceclaim. BigVGAN strictCPU50106 passesall667tensors;Mac randommel+CFMmel two-waveformoracle generated;CUDA10281 running. GPT/fullreferencefrontend/integratedspeech,Runtime/Worker/Host/publication stillpending.

- IndexTTS W2V-BERT CUDA2656 completed:strict772tensors,allneuralCUDA;layer17MacrelativeRMSE0.003154(unmasked33frames)/0.006387(masked80frames),finite andbelow predeclared1%gate. CAM++/codec/W2V componentoracles accepted;GPT,S2Mel,BigVGAN,realfrontend/fullinference/Runtime/Host/publication pending. Alljobs terminal.

- CosyVoice corrected modes21037 generatedall8;ASR91335 passes7/8,8bittranscript retains你好/您好 mismatch. Slowvsfast durations4bit2.68/1.72s,8bit2.64/2.28s show directionaldifference ononephrase,notgeneralizedstyle/speed acceptance. Evidence corrected-modes-native/roundtrip retained. IndexTTS codec241tensors strictCPU83755 pass afterexplicit2weightnormflattenings;CUDA53730 exact34totalVQcodes across33/34frameinputs,featuresrelativeRMSE3.5e-8,decoded0.001423/0.001494(<1% gate),allneuralparamsCUDA. Mac W2V-BERT772tensor oracle generated2masked/unmaskedcases;CUDA2656 running. NofullIndexTTSpipeline/Runtime/Host/release claim.

- CosyVoice second-segmentcancel81718 completed:4/8both deletepartialfile and recoverbyteexact fullzhlongoutput. CorrectedRASH+losslesssegmentation sixcontentcases/HTTP/lifecycle acceptedwithin scopes;transcript/instruction revalidation,voice/style/fullHost/release remain. IndexTTS CUDA CAM++1998 passes actualreal+randomfeatures againstMacFP32:relativeRMSE2.214e-6/1.385e-6,cos1.0/0.99999988,allneuralparametersCUDA. Strict937tensors/815Macparameters+122trackingbuffers;completepipeline remainsunimplemented. Alljobs terminal.

- Corrected CosyVoice HTTP76597 passed4/8 reference generation exactPCM againstsix-case acceptednativebaseline;cancel0.00215/0.00261s,recovery/drain/resume exact,auth/parameterrejection,networknone/read-onlyuid1000/capdropALL verified. New sourcehash inventory preserved in cosyvoice3-corrected-source-export-20261007.json. Second-segmentcancel81718 running;formal Host/signature/publication and broader voice/style/modes remainpending. IndexTTS CUDA CAM++ oracle prepared usingMac realfeature+fixedrandomfeature outputs,predeclared relativeRMSE<1%/cosine>.999,not yetrunwhileGPUowned.

- CosyVoice corrected engine60144 passes all6 byte-exact PCM comparisons against accepted upstream-RAS diagnostics;losslessguard includespunctuation/quotes/decimals andmissingfinalpunctuation,degenerate repeatedtoken exclusion tested. Standard reexport75564 passes61deps/8022files+60source/27retained;freshunsignedfixture-r3 assembled. HTTP76597 currentlyrunning on correctedsource;second-segment cancellation probe prepared. 9adaptertests pass. IndexTTS Mac CAM++ oracle2cases generated from815assignedMLXtensors,122trainingtrackingbuffers explicitlyexcluded;CPUloader937strictpass. CUDAforward stillpending.

- CosyVoice upstream RAS diagnostic34367/ASR41849 completed:all6 strict full-text cases pass (4/8 x longzh,longen,shortzh),including previous4biten omission and4bitshort您好 mismatch. Corrected production cuda_cosyvoice_sampling.py tostable sort and exclude repeated selectedtoken before fallback,matching pinnedofficial rather than Mac omission. Added official80/60/20 sentence grouping with losslessguard (any unexpected text loss falls back to original fullinput). Engine preprocesses reference once,serially generates allsegments withrequestseed42 semantics,concatenates fullwaveform,retains cancellation/exclusiveoutput/cleanup. Integrated six-case PCM oracle60144 running against independent accepteddiagnostic outputs;degenerate RAS exclusion and punctuation/decimal/text preservation checked beforegeneration. Need lifecycle and standard Runtime source reexport/HTTP;oldfixture stillcontainsoldengine and cannot validate newcode. No release yet.

- CosyVoice pinned official frontend splits text at80/60 with merge20; diagnostic85927 preserves entire input andseed42. FullASR30599 now passes3of4 (8bitzh extra tail removed),4biten still omits final sentence. No production segmentation change yet. Pinned official RAS excludes repeated selectedtoken before fallback;installedMac/CUDA policy does not. Diagnostic34367 tests upstream RAS+split across4long+2short cases atsame seed,not a production sampler change. IndexTTS matching WIndexTTS source downloaded at eafb98c1b2ba46f6a608f29d8831208b89047681,archiveSHA9813d77fd70555bbcbe5b64b38ab7bad840cad0c900f9f1857912707ddfe01e3. New strict inverse-layout loader rejects hash/keys/shapes/nonfinite/nonintegral buffers;CPU meta initialization CAM++ probe16510 loadsall937tensors without randomfallback. CUDA numericaloracle/runtime/Host remainpending. First source hash command usedsystemPython withoutfile_digest;reranwithprojectPython againstsamearchive. Initialscp wrongdestinationfailed,nodataexport;corrected.

- IndexTTS remote hash verification36044 completed:all15files3,338,231,798B match Mac SHA256. Evidence indextts25-spark-preparation-20261007.json. Fixed checkpoints now available on Spark; CUDA implementation remains pending. All jobs terminal.

- CosyVoice3 long generation82479:4/8bit x zh/en all4 produce36.84–42.32s audio in16.02–17.34s,RTF0.408–0.435 with fixedseed42/PCM16reference/CUBLAS4096:8. Full ASR70718 passes4bitzh and8biten but fails4biten (missing final Thank you for listening) and8bitzh (extra 科他). Tail-only ASR51485 reproduces both mismatches; same recognizer so not an independent perceptual oracle. Strict full-text quality remainsfailed; no seed selection/truncation or normalization change. First tail script lacked soundfile; replaced crop with standard wave without dependency changes. Next Mac same-condition long baseline and official text segmentation/sampling review, preserving full text. Evidence cosyvoice3-long-native/long-roundtrip/long-tail-roundtrip-20261007.json. IndexTTS fixed Mac15files3,338,231,798B located in Dev weights cache and full conversion hashes verified; transfer36081 complete,remote fullhash36044 pending. INDEXTTS25-REUSE.md records exactMac controls/source/remaininggates; no CUDA implementation claim.

- CosyVoice3 isolated HTTP r4 (65691) passes both variants: same-environment native PCM exact, auth/invalid-parameter checks, cancellation (4bit0.002887s,8bit0.002306s), recovery, drain/resume and zero active requests; networknone/read-only/nonroot/capdropALL verified. However strict ASR72115 fails 4-bit: expected 你好 but transcript 您好;8-bit full text matches. This is a quality failure, not waived as synonymous, and cannot yet distinguish synthesis from ASR error. Evidence cosyvoice3-http-r4 and cosyvoice3-http-r4-roundtrip. Prior FLOAT-reference native matrix passed, current PCM16-reference 4-bit fails; preserve both. Next examine reference quantization/content sensitivity with fixed seed/text and independent listening/oracle, plus long-text/speaker/style gates. Full signedRuntime/Host/publication still pending. All jobs terminal.

- CosyVoice3 numerical diagnosis39752/28760 completed: native with Worker OMP8+CUBLAS :4096:8 matches both Worker WAVs exactly. Single-variable 8-bit OMP8 alone matches original baseline; CUBLAS :4096:8 alone matches Worker (max0LSB). Thus the observed difference tracks CUBLAS configuration, not export bytes or OMP. HTTP r4 now compares against independently generated same-environment native baselines at unchanged <=1LSB/RMSE<0.1 gate; original failed comparison preserved. Does not establish the internal kernel-level cause or voice quality. Full lifecycle and ASR revalidation pending.

- CosyVoice3 r2 standard export passes 61 exact dependencies / 8,022 RECORD files (zero missing or extra), 60 source files and 27 retained source/license files. 50 builder/adapter tests pass. Isolated HTTP r3 job75869: 4-bit PCM exact and cancel/recovery passed (cancel 0.00299s); 8-bit generated same-length audio but PCM max difference39,994 / RMSE6,000.529LSB, so acceptance failed, not relaxed. Fresh same OMP8/CUBLAS environment native diagnosis39752 running; original baselines/failure logs retained. No full Runtime or Package publication.

- HTTP r2 job72391 terminal:PCM16native baselines completed,but isolatedWorker model_load_failed No module named onnxruntime. PinnedCosyVoice upstream import requiresonnxruntime despiteourGPU speaker/tokenizer paths;developmentoverlay had maskedmissingdependency. Addedonnxruntime root tostandardprofile;standardclosure r2passes61exactpins,revisedlock saved,old58pin evidence retained. No CPU model fallbackintroduced. Must rerunstandarddependencyexport into freshr2 directory,reassemblefixture,andHTTP;source60fileexport alreadyverified. HTTP acceptance remainsfailed. Alljobs terminal.

- First isolatedHTTP8175 failed correctly at unsupported_audio_format because development reference WAV subtypeFLOAT is outside transportPCM contract;Worker startup/auth succeeded. Preserved r1logs. No transport relaxation. New PCM16reference+bothvariant matchingnative baselines prepared;serial baseline+HTTP r2 job72391 running. HTTP probe paths immutable r1/r2,comparison uses exactsamePCMreference. Sourceexport remains accepted;offlineHTTP acceptance not claimed yet.

- CosyVoice3 standard source export completed:60runtime source files and27retainedsource/license files fullSHA match;26fixed input files pinnedin cosyvoice3-sources.lock.json. Standardbuilder now pairs --cosyvoice3-python/--cosyvoice3-sources with declaredcapability,rejects undeclaredpayload;source/notice corruption/pathescape tests added,47builder/profiletests pass. Independentfixture49276 assembled with exactcoreinventory equality. HTTP8175 running networknone/readonly/nonroot onstandard58dependency+60source export with reference multipart,4/8nativePCM,auth/validation,cancel/recovery/drain/resume. Firstscp wrongdestination failed withoutcopy,corrected. No productionRuntime/Package build orpublication.

- Upstreamlicense retrieval4452 completed:Chatterbox5de7a54a MIT/Resemble2025,S3Tokenizer9bf5d845 Apache2.0,3D-Speaker065629c3 Apache2.0. Fulltexts andSHA/URL/immutablecommit provenance retained underupstream-licenses andevidence/media/cosyvoice3-upstream-license-provenance-20261007.json. Retain alongside exactMacsource snapshots/copyright andMLXMIT;latestupstreamlicense snapshot isnot a claim ofexactMacsource revision. Alljobs terminal;next standard sourcecopy+CLI/profileacceptance tests.

- CosyVoice3 standard dependency export32439 completed via existing _copy_isolated_profile:58distributions,7620unique selectedRECORD files allSHAequal,zero missing/unexpected,no.pth exported. Uses isolateddevelopment interpreter and existingcore distribution inventory;source/wrappers not yet included,no finalRuntime/HTTP claim. Receipt cosyvoice3-standard-dependency-export-20261007.json. Installed MLXsource references absent licenses/chatterbox.txt ands3tokenizer.txt;official MLXrepo tree70f4add3 also lacks thosefiles. Retrieving original upstreamlicense snapshots atimmutablecommits,explicitlynot asserting they identify exactMacsourcecommit. ExistingMITMLXlicense retained. Sourceexport/CLI wiring/fullRuntime remainpending.

- CosyVoice3 export preparation:read complete publication runbook incl6.4/7 (missing truncated line reread);created independent export-venv with explicit development framework paths and copied5extra-dependency packages,without modifying accepted Runtime. Standard builder _distribution_closure passes58exactpins savedcosyvoice3-cuda-requirements.lock +dependency-closure receipt. Added isolatedprofile registration and required exact-lock verification to existing build_cuda_torch_runtime_package.py;45existing builder/profile tests pass(exit0,local Metal atexit diagnostic). Full profile CLI/source export and license closure stillpending;no Runtime tar/Package built or published,no existing0.5digest changed. Need retain upstreamsource+MLX/Chatterbox attribution before source payload,then standard fileexport/full-byte verifier/offlineHTTP. All remote tasks terminal.

- CosyVoice3 actual adapter97994 completed:4/8bit reference multipart generation matches resident native PCM exactly;request cancellation returns in0.00103/0.00317s aftercancel signal,same-engine recovery byteexact;variant switch and actual inference afterstop/start also byteexact. Exact Host S3 dependency resolution exercised via shared model-worker context. Receipt cosyvoice3-adapter-20261007.json. This is development adapter,not isolatedHTTP/completeHost orRuntime acceptance. All processes terminal;next standard isolatedRuntime export and offlineHTTPWorker;longtext/speaker/style quality andpublication stillopen.

- CosyVoice3 adapter integration preparation found inherited synthesis_options passes numeric speed;Mac engine converts CosyVoice speed to qualitative instruction. Fixed same thresholds/wording in CUDA adapter while preserving shared emotion+instruction order and passing engine speed1.0;9targetedtests pass. Actual shared-protocol adapter97994 running bothvariants with declaredfixedS3,reference multipart,nativePCMbaseline,cancel/recovery,switchandstop/start generation. Development-only worker-models JSON derives existingMac declaration withCUDA IDs;not signed/published Package. Next standard Runtime isolated dependency/source closure after protocol acceptance;no parallelGPUjobs.

- CosyVoice3 resident stages91931 completed:4/8bit x LM/Flow/vocoder cancel at fifth targeted module call,all6 delete partial output and recover exactPCM(max0LSB/RMSE0);both engines close with models/hooks removed. Report cancel_request_seconds includes pre-cancel work,not cancellation latency. New cuda_cosyvoice_adapter.py reuses shared serialized CUDA TTS protocol,strict Host model/S3 revision+declared dependency,required reference,request/stop protection,Mac shared qualitativecontrols,request seed andOOM release.8targeted adapter admission/dependency/ownership tests pass;localpytest exit0 had non-failing Metal atexit diagnostic. Adapter nativeHTTP/Worker and Runtime export not yet tested. All GPU jobs terminal;remaining media scope unchanged.

- CosyVoice3 resident4bit engine81611 passes actual inference:59520samples/2.48s audio generated2.3566s after loading;cancel at100th neural callback propagates,partial output removed;fresh request on same engine reproduces PCM exactly(max0LSB,RMSE0),close removes models/hooks. Receipt cosyvoice3-resident-engine-20261007.json. This cancellation occurs early in reference encoder;LM/flow/vocoder cancellation stages and8bit resident,adapter/offlineWorker/export/Host/longvoicequality remain pending. All jobs terminal.

- CosyVoice3 shared official prompt matrix1336 and ASR58979 completed:all8 (4/8bit x zh/en cross,zh transcript,zh instruction) generate and exactly match normalized full target text at unchangedseed42. Earlier missing-boundary failures retained. Evidence cosyvoice3-official-native-matrix and official-matrix-roundtrip. Establishes short content/mode correctness,not speaker similarity/style realization,long text orRuntime/Host. Resident4bit engine81611 now running baseline,cancel100th neural check,partial cleanup,recovery andclose. Engine output preservation uses exclusive create;all-component resident loading and fixedfile verification are not yet accepted until probe completes.

- CosyVoice3 official8case matrix1336 running through shared prepare_speech_prompt helper;first5native cases completed successfully. Added resident cuda_cosyvoice_engine.py and Runtime-owned fixed hash lock for bothspeech variants plusS3. Validates every fixedfile,keeps allCUDA components resident,reference required/bounded,request RNG/prompt priority,exclusive output creation,per-module cancel hooks,CUDA sync before request release,partial output deletion and close cleanup. Real lifecycle probe prepared but not run while matrix owns Spark GPU. Engine is development implementation,not accepted Worker/Runtime;tests and8bit lifecycle pending.

- Official prompt comparison7693/ASR95424 completed:unchangedseed42 4bit zh and8bit en now both normalized exact target text;8bit en stops normally. Fixed official example.py prefix/boundary omission is a demonstrated contributor to these2failures. Added prepare_speech_prompt central helper:official default prefix+endofprompt,reference transcript after boundary,explicit instruction priority clears transcript/speech LM reference;prompt excluded from spoken length limits. Helper still awaits integrated all-mode revalidation;2cases do not prove broad quality. Earlier failures preserved. All jobs terminal;next use helper for4/8 xzh/en/transcript/instruction matrix and resident lifecycle.

- Mac8bit original token->CUDA acoustic84827 and ASR38553 completed but content still fails:zh extra G prefix,en repeats Hello. Stronger lead from pinned official CosyVoice commit074ca6dc example.py lines76/81/86:zero-shot/cross/instruction all include You are a helpful assistant. plus endofprompt boundary;installed Mac wrapper omits default prefix. Added diagnostic-only --official-prompt preserving original seed42 and old artifacts;4bit zh/8bit en probe7693 running. This changes prompt construction,not kernels/checkpoints or success gate;no acceptance until ASR. Cross default prefix provided as prompt_text so target length bounds remain based on spoken text.

- CosyVoice3 original Mac8bit token acoustic probe84827 running serial zh/en. Development integrated probe accepts diagnostic Mac tokens only when source did not hit its length limit and text matches exactly;records token_source,never substitutes for native CUDA sampling acceptance. Mac8bit zh and CUDA8bit zh both112tokens but sequences differ (0of first20 equal),consistent with different backend RNG streams. All previous content failures preserved;same seed alone is not a cross-backend RNG oracle.

- Same-token ASR49801 terminal:both Mac fixed-mel/source and Mac flow/same-source audio transcribe 主持人你好，欢迎使用语音服务。,exactly the same extra prefix as CUDA. Therefore this sample extra prefix persists after swapping both decoder and Flow to Mac;not explained by CUDA-only Flow/vocoder computation. Excitation is shared and untested,so do not overclaim exhaustive root cause. Next common-draw sampling comparison and original Mac sampled-token decode,plus excitation fixed-noise oracle. Quality gates remain failed;all jobs terminal.

- CosyVoice3 same-token acoustic Mac51912 completed:real218frame flow mel relativeRMSE0.004774;fixed CUDA mel/source decoder waveform0.010648 exceeds prior1% component gate;Mac flow+sameCUDA excitation waveform0.488479 (phase-sensitive full-waveform difference),retained not accepted. Strict Mac loader required deterministic stft_window plus explicit vector-alpha reshape matching existing Snake broadcast;first2probe failures retained. This oracle shares source excitation and cannot validate excitation. Two diagnostic WAVs submitted to same ASR49801;content comparison pending.

- CosyVoice3 same-token acoustic diagnosis started:integrated probe now archives tokens,prompt mel/speaker,explicit noise,generated mel/source/audio in nonsecret NPZ;diagnostic90523 completed without overwriting original failure cases. Mac acoustic76133 running on identical4bit weights/token/reference/noise with strict vocoder weights:compare Flow mel,decoder with same CUDA mel/source,and Mac Flow mel with same source. Shared excitation intentionally isolates decoder and does not validate excitation. Next compare ASR across both diagnostic WAVs;quality/release remains failed.

- Original Mac RAS sampling45455 terminal:seed42 4bit zh240/en160 tokens both reach original20x limit (Mac generator silently ends at cap),8bit zh112/en109 stop below cap. Saved full token sequences in cosyvoice3-mac-native-sampling-20261007.json. This is upstream Mac speech-sampling baseline,not waveform/ASR quality,does not establish CUDA failed content is acceptable. CUDA explicit limit error intentionally avoids claiming truncated success. Next same-token Mac/CUDA acoustic decoding to isolate content before changing sampling. No live jobs remain.

- CosyVoice3 real-text teacher-forcing oracle69438 completed:4/8bit x zh/en x21positions=84,embedding exact,all84 Top1 equal for full and cached Mac-vs-CUDA;full logit relativeRMSE0.001306–0.001725,cached0.001446–0.002098. CUDA and Mac cache-vs-full each retain all21Top1 with expected FP16 differences. Evidence narrows diagnosis but does not prove full sampled parity or excuse failed ASR. Original Mac RAS sampler45455 running atseed42 for shared text to provide same-token acoustic comparison;no kernel change based on these results. All Spark GPU jobs terminal.

- CosyVoice3 native modes89682 terminal:4bit transcript8.52s,4bit instruction2.44s,8bit cross zh4.48s,4bit cross en2.60s WAVs generated;8bit transcript fails sampling20x length limit. ASR13642 strict content fails all4:transcript repeats reference sentence before target,instruction 您好 instead of 你好,8bit zh omits 你好,English repeats Hello. All failures retained in cosyvoice3-roundtrip-modes-20261007.json and native-modes receipt;no acceptance by seed selection or normalization relaxation. Next diagnose real text/prompt teacher-forced Mac-vs-CUDA speech-LM logits/cache rather than rely on previous4speech-token-only component oracle;then fixed-noise vocoder and full same-token audio comparison. All jobs terminal;not releasable.

- CosyVoice3 first complete waveform ASR61756 failed strict normalized content:expected 你好，欢迎使用语音服务。 but transcript 主持人你好，欢迎使用语音服务。 Extra prefix retained in cosyvoice3-roundtrip-first-20261007.json;waveform generation is not content acceptance. Native probe now supports explicit4/8bit,transcript/instruction/cross modes and immutable case outputs. Serial5case probe89682 running (4/8 transcript,4instruction,8zh cross,4en cross) to locate mode dependence. Model source confirms reference transcript has no endofprompt marker;instruction appends marker. No runtime/Host/release claim.

- CosyVoice3 integrated4bit Chinese reprobe50165 completed:real reference66speech tokens,generated109tokens,flow218mel frames,24kHz104640samples/4.36s WAV,15.37s full cold pipeline,finite,all vocoder neural parameters CUDA. SHA23523ee6ff92e396c2c3e47c2d1f02bf9c26740f6e3e649a847884524e1bb9a3. Native no-transcript/cross-lingual path now produces complete waveform;not ASR/perceptual speaker quality,mode coverage,Worker,Host,Runtime or release acceptance. Artifact artifacts/cosyvoice3-cuda-preparation/integrated-4bit-zh.wav;receipt evidence/media/cosyvoice3-integrated-4bit-zh-20261007.json. Next ASR and fixed-noise excitation oracle,then transcript/instruction,4/8bit English and lifecycle. All jobs terminal.

- Integrated CosyVoice3 first probe23365 reached vocoder then failed on upstream non-state_dict meta rand_ini. Inspection also proves upstream causal cached uniform noise differs from Mac per-call Gaussian excitation. Added explicit synthesize_hifigan with request-owned generator,Mac phase/nearest upsample/Gaussian excitation and trained source linear+tanh;no global RNG mutation or random checkpoint substitute. Reprobe50165 running. New excitation path still requires fixed-noise Mac numerical oracle;first failure retained.

- CosyVoice3 full reference frontend implemented using actual Mac Model.generate semantics:24k30s cap,librosa trim600/300/top_db60,scipy FFT16k resample,symmetric Hann,compat S3 final-frame crop,flow80mel1920/480/fmax8000. Real reference CUDA31219 passes original0.001 relative gate:trim exact,resample2.77e-7,S3mel0.0001695,flowmel0.0001579. New complete native cross-lingual/no-transcript4bit Chinese probe23365 running through S3,speaker,speech LM,flow,HiFiGAN with fixed checkpoints;not yet waveform/quality acceptance. Releasable frontend tracked;no accepted Runtime changed.

- CosyVoice3 token-to-mel conditioning implemented for finalized batch1:strict token/device/finite/length validation,explicit2:1 reference alignment,normalized speaker projection,lookahead/repeat and prompt crop. RealCUDA probe97258 passes fixed Mac oracle:mu relativeRMSE0.000462,speaker1.23e-7,conditioning exact,10-step croppedmel0.004008 (unchanged1% gate). Synthetic reference mel plus real speaker embedding is component evidence,not full speech quality. Four4/8bit zh/en text-ID sequences match installed Mac tokenizer exactly despite same regex warning on both;8bit English seed42 stop-limit failure remains. Authoritative full Model.generate imports log_mel_spectrogram_compat (drops last STFT frame),not the similarly named non-compat helper;use compat in full reference frontend. All jobs terminal;next full reference mel frontend and integrated waveform.

- CosyVoice3 speech sampler probe12537 completed:4bit zh109/en65 tokens and8bit zh112 tokens stop normally;8bit English seed42 reaches unchanged20x text-token limit and raises explicitly,retained as failed case. Both variants cancel at4th callback and recover exact Chinese tokens with request-owned RNG/cache. RAS/tokenizer mirror fixed Mac policy; Transformers emits a tokenizer-regex warning,so text-token oracle remains required before any tokenizer patch. No waveform/content/voice quality claim. Speaker/frontend and sampler evidence saved; full reference frontend,token-to-flow orchestration,integrated TTS and lifecycle/Runtime/Host/release remain pending. All GPU sessions terminal.

- CosyVoice3 CUDA CAM++ speaker encoder now strictly loads all815 tensors with no CPU ONNX/zero-embedding fallback. Real speech fixed-feature relativeRMSE0.001747,cosine0.99999857; same16k waveform through CUDA Povey/HTK frontend+CMVN+CAM++ relativeRMSE0.001759,cosine0.99999845;fbank relativeRMSE9.234e-5. Both unchanged numeric gates pass. Reference trim/resampling and full TTS remain separate. Added bounded request-owned RNG/cache speech sampler preserving Mac nucleus/RAS and extended stop-token rules,with cancellation and explicit length-limit failure. Real4/8bit zh/en token probe17329 running; first probe manifest lookup failed before loading because4bit is downloaded rather than installed,log retained. No speech/audio quality,Worker,Runtime or publication claim.

- CosyVoice3 flow330/330 tensor strict mapping/load passed (73983);dedicated development extra-deps overlay pinsx-transformers2.11.24,omegaconf2.3.0,antlr4-runtime4.9.3,einx0.3.0,frozendict2.4.7 without changing accepted Runtime. CUDA component4012:lookahead relativeRMSE4.16e-7 passes;DiT single-step0.011323 exceeds0.01 gate,retained failure. Explicit-noise cosine Euler/CFG implementation avoids global RNG mutation;10-step20520 passes relativeRMSE0.003229,maxabs0.06395,same [1,80,16]shape;cancel at4th check and identical recovery. Mac first probe default512input mismatch corrected to manifest80,original log retained. Strict loader uses pinned official DiT/PreLookahead directly;no Matcha training imports required for this inference path. Components do not prove real TTS quality. Next speaker encoder,reference preprocessing,speech-token sampler and integrated audio;single-step/tokenizer differences still open. All sessions terminal.

- CosyVoice3 HiFiGAN stage trace located first mismatch in STFT (Mac zero padding vs official Torch reflection). Explicit adapter subclass preserves Mac zero padding; unchanged7680sample waveform gate now passes relativeRMSE0.005101/maxabs0.002057 vs original0.012175 (1% threshold unchanged); original trace/failure retained. New strict speech-LM loader accounts292parameter tensors per4/8-bit checkpoint, expands168affine layers toFP16 and materializes deterministic nonpersistent RoPE inFP32 (first meta-buffer move failure retained). Native36456 passed both full/cached4-token runs; maxcachelogitdifference0.01172/0.00977,top1matches. Mac oracle19413 passes relativeRMSE0.000991/0.000959,all4positions Top1 and Top10 sets identical. Scope fixed speech embeddings only,not sampled TTS quality. Flow needs dedicated x-transformers/omegaconf/Matcha setup; speaker encoder/full generation/lifecycle/Runtime/Host/release remain. All probes terminal.

- CosyVoice3 tokenizer long-window probe29219 completed:3000/3101/5201mel frames yield750/776/1251tokens with exact lengths but1/1/2 token differences vs unchanged Mac single-window + merge oracle. Mixed batch matches CUDA serial;3 invalid-length cases rejected. Mac batch defect remains; this is repeated-speech boundary evidence,not natural long-reference quality. HiFiGAN246/246 tensor name/shape coverage and strict loading pass using pinned official source; new CUDA loader verifies SHA, reverses fused conv layouts and materializes deterministic Hann window after meta construction. GPU pitch-predictor50417 passes FP32/FP64 relativeRMSE1.94e-6/3.87e-6. Fixed-input full decoder98071 produces correct7680samples,finite,all neuralCUDA, butrelativeRMSE0.012175>0.01 gate (maxabs0.005491): retained failed gate; waveform parity not accepted. Next diagnose decoder stages, then remaining flow/LM/speaker encoding and complete TTS. All probes terminal.

- CosyVoice3 CUDA S3TokenizerV3 implemented with SHA-checked strict198-tensor load,FP32 CUDA parameters,explicit conv axes,RoPE/FSMN/FSQ and30s/4s window logic. Short,padded-single and real-speech mel cases preserve all token IDs/lengths (speech73tokens). Intermediate relativeRMSE0.00191–0.00334 exceeds original0.001 gate: not full numerical acceptance. Layer trace locates difference at first linear; independent FP64 oracle gives CUDA relative1.26e-7 vs Mac6.23e-4,max1.08e-6 vs0.002277. Keep accurate CUDA math; original failure retained. Existing Mac batch2 mask broadcasting fails, recorded separately; long-window/batch/lifecycle remain unverified. No full TTS/Runtime/Host claim. All probes terminal.

- CosyVoice3 preparation: official074ca6dc and exact Matcha gitlinkdd9105b3 pinned;4/8-bit plus S3TokenizerV3 transferred and Spark full SHA verified10files/3,604,165,611bytes.4-bit was fetched at fixed HF revision;8-bit/tokenizer reuse installed Mac bytes.672 affine first/last-row checks across168quantlayers x2variants pass exactly with FP16 rounding. Native CUDA/Worker/Runtime/Host/quality/publication remain unimplemented; see spark/COSYVOICE3-REUSE.md. Preserve mandatory reference audio, instruction priority and no implicit STT downloads. All transfer/probe sessions terminal.

- VoxCPM2 Mac Runtime1.8.10 long-text baseline65426 and same-ASR check90896 completed:all4 normalized full transcripts match too. Mac36.80–44.96s audio generated18.08–22.18s (RTF0.483–0.493);Spark40.32–50.72s generated47.66–60.43s (RTF1.172–1.191). Different sampled speech lengths are retained; no cross-device waveform/style parity claim. Evidence voxcpm2-mac-long-native-20261007.json and voxcpm2-mac-long-roundtrip-20261007.json. All probes terminal. Next implementation candidate CosyVoice3 has4/8-bit checkpoints plus required S3TokenizerV3; preserve reference-audio requirement and optional transcript semantics.

- VoxCPM2 natural long-text probe80817 and ASR73185 completed:4/8-bit Chinese/English 40.32–50.72s, generation47.66–60.43s; all4 normalized transcripts exactly match complete inputs including endings. Full WAV decode,48000Hz mono PCM16,frame counts and SHA checks pass. Mac same-text baseline65426 is running; voice/style/perceptual quality remains pending. Standard builder signed CUDA distributions4bit991dc1fd…(5files/275pieces/2,300,904,017bytes) and8bitf517e799…(5files/385pieces/3,225,461,623bytes), metadata_verified with local full bytes and fixed MS metadata; neither submitted nor published. Full signed Runtime/Host/product audit/release remain pending; immutable Runtime0.5 unchanged.

- VoxCPM2 HTTP6028 completed under standard56-dependency/42-source profile:4/8-bit plain speech and authorized multipart reference clone pass against deterministic native PCM (4-bit plain sparse1LSB bound; other3cases exact).Cold24.12/17.99s,clone5.33/4.19s,cancel0.0365/0.0384s,same-engine recovery and actual generation after drain/resume pass.Offline network none,readonly,uid1000:1000,capdropALL,no-new-privileges verified.Receipt voxcpm2-http-worker-20261007.json,adapterSHA3750bc301e9d7e8979a1d45aab7b9aebd6395f96c799add83bbf1fd53204a786.25 targeted plus45 builder/profile tests passed.4/8-bit unsigned CUDA distribution specs preserve existing fixed HF/MS sources and Apache terms; not signed,submitted,published or referenced by formal Package. Full signed Runtime/Host and broad voice/style/long-text quality remain pending. All probes terminal.

- VoxCPM2 standard Runtime builder now has explicit capability/paired source+interpreter inputs, pinned official archive hash, retained license/source archive and Runtime-owned weight lock.56 exact dependencies; standard export12276 passed42sourcefiles/7597full-byte checks against accepted environment/source.45 builder/profile tests passed. Independent unsigned fixture46600 assembled from accepted core plus standard VoxCPM2 profile. Adapter numeric admission now handles multipart integer strings and returns400 before loading;25 targeted tests pass. First HTTP client failed before creating Worker due missing host soundfile; replaced probe decoder with stdlib wave, no Host dependency changes. HTTP6028 now running; no HTTP/Host/publication acceptance claimed.

- Deterministic VoxCPM2 ASR90580 completed:all8 plain/design/reference-clone cases exactly match normalized input text. Receipt voxcpm2-roundtrip-deterministic-20261007.json. All GPU sessions terminal; next gate is dedicated Runtime export and isolated HTTP Worker using latest OOM-safe adapter, followed by formal Host/quality/release.

- VoxCPM2 deterministic native8-case baseline23349 completed. Adapter54399 passed both variants through actual TTS protocol,request cancel(4bit0.0215s/8bit0.0268s),same-engine recovery,variant switch and actual stop/start generation.4-bit full-waveform recovery differs on133samples by1PCM16 LSB(max1,RMSE0.03650);8-bit recovery and restart are byte-identical. Original byte-exact failures preserved; acceptance explicitly uses same48000Hz/shape,max1LSB andRMSE<0.1LSB rather than claiming bitwise4-bit repeatability. Native/adapter evidence archived. Added OOM release/reload path with21 targeted tests passing; OOM change is unit-verified and awaits next real isolated Worker snapshot. ASR90580 revalidating deterministic8-case content; Runtime export/HTTP/Host/release remain pending.

- VoxCPM2 Adapter first cross-path SHA check failed:4-bit WAV has identical48000Hz/107528sample shape,135samples differ by exactly1PCM16 LSB (RMSE0.03543LSB). Saved diagnostic receipt. Same-adapter post-cancel byte equality also failed, so lifecycle acceptance remains unproven. Deterministic CUDA algorithms/CUBLAS workspace were enabled; this changes sampled native output length, so old baseline cannot be used as a same-config oracle. Independent deterministic native8-case baseline23349 is running, to be followed by matching-config adapter and ASR revalidation. Preserve all prior receipts/logs; no Worker/Host/publication completion claim.

- VoxCPM2 resident engine now uses Runtime-owned fixed 4/8-bit weight locks, request-scoped native module checks, CUDA synchronization before ownership release, bounded inputs and exclusive output ownership/cleanup. Real resident93967 passed mid-network cancellation at100th check for both variants, removed partial output, fresh-callback recovery reproduced native hashes,close removed hooks/model. TTS adapter reuses existing speech protocol and serialized CUDA runner, adds exact Host checkpoint selection and Mac qualitative speed/emotion/instruction controls, rejects duplicate requests/stopping work.20 targeted engine/adapter/shared lifecycle tests pass. Actual adapter66699 is running; no isolated Worker/Host claim yet.

- VoxCPM2 Mac-padding component recheck86569 completed:VAE encoder max8.34e-6/relativeRMSE1.22e-6;decoder now exact15368sample shape,max1.264e-4,relativeRMSE0.00683;BF16 feature encoder relativeRMSE0.01012 remains documented,not bitwise parity. Native r2 eight cases (4/8-bit x zh/en/design/reference clone) all real CUDA48kHz passed;duration2.24-3.52s,generation1.94-4.16s,peak5.80GB. ASR80469 exactly matches normalized input text for all8. These establish native content only,not speaker/style similarity,long text,lifecycle,Worker,Runtime export,Host or production publication. All GPU/probe handles terminal.

- VoxCPM2 strict development loader now accounts for all1,326 Mac tensors, loads811 inference tensors with strict=True and verifies9 computed rotary buffers (max5.96e-8). Removes unused logvar via explicit mean-only inference encoder, no random substitute. Both4/8-bit checkpoints generated real48kHz Chinese/English audio with all neural parameters CUDA; packing currently expands toBF16. Fixed-input comparison exposed official-vs-Mac odd-stride VAE padding mismatch (encoder relativeRMSE19.35%,decoder15360vs15368samples); retained failure and implemented explicit Mac padding behavior, component recheck86569 running. First source module naming failure also retained. Native generation alone is not quality/Worker/Host acceptance.

- AVTR standard FP32 60s probe99465 completed:1,500frames25fps,879.99s generation,CUDA peak6,541,899,776bytes,zero fallback,engine close passed. SHA f562368fbe843d24e4ba9674448b102dadc304b48a683281f586ccb7858553fd. Independent complete decode passes all frame timestamps,512x512 and16k mono audio SNR44.72dB/512AAC padding. Six time-spaced images retain identity/background and speech motion. Scope remains repeated-speech max boundary,not broad natural long-form quality. No GPU jobs remain; formal Runtime/Host/release gates pending.

- VoxCPM2 checkpoint copy30875 and remote verification42475 completed:10files5,526,365,640bytes match Mac hashes; official source import passes. CPU/meta target inspection81625 maps811of813 tensors by explicit names/layouts; two fc_logvar parameters removed by Mac require an explicit inference path, and nine rotary buffers still require computed-value checks. No native CUDA synthesis claim.

- VoxCPM2 preparation: fixed official source f0c787f0937dc1c9a8f4f64d9a332d9c5da2e629; freshly hashed Mac 4/8-bit checkpoints (2.301/3.225GB). New affine decoder matches MLX exactly on 1,012 first/last-row cases covering every quantized layer. This is a conversion primitive, not packed CUDA inference; full layout mapping, native synthesis, Runtime/Worker/Host/release remain pending. Checkpoint copy30875 live; AVTR standard60s99465 remains the only Spark GPU job.

- AVTR fast HTTP71052 completed:standard36.28s/fast12.51s both exact native hashes,fast cancel0.012s,standard-after-fast and actual fast-after-drain/resume pass in offline readonly nonroot sandbox. Mac60s reference51190 completed; full1500-frame comparison41243 meanPSNR42.53dB,min41.33dB,all timestamps aligned; six samples show matching identity/mouth/eyes/pose through59.96s. CUDAfast60s took366.38s,peak3.361GB,no fallback. These are repeated-speech boundary and fixed-identity evidence,not broad natural60s quality. Separate standardFP32 1500-frame probe99465 now running; only active Spark GPU job. No Runtime/Package production publication.

- AVTR1500-frame/60s fast native61491 completed with zero FP32 fallback and closed engine. Complete independent decode proves1500 exact25fps frames,512x512 and mono16kHz audio SNR44.72dB,512AAC padding samples. Six time-spaced frames preserve identity/background and show speech motion; not natural long-speech/lipsync acceptance. Standard fast export90697 completed25distributions2822verifiedfiles19sourcefiles; fast HTTP71052 running with both modes/cancel/resume. Parallel Mac60s reference51190 uses separate Mac GPU on identical repeated speech. No Package publication or formal Host claim.

- AVTR fast Worker wiring implemented: standard/fast explicit per-request selection and reset,approximate/fallback output metadata;36 parameter,ownership,and nonfinite fallback tests passed. Standard exporter refreshing fast source with exact existing25 dependency pins in independent fixture90697.1500-frame native boundary61491 confirmed live~900frames; no second GPU workload started. Fast HTTP probe prepared to verify both baselines,fast cancellation,standard after fast and fast generation after drain/resume. No formal fast Worker or60s completion claim yet.

- AVTR fast decoder43677 passed Mac-derived approximate gate on real inputs: FP16scaled256 Conv median~0.084s vs FP32~0.432s; preserves FP32 bias/residual/norm. Synthetic fastCUDA-vsFP32 PSNR58.91dB but fastCUDA-vsMacFast40.72dB retained as cross-backend stress difference. Native fast50frames59439 passed12.52s vs standard30.11s,zero fallback; switching back reproduces standard SHA f366d6c8. Four nonfinite/cancel fallback tests pass; standard builder retains new fast source/provenance (export refresh pending). Complete short-video comparison: CUDAfast-vsstandard meanPSNR42.94dB,vsMacfast42.36dB,matching sampled mouth/eye/pose. CUDA fast/standard decoded audio identical; cross-platform exactAAC sample assertion failed,source-waveform SNR45.62dB on both backends passes preserved-driving-audio check.60s/1500frame boundary probe61491 currently running on repeated reference speech,not natural long-form quality evidence. Worker still rejects fast until its integration/acceptance.

- AVTR fast decoder prototype now mirrors Mac scaledFP16 Conv (input/256,output FP32*256;bias/residual/normalization FP32) with persistent channels-last weights and fixed-op rejection. Actual Mac fast decoder oracles generated for animal,human,and synthetic features. Real Spark component numerical/performance probe launched; Worker still rejects fast pending full acceptance. Existing standard Runtime/Worker and signed candidates unchanged.

- AVTR Host-default HTTP62860 completed: current adapter31c0f57c accepts all Mac declared standard default fields, first generation36.49s matches native SHA f366d6c8,auth/bounds/cancel/post-cancel and actual drain/resume generation pass under standard25-dependency AVTR Runtime profile. Receipt avtr-host-defaults-http-worker-20261007.json. CUDA distribution envelope independently verified using authenticated Index116 Publisher key fingerprint216f5256; candidate is not submitted/published. Next remaining AVTR gates include fast mode,60s boundary and broader quality,full signed Runtime and formal Host/package install. No live AVTR GPU or build sessions remain.

- AVTR standard-profile HTTP13470 completed: baseline SHA f366d6c8,36.96s cold,cancel0.061s,post-cancel and actual post-resume inference pass in offline readonly nonroot sandbox. Signed CUDA distribution builder18607 completed dist_ai2apps_avtr1_cuda_57bfb656_v1, digest457727dda1c98bf7edf3757271270f221e1b47ed752839c109ed7706e1a676ad,30files2,549,026,222bytes304pieces,HF/MS metadata_verified; preserves original conditional composite license/consent. Candidate only, not Registry published or referenced by Package. New Host-default parameter compatibility fix accepts exactly declared resolution/ratio/output_format/audio mode, rejects unsupported alternatives, preserves flat seed;14 adapter tests pass. Full-default HTTP revalidation launched with new adapter snapshot; prior accepted fixtures preserved.

- AVTR standard export6968 initially failed byte-equality solely on source-provenance.json; retained the failure. Explicit comparison70673 proves2820 exported files identical to accepted execution fixture and only adds pipeline lineage metadata;25 exact distributions. New independent avtr-profile fixture completed, standard HTTP test launched. Independent portable-decoder ONNX CPU reconstitution shows Mac stress max2.31743e-4 vs ONNX, while CUDA vs same ONNX passes unchanged1e-4 (stress5.73397e-5,real-input1.13249e-6). This triangulates backend numerical differences without claiming fresh original upstream ONNX verification or erasing the Mac stress mismatch. No inference CPU fallback, no tolerance change.

- Standard Runtime builder now supports explicit avtr capability plus --avtr-python, dedicated25-distribution exact lock, reviewed CUDA wrappers, retained AVTR source provenance/licenses and unchanged-helper hash verification.43 Runtime builder/profile tests pass, including missing license and changed retained helper rejection. Actual Spark standard profile export and byte comparison launched; not yet accepted and no signed Runtime replacement/publication. Existing signed0.5.0 candidate remains unchanged.

- AVTR isolated HTTP Worker54302 completed exit0: first standard inference36.64s incl cold setup exactly matches native human baseline SHA f366d6c8; invalid bounds/auth rejected, HTTP cancel0.041s, post-cancel and actual post-drain/resume generation match baseline. Offline readonly nonroot/capdrop/no-new-privileges sandbox inspected. Receipt avtr-http-worker-20261007.json. Fixture inherits byte-verified Echo dependency profile; AVTR dedicated standard export, fast mode,60s boundary/quality, synthetic decoder stress, formal signed Host installation and publication still pending. All AVTR runtime sessions are terminal.

- AVTR resident engine61469 completed: fixed22-file checkpoint verification, mid-decoder cancellation drains CUDA in0.00147s for this injected node-boundary cancellation, then a new callback succeeds even while old callback remains cancelled. Recovery MP4 matches independent human baseline f366d6c8.160-frame6.4s generation94.52s,close passed. Independent complete decode proves160 CFR25fps frames and102400 audio samples at16kHz. This does not establish60s maximum or general temporal quality. Worker adapter implemented with controlled paths/Host checkpoint/serial owner and rejects unverified fast mode;25 admission,adapter and lifecycle tests pass. Independent unsigned HTTP fixture54275 remains running; no HTTP acceptance yet.

- AVTR resident engine added fixed22-file Runtime-owned hash lock, bounded parameter/audio admission, request-scoped cancellation rebinding and CUDA synchronization before ownership release.12 admission/security tests passed (corrupt same-size weights, symlink escape, hash cancellation and invalid parameters). Real mid-decoder cancellation/fresh-callback recovery/160-frame probe launched; no new acceptance claim yet. New user grant covers current related Package publication via Dev Cookie; standard exact-DB Runtime0.5 query96647 still failed database locked before submission. Explicit live-method override requested because AGENTS path-only restriction conflicts with current runbook preference; no live Cookie read performed.

- AVTR native full CUDA chain passed two fixed inputs: s22 is an animal sample (not a human portrait), s42 is a visually confirmed photographic human portrait. Both50frame/25fps/2s outputs independently decode with exact CFR and preserved16kHz mono audio (SNR45.62dB,768AAC padding samples recorded). Mac reference comparisons: animal meanPSNR48.07dB; human42.57dB. Four sampled frames visually retain corresponding mouth/eyes/pose; not full lipsync/temporal quality acceptance. Native chunk-boundary cancellation cleans partial output; fresh generation after cancellation is byte-identical to independent baseline SHAe1688cf2. Full-source reference CUDA throughput ~1.6–1.8fps,peak~6.5GB. Channels-last decoder diagnostic halves warm decoding time (~.43→.19s) but synthetic stress error remains~2.33e-4; optimization is not activated. All probes terminal. Worker/Host/long-video/Runtime export/distribution/release and synthetic stress parity remain open.

- AVTR decoder diagnosis: Mac per-node trace195 nodes is bit-exact to original reference. FP64 CUDA does not resolve synthetic input error (max2.33427e-4); sampled node differences grow through late decoder blocks. Independent real portrait s22 three-component renderer passes unchanged1e-4 threshold (decoder max1.13249e-5). Synthetic stress failure remains open. Full CUDA audio-to-video development pipeline implemented with Mac CPU geometry/provenance/licenses retained, CUDA-only neural operations and serial source-canvas encoding; initial probe failed missing PyAV before inference, retried using existing isolated Echo export environment. Not a production Worker/Host acceptance.

- AVTR CUDA graph74710 passed HuBERT,motion_extractor(all7outputs),appearance_extractor at5e-4. Remaining graph7959 passed landmark106,landmark203,insightface_det,stitch_network,warp_network; decoder failed1e-4 gate(max2.27153e-4,mean4.79276e-6). Mac reference initial detector640 input failed because actual AVTR pipeline uses512; corrected probe only, preserved failure. Explicit Mac arithmetic for InstanceNormalization tested88664, decoder still fails(max2.22325e-4,mean4.78097e-6). Tolerance unchanged. Eight of nine graph components pass plus prior motion network; no full video/Worker/Host. Next diagnose decoder layerwise/convolution rounding before acceptance. All GPU sessions terminal.

- AVTR constrained CUDA portable graph executor implemented for actual locked graph operators with early unknown-op rejection, CUDA neural operations and last-use temporary release. Mac oracle generated for HuBERT1x8400, motion extractor1x3x256x256 and appearance extractor; real Spark parity probe launched. No component graph pass yet, no full-video claim. Runtime publication method override still pending.

- AVTR portable copy35351 completed. CUDA probe6655 rehashed all22 files and passed five condition outputs at5e-5 plus four-Euler-step motion at2e-4 tolerance against identical actual Mac MLX inputs. Final maximum error1.54972e-5,mean2.221e-6; all weights CUDA,peak627646464bytes,component test1.204s including load. Receipt avtr-motion-cuda-parity-20261007.json. No full avatar video/Worker/Host claim: HuBERT and8 detector/render graphs plus full lifecycle remain next.

- AVTR native CUDA motion port cuda_avtr_motion.py implemented from the reviewed213-line Mac model: same condition encoder, rotary/rms/CFG and Euler schedule with Torch CUDA tensors; no neural CPU fallback. Syntax check passes, numerical acceptance not yet run. Mac fixed-input reference generation launched via existing MLX model; portable checkpoint copy35351 remains live. Nine renderer/audio graphs and full pipeline remain unimplemented.

- AVTR original /private/tmp checkpoint paths are empty, so original-input rehash failed missing HuBERT; no false reuse claim. Located actual installed Dev Registry distribution directory c3278655 under Library/Caches/AI2Apps/.../models--Avdpro--AVTR-1-MLX/distributions. Fresh portable manifest verification passed22 files/2,548,975,525bytes; receipt avtr-portable-inputs-20261007.json. Selected weights+manifest copy to Spark avtr-cuda-preparation/models started, no app-state/Cookie copy. Native CUDA implementation and original tensor-identity verification remain pending.

- EchoMimic published-layout HTTP75555 completed exit0: exact171.34s/fast57.85s reproduce native SHA, cancel0.313s, post-cancel and actual post-resume generation pass, offline readonly nonroot sandbox verified. Saved echomimic-published-http-worker-20261007.json. No live GPU probes remain. AVTR-1 next-source inventory saved with10 original hashed-asset declarations and9 portable graphs plus motion; AVTR-REUSE.md records CUDA/component/Host gates, no Spark execution claim. Runtime0.5 browser-live method override remains unanswered; no broadened Cookie access.

- Final published-layout standard export90174 completed: all53 exact pinned dependencies validated,25 source files and6436 profile files equal the current10-weight-file candidate. Receipt echomimic-published-profile-export-20261007.json. No changes to signed Runtime0.5 r2; Echo profile belongs to a future full Runtime candidate.

- Published-layout HTTP75555 exact171.34s and fast57.85s match accepted video hashes; cancellation0.313s, remaining recovery/resume still live. CUDA checkpoint envelope independently verified against registered Publisher key from trusted public Index116. Standard ten-file profile re-export/full-byte comparison90174 launched. Runtime0.5 exact authorized Cookie DB query86440 again failed database locked before network; no submission. Asked explicit user override to allow same exact Runtime/SHA via standard --browser-live because user AGENTS allows only DB path. Pending answer; no live Cookie access performed.

- Standard signing39595 completed: dist_ai2apps_echomimic_v3_cuda_c04fb474_v1, manifestDigest sha256:62a03e7fc3b291252ad2cadaf67a7fa66443c32285edb0aa424c89348c2dcd39,15files20,766,374,281bytes/2476pieces, metadata_verified HF+MS. Envelope and verification receipt retained under spark/artifacts. This is signed candidate only, no Registry submission/publication; exact Cookie authorization has not been requested for this distribution. Published10-file HTTP75555 still live; formal Host/quality/release gates remain.

- Published-layout candidate46050 completed; GPU HTTP75555 is live. Exact15-file checkpoint snapshot69170 completed with fresh10-file tensor rehash and5 small anonymous HF license/metadata downloads. Standard distribution builder33170 rejected snapshot directory basename (required full revision), before any envelope/publication. Corrected owned snapshot layout to artifacts/echomimic-distribution-snapshots/c04fb47465c0c615681b7d927256f6d5a3a314cc; standard signing retry39595 running with same spec/Publisher/key. No Cookie access, new identities or release mutation.

- Standard EchoMimic HTTP48701 completed exit0, including actual post-drain/resume generation with baseline SHA554987af, exact/fast/auth/bounds/cancel/recovery and sandbox checks. Receipt echomimic-standard-http-worker-20261007.json. New published-layout candidate46050 completed with exactly10 hashed weight files; Runtime lock now matches these published files after full tokenizer identity proof.26 targeted adapter/recovery/cache/media tests passed. Accepted12-file fixtures remain unchanged. Published-layout HTTP next serial GPU probe launched; fixed15-file local distribution snapshot69170 preparing by rehashing existing tensors and fetching only5 public license/metadata files. No signing/publication performed.

- Published-layout tokenizer62129 completed: complete backend JSON SHA49813a9a matches four-file fixture, same special map/IDs/model_max_length and10 multilingual/truncation cases. Prepared unsigned/unpublished echomimic-checkpoint-distribution.json for CUDA model identity with existing immutable HF/MS15-file sources; no new upload, signing, publication or Package distribution reference.10-file real checkpoint acceptance is next before activating this layout. Standard-profile HTTP48701 now passed exact167.11s and fast58.15s baseline hashes plus cancellation0.318s; post-cancel and post-resume generation still running.

- Exact53-dependency Runtime lock passed against actual Spark echomimic-export-venv.40 builder/profile tests passed including wrong/missing/nonexact lock and bad source digest rejection. Anonymous standard Registry verifier confirmed existing Mac Echo distribution at Index116 with digestd9d41bf8 and registered Publisher/key.10 published runtime files match hashed CUDA inputs exactly; two extra fixture tokenizer files are not in distribution. CPU tokenizer probe proves published tokenizer.json/config reproduce entire fast backend, special IDs/map and max length plus10 multilingual/truncation cases exactly. CUDA model-ID binding still needs its own proper distribution; existing MLX ID cannot be relabeled. Current12-file Runtime lock is preserved until a10-file checkpoint real acceptance is prepared. Standard HTTP48701 first exact passed167.11s/SHA554987af, remaining lifecycle runs live.

- EchoMimic Runtime dependency lock validator now rejects nonexact pins, wildcard versions, missing distributions and version drift before exporting. Added7 targeted builder tests;40 builder/profile tests pass. Existing source archive digest mismatch is rejected before extraction. Standard-profile HTTP48701 remains live in CUDA loading; do not restart. Exact53-dependency validation against the Spark export environment launched.

- EchoMimic HTTP38126 completed exit0: exact163.93s cold and fast57.57s both native-baseline MP4 SHA; cancellation0.316s and post-cancel exact recovery passed; invalid parameters/auth checks passed. Sandbox network none/read-only/capdropALL/no-new-privileges/uid1000 confirmed. Drain/resume endpoints passed but post-resume generation was not included; next standard-profile probe explicitly adds it. Standard export53 distributions/25 source files/6436 full-byte matches to fixture; source/legal retained. Builder now checks exact dependency lock,33 builder/profile tests pass. Independent standard fixture41273 preparing; signed Host/release/quality remain pending.

- EchoMimic HTTP38126 first exact generation passed (163.93s including cold load), output SHA554987af exactly matches native baseline; fast/lifecycle still running. Standard CUDA builder now supports mandatory paired --echomimic-python/--echomimic-sources with declared capability, fixed archive SHA, retained license/source and per-file source inventory.33 existing builder/profile tests passed. Dedicated dependency/source export62756 completed; full-byte comparison against executing fixture launched. No signed Runtime replacement/publication.

- EchoMimic unsigned Runtime fixture32620 completed (8575 profile files, inherited accepted ACE dependencies plus pinned Echo source and isolated PyAV/OpenCV/imageio overlay). Authenticated HTTP no-network/read-only sandbox probe38126 launched; live Worker reached CUDA Transformer loading. No HTTP inference pass yet; preserve this session and inspect before any restart. Follow-up must verify generation after control resume, not only the resume endpoint.

- EchoMimic CUDA Worker adapter implemented: Host-selected checkpoint, Runtime-owned fixed12-file hash lock, strict multipart reference/parameter validation, controlled output/recovery paths and serialized native owner with cancel/stop drain.30 adapter/lifecycle/recovery/cache/codec tests pass. Independent unsigned HTTP fixture creation32620 running; HTTP acceptance script prepared, not yet executed. Source/profile export, Host and release remain pending.

- EchoMimic real CUDA exact recovery39969 completed exit0: interruption after step3 resumes only4–8 in50.64s; interruption after step8 runs no denoise steps and decodes/muxes in15.54s. Both MP4 SHA554987af match the independent uninterrupted baseline exactly. Wrong-seed recovery rejected without changing checkpoint; checkpoint removed only after successful output; engine closed. Receipt evidence/media/echomimic-recovery-native-20261007.json. Native exact/fast/long/recovery lifecycle now accepted for the fixed reference; Worker/Host, cross-identity/lip-sync quality, Runtime export and publication remain pending.

- EchoMimic recovery/media/cache targeted tests:16 passed. Independent fast81 and long161 full-frame/audio decode passed (25fps, original mono16kHz, audio SNR46.21/46.11dB). Real checkpoint step3 replay passed exact video SHA554987af; step8 boundary acceptance still running.

- EchoMimic resident long161-frame lifecycle passed; fast mode passed cancellation,16 CFG calls/6 computed steps,57.64s versus exact72.17s, and return-to-exact SHA554987af matches baseline. UniPC CPU recovery after steps1/3/7/8 is tensor-exact and rejects mismatched request/schedule. SafeTensor recovery is now integrated with model/source/input fingerprint and atomic writes; real CUDA step3/8 replay running39969, not yet accepted. Worker/Host/quality/export/publication remain open.

- EchoMimic resident26838 incrementally passed cancellation at step2 (21.09s whole request, not cancel latency), partial output/hook cleanup, then81-frame recovery71.38s with SHA554987af exactly matching prior independent512 baseline. Long161frame phase remains running. Implemented fast-mode bridge because pinned upstream Pipeline omitted cond_flag and incremented TeaCache per model call: explicit conditional/unconditional pairs,one timestep counter,FP32 distance matching Mac,threshold.15/skip2,window-owned residual cleanup. Nine CPU/media tests pass, including pair mismatch/cancellation/short-window failures. Engine fast path integrated locally; real fast probe prepared but not launched while resident GPU test runs. Exact checkpoint recovery remains pending.

- EchoMimic native768 completed27762 exit0:81frames768x768,load79.35s,pipeline208.70s,peak24719323648CUDA bytes. Independent full decode passed exact25fpsPTS/3.24s/16kHzmonoAAC. Added cuda_echomimic_weights/media/engine resident implementation: strict fixed native loading,exact single-window plus Mac81/80 overlapping-window seam blend,per-module cancellation hooks,finally hook/scheduler/VAE-cache cleanup,request-owned partial MP4. Four real codec/output-ownership tests passed. Fast preset/recovery explicitly unimplemented,not silently approximated. Resident real cancel-step2/recovery/161frame long probe26838 now running; no lifecycle acceptance yet. Receipts echomimic-native-768-mac-media and echomimic-native-768-decoded (20261007).

- EchoMimic native512 Mac-media11362 completed exit0: strict all five CUDA networks,81frames512x512,8steps,load83.11s,pipeline71.64s,peak21,076,485,120 CUDA bytes. OutputSHA554987af5d1a994b9513d781cd148dcbf13e4628b75cbe1693012f573ace7544. Independent full decode passed81frames/exact25fpsPTS/3.24s/16kHzmonoAAC,46.21dB audio SNR vs original,384codec padding samples recorded. Mac frame comparison meanPSNR20.69dB (not parity); four-frame visual review retains subject/book/glasses/background, mouth poses broadly similar but blink/pose differ; full lip-sync/cross-identity quality pending. Native768 Mac-media27762 now running. Evidence echomimic-native-512-mac-media, echomimic-native-512-decoded, echomimic-mac-cuda-frame-comparison (20261007). Worker/Host/release still incomplete.

- EchoMimic Mac reference video located and independently SHA-verified against pipeline-m3.lock.json:67e2a48c048ddba42218093f00b6eb9a1f3427707ebf9cea9c3fdceae8aa7911. Prepared compare_echomimic_video.py for complete81-frame decode metrics plus four-frame side-by-side review, without claiming pixel parity across RNG/backends. Mac-media512 probe11362 remains live (PID1807881), observed actual denoise3/8. Independent decoder and H264/AAC preflight are ready; no completion claim yet.

- EchoMimic native512 task80872 completed all8 denoise steps (~56s) and finite VAE decode but failed final mux because host ffmpeg is absent; no completed video acceptance. Added explicit PyAV18.0.0 only to EchoMimic dependency overlay and independent H264/AAC preflight passed. Probe now uses PyAV and preflights before model load. Mac comparison found crop-before-LUFS and rounded RGB semantics; new native-512-mac-media-r2 run11362 uses these with separate directory, prior failure retained. Independent full video/audio decoder prepared, including exact CFR81frames and explicit AAC tail-padding accounting. Generation remains running.

- EchoMimic first native video probe53814 ended before main(): official src.utils required imageio and cv2 absent in ACE development environment. Added fixed imageio2.37.0 and opencv-python-headless4.11.0.86 with --no-deps into EchoMimic-only dependencies directory; ACE environment unchanged. Native512 baseline restarted80872 with explicit dependency PYTHONPATH, log native-512-r2.log. No completed generation yet; full Runtime closure still required.

- EchoMimic full strict probe95502 ended at audio key mismatch after Transformer/VAE/T5/CLIP stages. Fixed official ForPreTraining→base encoder mapping: strip wav2vec2 prefix, explicitly exclude exactly7 pretraining-head tensors, map legacy weight_g/v to current weight-norm parametrization only when required. Audio-only strict CUDA check2347 passed; receipt echomimic-strict-load-audio-20261007.json. Full native512px81-frame8-step video probe53814 now running (native-512-r1.log); no generation acceptance yet.

- EchoMimic12-file checkpoint copy54241 completed exit0. Full file rehash and strict five-component CUDA load started95502; process1799624 confirmed live during T5 stage. Full native81-frame512px probe prepared in check_echomimic_native_video.py with exact fixed inputs/eight-step callbacks,all five neural modules CUDA,TeaCache off,H264+16kHz mono driving audio. Not yet run. ECHOMIMIC-REUSE.md records source/weight evidence, explicit baseline differences and remaining long-video/recovery/Worker/Host/release gates.

- EchoMimic fixed-image CUDA component forward passed5949: CLIP1x257x1280 in0.340s, VAE mode encode/decode512x512 in0.337s, all outputs finite/CUDA. Initial probe incorrectly passed32-channel Gaussian moments into16-channel decoder; corrected to public encode().latent_dist.mode(), no upstream/model change. Receipt echomimic-visual-forward-20261007.json. This is component execution only, not full video or perceptual acceptance. Checkpoint transfer54241 remains live; no other GPU task.

- EchoMimic new Spark progress: existing Mac T5(242 tensors) and CLIP(784) Safetensors exactly match every original PTH tensor after original fixed SHA verification. VAE Safetensors SHA matches the historical Mac decoder parity lock; fresh original-PTH identity not asserted. VAE194 tensors and CLIP784 tensors strict-load onto CUDA2.10cu130 successfully. Native CLIP constructor cannot use meta initialization because it calls to(cpu); validation now preserves official construction, no missing/unexpected keys tolerated. Receipts echomimic-converted-tensor-identity-20261007.json and echomimic-strict-load-visual-20261007.json. Fixed-image component forward running90042; full checkpoint transfer54241 still active, no full-video acceptance.

- Authorized Runtime0.5.0 standard Publisher query40843 ended before network access: exact Dev Profile SQLite database is locked. No Cookie value printed/exported, no alternate Profile tried, no submission created, no publication. Preserve grant for this exact candidate; user AGENTS requires exact database path, so do not silently switch to browser-live. Independent EchoMimic checkpoint transfer54241 continues.

- EchoMimic fixed source archive SHA verified on new Spark; all six native model/pipeline imports pass using existing ace-step-venv without dependency changes.12-file20.77GB Mac checkpoint transfer is running in exec session54241. Runtime0.5.0/SHA20092284 Cookie permission was explicitly granted this turn; exact current Dev app-shell Profile confirmed from process arguments. Standard publisher query running40843; no publication/submission or audit approval performed.

- Combined signed Runtime r2 product audit completed on Spark: signature valid, no static findings, decision review because local_ai_auditor_not_configured. Audit-only probe never installs/approves; active Runtime digest unchanged. Receipt combined-runtime-signed-audit-r2-20261007.json. Exact Runtime0.5.0/SHA20092284 Cookie authorization requested and pending; no Cookie read or publication.

- EchoMimic CUDA preparation started: official clean source fixed to7e89489ca51c0d008fc1963ec6c03fc5bd0b9397, archive SHA88a87dfac7d1c4df4f706a026621f6ae4b3b8280f987aa6546e1314eba36d023. Existing Mac12 selected files20,770,911,185 bytes hashed; Flash/Wav2Vec bytes match upstream lock. VAE/T5/CLIP safetensor conversion identity remains to verify. Historical sibling Spark benchmark is provenance only; new Spark inference has not run. Independent checkpoint copy launched to echomimic-cuda-preparation/models; no sibling changes. Receipt echomimic-cuda-source-inputs-20261007.json.

- Combined Runtime r2 signed candidate completed and independently verified: ai2apps/runtime-cuda-torch 0.5.0, SHA256 200922842b44e6f6ef763e568c556dbfb9f42e6510f7e810b543edfa33b4cdf5, 3,906,220,347 bytes (within 4 GiB). Existing registered Publisher fingerprint matched. Receipt: spark/evidence/media/combined-runtime-signed-r2-20261007.json. Standard Installation-session publisher query returned active user session required; no Cookie read, submission, publication or approved installation. Product audit and formal Host acceptance remain open.

- Combined Runtime r2 unsigned build completed: inner tar.gz3,921,834,611 bytes, SHA86682691851c1bfe57621988c4cf83756ba70e02dad0d66df858bdc8150fd04e, logical unpacked8,398,707,575 bytes. Production tar materializer into fresh combined-media-extracted-r2 passed all103,219 file-byte comparisons plus2,821 H3 inventory entries; Mac transfer full hash/size verified. Existing Publisher key public fingerprint re-derived and matched; standard signed candidate build is running in exec session19869 at artifacts/runtime-0.5.0-combined-r2. No Cookie read, publication or install. Final outer size/signature verification and product audit/Host gates remain pending.

- Combined Runtime r2 export audit passed: all11 profiles have identical runtime bytes to their accepted fixtures; seven license/README relocations are byte-exact and six pinned Diffusers README restorations accounted.32,119 core Python/framework and26 app files match baseline; H3 has only the expected retained new builder-source difference (cmp verified), no native payload drift. Stable Audio combined HTTP acceptance passed and all3 WAV hashes exactly match independent fixture. ACE-Step combined HTTP passed instrumental/lyrics, auth/bounds, cancel0.204s, recovery/drain/resume against raw Host weights. Containers removed. Archive job52548 remains active; full tar/outer artifact size, signing, registry installation/Host and broader quality gates incomplete. Evidence under combined-runtime-*-r2-20261007.json, stable-audio-combined-worker-r2 and ace-step-combined-worker-r2.

- Combined candidate r1 terminated before archiving: standard FlashHead source digest gate correctly rejected the old Lite-only patch0bd7fdcf. Corrected input snapshot r2 uses the already-verified Lite/Pro patch11c0c020; all other snapshotted inputs unchanged, r1 retained for diagnosis. Standard stage-only r2 build launched under exec session52548, work runtime-0.5.0-combined-media-candidate-r2; no signed artifact or installation changed. Full size/equivalence/regression gates remain pending.

- Started full combined media0.5.0 unsigned stage-only build via the standard builder from immutable input snapshot artifacts/combined-runtime-source-r1, remote work runtime-0.5.0-combined-media-candidate-r1. Existing signed0.5r3 and installations preserved. All current core dependency names/versions match baseline exactly; all24 Worker Python files match baseline byte-for-byte. Nine media profiles plus existing TTS/H3/NVFP4 declared only in candidate snapshot. Build process is still running (exec session63502); final size, full profile equivalence, combined inference regressions and signing/install/publication remain unverified. Operation receipt and build log are on Spark under combined-runtime-candidate-r1-*.

- Combined-media delivery sizing: nine profiles individually gzip-tar measured at 665,801,784 bytes; with signed0.5r3 baseline estimate 3,707,988,247 bytes, leaving 586,979,049 bytes before retained upstream archives and final metadata. This is not a final artifact size guarantee; measure full candidate before signing. Existing source archives/licenses must be retained, no capability removal or weakened checks. SoL Custom standard exporter refreshed:51 dependencies,1,061 source files,1,416 runtime files equal to accepted Custom HTTP Worker (README documentation restored from pinned archive). Evidence: combined-media-runtime-size-20261007.json and sol-refiner-custom-standard-export-20261007.json.

- Stable Audio isolated HTTP Worker passed real music/SFX/short requests, variant switch, 401/400 bounds, active cancellation (3ms observed), recovery, drain503/resume and zero active requests. Docker network none, read-only root, uid1000:1000, all capabilities dropped and no-new-privileges verified; container removed. Independent WAV decoding/hash check passed. Standard Runtime builder now supports paired --stable-python/--stable-sources with stable-audio capability and fixed archive gate. Standard export has39 dependencies/40 source files and3,693 runtime files byte-identical to accepted unsigned Worker (LICENSE/README retained separately);33 builder/profile tests passed. Signed Runtime, real Package installation/Host lifecycle, distribution/publication and perceptual quality remain pending. Evidence: stable-audio-isolated-worker-20261007.json and stable-audio-standard-export-20261007.json.

- Stable Audio resident-r2 maximum contract passed: 120s/100steps generated in 5.444s, recovery 1s/1step in0.073s; no cancelled output and text hooks removed. Receipt: spark/evidence/media/stable-audio-resident-engine-20261007.json.

- Stable Audio resident implementation added: cuda_stable_engine.py, cuda_stable_adapter.py. Strict music/SFX task and no-lyrics v1 validation, 1–120s/1–100 steps, fixed Host checkpoint identity; shared native ownership drains cancelled writers before output cleanup. Real engine 10s generation, cancellation at sampling step2, no partial output, text-hook cleanup, one-step 1s recovery and sequential SFX recreation passed. 14 adapter/shared-lifecycle tests passed. Isolated HTTP Worker, standard Runtime export and full Host lifecycle are still pending; engine acceptance does not prove them.

- Stable Audio native full pipeline: offline Transformers T5Gemma strict-loads 134 tensors and embedded SentencePiece; English/Chinese/empty token IDs and masks exactly match Mac, visible-token embedding relative L2 0.196–0.231%. Music 10s/120s and SFX 10s/1s generated with strict DiT/SAME-S, matched eight-step logSNR ping-pong/real-latent overlap decode; independent WAV decode verifies finite non-silent stereo 44.1kHz and duration tolerance. Generation times 0.834/1.962/0.765/0.661s, load ~7s, peak allocation 2.412GB. Four original Mac NPZ hashes verified on Spark. RNG is Torch, not identical MLX seed stream. These are development native runs; perceptual/semantic quality, resident cancellation/lifecycle, signed Runtime/Worker/Host/publication remain pending. Evidence: spark/evidence/media/stable-audio-native-generation-20261007.json.

- Stable Audio follow-up: identical synthetic SAME-S inputs agree between MLX CPU and CUDA at relative L2 1.15–1.20e-4 (78.4–78.8 dB), while Mac GPU remains ~3%; initial projection CPU/GPU diagnosis saved without altering Mac product behavior. Small-music DiT inverse mapping strictly covers 438 upstream tensors plus 3 conditioner tensors; real CUDA FP32 forward passes (0.294 s, 1,862,058,496 bytes peak allocation). DiT reference relative L2: MLX CPU 7.62e-4, MLX GPU 4.61e-3. MLX explicitly validates checkpoint RoPE frequencies and retains its generated Fourier buffer. These are component/synthetic checks, not full generation or perceptual acceptance; tokenizer/text encoder, sampler, SFX, Runtime/Worker/Host/publication remain pending. Evidence: stable-audio-decoder-parity, stable-audio-dit-cuda-forward, stable-audio-dit-parity (20261007).

- Stable Audio: fixed source includes a SAME-S PyTorch implementation consuming the existing Mac NPZ. Both backends strict-loaded all 114 FP32 tensors; Spark CUDA passed synthetic lengths 2/32/64. Final relative L2 is 3.01–3.37%, so numerical parity is NOT accepted. Per-block traces saved; first projection compared with NumPy float64 gives MLX 4.37e-5 versus CUDA 2.65e-8 relative error, insufficient to attribute all downstream drift. Native music/sfx config endpoints require upstream authorization; no bypass or gated weights download. Text encoder/DiT/full generation, Runtime/Worker/Host and publication remain pending. Evidence: spark/evidence/media/stable-audio-decoder-parity-20261007.json.

- ACE-Step signed distribution candidate completed with existing verified Publisher key: dist_ai2apps_ace_step15_turbo_cuda_19671f40_v1,digest1c3b7a63ca7c0025108d46d57acdf8730bda103a9dda3b94c98dcb145cd228b9,23files/1204pieces. Installation publisher query returned active user session required; exact distribution Cookie authorization asked and pending, no Cookie read/submission. Independent work: Stable Audio3Small music/sfx Mac0.1.1 contract inspected,clean source3a82c807b69cf4b7c5c05270011a5d5e47abac18 archived with SHA receipt; no CUDA weights/inference acceptance.

- ACE-Step official dual-source unsigned preflight31120 passed:23files10,091,984,223bytes/1204pieces; fixedHF19671f406d603126926c1b7e2adc169acbcade22 andMS3e24671cd4f2830dea1cbf5eaaf00cab1087f7ea. No downloaded Python selected; original silence_latent.pt retains weights_only loader. Prepared unsigned spec dist_ai2apps_ace_step15_turbo_cuda_19671f40_v1; no Package manifest references unpublished distribution. Signature/publication/quality/Host gates remain open.

- ACE-Step standard export r2 session21907 completed:71dependency records,620source files,8128runtime files byte-identical to accepted raw-checkpoint Worker candidate. Evidence ace-step-standard-export-r2-verification-20261007.json supersedes old-engine equivalence for current build. Official MS repo master resolved via git ls-remote to3e24671cd4f2830dea1cbf5eaaf00cab1087f7ea. Fixed HF/MS selected-weight preflight running31120 using standard checkpoint_publishing library,excluding downloaded Python; no signing/publication/Cookie access.

- ACE-Step Runtime-owned checkpoint preparation HTTP probe31433 passed in offline readonly sandbox using original reference checkpoint, not prepatched view: instrumental55.933s cold,zh lyrics5.379s,499 cancellation218ms,recovery/drain/resume. Receipt ace-step-host-checkpoint-worker-20261007.json. Original28-file post-run rehash43388 completed exit0: all10,092,102,351bytes retain the recorded hashes. New engine/helper require refreshed standard-export byte comparison; old export receipt remains historical. No formal Host installation/publication or audible-quality acceptance.

- ACE-Step formal Host checkpoint gap addressed: Runtime now creates a disposable view referencing read-only Host weights while copying only hash-verified Runtime model/config Python. Downloaded Python/cache ignored; original checkpoint untouched; view cleanup on failure/close.19 checkpoint/adapter/schedule tests pass (untrusted Python excluded,source drift rejected,cancellation cleans partial view). Standard builder and development exporter include helper; prior8127-file proof applies to old engine only and must be refreshed. New independent fixture+raw-checkpoint HTTP probe31433 running; accepted old fixture preserved.

- ACE-Step standard profile export2689 completed exit0:71 dependency records,619 source files,8127 runtime files byte-identical to accepted HTTP Worker fixture. LICENSE/README moved only to retained sources/ace; archive+patch+requirements retained. Evidence ace-step-standard-export-verification-20261007.json. Formal signed Runtime/model distributions/Package,Host and audible quality remain pending; no active export/GPU task.

- ACE-Step standard CUDA Runtime builder integrated: capability-gated paired --ace-python/--ace-sources,checked-in dependency requirements,existing isolated closure exporter,original fixed source archive+exact schedule patch reconstruction,retained license/archive/patch/requirements and source hashes.31 builder/profile tests pass including source drift rejection. Standard re-export+byte comparison to accepted HTTP Worker running session2689 in ace-standard-profile-export.log. No signed artifact,version change,publication or Cookie access performed.

- ACE-Step isolated HTTP Worker77237 completed exit0:10s instrumental52.163s including cold load,20s zh lyrics5.415s;401auth/400bounds/499cancel182ms/recovery/drain-resume passed. Offline networknone/readonly/nonroot1000:1000/capdropall confirmed. Independently decoded returned WAVs:48kHz stereo exact480000/960000frames,finite,nonsilent,peaks~.95 with distinct stereo channels. Evidence ace-step-isolated-worker-20261007.json and ace-step-worker-decoded-20261007.json. This unsigned fixture is not formal signed Runtime/Package/Host acceptance; audible lyric/music quality still open. No live GPU task.

- ACE-Step isolated HTTP probe77237 started (ace-worker-r1-driver.log); Uvicorn and ACE handler imports passed inside exported profile, first GPU checkpoint loading observed. Probe includes decoded WAV dimensions/duration,instrumental+zh lyrics,401/400 bounds,499 cancellation/recovery,drain/resume and sandbox evidence. No first HTTP generation result yet; preserve live task.

- ACE-Step unsigned Worker Runtime export49027 completed exit0 through existing _copy_framework;71 dependency records, explicit ace service/profile mapping and patched model SHA c309c551bc4442a79eb288f779d4d1f228af147bbec6ea0f0e818557657bc421 retained. Evidence ace-step-worker-runtime-export-20261007.json. This is dependency export only; offline HTTP import/inference validation remains next. No live GPU or export task.

- ACE-Step CUDA Worker adapter implemented: shared validated v1 music10–120s contract,exactmodel/fixedHostcheckpoint,explicit v2 rejection,request-owned unique WAV,serialized resident engine,OOM release,thread-drained cancellation before partial-output cleanup. Conservative development admission28GiB cold/12GiB warm remains provisional.20 schedule/adapter/lifecycle tests pass, including repeated cancellation with actual late native writer. Unsigned dedicated ace profile export via standard dependency closure running49027 (ace-worker-runtime-export.log); no HTTP Worker acceptance yet.

- ACE-Step resident engine95725 completed exit0: default8-step10s generation7.360s, cancellation inside16-step sampling(no output artifact), subsequent1-step10s generation7.635s. Actual CUDA timestep inputs recorded (BF16 rounding), not merely config; cancellation6.145s is whole request including planning, NOT cancellation latency. Evidence ace-step-resident-engine-20261007.json.100-step native count gate also passed10.872s generation. HTTP sandbox/Worker lifecycle,planner/decode cancellation,quality,Host and signed release remain pending. No live GPU task.

- ACE-Step100-step GPU probe14381 passed: actual100 DiT calls,10s waveform,10.872s generation,10906979328 peak CUDA bytes. Added resident cuda_ace_engine.py with mandatory planner/CUDA,explicit Mac schedule,forward cancellation hooks,finally hook restoration,float-waveform validation and close. Real default8/cancel16/recovery1 engine probe95725 running; no engine lifecycle acceptance until receipt completes. HTTP Worker/quality/Host/release remain pending.

- ACE-Step16-step Mac-schedule CUDA probe12150 passed: actual16 DiT calls,10s48kHz stereo,8.471s generation/10,907,008,000 peak CUDA bytes. Explicit schedule equals Mac source inCPUall1–100 comparison. Original8-step native receipts remain pre-parity baselines and must not imply matched Mac defaults.100-step boundary probe14381 started in ace-step-parity-100-r1.log. Worker/quality/Host/release still incomplete.

- ACE-Step explicit schedule bridge implemented: CPU comparison against checked-in Mac source matches all1–100 step schedules;7tests pass including pinned-source drift rejection and CUDA explicit branch1/8/16/100 preservation. Found default shift mismatch too; parity probe explicitly supplies Mac shift3 sequence. Exact-source patch changes only explicit-timestep validation/mapping, leaving networks/attention unchanged. Independent source and hardlinked-checkpoint view breaks the modified code hardlink before writing; original views preserved.16-step GPU probe session12150 running with actual decoder-call count assertion; no GPU parity claim yet.

- ACE-Step120s native upper-bound probe57031 completed exit0:5,760,000frames48kHz stereo,28.338s generation after39.98s load,11,639,489,536 peak CUDA bytes. Real planner emitted11,835characters codes; finite nonsilent waveform verified. Native10s instrumental,20s zh-lyrics and120s structural gates now pass, but audible quality,nondefault steps,Worker/Host and signed releases remain open. All GPU probes ended; no live GPU work.

- ACE-Step20s zh-lyrics native probe15936 passed:960000frames48kHz stereo,7.858s generation after60.80s load,11,583,114,240 peak CUDA bytes. Planner emitted1984characters codes and all four networks stayed CUDA. This proves lyric-conditioned execution and structural waveform contract, not lyric intelligibility/audible quality.120s upper-bound probe57031 now running in ace-step-native-long-r1.log; no other GPU inference launched.

- ACE-Step20s Chinese-lyrics native probe started session15936 with explicit zh language and original user lyrics, mandatory real planner. Static source comparison found unresolved nondefault-step parity: Mac supports custom linspace schedule1–100; official CUDA handler clamps Turbo above8 and model grid/cap20 differ. Recorded exact source behavior in ACE-STEP-REUSE.md; do not silently accept ignored step requests or claim general parameter parity.120s boundary fixture prepared but not yet run.

- ACE-Step first native CUDA probe6795 completed exit0: actual1.7B planner emitted990characters of audio codes; DiT,VAE,text encoder,planner all CUDA.10seconds480000frames48kHz stereo generated in8.472s after42.03s initialization,peak10,906,958,848 CUDA bytes. Finite nonsilent waveform RMS0.1201. Source inspection explains returned peak1.0: upstream VAE output uses whole-waveform peak attenuation, not hard clipping; receipt annotates this distinction. No audible/lyrics/long-duration/Worker/Host/release acceptance yet; no live GPU task remains.

- SoL Custom isolated HTTP Worker completed successfully (33879 exit0): image/video,auth,bounds,499 cancellation20.4ms,recovery,drain/resume and Custom→Standard switch all passed; networknone/read-only/nonroot sandbox verified. Decoded alpha/timestamps/AAC evidence retained. Receipt sol-refiner-custom-isolated-worker-20261007.json. Cold image370.60s and quality/Host/formal release remain unresolved. ACE-Step original CUDA native mandatory-planner probe started session6795, ace-step-native-r1.log; no inference success yet. ACE-STEP-REUSE.md records exact provenance, capability bounds and remaining acceptance gates.

- SoL Custom isolated Worker image/video completed: cold image370.60s and warm60-frame video9.95s; parameter bounds passed and cancellation20.4ms. Independent artifact decoder confirms1026x682 RGBA exact Lanczos alpha/sRGB,60frames30fps512x288 exact PTS and95 byte-identical compressed AAC packets. Full lifecycle/Custom-to-Standard switch still running session33879, so overall Worker acceptance not yet claimed. ACE-Step GPU probe remains queued; native waveform/device validation prepared.

- ACE-Step native probe strengthened before execution: all four modules must hold CUDA parameters, planner must return nonempty audio-code tokens, original floating waveform is validated before single PCM16 output quantization; no normalized/saved intermediate reused as raw data. Probe remains pending behind live SoL Custom Worker session33879.

- SoL Custom native CUDA passed: default prompt output SHA matches Standard exactly; nondefault prompt invokes original text encoder and connectors once,1026x682 RGBA in4.764s/73,391,460,352 peak CUDA bytes. Cold CUDA transfer339.29s remains unresolved. Custom isolated HTTP Worker running session33879; quality/Host/signed release not accepted. ACE-Step transfer87479 and environment61261 completed;28files10,092,102,351bytes rehashed on Spark, original CUDA handler/planner imports pass. Independent environment retains inherited unrelated qwen-tts/gradio dependency conflicts; dedicated release closure still required. Native ten-second mandatory-planner probe prepared, not started while SoL owns GPU.

- SoL Custom transfer48953 completed; Spark rehash passed15files30,752,812,471bytes, receipt sol-refiner-spark-custom-verified-20261007.json. Native session7046 now loading original transformer/text/connector weights, no final inference yet. In parallel ACE-Step preparation pinned clean official Gitca1e85fe9430179831e6bc6be790c332190a3866;8,438,182byte source archiveSHA9c4740a17bdb82a33715e375ddaedacaf9f97c0f82fe4bd2dc689931cc15fab1. Mac reference28files10,092,102,351bytes validated: tensor/data match HF19671f406d603126926c1b7e2adc169acbcade22 metadata, two Python files match fixed official Git due official handler code synchronization (not untouched HF files). No Mac source/checkpoint changes. ACE transfer87479 started to checkpoints/ace-step/reference; no CUDA inference/environment/Worker acceptance yet.

- SoL Custom unsigned Worker fixture cloned independently from passed Standard fixture; build session1314 completed, updated facade/resources and unchanged lifecycle hashes recorded in evidence/media/sol-refiner-custom-worker-fixture-20261007.json. Standard fixture preserved. Current-task dependency waiter/native probe session7046 confirmed live: waits up to30minutes for all declared sizes, then existing probe rehashes15 components before any model loading and executes once. Transfer48953 remains the original live transfer; do not restart or separately launch another Custom GPU probe. No Custom inference acceptance yet.

- SoL Custom checkpoint ownership tests added: absent/incomplete custom checkpoint fails503 without native execution; only exact Host-selected Custom model is queried and complete Custom path is passed through.27 related regressions pass. HTTP probe now supports separate Custom fixture/probe names, nondefault image/video prompts, cancellation/recovery and Custom→Standard switch; not yet run. Transfer48953 remains live, last snapshot8files16,215,313,898/30,752,812,471bytes size-complete, SHA revalidation pending.

- SoL Custom Worker selection implemented: exact custom CUDA model ID selects its own Host checkpoint, required text/connector/tokenizer configs checked, nondefault prompts remain rejected by Standard. Resident cache key includes model ID as well as root; switching variants releases prior model before admission even for same checkpoint path. Conservative cold residency estimate72GiB for Custom vs42GiB Standard, incremental working/headroom retained; estimate not yet GPU-profiled for Custom.24 media/adapter/lifecycle regressions pass. Weight transfer48953 remains live; Custom native/HTTP inference pending. Existing passed Standard fixture not modified.

- SoL Custom Prompts preparation:15 original text_encoder/connectors/tokenizer files30,752,812,471bytes verified on Mac against fixedHFc69c2a543997fe12c1ae24c776df6188e5d2248a; transfer session48953 live to separate original-custom checkpoint. Shared18 standard files hardlinked without modifying original-standard. Added CudaCustomRefiner using original Gemma/LTX text components, fixed default-context fast path and cancellation hooks on text/connector modules; actual new-path inference pending. Native probe will rehash all15 files and verify nondefault prompt invokes both text encoder/connectors.21 media/ownership tests pass but do not validate new GPU loader; previously accepted Worker fixture remains unchanged.

- SoL standard Runtime builder integration completed: capability-gated paired --sol-python/--sol-sources, isolated51-record dependency export, fixed Sana/Diffusers archives and1061 source/module hashes, retained upstream archives/license declaration/Diffusers license. First real source comparison identified only6 directory READMEs omitted by upstream wheel; builder restores those from pinned archive and still rejects any code drift/extra files.28 builder/profile regressions pass. On-Spark verification matches1416 files byte-for-byte to passed HTTP Worker fixture with only6 added pinned READMEs; no changed/missing runtime files. No signed Runtime/model Package or publication. Custom Prompts,Host,numerical/visual quality and resource-bound profiling remain pending.

- SoL Standard isolated HTTP Worker PASSED image/video,401,invalid controls,499 cancellation9.1ms/recovery and drain/resume. Offline/read-only/nonroot1000:1000 sandbox verified. Cold image200.49s includes~193s device transfer; warm60-frame video4.130s. Decoded PNG1026x682 alpha exactly Lanczos/sRGB; video60frames30fps512x288 exact timestamps and95 unchanged AAC packets. ImageSHA exactly matches prior native output. AdapterSHA3c561327eca0b30cb1e32742fd47c662d02aa545caf9bc40cf47fee27e03f504. Session13436 completed/container removed. Cancellation timing proves HTTP request cancellation/recovery, not a specifically instrumented DiT phase. Standard signed Runtime export/model Package,Host,Custom Prompts,max-bound resource profiling and visual/numerical quality still pending.

- SoL unsigned isolated Runtime fixture exported through standard _copy_framework dependency closure; fixed Sana source archive verified and original SoL modules staged with shared Mac media helpers. HTTP Worker r1 started session13436, confirmed Uvicorn startup and first model shard load. Probe covers image/video,401,parameter bounds,499 cancellation/recovery and drain/resume in offline read-only nonroot sandbox. Artifact decoder prepared to verify exact alpha/frame timestamps/AAC packets. No HTTP inference result or release acceptance yet.

- SoL Standard CUDA Worker adapter now binds image/video engines to resident request ownership, exact CUDA model/checkpoint selection, fixed-prompt/scale/seed validation, MIME checks, unique request-owned outputs and cleanup only after native drain. CUDA OOM releases model and maps to resource_exhausted503. Development admission uses verified GB10 MemAvailable, discrete GPUs still constrained by CUDA free, conservative whole-clip working estimate plus42GiB cold residency/4GiB headroom; broad resource profiling still pending.21 related tests pass, including real-thread late-write cancellation cleanup and UMA-vs-discrete regression. Not yet deployed to isolated HTTP Worker or signed Runtime; Custom Prompts/Host/quality remain incomplete.

- SoL CUDA request ownership implemented in cuda_sol_lifecycle.py: one resident-engine lock, registered queued cancellation, duplicate active-ID409, repeated coroutine cancellation drains native thread before unlocking, stop rejects new work/cancels active and queued work, model release runs once and survives cancellation of an individual stop waiter, late cancellation cannot return success.4 real-thread barrier regressions pass. This helper is not yet wired to the HTTP adapter; no Worker/Host acceptance claim. Engine/output cleanup, production admission and actual sandbox lifecycle remain next.

- SoL native CUDA video r2 PASSED media/timeline/audio acceptance:60frames30fps256x144→512x288, one65-frame padded refinement, two6-latent decode windows, exactly60 output frames/all timestamps and95 identical compressed AAC packets.4.694s inference/43,373,898,752 peak CUDA bytes;199.34s CUDA transfer excluded. At admission cudaFree10.67GB vs systemAvailable80.01GB confirms r1 false refusal from ignoring reclaimable page cache. Frames31–33 show no obvious hard window cut but moving face/limb ghosting remains; visual/numerical quality not accepted. Session85127 completed, no live SoL GPU process. Worker/Host/production admission/custom/signed release still pending.

- SoL video r1 stopped before inference: fixture admission incorrectly used min(cudaFree, MemAvailable). Idle GB10 probe proves cudaFree=LinuxMemFree53,249,425,408 while MemAvailable122,538,524,672 and cached71,382,204,416. Corrected fixture-only UMA policy requires exact GB10/shared total and same16GiB incremental headroom from MemAvailable. Original failure log preserved; independent r2 session85127 now running. Host already uses psutil system-memory accounting; no Host behavior changed.

- SoL native video acceptance launched session56720:60 real-motion frames plus synthetic chirp, one65-frame padded refinement, multiple decoder windows, exact timestamps/audio packets. Fixture-only resource bound; no general CUDA admission policy claimed. Updated SOL-REFINER-REUSE.md to remove obsolete transfer status and distinguish actual image acceptance from unresolved numerical/visual quality.

- SoL native CUDA image wrapper PASSED existing Mac RGBA fixtures:513x341→1026x682 in3.093s/40,758,936,064 peak CUDA bytes;1920x1080→3840x2160 in9.674s/43,101,340,160bytes. Exact Lanczos alpha, dimensions and PNG sRGB verified. CUDA transfer193.27s excluded from inference timings. Both Mac/CUDA preview outputs redraw facial detail; no obvious preview tile seam, but4K preview downsampled and full quality/numerical parity remain pending.8 media contract regressions pass. All SoL GPU processes completed (58338 terminal); no live inference job. Native-only, no Worker/Host/Custom Prompts/signed Package acceptance or publication.

- SoL common-input component probe completed: CUDA upsampler vs Mac with identical encoded tensor has relativeL2 0.04124; DiT velocity with identical noisy tensor has relativeL2 0.13124/cosine0.99138. Divergence is not solely propagated from VAE. No numerical parity acceptance or implementation fix claimed. Native real CUDA image wrapper probe started session58338 for existing Mac513x341 RGBA and1920x1080 RGBA fixtures; output1026x682/3840x2160 and exact alpha checks pending.

- SoL stage localization completed with identical RGB/context/noise: VAE encode relativeL2 0.00630, upsampler 0.04055, noisy input 0.02011, velocity 0.19159, final latent 0.13717. These include propagated input differences; no intrinsic-component failure inferred yet. Common-input upsampler/DiT diagnostic now running session36769. CUDA loader timing isolates205.05s of205.77s to pipeline CUDA transfer; inference1.689s. No quality/Worker/Host/Package acceptance claimed.

- SoL controlled Mac/CUDA comparison completed, session34373 ended. SameRGB/defaultcontext/BF16noise yields visually similar redraws on both; content hallucination in this low-resolution sample is not CUDA-specific. Output MAE0.0220/RMSE0.04363/PSNR27.20dB/cosine0.99821; latent relativeL2=0.13717/cosine0.99058. Numerical parity NOT accepted; stage-level investigation remains. CUDA load200.75s/inference1.80s vs Mac1.626s total for this tiny fixture. Added future loader phase timings to diagnose repeated long CUDA cold load; no behavior change. Evidence shared-comparison/shared-cuda JSON and first-frame PNG retained.

- SoL shared-input parity fixture created: identical9x160x256 RGB input and BF16noise[1,128,2,10,16] with SHA receipts. Mac current Package-source reference completed via existing Metal environment, recording latent/output arrays; visual reference also strongly redraws this low-resolution scene. Cannot attribute fidelity issue solely to CUDA. Spark same-fixture comparison running session34373 (sol-refiner-shared-fixture/cuda.log); no comparison conclusion yet. CUDA facade explicit noise input is for controlled parity, not a new exposed user control.

- SoL first native CUDA9-frame standard inference completed: full18-file SHA verified; load186.67s/inference1.493s/peak40,830,044,672 CUDA bytes; output9x288x512, one transformer call/torch SDPA. Process session63323 completed, no live GPU job. Visual first-frame review shows substantial face/clothing redraw relative to low-res input; quality NOT accepted. Next compare Mac with identical input/context/shared noise before attributing cause. Eight CPU image/video contract tests now pass including compressed AAC packet+PTS/DTS passthrough with injected decoder. Formal Worker/Host/Package and custom prompt path remain pending.

- SoL standard checkpoint transfer session7646 completed successfully. Independent environment realGB10 BF16 matmul, SDPA and Conv3D smoke passed (evidence/media/sol-refiner-cuda-environment-20261007.json). Full on-Spark SHA verification and9-frame native inference launched, exec session63323, log~/ai2apps-spark-dev/sol-refiner-native-standard.log; do not count inference as passed yet or restart while session is live.

- SoL CUDA facade adds whole-clip latent refinement and independent VAE decode APIs; shared video wrapper now applies Mac window_plan/join_window/remux_audio, crops exact2x canvas, emits explicit frame PTS and verifies exact original frame count. Seven CPU image/video contract tests pass;60-frame synthetic decoder test confirms one whole-clip refine call and multiple decode windows with60 output frames. This is media orchestration verification with an injected test runner, not real CUDA/quality acceptance. Diffusers fixed-context subclass component signature validated on Spark; transfer session7646 still live.

- SoL CudaStandardRefiner now loads original components locally, checks fixed-context SHA, enforces full8k+1/padded2x canvas preconditions and default-prompt identity, and installs/removes forward cancellation hooks across original networks. Native9-frame probe now uses this same facade with edge padding and exact crop rather than upstream resizing. Static compile passes only; GPU loading/output still unverified pending live transfer session7646 (24G last observed).

- SoL CUDA whole-clip staging added: real decoded CFR/timestamp/geometry/audio-codec scan,1500frame/60s limits, admission callback before memmap allocation, edge spatial padding and repeat-last temporal padding up to8k+1, second-pass input consistency, request-owned temporary cleanup. Real MP4 tests confirm10frames preserved as17 inference frames, admission refusal before staging, and61s rejection; combined image/video contracts6pass. Initial test fixture overflow fixed (uint8 generation), not product behavior. GPU bridge still pending; transfer session7646 live at20G, no restart.

- SoL CUDA image media wrapper now reuses Mac load_image EXIF/color handling, edge-pads to32, requests exact padded2x inference, crops top-left back to original2x, preserves alpha with Lanczos and writes sRGB PNG. Three CPU contract regressions pass (odd47x35 RGBA pixel geometry/alpha, EXIF orientation, nonfinite rejection). CUDA callback/inference not yet verified; transfer session7646 remains active. No claim of actual neural image upscaling yet.

- SoL native nine-frame CUDA probe prepared with on-Spark full SHA verification and fixed-context-only override. SOL-REFINER-REUSE.md records critical Mac contract gaps in upstream CLI: must pad rather than truncate temporal frames, edge-pad spatial dimensions rather than resize, preserve image alpha/audio/CFR and whole-clip refinement. Transfer session7646 remains active; no inference started.

- SoL-Refiner CUDA preparation: located Mac original and compact checkpoints under ai2apps/.build/sol-refiner; fixed clean Git sources Sana670482d8a857d578ac8a2ea89b052d0fb47badba and Diffuserse0abab83b5df05de9e7abd788643c1a7c1e42e28 archived with receipts.18 original standard-component/default-context files total40,435,014,538bytes verified against official HFc69c2a543997fe12c1ae24c776df6188e5d2248a and Mac context hash. Transfer to Spark checkpoints/sol-refiner/original-standard is running (rsync exec session7646); do not restart without checking handle. Independent sol-refiner-venv dependency installation completed; Pipeline import validation pending. No CUDA inference acceptance; custom-prompt text components not yet transferred.

- SAM2.1 isolated Worker boundary acceptance PASSED:450 frames at24fps/18.75s,960x540, complete decoded output in35.97s;451frames rejected400 in0.59s;200frames at10fps/20s rejected400 in0.33s; zero active requests afterward. Adapter unchanged SHA175c828cec016f12da1ad5aabc766e34f200e3bdee1ba428894fe1cf71831fd1. Repeated official clip tests capacity/timing only, not continuous18.75s semantic quality or maximum-resolution combination. Receipt evidence/media/sam21-worker-bounds-20261007.json. Signed Runtime/Package and formal Host still pending.

- SAM2.1 standard Runtime builder integration added capability-gated --sam21-python/--sam21-sources, pinned archive/decoded-frame patch verification, shared Mac controls/media and retained Apache/BSD licenses. Standard profile export31 distribution records; verification matches41 source/config files and2101 dependency files byte-for-byte to the passed isolated Worker fixture.31 existing builder/profile and SAM2 boundary/cancellation regressions pass. No signed Runtime/Package built or published; full Host,450-frame and broader quality acceptance remain.

- SAM2.1 Small isolated Worker PASSED200-frame/30fps mask generation (cold17.30s), negative-point/late-frame controls (14.04s),499 cancel1.36s/recovery,401/drain/resume and offline read-only non-root sandbox. Decoder verifies frame count/rate/canvas, grayscale masks, positive/negative point pixels and five blank prefix frames. Single-point shorts mask empty at65–68; inspected65 shows target occluded, final199 reacquires shorts. Late positive+negative sample tracks full person at199. Six request/cancellation ownership tests pass. Decoded-frame bridge patchSHAaa808a7d03b932c9e306371db154802be6b92e562b20298735d4f18badfd7bfa avoids lossy intermediate JPEG; original networks unchanged. Initial probe model-ID typo failed404 and remains recorded; corrected separate r2 passed. Standard Runtime build integration, formal Package/Host,450-frame bound and broader quality remain.

- SAM2.1 Small native CUDA20-frame tracking PASSED on official bedroom clip: strict519-tensor original state_dict, BF16 autocast, load0.681s/inference1.921s/peak640,881,664 CUDA bytes. Official source2b90b9f5ceec907a1c18123530e92e794ad901a4 archived SHA1f2fbfad3ffa38110368abac76c6ef9df9c282a66d5c2807bc94abf4d2fb30f8; official checkpointfacebook/sam2.1-hiera-small@ee5bba1d82bb8749febdf90f45e84b687142ba03. Safe conversion preserves all tensor values/dtypes (SHAf3e03d4ec31315e9feea2ca161ce7cb9f9a932e545ab63e40e7fb4da19c3b813). Single positive point selects shorts in frame0; first/last overlays retain that target, not a full-person mask acceptance. Optional upstream connected-component postprocessing explicitly disabled to match Mac exposed controls. Native-only; Worker/Host/Package and full quality remain pending.

- LivePortrait isolated Worker PASSED full78-frame/3.12s FP32 video at600x704 (16.06s), BF16 crop512 video (8.27s), image driving, precision switching,499 cancellation0.125s/recovery,401/drain/resume and offline read-only non-root sandbox. Separate preserve-driving-audio probe verifies148 AAC packets including PTS/DTS/timebase byte-identical and decoded samples exactly equal; explicit none removes audio. Seven shared-import/cancellation/boundary tests pass;25 existing Runtime builder/profile regressions pass. Standard source export preserves39 Python files and original module bytes/license; dependency profile export passed. Unsigned fixtures only: signed Runtime/model Package, Host workflows and cross-identity/temporal quality remain pending.

- LivePortrait original CUDA 12-frame probe PASSED both FP32 and BF16 with shared Mac YuNet preprocessing/NMS/alignment and motion math. FP32 load0.757s/process2.424s/peak1,201,740,288 CUDA bytes; BF16 load0.758s/process1.816s/peak609,363,456bytes. All motion values finite and output512px; selected frames preserve source portrait. One final-frame BF16-vs-FP32 MAE0.984 RGB units/PSNR42.73dB, not a quality benchmark. No full-video/Worker/Host acceptance yet. Source/checkpoint hashes and receipts retained; first SDK-import failure log not overwritten.

- LivePortrait CUDA now inherits existing Mac motion/keypoint/stitch math; original Torch feature/motion/warp/decoder modules load safe weights. YuNet uses OpenCV4.13.0.92 CPU graph executor with unchanged Mac resize/decode/NMS/crop, NumPy2.5.3 dependency compatible. Mac detector/model imports lazy; no-MLX import regression and all five original Mac class exports pass. First CUDA probe stopped before inference because SDK path was absent; explicit immutable Runtime app path added to probe and rerun started.

- LivePortrait pinned official source9b294b3d0536135442ea73cb01e6cb3ca7029dd3 (archiveSHA14db8304a3eb98461ec5c19f95a1b46b996ea7daa9cbbcf113b9139d60e0f3be), matching Mac human checkpoint82a4fa6735ca58432b6ce39301b4b9ee066dea47. Five original files verified; seven safetensors converted with weights_only=True, exact dtype/value roundtrip and strict CPU module loading for626 tensors. Original spectral weight_orig/u/v preserved. Shared Mac motion pipeline imports made lazy so CUDA can inherit orchestration without Metal; no-MLX import regression passed. New CUDA wrappers use original Torch modules; no inference acceptance yet. Same fixed YuNet232,589byte ONNX SHA verified.

- FlashHead Pro isolated Worker PASSED2/10s generation (warm10s77.28s), duration/model/input bounds,499 cancellation0.213s and recovery,401/drain/resume,offline read-only non-root sandbox.2s output byte-identical to native reference. Decoded50/250frames and zero-offset audio correlations>0.999 pass; native10s continuous audio also passed (78.59s,6.64GB peak CUDA allocation), last-frame sanity reviewed. After Pro changes, Lite2s full lifecycle regression also passed. Full perceptual lipsync and signed Runtime/Package/Host still incomplete.

- Pro native2s/50frames CUDA passed using strict safe Wan VAE: load5.90s/generation19.12s/peak6,605,110,784 CUDA bytes; decoded/raw pixel check and H264/AAC exact2s durations passed. One middle frame visually normal, no lipsync claim.10s native run ongoing. Standard source-builder patch pin advanced to safe-Pro patch; no existing signed Runtime changed.

- Pro transfer completed and Spark rehash passed all six files. Original Wan VAE strict CPU state_dict loading accepted194 tensors/126,892,531 parameters from the existing safe conversion. CUDA adapter now routes Lite/Pro explicitly, with independent60s/10s limits and9/5-frame overlap;9 request/layout tests passed. Native Pro2s CUDA probe running; no Worker support acceptance yet.

- FlashHead Pro preparation: six Mac files (6,916,065,877 bytes) verified against cached manifest; Pro model/config also exactly match fixed original HF metadata. Separate safe-Pro patch11c0c020ed3a3da8d457917d2aff269d6af0815bf3ec1abca08b92abb2488fa9 loads existing Wan VAE safetensors with strict original state_dict layout. Pro uses5-frame overlap (Lite9). Transfer/native CPU load/CUDA2s/10s acceptance pending; existing Runtime builder remains pinned to Lite-tested patch until Pro validation.

- Standard FlashHead dependency export PASSED on Spark (47 records), including Diffusers0.35.1/Transformers4.57.3/PyAV18.0.0. Source reconstruction also passed33 Python-file byte comparisons with license retained. Evidence flashhead-standard-dependency-export-20261007.json and flashhead-standard-source-export-20261007.json. Incomplete unsigned export only; no signed Runtime or production publication claim.

- FlashHead Lite isolated Worker r2 PASSED2/10/60s (50/250/1500frames), input bounds, cancellation499 in0.456s with recovery,401/drain503/resume and zero active requests.60s generation74.47s. Full decode verifies H264/AAC exact2/10/60s duration and zero-offset driving-audio correlations0.99967/0.99982/0.99985 after shared encoder PTS fix. Three60s frames visually retain source identity/background. Single portrait/repeated2s audio fixture, not continuous perceptual/lipsync quality. Formal Runtime/Package/Host and Pro pending.
- Standard CUDA Runtime builder now supports capability-gated FlashHead dependency/source inputs. Source archive and patch pinned;33 Python files match development source, Apache license/original archive/patch retained.25 builder/profile regressions passed. Existing signed Runtime0.5.0 remains unchanged; real standard dependency export being verified separately.

- Shared FlashHead Mac/CUDA PyAV encoder now supplies frame/audio PTS, fixing measured64ms AAC priming delay. New chirp regression proves zero-offset decoded correlation>0.99;8 focused tests passed. CUDA cancel maps inherited409 to499. Original60s generation passed but overall first probe failed these checks; separate r2 verification pending. Future Mac Package version/release must include encoder correction; published0.1.0 remains unchanged.

- FlashHead Lite corrected2s/50-frame CUDA probe passed container and decoded/raw RGB checks; three reviewed frames retain portrait/background and mouth movement. Load4.31s/generation3.62s/peak5,423,325,696 CUDA bytes. Single portrait sanity only, not lipsync quality. New CUDA facade reuses Mac validation/lifecycle and streaming MP4 encoding, includes native-forward cancellation; independent unsigned dependency/source fixture exported through standard closure builder. Real2/10/60s Worker lifecycle probe started.

- FlashHead first CUDA inference/container succeeded but encoded frames failed visual inspection due to probe pixel-range mismatch with shared Mac encoder. Caller fixed, encoded/raw RGB checks added, separate r2 rerun underway; upstream model and shared encoder unchanged.

- Qwen Edit square-r3 Worker/lifecycle and single512-output visual preservation passed after1024 internal rendering. FlashHead CPU source import, SDPA and Spark weight hashes passed;2s Lite CUDA probe prepared with shared Mac media encoder, no inference claim yet.

- FlashHead Lite preparation started: seven Mac cached files match fixed original HF bytes; source pinned with auditable optional single-GPU dependency patch. Independent dependency environment being validated after initial Hub/Diffusers conflict; no CUDA inference/Runtime/Host claim yet.

- Qwen Edit1024 single-reference visual preservation passed. Low-resolution square path now renders1024 and downsamples to requested size to avoid observed512 artifacts;16 tests passed, real512 Worker fix acceptance running. Latest SenseVoice short/long timestamp provenance live regression passed.

- Standard speech-profile export now verified on Spark for both profiles (93 records), preserving selected dependency versions. Incomplete export fixture only; full signed Runtime remains pending.

- SenseVoice adds short segment bounds and native/pipeline timestamp provenance for the Host contract; updated live regression queued after1024 image test. Prior long-audio receipt predates this metadata change.

- SenseVoice long Worker passed47.68s/8-segment original-timeline transcription,31s silence,long cancellation/recovery andChinese auto/zh; numerical-time formatting still fails. No full language/hour-long quality claim.1024 Qwen Edit quality run started serially.

- Qwen Edit non-diagnostic isolated rerun passed cold generation and lifecycle with byte-identical output; original timeout retained and512px quality still fails. Long SenseVoice Worker acceptance now running serially.

- SenseVoice long-audio adapter implemented using fixed CPU VAD and serial CUDA chunks, original-timeline offsets, cancellation and empty-speech handling; VAD47.68s/8-segment and silence reference passed. Full long-audio Worker test pending; no formal capability/publication claim.

- SenseVoice long-audio preparation pins and verifies official FSMN VAD weights; CPU segmentation/silence probe added. No checkpoint distribution publication or CUDA adapter long-audio claim yet.

- SenseVoice serial isolated Worker passed real recognition/native word timestamps,415 invalid WAV,language/30s limit,cancel499/recovery,401/drain/resume and sandbox checks. Qwen Edit diagnostic full1–3-ref protocol/lifecycle passed, but512px visual quality still failed and normal-mode stability rerun is active. Formal Package/Host remains pending.

- SenseVoice initial concurrent Worker load failed CUDA OOM; failure retained and serial rerun required. Future image recovery-only probes use explicitly recorded two-step execution after full quality/format runs; current diagnostic remains unchanged.

- Standard CUDA Runtime builder now accepts capability-gated SenseVoice and punctuation dependency profiles. Each preserves existing profiles and selected dependency versions without inheriting PYTHONPATH/PYTHONHOME;22 builder/profile tests passed. No manifest/version bump, signed artifact mutation or publication.

- Added SenseVoice real HTTP Worker probe covering native timestamps, input limits, cancellation/recovery and sandbox/lifecycle boundaries. Adapter rejects timestamp starts beyond audio duration; live acceptance pending GPU availability. Inventory records CUDA equivalence separately from unresolved quality and formal Host acceptance.

- SenseVoice dependency fixture exported; development Worker adapter implemented with fixed CUDA weights, native timestamp conversion and cancellation. Not yet live-tested;30s prototype limit explicitly leaves long-audio parity unfinished.

- SenseVoice actual CUDA output matches CPU in four English fixture cases; numeric formatting remains unresolved. Qwen Edit Worker confirmed900s timeout, preserved failure and started bounded stack diagnostic.

- Punctuation real isolated HTTP Worker acceptance passed Chinese/English/word-preservation and400/401/drain/resume; unsigned fixture only, formal Runtime/Package/Host still pending.

- Punctuation unsigned dependency fixture exported using standard closure; sandbox HTTP Worker acceptance started. Formal Runtime/Package/Host still pending.

- Qwen Edit isolated Worker first step shows abnormal waiting despite sufficient memory; no acceptance claimed. Added opt-in test-only periodic Python stack output for next diagnostic run, without changing Runtime or sandbox privileges.

- Shared punctuation Package source fixes English-only output marks while preserving words, numbers and mixed CJK text. Five regressions and real Spark CPU rerun passed. Applies to a future Package revision; existing published0.1.1 untouched. No Desktop rebuild/publication.

- Unchanged Mac punctuation adapter runs on Spark CPU with pinned ONNX weights and official sherpa-onnx1.13.8 ARM64. Three Chinese/English cases preserve words; model clears on stop. Worker/Runtime/Host acceptance still pending.

- SenseVoice CPU reference safely loads fixed upstream weights; exact spoken-number fixture fails because ITN on/off both produce 930. Failed comparison evidence retained; CUDA equivalence, Mac comparison and number/punctuation quality remain open. No hard-coded transcription fix.

- Qwen Edit first CUDA result changes requested color but fails visual quality due to texture artifacts at512px; evidence retained. Worker protocol checks continue; 1024 quality retest prepared. SenseVoice Spark fixed-byte verification passed, inference pending.

- SenseVoice development dependency import/pip check passed. Five fixed upstream files locally verified and transferred; CUDA fixed-audio probe prepared with offline/safe loading. Real ASR and punctuation/Worker/Host acceptance remain pending.

- Qwen Edit development environment repaired with matching official Torchvision; CUDA ABI check passed. Signed Runtime unchanged. SenseVoice fixed upstream metadata saved; isolated NumPy1.x environment installation started, no model inference yet.

- Qwen Image 1328² 新版 adapter 全套 Worker 通过，热请求约 110 秒，单样例英文文字目视通过。Qwen Edit Spark 33 文件摘要全部通过，真实编辑/Worker 验收已启动，未宣称通过。

- Qwen Edit 固定权重传输完成，Spark 摘要校验进行中；开发质量探针支持独立记录 1–3 张参考图和提示，语法验证通过，尚未实机编辑。

- Qwen Image 1328² 首张真实 Worker 图的英文文字与场景目视通过，证据已保存；属于单样例，后续格式与生命周期验收尚在运行。总模型对齐清单同步 H3/Demucs/绘图当前实测状态。

- Qwen Image 2512 / Qwen Edit 2511 / Z-Image Turbo 三个 CUDA checkpoint 分发候选已标准签名，完整 HF 字节与 MS 固定元数据一致。精确 ID/digest 见 spark/IMAGE-DISTRIBUTIONS-20261007.md；未发布，无 Cookie 访问。

- 开始标准构建 Qwen Image/Edit/Z-Image CUDA checkpoint 分发候选；新 Z-Image spec 包含固定 scheduler。发现旧 Mac Apache termsHash 与当前官方文本不同，新 CUDA 候选内嵌实际原文与 SHA-256，未覆盖历史分发；旧 Mac 后续修订需核对许可证摘要。

- 新版共享 adapter 的 Z-Image 1024² 三格式与取消/鉴权/drain/resume 全通过，热请求约 12.3 秒，PNG 目视通过；Qwen Image 1328² 文字渲染/生命周期复验启动，尚待结果。

- Z-Image Turbo 首轮 512² 隔离 Worker 三格式及生命周期验收通过。探针新增 1024²/1328² 尺寸选择并校验模型对齐倍数；新版共享 adapter 的 Z-Image 1024² 复验进行中。

- Z-Image Turbo 开发 CUDA 512²/9 步出图 3.65 秒，视觉核验通过。开发绘图 adapter 增加 Qwen Edit 独立 factory（1–3 图、30 步/CFG2.5），15 项边界测试通过；新版共享 adapter 待实机复验，未改签名 Runtime。

- Qwen Image 2512 开发 adapter 在 Runtime 0.5.0 解包候选的断网只读 Worker 通过三格式、拒绝编辑、取消恢复、401/drain/resume 验收；热请求约 33 秒，图片目视通过。正式 Package/Host 与高分辨率质量验收仍待完成。

- Z-Image Turbo 固定权重在 Spark 逐文件验收通过。Qwen Image Edit 2511 复用 Mac 固定原始权重，33 文件全部校验，传输及开发编辑探针已准备；未计入正式支持。

- Qwen Image 2512 BF16 开发 CUDA 出图通过（512²、20 步、33.41 秒），已视觉核验；隔离 Worker 多格式与生命周期测试进行中。验收探针支持有界自定义超时，保留原默认值；未改 Runtime 0.5.0 签名制品。

- 标准 CUDA builder 增加受能力声明约束的 audio-processing 依赖层导出，保留 TTS/H3 隔离映射；14 项构建器测试通过。未修改 0.5.0 manifest/签名制品，Demucs 正式支持需后续 Runtime。

- Demucs CUDA 权重分发候选已签名；新 spec 修正为固定官方 LICENSE 的实际 SHA-256。发现 Mac 旧 Demucs spec 的 termsHash 与原文不一致，后续修订须新不可变分发，未篡改既有版本。Qwen Image 固定权重在 Spark 校验通过，真实 CUDA 生成中。

- Demucs 打包中途取消的针对性测试通过（499、无成功制品、事件清理）；修改后的隔离 Worker 全量复验通过，r2 回执已保存。

- Demucs 独立导出 Runtime 的断网只读非 root HTTP Worker 三配置、ZIP/时间线、鉴权、取消恢复及 drain/resume 通过。补充打包阶段取消检查后在新目录复验，正式 Runtime/Package/Host 尚未完成。

- Demucs 共用 Mac 分离管线三配置与取消恢复实机通过，残差双轨重建误差 <1e-6；新增标准音频 Worker 开发适配器及独立依赖导出 fixture，断网 Worker 验收进行中，未改签名 0.5.0。

- Demucs 官方 TorchAudio 2.10/cu130 匹配修复后，Mac 固定安全权重严格加载及 CUDA 四轨分离通过（5.248 秒语音，0.873 秒推理，约 553 MiB 峰值分配）；仅开发探针，Worker/Host/音乐质量尚未验收。H3 FL2VA 权重分发签名完成，未发布。

- Demucs CUDA 开发验收开始：复用 Mac 固定 safetensors 的纯 NumPy 布局恢复，官方 Demucs 4.0.1 源码摘要固定，隔离开发环境 pip check 通过；四轨真实推理测试中，尚未导出正式 Runtime 或接入 Host。

- Qwen Image/Z-Image 独立开发 Worker 适配器及多格式、取消恢复验收探针已实现；12 项参数/操作边界测试通过，固定 checkpoint 本地字节全部验证。尚待 Spark 同步与实机验收，不改变 0.5.0 签名制品或声明正式支持。

- 0.5.0 独立 Host 验签通过；无静态发现，未配置审计器导致 review，等待精确版本人工批准。并行准备 Qwen Image 2512/Z-Image Turbo 固定原始权重及 CUDA 开发探针，尚未计入正式 Runtime/Host 支持。

- r3 从生产解包后的独立路径执行 H3 文本/首帧/参考图及取消恢复回归通过；签名制品已传回 Spark，独立 Host 审计进行中。

- Runtime 0.5.0 外层签名候选已生成（3,042,186,463 字节；SHA-256 `6a7cfc1d169dce18da1c2ee555ed6d275efe5b709e6d73c4e365ffb034fff82c`）。精确制品独立 Host 审计探针已准备，默认不批准审计；生产 0.4.0 未变。

- r3 生产解包器及 2,821 个 H3 文件摘要校验通过；参考音频、视频、参考视频静音与混合输入四例隔离推理及逐帧/音轨检查通过。Mac 标准签名构建成功，尚未完成新版本 Host 安装或生产发布。

- r3 含完整工具链源码候选构建完成（3,052,236,612 字节，payload SHA-256 `ea586940238c21aa1c77d6b8e2a38910ee539326461c3c438f54373fd64073f7`）；r2 27B NVFP4 多图/128 tools/流式取消兼容回归通过。r3 生产解包器校验、参考媒体和签名准备进行中。

- Runtime 0.5.0 r2 已通过 TTS Base 合成/回转写、FLUX 生成及 1–4 参考图边界、ASR 中英文 Worker 回归。标准 builder 新增完整对应工具链源码打包与二进制/源版本及 SHA-256 门禁，固定五组 Ubuntu 源包（397,264,713 字节）；构建器 13 项测试通过，r3 含源码候选构建中。未签名发布或替代正式 Host 验收。

- 标准 CUDA Runtime builder 开始集成 H3：固定归档/补丁摘要门禁、来源版本记录、独立 H3 依赖层、保留音频配置、ARM64 编译器与包归属头文件及版权/SBOM；CLI 要求能力声明和完整输入一致。构建器/依赖层/Package 合同 22 项测试通过；Runtime 0.5.0 H3 候选已完成源码/依赖导出并通过文本/首帧/参考图/取消恢复断网 Worker 回归；标准 builder 载荷压缩完成，原始 tar.gz 大小 2657869197 字节；仍需签名制品审计与安装。构建器环境继承修复后 23 项构建/合同测试及 51 项 Worker 回归通过。0.4.0 生产安装不变；工具链对应源包需从历史仓库补齐。

- H3 参考媒体扩展中：加入单音频/单视频及混合参考输入、参考视频音轨开关、格式/时长边界检查；复用匹配 Torch 2.10 的 TorchAudio 导出到 H3 依赖层。四例断网实机及取消恢复通过（39.33/47.34/45.05/52.55 秒），15 项测试通过；尚未正式构建、签名安装或发布。

- H3 标准视频适配器实现中：文本、首尾帧及 Ref2VA 图片 multipart 输入映射、Host 控制输出根、取消与临时输入清理；暂不声明参考音频/视频或快速变体完成。13 项参数/生命周期测试及真实断网只读非 root Worker 的文本/首帧/参考图、取消恢复、drain/resume 已通过。开发副本包含可重定位 C 工具链，仍需正式 builder/SBOM/签名安装/Host 验收。

- 2026-10-07 H3 Worker 接入实现中：新增私有 Comfy 子进程管理、可信 Runtime 源码路径限制、独占队列、取消等待空闲、未知提交结果回收进程及输出路径约束；3 项生命周期/路径测试通过。独立导出验收副本（标准依赖导出器，新增依赖约 1.1 GB）已脱离开发 venv，真实 GPU 冷请求/取消恢复/子进程重启通过；仍未签名发布 Runtime 或接入 Host，不能宣称 H3 已交付。

- 2026-10-07 继续推进：TTS 1.7B CustomVoice/Base/VoiceDesign 在正式 Runtime 0.4.0 断网 Worker 中合成、取消恢复通过，六段输出 ASR 回转写一致。四份 TTS BF16 与 FLUX CUDA 完整权重分发已签名，待 Cookie 授权发布；未生成占位 distribution。H3 固定 Torch 2.13 独立开发环境通过 pip check/GB10 导入，五个固定模型文件双源元数据一致，63,440,965,087 字节全部下载并完成 SHA-256 校验。新 Spark Ref2VA 冷/热及 FL2VA 文本短片通过，分别 47.73/16.11/27.07 秒；音轨和逐帧解码通过。首尾帧及取消恢复开发探针也通过（取消确认约 0.62 秒）；复用 Runtime 0.4.0 Torch 2.10 核心加 Comfy 开发依赖的三例兼容探针通过；正式依赖导出与 Runtime/Worker 接入继续推进。

- 状态：`in_progress_partial_packages_published`。优先音频、绘图、视频，对话保持 27B；媒体全量对齐未完成。
- 2026-10-07：CUDA Runtime 0.4.0（metadata 268）及 Qwen3-ASR CUDA 0.1.4（metadata 269）由既有 Publisher/key 和标准脚本生产发布，公开元数据及制品摘要一致。Runtime 上传 504 后查询并恢复同一 submission，无重复提交。初始 Cloud 单源例外已记录，镜像待验证。
- 用户明确批准两版安装审计。Runtime Registry 安装通过，Spark Dev Discover 升级及 Host 重启健康通过；ASR 正式签名包中英文自动/指定语言、停止/重启/卸载通过，Dev Discover 生产安装/权重校验/启动通过。两版均 active，数据库 quick_check 正常。详见 `spark/MEDIA-RELEASE-20261007.md`。
- ASR 修复指定语言前填充、auto、空输入；正式六文件 distribution 缺少的模板以固定上游 revision 的签名适配器资源补齐，保持共享权重只读。9 项回归及六文件真实 Worker 验收通过。
- Runtime 新增 Diffusers 0.41、Qwen3-TTS 音频依赖层和可信服务映射；默认 Transformers 5.18、音频 4.57.3，校验导出闭包版本，不导出开发 .pth，SBOM 区分层版本。15 项 Runtime/构建器测试通过。共享 launcher 的无 profile 路径保持兼容，Desktop 仍需随未来 Runtime 重建验收。
- CUDA TTS/FLUX 适配器复用统一媒体协议。FLUX 隔离 Worker 生成/编辑/取消恢复通过；TTS 修复上游停止条件丢失，按变体处理采样（CustomVoice/VoiceDesign 默认确定性，Base 保留温度 0.8），保留早期异常和静音证据。四变体开发样例及 r3 0.6B 隔离重复输出/转写/取消恢复通过。27B NVFP4 图像/工具/流式回归通过。相关回归总计 34 项通过。
- TTS、FLUX 和 H3 独立模型 Package 尚未发布。旧 H3 ComfyUI/Studio 固定源码与补丁已迁入新 Spark；已完成 Torch 2.13 开发环境、权重和三例短片，仍需正式 Runtime/Worker/Host 验收，见 `spark/H3-REUSE.md`。
- 本次仅 Spark Runtime/Package 发布，未修改 Cloud、未重建或发布 macOS Desktop。共用 Runtime/Host 变更不能默认随 Desktop 发布，未来须独立补充 Desktop 验收。


### NXR-HOME-PUBLIC-ACCESS-20261006：Home 公网访问状态与开关

- 追加：Home 新增“链接二维码”按钮，弹窗仅展示 Cloud `GET /v1/space` 返回的账户固定 `spaceUrl`（`/u/<ownerUserId>`）；移除卡片设备域名。Local core-only `/cloud/space` 代理生成 QR，禁止临时 query/fragment、设备路径和身份不匹配的 URL；不修改 Cloud。弹窗每次重新读取，账户边界改变时关闭。
- 验证：3 项固定 URL/临时链接拒绝/401 保留测试及 3 项现有开关交互测试通过；Python/JS/中英文 JSON 语法通过。新增 Local API 需重启 App Dev Local 后刷新 Shell；本轮尚未实机激活与扫码验收。

- 状态：`implemented_unpublished`。Home 口号右侧环境卡片显示本机已登记设备的公网访问状态、地址与开关，复用现有 Remote status/reconcile/start/stop API；未配置时可进入账户设置。
- 区分关闭、连接中、已连接、连接异常与不可用；串行刷新、操作锁、防重复提交，Cloud 状态读取失败不显示陈旧在线地址且保留已启用设备的停止入口。接口继续执行现有身份与权限校验，无 Cloud 代码修改。
- 静态网页变更，App Dev 刷新 Shell 生效，无需重建。JavaScript 语法与中英文 JSON 校验通过；真实公网开关及 App Dev UI 尚未验收，未发布 Desktop。


### NXR-WEB-AGENT-CALLS-20261006：复用 Agent 能力与按需登录规划

- 状态：`implemented_activated_app_dev`。新增 `agent.call`，指定 Agent、导出能力、generation 和参数映射；服务端按 owner 固定活动版本，拒绝注入 IR、递归环、超过 4 层或 100 静态步骤的调用图。子步骤在同一父 AgentRun 中持久化并按调用路径命名，沿用浏览器上下文；返回值支持 `${steps.call.output.field}`，文件数组映射保留类型。
- 构建、探索、Review 修订接收当前网站能力目录，由 AI 判断是否需要认证，公开读取不强制登录。优先网站专用登录能力，缺省 `site.ensure-login` 根据清洗 DOM 和 opener 关联窗口判断状态；自动打开登录入口，只有真实 QR/OTP/凭据才暂停。Continue 后重新观察，不把用户确认或点击入口当作登录成功。
- 编译器 p1.3；侧栏增加能力选择/参数映射，探索调用的幂等键、run ID 随 checkpoint 保存，刷新或协助后续用原 run，停止取消调用。浏览器仍使用透明 BiDi Gateway；不读 Cookie，不创建新 Profile。
- 验证：20 项 Python 调用、编译器与 API 测试通过；14 项 Node 调用、输入、窗口与恢复测试通过；语法及 scoped diff 检查通过。广回归 33 项中 26 通过、7 失败：旧结果恢复、旧函数签名/Review 字符串、增强 DOM 之前的禁止正文及原有重复打开断言；本次未更改这些不相关断言。真实扫码和发布端到端仍待验收。
- Python/静态变更只需 App Dev Local 重启、侧栏刷新；无需重建或发布 Desktop。

- 实机激活：修复嵌入 server 先导入 agents 时的循环依赖（调用辅助模块延迟加载），补充独立进程启动顺序测试。App Dev Local PID 16125、端口 61916，Helper ready；3 次 health HTTP 200（189.9/1.5/0.9 ms）。重启控制请求曾超时，但随后新 Local 成功就绪；未重建 App。


### NXR-AUDIO-PACKAGE-UPGRADE-20261006：语言策略 Package 升级

- 状态：`packages_published_host_pending`。Stable Audio 0.1.1、音频套件 0.2.1 已发布；Repository metadata 263，匿名完整下载验签和 Dev Discover 验证通过。
- 103 项回归、真实签名安装的音乐/音效生成、取消 499、重启/卸载与套件 0.2.0 → 0.2.1 升级/三入口挂载通过。推理代码、权重、Runtime 未变化。
- Host 条件语言策略仍由客户端交付；本次没有升级 Dev 已安装模型或发布 Desktop，未证明先前 Cloud Task 502 已解决。
- 回执：`docs/ai2apps-audio-language-packages-release-20261006.md` 与 JSON；证据 `artifacts/audio-language-release-20261006/`。

### NXR-AUDIO-LANGUAGE-POLICY-20261006：模型声明驱动提示词翻译

- 状态：`packages_published_host_pending`。用模型签名元数据 `metadata.audio_generation.preferred_prompt_language: en` 替代全模型强制翻译。仅声明推荐英文的模型调用 work_simple；缺少字段保留原文，不推断模型名，不自动改写歌词/ABC。
- Stable Audio 音乐和音效的源码声明 en；ACE-Step、YuE2 未声明，保留原文。Host 对外提供 preferredPromptLanguage，Mini-App 按该值提示。当前只实现 en 目标，拒绝其他值，后续语言可扩展。
- 已发布 Stable Audio 0.1.0 的签名字节未变；要让安装版生效，需发布模型 Package 新版元数据、升级 Mini-App 并交付 Host。运行实例尚未部署，不代表 Cloud 502 已解决。
- 覆盖英文偏好调用、缺省不调用、中文原文保留、失败和取消；取代此前“所有模型每次翻译”的策略。


### NXR-AUDIO-TASK-502-20261006：简单 Task Cloud 故障诊断

- 状态：`local_fix_cloud_diagnosis_pending`。Dev 18:06:24 的翻译 502 来自 Cloud `/v1/ai/responses`，上游 code 为 AI_PROVIDER_ERROR，模型为 openai/gpt-5.6-luna；根因尚未由生产日志确认。
- 简单 Task 调用省略固定 temperature=0；错误展示模型/HTTP/白名单 code，不转发任意上游诊断文本。未变更模型选择或跳过翻译，未发布/部署。
- 新增 ASGI 合同回归覆盖成功和 502；服务端交接见 `docs/ai2apps-cloud-audio-task-502-20261006.md`。仍需 Cloud 生产排查与完整真实推理验收。


### NXR-AUDIO-PROMPT-TASK-20261006：生成前翻译润色

- 状态：`implemented_unpublished`。音乐、音效、歌曲每次调用音频模型前，使用系统 `work_simple` 默认模型将描述翻译润色为英文；保留声音语义与排除条件，不改歌词和 ABC。无缓存或原文静默回退。
- 复用 Host 现有受认证模型调用路径，保留 mount/actor 上下文。未配置模型、无效回复、120 秒超时均终止生成；取消翻译时不得进入音频推理。
- Mini-App 保留原文草稿，成功后展示实际送入模型的英文描述；共享 Preview & Output 不变。Host 与 Package 源码需后续部署/升版，本轮不读取 Cookie、不覆盖已发布制品。
- 取代上一项“无自动翻译”的临时提示方案。65 项 Host/音频回归、18 项歌曲交互、16 项安装菜单交互、Host 取消消息链与 Quick Read 输出作用域检查通过；尚未做真实 Simple Task + 音频模型端到端复测，未在运行实例部署。


### NXR-STABLE-AUDIO-PROMPT-LANGUAGE-20261006：音效输入语言提示

- 状态：`implemented_unpublished`。用户反馈中文“雷鸣般的掌声”与输出不符；源码链路将 prompt 原样传给 Stable Audio T5Gemma，没有翻译。上游明确说明英文描述训练、其他语言效果下降。
- 音频套件在选择 Stable Audio 时增加中英文语言提示，说明使用具体英文描述且当前无自动翻译；不影响 ACE-Step，不改写用户输入。已发布 0.2.0 制品不变，后续 Package 升版需纳入。
- 此修正只补产品提示，不代表已经完成音频语义质量修复。尚未对用户音频进行听觉判定或中英文同种子生成对照；实际不符原因仍需结合该对照确认。
- 依据：https://github.com/Stability-AI/stable-audio-3/blob/main/docs/guides/model-overview.md 。


### NXR-SPARK-QWEN38-20261006：CUDA 模型与 Runtime 候选

- CUDA Runtime 0.3.0 / 27B Package 0.2.0 已发布，Repository 266/267，保留原身份，
  新增 `nvfp4-sm121` 能力与 FlashInfer AOT 内核；Spark Discover 升级、正式 Host
  文本/思考推理和重启恢复已通过（161 / 43）。Runtime staged 后按合同重启激活。
  用户已授权本次升级发布使用 Dev Cookie，发布查询完成后不再读取。
- 独立原生 Runtime 的图像/多图/128 工具/思考/SSE/取消恢复均通过，Qwen2.5
  共享 Runtime 回归通过；AOT 进程映射证明不依赖开发缓存。构建器修复重复
  distribution 优先级、排除开发 `.pth`，12 项合同/构建器测试通过。
  两个制品已用原 Publisher 签名验签并发布；Runtime 上传 504 后按既有 submission
  ID 恢复成功，没有重复提交。完整状态见
  `spark/NATIVE-NVFP4-RELEASE-20261006.md`。
- 当前 27B 原生发布链路已验收；Flash 严格路由、FP8/线性注意力优化、Linux
  Worker 遥测仍未完成。没有发布 Desktop，也未修改 Cloud 后端。
- 原生 NVFP4 后续：新增 `spark/NVFP4-PLAN.md`、显式 CUTLASS 内核数值/profiler
  探针和保留 packed 权重的 168 个 MLP Linear 实验加载器。独立 nvfp4-venv
  固定 Torch 2.10.0+cu130 / FlashInfer 0.7.0.post1。状态 `in_progress`，
  不属于已发布 0.2.0/0.1.0，不宣称整模正确或性能达标；FP8 部分暂保留 BF16 对照。
- NVFP4 实验进展：`spark/native_nvfp4.py` 提供显式原生 Linear，无 BF16 回退；
  3 组 profiler/数值内核探针、9 组真实权重层通过。官方 compressed-loader 路径的
  168 个原生 MLP 整模数学/中文输出通过，常驻 30.91 GiB，短推理峰值 31.14 GiB。
  手工 meta loader 的原生/BF16 控制实验失败，保留诊断，默认入口改用通过的官方路径。
  扩展能力及固定 token 基准正在验证；尚未改变正式安装的 Runtime/Package。
- NVFP4 模型级扩展能力和 BF16 同条件对照已通过：69-token 提示、相同 64-token
  强制序列、三轮解码中位数 4.077→6.285 t/s（+54.15%）；常驻 52.70→30.91 GiB。
  图像、工具模板/结果续答、思考、增量输出和取消通过。正式断网 Runtime/Host 集成
  仍待实施，当前状态 `native_model_validated_not_packaged`。完整回执
  `spark/NATIVE-NVFP4-20261006.md`。
- 状态：`in_progress_publication_acceptance`，27B 已签名，Runtime 已完成 4 GiB 合同配套与签名；未发布或升级 Desktop。
- 新增 Qwen3.8 CUDA Package 源码，复用 Mac 的 service/model ID 和已签名 checkpoint
  distribution；当前 BF16 基线限制 8192 context / 2048 output。图像、工具往返、
  思考分离、增量 SSE、断连恢复已在断网只读 Docker Worker 验证。
- CUDA Runtime 构建闭包加入 accelerate、compressed-tensors、torchvision、jsonschema
  及 Triton，支持显式开发环境 site-packages overlay，输出仍不携带 .pth。
  新 `qwen38-bf16` 能力防止模型错误使用旧候选。最终独立载荷在无开发 venv 的
  Docker 内通过图像、工具、思考、SSE、显式取消、断连和恢复验收。
- 不修改 Mac 模型或生产 Runtime。记录见 `spark/QWEN38-ALIGNMENT.md`。
- Flash 源候选 `ai2apps-model-qwen38-flash-next-cuda` 标记 experimental、parity-pending，
  复用 Mac 模型身份与签名 distribution；基础 Worker 图像/工具/思考/SSE/取消恢复
  通过，严格层级路由、性能和签名安装验收尚未完成。新增有界十专家批量搬运，
  两组微测输出逐位一致且整模数学/EOS 正常，完整基础 Worker 回归通过；
  26-token 流式短请求 77.72→39.76 秒，尚非稳态性能门槛或 Mac 数值对齐。
  扩展 128 工具/多图验收也通过，加载的源文件摘要与当前候选一致。
- 两个 CUDA Qwen 模型共享纯 Python Worker 协议实现与输出解析器，放在
  `ai2apps/model_worker/cuda_qwen.py` / `qwen_output.py`；按需导入 Torch，
  checkpoint 加载器仍在各模型 Package。包含新模块的独立 Runtime 已重建，
  完整 27B 回归通过：`spark/evidence/qwen38-shared-runtime-check.json`。

- Registry 明确允许官方 CUDA Runtime inference_provider 并选择管理员 Runtime 上传路径，
  保留普通包路径、现有大小限制和 oMLX 历史重启回退；Registry 全部 47 项回归通过。
  Cloud 配套尚待部署，不能据此声明正式可安装。交接文档：
  `docs/ai2apps-spark-runtime-registry-requirements-2026-10-06.md`。

- OpenAPI 1.59.0 配套：仅两个官方 service Runtime 的文件/envelope/ZIP/下载预算放宽至
  4 GiB，普通合同 1 GiB、上传 25 MiB 不变；构建、哈希、解包检查采用分块 IO，
  服务定义读取限制 1 MiB；验签仍先于安装 ZIP 解析。67 项合同/Registry/构建器测试通过。
  已签 Runtime 外层 SHA-256 `ea4eacf71237c9af8c3c1e48bdda20ac368869e1fce750b12a58bf61b05bfdd6`，
  1,655,127,656 bytes，已发布至 Repository 264，Spark 安装验收进行中。此共享客户端修改需下次 Desktop 评估。

- Spark 安装发现 Linux OS 兼容性误将内核版本作为发行版版本，Registry 与 Service Manager 现共用 `platform_compatibility.local_os_version` 读取 VERSION_ID，
  仍拒绝缺失和过低版本；Registry 50 项测试通过。Runtime 生产发布回执：
  `spark/RUNTIME-0.2.0-PRODUCTION-20261006.md`。

- 2026-10-06 后续：用户批准后 Runtime 0.2.0 已在主 Spark Host 安装完成；27B 0.1.0
  已发布至 Repository 265（submission 04c95428-38b6-42b5-b346-1e6cf02bc779）。
  正常模型安装暴露目录详情 package.modelInstall 未提升到顶层，已修复三个目录投影
  （安装计划、内存要求、发现分类）以及重复装饰的 source 字段处理；51 项 Registry 回归通过，
  已部署 Spark，正式 Host 模型验收继续。
- 正式安装进一步发现 Service Manager 未将 Linux aarch64 归一到合同 arm64；
  与 Registry 共用 normalized_architecture，仍拒绝异架构。Package 生命周期 36 项
  （开放本机回环端口后）、Registry 51 项通过。主 Host 的 27B 安装、checkpoint 校验、
  服务启动全部完成，截图 `spark/evidence/qwen38-installed-20261006.png`。
- 正式 Host Chat 已返回正确结果 42（完整冷启动 141.72 秒）；为当前 Spark 的
  27B 持久化 max_tokens=2048。新机器安装默认预算、Linux Worker 内存遥测及
  Flash 数值/性能对齐仍需后续处理。当前发布验收见
  `spark/QWEN38-0.1.0-PRODUCTION-20261006.md`。
- systemd 重启后，新 Chat 使用持久化默认输出预算及默认思考模式，19+24 返回 43；
  160.46 秒包含冷加载。正式安装与 Host 文本/思考/恢复验证完成，Flash 和性能对齐仍未完成。
- 标准发布入口发现 agent_builder 的循环导入，packages 改为直接导入 extensions.models，
  service 在 create_ir_run 中按需导入 Agent 常量；24 项发布器/Agent Builder 回归通过。
  两项共享修复纳入下次 Desktop 评估，未发布 Desktop。

### NXR-VOICE-STUDIO-STARTUP-20261006：启动反馈与加载链路优化

- 状态：`implemented_and_tested`；未发布，未测量真实冷启动耗时。
- 所有 Package 就绪检查移出宿主启动关键路径；基础数据与草稿并行读取，草稿恢复后只加载一次项目详情；五项独立历史/输出/能力请求并行执行，失败分别反馈。
- 主内容就绪后即退出启动等待，无需等待历史和能力恢复；冷启动及 Mini-App 切换显示“正在启动”提示和加载指示，异常退出等待并可刷新重试。
- 验证：前端 scope 回归覆盖未完成的 Package 检查不阻塞主界面、项目仅恢复一次、后台并发及切换等待状态；JS 语法检查通过。仅宿主 HTML/CSS/JS/翻译改动，刷新页面生效，无需更新 Runtime 或 Suite Package。


### NXR-WORKER-BACKEND-IMPORT-20261006：独立 Runtime 的按需适配器导入

- 状态：`verified_on_spark_unsigned`。CUDA Runtime 独立载荷发现公共 Model Worker 初始化会
  提前导入 oMLX，导致不含 oMLX 的 Runtime 启动失败。现将 oMLX 适配器公开
  导出改为按需加载，保留原有导入 API；协议及 HTTP server 可独立使用。
- 新增禁止 oMLX/MLX 导入的独立进程回归和既有适配器导出兼容验证。
- 相关 48 项回归通过；独立 CUDA Runtime 在 Docker 中鉴权、推理、SSE、
  drain/resume 通过。发布准备见 `spark/RELEASE-0.2.0.md`。
- 共享模块影响后续 Desktop/Runtime，尚未构建或发布 Desktop。

### NXR-AGENT-RELOAD-PROFILE-20261006: Sidebar recovery and Profile tab identity

- Status: `activated_in_app_dev`. Exploratory progress previously lived only in Sidebar memory; Local-origin replacement/context remount could erase it. Added owner- and Tab-bound atomic Local recovery points with 24-hour TTL, ordered writes and a required pre-action checkpoint. Reload restores goal, attachments and timeline in a paused state; an in-flight action is marked unknown for observation before repeating. Tab switches retain the old Tab checkpoint without executing on the new Tab.
- Native browser Profile windows now bind newly created tabs to their managed Container. Current App-Dev session metadata showed Weibo in Container 0 while the managed Profile has Container 6; this proves a mismatch, not which Container held the earlier login. No Cookie/credential read, migration or deletion. Existing tabs are preserved.
- BiDi reconnect now retains an authorized Tab across URL changes/login redirects and rejects missing bound Tabs instead of choosing another Tab by stale URL.
- Verification: 17 Node recovery/window/profile tests, 26 Node input/upload/DOM regressions, 4 Python checkpoint tests (including owner/Tab isolation API), 5 Python login/attachment tests, and JS syntax passed. Gallery regression has one unrelated existing cache-tag assertion failure. Fixed App-Dev rebuilt through build-app-dev-environment.sh; verify-release-app.sh and strict deep codesign passed. Local restarted and checkpoint API confirmed in live OpenAPI on port 61912; native title verified. Opening Profile and adding a Tab produced live session metadata containers [6, 6], and the new Tab Sidebar showed no unrelated prior result. No end-to-end Weibo sign-in/upload/publication was performed. Activation initially encountered an old Local process holding the instance lock after SIGTERM; exact old App-Dev PID was terminated and the new service is online. Historical progress predating checkpoints cannot be restored.


### NXR-CLOUD-CAPABILITIES-20261006：Cloud 1.58 客户端对接

- 状态：`verified_on_spark`。Peer 注册前读取并缓存能力发现；关闭/未知协议不请求
  Device keys/challenges，300 秒默认刷新，旧 Cloud 404 不推断启用。
- 托管 Cloud 聊天按模型目录 toolOptions.maxTools 预检，不按模型名猜限制、
  不截断工具；保留超限 details/param，Agent 尊重不可重试错误。
- 共用 broker/cloud gateway/Agent runtime，需评估未来 Desktop；尚未发布。
- Cloud 升级后 Spark 原有客户端已真实完成 workspace.write/read，并核对文件。
- 新客户端部署后再次读回通过，关闭协议的密钥轮询停止；76 项本地回归通过
  （退出时本机沙箱 Metal 清理警告）。详见 `spark/CLOUD-158-ACCEPTANCE.md`。

### NXR-SPARK-CHAT-EMPTY-STREAM-20261006：聊天空流渲染兼容

- 状态：`verified_on_spark`。Spark 实机验收发现聊天切换/请求结束后 Alpine 仍求值隐藏
  的 thinking token 文本，对 null currentStream 解引用报错。改为可选链及零默认值。
- 共用 `ai2apps/web/templates/chat.html`，需纳入后续 Desktop；不重建或发布 App。
- 已部署到 Spark 开发实例；刷新并切换历史会话后未再出现该控制台错误。
- Spark Host 的云端普通聊天及重启后会话恢复已验证；Agent 另被 Cloud
  `INVALID_AI_TOOLS`（最多 32 functions）阻塞，不属于此渲染修复的完成范围。

### NXR-AGENT-ATTACHMENT-INPUT-20261006: Agent input and attachment upload

- 2026-10-06 live image-post diagnosis: Source normalization discarded `arguments.asset_ids`, so an observed hidden file input was incorrectly executed as ordinary text input and returned `not_found`. Preserve attachment IDs through normalization and preserve explicit target refs in client upload dispatch. Regression: 1 Python normalization-to-IR test and 6 Node input/upload tests passed. User restarted App-Dev Local; activated on port 56282. Live WebAgent completed 4 successful steps (text input, native BiDi image upload, send, inspect). Verified visible post https://weibo.com/7015980724/RlnO6A98U with exact text 马上又要过年了 and supplied 封面参考.png; compose cleared and send disabled. No duplicate send. Planner still issued an unnecessary image-preview assistance request before continuation; upload itself succeeded. No Desktop publication.

- Status: `activated_in_app_dev`. Ordinary compose input and upload-entry clicks no longer require generic confirmation; sensitive input, CAPTCHA and legal consent retain their explicit policy. Assistance hints show the actual reason instead of assuming login.
- Enhanced shared DOM observation includes framework pointer controls and hidden file inputs. Planner receives file_inputs and supplied asset IDs; client uses the owner-bound Gallery browser-transfer route and native BiDi input.setFiles. Ambiguous upload controls are not guessed; failures return to the planner. Reusable attachment IDs bind to runtime file parameters.
- Verification: 26 Node tests and 5 Python tests passed, plus JavaScript syntax checks. Real Weibo image upload and publication verified on 2026-10-06; see live diagnosis entry above.
- Activation: App-Dev Local restarted during the subsequent Sidebar recovery/Profile fix; current source API loaded on port 61912 and new Sidebar mounted. Real Weibo image upload/post now verified on port 56282 after user restart. No Desktop publication.


### NXR-YUE2-PACKAGE-20261006: YuE2 model Package publication

- 状态：`packages_published_host_pending`。YuE2 模型 0.1.0 与 audio-generation-suite 0.2.0 已发布；Repository metadata 260，公开完整下载/签名/哈希与 Discover 验证通过。主模型、VAE 的 HF/MS 双源全量字节及 930 pieces 验证通过，原始许可仍须用户在 ACPF 确认。
- 已安装真实推理、取消 499、重启、卸载及共享输出保留验收通过。最终模型仅改展示信息、App 仅省略可选目录投影；最终签名安装验收通过。
- 安装环境冷调用生成 46.6 秒音频耗时 353.69 秒，显著慢于独立版 22.8 秒；差距待定位，模型卡已披露。Runtime 1.8.10 不变。
- 详见 `docs/ai2apps-yue2-audio-packages-release-2026-10-06.md` 及 JSON 回执。Package 发布不代表生产 Desktop 已获得 Host 工作流支持。

### NXR-SONG-MINI-APP-20261006：歌曲创作 Mini-App

- 状态：`packages_published_host_pending`。audio-generation-suite 0.2.0 已发布同包音乐、音效、歌曲三个入口；歌词编辑、规划模式、ABC 导入、时长上限、种子、草稿、阶段进度和取消。
- Host 增加签名工作流筛选、Runtime 1.8.10 协议、共享输出及歌曲 ACPF。YuE2 模型已上架；Host 必须随后续 Desktop 交付，当前生产 Build 2258 不具备歌曲 broker。
- 原 109 项 Python、18 项中英文交互及跨 Mini-App 输出检查通过；本次另完成已发布依赖的真实签名安装推理及最终三入口挂载验收。App-Dev UI 与 ACPF 入口实测通过。
- 阶段保存/局部重跑不在本版；输出由 Host Preview & Output 拥有。见 `docs/ai2apps-song-mini-app-0.2.0.md` 和上述发布回执。

### NXR-RUNTIME-YUE2-20261006：音乐工作流 Runtime 1.8.10

- 状态：`runtime_published_host_pending`。Runtime 1.8.10 已正式发布，Cloud/GitHub/ModelScope 三源active；submission `6b409372-8180-45fc-b5ee-4011b7ab8264`，Repository metadata 258，Source revision 6。
- 基线为已发布1.8.9；唯一Worker源码差异为版本化音频生成协议，支持自动时长、规划模式、内联ABC及token/guidance参数。Python3.11与MLX0.32.0等原生依赖不变，旧音乐/SFX语义保留。
- 制品SHA-256 `3bd58e16f5cd54cca9d205077f6396a9536a0097f25c049dda720bf0fc3c6256`，380899239 bytes；Developer ID、公证/staple/Gatekeeper、真实签名安装与依赖解析通过。
- 验证：55项Worker、15项多源/Range、13项原生Python3.11测试；已安装Runtime真实HTTP生成46.6秒YuE2音频且WAV哈希与独立优化版一致，取消499、输出清理、停止/重启/卸载通过。三源完整字节及最终46个piece/签名Snapshot通过。
- YuE2代码/权重仍属于后续模型Package，Host/Mini-App接入与Desktop发布未包含。未做第二台Mac验证。见 `docs/ai2apps-runtime-1.8.10-release-2026-10-06.md` 与JSON收据。

### NXR-PACKAGE-CANDIDATE-RECOVERY-20261006：未发布候选撤回

- 状态：`cloud_deployed_package_recovery_pending`。Cloud OpenAPI 1.57.0 已部署，标准 `scripts/publish_signed_registry_artifact.py`
  增加显式 `--withdraw-submission --submission-id --expected-artifact-sha256 --withdraw-reason`，
  只撤回，不隐式重新提交或批准。调用 Cloud 正式受保护 API；原 Cookie 授权和 step-up 边界不变。
- 仅标准发布工具与合同变化，不修改 H3 已验收制品字节，不重建 Desktop。
  `--submission-id` 恢复会先查询实际状态，只执行剩余步骤；approved 不重复审批，
  published 不重复发布，withdrawn 明确拒绝。
  Cloud 对接合同：`/Users/avdpropang/sdk/ai2apps-cloud/docs/package-candidate-recovery-v1.md`。
  H3 0.10.0 的生产撤回/重新发布仍须真实授权会话，不能将此实现条目标记为 Package 已发布。
- 验证：标准脚本 12/12 Mock 回归及 Ruff 通过；Cloud 真实 accepted 字节在隔离数据库完成
  撤回/修正/重新审核/发布回归。生产回执：`/Users/avdpropang/sdk/ai2apps-cloud/docs/h3-avatar-recovery-production-2026-10-06.md`。

### NXR-AUDIO-GENERATION-MINI-APPS-20261005：音乐／音效 Mini-App 套件

- 2026-10-06：两个模型下拉框加入“安装模型…”入口，按音乐／音效能力触发 ACPF，返回刷新并保留选择；16 项交互检查及 7 项相关回归通过。真实推理证据来自此前候选；本次仅修改菜单并重新签名。
- 状态：`signed_candidate_host_pending`。同一 App Package `ai2apps/audio-generation-suite` 0.1.0 提供音乐生成和音效生成两个 Voice Studio Mini-App；共享 Host 输出、挂载绑定模型调用及 ACPF 许可流程。
- Host 增加音乐／音效语义能力、模型选择、受控推理和取消；不得将模型 Worker、权重路径或凭证暴露给 Frame。须随下一版 Desktop 评估，未发布 Desktop。
- 验证：73 项相关回归、另增断开取消测试、共享输出跨 Mini-App 选择、源码隔离／热刷新、真实签名包安装后两个 mount 的 10 秒生成及原子启停卸载通过。候选 SHA-256 `6e070e0f01e2900b9fc72262ed20049dcfd929463eae7738289109c5898dc658`，12,892 bytes；未发布 Cloud。详见 `docs/ai2apps-audio-generation-suite-0.1.0.md`。


### NXR-CODEX-SYSTEM-20261005：系统级 Codex 接入

- 2026-10-06：修复 Todo 在 Codex Desktop 中打开按钮无响应：绑定区和当前执行区由 iframe 自定义协议链接改为调用系统 Codex POST /threads/{id}/open；要求 Coder 权限和 loopback 请求，严格 UUID 校验，macOS /usr/bin/open 固定协议 argv 无 shell，10 秒超时回收进程，界面展示错误。验证：Python 打开成功/错误/非法参数 2 项、Node 当前执行 7 项、JS 语法通过；sandbox 内 LaunchServices 不可用，获准在原生环境打开当前会话命令退出 0。需重启 Local 刷新，尚未做 Todo 原生点击端到端验收。

- 2026-10-06 结构化回报：Codex 新会话及 Desktop 原生投递统一要求带版本/运行 ID 的 ai2apps-result JSON；严格解析最终 assistant 回报，支持 completed/partial/waiting_user/failed、完成内容/验证/剩余/提问。当前执行及历史显示 AI 自述及待确认说明；缺失/无效/错误运行 ID 不推断成功，任务状态/百分比不自动修改。27 项 Python 与 6 项结果 UI 测试通过。源代码完成，实际模型遵从及 App-Dev 重启后 UI 验收尚未完成；未重建发布。

- 本轮原生队列回归：76 项 Python、29 项 Node 测试通过；历史执行区同样隐藏伪停止入口，后端拒绝 Desktop 任务本地停止时返回 422。

- 2026-10-06 原生投递：已有会话改用 Codex CLI queue，避免 Desktop active writer 冲突；运行标识关联只读 turns/list 记录，以 completedAt 判定终态，回传输出/步骤。持久化投递意图和队列 ID，Local 重启仅恢复跟踪，模糊投递不自动重试；Desktop 执行持续占用 Todo 名额。审批/回复/停止在 Desktop 完成，Todo 不伪装远程取消。新会话保留直连路径。真实原生消息消费及新观察器读取精确回复/终态已验证；Helper UI 超时，App-Dev 重启及实际 Todo 端到端验收待完成。已知边界：用户在 Desktop 删除尚未执行的排队消息时，缺少回合收据，当前仍保持待确认，尚不能自动释放名额。未重建或发布。

- 2026-10-06：修复外部会话 active writer 冲突的处理：解释 Desktop 写入权占用，当前执行区域以“更换会话”替代无效重试，兼容历史错误；resume 失败时不发送 unsubscribe/interrupt，不自动创建替代会话。8 项 Python、3 项当前执行 UI 测试通过。此改动不代表能直接派发到 Desktop 已持有会话，真正 Desktop 会话派发仍待接入；未重启或发布。

- 2026-10-06：工程选择优先只读 Codex Desktop 保存的 local-projects 名称和主目录（兼容旧 saved roots），不可用时回退会话目录；Todo 改为明确的工程下拉选择，选择后自动加载会话，保留其它目录入口。此为本机元数据兼容适配，不是公开 App Server 工程 API；不写 Desktop 状态，不读取凭据。真实读取 17 个工程并与 Desktop 工具列表核对，11 项 Python 与 27 项 Node 测试通过；需重启 App-Dev Local 并刷新页面加载，未重建或发布。

- 状态：`in_progress`。从 Todo 提取 `ai2apps.codex`，由 PlatformRuntime 持有共享 App Server 传输、目录/会话查询、会话互斥、输出/审批/问答与取消清理；新增独立 `/v1/platform/codex` 接口，要求 Coder 权限，不依赖 Todo 插件配对。
- Todo 作为首个调用方保留任务绑定、三槽队列与持久执行记录；反向 Todo MCP 插件独立保留。目录来源仍是会话 cwd 分组，不声称是 Desktop 注册项目列表；互斥只覆盖本 Local 实例。
- 验证：87 项 Python 回归与 27 项 Node 测试通过，包含无 Todo 的系统接口、跨调用方同会话互斥和关闭清理；旧 MCP 回环测试经批准在沙箱外复测通过。此前真实临时只读回合已通过；当前 App-Dev 仍需重启 Local 后完成端到端验收。未重建或发布 App。

### NXR-MUSIC-PACKAGES-20261005：ACE-Step / Stable Audio 模型 Package

- 状态：`model_packages_published_host_pending`。`ai2apps/model-ace-step-mlx` 0.1.0 已发布，Package SHA-256 `c31672d7842b621d8409075c08957085943f0e3864736f618c0e103dcec94eff`，75,942 bytes；submission `eccb9f9c-da2c-4081-9c1e-9535d3fed7b4`，metadata 253。依赖 Runtime >=1.8.9。
- 权重：`dist_ai2apps_ace_step15_turbo_mlx_v1` 已发布，HF/MS 固定 revision、27 文件／1,203 pieces／10.09 GB 双端完整核验；公网 Checkpoint Index 103 验签通过。MS 临时连接失败后实际断点恢复通过。小型代码包走 Cloud，权重独立双源。
- Host：独立 `audio_generation` 类型与 endpoint、签名能力声明校验、音频生成资源预留、仅验证 Registry 回执可激活的 NPZ 布局。涉及 `ai2apps/model_providers.py`、`ai2apps/checkpoints.py`、`ai2apps/worker_resources.py`。这些 Host 改动仍须随未来 Desktop 发布；本轮未构建或发布 Desktop。
- 验收：78 项 Host/Worker/checkpoint 与 10 项多源测试通过；三分支真实 MLX 10/120 秒生成、采样取消与内存释放通过。ACE 真实签名包 Sandbox 安装、10 秒 WAV、取消 499、重启、卸载和公开下载验签通过。完整 120 秒范围要求 48 GiB；测试机 M5 Max 128 GiB，第二台 Mac 未验收。
- Stable：`ai2apps/model-stable-audio-mlx` 0.1.0 已发布，SHA-256 `9a5622efb92316935d609164a1b943ff21e96422c2254f9cd4bf3f7505579826`，199,759 bytes，metadata 254。Music/SFX 各 1.70 GB／8 文件／204 pieces，HF/MS 完整双源核验与公网 Index 104/105 验签通过。用户确认非商业安装体验用途；ACPF/Discover 下载前绑定具体清单及条款哈希的明确许可同意，完整 Stability/Gemma 条款与 Notice 随权重分发。真实签名包 Sandbox 两分支生成、取消 499、重启、卸载通过。
- 授权：两个模型 Package 发布验证完成，对应 Dev Cookie 授权均已结束。详见 `docs/ai2apps-audio-model-packages-2026-10-05.md` / `.json`。

### NXR-RUNTIME-MUSIC-20261005：音乐生成 Runtime 1.8.9

- 状态：`runtime_published_host_pending`。Runtime 1.8.9 已正式发布，Cloud/GitHub/ModelScope 三源 active；submission `1aaa7445-e1a7-4b5a-8178-039dcbea1dd5`，Repository metadata 252，Source revision 6。
- 以已发布 1.8.8 精确载荷为基线，仅新增 `audio_generate` / `/v1/audio/generations`、请求验证和 `audio-generation-v1`；Python 3.11 与原生依赖不变。SHA-256 `37cba2443a5848aac090957d37ef0ccaaef7081c58483d257cf6b3c692c4ba02`，380695388 bytes。
- Developer ID、公证、staple、Gatekeeper、Publisher 签名、真实签名包安装与三模型 HTTP 推理/取消通过；36 项 Worker 回归、5 项多源回归、三源完整摘要、Cloud 46-piece 预检及匿名签名快照/下载验签通过。第二台 Mac 加载验收未执行。
- Cloud 500 经 Cloud 空间清理及用户恢复 step-up 后解除；ModelScope 严格 200 + Content-Range 已按既有策略通过预检和管理员激活。手册新增明确 200/206 判定表、单管理员审批矩阵和防回归清单。
- 此项仅完成 Runtime 发布，未发布 Desktop；模型 Package、Voice Studio Host 接入及 Desktop Build 仍独立评估。详见 `docs/ai2apps-runtime-1.8.9-release-2026-10-05.md` 与 JSON 收据。

### NXR-MUSIC-MLX-20261005：ACE-Step / Stable Audio 本地推理实验

- 状态：`prototype_verified`。`experiments/music_mlx/` 固定官方源码及权重版本，已下载 ACE-Step 1.5 Turbo 与 Stable Audio 3 Small SFX/Music，建立离线 WAV 推理、转换、隔离调用和时间/内存/音频有效性记录入口。
- 后端边界：Stable Audio 使用官方纯 MLX 路径；ACE-Step 原生路径复用固定 `mlx-audio pc/add-ace` 提交，官方权重转换后文本编码、1.7B LM、条件网络、DiT、VAE 均以 MLX 执行。独立 native 环境未安装/导入 PyTorch。保留单独官方混合参考路径，并显式禁止 DiT/VAE 静默回退；两条路径不能混淆。
- 发布边界：仅本地实验，未接入生产路由、未创建/构建/发布 Package、未修改 Cloud、未重建 Desktop。后续接入需增加显式音乐/音效能力，并走 Voice Studio Host 共用 Preview & Output。
- 验收：M5 Max / 128 GiB，10 秒 SFX 0.698 秒、30 秒 Stable Music 0.629 秒、30 秒 ACE 配乐 8.334 秒、30 秒 ACE 中文歌词样本 6.217 秒（含加载，不含进程/Metal 启动和下载，非驻留稳态基准）。MLX 峰值分别约 1.71/1.93/12.76/12.76 GiB。音频时长/双声道/非静音/有限值校验通过；3 项桥接测试及真实 5 秒 Artifact 调用通过，两个环境依赖一致性检查通过。详见 `experiments/music_mlx/validation.json` 与 `README.md`。
- 剩余边界：试听与官方全链路数值 parity 尚未验收；ACE 规划元数据不保证严格遵循提示时长/BPM。正式接入前需 Runtime 封装、Stable Audio 授权核对及 shared output/cross-Mini-App 测试。

### NXR-RELEASE-015-2258-20261005：Desktop 0.1.4 Build 2258

- 状态：`released_pending_target_mac`。2026-10-05 13:57（北京时间）已完成签名、公证、
  GitHub/ModelScope 双源预检与 Cloud 0%→100% 发布；生产基线推进到 0.1.4 / Build 2258。
- 源码提交：`51d30e440d942eb04d254f1e5a796a29d39f13ac`，独立 clean worktree 构建，已同步
  GitHub main。原开发工作区与未提交实验内容保留；本条不表示后续新改动也进入该提交。
- 生产摘要：`d6aa53c228641e800232e65189d137a7e97236b67ec1c1704140cc28899c731d`；
  ModelScope revision：`feb3dd54e5d8daf9c4ec8ede754238fd013d766f`。
- 本次纳入条目、延期项目、测试、公证与生产验收归档：
  `docs/ai2apps-desktop-0.1.4-build2258-release-2026-10-05.md`。
  回执列明的 NXR 源码实现为 `included`，下方“未发布”等文字是开发历史；真实模型/UI
  验收限制仍保留，目标 Mac 升级闭环待完成。
- Cloud 根分区仅余约 240 MiB，本次使用内存盘完成预检且已清理临时工件；仍需运维清理/扩容。
- 本次未重建或重启 Dev/App-Dev/Test。

### NXR-MEDIA-VOICE-I18N-20261005：音视频扩展 Package 多语言

- 状态：`package_published_host_pending`。`ai2apps/media-voice-studio-suite` 0.2.1 已发布；音视频语音工作室 Suite 的 Package、六个 Mini-App 名称/描述及页面动态 UI 已补齐中英文，英文为回退；用户字幕、角色名、文件名和模型名不被翻译。
- Studio 共用 mount 客户端统一解析 Package Mini-App `localizations`，将当前 Host locale 写入受约束 mount context 与 Entry URL；Voice、Video、Imagine Studio 均采用同一解析入口。旧 Package 没有本地化字段时仍使用原有 name/description，不改变安装、能力或输出合同。
- 开发手册明确区分 Package、Provider App 与每个 `mini_apps[]` 的本地化名称，给出 manifest 示例、locale 回退、动态 UI/accessible name 要求和 App-Dev 中英文真实 mount 验收步骤；localized metadata 与 Studio 设计清单同步。
- Package 发布：0.2.1，submission `af5ec328-6bab-4d5a-a07f-9a38efb3d381`，review `ea7892c9-cb0a-4220-98cb-4979b242071f`，Repository metadata version 247；artifact SHA-256 `c502c05dac2b1c7ef454a202e0f6937186b21c6c229a792599adc9dbda77771b`，49980 bytes。无 Runtime/模型依赖变化；小型 Package 继续使用 Cloud 单源。发布回执：`docs/ai2apps-media-voice-studio-suite-0.2.1-release.md`。
- 发布边界：Package 已发布；Desktop Host 静态客户端仍须纳入下一 Desktop 候选，当前 Package 发布不等于 Host 已投产。App-Dev 源挂载可继续刷新验收，尚未构建或发布正式 Desktop。
- 验证：Package i18n/字幕编辑 Node 测试、148 项相关 Package/Host/Sandbox/能力与工作流 Python 测试、Ruff、JavaScript 语法、可复现 Contract 构建、精确签名包隔离安装及六 Mini-App 发现均通过；公网无 Cookie 回读确认 artifact 与 envelope 精确一致。较宽 extensions 回归中的两项既有 Todo 清单断言失败，与本改动无关。

### NXR-AUDIOBOOK-EDIT-SAVE-RACE-20261005：片段重生成使用最新编辑文本

- 状态：`implemented_and_tested`；未发布。
- 同一项目/片段的保存按编辑顺序串行提交，旧保存响应不得覆盖等待期间的新编辑；再次生成等待本次文本保存完成。
- 增加旧保存未返回时修改文本并立即重新生成的前端回归场景。仅修改宿主静态 JS，刷新 Shell 即可载入；无需 Runtime 或 Suite Package 更新。
- 验证：`node tests/test_ai2apps_readaloud_scope.cjs`、JS 语法检查、`tests/test_ai2apps_readaloud_tasks.py` 16 项及 scoped diff check 通过。未使用真实模型重跑用户片段；Python 退出时有沙箱 Metal 设备不可用提示，测试本身全部通过。


### NXR-SHELL-STARTUP-NAVIGATION-20261005：区分刷新与 Helper 重启导航

- 状态：`implemented_and_tested`。普通刷新保持当前 Shell URL/App；Helper 菜单重启 Local 和 Helper 自身启动产生新 Home epoch，进入 Home。Runtime/API 自动重启不产生 Home epoch，保留 ACPF 恢复。
- Shell 仅在原生重连明确标记 resume 时查询 ACPF 自动返回，忽略历史 failed/cancelled/unsupported 会话，并防止异步恢复覆盖用户新导航。不删除历史会话，不把失败记录清理伪装成修复。
- Helper main.swift、ai2apps/web/static/js/shell.js、公共 apply-shell-navigation.py 及 Dev/Release 构建入口统一实现。Dev/App-Dev 已通过各自固定脚本重建并启动，保留实例数据；两个包深层严格签名通过，App-Dev 完整 verify-release-app.sh 通过。Test/Release 下次构建自动包含，未发布生产。
- 验证：tests/shell_startup_navigation.test.cjs 的 12 个行为场景通过，Swift Helper 编译、JS 语法和 scoped diff check 通过。现有 Shell Python 套件 110 passed、4 failed：三处已有 Todo 清单断言未更新，一处 Discover 旧模板断言，不属于本次导航改动。
- Dev 实机：首次启动 Home；Todo 页面 Cmd+R 后仍为 /apps/ai2apps.todo；仅重启 Helper 后同一 Shell、同一 Local 端口返回 / Home，确认 epoch 检测与重定向 fragment 消费。托盘菜单 Computer Use 读取超时，菜单分支通过源码及行为测试验收，未宣称真实菜单点击；Runtime 安装恢复使用模拟会话测试，未实际安装模型。
- 追加安装链路复核：Runtime/ACPF 的 /client/restart-local → Helper local.restart 不写 Home epoch；Local 先启动 Package Manager 激活 Runtime，再 provisioning.startup 按新的 runtimeEpoch 恢复原持久会话。新增真实编排器跨 epoch 测试覆盖 Discover 与 Video Studio 从 awaiting_restart 到 provider/checkpoint/verify/ready，安装 I/O 使用替身；返回意图保持不变，同 epoch 不重复执行。
- 补齐旧 Discover registry_install_continuations 的 Shell 返回入口：仅 resume 重连且无可返回 ACPF 会话时读取 /packages/install-continuation 并打开 Discover，由 Discover 原有流程消费记录；Home/普通刷新不读取或删除续接记录。新增 awaiting_restart、旧续接和异步导航竞争回归。
- 追加验收：ACPF、Registry、Inference Runtime Python 三套共 111 passed；Shell 导航、Discover 升级与下载进度 JS 共 19 passed（初次 JS 从子目录运行导致相对路径错误，改从仓库根目录全部通过）。未下载/安装真实 Runtime 或模型；本次补充只改热挂载 Shell JS 与测试，无需重建 Dev/App-Dev，页面刷新后采用。

### NXR-MEMORY-INSTANCES-ACTIVATION-20261005：记忆系统开发实例启用

- 状态：`activated_and_verified`。按用户授权通过三个固定入口重建并启动 Dev、App-Dev、Test；旧 App 分别归档在 .build/archive，独立实例数据未重置/复制。Dev 使用仓库 .venv 开发入口，App-Dev/Test cloud Runtime 内嵌关键记忆/omlx 文件与当前源码逐字节一致；Test 非 Development、无 source-root；App-Dev Development/source-root 和禁用更新合同保持正确。
- 三包严格深度签名通过，App-Dev/Test 完整 verify-release-app.sh 通过。实际 Local：Dev 127.0.0.1:63452/PID 22343，App-Dev 127.0.0.1:63634/PID 22662，Test 127.0.0.1:63982/PID 40313，均 healthy；实际 OpenAPI 含 memory/compact，运行数据库中新 memory/checkpoint reader 均 enabled。
- App-Dev 原生标题由 Computer Use 确认为 AI2Apps-App-Dev: App-Dev 127.0.0.1:63634；Test Shell 已启动，当前为登录页。未代登录、未读取 Cookie、未复制认证状态。仅验收 General Agent 模块/API 已加载，不冒充真实模型长任务压缩验收；未发布生产。回执 docs/context-memory-instance-activation-2026-10-05.json。

### NXR-HARNESS-SESSION-MEMORY-20261005：跨 Run 对话记忆

- 状态：`implemented_and_tested`，真实模型/应用实机验收未完成。新增 SessionMemory 投影与 started/committed/ended 日志，原子来源 CAS、并发锁/终止 owner 恢复、跨 Run 复用、用户原文侧记录、同 Session 来源 reader、手动维护 Run 和完整旧 Run 工具证据。启用 reader 后取消 200/1000 条静默截断；原始记录保留。
- 独立图投影和旧 Run 大工具结果裁剪先隔离验收后接入；大结果持久投影为可回读 head/tail/hash，原文及工具配对保留，回读不重复裁剪，摘要中断可以重新开始。图投影：超限可明确省略最旧非 pinned 输入图，持久来源/part index/hash，当前输入与 assistant 图不省略。Session 摘要复用原 system/消息/tool schema 前缀；摘要 tool-call/截断/无缩减拒绝提交。最多 8 次尝试、同来源无进展停止；维护 Run 一次提交完成，无任务回答。
- 本地文本模型实际 tokenizer/template/schema 计量通过 Runtime 注入，记录实际路由/窗口/输出预留；未指定 max_tokens 时实际请求采用 min(2048, capacity/4, serving default)。远程/多模态/custom extractor 明确回退字节；摘要选区仍采用字节预算，不夸大统一 token-meter 完成度。仅已确认 provider context overflow 恢复一次，摘要超限及无进展明确失败，业务工具不重放。
- 验证：独立 35 项、宿主 78 个不同用例通过，Ruff scoped 与 compile/scoped diff check 通过。宿主覆盖完整 Agent 回归、checkpoint/adapter、来源 reader/control/reliability、Session memory 12、serving meter seam 2；seam 用 fake engine 抽取生产函数，不是实际模型测试。初版变量名/手动重复压缩缺陷已修复，旧问答/纠错测试调整等待窗口后通过，未削弱成功条件。Metal 沙箱 atexit 提示不作为 GPU 验证。
- 生效：未重启/构建/发布。omlx/server.py 属于 embedded Runtime，需使用固定 build-app-dev-environment.sh 重建 App-Dev 才采用；真实模型长任务、性能/缓存命中和实机故障验收仍待完成。详见 docs/ai2apps-context-engine-python-port.md。

### NXR-HARNESS-CONTEXT-PYTHON-PORT-20261005：独立上下文引擎 Python 移植

- 状态：`core_implemented_and_integrated`，整体移植仍在阶段性实施。新增 `ai2apps/context_engine` 独立标准库核心，固定参考 DeepSeek 5badb150，保留 MIT 来源/许可证。核心以不可变 Surface/Route、Meter、Summarizer、Store 为边界，提供压力/保留预算、精确路由策略选择、工具配对、选区/替换校验、异步事务取消与有界超限恢复；不导入 AI2Apps/MLX/数据库/模型 SDK。
- 先隔离验收：`scripts/test_context_engine_isolated.py` 复制核心和测试到新临时目录，创建无 system-site-packages 的 venv，以 `-I` 运行并断言未导入 AI2Apps。31 项通过，之后才通过独立宿主桥接接入现有检查点的选区和缩减验证；业务工具无对接修改。宿主计量仍为明确字节回退，审计 token_count_exact=false。
- 验证：独立 31 项、宿主相关 29 项通过（共 60 个不同用例）；宿主桥接原低压力 fixture 使用 5000 字节请求配 13000 字节数据而失败，修正为一致数据后通过，未放宽生产判定。Ruff 和 scoped diff check 通过。回执含测试数量/核心 SHA-256：`docs/context-engine-isolated-acceptance-2026-10-05.json`。详细合同/源码映射/重跑命令：`docs/ai2apps-context-engine-python-port.md`。
- 后续接入见 NXR-HARNESS-SESSION-MEMORY-20261005：本地文本 token Meter、跨 Run Session surface、手动维护、宿主已确认 overflow 恢复、图投影与 Session 摘要前缀复用已实现。仍待完整上游逐项差异/真实模型长任务与性能验收；未知/远程/多模态计量明确回退字节。未重启 App-Dev Local、未构建/发布生产客户端。

### NXR-HARNESS-CHECKPOINT-COVERAGE-20261005：检查点原文与状态覆盖

- 状态：`implemented`。`context-checkpoint/v2` 为被覆盖历史中的用户消息保留有序原文、来源组/消息坐标与哈希；来源清单随摘要请求持久化，宿主元数据记录清单 hash，回放和投影核对覆盖一致性。模型漏写约束不再导致对应原文随压缩消失。原文优先于冲突的派生摘要，后续更正及引用数据边界保留，不自动提取/删除约束。
- 确定状态：采用摘要后的普通模型请求从 Run/Step/Interaction 与当前计划重建状态块，包括计划版本、工具步骤 ID/状态/错误码、问答原文；审批响应内容不投影，工具完成不等于任务成功。状态随下一次模型请求持久化并记录独立 hash，不依赖摘要回忆。v1 检查点不直接采用，可在既有预算内重新生成 v2。
- 预算：启用 checkpoint reader 时不再通过旧轮次裁剪回退腾空间；原文、状态和摘要必须一起满足字节上限，超限明确失败。禁用 reader 保留既有模式。未引入全 Session 约束注册表、通用语义遗漏检测或 Artifact/最终验收独立验证；保护范围限于已加载上下文，既有消息条数/1000 条读取边界之前的内容不保证覆盖。
- 验证：27 个不同相关用例通过（检查点 11、可靠性 6、结果引用 7、控制工具 3）；合跑 26 passed，追加 v1→v2 迁移测试后检查点 11 passed。含摘要故意省略约束仍保留原文、来源清单 hash 不匹配拒绝、计划更新无需重新摘要、问答原文、审批内容排除、字节预算拒绝删历史，以及此前中断恢复/工具不重放。Ruff 与 scoped diff check 通过；沙箱退出有 No Metal atexit 提示，不涉及 GPU 结论。
- 来源：核对 DeepSeek 固定 5badb150 的 summarizer.ts 与 region.ts，确认其提示模板和区间/来源提交保护；本轮确定性原文侧记录及状态投影是本地设计，不宣称上游已具备完整语义覆盖校验。
- 未重启 App-Dev Local、未发布；生效需按固定 App-Dev 工作流重启 Local。真实模型长任务效果、实际 token 窗口计量和端到端界面验收仍待完成。

### NXR-HARNESS-CONTEXT-CHECKPOINT-20261004：长任务上下文检查点

- 状态：`implemented`。新增 `context-checkpoint/v1`：字节压力达 75% 后，分批摘要较早文本历史与完整工具轮次；保留 system、当前输入与最近两组原文。摘要走独立持久模型步骤，来源/锚点哈希一致且响应完整、结构/大小/实际缩减校验通过才投影；原消息和步骤不删除，摘要不成为系统指令或权限来源，摘要步骤不参与普通模型决策/最终回答。
- 新增 `agent.read_context_checkpoint`，当前 Run/Session 内分页读取摘要调用的精确来源 JSON，通过 previous_checkpoint_step_id 回查更早来源；大结果原文继续走既有 reader，回读页不递归裁剪。模型侧过滤 reader 时停用检查点投影；Host 元数据不传给 provider。
- 上限：每 Run 最多 8 次检查点尝试；摘要请求不超过字节预算 85%，输出请求最多 2048 token，接受文本最多 8192 UTF-8 字节，节省须超过 512 字节。摘要同样消耗 Run 步数、时间和 token 预算。无效摘要不在没有新执行进展时立即循环重试；provider 异常仍按现有可重试 Run 失败处理。
- 验证：相关 75 个不同用例通过（Agent/Services/stream 52、此前可靠性/结果引用/控制工具 16、新增检查点 7）；覆盖摘要中断重启、已完成工具不重放、恢复后继续最终任务、来源与当前指令变更拒绝、格式/截断/空摘要拒绝、完整工具配对、多轮增量来源、无 reader/多模态回退、来源回读隔离。初版新增集成测试的 echo fixture 输出多余字段被真实 gateway 拒绝，修正 fixture 后通过；未放宽生产 schema。Ruff 与 scoped diff check 通过；沙箱退出有 No Metal atexit 提示，未作 GPU 性能结论。
- 限制与生效：仍按字节计压，未接准确的路由模型 token 窗口；多模态摘要和真实模型长任务效果/成本验收未完成，结构校验不能证明语义无遗漏。既有消息条数/字节裁剪及预算仍可能停止任务。未重启 App-Dev Local、未构建或发布；Python 生效需按 App-Dev 工作流重启 Local。

### NXR-HARNESS-CONTROL-SEARCH-20261004：提问、Run 计划与搜索增强

- 状态：`implemented`。新增 `agent.ask_user`，沿用持久 Interaction 等待/恢复，支持建议选项及自由回答，恢复后返回配对工具结果，回答不授予权限；新增 `agent.read_plan`/`agent.update_plan`，当前 Run/Session 隔离、版本冲突保护、幂等更新、稳定条目 ID、最多一个进行中项，以事件持久化并在父/子 Run 卡片显示；计划完成不更改 Run 或 Todo 完成状态。
- 搜索：新增 `workspace.glob`，增强 `workspace.search` 的逐行正则、文件模式、大小写、上下文行和隐藏文件选项；限制单文件/总字节、条目、文件数、深度、时间及正则执行时间，返回不完整原因。扫描不跟随符号链接，保留 Session 工作区边界，无数据库迁移或新依赖。
- 验证：Agent、Services、Workspace、流式响应、可靠性、大结果及本轮测试共 89 个不同用例通过。合跑 88 passed + 1 旧工具清单断言失败；加入新增 glob 后针对清单及控制工具复测 4 passed。覆盖提问重启恢复、任意文本回答、伪造回答拒绝、计划版本冲突/幂等/跨 Session 拒绝，以及 glob/正则超时/隐藏文件/上下文/扫描上限/符号链接隔离。本轮新增/主要修改文件 Ruff、scoped diff check、Chat Jinja 与中英文 JSON 解析通过；扩展 Ruff 仍报告 workspace/repository.py 和既有 workspace 测试中未涉及的导入排序/分号问题，未扩大范围整理。退出时存在沙箱 No Metal atexit 提示，本轮不涉及 GPU 验证。
- 生效与发布：尚未重启固定 App-Dev Local；Python 改动需 Local 重启，模板需刷新，无需重建 App。真实模型与界面交互实机验收待完成，未发布 Desktop。

### NXR-HARNESS-RESULT-REFERENCES-20261004：大结果按需回读与循环保护

- 状态：`implemented`。继续对照 DeepSeek 的 spill 与 tool-result pruning，使用现有 RunStep 原文为超过 32 KiB 的 JSON 工具结果提供 2048/1024 字符首尾预览、遗漏统计、SHA-256 和实际回读工具别名；新增 `agent.read_tool_result`，只允许当前 Run/Session 的已完成工具结果分页读取，每页最多 8192 Unicode 字符。仅当回读工具可用时缩减上下文，原始存储与工具配对不变，读取页不递归缩减。新增二至四步工具周期检测，输入和结果相同重复三轮后停止下一轮，参数/结果变化不触发。
- 验证：Agent、Services、流式响应、第一轮可靠性与本轮测试共 65 个不同用例通过。合跑 64 passed + 1 循环测试等待超时（运行到第 10 个持久步骤）；调整测试等待预算以覆盖真实调度节奏后，本轮 7 项全部通过（18.54 秒），确认只分派六次工具、七次模型后 `repeated_tool_cycle`。Ruff 与 scoped diff check 通过。退出时仅有沙箱 No Metal atexit 提示，无 GPU 效果结论。100030 字节合成原文预览为 3605 字节（减少 96.4%），16000 字节请求预算内可回读中部文字。未重启 App-Dev Local、未发布；真实模型长任务与性能验收仍待完成。

### NXR-ALL-INSTANCES-RECORDING-20261004：全部实例准备录屏

- 状态：`implemented_and_verified`。取代 App-Dev/Test 白名单，所有 Helper 实例（含 Release/default）显示“准备录屏”。目标保持 1600×900 和屏幕左上角，不启动录制。
- Helper 使用标准 InstanceID 校验；Shell 仅消费自己 run 目录下且 instance_id 与自身一致的命令，保留跨实例隔离。
- 通用 apply-screen-recording-shell.py 由 Dev 和 Release 公共构建入口统一应用到打包 Shell；App-Dev/Test 继承公共入口，不再单独注入。Release 不启用开发源码 overlay/热挂载。
- 验证：App-Dev、Test、Dev、default、自定义实例共 10 个命令接受/跨实例拒绝行为场景通过，JS/zsh 语法和 diff check 通过。固定三个构建脚本均成功，三个包统一处理器唯一性及深层签名通过，App-Dev/Test 完整 verify-release-app.sh 通过；App-Dev 固定窗口标题/身份合同正常。
- 本机 App-Dev、Test、Dev 均已更新并恢复运行，数据保留。Dev 通过同菜单命令实机验证：命令已消费，窗口截图 3200×1800 Retina 像素（1600×900 逻辑尺寸），端口 63799。未以命令测试冒充托盘菜单点击验收。
- 生产用户在正式 Desktop Release 发布后获得此功能，本次未构建或发布正式 Release 制品。

### NXR-TEST-RECORDING-20261004：Test 准备录屏入口

- 状态：`implemented_and_verified`。Test Helper 增加与 App-Dev 相同的“准备录屏”菜单，窗口为 1600×900 并移至可用屏幕左上角；不直接开始录制。
- 入口绑定非 Development 的 com.ai2apps.desktop.test/test。Test 构建仅对已打包 Shell 应用实例专属录屏转换，不启用源码热挂载或 Development overlay；命令只接受当前 test 实例，App-Dev 保持原规则，生产及普通 Dev 不增加入口。
- 文件：Helper main.swift、apply-app-dev-shell-overrides.py、build-release-app.sh。
- 验证：App-Dev/Test 打包 Shell 转换、Node 行为检查（尺寸、一次性消费、跨实例/生产拒绝）、JS/zsh 语法与 diff check 通过。固定 build-test-app.sh 构建完成，verify-release-app.sh、codesign --verify --deep --strict 通过；test bundle ID、instance ID、cloud Runtime、无 Development 标记均核对。
- 实机 Test `127.0.0.1:58896` 经重启旧 Shell 后，通过与菜单相同的命令验证：test 命令已消费，Computer Use 窗口截图为 3200×1800 Retina 像素，对应 1600×900 逻辑尺寸。Helper 无窗口辅助功能读取超时，因此未冒充实际点击菜单验收；未触发录制，实例数据保留。

### NXR-HARNESS-RELIABILITY-20261004：长会话与执行恢复

- 状态：`implemented`。基于 DeepSeek Harness 源码对照完善本地 General Agent：按当前输入截止位置读取最近历史、按幂等键定位生成输入、固定委派父输入锚点；硬中断模型步骤保存 cancelled 尝试并释放 action key；默认 512 KiB 请求字节预算仅裁剪完整旧轮次，保护 system、当前输入与本 Run 工具链，超限明确失败；记录请求 hash/字节数/策略版本/Step ID；只读工具 schema 拒绝允许最多三次模型纠正，保持 FAILED 步骤和工具结果配对。沿用宿主身份、权限、SQLite 与副作用不确定处理。尚未实现精确 token 窗口、摘要压缩或工具并发。
- 验证：Agent/流式响应与初版新增用例 43 passed；最终新增用例/存储/Services 43 passed（共 81 个不同用例）。覆盖 1000 条边界、后续输入隔离、生成输入幂等、委派锚点、硬中断恢复、审计 hash、字节裁剪与纠错上限；Ruff、scoped diff check 通过。扩展存储套件首次因沙箱 MLX/Metal 不可用中止，在本机 Metal 可用环境重跑全部通过。待固定 App-Dev Local 重启及真实长任务实机验收，未发布 Desktop。

### NXR-AGENT-REVIEW-PROGRESS-20261003：流程调整等待与结果提示

- Status: implemented. AI 调整流程时增加覆盖整个 Mini-Entry 侧栏内容的固定等待层、等待圆圈和说明，底层内容 inert 防止重复操作；成功显示新版本和步骤数量变化，失败保留修改意见并展示接口与编译错误详情。结果持续显示到用户关闭，支持中英文及减少动态效果偏好。
- Validation: JavaScript 语法检查与参数/导航确认回归通过。模板与静态资源更新，无需 Local 重启或 App 重建。原失败请求模型 HTTP 200 但未产生新版，历史日志未留具体校验错误，不推断原因；真实重试已生成有效 v2（5→3 步）。本项未发布 Desktop。


### NXR-AGENT-REVIEW-TEST-POSITION-20261003：试运行按钮归入 Review

- Status: implemented. 将“先试运行”从编译 Review 上方移入 Review 卡片内，位于步骤和 Source/IR 查看区域之后、修改意见与审核操作之前。保留现有按钮 ID、可见性逻辑、运行版本和参数提交行为。
- Validation: HTML 结构检查通过，按钮 ID 唯一、属于 Review、顺序在步骤之后和修改意见之前。仅模板位置调整；当前 Sidebar 刷新后生效，无需 Local 重启或 App 重建。未执行浏览器任务或发布 Desktop。


### NXR-AGENT-PARAMETER-VISIBILITY-20261003：探索参数提取遗漏和审核入口

- 状态：`implemented`。参数提取对齐执行器的自然语言引号输入回退；审核页将参数区放在步骤前，空时明确提示并提供从现有步骤提取参数按钮。提取通过 actor 隔离与 revision 校验，重新编译并使旧审核失效，保留已有输入定义和可选状态。待审核 Recipe URL 保存精确 recipe_id，刷新时恢复该记录，不自动挑选其他 Recipe。
- 中文引号输入编译与提取幂等回归已补齐；Python 参数/平台 23 passed，Node 相关 31 passed，Ruff、JS 语法和 scoped diff 通过。固定 App-Dev Local 已重启，原四步“打开Google，搜索OpenAI” Recipe 经认证提取接口返回 200，生成 query 默认 OpenAI、版本 v2，有效审核页实机显示“参数”“本次运行参数”及 QUERY 输入框。未通过 Review、保存为 Agent 或发布。搜索按键授权也支持已恢复 Recipe 的任务描述。


### NXR-AGENT-NAVIGATION-BOUNDARY-20261003：探索导航范围和输入目标修复

- 状态：`implemented`。URL 范围检查改为解析协议、hostname、端口、路径 glob，修复 Google 根地址省略末尾 / 时被 origin/** 拒绝；探索保留已请求或已确认的导航 origin，不随当前页面反复覆盖授权范围。输入步骤解析仅选择可输入控件，避免同名搜索链接/按钮被当成输入目标。搜索输入支持替换原文本及原生 BiDi Enter 提交；单独提交不要求再次提供文本且保留现有查询，搜索回车描述即使被模型标为 click 也执行真实按键。仍检查未授权导航、域名、协议、端口和敏感交互。
- 文件：`ai2apps/web/static/js/agent_mini.js`、`ai2apps/web/static/js/browser_bidi_client.js`。Node 参数/导航/确认/范围/重连/输入键盘 31 passed，JS 语法与 scoped diff 通过。静态源码修改，只刷新 Sidebar，无需重建或 Local 重启；固定 App-Dev 实测从 Google Images 返回普通 Google 搜索，导航成功，提取 19 条结果并进入有效 Review，无范围限制。追加键盘恢复有定向回归，未声称模型文字即真实提交成功。未保存或发布 Agent。


### NXR-AGENT-PARAMETERS-20261003：制作与运行 Agent 的输入参数

- 状态：`implemented`。制作界面新增参数名称、显示名称、类型、默认值、必填及步骤绑定；能力间隔离 Schema，修改参数名同步绑定，已引用参数禁止直接删除。步骤预览/试运行及 Recipe 试运行填写并传递 input，数字/布尔类型保真，缺失参数阻止执行。探索沉淀将成功 input.arguments.value 和已识别搜索引擎 URL 的 q/wd 查询提取为参数，搜索使用 query，保留原值为默认值，目标和站点范围保持固定；参数 Schema 随 Source/IR 和能力提交持久化。补齐中英文。
- Python 参数与平台回归 21 passed，Node 参数/导航/范围/重连 25 passed，Ruff、JS 语法与 scoped diff 通过。直接搜索 URL 参数化编译有效，URL 插值对查询值编码而保持站点范围。通过固定 app-dev Helper 重启 Local 加载最终实现；实机确认参数编辑、默认值回填、本次运行输入和步骤绑定控件可见，未保存验收草稿或发布 Agent。未发布 Desktop/Package/Cloud。


### NXR-AGENT-SEARCH-CONFIRMATION-20261003：普通搜索输入与提交免重复确认

- 状态：`implemented`。此前前端逐动作确认和服务端 submit 关键词误将 Google 搜索输入当成提交操作。用户任务明确要求搜索时，在 Google/Bing/百度的准确域名上，搜索框输入与搜索按钮点击直接执行；账号、验证码、支付、发布等目标不适用此例外，执行阶段仍检查目标与敏感输入策略。
- 文件：`ai2apps/web/static/js/agent_mini.js`、`ai2apps/tests/agent_navigation_confirmation.test.cjs`。导航/搜索确认/范围/重连 Node 21 passed，JS 语法通过。纯静态源码修改，刷新 Sidebar 生效，无需重启 Local 或重建 App。实机侧栏刷新未完成：验证时用户切换到 Imagine Studio，未继续干扰其工作。


### NXR-AGENT-PRESENTATION-RECOVERY-20261003：AI 展示校验恢复与诊断

- 状态：`implemented`。统一 Run/Recipe 的展示生成路径，模型展示 JSON 无效时携带具体校验错误修复一次，修复预算 3000 tokens；校验仍严格拒绝不存在路径或可执行内容。保存不含输入值的结构化校验原因、请求 ID、模型 ID、finish_reason，前端保留并显示错误详情。实机复现原 19 条搜索结果：DeepSeek V4 Flash 返回不以 $ 开头的 data_path，finish_reason=stop；一次自动修正后返回 $.items，展示描述通过校验并返回 200。根因是此前 JSON Schema 没有表达 Python validator 的路径约束；补齐 data_path/field.path pattern 与说明，使模型请求契约与运行校验一致。最终 Schema 回归 22 passed，导航/范围/重连 Node 19 passed，Ruff 和 scoped diff check 通过。通过固定 app-dev Helper 重启 Local 后，原 19 条结果再次实测返回 200，生成 table 展示与合法 $.items 路径；当前 Local 已加载修复。


### NXR-AGENT-MENTIONED-SITE-20261003：用户明确提到的网站免重复确认

- 状态：`implemented`，固定 App-Dev 已实机验收。探索模式 open 的目标与任务明确给出的网址/域名或已识别网站名称一致时直接导航；未提及网站和其他交互仍保留确认。明确授权的 open 只执行原生导航，不因服务端文本关键词误判重复询问。网址匹配精确 hostname（允许 www），不接受 lookalike 域名；Google/谷歌、Bing/必应、百度、Wikipedia/维基百科等名称解析到固定网站。
- 文件：`ai2apps/web/static/js/agent_mini.js`；Node 定向 7 passed，JS 语法通过；实机 Open Google 从新标签页直接打开 Google，未出现确认弹窗，1 步成功并进入 Review；导航/范围/重连 Node 合计 19 passed。Python Agent Mini 因同期其他改动的 SYSTEM_APP_MANIFESTS 缺少 ai2apps.todo 本地化映射而未能收集，未计作通过。前端刷新 Sidebar 生效，无需重建或重启 Local。


### NXR-AGENT-NEWTAB-SCOPE-20261003：新标签页探索导航范围修复

- 状态：`implemented`，App-Dev 已实机验收，待下一版 Desktop 纳入。Agent Mini 的 pageScope 仅对 HTTP(S) 页面生成 origin 范围，修复 about:newtab/about:blank 产生 null/** 导致首步导航误判 site_scope。open 检查目标 URL 范围而非起始页，预览也检查目标；页面交互仍要求当前页面处于授权范围。
- 文件：`ai2apps/web/static/js/agent_mini.js`，Node 定向 7 passed，Python Agent Mini 16 passed、JS 语法与 scoped diff check 通过。固定 App-Dev 实测 Search Google for OpenAI IPO date：从 about:newtab 导航成功，inspect 与 extract_list 成功，提取 11 条结果，3 步沉淀并编译有效、等待 Review；未保存/发布 Agent。探索模式既有逐动作确认仍保留，本次实测确认了一次 open。纯前端修改，刷新 Sidebar 即可，无需重建或重启 Local。


### NXR-TODO-MVP-20261003：内置 Todo 项目树与执行调度

- 2026-10-09：桌面 Todo 行内进度滑块旁新增实时百分比，打开即显示当前滑块值，input 时同步更新并提供 aria-valuetext；保留 5% 步进和松手保存关闭行为。验证：JS 语法和 diff 检查通过。纯前端刷新生效。

- 2026-10-09：桌面 Todo 行内优先级/状态/进度浮层改为以触发控件水平居中，按项目列表左右边界限制位置和宽度，避免覆盖右侧详情；底部不足时向上弹出。验证：JS 语法和 diff 检查通过；未做实机截图复验。刷新页面生效。

- 2026-10-09：修复桌面 Todo 优先级由 span 改为 button 后被通用按钮 padding/font/border 覆盖造成的徽标变形与文字下沉；提高行徽标选择器优先级，固定 22×22、border-box、零 padding、line-height 1 和 flex 居中，保留等级配色及快捷菜单，不增加行高。验证：样式层叠检查和 diff 检查通过；未做实机截图复验。刷新页面即可。

- 2026-10-09：补齐 Todo 移动端中英双语，模板与动态 UI 跟随 current_lang/html lang；覆盖创建/搜索/编辑/快捷菜单/高亮/状态/进度/Toast/确认提示及执行状态，英语操作按钮允许换行避免窄屏溢出。桌面修正请求失败固定中文及 Activity 字段标签。沿用既有简体中文/英语策略（其它非中文语言回退英语），不翻译用户内容与服务端原始错误。验证：3 项中英模板渲染测试（英文无残留中文）+14 项移动 API 测试、9 项 Node 回归、JS 语法和 diff 检查通过；未做真机语言切换验收。前端/模板刷新生效，无需重建。

- 2026-10-09：Todo 新增 30 天 Activity：SQLite 触发器与项目创建/修改/删除同事务记录，覆盖 Store、移动端、Chat/Codex 和周期调度写入；忽略只有时间戳变化的保存，记录字段前后值、当时路径、启用时间，写入/查询清理过期历史并按 owner 隔离。导入任务改用 UPSERT，保留更新前记录。新增分页 /activity 查询，支持目录/项目子树、1–30 个日历日与 IANA 时区；目录移动也可从原目录查到。Chat list_activity 默认当前目录，明确项目问法才限子树，提示不能从 updated_at/执行记录推断历史；详情增加最近活动及分页。验证：初轮 98 项 Todo/移动/迁移/Activity 后端测试通过，增补后 3 项 Activity（含 API 隔离/时区）通过，7 项前端 action/autosave 回归、JS 语法、diff 检查通过。未做真实模型/桌面端到端复验。需重启 App-Dev Local 并刷新 Todo 生效；不回填过去历史。

- 2026-10-09：桌面 Todo 项目行的优先级、状态、百分比增加可聚焦快捷编辑按钮；锚定浮层选择后自动保存，进度滑块按 5% 松手提交。复用字段保存队列和 revision，归档/回收站禁用，未保存详情草稿时提示先保存；浮层支持 Escape/外点/滚动关闭，保留原行高及拖拽边界。验证：7 项 action/autosave 回归、JS 语法、diff 检查通过；未做桌面交互实测。纯前端，刷新页面生效。

- 2026-10-09：移动 Todo 项目行支持点击优先级/状态弹出选项、点击百分比弹出 5% 步进滑块；选择或滑块 change 后直接保存并关闭，沿用 revision 冲突检查并同步状态/进度，不修改排列或高亮。标题独立进入详情，避免嵌套按钮。验证：14 项移动 API 测试、2 项树结构测试、JS 语法和 diff 检查通过；未做真机交互复验。刷新移动页面即可。

- 2026-10-08：移动 Todo 的新建目录、新建项目、搜索项目改为同一行按钮；搜索按钮打开原生 dialog，提交后按标题/内容筛选，取消不改变当前筛选，展示当前关键词并提供清除入口。验证：JS 语法、2 项树形/搜索路径测试及 diff 检查通过；未做真机视觉复验。刷新移动页面生效，无需重启或重建。

- 2026-10-08：移动 Todo 列表优先级移至任务标题前，以 `[U]` / `[S]` / `[A]` / `[B]` / `[C]` / `[D]` 显示；副标题保留状态和进度，避免重复。验证：JavaScript 语法和 diff 检查通过。纯前端变更，刷新移动页面即可。

- 2026-10-08：移动 Todo 的刷新/保存等 notice 改为底部固定 Toast，不占文档流、不阻挡点击；3 秒自动清除，新提示重置计时。保留 aria-live 状态播报并适配底部安全区。验证：JavaScript 语法及 diff 检查通过；未做真机复验。纯前端变更，刷新页面即可。

- 2026-10-08：修正移动 Todo 高亮底色侵入树形缩进区域：底色从整行容器移到任务卡片，沿用普通卡片的边框、宽度与位置，展开按钮和树连接线区域不再着色。验证：diff 空白检查通过；未做真机复验。纯 CSS 变更，刷新移动页面即可，无需重启或重建。

- 2026-10-07：移动 Todo 补齐 highlight 读取、创建和更新；列表使用与桌面一致的六种浅色整行底色，详情提供无文字色块及清除入口（保留无障碍名称），已有任务选择后立即保存颜色且不提交其它表单草稿。旧移动客户端遗漏字段时保留已有颜色，沿用 owner/revision 校验与稳定顺序。验证：14 项移动 API 测试、2 项树结构 Node 测试、JS 语法及 diff 检查通过；未做真机视觉验证。需重启 App-Dev Local 并刷新移动页面，无需重建 App。

- 2026-10-07：增强 Todo Emoji 生成提示词；AI 回答按 Unicode grapheme 提取首个未被排除的完整 Emoji，兼容说明文字、多候选、肤色/组合表情、旗帜和键帽，保留手动输入严格校验与最近历史去重。无可用新 Emoji 时在原 90 秒预算内最多请求三次。验证：`ai2apps/tests/test_todo.py -k emoji` 23 项通过；未执行真实模型端到端验证。Python API 变更需重启 App-Dev Local 后生效，无需重建 App。

- 2026-10-07：移动 Todo 列表显示加粗进度百分比（未开始且 0% 隐藏），编辑页增加 0–100 整数输入与聚焦展开的 5% 滑块，松手失焦隐藏；状态/完成操作联动进度，仍按保存提交。移动 API 开放受校验 progress 字段，旧客户端未传进度时保留原值，沿用 revision/owner 边界。验证：移动 Todo API 13 项（含进度、完成、重开、范围与旧客户端）、树形 Node 2 项、JS 语法通过。需 Local 重启并刷新手机页面，未进行真机触控验收。

- 2026-10-07：移动 Todo 列表由平铺改为父子树，按同级 position 排序，增加逐级缩进、连接线、独立展开/收起按钮与 aria-level；搜索保留并展开祖先路径，未完成子项的已完成父项灰色显示，深层允许水平滚动。移动只读字段补充 position，编辑权限不扩大。验证：Node 树顺序/多级/收起/搜索路径 2 项、移动 Todo API 9 项、JS 语法通过。需要 Local 重启读取 API 字段并刷新手机页面；未做真实手机视觉验收。

- 2026-10-07：Run 页执行器选择接入已有字段自动保存队列，切换即保存 executor，沿用 revision 串行校验和错误提示，保留其他未保存草稿。验证：Node 自动保存 5 项及 JS 语法通过。纯前端刷新生效。

- 2026-10-07：修复 Todo Emoji 备用模型调用使用虚构 ai2apps.internal origin 的问题，沿用已认证请求 base_url 并转发 Origin/sec-fetch-site，保留同源校验；上游错误保留 HTTP 状态与有限 message，前端解析统一 error.message 而非显示整段 JSON。证据：dev server.log 中同次内部调用连续 403，外层被转换为通用 502。验证：Emoji 15 项测试通过（含当前 Local origin 转发/上游错误回归），JS 语法通过。需重启 Local 刷新；未重放真实付费模型请求。

- 2026-10-07：Todo 创建对话框标题/内容加入 ASR 语音输入，复用 StudioAudioRecorder 和 /v1/audio/transcriptions；点击先 ensure audio.speech_recognition，缺模型走 Todo 专属 ACPF 配置（Qwen3 ASR 0.6B），已配置直接录音，停止后追加可编辑文本，不自动创建。关闭取消录音与转写并隔离迟到结果，转写中阻止提交，保留手动输入，120 秒录音上限。ACPF 浮层挂到已打开 dialog，避免被顶层模态遮挡。验证：Node 语音输入/缺模型保护 2 项与 JS 语法通过；真实麦克风与安装验收待进行。新增 provisioning profile 需重启 Local 读取并刷新页面。

- 2026-10-06：修复编辑 Todo 项目导致同级显示顺序漂移：save 改为 ON CONFLICT 原位更新，保留 SQLite rowid，兼容旧数据相同 position 的稳定次序；同目录/父节点普通保存强制保留既有 position，排序仅由 reorder 修改；新建或迁入同级末尾。验证：旧重复排序值编辑、拖拽后编辑 2 项新增测试及 Todo/导入导出回归合计 75 项通过。Python 变更需重启 Local 生效，不重排现有数据。

- 2026-10-06：修复确认完成/仍需继续及打开 Codex 按钮事件注册在 Todo IIFE 外部导致 safe 未定义、处理器未绑定的问题；将两个处理器纳回模块作用域。新增保留真实初始化尾部与闭包边界的点击测试，验证 review 携带 revision、Desktop open 发往系统接口。验证：Node 点击 2 项及当前执行 7 项通过，JS 语法通过。仅前端刷新生效，无需新增后端重启。

- 2026-10-06：Todo 左/右栏默认宽度由 280/360px 加宽至 340/420px；增加独立拖动分隔线，指针捕获支持跨 iframe 拖动，松手保存 localStorage，双击/Home 恢复单侧默认，方向键调整。窗口不足时按比例收缩并保留中栏 320px，不覆盖偏好；收起栏和移动窄屏隐藏拖柄。验证：Node 布局交互/持久化/重载/重置/宽度约束 2 项、JS 语法通过。仅前端刷新生效；宽度偏好按当前浏览器 origin 保存，未作跨 Local 端口迁移。

- 2026-10-06：补齐执行结果人工确认：最新 ended 执行支持确认完成/仍需继续，同一事务记录 review 决策、操作者与时间并更新项目；确认完成设 100%，继续设进行中且原 100% 重置 0%，不重跑。校验 owner、revision、最新执行与归档状态，重复同决策幂等。确认后移除行内待确认，当前执行及历史展示审核结果；保留 AI 原始报告。验证：新增存储测试 4 项、已有 Todo Python 63 项、当前执行 Node 7 项通过；JS 语法通过。需要重启 App-Dev Local 并刷新页面，原生验收尚未进行。

- 2026-10-06：修复共享 Mini-App Chat 频道初始化缺陷：新频道同时写入 iframe 查询参数，避免恢复旧 iframe 后仅 hash 导航保留旧 JS 频道而导致 host timed out；宿主按绑定 iframe 的当前 contentWindow 校验消息和发送更新，拒绝旧窗口。验证：Node Mini-Chat 8 项、Python Mini-App Chat/Chat Mini 9 项及 JS 语法检查通过。前端刷新生效；尚未在用户原生窗口复现确认。

- 2026-10-06：修复 Todo Mini-Chat 无法取消行高亮：项目摘要和创建/更新工具暴露 highlight 枚举，空字符串清除；明确区分持久高亮与焦点。查询/读取/更新支持显式 scope=directory，用于用户明确指定当前目录的请求，默认保持选中项目子树范围，聚合视图禁止隐式扩展目录；保存不写入 scope，保留其他字段及 revision 校验。验证：Mini-Chat Node 测试 6 项通过，todo.js 语法检查通过。仅前端变更，刷新 Shell 页面生效；未进行真实模型对话验收。

- 2026-10-05：新增 Todo → Codex Desktop App Server 接入（原生 Local 重启后验收待完成）。执行页可选本机项目目录和已有会话，或选择执行时新建；服务端校验目录归属/版本并保存绑定，设置 codex_desktop 执行器。使用统一三名额队列；新会话 ID 自动回填、已有会话 resume，流式输出/步骤与单次授权/结构化问答显示在当前执行区，等待保留名额，结束标记 ended 待确认，取消 interrupt 后 unsubscribe；未知交互显式失败。仅已连接 Todo 的用户且有 Coder 权限可用，不读取 Desktop 私有数据库或借用内部工具凭据。目录列表来自会话 cwd，不冒充 Desktop 项目 ID；同一会话不要在 Desktop 与 Todo 同时执行。验证：Python 83 项、Node 27 项回归；本机真实 App Server 读取 22 个 AI2Apps 会话并匹配当前会话；ephemeral/read-only/no-tools 临时 turn 完成且精确返回 TODO_CODEX_OK。已在原生 App-Dev 查看新弹窗，运行实例仍未重启导致新路由 Not Found；已请用户通过 Helper 重启，未修改原任务或发送到其已有会话。

- 2026-10-05：Todo 普通项目行选中时增加与高亮行一致的 2px 内描边，统一选中标识，保持行高及布局不变。验证：git diff --check 通过。

- 2026-10-05：将 Todo 行高亮入口合并到现有六点拖拽指示，移除独立下拉控件；点击展开纯色块浮层（含斜线清除项，无可见文字），保留拖拽排序，拖拽后抑制误点击；支持键盘打开、方向键选择、Escape 关闭，以及点击外部/滚动关闭。颜色选项保留无障碍名称。验证：Node 回归 27 项通过，JS 语法检查通过。

- 2026-10-05：Todo 任务行左侧新增高亮颜色下拉，默认无高亮，支持荧光绿、浅黄、浅橙、浅粉、浅蓝、浅紫；选择即保存整行底色，保持行高，选中高亮行增加轮廓，深色模式使用对应低亮度底色。新增受枚举约束的 highlight 字段及旧数据默认值，随备份导入导出；与现有字段保存队列共用，保留详情未保存编辑，颜色选择不触发行选择或拖拽。验证：高亮持久化/清除/校验 7 项、备份测试 10 项（含高亮及旧备份兼容）、Node 回归 27 项通过，JS 语法与 diff 检查通过。含 Python 模型变更，运行实例需重启 Local 后刷新；尚未进行原生窗口视觉验收。

- 2026-10-05：Todo 项目行标题由继承的 13px 增至 14px，标题行高固定 20px，保持项目行原有 48px 最小高度与间距，长标题仍单行省略。验证：git diff --check 通过。

- 2026-10-05：Todo 项目行进度百分比字重提升至 700，状态文字保持原样，聚合父级路径仍保留灰色。验证：git diff --check 通过。

- 2026-10-05：提高 Todo 项目行状态与进度的可读性，使用正文颜色及 500 字重，保留聚合筛选父级路径的灰色展示；未开始且进度为 0 的项目仅显示状态、不显示 0%，其他状态仍显示进度。验证：JS 语法检查与 git diff --check 通过。

- 2026-10-05：Todo 新建项目/子任务弹窗增加 U/S/A/B/C/D 优先级（默认 C）与多行任务说明，随标题一次提交创建；新建目录仍仅输入名称，重开弹窗重置字段，弹窗适配小屏滚动。验证：JS 语法检查、创建字段及取消/目录隔离回归测试 2 项、git diff --check 通过。

- 2026-10-05：增加 Todo 项目列表底部滚动留白：非空项目树底部内边距从 8px 增至 80px，普通目录与聚合目录共用，避免末行紧贴面板底边；空列表布局保持原样。验证：git diff --check 通过。

- 2026-10-05：修复 Todo 导入/合并对话框底部按钮未应用统一样式：弹窗位于 .todo-app 外，新增共享 .todo-dialog 按钮作用域，覆盖导入、新建和 Codex 连接弹窗；确认合并使用黑色主按钮，取消使用中性次操作，并统一 hover、键盘焦点和禁用状态。验证：git diff --check、Todo 导出相关 Node 测试 3 项通过；未执行实际导入，原生窗口视觉验收待刷新后确认。

- 2026-10-04 Todo 导出无响应修复：移除 fetch→Blob 的 iframe 下载流程，顶部导出改为真实 HTTP download anchor，单目录导出同步触发同源 HTTP 链接，沿用账号权限及原生 Shell Save As；增加下载已请求反馈。App-Dev 64738 实机验证两种入口均弹出另存为并成功写入临时 ZIP，CRC/manifest 检查通过：全部 4 目录/28 项，单目录 1 目录/3 项。Node 25 passed（新增 3 项下载契约/目录范围/取消回归），JS 语法通过；前端刷新已生效，无 Local 重启。普通浏览器人工验收留待发布前完成。

- 2026-10-04 Todo 顶部工具栏 Hover-Tip：Codex 链接按钮明确命名“Codex 连接”；连接、导入/导出、刷新、左右栏切换及目录/Gallery 图标按钮统一复用 Dock 深色圆角悬浮提示的配色、阴影、字号、70ms 延迟和 80ms 动画，移除重复的原生 title；支持键盘聚焦，移出/点击/Esc/滚动/缩放隐藏，保留 Emoji 的多行说明。JS 语法与 Node 22 项回归通过；前端刷新生效，无需重启 Local。

- 2026-10-04 Todo × Codex Desktop MVP：增加本机 owner-scoped 可撤销连接、专用 stdio MCP 插件/Skill/本地安装器；任务存储 Codex 项目/主对话关联与最近 30 条进展，项目沿父链继承、对话不继承，详情显示关联与最近 5 条进展，导出导入保留关联但不包含连接凭据。工具限制为查询/读取/创建/绑定/更新，不启动 Desktop 对话、不参与运行队列；附件仅元数据。Python 69 项回归通过，新增配对 API 后专项 5 passed（合计 70 项覆盖），Node 22 passed、JS 语法通过。App-Dev 已加载；插件 ai2apps-todo@ai2apps-local 0.1.0 已通过 Codex CLI 安装并启用；经用户同意完成本机配对，真实已安装 MCP 读取 4 目录/27 原任务，并在 Todo MVP 体验创建演示任务，绑定当前项目路径/当前对话并回填完成记录，实机详情已核对。原任务未修改。新 Codex 对话载入插件；不承诺现有对话热载入或外部 Desktop 会话控制。

- 2026-10-04 Todo 等级筛选：项目列表下拉菜单增加 U/S/A/B/C/D 级项目；按等级和搜索组合匹配当前普通目录的活动项目（包括已完成项目），仅保留匹配节点及完整父级路径，非匹配父级灰色标注“父级路径”。筛选自动展开路径，行展开图标/ARIA 与实际显示一致；排除其他目录及归档/回收站数据，缺省优先级按 C。新增 5 项树筛选测试，Node 共 22 passed、JS 语法通过。仅前端变更，刷新 Shell 页面生效；实机视觉待验收。

- 2026-10-04 Todo 单目录导出：普通目录右键菜单新增“导出此目录”，支持 Shift+F10、Esc/点击外部/滚动收起和边缘定位；聚合目录不挂菜单。导出绑定右键目标，文件名包含目录名；backup API 可选 directory_id 并验证当前账号所有权，仅包含目标目录及项目树/附件/文本历史，空目录可导出，沿用原导入合并格式。Python 65 passed（新增范围/附件/历史/空目录/所有权及单目录往返），Node 17 passed、JS 语法通过；已请求 App-Dev 单次重启，菜单实机尚未验收。

- 2026-10-04 Todo 导出/导入迁移：新增账号范围 ZIP 下载与预览/确认导入入口，按目录名+完整父级路径+名称合并，新时间胜出、相同时间保留本地、本地独有项目保留。更新时间覆盖属性/排序/附件/生命周期/周期提醒更新；旧数据缺时间显式以创建时间估算。获胜项目附件集合替换，保留旧不可变 blob；归档/回收站批次保留，周期重算未来时刻，无补跑。执行文本历史去重导入，活动记录转中断并去除 Agent/Terminal 绑定；不含会话产物/模型/活动进程。拒绝同名歧义、活动队列导入、损坏附件、越限 ZIP；成员按名称读取而不解压到任意路径。导入比较预览指纹、SQLite 事务及失败文件清理。Python 66 passed（含往返、较新合并、幂等、归档恢复、损坏/歧义、并发预览、文件失败回滚、API账号隔离），Node 17 passed、JS 语法通过。导出/导入上限 512 MiB，单附件 32 MiB。

- 2026-10-04 Todo CLI/Terminal 联动：外部 Codex/Claude 使用交互 CLI argv，通过共享 TerminalManager 创建 PTY；Run 绑定 terminal_id，执行页可直接打开 Terminal App 并定位会话。Terminal 显示 source_app/source_task/managed_run、自动刷新列表；运行中来源任务终端前端禁用关闭、后端 close 默认拒绝，来源服务与关机清理可显式终止。断开页面不结束进程，等待持续占队列名额；终端退出码 0 记 ended（待确认），非零失败，日志保留，Local 重启标中断，不做 PTY 恢复承诺。保留 Codex workspace-write 和默认授权，不放宽权限；清理继承环境中的 AI2Apps/OMLX 凭据变量。Python 63 passed（含真实 PTY 输入输出/保护关闭/源端停止及既有 Terminal 合约），Node 17 passed、JS 语法通过。沙箱测试退出时出现无 Metal 设备的 atexit 提示，测试断言全通过；真实 Codex/Claude 交互 UI 尚待验收。

- 2026-10-04 Todo 队列完善：快照增加名额上限/占用、本人运行/等待处理/排队计数及队列位置；执行页与当前任务汇总显示，排队提供取消入口，失败/中断/取消支持按已保存配置重新执行（不自动重试）。内部 Harness 停止后继续观察，确认终态才释放名额；未捕获 job 异常登记失败后接续队列，超时提示明确。等待用户/授权继续占名额。Python 56 passed（覆盖停止等待确认、异常释放与账户隔离），Node 17 passed、JS 语法通过；已请求固定 App-Dev Local 单次重启。本项未改变外部 CLI 退出码结果判断，未增加 Desktop 会话接管。

- 2026-10-04 Todo 统一 FIFO 队列：所有执行器/项目共用默认 3 个名额，数据库持久化 todo_queued/queued_at，入场后记录 started_at，完成/失败/取消释放名额，等待任务可取消，重启恢复等待队列；既有 durable Harness Run 接回观察并占名额。等待输入/授权也占名额，同项目防重复保持。新增“当前任务”聚合运行/排队，“执行中”排除尚未入场任务；执行卡片显示等待说明。Python 54 passed（新增 6 任务验证上限/FIFO/取消/重启），Node 共 17 passed；已请求认证 Helper 单次重启 App-Dev，真实多执行器并发实机验收待完成。

- 2026-10-04 Todo 当前执行卡片：执行页顶部常驻状态、开始时间、耗时、当前步骤/最近日志、最新输出和错误，活动 Run 优先，结束后保留最近结果，可直接停止。沿用 5 秒轮询，不展示百分比；输出转义且限制展示尾部，完整记录仍保留；无日志时明确等待进展。JS 语法及原 Node 14 项回归通过，新增当前执行 2 项验证耗时冻结、活动优先、结束/空态及输出转义。仅静态刷新生效，实机真实 Agent 运行展示待验收。

- 2026-10-04 Todo 右栏详情/执行页签：详情保留状态/进度/优先级/Emoji/说明/父级/附件及归档删除，执行页集中执行器、模型、工作目录、周期与自动执行开关、执行按钮和记录。共用原表单与保存逻辑，切换只控制可见性保留草稿；隐藏字段校验失败自动定位页签；Gallery 导入自动回详情定位附件。归档/回收站记录也按页签展示；支持方向键切换。Node 14 passed、JS 语法通过，仅静态修改，刷新生效；尚未实机验收（当前 App-Dev 前台为浏览器子窗口）。

- 2026-10-03 周期提醒模式：Schedule 新增 auto_execute（默认 true，兼容已有自动任务），详情周期区域提供自动执行开关，保存后生效，Chat schema 同步。关闭后到期只重置 not_started/0%/completed=false/completed_at=null，不调用 Agent、不生成 Run；沿用停机补最近一次规则。状态与 next_due 同事务写入，校验 revision 避免覆盖并发编辑，轮询同步无草稿详情。Python 53 passed、Node 14 passed、JS 语法通过；已请求认证 Helper 重启 App-Dev Local，开关实机交互尚未验收。

- 2026-10-03 聚合目录扩展：新增执行中（含排队/规划/等待处理）、最近完成（最近 7 天）和周期任务，共用来源分组/祖先路径/计数/搜索/Chat 范围。后端记录真实 completed_at，编辑/排序保留时间，重新打开清除；旧完成项目无时间则不计入。快照保留全部活动 Run，避免最近 200 条历史截断执行中项目。Python 48 passed、Node 14 passed、JS 语法通过；已通过认证 Helper 重启固定 App-Dev Local。实机端口 50999 确认四个聚合入口、数量和最近完成切换/空态正确。

- 2026-10-03 Todo 聚合目录：左栏新增“紧急”，聚合各目录 U 级未完成且未归档/删除项目，按来源目录分组并保留必要祖先路径，父子命中不重复，路径行弱化且不计数。支持搜索/折叠、原目录定位；即时修改后移出结果但保留详情提示。聚合视图禁用手动排序和无归属顶层新建，子项目按父项目原目录创建，Chat 绑定聚合范围。Node 13 passed（含新增祖先闭包、搜索/折叠、生命周期/优先级过滤回归），JS 语法通过。仅模板/CSS/JS 修改，刷新生效；尝试实机验收时 Mac 锁定，未能完成 UI 验收，未重启或重建 App。

- 2026-10-03 Todo 归档/回收站：继续使用 SQLite；项目归档、软删除按子树批次处理，恢复不误恢复原先独立归档/删除的子项目，保留附件、执行记录和 Emoji 历史。列表筛选新增已归档/回收站及只读详情与恢复入口；关闭项目拒绝编辑、执行和附件变更，活动 Run 阻止归档/删除。归档/删除清除周期 next_due，恢复后从下一计划时间继续；未增加自动清空或永久删除。最终 Todo Python 47 passed、Node 10 passed、JS 语法通过。已通过认证 Helper 请求重启 App-Dev Local；交互实机验收待完成，未发布生产。

- 2026-10-03 Gallery 拖入项目行定位：接受素材时选中目标项目并展开右侧详情，聚焦/滚动到附件区域；上传完成后再次定位，若用户期间切换项目则不抢回焦点。同项目保留草稿，跨项目沿用未保存确认，等待即时保存结束后切换。Gallery Node 3 passed，覆盖目标绑定、定位调用、取消切换不导入及上传中导航不被覆盖；JS 语法通过。仅静态修改，刷新生效。

- 2026-10-03 Todo Gallery/目录排序：左栏增加 Gallery Tab，复用 Shell mountMiniEntry 与既有 Gallery mini URL。使用 gallery-asset MIME 和当前身份授权的素材接口，将文件复制到放下时绑定项目附件，支持项目行/附件区及 32 MiB 上限；附件独立刷新保留草稿。目录拖拽带插入提示，独立 order 表持久化，事务验证完整集合、预期旧顺序及所有权，新目录追加。Python 45 passed、Node 9 passed、JS 语法通过。已通过认证 Helper 重启 App-Dev Local（65039），实机确认三页签和 Gallery 真实素材加载；原生跨 iframe 拖拽及目录拖动尚未实机验收。

- 2026-10-03 进度滑块收起交互：移除下方数值/刻度行，滑块 change（拖动松手）提交后使滑块和数字框失焦，自动收起；Enter 确认同样收起。自动保存回归 4 passed（含失焦断言），JS 语法通过，刷新页面生效。

- 2026-10-03 进度聚焦滑块：数字框聚焦时下方展开 0–100%、step=5 的 range；移到滑块后保持展开，离开整个控件收起。拖动实时同步数字，change/回车提交自动保存，仍支持数字框 1% 精度输入；键盘可操作，保存回填同步滑块。Node 自动保存回归 4 passed，含拖动预览不提前写入和松开提交，JS 语法通过；静态刷新生效。

- 2026-10-03 项目状态/进度：新增 not_started/in_progress/completed/paused 与 0–100 整数进度，旧数据按 completed 映射为未开始 0%/已完成 100%。详情提供状态选择和百分比输入（change/回车自动保存），项目行显示状态与百分比，Chat 读写同步支持。服务端统一完成框、状态和进度：已完成/100%联动，降低已完成进度转进行中，暂停保留进度，取消完成复位；AI Run 状态独立。沿用串行自动保存和其他草稿保护，回填关联状态字段。Todo Python 43 passed、Node 6 passed、JS 语法通过；需保存当前编辑后重启 App-Dev Local 并刷新，实机未验收。

- 2026-10-03 Emoji/优先级即时保存：有效 Emoji 输入、回车确认、常用选择、清除、AI 生成及优先级 change 自动提交，更新项目行；使用已保存基线和乐观版本，不提交标题/说明等无关草稿。请求串行处理，刷新避让待保存操作，失败保留 dirty 状态并报错，IME 组合期不提交，Emoji 回车阻止整表单提交。新增 Node 回归覆盖连续写入版本、无关草稿隔离、回车/IME/无效输入和失败保留；连同 Mini-Entry 共 6 passed，JS 语法通过。仅 JS 修改，刷新生效。

- 2026-10-03 项目行顺序微调：完成框后依次显示优先级、Emoji、项目标题；仅修改渲染顺序，JS 语法检查通过，刷新页面生效。

- 2026-10-03 项目优先级：新增 U/S/A/B/C/D 六档（从高到低），新建及旧项目默认 C。详情提供下拉设置和顺序说明，项目行显示等级标记；Chat 查询/创建/修改同步支持，不改变手动排序。模型验证非法等级，持久化和 reorder 保留优先级；Todo 41 项测试通过，JS 语法通过。Python 模型更新需保存当前编辑后重启 App-Dev Local 并刷新生效，尚未实机验收。

- 2026-10-03 项目树同级拖拽排序：行可拖拽，增加 grip 和前/后插入线，只接收同目录/同父节点目标；排序包含未显示同级项，子树保持父子关系。专用 reorder API 事务内校验完整同级集合、去重、所有权和全部版本，原子更新 position/revision，保留计划时点。拖拽/提交期间暂停快照替换，有未保存编辑时阻止拖拽；刷新不会覆盖期间新增的表单编辑。Todo 34 项测试通过，含根级 API、子树保持、持久化、冲突回滚和跨用户/跨父项拒绝，JS 语法通过。Python 改动需重启 App-Dev Local 后刷新；尚未进行原生拖拽实机验收。

- 2026-10-03 新建弹窗回车修复：取消按钮改为 type=button 并显式 close(cancel)，创建保留唯一 submit/save，使输入框回车触发创建而非取消；每次打开清空 dialog.returnValue，避免 Esc 复用前次 save。目录、项目、子任务共用弹窗均适用。JS 语法及 Mini-Entry 3 项回归通过；纯静态修改，刷新生效。

- 2026-10-03 Emoji 再生成去重：请求传入当前草稿 Emoji，结合已保存符号和用户/项目隔离的最近 5 次成功生成历史，提示模型排除并对返回值强制检查；忽略 variation selector 的重复，最多 3 次模型尝试，总超时仍 90 秒。历史独立持久化，不变更项目草稿/版本；事务内复查避免并发重复，删除项目时清理历史。Todo 32 passed，覆盖当前/历史排除、连续重复失败、历史持久化/容量/隔离，JS 语法通过。用户截图存在未保存草稿，本轮未主动重启 App-Dev 以免丢失编辑；需保存后重启 Local 并刷新生效。

- 2026-10-03 Emoji Hover-Tip：输入说明和 AI 说明移入悬停/键盘聚焦气泡，移除原生 title 和常驻说明，选择区改为简短「常用 Emoji」。对齐 Shell Dock 的深色半透明背景、8px 圆角、阴影、70ms 延迟与 80ms 淡入缩放；固定定位、边缘避让，滚动/编辑/Escape/切换详情时关闭，关联 aria-describedby。JS 语法检查通过，静态页面刷新生效。

- 2026-10-03 Emoji 控件紧凑布局：输入框收窄到 56px，与 AI 生成、清除按钮同行并对齐高度，保留独立 label 与输入提示；JS 语法检查通过，刷新静态页面生效。

- 2026-10-03 项目 Emoji：增加独立可清除的 emoji 属性，旧数据默认空值；服务端校验单个 Unicode 字素（支持肤色、ZWJ、旗帜），项目树显示符号，详情提供输入、常用选择和 AI 生成。AI 使用 work_standard 模型与当前草稿标题/说明，复用 actor/app 隔离调用通道，结果只回填草稿，保存才持久化；避免生成期间切换项目或修改输入导致陈旧结果覆盖。Chat 创建/修改工具同步支持 emoji。Todo Python 31 passed（含持久化、清除、旧数据兼容、复合 Emoji、AI 预览及所有权/无效输出/未配置模型），JS 语法通过，共享 Mini-Entry Node 3 passed。已通过 App-Dev 认证 Helper 重启 Local，实际主窗口端口 49567；实机打开项目 Emoji 控件、调用真实标准任务模型生成 ✅、保存并通过 App 内刷新重新读取仍保留。示例目录 Todo MVP 体验的父项目保留此次生成符号。

- 2026-10-03 Todo 新建弹窗加宽：共用名称弹窗从 350px 调整为 700px，最大宽度限制为视口减 32px，使用 border-box 避免窄屏溢出。CSS 定向检查通过；静态资源刷新生效。

- 2026-10-03 项目树快捷创建：每个项目行右侧常显 Lucide 加号，点击以该行为父项目打开「新建子任务」弹窗，复用创建接口和未保存编辑保护；创建后展开父节点并选中新子任务。按钮支持键盘操作与无障碍标签，窄屏保留。JS 语法检查通过。

- 2026-10-03 UE 对齐：Todo 改为与 Studio 一致的独立 App 标题栏、黑色图标/主按钮、浅灰工作区与白色圆角三栏面板；目录/对话使用带图标页签，项目树与详情统一中性色、间距、控件和 Lucide 图标。新增刷新与左右面板开关，选中项目展开详情，窄窗口以浮层显示面板。仅改 Todo HTML/CSS/JS，App-Dev 刷新生效，无需重建。验证 JS 语法、既有 Mini-Entry Node 用例 3 passed；原生 AX 验证目录/项目树加载、详情选择、详情收起/展开和对话 Mini-Entry 加载。截图工具返回旧首页画面，像素级截图验收尚未完成。

- 状态：`implemented`，固定 App-Dev 已重建、通过签名/Runtime 校验并打开页面。用户级内置 `ai2apps.todo`：左栏目录／Chat Mini-Entry 切换，中栏项目树，右栏说明、附件、执行配置与运行记录。支持父子关系调整、完成标记、搜索、独立 SQLite 持久化与用户隔离、乐观版本冲突检查；不递归执行子项目。
- 执行：复用内部 General Agent Harness 和所有权隔离的 Session／Workspace／Document 服务；附件复制到每次运行的输入快照，并注册会话资源，文档可由既有工具读取。新增 Codex/Claude Code 非交互 CLI 适配，保留其默认权限机制；移除 Local 私有控制环境变量，不拼接 shell 命令。记录日志、结果、内部产物下载、停止、失败、外部运行重启中断、内部 durable Agent 重启后重新关联；运行成功不自动完成项目。DeepSeek 独立外部 Harness 尚未适配。
- 服务生命周期内调度每小时／每天／每周／每月；小时错过不补，日周月只补最近一次；新建或重启计划不追溯，运行重叠跳过，计划时点持久化推进。时区、DST 跳过、月末日期收敛已覆盖。按当前成员身份重新检查外部执行权限。
- Chat 宿主工具支持查询、新建、修改、执行；单轮对话冻结目录／节点范围，防止生成期间切换选中项写错位置。实际模型对话已创建指定子项目；随后暴露共享流式工具调用 ID 被重复拼接导致 `callId is invalid`，已修复并加回归，同时修正 hidden 样式和结构化错误显示；修复后真实模型往返待最终验收。
- 验证：`.venv/bin/python -m pytest -q tests/test_ai2apps_mini_app_chat.py ai2apps/tests/test_todo.py` 共 22 passed（Todo 18 + 共享 Mini-Entry 4）；在 ai2apps 目录运行 `node --test tests/todo_mini_chat.test.cjs` 3 passed；General Agent 既有模型调用用例另行通过。包含真实内部 AgentRepository/运行状态机 + 假模型、隔离工作区附件、外部 CLI fixture 的完成/取消/中断、权限隔离、树循环、四类计划和去重。Ruff、Python/JS 语法及 scoped diff 检查通过。真实 Codex 冒烟通过：独立 `/tmp/ai2apps-todo-codex-smoke-m1zcnfjm` 仓库，通过 TodoService 启动真实 Codex，要求不调用工具、不读写文件、仅返回 TODO_MVP_OK；status completed、exit_code 0、预期回复匹配。Claude 尚未真实验证。
- 固定 App 通过规定 `build-app-dev-environment.sh` 重建，前版归档 `AI2Apps-app-dev-20261003-125223.app`。`verify-release-app.sh`、`codesign --verify --deep --strict` 通过；根/Helper 保持 app-dev、Development、cloud、固定源码根与无生产更新 URL。实际原生标题已验证 `AI2Apps-App-Dev: App-Dev 127.0.0.1:57429`。实机验证目录/项目创建、说明保存、刷新持久化、Chat Mini-Entry 加载和子项目创建。App-Dev 内留有“Todo MVP 体验”示例目录。最新 Python 改动已通过认证 Helper 重启 Local；未发布 Desktop/Package，未改 Cloud。


- 最终限制：原生 Computer Use 在后续共享 App-Dev 浏览器调试窗口上连续超时，未完成最后一次真实 Chat 往返与附件 picker 复验；不操作其他调试任务的审核弹窗。后台/API 附件和内部 Harness 工作区接入已测试，最后代码通过认证 Helper 重启生效。

### NXR-BIDI-NATIVE-RECOVERY-20261003：原生 Shell BiDi 启动与自动恢复

- 状态：`implemented`，固定 App-Dev 已重建并完成连接验收，待下一版 Desktop 纳入。原生 AceFox Shell 入口补齐每次启动独立的 256-bit bearer、loopback 自动端口与 WebDriver BiDi 参数，避免绕过旧 Swift Launcher 后遗留失效记录。
- 受信任 Shell 从实时 RemoteAgent 状态原子发布当前实例 shell-automation.json，写入凭据前设置 0600；每秒核对并修复缺失/失效记录。Gateway 有界重读当前实例记录，404 失效 Session 重新建立；客户端建立连接失败时重新获取一次性票据并重连一次，401/403 不重试，不重放已提交浏览器动作。Chat/Agent 清除断线客户端，下一次操作重新连接。
- 同一 Gecko buildID 的开发资源覆盖会被旧启动缓存掩盖；构建入口给嵌入 Shell 设置 Development 标记，原生入口仅对该标记加入 -purgecaches，确保 App-Dev 的 Shell 覆盖实际生效。
- 文件：AceFox `browser/app/nsBrowserApp.cpp`、`browser/components/ai2apps/content/shell.mjs`；Local `ai2apps/browser/shell_bidi_gateway.py`、共享 `browser_bidi_client.js`、Chat/Agent Mini JS；`apps/ai2apps-acefox/scripts/build-release-app.sh`。
- 验证：Python 定向 51 passed；Node 恢复专项 5 passed（新票据、有界重试、拒绝认证重试、断线动作不重放、Agent 下次任务重连）；Shell 发布函数测试验证缺失/旧记录恢复及 0600-before-secret。JS 语法、Ruff 与 scoped diff check 通过。测试结束时隔离环境 MLX atexit 提示无法获取 Metal，不影响本轮浏览器测试结果。
- 固定 App-Dev 使用规定入口重建，旧 App 归档 `AI2Apps-app-dev-20261003-122321.app`；verify-release-app 与 codesign --verify --deep --strict 通过，根/Shell/Helper 实例与 Bundle ID、Development、cloud Runtime、可信源码路径契约通过。实机原生标题 `AI2Apps-App-Dev: App-Dev 127.0.0.1:53491`；通过认证 Helper 重启 Local。记录丢失实测 0.8 秒自动恢复，原生 getTree 成功；打开默认 Profile 后 Agent Sidebar 初始化、pageState 正常且无 Gateway 错误。本轮未执行 LLM 探索任务、未发布生产 Desktop。


### NXR-BROWSER-LAUNCH-SPINNER-20261003：浏览器启动等待图标

- 状态：`implemented`，待下一版 Desktop 纳入。AI Browser 启动按钮改用独立 CSS 等待圆圈，忙碌时隐藏外链图标、仅旋转圆圈，结束后恢复静态外链图标。避免 Lucide 将 i 替换为 SVG 后动态图标名称未及时更新，导致外链图标旋转。
- 文件：`ai2apps/web/templates/system_apps/ai_browser.html`、`ai2apps/web/static/css/ai_browser.css`。移除禁用按钮内所有 SVG 旋转的选择器；模板与 CSS diff 空白检查通过。仅静态变更，刷新 AI Browser 页面生效，无需重建或重启 Local；未完成实机动画验收。


### NXR-SUBTITLE-LLM-CORRECTION-20261003：字幕 LLM 修正与规则 Profile

- 状态：`implemented`，待 Host 更新和 Media Voice Studio Suite 发布。字幕提取后的校对区提供可选修正，使用系统 Standard tasks 模型，按有界批次生成严格一一对应的文本建议；用户审阅确认后才修改字幕，时间轴、说话人、段落顺序不变，修改文本清除旧逐字对齐。
- 修正规则支持保存、选择、更新、删除 Profile，复用可信 Host 中 owner/provider/resource 隔离的本地存储，独立于任务草稿，重置素材不删除 Profile。Opaque Package frame 经受校验的 Host 通道请求 LLM，不直接访问认证或浏览器存储。
- 新增 Host JSON API 与 Bridge 操作；需重启 Local 并刷新页面，Package UI 改动需后续发布 Suite，无需 Runtime 更新。本次不发布 Package、不读取 Cookie。
- 验证：Broker 与 Suite 定向回归 55 passed，包含修正结果时间/说话人保持、空字幕保持、原始数据不变、异常 JSON/数量/空文本拒绝和未声明能力拒绝；前后端语法与 diff whitespace 通过。未执行真实模型推理和桌面交互验证。

### NXR-H3-16X9-RESOLUTIONS-20261003：H3 新增 1024 与 1280 宽幅/竖幅尺寸

- 状态：`in_progress`。Video Studio 的 H3 系列变种新增精确 16:9／9:16 的 1024×576、576×1024、1280×720、720×1280 输出选项。1024 档直接满足 Worker 的 32 像素网格；1280 档由 Host 向既有 Worker 提交 1280×736／736×1280，并在结果发布前居中裁回目标尺寸、复用原压缩音轨。两种内部画布均低于既有 1,032,192 像素上限，无需更换或发布模型 Package。
- 需验证文生、图生及各 H3 变种的真实推理输出和首尾帧构图；当前仅有 Host 参数、裁切尺寸/帧数/音轨的合成测试，尚不能宣称视觉效果验收。

### NXR-AUDIOBOOK-SELECTED-DIALOGUE-20261002：完整对话仅合并勾选片段

- 状态：`implemented`，待下一版 Desktop 纳入。Audiobook 每个 Line 卡片前增加默认选中的复选框；完整对话只提交勾选的 segmentIds，按工程原顺序复用或生成音频并合并，未选片段不审批、不生成、不合并。
- 选择状态按工程保存在现有 Mini-App 草稿中，新片段默认选中；显示已选数量，空选禁用生成且函数再次保护，生成期间禁止修改选择。复选框不触发卡片展开或拖拽。
- 验证：Voice Studio scope 测试覆盖默认全选、排除片段、工程隔离、草稿恢复、生成请求、未选片段状态保留、空选保护和新增片段；JavaScript 语法检查通过。纯前端变更，刷新页面生效，无需 Runtime 或 Package 更新；尚未实机点击验证。

### NXR-DISCOVER-INSTALLED-UPGRADE-20261002：已安装模型升级入口

- 补充修复：实机 SoL-Refiner 升级误走可选的 model-install-plan，返回未声明安装计划。升级现在显式使用 Package 安装操作，保留现有 Checkpoint；审核批准/重试同样保持 Package 流程，不再退回模型档位选择。

- 状态：`implemented`。Discover 已安装列表为存在较新服务器版本的模型 Package 显示“升级”，保留详情与卸载；复用现有多语言和安装流程。升级明确传入服务器目录版本及兼容性信息，避免使用本地旧版本。
- Node 回归覆盖模型、服务、App、智能体的新版本入口、相同/旧版本及目录缺失不升级，并保持发现页模型操作不重复。仅静态 JS/模板变更，App-Dev 刷新即可生效，不需要重建或发布 Package。

### NXR-SOL-WHOLE-CLIP-20261002：SoL 全片精修与分块解码

- 状态：`package_published`。SoL 0.1.3改为全片 VAE 编码、潜空间放大与一次 DiT，仅 VAE 解码分块；修复 DiT RMSNorm 仿射与 GELU/SiLU、Upsampler SiLU 的 BF16 中间舍入差别。沿用 Runtime 1.8.8 和现有权重。
- Host 内存接纳按真实帧数增长；Worker 在模型载入前复查可用内存，不足时明确拒绝。新版 capability 禁止 Host 独立分段精修。需要未来 Desktop 纳入 Host 资源估计与 Studio 编排修改。
- 189 项相关回归通过。你的 124 帧 512×288 视频输出 1024×576，24 fps/音轨保留，41.30 秒；MLX peak 4.78 GiB、采样 physical footprint peak 6.22 GiB。签名候选在 Runtime 1.8.8 安装通过：4K RGBA/自定义提示词图片、124 帧视频、取消 499、restart/stop/start/uninstall；未代替用户接受模型许可。
- Package 0.1.3 已发布：submission `7b820804-645d-4126-9820-6b89c03203c1`，Repository Snapshot 242；公开完整下载与签名验证一致。Desktop Host 尚未发布。权重不变。杯子周期性形状跳变改善，但原杯纹理仍被模型重建成篮状纹理；不声称无失真。详见 `docs/ai2apps-sol-refiner-0.1.3-validation-2026-10-02.json`。

### NXR-VIDEO-UPSCALING-MINIAPP-20261002：Video Studio 内置视频放大 Mini-App 与长视频叠帧拼合

- 状态：`in_progress`。按用户后续决定改为 Video Studio 内置的“放大视频” Mini-App，不再需要独立 App Package；Video Studio 模型菜单提供“安装模型…”，通过 `video.upscaling` ACPF 安装 SoL-Refiner 标准或自定义提示词模型，固定 2×。结果进入 Video Studio 现有预览与输出。
- Host 使用后台持久 Studio Run 调度放大、进度轮询、取消与冻结输入重试。长输入按原帧时间轴分成有界重叠片段，对对应重叠帧交叉融合，校验最终帧数和 2× 尺寸，复用原压缩音轨；片段长度与重叠帧数按分辨率限制 Host 内存。单段合规视频直接交 Worker。输入暂限 CFR 1–60 fps、每边至少 32 像素、最长 1 小时/108000 帧和 1 GiB；按所选已安装模型能力区分旧版 512 上限与新版 `resource_limited`（无固定上限，仍受资源和编码器限制），不声称无缝画质与真实模型性能已验收。
- Host Python、Video Studio UI 和 ACPF Profile 须纳入未来 Desktop；不发布独立 App Package。需在固定 App-Dev 环境完成真实模型长片段接缝、音画同步、取消/重试验收。当前合成媒体的帧数、尺寸、音轨与内置 Mini-App/ACPF 契约定向测试通过；无 Metal 会话未做真实 SoL-Refiner 推理。

### NXR-SAM21-VIDEO-CUTOUT-20261001：动态视频抠像模型 Package 与 Worker 协议

- 状态：`package_published`。`ai2apps/model-sam21-mlx` 0.1.0、依赖的 `ai2apps/runtime-omlx` 1.8.6 及 Hiera Small Checkpoint Distribution 均已正式发布。Package 固定权重 revision，支持单对象正/负点提示、向前视频跟踪、软边缘灰度 MP4 蒙版；权重不进入 Package，MVP 限制为 450 帧、最高 1920×1080。
- 新增独立 `video_segmentation` Model Worker operation、`video_segmentation` model type 与严格 capability schema；Runtime 候选从 1.8.5 提升为 1.8.6，并声明 `video-segmentation`，复用现有 MLX/NumPy/SciPy/Pillow/PyAV/视频编码层，不新增 OpenCV 或其它原生依赖。Host 与 Runtime 必须同时升级，旧 Runtime/Package 机制保持兼容。
- Package 包含固定上游源码/权重提交、Apache-2.0、NOTICE、SBOM、纯 Python OpenCV 最小兼容层和 Sandbox-safe Worker Adapter。当前 75 项 Provider/Worker/资源/capability 回归、Ruff、diff check 与标准 Model Worker harness `--check` 通过；软蒙版 MP4 编码/回读通过。无 Metal 的终端测试仅产生已知 atexit 警告，不计为推理验收。
- 正式回执：Checkpoint Distribution `dist_ai2apps_sam21_hiera_small_mlx_1b7b9882_v1` 使用 HF/ModelScope 双端完整下载验证，Index 97；Runtime 1.8.6 submission `e2bf34a2-8fdf-447e-81c6-9e747c3a49ad`，Cloud/GitHub/ModelScope 三源 active；模型 submission `7894c594-7325-4d7b-9acc-dede4de87c0d`，Repository metadata 236。精确签名 Runtime + SAM Package 已在独立实例安装，Worker `running`，依赖锁精确指向 1.8.6；公开 Registry 回读确认两份归档和 envelope 与本地完全一致。真实权重视频推理和 Composer 动态蒙版 UI 接入仍作为下一阶段 Desktop 验收，不在本次 Package 发布结论中宣称完成。

### NXR-AVTR1-MLX-20261001：授权权重与完整推理移植

- 第二轮优化 `verified`：默认 2 帧解码批次，GPU uint8 转换与下一批预取，有界异步 FFmpeg 直出 H.264/AAC；快速模式同素材生成循环 23.75 s（10.53 fps），文件就绪 23.98 s，MLX peak 4.97 GiB，无回退。5 帧模式 24.17 s / 7.76 GiB，不设默认。
- 2/5 帧批量与逐帧对齐、尾批次和坏帧回退通过；编码帧序/同步异步一致性/错误原子性/线程与进程清理 3 项集成测试通过。三维布局、通道补齐、稀疏采样未证明明显提速，实验实现已移除。仍未纳入生产 Runtime / Model Service。

- 渲染优化已验证：融合 Metal 采样、等价 mask 卷积、肖像固定子图缓存、NHWC 解码、静音 HuBERT 缓存。默认 FP32 模式生成 10 秒视频 31.85 s；可选缩放 FP16 解码模式 25.86 s（较原版 39.01 s 快 1.51×），MLX peak 4.41 GiB，250 帧无非有限值回退。
- 新增 12 组姿态逐像素对齐、源缓存切换回归和模式选择；高精度最大误差 1.37e-4，快速模式 PSNR 56.55–62.97 dB。快速模式仍为可选，未做多肖像长视频和最终 Runtime 验收。
- 状态：`prototype_verified`，不纳入当前 Desktop 发版。用户授权权重已下载，完整 MLX 音频、运动和渲染链生成 10 秒 512²/25 fps 视频；开发入口、固定资产摘要及转换/对齐脚本已保存。
- M5 Max / 128 GiB：生成循环 39.01 秒（6.41 fps），MLX peak 5.53 GiB；18 项真实权重数值对齐和 12 组采样回归通过。独立入口未导入 Torch/ONNX Runtime；抽帧与音画轨道检查通过。
- 仍需渲染优化、正式共享依赖、Model Service/Worker/安装和最终 Runtime 验收；本轮未变更生产 Runtime、Desktop 构建或发布 Package。详见 `packages/ai2apps-model-avtr1-mlx/README.md`。


### NXR-RELEASE-013-2256-20261001：Desktop 0.1.2 Build 2256

- 状态：`candidate_testing`。生产匿名基线仍为 0.1.1 / Build 2254；此前 0.1.2 / Build 2255
  只完成 App/DMG、公证和 GitHub/ModelScope 双源，未经过 Cloud stable 发布，因此不会被
  客户端发现，现由 2256 取代，不再激活 2255。
- 2256 纳入已经完成的数字人 Host/ACPF/素材槽位、照片说话持久任务与共享输出、FlashHead
  已发布源码记录、Video Composer 特殊层/轨道/羽化/相邻片段空帧修复、字幕提取后校对与
  渲染，以及 multipart 复杂字段编码修复。产品版本保持 0.1.2，rollout ID 固定为
  `build2256-test`。
- 明确延期并排除 AVTR-1、MuseTalk、InfiniteTalk、Ex-Omni 的实验移植、对应 parity 测试与
  权重准备脚本；个人参考音频 `ai2apps-test-system/assets/voice-1.wav` 继续排除。Avatar Studio
  Suite 仍须作为独立签名 App Package 发布，不作为 Desktop DMG 内置 Package 冒充已发布。
- 首轮候选门禁：Python 定向 187 项、ACPF 本地化 3 项、Node 专项 5 项、全部 18 个 Node
  文件、Swift 77 项 Swift Testing + 2 项 XCTest、JavaScript 语法、限定 Ruff 和 diff check
  通过。完整 Python 首轮发现 Avatar ACPF 新 Profile 缺少 9 组中英文映射；已在
  `fff39864` 修复并专项复验，正式候选须在最终源码提交上重新跑完整 Python。
- 发布准备记录：`docs/ai2apps-desktop-0.1.2-build2256-release-preparation-2026-10-01.md`。

### NXR-VIDEO-DURATION-HALF-SECOND-GRID-20261001：视频时长滑块对齐半秒档位

- 状态：`implemented`，待下一版 Desktop 纳入。Video Studio 现在先将模型声明的时长上下限收紧到 0.5 秒网格，再以相同步长量化恢复或切换模型后的时长。修复 OpenVDN 因 `minimum_seconds: 0.92` 导致浏览器产生 `0.92/1.42/1.92/2.42...` 档位，界面只能显示 1.9/2.4 而无法选择 2.0 秒的问题。
- 变更仅涉及 Host 静态 UI 与回归断言；不需要更新 MiniMax H3 Package 或 Runtime。

### NXR-AVATAR-SLOTS-20261001：数字人模型菜单与素材槽位

- 状态：`completed`（开发实现）。模型下拉菜单增加“安装模型…”并启动 ACPF，保留当前模型选择；图片/声音使用支持选择、替换、移除的素材槽位，图片显示缩略图，声音显示文件信息。
- Finder 直接读取 File，Gallery 和图片/声音 Output 通过已授权 mount 的 `avatar.input.read` 桥接读取；Host 固定源 API、验证 actor/实例可见性、媒体类型和大小，拒绝任意 URL、未知引用和类型不匹配。图片上限 20 MiB，声音 100 MiB；读取时限制流大小。
- 本项修改共享 Host JS 与缓存版本，须随 Desktop 发布；App Package 尚未发布。验证：20 项 Python 定向回归；Node 覆盖 ACPF 菜单、Finder/Gallery/Output 拖拽处理、清空/类型拒绝、引用权限和共享输出。App-Dev 实测菜单打开 ACPF、取消保留模型、图片选择/移除及声音选材，Gallery 跨 iframe 的原生拖拽自动化未观测到投递，未计作实机通过；对应事件与桥接路径由 Node 回归验证。Package 沙箱目前没有 media-src，故声音槽位不新增内嵌播放器。

### NXR-AVATAR-MINIAPP-20261001：照片说话独立 Package 与可选模型

- 状态：`completed`（开发实现与 App-Dev 成片验收完成，待发布）。独立 `ai2apps/avatar-studio-suite` 源码 Package 挂载 Video Studio；必需能力 `video.avatar_generation` 由 Host ACPF 按用户选择解析模型 Package、Runtime 和 checkpoint，默认 FlashHead Lite，另有 Pro/EchoMimic。App 不强制安装全部模型。
- 新增签名模型能力协商、持久视频任务、mount-bound 模型/任务查询、显式取消和冻结输入重试。页面断开不取消，重新挂载恢复状态；Local 中断的推理可重试，不承诺断点续算。Host 输出回读幂等发布 Studio Artifact，Mini-App 不维护播放器/下载/输出历史。
- Host 后台 multipart 对 list/dict/bool 使用 JSON 编码，修复真实 FlashHead 请求的 reference_parts 400 错误。共享输出接收没有下载 URL 的任务状态通知并刷新；更新静态资源版本。挂载上下文中的 studioInstanceId 由已授权的 Host Header 决定，不允许请求 context 覆盖。
- 验证：90 项 Python 定向回归通过；Node 数字人任务/共享输出通知与 Voice Studio 输出选择检查通过；Ruff、JavaScript 语法检查通过。
- 实机：固定 App-Dev 的 ACPF 成功安装已发布 FlashHead 0.1.0、共享 Runtime 1.8.5 及 Lite checkpoint（7.60 GiB 下载显示）。正常 UI 上传上游测试人像和两秒音轨，首次请求暴露上述传输错误，修复后重启 Local，通过 Mini-App 重试保存输入成功。生成期间切换“提取音轨”，返回后状态恢复完成；Host 播放器显示视频、Gallery 和下载入口。底层任务用时 31.27 秒，输出 H.264 512×512、25 fps、50 帧及 AAC 音轨，容器 2.064 秒、116889 字节；这是功能验收，未作性能基准。
- 成功任务 `vgt_0752f6a8cccf45f7a79714ea0a582756`，Run `strun_522558f1bab64e009585c3bbc5462e93`，一次输出 `sta_6f36f37ed89a4c1d85d622e08c05cf1c`。权限范围与重复投影、取消/重试路径有自动回归；本轮未单独做生成中取消的 GUI 验收。
- 发布门槛：本项必须纳入未来 Desktop（Host Python/JS/ACPF 改动）。Mini-App 0.1.0 尚未签名构建或发布，须在支持该 Host 桥接的 Desktop 上完成精确签名归档的严格沙箱安装验收，再发布 App Package。完整公共 Avatar SDK（plan、人物准备、实时会话）仍待实现。

### NXR-FLASHHEAD-PACKAGE-20261001：FlashHead Lite/Pro 独立模型 Package

- 状态：`completed`（Package 已独立发布）。Cloud schema 修复已生产部署；FlashHead 0.1.0 与两项权重 Distribution 均已发布。submission `9bdace9a-a530-4055-b2d1-a1fd73bd86be`，Repository Snapshot 227。原始归档/签名未变。
- 一个 Package 提供 Lite/Pro，Lite 推荐；不内嵌 Runtime 或权重，依赖已发布共享 oMLX Runtime >=1.8.5,<2.0.0。没有新建 Runtime。
- 新增 Worker Adapter、变体切换、按需加载/卸载、取消与输出清理、自包含检查点清单和双源规格；修复非整数帧音频尾部截断、multipart 文本参数解析和 Sandbox 父目录探测。
- 验证：16 项定向测试、标准 harness 和 Ruff 通过；真实 Runtime Worker Lite 60 秒/1500 帧耗时 99.71 秒，MLX 峰值 8.53 GiB；Pro 10 秒/250 帧耗时 132.59 秒，峰值 10.53 GiB（含加载和媒体校验）。
- 精确签名归档在独立临时实例安装，依赖锁为 Runtime 1.8.5。Host 验证已发布 Distribution 并激活 checkpoint，两版真实 Sandbox 生成 2 秒视频成功；生成中取消、健康、停止、重启和卸载通过。保留权重；未修改用户 Dev/App-Dev 安装状态。
- Cloud OpenAPI 1.55.0 已接受完整安装投影，无需新增 legacy map。Cloud 回执：370 passed、旧客户端 130/130、独立实际安装 active；本轮未重跑推理。本地匿名回读确认双模型选择、Lite 推荐、归档逐字节与 envelope JSON 一致。未发布新的 Desktop；本项不要求重建 Desktop。
- 归档 SHA-256：`9441a6f06dc0a3175f858be678e8eb13d53993fed4ba2c946a220d666a051e69`，59,293 字节；收据位于 Package `dist/0.1.0/`，详情见 `docs/ai2apps-flashhead-mlx-0.1.0-release-2026-10-01.md`。

### NXR-AVATAR-STUDIO-20260930：数字人 Package 与照片说话接入

- 状态：`in_progress`。新增 Avatar Studio Suite 源码 Package、EchoMimic 的 ACPF Profile、mount-bound Broker、视频队列与共享输出接线；复用现有 oMLX Runtime。随后按用户要求暂停 UI 推进，新增 MuseTalk、FlashHead Lite/Pro、AVTR-1、InfiniteTalk、Ex-Omni 的原生 MLX 移植源码；现有 EchoMimic 和 MoE 算子保持原样。
- 验证：Package manifest/ACPF 校验、新增数字人 Python 回归及既有 Broker、视频队列、Mini-App、Video Studio 定向回归共 76 项通过；Node 数字人取消、setup 和 Voice Studio 输出选择回归通过。App-Dev 界面控制超时，真实挂载、成片、取消与正式 sandbox 安装验收待完成；尚未发布。
- 模型阶段进展：FlashHead Lite/Pro、MuseTalk 模板、InfiniteTalk 单人和 Ex-Omni Teacher 已跑通原生 MLX 短视频；Ex-Omni Thinker/Talker/codec/参考音色 encoder 真实权重分别验证。新增离线 CLI、安全权重转换和数值/媒体回归。AVTR-1 完整权重访问返回 401，尚未完成模型还原；自动预处理、完整多模态、长视频与最终 Runtime 仍在进行。
- 模型验证与缺口：`docs/ai2apps-avatar-model-port-status.md`。新模型源码尚未注册为可安装 Service，未进入生产发布或升级现有 Runtime。
- 计划：`docs/ai2apps-avatar-studio-implementation-plan.md`。
- 接口设计：`docs/ai2apps-avatar-capability-contract-v1.md` 已形成，覆盖人物准备、能力协商、离线 Job/输出与未来实时会话。尚未落地新 API；后续迁移必须移除 Host 对 EchoMimic/固定分辨率的绑定，并验收同请求切换 Provider。

### NXR-RELEASE-012-2255-20260929：Desktop 0.1.2 Build 2255

- 状态：`superseded_unpublished`。生产匿名基线为 0.1.1 / Build 2254；用户已批准提升产品版本至
  0.1.2，重建 Dev、App-Dev、Test 和正式 Release，并完成签名、公证、GitHub/ModelScope
  双源及 Cloud 100% 发布。Build 分配为 2255，rollout ID 固定为 `build2255-test`。实际仅
  完成公证与双源上传，Cloud 因需在生产任务中逐 Build 直接授权而未发布；生产始终保持
  2254。2026-10-01 已决定由包含后续修复的 Build 2256 取代，2255 不再进入 stable。
- 相对 2254 的产品代码增量仅为 Video Composer 无原生文件路径时的安全文件流导入修复，
  以及产品版本提升；不重发独立 Runtime 或模型 Package。范围与门禁见
  `docs/ai2apps-desktop-0.1.2-build2255-release-preparation-2026-09-29.md`。
- 个人参考音频 `ai2apps-test-system/assets/voice-1.wav` 明确排除。完整 Python 为 10287
  passed、68 skipped、74 deselected；Swift 77+2、Node 16/16 通过。Dev、App-Dev、Test
  已按固定脚本重建并通过身份/深层签名验证；正式 Release 仍须 clean main、Developer ID、
  公证、双源和 Cloud 两阶段验收。

### NXR-RELEASE-011-2254-20260929：Desktop 0.1.1 Build 2254

- 状态：`released_pending_target_mac`。正式 main
  `7850b8ab6edfa701504badb2788ecf4307e85e01` 已完成构建、Developer ID 签名、Apple 公证、
  GitHub/ModelScope 同字节双源发布；Cloud 已按同一 `build2254-test` 先 0% 原子登记并扩至
  10000 basis points。最终生产清单 SHA-256 为
  `e743e9a5e018e5535d4ebaae6717d3492ab01c0bd865943109035e21b34d40c9`。当前只待目标 Mac
  实际升级、启动及旧备份清理验收，完成前不标记 `included`。正式记录见
  `docs/ai2apps-desktop-build-2254-release-receipt-2026-09-29.md`。
- 本候选汇总 2253 后已实现的 ACPF 生命周期/Checkpoint 阶段、Chat Rush/上下文/实时与
  整轮遥测、Models/Worker SSD 状态、Video Composer、Unicode Artifact、Audiobook 拖拽
  以及对应 Runtime 1.8.5 Host/UI 承载。App-Dev 录屏工具仍严格限定 Development，生产
  Shell 不注入该变换。详细范围见
  `docs/ai2apps-desktop-0.1.1-build2254-release-preparation-2026-09-29.md`。
- Node 16 个测试文件及 Swift 77+2 项通过。完整 Python 首轮发现两处过期合同并已修正；
  下一轮只出现 5 个上下文窗口兼容失败，根因是未传 `max_context_window` 时仍访问合成
  Engine 的空 tokenizer。现已限定为只有显式窗口才计数，Batched/VLM/SpecPrefill 定向
  56 项通过；最终完整 Python 复验为 10287 passed、68 skipped、74 deselected，742.17 秒，
  无失败。JUnit：`/private/tmp/ai2apps-2254-full-final2.xml`。
- 发布门禁已经通过：clean main、Developer ID、公证/staple/Gatekeeper、GitHub/ModelScope
  匿名完整回读与 Range 字节校验、Cloud 0%/100% 两阶段验收均成功。个人参考音频
  `ai2apps-test-system/assets/voice-1.wav` 明确排除；四网络矩阵和目标 Mac 端到端升级仍待完成。

### NXR-AUDIOBOOK-LINE-GALLERY-DRAG-20260929：已生成 Line 音频拖入 Gallery

- 状态：`implemented`，待下一版 Desktop 纳入；静态页面刷新即可生效，无需更新 Runtime 或 Media Voice Studio Suite。
- Audiobook Line 卡片悬停时读取现有、服务端验证匹配的私有音频缓存，复用 Host 音频拖拽方法，以 WAV File 导入 Gallery。无需重新生成或向共享输出历史发布中间 Line；Gallery 副本与私有缓存独立。
- 仅暂存一个卡片的音频，最多 64 MiB；未生成、待更新以及文本、角色或配置发生变化的卡片不拖出旧结果。编辑框和卡片操作按钮保留原交互，异步请求过期时丢弃结果。
- 验证：JavaScript 语法与 Voice Studio scope 回归通过，覆盖 File 拖拽、缺失/过期音频拒绝、异步失效和编辑区域保护；尚未完成 Shell 中真实鼠标拖放验证。

### NXR-ACPF-SHARED-CHECKPOINT-VERIFY-20260929：共享模型命中不再假死

- 状态：`implemented`，已通过受认证 Helper 控制通道重启固定 App-Dev Local（当前端口 56424）并确认 Shell 恢复；待下一次全新实例安装进行完整实机时序复验并纳入下一版 Desktop。重置实例后安装已存在于机器共享 Cache 的 DeepSeek V4.1 时，后台并非重新下载或死锁，而是对约 206 GiB 权重生成首次 SHA-256 验证收据；随后创建 Worker 视图又重复全量读取一次，ACPF 全程停在“下载 55%”，造成卡死观感。
- 同文件系统的 Worker 视图现在只硬链接刚完成密码学验证的只读文件，并为目标树生成独立、绑定 inode/stat 的验证收据，不再进行第二遍 O(model bytes) 哈希。若跨文件系统退化为真实复制，仍保留完整 SHA-256 校验，不能以性能优化绕过信任边界。
- 没有验证收据的旧共享 Cache 仍会执行一次必要的全量校验，但按当前文件和总字节持续上报 `verifying_checkpoint` 进度；ACPF 将该阶段显示为验证而非下载，进度条不再固定在 55%。已有有效收据的后续实例重置只做 O(number of files) 的只读 stat 校验。
- Qwen3.8 Flash Next 实机跟进确认首次 103.94 GB 校验到 100% 后，Worker 启动期间仍短暂停在 88%，并继续显示过期的 `vocab.json · 100% · 0 B/s`，造成第二种“卡住”观感。现于校验结束后立即清空逐文件传输字段，依次切换为 `materializing_checkpoint` 与 `activating_checkpoint`；ACPF 隐藏过期传输卡并改显验证/启动阶段。该次安装随后成功，两个快照验证收据均存在，抽查权重的 device/inode 完全相同，确认没有第二次复制或哈希。
- 部署：修改 Host Python、共享 ACPF JavaScript 与测试；App-Dev 只需从 Helper 重启 Local 并刷新页面，无需重建 App、升级模型 Package 或 Runtime。
- 验证：Checkpoint acquisition/distribution、Installer 状态清理与 ACPF Provisioning 定向回归 76 passed；JavaScript 语法、Python compile 与 `git diff --check` 通过。Ruff 对本次新增闭包绑定无新增告警；文件中既有 Piece download 闭包仍有独立 B023 基线告警，不在本修复范围内。

### NXR-RUNTIME-185-MOE-TELEMETRY-MEMORY-20260929：全 Cached-MoE SSD SSE 与 macOS footprint

- 状态：`runtime_1_8_5_released`。Runtime 1.8.5 已完成 Developer ID 构建、Apple 公证、
  精确签名 Package 隔离安装、Cloud 发布和 GitHub/ModelScope 三源激活。Package SHA-256
  为 `56997274091b7c7df8d7823c26767c7111eb53539ff400e361220b0f0fec7c97`；Cloud submission
  `bc7414ec-5cea-4854-aea2-98da196138da`，最终 Repository metadata 224、Source revision 6、
  Snapshot `3a07275ea889a89005f9c9610e1c522686fe9e95842508abd37dfbb88c3f2d0b`。正式收据见
  `docs/ai2apps-mlx-runtime-1.8.5-moe-telemetry-memory-release.md`。
- Runtime 将 rolling 10-token 与 whole-turn SSD pressure 接入全部已发布 Cached-MoE
  引擎：DeepSeek V4/V4 2-bit、DeepSeek V4.1、GLM-5.3、Qwen3.6 text、Ornith 1.5
  Vision 和 Qwen3.8 Flash Next。新增共享 helper 只采样既有缓存计数，并复用 Decode
  完成 callback；原 Boost/adaptive callback 保持在同一边界执行，不增加 MLX 求值、
  Metal readback 或 GPU→CPU 同步。模型 Package 与 checkpoint 无需升版。
- Desktop/Host Worker snapshot 新增 macOS `phys_footprint`，同时保留 RSS；Chat 当前值
  与整轮峰值优先显示 footprint，并以 `FOOTPRINT` 标明口径。真实 V4.1 短推理峰值
  RSS 43.4923 GiB、physical footprint 51.6140 GiB，相差 8.1218 GiB，确认旧 UI 低报
  来自 Metal/IOAccelerator 统一内存未完整计入 RSS。此项必须随下一版 Desktop/App
  纳入，单独发布 Runtime 不能改变旧 Host 的内存卡片。
- 验证：共享 telemetry/四引擎接线 9 passed；Runtime、Worker、Package、Engine、
  Adapter 与 Chat 联合套件 237 passed；Desktop Product、Shell、Package、Chat UI 收口
  198 passed；Ruff、compileall 与 diff whitespace 通过。真实 V4.1 的 1 个完整 Decode
  步读取 83 个专家、1,560,453,120 bytes，pressure 34.583333%，recent/turn 一致。
  交接见 `docs/ai2apps-mlx-runtime-1.8.5-moe-telemetry-memory-handoff.md`。

### NXR-CHAT-TURN-TELEMETRY-20260929：整轮 SSD 平均、Worker 峰值与 Cloud 指标收口

- 状态：`runtime_1_8_5_released`。Runtime 1.8.3 已完成的传输链路在 1.8.5 中扩展到全部已发布 Cached-MoE 引擎，并正式完成 Developer ID 构建、公证、精确隔离安装、Cloud 发布和 GitHub/ModelScope 三源激活；submission `bc7414ec-5cea-4854-aea2-98da196138da`，最终 Repository metadata 224、Snapshot `3a07275ea889a89005f9c9610e1c522686fe9e95842508abd37dfbb88c3f2d0b`。中间 1.8.4 候选已由 1.8.5 取代。Desktop/Host 展示仍待下一版 Desktop 纳入。本地 Cached-MoE 生成期间继续显示最近 10 个 Decode token 的 SSD pressure；推理结束后切换为本轮累计 SSD 读取字节 / 本轮理论路由专家字节的加权整体平均，并保留整轮专家加载次数与健康分级，不再让最后一个 10-token 窗口冒充整轮结果。
- 本地模型的 Worker memory 在生成期间显示当前 macOS physical footprint，并以 250ms 频率采样本轮最大值；结束后显示并随回复保存 `WORKER MEMORY · PEAK`。峰值与 Worker service key 绑定，切换模型或历史回复时不会套用另一 Worker 的数值；系统 footprint 不可用时安全回退到 RSS。
- Cloud/Fusion 模型的性能区只保留横跨整行的端到端 `DURATION`。客户端虽然能观察 SSE chunk 到达时间，但无法获得可信的提供方 Prefill、Thinking 分段或逐 token 发射时间，故不展示可能受网络、代理缓冲和 chunk 合并影响的伪 Prefill/Token Gen TPS；本地模型继续显示完整六项指标。
- Runtime/Host 合同：DeepSeek V4 Flesh 与 DeepSeek V4.1 专用引擎均按 Session 维护 `ssd_turn_by_session`，并通过 `get_live_metrics(session_id)` 只导出已经物化的 `ssd_recent_10_tokens` / `ssd_turn_average`；Worker 将其放入既有 `ai2apps_metrics` SSE 扩展帧。V4.1 在 Prefill 完成后建立基线，并从各层 resident bank 已完成的 SSD 字节精确换算专家数；统计读取纯 Python 计数，不新增 MLX 求值或 GPU→CPU 同步。无需升级模型 Package。
- 验证：整轮 SSD 数学回归以及 Runtime、Worker、Package、Product、Chat 与 Engine Pool 定向回归共 254 项通过；Python 编译与 diff whitespace 检查通过。正式 Runtime 1.8.3 的公证、staple、Gatekeeper、匿名三源逐字节/Range、Publisher envelope、CPython 3.11.10、MLX 0.32.0、Metal、原生 `preadv_fused_experts`、实时遥测接线和 DeepSeek V4.1 Worker 启动均通过；发布收据见 `docs/ai2apps-mlx-runtime-1.8.3-live-telemetry-release.md`。固定 `AI2Apps-app-dev.app` 已通过专用脚本重建并完成严格深层签名验证，bundle ID/instance ID 分别为 `com.ai2apps.desktop.appdev` / `app-dev`；实机刷新后本地模型空闲态显示 `SSD PRESSURE · TURN AVG`，非本地/模型目录加载前只显示 `DURATION`。
- 2026-09-29 实机跟进：Runtime 1.8.3 的滚动 Token Gen 已在 DeepSeek V4.1 生效，但 SSD 卡片仍为空，由此定位到专用引擎遗漏。中间 1.8.4 候选在 V4.1 完成 Decode 步的既有安全边界更新统计；最终 1.8.5 统一 GLM/Qwen/Ornith 遥测并已正式发布，同时改正 Host 内存口径。完整测试、实测与发布结果以 1.8.5 发布收据为准；仍待包含 Host/UI 的下一版 Desktop/App 纳入并实机复验。

### NXR-CHAT-LOCAL-WORKER-TELEMETRY-20260928：本地模型 SSD 压力与 Worker 内存

- 状态：`implemented`，待下一版 Desktop 纳入。Chat 右侧性能区对任意本地对话模型始终显示 `SSD PRESSURE · 10 TOK` 与 `WORKER MEMORY`；Cloud/Fusion 模型不显示这两张本地运行卡片。
- Cached-MoE 从当前模型独立 Worker 的最近 10 个 Decode token 窗口显示真实 SSD pressure、专家加载数与健康颜色；生成中 Worker 暂停导出引擎统计时保留最近一次有效窗口。非 Cached-MoE 或尚无真实窗口时明确显示 `— / —`，不再把缺失数据伪装为 `0.0% / 0 experts`。
- 原 `SCOPE` 卡片移除，改为当前模型 Worker 进程内存（GiB/MiB）；1.8.5 Host 修正后主值为 macOS physical footprint，并保留 RSS 作为回退/诊断。未驻留或 Worker 不可用时显示 `—`。该数值代表 Worker 的 Runtime、模型与缓存，不伪装成模型权重或全系统内存压力。
- Host 的 Worker snapshot 只从空闲状态安全投影 SSD 窗口，不向浏览器暴露完整引擎内部统计；Chat 以最多每秒一次的频率读取既有同源 `/v1/platform/workers`，内存可在生成期间更新，SSD 窗口在安全可读时更新。
- 部署：HTML/JavaScript 刷新即可加载；新增 Host Python Worker snapshot 字段需重启 App-Dev Local。无需重建 App，也无需升级 Runtime 或模型 Package。
- 验证：Worker 遥测投影、完整 Chat UI、Chat 产品合同与 Worker 管理接口共 64 项定向回归通过；Ruff（忽略该文件既有无关 `SIM102`）与 diff whitespace 检查通过。仅通过认证 Helper 控制通道重启固定 `app-dev` Local 后，实机 Chat 已显示 `SSD PRESSURE · 10 TOK — / —` 与 `WORKER MEMORY 80 MiB RSS`，原 `SCOPE` 卡片消失；当前 Worker 尚未执行新一轮 Decode，因此未把无样本状态冒充为 SSD 真值，真实压力数值随下一次完成的 Cached-MoE Decode 窗口更新。

### NXR-CHAT-LIVE-INFERENCE-METRICS-20260928：思考 token 与流式性能指标

- 状态：`implemented`，待下一版 Desktop 纳入。Chat 的 Thinking 块无论展开或折叠，生成期间都显示引擎已生成的思考 token 数；完成后随消息保存，切换历史消息仍可见。
- oMLX Worker 在每个 Chat Completions 流式输出中增加隔离的 `ai2apps_metrics` 扩展帧，携带累计 prompt/completion token、引擎单调生成时间与 Prefill 速度。Prefill 在首 token 到达时立即显示；若引擎未提供原生值，明确使用 Worker 观测 TTFT 估算，不包含模型加载。
- 生成期间的 Token Gen 速度按最近 20 token 的引擎时间窗口计算，反映当前速度而非从请求开始到当前的累计平均；完成后仍以最终 usage 的整次平均作为回执。旧 Worker/Cloud 路径仍保留 `/admin/api/stats` 轮询兼容。
- 部署：Host HTML/JavaScript 刷新即可加载；Worker Python 需重启 App-Dev Local，无需重建 App，也不需升级模型 Package 或独立 Runtime Package。
- 验证：Worker SSE 与 Chat UI 定向回归 56 项通过，覆盖原生/估算 Prefill、累计 token 扩展帧、20-token 滑动窗口、Thinking 折叠计数和多会话隔离；`git diff --check` 通过。App-Dev 已热刷新前端，但本轮未能通过 Helper 状态栏重启 Local，故尚未完成真实模型的流式界面验收。

### NXR-CHAT-RUSH-TOGGLE-20260928：Rush 改为单击开关

- 状态：`packages_released`。Runtime 1.8.1 与 Ornith 0.1.5 已按依赖顺序正式发布；App-Dev 页面开关与重启复位已实机验收，仍待最终签名 Runtime 的六后端真实 Natural/Blast 矩阵及长回复中途切换速度验收。Chat 右侧 Rush 不再要求持续按住，也不要求已经开始生成：单击开启后，下一轮对话从请求起始即使用该模型声明的 Blast 策略；生成过程中开启或关闭仍可实时切换，再次单击恢复 Rush 前的 Engine Boost 模式。各模型的 Blast 保护路由数不同，界面不再把所有 MoE 错写成 Head2。

- 2026-09-28 Engine Boost 生产链修复：DeepSeek V4.1 正式接入既有 Decode Burst（Natural=精确 Top6、Turbo=Top4、Blast=Top2，Prefill 保持精确），控制切换在请求/下一 Token 边界生效；Qwen3.8 Flash Next Cached-MoE 与 Ornith 1.5/Qwen3.6 VLM Worker 改用带会话控制器的专用 VLM Engine，不再静默忽略 `flesh_boost_mode`。Worker 最终 usage 与空闲状态端点记录实际 Boost 模式、替换/miss/命中统计。现有 DeepSeek V4、Qwen3.6 文本版和 GLM 5.3 控制链保持不变，并纳入跨模型契约测试。
- Package 发布：`ai2apps/runtime-omlx 1.8.1` 已完成 Apple 公证、Cloud 发布和 GitHub/ModelScope 三源激活；`ai2apps/model-ornith15-35b-a3b-4bit-vision 0.1.5` 随后发布，Runtime 下限为 `>=1.8.1,<2.0.0`。其余模型 Package 复用公共 Runtime 修复，无需仅为依赖重锁而升版。正式收据见 `docs/ai2apps-mlx-runtime-1.8.1-boost-release.md`，未完成的真实模型门禁保留在 `docs/ai2apps-mlx-runtime-1.8.1-boost-release-handoff.md`。
- 按钮通过 `aria-pressed` 和 On/Off 文案明确当前状态；键盘 Enter/Space 复用原生 button click。Rush 在当前 Chat 会话内跨轮保持，切出窗口、页面隐藏或本轮生成结束不会意外关闭；切换 Chat 时各会话保留各自的内存态，切换模型或新建 Chat 时安全回到 Off，App 重启后也默认 Off。
- Engine Boost 设置在 Rush 开启时继续禁用并提示先关闭 Rush。英文、简中、繁中、西语、韩语、葡语、法语、俄语和日语提示已同步为开关语义。
- 验证：最初的开关 UI 变更完成 Chat 产品契约、Shell 结构和 UI overhaul 定向回归 162 项；随后生产链修复的 MoE 矩阵 85 项通过，覆盖 DeepSeek V4/V4.1、Qwen3.6 文本/VLM（含 Ornith 1.5）、Qwen3.8 Flash Next 与 GLM 5.3。Engine Pool/Worker 154 项、Package/Provider/Adapter/资源兼容套件 131 项、最终收口套件 52 项分别通过；套件间有重叠。Runtime 1.8.1 正式制品的公证、staple、Gatekeeper、三源、匿名回读和隔离安装通过；DeepSeek V4.1 与 Ornith Worker 均在各自隔离根目录中锁定该 Runtime 并启动。DeepSeek V4.1 源码阶段同检查点对照的 Blast 回执为 `protected_top=2`、`omitted_tail_routes=220`、`executed_routes=500`，Natural 为 `protected_top=6`、`omitted_tail_routes=0`。最终签名 Runtime 的六后端真实 Natural/Blast 推理与现有 Dev/Test 全量依赖锁迁移尚未验收，不宣称已完成。

### NXR-MODEL-PACKAGE-CONTEXT-WINDOW-20260928：对话 Package 缺省上下文统一为 32K

- 状态：`runtime_released`。Runtime 1.8.0 已完成 Developer ID 签名、Apple 公证、隔离安装、Cloud 发布及 GitHub/ModelScope 三源激活；submission `0492a1f9-bfc7-436c-8364-a62cf95a2925`，最终 Repository metadata 211、Snapshot `8bd0639ff4dbb91604e404b47b15d93d2f790ddf5b7643801acb9fa6b6ea86a2`。Desktop/Host 的 Package 归一化与展示部分仍待下一版 Desktop 纳入。`llm`、`vlm` Package 的 `context_window` 显式声明优先；既有 Package 未声明时统一按 32768 token 归一化，非对话模型不错误填入上下文窗口。
- Host 在验证 Package 时归一化有效窗口，隔离 Worker 从签名模型声明读取该值。Chat Completions/Responses 的流式与非流式路径均把有效窗口传入引擎；通用文本、VLM 与 DeepSeek V4.1 专用引擎都按实际 Prompt token 数裁剪输出上限。因此旧 Package 无需升级。
- DeepSeek V4.1 专用引擎默认值由 4096 对齐为 32768；全部对话引擎抵达窗口边界时正常返回 `finish_reason=length`，不再多执行一次 Decode 后暴露 `batch/context limit`。语音 tokenizer、标点恢复器等非对话辅助 LLM 不套用 32K 对话默认值。
- 模型 Package 手册已明确：新建或升级的对话 Package 必须按公开模型卡/正式配置声明，同时不得超过 Adapter、Runtime 与执行后端实际验证的能力；旧 Package 走 32K 兼容默认值。
- 验证：逐项读取全部已签入 Package 的 Worker manifest，覆盖 DeepSeek V4/V4.1、GLM-5.3、Ornith 1.5、Qwen3.6、Qwen3.8 Flash Next、Qwen3.8 27B、Qwen3.5 与 CUDA Qwen；Model Provider、四种 oMLX API 路径、通用文本/VLM 引擎上下文裁剪、DeepSeek V4.1 流式边界及 Cache-MoE Worker 定向回归已在正式 CPython 3.11 / MLX ABI 下扩展为 115 项通过。正式 DMG 的深层签名、staple、Gatekeeper、CPython 3.11.10、MLX 0.32.0 与 Direct-L1 原生符号通过；精确签名 Package 隔离安装后 DeepSeek V4.1 Worker 为 `running`，依赖锁精确指向 Runtime 1.8.0。Cloud/GitHub/ModelScope 完整摘要、46-piece manifest、两类 Range 兼容与匿名回读通过。当前验证的是配置与执行合同，没有逐个下载并运行全部 checkpoint。发布收据见 `docs/ai2apps-mlx-runtime-1.8.0-context-window-release.md`。
- App-Dev 实机：2026-09-28 通过固定脚本重建 `AI2Apps-app-dev.app`，严格深层签名、`com.ai2apps.desktop.appdev` 与 `app-dev` 身份检查通过；嵌入 Runtime 对未声明窗口的 DeepSeek V4.1 在通用 Adapter、专用 Engine 与请求参数三处均求值得到 32768。重启后的本地 DeepSeek V4.1 在 Thinking Off 下对短请求真实返回 `OK`，旧会话中的 `Error: batch/context limit` 仅作为历史失败消息保留。

### NXR-ACPF-PACKAGE-LIFECYCLE-20260928：全部 ACPF 统一识别过时模型

- 状态：`implemented`，待下一版 Desktop 纳入。共享 Registry 客户端通过独立无 Cookie 公共 Cloud 通道接入 `/v1/registry/package-lifecycle/latest` 完整签名快照，不携带当前用户或管理员会话；复用固定 Repository Ed25519 信任根，校验 schema/domain/字段/签名/有效期/重复记录，独立持久化 lifecycle 版本、payload digest、ETag 与验证缓存；拒绝回滚和同版本不同 payload。
- 所有 ACPF Planner 按 provider Package 统一关联 lifecycle。`deprecated` profile 退出自动推荐和自动选择，正常候选耗尽时改选下一项 active 兼容 profile；过时项仍允许明确选择并保留已安装/离线工作流。Discover 由 Registry Package 动态生成的模型安装计划与持久化安装会话也走同一规则，不存在旁路。
- 共享 Choice Sheet 将过时项稳定移动到全部正常项之后，以虚线弱化样式显示“已过时”徽标和 Cloud reason；已安装过时模型同时显示“已安装 · 已过时”，不伪装成推荐项。
- 状态接口或可信缓存不可用时降级为 unknown，不把未知宣称为 active，也不阻断现有能力。该行为写入 ACPF 唯一规范，不在 Chat 等 App 中复制特例。
- 生产公共快照只读联调确认 lifecycle v2 当前将 `ai2apps/model-qwen36-35b` 标为 deprecated，reason“已有更强的新模型”，replacement 为 `ai2apps/model-ornith15-35b-a3b-4bit-vision`；返回 keyId 与 Desktop 固定 Repository 指纹一致。未调用管理 API 或修改 Cloud 状态。
- 验证：Cloud Client、Registry、Provisioning 与动态 Discover ACPF 联合回归 135 项通过；Ruff、共享 Choice Sheet JavaScript 语法、英文/简中文案 JSON 和 `git diff --check` 通过。App-Dev 仍需重启 Local 后进行页面实机验收，无需重建 App。

### NXR-CHAT-ACPF-STRONG-MODEL-RECOMMENDATIONS-20260928：按新一代模型重排本地聊天推荐

- 状态：`implemented`，待下一版 Desktop 纳入。Chat 本地模型 ACPF 不再把旧 DeepSeek V4/V4 2-bit 作为 32/64/128 GiB 默认推荐；两者继续作为兼容选项列出。
- 推荐分档调整为：8–15 GiB Qwen3.5 2B、16–31 GiB Qwen3.6 35B、32–63 GiB Qwen3.8 27B NVFP4、64–95 GiB Qwen3.8 Flash Next 4-bit、96 GiB 及以上 DeepSeek V4.1 Flash。列表优先级同步按 DeepSeek V4.1、Qwen3.8 Next、Qwen3.8 27B 排在旧模型之前。
- ACPF 的 Qwen3.8 27B/Next 最低内存由过时的 24/48 GiB 对齐各自 Package `modelProfile` 的 32/64 GiB；最低 Runtime 对齐到 1.7.5。DeepSeek V4.1 推荐要求 Runtime 1.7.13，以包含长 Decode Metal 资源生命周期修复。
- 补齐 8–15 GiB 推荐空洞，并更新 Chat ACPF 分档回归；未安装、升级或发布任何模型、Runtime 或 Desktop 制品。

### NXR-DSV41-LONG-DECODE-RESOURCE-LIFETIME-20260928：长 Decode Metal 资源有界化

- 状态：`runtime_released`。Runtime 1.7.13 已完成 Developer ID 签名、Apple 公证、Cloud 发布及 GitHub/ModelScope 三源激活；submission `480c75c6-a842-4b7a-a09c-864388bd123a`，最终 Repository metadata 208、Snapshot `5d5039fb63ff3e7de23e5676ea5828ff1f2fef0d4cab43de78f8a061c66bc8c6`。Desktop 的 Chat 流失败 UI 防御仍待下一版 Desktop 纳入。DeepSeek V4.1 的 resident bank 原先跨 token 保留每层专家输出，只有 SSD reload 才 fence/清空；连续命中会按层×token 累积 MLX lazy graph，最终触发 Metal 499000 resource limit。现于既有 logits materialization 边界同时 materialize cache counters/ages，并清除已完成输出引用，不新增 GPU→CPU 同步或 router readback。
- Model Worker 仅在完整消费流后标记成功；流内异常记录 request/operation/model 上下文、标记 failed、写日志并发送结构化 SSE error，取消标记 cancelled。Chat 明确要求 `[DONE]`，错误帧或异常 EOF 保存为 failed 并保留 partial answer/reasoning；用户停止保存为 cancelled。DeepSeek V4.1 达到 max_tokens 的最终 chunk 现在报告 `finish_reason=length`。
- 其它 Cached-MoE 路径源码审计未发现同构引用链：DeepSeek V4 每次 forward materialize cache arrays；GLM 预填充 pending 为固定双 bank 并逐组 drain，promotion 仅保存有界专家 ID；Qwen Next/Qwen3.6 的 promotion/Scope collector 均为按层或单次 probe 有界状态。该结论不等同于所有模型完成 32K 真机压力测试。
- 验证完成：真实 475GB 共享 SSD checkpoint 的 12K 强制 Decode 通过，Decode 1,157.792 秒（资源回归 10.365 TPS），Metal active 仅增 3,100,812 bytes，pending 始终为0；480,000层次中89.788% all-hit，49,017层为非 all-hit，后续第二短请求完成。Runtime/DeepSeek V4.1/Worker/Package 合计 149 passed。逐点数据 `artifacts/dsv41-long-decode-resource-20260928/report.json`；修复报告 `docs/dsv41f-long-decode-resource-lifetime-fix-2026-09-28.md`；发布收据 `docs/ai2apps-mlx-runtime-1.7.13-deepseek-v41-long-decode-release.md`。Runtime 已发布；仍需要包含 Chat 防御的 Desktop Release，checkpoint 不变。

### NXR-CHAT-COMPOSER-MODE-BAR-20260927：明确区分模式栏与消息输入区

- 状态：`implemented`，待下一版 Desktop 纳入。
- Chat 输入组件顶部的 Chat/Agent 模式栏增加独立弱底色与下边界，避免模式说明及其右侧空白继续呈现为输入区域。
- 点击模式说明或模式栏非控件空白处会直接聚焦真正的消息输入框；模式按钮、Agent 选择及其他交互控件保持原行为。
- 仅修改 `ai2apps/web/templates/chat.html` 的静态样式与前端焦点交互；App-Dev 刷新即可加载，无需重建 App。
- 验证：Chat UI 与 Shell 定向回归 155 passed；App-Dev 热刷新后视觉检查确认模式栏形成独立工具栏。Computer Use 的坐标点击受窗口绑定错误影响，空白区域焦点仍需补一次人工点击验收。

### NXR-RELEASE-011-2253-20260926：全量产品候选核对

- 进展：正式 0.1.1 / 2253 已由 clean、已推送 main `ecb64006311317d65f7794148d9a209a6989a82a` 构建，Developer ID、Apple Accepted/staple/Gatekeeper 与 2252→2253 资格检查通过。GitHub `v0.1.1-build2253` 与 ModelScope immutable revision `b18618ac138fef2c5e0ef30d9f9d2e614d2c2626` 均已发布，同字节制品完成匿名完整摘要及 Range 验证。Cloud 已部署严格限定的 ModelScope `200 + Content-Range` 预检兼容修复，并于 2026-09-26 完成 0% 原子登记及同一 `build2253-test` rollout 扩至 10000 basis points；最终生产清单 SHA-256 `9c6438fe1802d3d4581cb7441f14fd259033a7e6c57256cb7636de14c8970cff`，审计新增 publish/rollout 两条。当前仅待目标 Mac 实际升级与启动验收；完成前不更新基线或将 NXR 标 included。见 `docs/ai2apps-desktop-build-2253-release-receipt-2026-09-26.md`。
- 2026-09-26 用户进一步确认原生托盘/启动页双语、中文登录流程均已现场验收通过；NXR-NATIVE-I18N-20260926 与 NXR-LOGIN-I18N-20260926 的历史现场待办关闭，纳入候选。验收来源为用户，不重复操作实例或改写既有测试证据。
- 全量复验完成：10231 passed、67 skipped、74 deselected（727.61 秒），无失败。日志及 JUnit 见发布准备文档。产品唯一版本源 `ai2apps/_version.py` 升至 0.1.1；Build 2253 由标准构建参数指定，不修改独立 Runtime/Package 版本。正式 App/DMG 已构建、签名、公证并完成双源发布；Cloud 与真实升级仍待完成。

- 2026-09-26 用户明确确认修改密码和 Imagine 新功能均已由其验证，无需 Agent 重复验收；对应真实改密/图片生成 UI 缺口按用户验收关闭，纳入本轮候选，源码回归及制品门禁仍须通过。此确认不代表 Agent 执行了真实密码操作或模型生成。

- 状态：`in_progress`。版本 0.1.1 / Build 2253 已完成源码、构建、公证、GitHub/ModelScope 双源和 Cloud 100% 发布；当前只剩目标 Mac 实际升级与启动闭环，完成前不改为 `included`。
- 当前生产清单为 0.1.0 / Build 2252；本文下方 2249 基线段为未归档的历史记录，不作为本轮版本分配依据。全部开放项仍须逐项核对，不能据此把旧 in_progress 自动改为 ready。
- 首轮源码验证：Swift 测试与 16 个 Node 测试文件通过；Python 定向回归 365 passed / 1 failed，发现共享 Studio setup 测试仍固定旧二参数签名。已更新为现行可选 installMore 参数并保留参数传递断言，待复验；完整 Python 回归进行中。
- 发布前发现正式 packaged AceFox 的 shell.mjs、shell.xhtml 与当前源码不一致；必须通过正式浏览器打包流程刷新，不能用 Development overlay 替代。密码修改及 Imagine 人工验收已按上方用户确认关闭，不声称 Agent 重复执行。
- 首轮全量 Python 为 10227 passed、4 failed、67 skipped、74 deselected；补齐 34 条 ACPF 中英文文案，并更新 Runtime 1.7.12、双语重置菜单及 Studio 客户端过期测试合同。124 项定向复验通过，全量复验仍在运行。翻译修复纳入本候选，回退可恢复对应键；不改变模型选择或权限逻辑。
- 个人参考音频 assets/voice-1.wav 不纳入提交或发布。尚未更改生产清单、用户实例数据或任何 Cloud 状态。
- 复验：更新旧接口与资源版本断言后，366 项定向 Python、16 个 Node 文件通过；额外行为测试确认 installMore 默认 false/显式 true 正确传递。Swift 为 77 项 Swift Testing 加 2 项 XCTest 通过。全量 Python 尚在运行；准备记录见 `docs/ai2apps-desktop-0.1.1-release-preparation-2026-09-26.md`，不是发布回执。

### NXR-NATIVE-I18N-20260926：启动页与托盘菜单中英文

- 状态：`ready`，2026-09-26 用户确认原生双语现场验收通过。固定 App-Dev 已重建并启动。NativeUILanguage 优先读取实例 data/settings.json 的 ui.language，没有有效值时读取系统第一首选语言（中文映射 zh，其余 en）。
- Helper 菜单、运行状态、端口、更新、启动登录项、测试环境、退出/重置确认接入中英文，展开菜单时重读当前语言；AceFox shell.mjs/shell.xhtml 的启动/连接/重试/日志/错误及进度辅助标签接入相同规则。
- Development-only Shell overlay 同时纳入匹配的 shell.xhtml，避免旧启动页硬编码中文闪现；生产构建仍使用正式 AceFox 快照，不开放源码 overlay。
- AceFox 源码：`/Users/avdpropang/sdk/moz/acefox-firefox-153/browser/components/ai2apps/content/shell.mjs`、`shell.xhtml`，正式发布需纳入匹配浏览器快照。
- 验证：Swift NativeUILanguageTests 2 项通过（覆盖系统第一首选语言、简繁体、已保存语言和删除/损坏设置回退）；Shell Node VM 6 个语言场景、JS 语法、定向 diff 检查通过。英文下载状态和百分比解析同时兼容，避免切换语言后进度归零。
- 使用规定 build-app-dev-environment.sh 构建；verify-release-app.sh、codesign --verify --deep --strict、固定身份/Development/cloud Runtime/源码根/禁用生产更新 URL 合同及 omni.ja 内语言实现和匹配 XHTML 均通过。实机标题 `AI2Apps-App-Dev: App-Dev 127.0.0.1:49305`，Local ready，Helper 状态为“AI2Apps 服务运行正常”，中文 Shell 首页正常显示。保留实例数据。
- Computer Use 无法读取无窗口 Helper/SystemUIServer（超时）；托盘展开菜单及短暂启动等待页的双语视觉验收未完成，不以首页检查代替。未触发真实更新安装、重置或退出确认操作。

### NXR-LOGIN-I18N-20260926：账户登录流程中英文

- 状态：`ready`，2026-09-26 用户确认中文登录现场验收通过；下方待验收描述为历史记录。
- `ai2apps/web/templates/login.html` 与 `web/static/js/login.js` 原先硬编码英文；现在统一使用现有 t() 和安装级语言。覆盖标题、登录/注册、邮箱验证、Core 绑定、密码规则、加载状态及本地错误兜底；Cloud 返回的具体错误仍原样显示。
- `web/i18n/en.json`、`zh.json` 新增 25 个 login.account 翻译键。中英文模板实际渲染、键完整性、JS 语法、Node VM 中英文已绑定/未绑定/注册切换/密码校验行为以及 diff check 通过。
- 无 Cloud 或鉴权行为变更。当前进程已缓存 locale，需 Helper 重启 Local；Computer Use 读取 Helper 两次超时，未清空数据或代替用户登录。

### NXR-SHELL-SYSTEM-LANGUAGE-20260926：首次启动按系统语言初始化

- 状态：`implemented`。固定 App-Dev 已于 2026-09-26 通过规定脚本重建并启动，旧包已归档，保留实例数据。
- `omlx/settings.py` 的 UI 默认值读取 macOS `AppleLanguages` 第一首选语言，中文地区/简繁体统一映射 `zh`，其余映射 `en`；读取失败时按 LC_ALL、LC_MESSAGES、LANG 和 locale 回退。GUI 启动不依赖终端 LANG。
- 首次启动、缺少 ui.language 或重置删除 settings.json 后应用系统默认；已有持久化语言优先，用户手动选择不被启动覆盖。Shell、App catalog 与原生 Shell locale API 复用同一设置。
- 新增 `tests/test_ui_system_language.py`，覆盖 macOS 首选顺序、地区标签、环境回退、读取超时、首次启动、保存英文与数据重置。与 `tests/test_settings.py` 合计 226 项测试通过；本机系统首选 zh-Hans-CN 实测得到 zh。
- 本次涉及嵌入 omlx，固定 App-Dev 需通过 `build-app-dev-environment.sh` 重建后验收；未删除用户数据或发布 Desktop。
- 重建验收：内嵌 settings.py 与源码逐字节一致；verify-release-app.sh、codesign --verify --deep --strict 通过；bundle ID、app-dev、Development、cloud Runtime、源码根合同与无生产更新 URL 已核对。实际原生窗口标题为 `AI2Apps-App-Dev: M5Max-128G 127.0.0.1:65268`。
- 用户此前用旧包重置后已持久化 ui.language=en，因此当前登录页仍按保存值显示英文；未擅自删除数据或覆盖该设置。内嵌 Runtime 使用临时全新设置目录验证系统中文默认，真实实例再次重置的 UI 验收尚未执行。

### NXR-SHELL-DOCK-ORDER-20260926：默认 Dock 按使用场景排序

- 状态：`implemented`，待下一版 Desktop 纳入。
- 默认顺序：聊天 → 创意画坊 → 语音工坊 → 视频工坊 → 图库 → 发现 → AI 浏览器 → 知识库 → 编程。
- 文件：`ai2apps/web/static/js/shell.js`。Dock 默认顺序独立于 catalog 排序和本地化名称；仅对没有有效已保存顺序的配置应用，保留已有用户排序，未固定且未运行的 App 不会因此加入 Dock。
- 验证：Node JavaScript 语法检查、定向 diff 检查通过；Node VM 验证默认顺序、损坏存储回退、自定义顺序保留、不可用 App 过滤与已保存空顺序保留。
- 仅静态前端变更，App-Dev 刷新 Shell 即可加载；未重建或发布 Desktop，未执行实机 UI 验收。

### NXR-ACCOUNT-PASSWORD-20260925：安全页修改密码

- 状态：`ready`。Cloud 已部署 OpenAPI 1.52.0；2026-09-26 用户确认已完成修改密码验收，下方待验收记录保留为历史。Agent 不重复操作密码；正式候选制品门禁另行执行。
- Account 安全页增加旧密码、新密码、确认新密码；手动提交，8–128 UTF-8 字节和一致性
  校验；成功重新登录，离开页面/账户切换及提交结束清空密码字段。九种语言文案齐全。
- Local 新增 `/v1/platform/cloud/auth/password/change`，转发当前浏览器 Cloud 会话，
  成功清理会话缓存，失败不清理；Cloud 404/405 提示功能尚未上线。
- 文件：`ai2apps/api/cloud.py`、`ai2apps/web/static/js/account.js`、
  `ai2apps/web/templates/system_apps/account.html`、`ai2apps/web/i18n/*.json`。
- Cloud 交接：`docs/ai2apps-cloud-change-password-requirements.md`。未修改 Cloud 代码。
- 验证：密码修改接口及密码规则 23 tests passed；Node 前端 8 个行为场景通过；
  九种语言 JSON/键完整性、JavaScript 语法与定向 diff 检查通过。
  测试：`tests/test_ai2apps_password_change.py`、`tests/test_account_password_change.cjs`。
  Cloud 合同与生产发布回执已核对：字段、错误码、成功后会话撤销及设备绑定保留均兼容。
  2026-09-25 用户通过 Helper 重启后，固定 App-Dev 端口为 57023；只读检查
  health=healthy，OpenAPI 已注册 `/v1/platform/cloud/auth/password/change`。
  Computer Use 实机确认 Account → Security 的 Change password 标题、说明、Current password、
  New password、Confirm new password、8–128 UTF-8 字节提示、提交与取消按钮均正常显示；
  已截图检查表单布局，旧翻译 key 缓存问题消失。
  当前登录的是真实管理员账号，未输入或提交密码；实际改密 E2E 仍待用户在专用测试账号
  亲自输入和提交后，复核重新登录及错误状态。未将界面检查冒充真实改密验收。
  Cloud 证据：`/Users/avdpropang/sdk/ai2apps-cloud/docs/change-password-v1.md`、
  `/Users/avdpropang/sdk/ai2apps-cloud/docs/change-password-production-2026-09-25.md`。
- 纳入 Build：待定。


### NXR-OMLX-RUNTIME-1712-DSV4-2BIT-PREFILL-20260925：DeepSeek V4 2-bit Direct Prefill 安全回退

- 状态：`released`。Runtime 1.7.12 统一 Direct Prefill 标记的生产与消费条件；带量化 biases 的九段 2-bit DQ store 使用异步 Legacy Prefill，陈旧 Direct 标记经 layer/expert IDs 校验后同步安全回退。模型代码、checkpoint 与 distribution 无需改动；现有模型 Package 0.3.5 的 `>=1.7.5` 依赖不会把已装 1.7.11 的实例自动升级到 1.7.12。自动 ACPF 修复需要另发提高最低 Runtime 版本的模型 Package。
- 181 项 Direct-L1、DeepSeek Prefill/patch/Scope、Worker、adapter 与 Runtime contract 回归通过；Ruff、compileall 和 diff 检查通过。
- 使用 Runtime 1.7.11 正式 CPython 3.11/MLX/已签名原生扩展的临时克隆完成真实 2-bit DQ A/B：`hi` 与 `20+20=?` 均非空，数学输出包含 40；Direct Prefill 开/关的 48-token SHA-256 完全一致，开启路径 40 次异步 Legacy 预取命中、0 次 Direct load，峰值 31.45 GiB。
- Runtime 1.7.12 Developer ID 内部 DMG 已构建；384,542,702 bytes，SHA-256 `aade49e5e185980a33255c81861b1e4d24aea279be2f1da315432fd30c0bbc5e`。深层签名、嵌入修复文件字节、版本 1.7.12、CPython 3.11 与原生 Direct-L1 符号通过；直接从只读挂载候选运行 2-bit `hi` 通过。
- Apple 公证 `c5c26f26-b75d-4bde-ba18-818692b16cb8` Accepted，staple/Gatekeeper、原 Publisher 指纹、正式 Package 隔离安装和 managed Worker 就绪均通过。Package 381892948 bytes，SHA-256 `1ad9dafbf39fca32ed6c1625a91cc6bd38ff06f562bf01cff514443fce89df87`。
- Cloud submission `56e0d3c1-d751-4367-aa70-9f3dfb1f18e7` 已发布；GitHub 206 与 ModelScope 严格 `200 + Content-Range` 均通过匿名完整字节、49 次 Range 和 46-piece 校验并激活。最终 Repository metadata 202、Source revision 6、Snapshot `fd4504d911fec1fca13e3591c362af9c5da162fc4ce35cadf64a0bcf0adb2cf4`。全新匿名缓存验证 Package 与 envelope 精确一致。发布收据：`docs/ai2apps-mlx-runtime-1.7.12-deepseek-2bit-prefill-release.md`。
- 当前 Test 的 4-bit SSD checkpoint 是 `scales, weight` 旧布局，不能执行 canonical `weight, scales` Direct Prefill 实测；六段 Direct 路径由单测保持。App-Dev/Test 安装正式制品后的 UI 复验仍属于实例升级，不阻塞已完成的 Runtime 发布。

### NXR-APPDEV-TEST-CENTER-20260925：Helper 测试环境入口

- 追加修复：实际完整服务返回 `local_session_required` 401，原因为外层 `verify_ai2apps_platform_access` 未将新入口交给 Helper 原生认证。现只为准确 POST 路径补入口，接口内凭据、Origin、app-dev/Development 校验保持不变。新增真实 guard + Client router 联合回归，覆盖合法请求、无凭据和浏览器 Origin；Helper 显示 HTTP 状态且跳过非 JSON 标准输出。相关回归 21 passed；Harness 80 passed/1 skipped。标准脚本已重建、verify-release-app 与 codesign 深度校验通过；旧 App 归档 `AI2Apps-app-dev-20260925-013408.app`，已重新启动，菜单点击验收待用户复核。

- 状态：`in_progress`。仅固定 App-Dev 开发构建显示启动／停止测试环境，启动源码 Harness，并通过受 Helper 认证的 Local 原生浏览器窗口队列打开 Test Center。
- Test/Dev/Release 不显示入口；Local 接口同时检查 app-dev 与 Development 标记。测试工具不继承 App-Dev 的 AI2APPS 身份环境变量。停止使用 SIGINT 请求 Harness 取消并等待运行收尾。
- 复用固定 Test Center 浏览器容器；Shell 源码 overlay 支持该窗口重新启动测试工具后打开新地址。Swift Helper 编译通过；Harness 80 passed/1 skipped；Local 入口和既有 browser-agent 回归 7 passed；控制台宿主启动与 SIGINT 退出验证通过（未运行 Case）。
- 已通过标准脚本重建固定 App-Dev，旧 App 归档为 `AI2Apps-app-dev-20260925-010021.app`，verify-release-app 与 codesign 深度校验通过。实机 Shell 标题 `AI2Apps-App-Dev: App-Dev 127.0.0.1:49625`；Computer Use 连接 Helper 两次超时，菜单点击到浏览器页面的端到端验收仍待完成。未修改其他实例或重置数据。

状态：滚动维护中的唯一下一版入口

### NXR-VIDEO-COMPOSER-SPECIAL-LAYERS-20260929

- 状态：`implemented`，固定 App-Dev 已完成前端实机检查和导出 API 实机复验。首次导出返回 422 的原因是长驻 Local 仍持有升级前的 Pydantic 请求模型；通过固定 App-Dev Helper 的 `local.restart` 控制通道重启后，新请求模型已加载，当前 4 轨道／3 Clip 项目成功渲染 5 秒 MP4，预览与下载均可用。
- Video Composer 新增可排序、可保存和可导出的聚光遮罩层与文本层。聚光遮罩支持圆角矩形／椭圆、高亮区外暗度、圆角和向内羽化，既有位置和尺寸关键帧控制高亮区域。向内羽化保持高亮区外的暗度不变，仅在边界内侧由暗向透明渐变；快速预览使用硬外部阴影加内嵌渐变，Pillow 导出使用硬形状与内缩模糊形状相乘，两者方向一致。文本层支持内容、字号、颜色、九点锚点、逐字读出及字符速度，新增关键帧缩放参数。
- 特殊层不依赖媒体素材源；Python 合成器按视频轨顺序将遮罩和文本合成进最终 MP4，项目打开／保存和纯特殊层导出均保留其配置。旧媒体片段在前端规范化时自动补 `layerType=media` 和 `scale=1`。
- 文件：`ai2apps/video/composer.py`、`ai2apps/api/video_studio.py`、`ai2apps/web/static/js/video_studio.js`、`ai2apps/web/templates/system_apps/video_studio.html`、`ai2apps/web/static/css/video_composer.css`、中英文 locale 与 Composer 回归测试。
- 验证：Composer 定向回归 13 passed，覆盖无素材源特殊层、遮罩明暗像素、文本缩放关键帧与可播放 MP4；Ruff、Node 语法和 diff check 通过。固定 App-Dev 强制刷新后实际创建聚光遮罩层和文本层，轨道、预览边框、Inspector 的形状／暗度／羽化／圆角、文本内容／字号／颜色／锚点／读出和关键帧 Scale 控件均可见，布局未溢出。当前 Local 进程缓存旧 locale，新增标签暂显示 key；按 App-Dev 工作流需从 Helper 重启 Local 后再验中文标签及实时导出。未重建或发布 Desktop。
- 2026-10-01 向内羽化增量验证：Composer 回归增至 16 passed，新像素测试确认遮罩外侧暗度恒定、边缘内侧逐步恢复亮度；Node 语法、Ruff、双语 JSON 与 diff check 通过。
- 2026-10-01 预览羽化反馈增量：为选中的普通媒体 Clip 与聚光遮罩层增加跟随当前关键帧、形状、圆角和羽化像素宽度的半透明向内范围指示；媒体使用青色、聚光使用橙色，辅助层不进入导出。保留浏览器实时羽化近似，并以范围指示规避多重 CSS mask／透明 inset shadow 在不同浏览器中的不稳定表现。
- 2026-10-01 轨道入口增量：移除 Composer 顶部“聚光遮罩 / 文本”按钮，将轨道区原“+ 视频轨 / + 音轨”改为“+ 轨道 / + 项目”下拉菜单。轨道头和空白行可明确选中当前轨道；新轨道在当前轨道后插入并成为当前轨道。“+ 项目”仅在未锁定的视频轨可用，聚光遮罩和文本直接插入当前轨道并继续执行同轨不重叠/后移规则，音频轨或锁定轨上禁用。Composer 16 项回归、JavaScript、双语 JSON 与 diff check 通过；固定 Dev Local 重启至 `56626`，实机确认顶部旧按钮消失、两个菜单的中文选项完整，并确认选择音轨后“+ 项目”变为禁用。
- 2026-10-01 轨道右键插入增量：“+ 轨道”左键继续直接选择视频轨/音轨并默认插在当前轨道之后；右键改为两级菜单，先选择“在当前轨道前/后”，再选择轨道类型，插入完成后新轨道成为当前轨道。补充前后插入索引、右键入口、两级状态及中英文文案回归覆盖；Composer 17 项回归、JavaScript、双语 JSON 与 diff check 通过，固定 Dev Local 重启至 `50636`，实机辅助功能树确认右键第一级菜单正确显示“在当前轨道前 / 在当前轨道后”。
- 2026-10-01 相邻片段空帧修复：导出渲染不再用经过 9 位小数舍入的浮点秒区间判断 Clip 是否命中，统一以项目 FPS 换算出的整数起始帧/持续帧选择片段，并以局部帧计算源时间和文字读出时间，消除相邻片段边界处两边都未命中的纳秒级缝隙。预览改用同一套整数帧命中规则，并提前一秒挂载、定位即将播放的相邻媒体，避免切片边界临时创建 `<video>` 带来的偶发首帧闪黑。新增 30fps 非零起点相邻片段的逐帧渲染回归，明确验证 F32 为第二段首帧而不是背景空帧；Composer 回归增至 18 passed，JavaScript、Ruff 与 diff check 通过，固定 Dev Local 已重启至 `53916`。

### NXR-APPDEV-SCREEN-RECORDING-WINDOW-20260929

- 状态：`implemented_and_verified`。App-Dev 专用 Helper 菜单增加“准备录屏 / Prepare for
  Screen Recording”；入口只在 `app-dev` instance、`com.ai2apps.desktop.appdev` 主包和
  Development source-root 三重身份校验通过时出现，不触碰 Dev、Test 或生产实例。点击后
  唤起 App-Dev Shell；Shell 已运行时立即处理，尚未运行时会在启动后消费命令。
- Helper 只向实例私有 `run` 目录写入固定、不可自定义几何的 0600 命令；App-Dev Shell
  校验版本、实例 ID 与命令后自行调用原生窗口接口，按当前屏幕倍率把主窗口设为
  1600×900、移动到主屏幕可用区域左上角、激活窗口，并立即删除命令。该路径不需要辅助
  功能权限，也不允许控制其他进程。App-Dev 专用 Shell 变换由仓库内脚本在构建时注入，
  不修改或依赖外部未跟踪的 AceFox 源文件。
- 验证：Swift 构建及 79 项测试、Shell 变换与 JavaScript 语法、两次完整固定 App-Dev
  重建、`verify-release-app.sh`、严格深层签名均通过。最终旧包归档为
  `.build/archive/AI2Apps-app-dev-20260929-042026.app`；新实例标题为
  `AI2Apps-App-Dev: App-Dev 127.0.0.1:53100`，健康端点返回 `healthy`。实机先将窗口改为
  1000×650 @ (120,120)，再点击菜单，首版系统读数为 1360×768 @ (0,34)；`y=34` 是当前
  macOS 菜单栏下方的可用屏幕顶边。用户现场确认该尺寸在 1728×1083 工作区内视觉偏小，
  因此目标调整为 1600×900；固定 App-Dev 再次重建，旧包归档为
  `.build/archive/AI2Apps-app-dev-20260929-043352.app`。最终实机点击后的系统读数为
  1600×900 @ (0,34)，新实例端口为 54062。一次性命令已消费，Dev Helper 菜单确认没有该入口。

### NXR-LOCAL-FOUR-INSTANCE-REBUILD-20260928

- 状态：`ready`。用户要求重建固定 app-dev、dev、test 和 main 四个本地实例，四项均完成。
  本次为当前工作树内部集成快照，不是正式候选，不发布、不公证、不改变生产基线或更新通道。
  保留各实例数据与共享权重；固定旧 App 归档。包含 Models SSD 激活状态修复。
  既有台账的未完成/延期工作不因本机构建而视为完成或获准发布。
- 验证：app-dev/test/main 均通过 verify-release-app.sh 与构建中的 deep strict 验签；
  dev 通过 deep strict 验签。三套内嵌 Runtime 确认包含 SSD installed 修复。
  App-Dev 现场窗口为 `AI2Apps-App-Dev: App-Dev 127.0.0.1:63105`，Models 卡片为 Ready，
  Configure 显示 `Model installation complete`，不再出现 Download & Prepare。
  旧包归档时间：app-dev 082257、test 082407、dev 082411、main 082518（20260928）。
  main 保留本地 Build 2250，内部 ad-hoc 签名，未公证发布；test/main 原先未运行，未主动启动。

### NXR-MODELS-SSD-INSTALLED-20260928：Models 页面读取 SSD 激活状态

- 状态：`ready`。上次修复只覆盖 Checkpoint 完整性；Model Manager 的非 native
  分支仍只查 model_dir/repo_id，遗漏 Worker Hub distribution。Package recipe 现在从
  已验证 Worker 路径检查激活描述文件的 model ID、repo、revision，再提供 installed。
  Admin 聚合保留该状态，旧转换目录仍保留兼容检测。现有配置弹窗会自动切换完成面板。
- 涉及 `omlx/admin/routes.py`，App-Dev 必须通过固定构建脚本更新内嵌快照；仅重启
  Local 不足。四实例已重建，App-Dev 已现场确认 Ready 与安装完成面板；71 项定向测试通过。

### NXR-WORKER-CHECKPOINT-SIDECARS-20260928：已激活 SSD Checkpoint 复用

- 状态：`ready`。Worker 完整性判断与缓存视图复用允许严格限定的本地激活元数据：
  v2 ai2apps-cache-moe-model 描述文件、按 SHA-256 命名且内容匹配的 Scope JSON。
  拒绝符号链接、异常 JSON、额外权重和缺失签名文件；共享签名缓存仍要求精确文件清单。
- 修复 DeepSeek V4.1 已下载后被误报 Weights required，重试又报 Registry 冲突。
  不删除、搬移或重新下载权重；Python 修改需要重启 App-Dev Local。
- 验证：checkpoint acquisition 22 项通过；现有 App-Dev DeepSeek V4.1 的 171 文件
  验证收据在修正后的完整性判断中通过，未修改缓存。未重启当前 Local。

### NXR-IMAGINE-MINI-APP-ORDER-20260924：内置列表排序

- 按用户指定顺序展示：Text to Image、Image Edit、Adjust Image、Change Image Style、Reference Creation、Sticker Workshop、Group Photo、Product Photo Studio；规划中的角色设计、漫画分镜放在最后。
- 仅调整前端定义顺序，不变更 ID、草稿、历史或 API；刷新页面生效，无需重启 Local。新增完整列表顺序回归断言。

### NXR-IMAGINE-PRODUCT-STUDIO-20260924：商品摄影棚首版

- 状态：`ready`。2026-09-26 用户确认 Imagine 新功能已验收，关闭下方历史人工验收待办，不重复付费生成。将原 Planned `ai2apps.imagine.product-poster` 升为内置 1.0.0 商品摄影棚，沿用原 ID。单商品参考图、六种场景（含自定义）、三种灯光、居中/左右留白，草稿和 Run 输入保存设置；复用 image_edit 模型筛选、OpenAI 优先和宿主 Run/Artifact/Gallery 输出。
- 共享风格默认不应用；显式开启后仅作用于布景。提示词约束原商品角度、Logo、标签、结构和颜色，但 UI/帮助明确首版为模型重绘，不承诺蒙版原图合成或像素级保真。无自动广告文案、价格、上架操作。
- 验证：商品摄影棚 Node 行为测试通过（缺图、自定义场景必填、预设无提示词运行条件、风格默认隔离、构图提示词、草稿恢复及无效值回退），表情包 Node 回归通过，Imagine API 14 tests passed，JS 语法及 diff check 通过。
- App-Dev 61884 实机刷新后已检查入口、六个有名称的场景 toggle、Lighting/Composition 标签、风格开关默认关闭、自定义场景必填状态和截图布局。Local 仍为旧 Python 进程，Mini-App not found，待从 Helper 重启 Local 后进行真实生成与 Gallery 验收；未声称出图已验证。不需要重建 App，不涉及模型 Package 或 Runtime 发布。

### NXR-IMAGINE-STICKER-WORKSHOP-20260924：表情包工坊首版

- 状态：`ready`；2026-09-26 用户确认 Imagine 新功能已验收，关闭下方历史人工验收待办，不重复付费生成。新增内置 `ai2apps.imagine.sticker-workshop`，人物/宠物单参考图、开心/比心/震惊/委屈四种表情，共享 Style、编辑模型筛选、OpenAI 优先、Run/Artifact/Gallery 输出。
- 可单张生成，整组串行四次生成，Cloud 上传与逐张费用显式确认；失败或取消停止后续任务，支持完成当前张后停止。运行中冻结输入和 Mini-App 切换，保留已完成结果。表情选择写入草稿与 Run 输入，Run 标题标识表情；同一表情重新生成不会覆盖历史。
- 首版明确白底，不承诺透明 alpha；未加入文案排版、整组 ZIP、刷新后自动续队列。使用原照片为每张独立参考，不将上一张结果传给下一张。
- 验证：Node 行为测试通过（四表情、prompt、草稿字段、逐张成功、取消/停止、异常解锁、拒绝确认），Imagine API 14 tests passed。首次在 ai2apps 子目录运行 pytest 遇 stdlib secrets 遮蔽，已从仓库根目录正确重跑；退出时 sandbox Metal 探测警告与本次 UI/API 无关。
- App-Dev 原生 Shell 实机检查已确认入口、四个有名称的 toggle button、缺图禁用、表情选中状态、共享 Output 布局。当前 Local 仍加载旧 Python 注册，出现 Mini-App not found；Helper 控制两次超时，待用户从 app-dev Helper 重启 Local 后验证真实生成/刷新恢复。没有重建或终止任何其他实例；未声称真实出图完成。

### NXR-SEPARATION-ARTIFACT-OUTPUT-20260923：音轨输出与Shell另存为

- 状态：`ready`。Voice Studio分离结果持久化为当前用户Artifact：ZIP走宿主原生下载链接，分离WAV加入Preview & Output历史，刷新可恢复，不自动加入Gallery。
- Package通过已校验mount通道请求下载，仅允许本次Host返回的Artifact URL；历史按音轨/ZIP分别20项，保持角色和Line音频独立。
- 验证：40项相关pytest通过；Node测试覆盖Host签发下载链接、拒绝外部下载URL、Voice Studio既有作用域；新增用户隔离、刷新恢复、失败回滚和JSON接口协商回归。Python API需重启Local，前端刷新生效，无需Runtime升级。正式交付涉及Desktop Host与suite Package UI。

### NXR-DEMUCS-MULTIPART-BOOLEAN-20260923：Host音轨分离参数修复

- 状态：`ready`。Host显式发送float32_wav字符串false，Demucs要求bool；multipart文本不能保留JSON布尔类型。删除冗余字段，使用模型默认PCM16输出，避免错误。
- Runtime1.7.11长请求验收没有这个字段，未覆盖页面Host请求参数差异。本次17项Broker回归通过；修复后的实际Host Broker以3秒48kHz测试WAV调用正式Runtime1.7.11+Demucs0.1.0，HTTP200返回vocals.wav/instrumental.wav，ZIP校验通过。此修改只需重启App Dev Local，无需Runtime或模型Package升级。

### NXR-RUNTIME-1711-RELEASE-20260923：Runtime 1.7.11 发布

- 状态：`released`。Runtime 1.7.11完成公证、签名、Cloud发布、Cloud/GitHub/ModelScope三源激活和匿名验签；包含Worker长音频主输入1GiB修复，沿用1.7.10签名及JIT权限。
- 正式Package隔离安装，Demucs成功处理131424044字节/1369秒测试音频并返回校验通过的分离ZIP；70项回归通过。ModelScope通过`package-single-range-v2`严格`200 + Content-Range`完整验证，49次Range、完整SHA/size和46-piece manifest匹配；最终Repository metadata 199、Source revision 6。空缓存匿名客户端完成382394257字节三源下载及签名/字节验收约12.8秒。收据：`docs/ai2apps-mlx-runtime-1.7.11-long-audio-release.md`。

### NXR-WORKER-LONG-AUDIO-LIMIT-20260923：Worker长音频请求限制

- 状态：`released`（Runtime1.7.11；用户实例仍需升级）。S01E01约1368.677秒的48kHz单声道PCM WAV约125MiB，超过Worker独立100MiB上限；此前Host入口修复未覆盖此处。
- audio_process/audio_transcription/audio_detailed_transcription的主file上限提高至1GiB，参考音频及其他操作仍100MiB；保留WAV校验、1小时/声道/采样率限制和临时文件清理。
- 验证：Worker真实multipart到测试适配器的边界回归，覆盖三个长音频操作、超限和参考输入限制。
- 交付：已纳入正式Runtime1.7.11发布；模型Worker由已安装Inference Runtime的launcher加载，用户实例须升级到1.7.11，仅重启Local不能更新旧签名Runtime。

### NXR-MEDIA-DAMAGED-PACKET-20260923：视频音轨孤立坏包恢复

- 状态：`ready`。用户S01E01.mp4在411帧后触发AAC InvalidDataError；逐包检查确认整段只有1个坏包，其余58943帧可解码。
- Host音频规范化按包解码，跳过孤立InvalidDataError，依据重采样时间戳补静音保留后续时间线；连续32个坏包、无有效音频或超时长仍拒绝，解码结束/失败释放输入容器。
- 验证：真实用户视频音轨完整规范化，新增坏包后静音补齐/音频保留/资源释放回归，以及既有音频codec和Broker测试。仅验证解码，未运行整集Demucs推理。重启App Dev Local生效。

### NXR-STUDIO-MEDIA-UPLOAD-20260923：支持超过100 MiB的媒体输入

- 状态：`ready`。修复261.5 MB视频被Host旧MVP限制拒绝：主素材前端/API统一放宽到1 GiB，参考音频单独保留100 MiB；空文件及超限明确提示。
- API按块写入缓冲并在调用Broker前释放缓冲，避免保留分块列表与合并副本。依然使用既有媒体解析和模型调用路径。
- 验证：相关Broker/API回归及上传边界测试；真实长视频模型推理尚未验证。Python API需要重启App Dev Local，再刷新页面。

### NXR-MEDIA-SUITE-ACPF-BUTTONS-20260923：分离与角色换声安装配置入口

- 状态：`ready`。音轨分离、音频角色换声、视频角色换声的缺模型提示均增加安装并配置按钮，复用已校验 mount 的 Host ACPF 通道。
- 分离配置 Demucs；两个角色换声入口调用各自能力的组合配置，覆盖 Detailed Transcription、Demucs、Seed-VC v2。配置结束刷新状态，取消保留表单。
- 验证：Package/Host 相关 pytest 与 JS 语法检查，通道回归覆盖四个入口。App Dev 刷新页面生效；正式交付纳入 suite Package 发布。

### NXR-TRANSCRIPTION-ACPF-BUTTON-20260923：详细转写安装配置入口

- 状态：`ready`。Package 详细转写页面缺少模型时展示安装并配置按钮，通过 mount 绑定的 Host MessageChannel 调用现有 ACPF，选择 Compact/Quality；结束后刷新就绪状态，取消保留表单。
- Host 每次 setup 校验有效 mount 和已声明能力，仅返回完成状态，不向 Package 暴露会话凭据。按钮等待时禁用，失败允许重试。
- 验证：9 项相关 pytest 通过、两处 JS 语法通过，新增 Node 通道回归验证 ACPF 调用及未声明能力拒绝。
- 交付包含 Desktop Host JS 与 media-voice-studio-suite Package UI；App Dev 源码挂载刷新页面生效，正式版本须分别纳入 Desktop/Package 发布。

### NXR-CLONE-PREVIEW-MULTIPART-20260923：修复情绪试听400错误

- 状态：`ready`。日志确认 Characters 克隆试听 Worker HTTP400；新增style对象未展开为multipart标量。参照Audiobook路径，将style转换为emotion/emotion_strength后上传，JSON声音设计路径保留style。
- 错误响应保留Worker状态码与原因，前端同时读取标准error.message，避免仅提示通用失败。
- 验证：克隆情绪测试改为检查真实上传字段及无嵌套值，新增Worker错误透传回归；现有Design表达快照回归保留。重启Local后生效，不需要Runtime升级。

### NXR-CHARACTER-PREVIEW-EXPRESSION-20260923：角色试听情绪与速度

- 状态：`ready`。Characters Design与Reference Clone试听区增加情绪/速度控件；默认自然语气和1倍速，修改后旧试听失效。克隆试听设置随草稿保存，Design生成快照记录并恢复参数。
- 后端Design/Training请求接收emotion/speed，按模型能力传递style与速度，速度限制到模型声明范围；不支持情绪提示后使用自然语气，不支持速度禁用输入并使用模型默认。
- 验证：Design及克隆参数传递、模型不支持fallback、速度越界拒绝与预览快照回归；前端scope/语法。重启Local并刷新页面生效。

### NXR-SOURCE-DIALOGUE-ATTRIBUTION-20260923：对白分配与引语提示省略

- 状态：`ready`。AI文本分析改为明确的演播脚本规则：对白只归对应角色一次，不保留整段旁白副本；纯引语提示（她说/他回答道）省略，同一演员被提示打断的相邻对白合并，剧情动作/间接引语保留为旁白。增加用户示例及动作保留示例。
- 对邻近旁白引号内容与角色对白完全重复的输出进行检测，使用同一模型自动纠正一次；不在客户端粗暴删除原文或推测说话人。重复纠正仍失败给出简短错误，分析仍不写入工程。
- 验证：重复检测/动作旁白保留及分析API回归。重启Local后重新分析生效，已有Lines不自动改写。

### NXR-SOURCE-MODEL-SELECTION-20260923：文本分析模型选择与音色容错

- 状态：`ready`。追加文本对话框增加分析模型下拉框，通过系统/v1/models列出对话模型，默认使用系统work_standard中难度任务配置；可显式选择本次分析模型，不修改系统默认。
- AI建议新演员的voice_profile_id在解析时统一清空，音色留给用户审核选择；不再因AI虚构音色ID阻断有效Lines。确认写入仍校验用户选择的音色归属。
- 验证：默认模型与显式覆盖、无系统默认时显式选择、AI虚构音色清空并继续审核/写入回归，JS syntax/scope通过。重启Local并刷新页面生效。

### NXR-SOURCE-ACTOR-ALIASES-20260923：容忍 AI 演员标识格式差异

- 状态：`ready`。AI分析结果在schema校验前规范化新演员key（如 narrator、中文姓名），同步替换Lines speaker_id；已合法key和已有Cast引用保持不变，生成key避让冲突。
- 仍拒绝重复/空标识及与已有演员ID冲突的歧义输出；最终schema和归属校验保留。校验错误不再显示Pydantic链接、原始输入和冗长错误堆叠。
- 验证：原分析/确认插入API测试改用无前缀alias，新增中文别名、key冲突避让、已有角色保留、重复与歧义拒绝回归。重启Local生效。

### NXR-AUDIOBOOK-SOURCE-AI-20260923：AI 分析追加文本

- 状态：`ready`。Source text 页签改为追加文本按钮，原生对话框输入最多30,000字符；默认 Standard tasks/work_standard AI 参考全部 Cast role/Notes 与插入点前后各8行（每行上下文最多1000字符）生成结构化方案。
- AI仅分析，不写项目。审核界面可编辑/移除台词、演员绑定、情绪/语速/间隔以及建议新演员的名称/定位/Notes/可选音色。确认才事务创建Cast和Lines，插入打开对话框时展开行后或末尾；已有台词内容保持不变。
- 校验模型JSON、演员引用/归属、项目revision；拒绝截断输出、过期方案，180秒超时；batch_id幂等重试防重复。支持Package和系统统一chat路由，未配置Standard tasks给出错误。
- 验证：API分析无写入、Standard选择、上下文边界、审核修改、插入顺序、尾部追加、新演员绑定、幂等与冲突回滚回归；JS语法/scope。重启Local并刷新页面生效。未调用用户付费模型实测。

### NXR-CAST-ROLE-HINTS-20260923：演员角色定位与 AI 参考

- 状态：`ready`。Audiobook 添加/编辑 Cast 增加自动匹配、旁白、女主角、男主角、默认男声、默认女声六项角色定位，配合原 Notes（description）保存；既有角色默认 auto。
- Schema 76 添加受枚举约束的 role 列，创建/编辑 API 支持校验与持久化。Mini-App Chat 项目上下文传递 role、notes、voiceProfileId，为 AI 生成 Lines/分配说话人提供参考。
- 验证：API角色与Notes创建/编辑/读取、默认值和非法枚举回归，前端scope/语法、数据库迁移检查。重启Local迁移并刷新页面生效。

### NXR-CAST-EDIT-DELETE-20260923：Cast 编辑删除与台词缓存失效

- 状态：`ready`。Cast 卡片支持点击/键盘打开编辑对话框，可改名称、描述、音色；保存后相关 Line 标为未更新。编辑框提供二次确认删除，仅删除项目 Cast，重置相关 Line speaker_id，角色库保留。
- 新增 owner/project-scoped PATCH/DELETE characters API，事务内更新台词状态与项目 revision；音频请求快照加入 speakerRevision，角色修改后播放/完整对话均不可复用旧缓存。
- 验证：API/tasks 回归，覆盖缓存生成→角色编辑→失效→重新生成→删除→角色重置与缓存失效、跨用户拒绝；前端scope与语法检查。重启Local并刷新页面生效。

### NXR-LINE-EMOTION-SELECTION-20260923：台词情绪显示同步

- 状态：`ready`。Line 编辑及新建对话框的动态 emotion option 增加显式 selected 绑定，避免 Alpine x-for 选项创建/重建后浏览器默认显示第一项 Neutral，而数据仍为已保存情绪。
- 保留已选情绪与模型不支持时的自然语气 fallback/warning，展开编辑不修改已保存参数。
- 验证：readaloud scope 回归、模板选项绑定及diff检查通过；静态页面刷新生效。

### NXR-CHARACTER-DELETE-20260923：角色删除与确认

- 状态：`ready`。编辑页返回按钮右侧增加红色 Delete character，已保存的 Design/Reference Clone 均可删除。原生模态确认显示角色名称和影响，默认聚焦取消，执行时禁止重复提交，生成/录音/ASR期间禁用。
- 新增 owner-scoped DELETE voice-profiles API，事务内软删除角色并解除 Cast 音色绑定，保留已有音频与素材；成功清空编辑草稿并返回列表。
- 验证：Voice training API回归、前端scope及JS语法；覆盖跨用户拒绝、删除后列表移除、重复删除和素材保留。重启Local并刷新页面生效。

### NXR-SYNTHETIC-GALLERY-REFERENCE-20260923：允许设计音频经 Gallery 创建角色

- 状态：`ready`。移除 synthetic_designed 必须来自直接转换且所有素材 ID 相同的路径限制；允许用户声明合成声音来源后，从自己的 Gallery/上传素材创建、更新和试听角色。原转换来源记录仍保留作历史信息。
- 保留素材 owner、格式、时长、模型要求和文本确认校验，Gallery 导入仍复制到角色私有素材存储。
- 验证：voice training 回归覆盖合成声音 Gallery 创建、替换、删除 Gallery 文件后试听、跨用户拒绝。重启 app-dev Local 后生效。

### NXR-DESIGN-INSTALL-MORE-20260923：声音设计模型安装入口

- 状态：`ready`。Design 模型下拉框增加安装更多模型，调用 ACPF installMore；独立 audio.voice_design 配置仅请求 speech_generation 与 voice_design，推荐 VoxCPM2（16–不足32 GiB 为4-bit，32 GiB以上为8-bit），Runtime最低1.7.10。
- 安装前保存草稿，完成刷新模型，取消保留绑定；支持安装会话恢复，防止入口哨兵值写入角色。生成或配置期间禁用下拉框。
- 验证：JS语法与scope回归、安装请求及绑定保留、真实Registry推荐分档、diff检查通过。重启Local加载ACPF配置并刷新页面生效。

### NXR-VOICE-PREVIEW-EXAMPLES-20260923：试听示例文本菜单

- 状态：`ready`。Design Preview 的 Use example text 改为下拉菜单，中文、英文、中英混合各提供长短两版；选择后替换试听文本并清除旧预览，保留自由编辑和草稿保存。示例正文固定语言，不随界面语言变化，生成中禁用菜单。
- 验证：JS syntax、现有 readaloud scope 回归通过。静态资源刷新后生效。

### NXR-CHARACTER-CLONE-RECOMMENDATIONS-20260923：角色克隆安装推荐

- 状态：`ready`。Characters audio.voice_clone ACPF 新增 IndexTTS 2.5 FP16（优先）和 VoxCPM2；16–不足32 GiB 推荐 VoxCPM2 4-bit，32 GiB 以上推荐 8-bit。Qwen Base 保留可选但不再默认推荐，8–不足16 GiB 保留 CosyVoice3 轻量推荐。
- 新模型绑定正式 Package/checkpoint ID，Runtime 最低 1.7.10。内存分档为保守产品策略，并非小内存设备实测保证；现有实测记录 VoxCPM2 4-bit peak footprint 8.67 GiB，8-bit 峰值尚待记录。
- 验证：真实 CapabilityProfileRegistry 的 8/16/24/32/64/128 GiB 推荐结果、Package/service/checkpoint 一致性检查通过。重启 app-dev Local 后加载；未自动安装模型或修改已有角色绑定。

### NXR-OMLX-RUNTIME-1710-RELEASE-20260922：Runtime 1.7.10 发布

- 状态：`published`（Cloud 可安装；外部源待完成）。Apple Accepted/staple/Gatekeeper 通过；Cloud submission `a28bc3ec-9d6e-441d-8ef7-031edbada125` 为 published，metadata v191。
- 正式 Package 摘要 `a18a4f7128c73eda724fbff9f25eed0e80af6793462a88f02f6de7383ec25d2a`，381986365 bytes。18 项测试、真实 Cosy 克隆、隔离安装/依赖锁及公开签名制品一致性验证通过。
- GitHub 预检通过待独立审核；ModelScope Range 返回 200，未启用。当前 Cloud 单源，App-Dev 未执行升级。
- 收据：`docs/ai2apps-mlx-runtime-1.7.10-cosy-jit-release.md`。本次 Cookie 授权结束。

### NXR-COSY-RUNTIME-JIT-SIGNING-20260922：修复 Cosy LLVM JIT 签名崩溃

- 状态：`released`（Runtime 1.7.10 已发布，用户实例待升级）。已安装 Runtime 1.7.9 的 Hardened Python 没有 LLVM 可执行内存 entitlement；Cosy librosa 静音裁剪触发 Numba，进程被 CODESIGNING Invalid Page 终止。
- 标准 Runtime 构建器仅给私有 Python worker 配置 allow-unsigned-executable-memory，保留 Hardened Runtime/library validation；最外层封装不再 deep force 重签覆盖子进程权限，并检查最终 entitlement。
- 验证：18 项相关测试；原签名 LLVM 探针 -9、修复后 0；标准签名候选 DMG 的真实 CosyVoice3 4-bit 克隆成功输出 24kHz/4.8秒 WAV，deep/strict 签名及最终权限复核通过。记录：`ai2apps/docs/cosyvoice-runtime-jit-fix-2026-09-22.md`。已安装 Runtime 未修改，候选尚未公证或发布。

### NXR-VOICE-CLONE-INSTALL-MORE-20260922：角色克隆模型安装入口

- 状态：`ready`。Reference Clone 与 Design 转参考克隆的模型下拉框增加“安装更多模型”，调用现有 ACPF ensure 的 installMore 模式，限定 audio.voice_clone / voice_cloning 能力。
- 安装前保存角色草稿，完成后刷新 providers；安装入口不写入模型绑定，取消保留选择，配置中禁用重复操作。
- 验证：能力请求/安装模式、原选择保留、取消状态恢复检查，以及前端 scope、JS syntax、diff check 通过。未实际下载模型；静态资源刷新生效。

### NXR-VOICE-DIALOGUE-BUTTON-LAYOUT-20260922：完整对话生成按钮布局

- 状态：`ready`。完整对话输出卡片操作区水平居中，与上方说明保留 16px 间距；生成和运行时取消按钮支持换行。
- 验证：模板操作区结构与 diff check 通过；静态资源刷新生效。

### NXR-VOICE-REMOVE-LOCAL-MODELS-20260922：移除 Audiobook 模型页签

- 状态：`ready`。移除 Local models 标签及对应模型选择、模型列表与空状态 UI，清理专用样式和未使用的 capabilitySummary 方法。保留 Performance script 与 Source text。
- 验证：前端 scope 回归、JS syntax 和 diff check 通过；静态资源刷新生效。

### NXR-VOICE-LINE-ACCORDION-20260922：台词卡片单行展开编辑

- 状态：`ready`。Line 默认紧缩，显示角色与台词摘要；点击卡片展开编辑，点击标题收起，展开另一行自动关闭前一行。生成、播放在紧缩状态继续可用，操作不会意外切换展开状态。
- 使用单一 expandedLineId，切换项目重置；编辑区使用 x-show 保留原有数据绑定，提供 aria-expanded/aria-controls 与键盘可操作的标题按钮。
- 验证：单行展开/切换/收起状态检查、现有前端 scope 回归、JS syntax 与 diff check 通过。仅静态资源变更，刷新 Shell 页面生效。

### NXR-VOICE-LINE-AUDIO-RETENTION-20260922：预览清理不影响台词音频

- 状态：`ready`。Line 成功生成后复制到按 owner/project/segment 隔离的私有存储，配置快照与音频独立于渲染任务目录和 Workspace artifact；每行仅保留一份最新配置音频。历史任务删除前为旧数据补存最新成功音频。
- 播放接口校验项目 owner 与当前配置，私有音频可直接播放并供合并复用；删除预览 artifact 或任务目录不使 Line 失效。Gallery 导入副本不参与此清理。
- 补接 Audiobook 按 Mini-App 保留最新 20 条终态任务的清理：任务结束及历史加载时执行，移除超限预览文件和 render jobs，保留 Line 私有音频；前端完成后刷新历史列表。
- 验证：API/tasks 24 项通过，包括实际 21 次任务触发保留20条、旧目录移除而台词/私有音频仍存在，以及手动删除 artifact+任务后的播放/合并复用；前端 scope、diff check 通过。重启 app-dev Local 生效。

### NXR-VOICE-DIALOGUE-STUDIO-OUTPUT-20260922：合并结果进入右侧输出

- 状态：`ready`。完整对话通过 Studio run 的 mergeOutput 标记启动，底部卡片只提供操作及进度；最终合并音频发布为唯一 Studio artifact，进入右侧 Preview & Output 和历史，中间行继续保持私有，不发布。
- Retry 保留 mergeOutput 语义；删除合并任务同时 retire 最终 Workspace artifact。输出文件名包含 job ID，避免同内容去重返回其他任务的来源 metadata。
- 验证：ReadAloud API/tasks 23 项通过，合并测试确认只发布一次最终结果；前端 scope、diff check 通过。重启 app-dev Local 生效。此项替代此前底部卡片内播放/下载的交互。

### NXR-VOICE-DIALOGUE-OUTPUT-20260922：完整对话合并输出

- 状态：`ready`。Lines 底部增加完整对话输出卡片、进度、取消、播放器和 WAV 下载。按完整配置复用已生成行，缺失/修改行先后台生成；中间行不创建 Studio run/artifact，不进入右侧 Preview & Output。
- 按台词顺序规范化至 24kHz 单声道 PCM 后合并，句间插入 pause_after_ms，末尾不额外追加间隔。使用持久化渲染队列，v75 增加合并标记与最终 artifact 引用；刷新恢复当前项目最后任务及输出。
- 验证：ReadAloud tasks/API 23 项通过，新增实际 WAV 帧数、无中间 artifact、重复复用及仅修改一行重生成测试；前端 scope 和 diff check 通过。重启 app-dev Local 应用数据库升级及代码。

### NXR-VOICE-LINE-PLAY-REGENERATE-20260922：台词播放与重新生成分离

- 状态：`ready`。卡片右侧纵向显示生成/播放；生成始终创建新任务。播放先保存编辑并查询当前配置匹配的持久化音频，命中则播放；缺失或配置变化则生成，成功后播放。
- 后端按 owner/project/segment 隔离，对比文本、角色、模型及 revision、参考素材、情绪强度、速度、句后间隔；只复用成功且 artifact active、输出文件存在的结果。旧记录缺少完整配置快照时保守重生成。
- 验证：ReadAloud tasks/API 22 项通过，覆盖配置命中、速度/模型 revision 失配及已删除音频；前端 scope 检查、diff check 通过。Python 与静态资源更新，重启 app-dev Local 生效。

### NXR-VOICE-LINE-EDITING-20260922：Audiobook 台词编辑

- 状态：`ready`。增加行内上移、下移、删除确认与句后间隔（毫秒）输入。移动边界禁用；运行期间禁止移动/删除。项目范围与 owner 校验，事务更新顺序及 revision。
- 数据库升级 v74：台词 deleted_at 软删除；项目读取、计数和新生成任务排除删除项，保留历史渲染外键和音频。原有 pause_after_ms 保存契约不变。
- 新建角色选择显式绑定 change，行内动态角色 option 同步 selected，避免创建后下拉框显示未选择。
- 验证：readaloud API/仓库/tasks 21 项通过，含顺序、越权、软删除、角色及间隔持久化回归；前端 scope 检查通过；diff check 通过。Python/数据库变更，重启 app-dev Local 生效，无 App 重建。

### NXR-VOICE-PROJECT-CONTROL-ALIGN-20260922：项目选择行对齐

- 状态：`ready`。Project switcher 改为底部对齐，New project/Delete project 按钮统一为与下拉框相同的 36px 高度；Project 标签保持在上方，保留窄屏换行。仅 CSS，刷新 Shell 生效。
- 验证：检查最终选择器及 git diff --check 通过。

### NXR-VOICE-EMOTION-FALLBACK-20260922：不支持情绪降级为自然语气

- 状态：`ready`。Audiobook 调用按角色绑定模型的情绪枚举过滤；不支持的情绪省略控制字段，继续自然语气生成，不修改原始台词选择。台词编辑区显示中英文黄色 warning，切换模型/角色后实时更新。
- 验证：ReadAloud tasks 9 项测试通过，覆盖 whisper 降级、angry 保留及 neutral；Voice Studio scope 前端检查通过。Python 模块变更需重启 app-dev Local。

### NXR-VOICE-ARTIFACT-FOREIGN-KEY-20260922：Audiobook 生成结果保存失败

- 状态：`ready`。修正 ReadAloudTaskManager 将 Studio/render job ID 写入 Workspace artifact 的 agent_runs 外键导致 FOREIGN KEY constraint failed；使用现有 metadata.runId 与 studio_artifacts 保留 Studio 关联，不修改数据库约束。
- 验证：tests/test_ai2apps_readaloud_tasks.py 6 项通过，新增真实 PlatformRuntime/SQLite artifact 导入测试，检查 run_id 为空、Studio runId 保留、foreign_key_check 无异常。
- 生效：Python 模块变更，重启 app-dev Local，无需重建 App。用户失败任务已有生成 WAV，错误在导入输出阶段。

### NXR-DISCOVER-INSTALLED-VARIANT-20260922：模型选择框识别已安装档位

- 状态：`ready`。打开 Discover 模型选择框前刷新 `/packages/installed`，按当前
  Package 版本与 readyModelConfigurationIds 标记已就绪档位，使用公共 ACPF installMore
  行为显示“已安装”并禁选；自动选择剩余兼容档位。全部就绪时继续按钮禁用。
- 保留新版本 Package 的升级入口，不以 Package 已安装代替 Checkpoint 就绪判断。
  仅 Discover JS 修改，刷新生效，不实际下载安装模型。

### NXR-DISCOVER-CANCEL-RESUME-20260922：取消安装后不再反复恢复

- 状态：`ready`。Runtime 依赖升级后的 Package continuation 在交接到安装 UI 前消费一次，
  后续由 ACPF 会话自行持久化；取消配置选择不会在刷新后重复弹出。公共 ACPF 取消错误
  使用稳定 code，Discover 不再将英文取消消息显示为失败；恢复忽略 cancelled/unsupported。
- 轮询在延时和请求返回后检查 stopped，避免取消后的在途响应重新保存 pending session。
  仅前端修改，刷新生效，不修改已安装 Package 或执行下载安装。

### NXR-DISCOVER-MODEL-INSTALL-I18N-20260922：模型安装流程多语言补齐

- 状态：`ready`。补齐 Discover 模型配置选择说明、安装标题、说明、确认按钮、
  就绪提示及三个步骤的九种语言翻译。动态“安装 {模型名}”在公共 ACPF 渲染层
  归一化，固定句子优先匹配，兼容已持久化的中文会话数据；不改后端会话协议。
- 仅 JS 和翻译目录变更，刷新页面生效，无需重启 Local；未触发模型下载安装。
- 验证：九种语言 JSON 解析、八类文案完整性、固定句子优先匹配及历史动态模型标题
  的实际 JS 翻译执行均通过；JS 语法与 diff 空白检查通过。未进行 App-Dev 现场刷新验收。

### NXR-DISCOVER-INSTALL-LAYOUT-20260922：安装弹窗三段式布局

- 状态：`ready`。Discover 安装弹窗改为固定标题、独立滚动内容区、固定操作栏。
  将按钮从滚动正文移到独立底部，弹窗外层禁止滚动，中段设置 min-height:0 和
  overflow-y:auto；小窗口中关闭、重试、升级依赖与重启按钮不再滚出可见区域。
- 仅模板/CSS 修改，刷新 Discover 生效，无需重启 Local 或重建 App；不改变安装状态机。

### NXR-VOICE-VOXCPM2-INDEXTTS25-MLX-20260922：两套高级语音模型

- 状态：`released`。2026-09-22 已发布 Runtime 1.7.9、VoxCPM2 0.1.0、IndexTTS 2.5
  0.1.0 及三份 checkpoint distributions。Runtime 的 Cloud、GitHub、ModelScope 三源
  均为 active；三个正式 Package 和三份 distribution 均完成匿名签名回读。完整收据见
  `docs/ai2apps-mlx-runtime-1.7.9-voxcpm2-indextts25-release.md`。Runtime 1.7.9 新增 VoxCPM2 与纯 MLX
  IndexTTS 2.5。统一 `audio_speech` 适配器增加模型专属结构化控制映射；VoxCPM2
  提供无转写参考克隆、声音设计和指令式情绪/语速，IndexTTS 2.5 提供参考克隆、
  八维数值情绪与原生 `duration_factor = 1 / speed`，P0 只开放中文和英文。
- Runtime 固定 MLX-Audio 0.5.5 commit
  `cd605ecfcc266ccf6ea3077586c373101be982c6`、Transformers 5.15.1 与 WeText
  0.1.8，并 vendoring WIndexTTS commit
  `eafb98c1b2ba46f6a608f29d8831208b89047681` 的 Torch-free MLX 路径。正式 Runtime
  不携带 Torch；wheel 检查确认 Python、license 与两份 `.npz` 前端数据均已打包。
- IndexTTS checkpoint 由固定官方主权重和 W2V-BERT/CAMPPlus/BigVGAN revision
  可复现转换为 FP16 safetensors，排除训练状态及可选 Qwen 情绪模型；本地候选约
  3.1GB。VoxCPM2 4-bit checkpoint 约 2.1GB；4-bit/8-bit 的现有 HF/MS 公共镜像
  已固定 revision，并通过本地开发签名 `metadata_verified` envelope 双源逐字节校验，
  无需重复上传 VoxCPM2 权重。
- M5 Max 实测：VoxCPM2 4-bit 生成 6.40 秒音频耗时 3.27 秒，RTF 0.51；
  8-bit 也已直接使用候选 Runtime 完成真实 Metal 推理，冷启动加生成 2.12 秒、输出
  3.36 秒；
  IndexTTS 2.5 FP16 中英文多组 RTF 0.72–0.94，最终可复现候选 4.42 秒音频耗时
  3.48 秒，RTF 0.79。峰值 RSS 分别约 2.73GiB、3.72GiB；Apple peak memory
  footprint 分别约 8.67GiB、4.55GiB。两者均在 MLX GPU 上完成真实推理。
- 38 项定向 Adapter、Package 与 Runtime 回归通过，依赖锁与 wheel 构建通过；正式
  Package/Checkpoint 发布兼容回归另有 65 项通过。最终 DMG 内 Bundle 验签、Apple 公证、staple
  与 Gatekeeper 均通过，并直接用候选 Runtime 内嵌 Python 对两模型完成真实 Metal 推理。
  Index checkpoint 已上传 HF/MS 不可变双源；三份 distribution、Runtime 及两个模型
  Package 均已签名、审核、发布并完成公开逐字节验收。发布后重启 App-Dev Local，现场
  确认 IndexTTS FP16 与 VoxCPM2 4-bit/8-bit 安装计划均可打开，未触发实际下载。

### NXR-VOICE-SEGMENT-CAPABILITIES-20260922：逐句生成能力过滤

- 状态：`ready`。根据每句角色绑定模型的 audio_capabilities 决定是否传 speed/emotion，缺失或 unsupported 不传，使用模型默认。修复 Qwen Base 因旧台词 speed=1.5 返回 400。支持的 multipart 情绪用独立字段传递；界面不显示不支持的情绪选项，语速显示 Model default。
- 回归覆盖绑定克隆模型不支持语速/情绪但旧台词含自定义值时仍生成成功。App-Dev Local 重启生效，未发布。

### NXR-VOICE-AUDIOBOOK-CLONE-RENDER-20260922：Audiobook 角色参考克隆

- 状态：`ready`。修复 Audiobook 仅传 provider_voice_id 而未传克隆参考音频导致 Qwen Base HTTP 400。每句请求快照记录角色绑定模型及参考配置，执行时使用角色模型和私有素材，经相同文本/时长/版本检查及合并逻辑后走后台 multipart；Design 角色传入声音描述，普通预设音色保留 JSON 路径。
- 模型错误保留受限长度的返回原因，便于定位。回归 23 项通过，包含使用不同于项目默认模型的角色及双参考音频合并。App-Dev Local 重启生效；旧失败任务可 Retry 重新获取角色配置，未发布。

### NXR-VOICE-PROJECT-DELETE-20260922：Audiobook 删除项目

- 状态：`ready`。项目选择栏新增删除入口及原生确认对话框，显示项目名称，默认取消。复用所有者隔离的项目 PATCH archived 状态实现软删除，列表移除并更新当前选择/草稿，保留生成历史、角色库及 Gallery；生成进行中入口禁用。
- 前端回归验证取消不修改、确认只移除目标及清理选中状态；JS 语法/diff 检查通过。静态刷新生效，未发布。

### NXR-VOICE-REMOVE-HEADER-RUN-20260922：移除顶部 Run

- 状态：`ready`。移除 Audiobook Mini-App 标题栏的 Run 按钮，保留现有生成方法供后续工作流使用。
- 仅模板变更，diff 检查通过；刷新生效，未发布。

### NXR-VOICE-REMOVE-ENSEMBLE-20260922：合并朗读入口

- 状态：`ready`。Mini-App 列表移除 Ensemble Drama，Characters 使用其 users-round 多人图标；列表顺序固定为 Quick Read、Characters、Audiobook（同步服务端排序及前端后备列表）。旧 Ensemble 项目在 Audiobook 项目列表继续可用；记忆的 Ensemble 入口转到 Audiobook，后台保留旧 ID 兼容读取/重试，不删除数据。
- 前端回归覆盖入口移除、图标及旧项目访问；11 项 API 回归通过。App-Dev Local 已重启，未发布。

### NXR-VOICE-PROJECT-TOOLBAR-FIT-20260922：项目用途下拉框溢出

- 状态：`ready`。项目标题输入框取消相对窗口的固定宽度，工具栏按 Studio 中间面板可用宽度换行；Purpose 与 Rights 下拉框可收缩并保持在面板内，窄面板时移至标题下方。
- CSS 及资源版本修改，diff 检查通过；刷新生效，未发布。

### NXR-VOICE-PRIVATE-MATERIALS-20260922：角色专属参考音频

- 状态：`ready`。新增按所有者隔离的 VoiceMaterials 存储；录音/上传及 Design 转 Clone 保存到角色素材目录，不再自动写入 Gallery。从 Gallery 选取只复制素材，角色引用与 Gallery 生命周期分离。保留原始音频及哈希，合并仍只在模型调用时生成。
- Local 启动时迁移现有角色所有参考音频，保持 ID 与验证状态；旧草稿在使用时补迁移。不删除原 Gallery 资产，缺失旧文件记录待重新导入。角色私有内容接口执行所有者隔离。
- 验证：29 项后端及前端回归通过，覆盖独立上传、Gallery 删除后试听、迁移幂等和跨用户拒绝。App-Dev 已重启并完成迁移，实地只读核对所有现存角色参考均有私有副本；帮助文档更新，未发布。

### NXR-VOICE-NOTICE-TIMEOUT-20260922：提示自动关闭

- 状态：`ready`。成功提示 4 秒后关闭，错误提示 8 秒后关闭；新提示替换时清除旧计时并重新计时，手动关闭同时清除计时器。
- JS 语法及 diff 检查通过；静态刷新生效，未发布。

### NXR-VOICE-SAVE-STAY-EDITOR-20260922：保存素材保留编辑界面

- 状态：`ready`。Save reference materials 成功后留在当前编辑界面，保留样本、确认状态、授权勾选及试听文本/输出；绑定返回的 profile ID，后续保存和试听更新同一角色，局部更新底部卡片列表，不关闭/清空表单。
- 前端回归覆盖保存后界面/素材/试听保留及重复保存复用 ID；JS 语法及 diff 检查通过。刷新生效，未发布。

### NXR-VOICE-MATERIAL-CARD-SIMPLIFY-20260922：底部角色卡片简化

- 状态：`ready`。移除 Saved reference materials 卡片内重复的 Edit materials 按钮，保留整卡点击及 Enter/Space 切换角色。
- 仅模板修改，diff 检查通过；刷新生效，未发布。

### NXR-VOICE-PREVIEW-DEFAULT-ICON-20260922：试听按钮状态与默认文本

- 状态：`ready`。参考克隆试听按钮使用两个固定 SVG 按 busy 状态显隐，避免 Lucide 替换节点后动态图标停留在 loader。Preview text 留空或仅空格时，自动使用与 Design 相同的中英文混合文本；新建时保留空输入，placeholder 显示默认内容。
- 前端回归覆盖空文本默认值及自定义文本保留；JS 语法及 diff 检查通过。刷新生效，未发布。

### NXR-VOICE-TRAINING-ACTIONS-20260922：参考克隆操作按钮布局

- 状态：`ready`。Generate voice preview 改为带播放图标的紧凑主按钮，居中对齐、不拉伸整行。Save reference materials 按钮保持单行、不压缩；说明文字可换行，窄容器时按钮整体换至下一行右对齐。
- 模板/CSS 修改，diff 检查通过；刷新生效，未发布。

### NXR-VOICE-MERGED-REFERENCE-20260922：单参考模型合并多素材

- 状态：`ready`。单参考克隆模型支持选择多条素材，按列表顺序将归一化的 16kHz 单声道 PCM 拼接为 WAV，并合并对应文本后调用模型。原始 Gallery 文件/样本列表保持独立；验证合并时长及总时长限制，合并最长 600 秒。可选文本必须全部提供且确认或全部留空，避免部分文本与完整音频不匹配。
- 前端保留多选、显示合并说明、取消单素材数量拦截，并同步合并时长/文本检查。保存与状态验证仍绑定完整所选样本；实际多参考模型及训练适配限制不变。
- 验证：Voice Training/API 26 项及前端回归通过，覆盖 WAV 帧数/文本顺序、部分文本拒绝、无文本及总时长超限。App-Dev Local 已重启，未发布。

### NXR-VOICE-REFERENCE-DELETE-CONFIRM-20260922：参考素材删除确认

- 状态：`ready`。点击参考语音删除先打开确认对话框，显示素材名、仅从角色移除及 Gallery 原素材保留说明。默认焦点在取消，Esc 取消，明确确认后才移除；不影响已保存角色直至保存。
- 前端回归覆盖打开/取消不修改列表、确认只移除目标；JS 语法及 diff 检查通过。静态刷新生效，未发布。

### NXR-VOICE-ASR-WAIT-FIX-20260922：自动 ASR 完成状态同步

- 状态：`ready`。自动导入传入原始 sample，完成时未通过 Alpine 响应式对象写回，导致识别成功仍显示等待。转录入口统一按 assetId 获取响应式 sample，成功/失败触发文本及等待框更新。识别请求增加 180 秒超时及 AbortController，超时退出等待并显示可重试错误。
- 对话框文案改为客户端翻译并提供中英后备文本，解决运行中 Local 缓存旧语言表时直接显示 key。保留“在后台继续”/Esc 收起等待。
- 验证：现场日志 ASR 返回 200；前端回归覆盖原始对象调用时响应式写入、完成关闭及超时关闭；JS 语法/diff 检查。静态修改刷新生效，未发布。

### NXR-VOICE-REFERENCE-DELETE-20260922：参考语音删除入口

- 状态：`ready`。将参考素材卡片底部 Remove from character 移到标题右侧，改为红色垃圾桶图标及 Delete 文本，长文件名换行且删除按钮不被挤出。沿用素材移除及草稿持久化逻辑，不删除 Gallery 原素材；保存角色后更新正式素材配置。
- 模板/CSS 改动，diff 检查通过；刷新生效，未发布。

### NXR-VOICE-WAIT-DIALOG-20260922：ASR 与试听等待对话框

- 状态：`ready`。自动/手动 ASR、Design/Reference Clone 试听与 Quick Read 生成显示原生模态等待对话框，包含旋转指示、当前素材或角色、处理说明。成功或失败自动关闭；支持“在后台继续”及 Esc 隐藏，任务继续执行。原生 dialog 提供焦点限制/恢复，支持减少动画偏好。
- 验证：前端回归覆盖 ASR/失败关闭、三种生成状态与完成关闭；JS 语法、i18n JSON 解析与 diff 检查通过。未发布。

### NXR-VOICE-AUTO-ASR-20260922：新增参考素材自动转录

- 状态：`ready`。移除自动转录对“模型强制要求参考文本”的限制：开启自动转录且 ASR 就绪时，录音、上传及 Gallery 新增样本均触发 ASR。文本可选或尚未选择克隆模型也生效；未就绪时显示配置提示，开关变更持久化。
- 验证：前端回归覆盖触发、关闭开关和 ASR 未就绪；JS 语法及 diff 检查。模板/i18n/JS 变更，未发布。

### NXR-VOICE-NEW-CHARACTER-RESET-20260922：新建角色清理旧克隆草稿

- 状态：`ready`。Create character 同时重置 Design 和 Reference Clone 表单，清除旧 profile/model/source/rights、参考样本、试听文本及预览选中状态；新建表单不自动选中旧试听历史。已保存角色、Gallery 及任务历史不变，同一次新建内切换模式仍保留当前草稿。
- 验证：前端回归覆盖编辑 Alice 后新建、切换克隆、表单与预览清理、模式切换保留及草稿恢复；JS 语法及 diff 检查。静态改动刷新生效，未发布。

### NXR-VOICE-CHARACTER-TOOLBAR-20260922：角色编辑顶部布局

- 状态：`ready`。Back to characters 与 Voice environment ready 共用首行，分别左/右对齐；Creation method 加粗，Design / Reference Clone 按钮紧随标签左对齐。移除克隆表单内重复环境按钮，Design 与 Clone 共用顶部布局。
- Voice environment ready 在就绪时显示绿色文字、浅绿色背景及边框；角色列表与编辑页一致，配置中不使用绿色。
- 静态模板/CSS 变更，刷新 Shell 生效；diff 检查通过，未发布。

### NXR-VOICE-CLONE-VERIFICATION-20260922：参考克隆试听状态

- 状态：`ready`。参考克隆试听前保存当前配置，成功后仅对匹配的模型、版本、所选参考音频/文本/确认状态及授权配置设置 Ready；失败或试听过程中保存了不同配置时不验证。重命名及重复保存保留 Ready，更改参考配置后回到待验证。
- 前端即时刷新角色卡片；Unverified 文案改为 Pending validation / 待验证。旧历史缺少配置快照，不推断验证状态，需要重新试听一次。
- 验证：Voice Training 与 Readaloud API 共 25 项回归通过，覆盖成功/失败、重复保存、重命名、参考变更及旧配置试听；前端 scope 回归、JS 语法和 diff 检查通过。App-Dev Local 重启生效，未发布。

### NXR-STUDIO-TASK-DELETE-20260922：Studio 任务右键删除

- 状态：`ready`。Video（生成/拼接/音频提取）、Voice（Quick Read/参考克隆/长文朗读）、Image 任务卡片共享右键菜单，支持 Shift+F10、Esc、点击外部关闭和视口定位。
- 新增按用户/Studio 实例授权的本地删除接口，删除历史及其自有输出；运行中任务拒绝删除，Gallery 独立副本保留，清除已删除的 Design 试听引用。Image 同步删除旧结果，避免历史重新导入。
- 验证：Video/Image/Workspace 删除及 Gallery 副本回归通过；Voice API、渲染删除及克隆回归通过，前端 scope 回归、JS 语法和 diff 检查通过。App-Dev Local 已重启，现场验证 Voice 卡片右键菜单与 Esc 关闭/焦点恢复，未删除用户现有素材。未发布。

### NXR-VOICE-TASK-CARDS-20260922：音频任务卡片

- 状态：`ready`。JS 语法、前端回归与 diff 检查通过。参考 Video Studio 的卡片结构，Reference Clone 与 Quick Read 共用纵向任务卡片：图标、标题、模型/演员、本地时间、状态、下载及选中高亮，支持键盘选择；最多 20 条，列表独立滚动。
- 修复克隆历史显示为一排文字按钮、标题错误使用 Generate voice preview 的问题；仅前端，刷新 Shell 生效，未发布。

### NXR-VOICE-CLONE-PREVIEW-REASONS-20260922：克隆试听禁用原因

- 状态：`ready`。现场确认 Alice.wav 参考文本尚未确认；试听按钮改为显示具体缺项（文本确认、模型就绪、素材数量等），提示文本确认所在步骤，不代替用户勾选。
- 修复合成来源克隆角色被素材列表过滤而显示 0 条的问题。前端回归覆盖未确认提示、确认后可试听及合成来源克隆列表；仅静态变更，刷新生效，未发布。

### NXR-VOICE-DESIGN-SAMPLE-20260922：双语默认试听文本

- 状态：`ready`。JS 语法、现有前端回归及 diff 检查通过。新建 Design 默认填写可编辑的中英双语短文；已有角色文本保留，增加“使用示例文本”按钮，替换文本后要求重新生成试听。
- 中英文界面共享同一双语示例，帮助说明用于比较语言表现，不承诺提高克隆质量。仅静态内容，刷新 Shell 生效；未发布。

### NXR-VOICE-CLONE-NAMING-20260922：参考克隆命名澄清

- 状态：`ready`。前端回归与 diff 检查通过；中英文转换按钮、角色标签、创建方式、素材保存提示及帮助统一使用 Reference Clone / 参考克隆，明确不训练权重。
- 新建转换副本名称后缀由 Trained 改为 Clone；已有用户角色名称保留。内部接口和持久化字段不变，未发布。

### NXR-VOICE-DESIGN-READINESS-20260922：按模型变体显示和配置就绪状态

- 状态：`ready`。45 项 provisioning 回归和两组前端回归通过；App-Dev 52322 实测配置入口默认选中 VoiceDesign。实际 checkpoint 校验确认为 Base/CustomVoice ready、VoiceDesign missing；未触发下载。此前包级任一变体就绪会隐藏其余变体安装入口。
- Discover 展示已就绪变体数量，仅所有声明变体都就绪时隐藏配置入口。Design 表单增加精确绑定当前模型的配置按钮，复用 ACPF；ReadAloud profile 新增 VoiceDesign 非默认配置，防止误配置 CustomVoice。
- 不改动各隔离实例权重，不绕过 checkpoint 完整性校验；未发布。

### NXR-VOICE-DESIGN-EDITOR-20260922：角色试听编辑与参考克隆转换

- 状态：`ready`（实现及接口回归）。23 项 Training/ReadAloud 回归、前端回归与 diff 检查通过；App-Dev 实测 Alice 卡片进入编辑器并保存描述/试听文本。当前 VoiceDesign checkpoint 未就绪，真实生成返回明确 409，未声称完成真实模型音色验收；未发布。
- 点击角色卡片打开编辑器；Design 绑定兼容模型、保存描述与试听文本，通过真实 audio_speech instructions 接口生成共享 Preview & Output 音频。更改描述、模型或文本会使旧试听失效。
- 可把生成音频复制到独立 Gallery 素材，创建绑定参考克隆模型的 Trained Voice 副本，保留原设计。带入文本待校对，保持 unverified；记录合成来源，禁止以转换来源替换任意真人音频。Gallery 副本不受试听历史清理影响。
- 涉及 API、Repository、前端、中英文及帮助；需重启 app-dev Local。

### NXR-VOICE-DESIGN-MODEL-FILTER-20260922：Design 模型能力筛选

- 状态：`ready`。20 项 Training/ReadAloud API 回归及前端能力筛选/旧选择清理回归通过；app-dev Local 已重启加载保存校验，未发布。
- Design 仅展示明确声明 voice_design 的 TTS 模型，不能用普通 instructions 支持推断声音设计；清理旧草稿中不适用的选择，保存 API 同样校验能力。
- 当前 Qwen3 三变体中仅 VoiceDesign 可用于 Design；Base 为参考克隆，CustomVoice 为内置演员及风格指令。

### NXR-CHARACTER-CREATION-LAYOUT-20260922：角色创建页空白修复

- 状态：`ready`。diff 检查通过；App-Dev 64205 刷新后截图确认创建方式与 Design 表单紧接显示，名称、模型、参考文本及提交按钮均在首屏可见。
- 创建方式选择区误用了带 580px 最小高度的整页样式，导致表单下移。改成按内容高度排布的紧凑工具栏，Design 表单紧接其后，Training 也共用该工具栏；窄屏允许换行。
- 仅模板/CSS，刷新 Shell 生效，无需重启或重建 App。

### NXR-VOICE-TRAINING-20260922：模型绑定与多段角色素材

- 状态：`ready`（素材管理及单参考克隆接口；真实多参考执行/训练仍为明确的未接入能力）。
- Training 绑定支持声音参考/训练能力的模型，展示模型声明的数量、单段/总时长与文本要求。统一素材列表支持批量上传、录音、Gallery、选用子集、逐段试听与删除引用。
- ASR 支持自动识别（模型要求文本且 ASR 已配置）、批量识别缺失文本、单段重试和确认校对，避免覆盖识别期间的手工编辑。
- Schema 73 持久化素材集、模型 revision 与要求；可重新编辑，保持 unverified，不把保存素材称为完成训练。原单参考音频协议接通绑定模型克隆试听；多参考/实际训练 adapter 尚不存在，明确阻止执行并允许准备素材，不虚构训练结果。
- 服务端检查素材所有权、真实音频格式/时长、选用数量与文本确认；试听使用同用户 ModelInvocationContext。需重启 app-dev Local；未发布。
- 验证：42 项 Training/ReadAloud/存储回归通过，后续扩展的 8 项 Training API 测试通过；20 项本地化/Workspace 回归通过。前端回归验证单参考选样、多段保留、确认条件、草稿恢复、ASR 不覆盖并发编辑与失败保留文本。App-Dev 64205 已加载 schema 73，旧 18 秒 Gallery 音频恢复，Qwen3 Base 显示单参考/文本可选，实机 ASR 成功返回未确认文本，刷新后模型绑定、素材、转录和未确认状态均保留；未执行实机克隆或真实训练。
- 试听输出独立保留最近 20 条并复用安全文件清理，支持共享 Preview & Output、下载和 Gallery 拖拽；不会混入 Quick Read 历史。模型 revision 变化要求显式重新绑定。

### NXR-VOICE-CHARACTERS-20260922：统一角色管理入口

- 状态：`ready`。11 项 ReadAloud API 回归、前端入口/模式切换/草稿回归、JS 语法、JSON 与 diff 检查通过。App-Dev 62459 实测仅保留 Characters 入口，创建页 Design / Training 切换正常，Training 录音、上传、Gallery 和转录界面可见。
- Voice Design 与 Train Character 合并为 Characters（角色管理）；创建角色时切换 Design / Training，统一角色列表，保留录音、Gallery 选择、转录及素材保存流程。
- 保留旧 Mini-App ID 的草稿接口兼容，恢复旧 Training 入口及草稿到统一入口；新草稿保存创建方式。Design 目前仍为声音档案保存，文字描述生成音色尚未接入，页面明确说明。
- 不迁移、不删除既有声音档案或 Gallery 参考音频。需要重启 app-dev Local 加载入口定义与翻译；未发布。

### NXR-STUDIO-HISTORY-CLEANUP-20260922：Studio 历史素材磁盘回收

- 状态：`ready`（50 项 Workspace、视频任务、视频 Studio、图片 Studio 回归通过）。
- Quick Read 超过 20 条时清理过期音频；视频生成保留 20 条已结束任务，回收旧输出 Artifact 与任务输入/临时目录；视频合成与音轨提取按 Mini-App 各保留 20 条已结束任务。生成结束与读取历史时执行，排队/运行中任务不清理，按原用户/实例边界隔离。
- Imagine Studio 已有最近 20 条及文件删除逻辑，本次补充 Gallery 副本保留验证。
- Workspace 回收按内容存储键检测其他有效 Artifact、资源句柄和进行中的导出；仍被使用的共享文件保留。导入与回收串行，避免写入/删除竞态；重复导入过期内容恢复有效记录。
- Gallery 导入是独立文件副本（独立 gallery 存储目录），来源链接只是元数据。回归覆盖音频、图片、视频生成和视频合成：旧 Studio 文件确实删除，Gallery 文件仍可逐字节读取；同时覆盖用户隔离、共享内容保护、运行中任务保留。
- 无 Cloud、数据库结构或 App Bundle 修改；已重启 app-dev Local 至 61123 加载变更，未发布。

### NXR-QUICK-READ-DIRECT-20260922：Quick Read 无工程朗读

- Quick Read 历史持久化：复用用户隔离的 Workspace Artifact，持久保存标题、模型、演员与生成时间；历史 API 返回最新 20 条，页面启动后恢复列表和已选结果（缺失则选最新）。旧版已保存音频可恢复，缺少旧元数据时显示原文件名。播放/下载链接为当前 Local 相对路径，重启换端口后仍可用；恢复结果拖拽按需预载音频 File。15 项 Python 回归及前端历史选择/缺失回退回归通过；App-Dev 重启至 60279 后恢复 4 条旧音频，选择旧结果后刷新仍保持选中，并加载 15 秒时长与下载链接。

- 用户确认 Preview→Gallery 拖拽已通过。修复播放进度拖动被外层 draggable 抢占：移除播放器父容器的 draggable，只允许音频图标、标题和提示作为素材拖拽起点；播放控件独立交互。diff 检查通过。

- Preview 精简与拖拽：自定义播放/暂停、进度与时长控制，不展示音量；移除 Active speech model 区域。预览支持 audio Artifact 引用及标准 File 拖拽；Gallery 优先导入受权限校验的 Artifact，接受文件的音频 Mini-App 使用 WAV File。前端拖拽 payload/File 与生成回归通过，国际化 4 passed；App-Dev 59548 真实生成约 18 秒音频，截图确认无音量、无 Active speech model，播放/进度正常。自动化跨 iframe 拖拽未观察到 Gallery 新资产，端到端落点仍待人工复验，不标记拖拽实机通过。

- 导出格式：Quick Read 下载旁增加 WAV / MP3 / M4A (AAC) / FLAC；标准 Artifact 下载接口接受受限 audio_format 参数，复用 Host audio_codecs 实际转码并匹配 MIME、扩展名和 ETag，不重新生成语音。保留原生 Save As。18 项编解码及下载 API 测试通过，逐一解码验证四种实际编码、MIME 和文件扩展名；前端格式链接回归通过。

- Download audio 修复：生成结果通过标准 Workspace Artifact 保存，返回受 Session 所有权保护的 HTTP download URL；下载按钮沿用 Gallery/Video Studio 原生 anchor 导航，由 AceFox 弹出 Save As。Blob 仅用于页面试听。14 项相关 Python 回归及前端下载 URL 回归通过；App-Dev 58091 实测生成约 10 秒语音，点击 Download audio 后成功弹出原生 Save As（Waveform Audio / .wav / Cancel / Save）。对话框保留供用户选择目标位置。

- 右侧栏细节：音频容器与原生控件限制在列宽内，长标题省略，下载按钮增加 12px 顶部间距；idle/succeeded 采用绿色。Quick Read 增加当前会话 Tasks，记录每次生成的标题、模型/演员、时间、状态，允许切回已有音频播放下载；历史持久化已由本条目后续改动补齐。前端多任务切换回归通过；App-Dev 53204 真实生成 9 秒音频，截图确认控件无溢出、下载间距、绿色 succeeded 与 Tasks 卡片均正常。

- Preview & Output 调整：恢复 Quick Read 共享右侧输出区，生成状态、音频播放与 WAV 下载统一放在该区；生成时自动展开，移动端转到 Output。Mini-App 中只保留文本、模型、演员和生成操作，隐藏其他工程的输出历史，避免混淆。 前端行为回归、JS 语法与 diff 检查通过；App-Dev 53204 已实测当前草稿生成，右侧 Preview & Output 显示 running→succeeded、音频播放位置及 Download audio 链接。

- 2026-09-22 实机修复：清理中英文 `readaloud.quick.help` 重复键；通过标准 Helper 控制接口重启唯一 app-dev Local，端口由 52011 变为 53204。重新打开后文本草稿完整恢复，说明与所有新控件翻译正常，Qwen3 TTS 1.7B CustomVoice 8-bit + serena 对现有 245 字草稿生成约 45 秒音频，UI 显示自动播放（Pause / 0:02 / 0:45）与 Download audio 链接；未再出现 404。国际化回归 4 passed。

- 状态：`ready`（源码回归及 App-Dev 真实生成/自动播放通过）。
- Quick Read 改为输入/粘贴文本、选择模型与模型声明的演员、生成并播放；不再要求创建项目，不创建隐藏工程。独立播放器支持下载 WAV，草稿保存文本与演员。
- Local API 通过带用户上下文的现有模型调用服务调度生成，验证文本长度、TTS 模型就绪状态和演员；不改 Cloud。Audio Book/多角色演播保留工程模式。
- 自动播放受浏览器策略限制时可手动播放；音频持久保存，刷新后恢复最近 20 条。更新内置帮助和中英文文案。
- 验证：ReadAloud API/任务、Mini-App Chat、国际化专项 22 passed；`node tests/test_ai2apps_readaloud_scope.cjs` 验证无工程生成、自动播放、空文本、草稿和工程隔离通过。API 测试验证演员/模型/文本限制、默认演员、用户调度上下文及零工程写入。JS 语法和 diff 检查通过。App-Dev 已重启 Local 并完成真实模型生成和播放器状态验收；未发布。

### NXR-VOICE-PROJECT-SCOPE-20260922：Voice Studio 项目归属隔离

- 状态：`ready`（源码回归通过，待 App-Dev 实机验收）。
- Quick Read、Audio Book、多角色演播的新项目持久保存 Mini-App 归属；各入口只显示自己的项目，切换时重置项目表单并恢复对应草稿，拒绝恢复其他入口的旧项目选择。
- 数据库迁移 72 将无来源记录的历史项目保留在 Audio Book，不删除内容；不推断历史创建来源。
- 影响：Local API、数据库和 Voice Studio 前端；开发验收需要重启 App-Dev Local 并刷新页面，无需重建 App。
- 验证：`pytest tests/test_ai2apps_readaloud.py tests/test_ai2apps_readaloud_tasks.py tests/test_ai2apps_platform_storage.py -q -p no:cacheprovider`：36 passed；`node tests/test_ai2apps_readaloud_scope.cjs` 通过创建、切换、草稿恢复和跨入口旧选择回归；JS 语法与 diff 检查通过。尚未完成 App-Dev 实机验收，未发布。

## Build 2252 已发布（2026-09-21）

- Build 2252 已从 clean、已推送 commit
  `9521a6d674babd03125ed0e310c926863dbd6cde` 构建；Developer ID、Apple 公证
  `3850a24c-4457-4516-b9d0-ff4cee2cc806`、Staple、Gatekeeper 和最终制品复验均通过。
- GitHub 正式 Release `v0.1.0-build2252` 与 ModelScope immutable revision
  `735eb1d4a1bfbc30677fc80308fc2bb9330a0429` 已发布；匿名完整回读的 DMG/metadata
  字节数和 SHA-256 均与本地一致。Cloud 先以 0 basis points 原子登记并完成严格双源预检、
  公网 GET/HEAD/ETag/304、Cloud 与数据库健康验收，随后将同一 `build2252-test` rollout
  提升至 `10000`。最终生产清单 SHA-256 为
  `894271943aa4977d78fae3a4c2f0d622382662905fd123b26a2e285df5002254`。
- 本版只纳入 `NXR-VERIFIED-OVERLAY-CHECKPOINT-READINESS-20260921`，不升级 oMLX Runtime
  或模型 Package。完整制品、测试、双源和生产发布回执见
  `docs/ai2apps-desktop-build-2252-release-receipt-2026-09-21.md`。剩余验收只包括目标 Mac 的
  2251→2252 自动发现、下载、安装、启动与更新后清理；不影响分发发布已完成的事实。

## Build 2251 已发布（2026-09-20）

- Build 2251 已从已推送源码 commit
  `12af6aa9bfd7bf853fbdbe752fbc8712e60bdbde` 构建，完成 Developer ID 签名、Apple
  公证与 Staple，并发布到 GitHub tag `v0.1.0-build2251` 和 ModelScope immutable
  revision `900bb17bee0d80949da98675dc369e9e28a1846c`。
- Cloud 先以 0 basis points 原子登记并完成公网 GET/HEAD/ETag/304 与双源完整预检，随后将
  同一 `build2251-test` rollout 提升至 `10000`。最终生产清单 SHA-256 为
  `3e3cecaa8a2aaf4f58e6c7a2ac5de4331ff28b026ad2f155f0b8ecb937e1a5dd`。
- 完整不可变回执见 `docs/ai2apps-desktop-build-2251-release-receipt-2026-09-20.md`。剩余验收只包括
  目标 Mac 的 2249→2251 自动发现、下载、安装、启动与更新后清理；不影响分发发布已完成的事实。

- 发布前生产基线：`0.1.0 (2249)`；正式版本：`0.1.0 (2251)`，`arm64`、`cloud` Runtime profile、
  `com.ai2apps.desktop`、instance `default`、`SANDBOX_MODE=0`。Build 2250 保持内部候选，
  不提升、不覆盖。
- 纳入本版的 Desktop/Local 用户能力：
  `NXR-DISCOVER-LEGACY-INSTALL-20260920`、`NXR-ACPF-ACTION-BREATHE-20260920`、
  `NXR-ACPF-SUCCESS-CONFIRMATION-20260920`、`NXR-DISCOVER-DOWNLOAD-TELEMETRY-20260919`、
  `NXR-PACKAGE-PARALLEL-DOWNLOAD-20260919`、`NXR-RESTART-AI2APPS-LABEL-20260919`、
  `NXR-DEEPSEEK-V4-SSD-AUTO-TIER-20260919`、`NXR-ADAPTIVE-DOWNLOAD-20260919`、
  `NXR-DOWNLOAD-PROGRESS-20260919`、`NXR-GALLERY-PAN-BOUNDS`、
  `NXR-IMAGINE-GALLERY-VIEWER`、`NXR-SHARED-CHECKPOINT-CACHE`、
  图片模型公共 Checkpoint 布局验证、Imagine Studio 配置后本地模型发现、
  ACPF 公共弹窗国际化、`NXR-052` Gallery 菜单、`NXR-051`、`NXR-050`、`NXR-048`、
  `NXR-047`、`NXR-043`、`NXR-042`、`NXR-041`、`NXR-038`、`NXR-034`、`NXR-035`、
  `NXR-036`、Studio/Mini-App `NXR-037`、`NXR-001` 至 `NXR-010`、`NXR-014` 至
  `NXR-029` 中所有标为 `ready` 的项目、`NXR-031`、`NXR-032`、`NXR-033`、Official
  Cloud Connector `NXR-037`、Launcher `NXR-039`、Voice Studio `NXR-040`、`NXR-045`、
  Video Studio `NXR-046`、Studio 列表 `NXR-052`、`NXR-ZIMAGE-BASE`、
  `NXR-IMAGE-CAPABILITY-SPLIT`、`NXR-SHARED-CHECKPOINT-REUSE` 与
  `NXR-ORNITH-FULL-SSD`。其中已经由独立 Runtime/Package 交付的部分不在 Desktop DMG
  重复内嵌大型推理 Runtime 或 checkpoint；Desktop 只交付 Host、目录、安装与 UI 合同。
- 纳入与已发布 Package/Runtime 对齐所必需的客户端合同：
  `NXR-MODEL-REASONING-CONTRACT-20260919`、`NXR-MODEL-PACKAGE-STREAM-CODEC-20260920`、
  `NXR-QWEN36-TIERED-PRESPLIT-20260920`、`NXR-FLUX2-KLEIN-9B`、
  `NXR-CHAT-SSD-CHECKPOINTS-20260914` 与 `NXR-PACKAGE-CHAT-METRICS-20260918` 的已发布、
  已回归或已实机验收部分。2026-09-20 用户已确认 DeepSeek V4 `auto`、Chat 性能指标、
  Runtime/Package 重启恢复、完整自适应下载和 ACPF/Discover 成功流程；未据此宣称所有模型、
  Rush 按压或所有大型 checkpoint 均完成逐一实机验收。
- 明确延期且不作为本版 Release note 的项目：`NXR-DEV-TEST-REBUILD-20260920` 与
  `NXR-PUBLISH-LIVE-SESSION-20260919`（开发/发布工具）；Ideogram JSON 提示词后续 Package；
  Z-Image 未完成的 UI 重试；`NXR-049` 视觉复核；Cloud Work complexity `NXR-046` 的完整
  Work 端到端；aria-label `NXR-044` 的 Accessibility Inspector；测试实例 `NXR-040` 的剩余
  P0 队列；`NXR-011`、`NXR-012`、`NXR-013` 的未验收阶段；`NXR-030` 的 Package 重建；
  所有 DSV4.1 L1/L2、miss/resume、ICB、性能实验及未切入生产默认的研究路径。延期代码若作为
  dormant development/experimental source 存在，不得在生产配置、目录或 Release note 中启用或
  宣称已交付。
- `NXR-RELEASE-ALL-20260911` 由本次 Build 2251 正式门禁取代；`NXR-INTERNAL-2250` 保留为
  历史内部证据。Build 2251 必须从 clean、已推送 commit 重建，重新跑全量 Python、Swift、
  JS/静态门禁，比较 2249 最终 DMG 与候选 staging 内容，并完成签名、公证、双源、Cloud 与
  2249→2251 实机升级验收后才能标记发布完成。
- 2026-09-20 正式源码门禁通过：Python 完整回归 10,050 passed / 67 skipped /
  74 deselected / 0 failed；AI2Apps Test System 80 passed / 1 skipped；Node 前端专项
  4/4；Swift 壳层 77/77。这些是候选源码门禁，不代替后续 App/DMG
  签名、公证、双源回读、Cloud 清单和 2249→2251 实机升级验收。
- 发布前门禁发现并修复 `NXR-FLUX2-KLEIN-9B` 的真实客户端缺口：Imagine
  Studio 现在为 FLUX.2 Klein 9B 的图片生成和编辑都提供明确 ACPF 安装方案，
  固定 Runtime `>=1.7.8,<2.0.0`、Package `>=0.1.0,<1.0.0`、Checkpoint `/9b`、
  48 GiB 最低设备门槛及 FLUX 非商业许可提示；中英文 ACPF 文案同步补齐。

### NXR-VERIFIED-OVERLAY-CHECKPOINT-READINESS-20260921：增量 Checkpoint 激活

- 状态：`ready`（107 项相关回归及 App-Dev OpenVDN DMD 8-step Q4 实机重试通过）。
- 修复已完整安装的 Registry 增量/overlay checkpoint 被通用独立模型布局探针误判为不完整的问题。
  OpenVDN 的 5.09 GB checkpoint 已通过签名分发清单校验，但权重位于
  `stage-dmd-step-250/` 等子目录，根目录按设计没有独立模型所需的 `config.json` 和
  safetensors，因此旧逻辑向 Worker 输出空路径并在 ACPF 95% 报
  `The model provider did not become ready after activation`。
- 同一缺陷覆盖 H3 的四个增量变体：LightX2V 4-step、LightX2V 8-step、OpenVDN
  DMD 8-step 和 OpenVDN Stage-B 50-step；本次通用修复一次覆盖四者。FL2VA Q4/Q8 与
  Ref2VA Q4/Q8 是完整 checkpoint，继续走既有独立模型布局校验，不受原缺陷影响。
- 模型感知校验现在接受与 Package 声明 `distribution_id` 精确一致的不可变 Registry
  snapshot，并校验分发格式、manifest digest、完整文件集合、只读常规文件及安装时记录的
  device/inode/size/mtime；任意文件变更、额外文件、符号链接或分发 ID 不匹配都会拒绝。
  普通 Transformer、Diffusers、ONNX 和 SSD Cached-MoE 的既有布局门禁不变。
- App-Dev Local 已通过 Helper 原位重启加载修复；对原失败会话点击 Retry 后直接复用共享
  checkpoint cache，四步立即完成，Worker 配置获得非空 OpenVDN 路径，Video Studio 随后
  识别 `(Local) AI2Apps-MLX · OpenVDN H3 DMD 8-step Q4` 并报告生成环境已就绪。Python
  源码热挂载验证无需重建 App。校验发生在 Desktop Local/Host 的 Service Supervisor，模型
  Package 与 `ai2apps/runtime-omlx` 均无需升版；正式交付需纳入下一版 Desktop App。使用当前
  仓库热挂载的 App-Dev/Dev 只需重启 Local，嵌入固定快照的 Test 和生产实例则需重建或升级
  Desktop App。
- 2026-09-21 已通过标准 `build-test-app.sh` 重建固定 Test App 并启动验收：Bundle ID
  `com.ai2apps.desktop.test`、instance `test`、cloud Runtime、生产更新地址、非 Development
  快照、`verify-release-app.sh` 和深度签名均通过。发布前门禁为 Swift 77/77、相关 Python
  107/107、`git diff --check` 通过；拟纳入 Desktop 0.1.0 Build 2252。

### NXR-VIDEO-TASK-INVOCATION-IDENTITY-20260921：视频后台任务身份分层

- 状态：`ready`（21 项 Video Task、Video Studio 与 schema 定向回归通过；App-Dev 原失败
  OpenVDN DMD 8-step Q4 任务实机 Retry 已越过身份恢复并进入 `generate`）。
- 修复 Video Studio 经 `/v1/videos/generations` 创建的持久任务把任务隔离键
  `ai2apps-user:<UUID>` 直接交给 Cloud 身份仓库的问题；身份仓库只接受 URL-safe 用户 ID，
  因此前一实现会在 Worker 调度前报
  `cloud_user_id must contain 1 to 200 URL-safe identity characters`。
- schema 71 为 `video_generation_tasks` 增加独立 `invocation_actor_id`：登录用户任务用真实用户
  UUID 恢复调度身份，API Key 任务继续以 `local-api:<hash>` 隔离列表、取消和幂等范围，同时
  以 `local` 进入本机后台调度。迁移保留已有任务并把历史 `ai2apps-user:<UUID>` 归属原位规范
  化，Retry 继续继承原始调用身份。
- `VideoTaskManager` 同时兼容已发布 Desktop 内嵌的旧 oMLX 路由与新路由：创建、读取、列表、
  取消、重试和 Join 都在持久层边界统一旧前缀，避免要求开发实例先重建 App 才能恢复任务。
  新 `omlx/server.py` 会直接传递分离后的任务归属与调用身份。App-Dev 只重启了自身 Local，
  schema 实机从 70 升到 71，原任务在刷新后仍可见；点击 Retry 后状态从 `starting` 进入
  `generate`，旧身份错误未复现。此修复不改模型 Package、Checkpoint 或
  `ai2apps/runtime-omlx` Worker Package；Test 与生产需由下一版 Desktop App 带入。

### NXR-DEV-TEST-REBUILD-20260920：开发与测试实例同步

- 状态：`ready`。按用户要求通过标准 `build-dev-app.sh` 与 `build-test-app.sh` 重建固定 Dev/Test App，旧 App 已分别归档；未改动实例数据。
- Dev 保留 `com.ai2apps.desktop.dev` / `dev` 与当前仓库 Development source root；Test 保留 `com.ai2apps.desktop.test` / `test`、cloud Runtime、非 Development 独立快照。Test 内 Registry 源码与当前兼容修复逐字节一致。
- Dev 严格签名验证、Test 标准 release App 验证通过；两实例已启动，本机 bootstrap 均返回 HTTP 200。仅本地开发/测试重建，未发布生产制品。
- 2026-09-25 候选发布前再次从当前工作树重建全部三套固定实例：
  `AI2Apps-dev.app`、`AI2Apps-app-dev.app` 与 `AI2Apps-test.app`。分别通过
  `build-dev-app.sh`、`build-app-dev-environment.sh` 与 `build-test-app.sh`完成原子替换，
  旧 App 进入 `.build/archive`，三个实例的 Application Support/Caches 数据均未重置。
  Bundle/instance 身份、Dev 源码挂载、App-Dev/Test cloud Runtime、Test 非开发模式、
  App-Dev 单橙点与 Test 双紫菱形托盘资源、三包严格深度签名均验证通过。
  三套新 App 已实际启动且 Helper 均进入 `ready`；可见 Shell 身份分别为
  `com.ai2apps.desktop.dev.shell`、`com.ai2apps.desktop.appdev.shell` 和
  `com.ai2apps.desktop.test.shell`，App-Dev 原生标题为
  `AI2Apps-App-Dev: App-Dev 127.0.0.1:58071`。本次仍只是本地实例重建，尚未生成或发布正式制品。
- 2026-09-29 在 Runtime 1.8.5 MoE SSD 压力与进程物理内存统计更新完成后，再次通过固定入口
  `build-dev-app.sh`、`build-app-dev-environment.sh`、`build-test-app.sh` 从当前工作树重建
  Dev、App-Dev、Test。旧包分别归档为
  `.build/archive/AI2Apps-dev-20260929-035135.app`、
  `.build/archive/AI2Apps-app-dev-20260929-035301.app`、
  `.build/archive/AI2Apps-test-20260929-035427.app`；三个实例的 Application Support、Cache
  与共享 checkpoint 均未重置或删除。
- 三包的固定 bundle/instance/Development/source-root/cloud-Runtime 身份与严格深度签名通过；
  App-Dev、Test 另通过完整 `verify-release-app.sh`。Dev 是不含正式 Release 许可证目录的轻量
  Development bundle，使用其专用构建门禁和深度签名验收。App-Dev/Test 内嵌
  `omlx/engine/ssd_telemetry.py` 与 `ai2apps/proc_memory.py` 均和当前源码逐字节一致。
  三套新实例已启动，App-Dev `127.0.0.1:50721`、Dev `127.0.0.1:50910`、Test
  `127.0.0.1:50906` 的 `/health` 均返回 `healthy`；App-Dev 原生标题确认是
  `AI2Apps-App-Dev: App-Dev 127.0.0.1:50721`。本次只更新本地开发/测试实例，不产生新的
  Desktop Release。

### NXR-DISCOVER-LEGACY-INSTALL-20260920：旧模型 Package 安装计划兼容

- 状态：`ready`（104 项 Registry/Discover 回归通过，App-Dev Local 已重启加载；未执行实际模型下载）。
- 修复目录装饰器把 modelInstall/modelProfile 解析依赖于 discovery 分类成功的问题。三类元数据现在独立解析，保留各自签名声明及旧版本映射边界；Flux 4B 0.1.4、Flux 9B 0.1.0、Ideogram、Qwen Image、Z-Image 等无需重新发布 Package 即可进入已有 ACPF 安装流程。
- 覆盖 7 类模型的计划/会话 API、全部旧版安装映射、未知 Package 与超版本拒绝。签名、Checkpoint 校验和许可确认流程不变。Python 改动仅需 Local 重启，无需重建 App。

### NXR-ACPF-ACTION-BREATHE-20260920：主操作按钮呼吸提示

- 状态：`ready`（CSS 与静态检查完成，待用户视觉反馈）。
- 共享 ACPF 的可见且可用主按钮增加 2.4 秒柔和阴影呼吸，覆盖继续、确认下载/许可、重启、重试和安装成功后的完成按钮。隐藏/禁用按钮不播放；悬停和键盘聚焦时保持稳定高亮，焦点轮廓保留；系统减少动态效果时使用静态光晕。只改变阴影，不改变按钮位置或文字对比度。
- 更新所有直接引用共享 CSS 的入口资源版本；纯样式修改，刷新页面生效，不需要 Local 重启或 App 重建，不改变安装/授权行为。相关 diff whitespace 检查通过。

### NXR-ACPF-SUCCESS-CONFIRMATION-20260920：安装成功后确认关闭

- 状态：`ready`（前端实现、自动化测试和 App-Dev 实机安装完成页验收均通过）。
- ACPF 到达 ready 后停止轮询，保留对话框并显示“安装成功”、可开始使用说明、100% 进度与“完成”按钮。点击完成才 resolve configured result/恢复调用方后续动作，保留原 completion policy 与 acknowledge-return 语义；ready 状态忽略过时的取消/重试点击。刷新恢复的未确认 ready session 同样展示成功确认；已就绪能力 probe 的 already_ready 快路径保持不弹安装框。
- 共享逻辑覆盖 Chat、Discover、Studio 等 ACPF 入口；新增三条文案覆盖全部 9 个语言目录，并统一更新 7 个入口的共享脚本版本以避免旧缓存。
- 验证：48 项 ACPF/本地化回归通过；Node 控制流测试覆盖下载变为成功、刷新恢复成功、未确认不关闭、不提前恢复动作、点击后正常返回且停止轮询。纯前端改动，刷新对应页面生效，无需重启 Local 或重建 App；未操作当前安装。
- 2026-09-20 用户完成 App-Dev 实机验收：Chat ACPF 的 DeepSeek V4 安装四步均进入 Completed，成功页保持可见直至点击 Done；Discover 的 FLUX.2 Klein 4B 安装成功页同样正确显示三步 Completed、100% 进度和 Done。验收中发现的问题已修正，Runtime 已升级。

### NXR-DISCOVER-DOWNLOAD-TELEMETRY-20260919：Discover Package/Checkpoint 下载统计

- 状态：`ready`（代码、自动化验证及 Local 重启后的 App-Dev 实机界面验收通过）。
- 已确认 Discover Package 使用 Registry 四块并行及两次同源连胜优选策略，Checkpoint 委托共享 ACPF 自适应下载链路。截图处于权限审核，下载已结束；此前页面只在下载阶段基于轮询估算速度，后续阶段清空显示。
- 新增共享后端 DownloadProgress：Package 和 Checkpoint 基于收到字节提供最近 5 秒速度、剩余下载 ETA、文件及总字节；续传基线不计入速度，重试回退重置采样，Checkpoint 跨文件使用总计。Installer task 和 ACPF 传递统计，Discover 下载时明确显示速度与 ETA，校验/授权阶段保留最近传输尺寸及最近速度并移除 ETA；ACPF 同步保留最近传输摘要。无后端新字段时保留旧页面采样兼容，过期实时统计归零，避免继续展示陈旧速度。
- 验证：129 项 Registry/Checkpoint/Acquisition/ACPF/本地化回归通过；新增统计与 Installer 取消共 3 项通过；Node 速度格式行为、Discover 实际 install 方法从下载到审核显示、模型委托 ACPF 行为测试通过；新增后端统计后的 ACPF 定向复测通过。
- 修改 Python 下载器/Installer/Orchestrator、共享 JS、Discover JS/template、中英文文案及测试。Discover 静态资源版本已更新。当前安装授权流程不自动批准或重启；完成当前安装后重启 Local 并刷新 Discover 生效。未修改 Cloud 或发布制品。
- 2026-09-20 用户完成 App-Dev 实机验收：下载面板正确显示当前文件 `experts/layer-000.moe`、当前文件百分比与字节数、总下载百分比与字节数、实时速度和 ETA；Discover 安装完成页及 Package 状态同步正常。

### NXR-PACKAGE-PARALLEL-DOWNLOAD-20260919：Runtime/Package 并行分块

- 后续选源规则：按分块顺序统计校验成功的竞争胜者，同源连续胜出两块后，后续预取只请求该源，保留最多四块并行；已发出的竞争请求正常收尾。选定源传输失败/超时/坏哈希导致请求耗尽时，清空优选及连胜记录并恢复多源竞争；使用选源轮次隔离旧在途结果，防止故障前结果重新锁定失效源。新增连续胜出、交替胜出不锁定、选定源失败后重新竞争并锁定备用源测试，Registry/ACPF 共 80 项通过。2026-09-20 已完成 App-Dev 下载、重启及状态恢复实机验收。

- 状态：`ready`（实现、77 项定向回归、完整 Runtime 实网对比及 App-Dev 重启状态恢复实机验收通过）。
- Registry Package 下载由逐块串行改为最多 4 个不同块同时下载；保留每块多源竞争与 SHA-256 校验，并按顺序 fsync 落盘和持久化连续已校验前缀，兼容原有续传文件。预取窗口按 32 MiB 预算缩减并发（单个更大的合法块仍可下载）；进度汇总在途块且不重复累计竞争源流量。
- 失败/取消清理所有预取请求，取消期间等待已开始的后台落盘及状态写入结束，防止旧写入与后续续传冲突。保留最终完整制品 SHA-256 校验和安装签名流程。
- 实网完整 Runtime 1.7.5（373,254,507 bytes）对比：串行 120.31 秒 / 2.96 MiB/s，四块并行 82.75 秒 / 4.30 MiB/s，两次完整 SHA-256 均与已发布制品一致；临时下载文件已清理。当时模型下载同时运行，结果仅代表此次共享带宽条件，不能承诺固定提速倍数。
- Registry 与 ACPF 定向回归 77 项通过，diff whitespace 检查通过。涉及 `ai2apps/packages/registry.py`、`tests/test_ai2apps_registry_v1.py`；新增四块实际重叠、乱序完成仍有序写入、进度边界、失败清理及取消中落盘持久化测试。App-Dev 已有进行中的模型下载，因此本轮不重启 Local；下载结束后的下一次 Local 重启加载此修改，无需重建 App。不修改 Cloud、不发布、不自动开始模型下载。
- 2026-09-20 用户确认 Runtime/Package 并行下载及 AI2Apps 重启后的安装状态恢复均通过；Runtime 已升级至已发布的 1.7.8。

### NXR-MODEL-REASONING-CONTRACT-20260919：强制思考模型协议化（in_progress）

- 新增签名的 `ai2apps.reasoning/v1` 模型契约；对话模型 Package 可声明
  `required / optional / none`，并由 Host 校验后公开到模型目录。Runtime 不再忽略
  `chat_template_kwargs`；`required` 会覆盖客户端 Thinking Off，从生成首 token 起把
  `think_tags` 分流为 `reasoning_content` 与 `content`，同时兼容模型省略 `<think>`、只返回
  `</think>` 边界的输出。非流式响应使用同一分离规则。
- Runtime 候选升至 1.7.5；全部现役 oMLX 对话模型 Package 同步完成显式契约：DeepSeek
  V4 Flash 0.3.4、Ornith 0.1.4、DeepSeek V4 Flash 2-bit 0.3.5、DeepSeek V4.1 Flash
  0.1.1、GLM-5.3 Flash 0.1.5、Qwen3.6 0.3.4、Qwen3.8 27B 0.3.3、Qwen3.8 Flash
  Next 0.1.4。DeepSeek V4 两个量化版本、Ornith 与 GLM 均声明
  `mode: required`，携带自己的 Jinja chat template，把 assistant generation prompt 从旧的
  `<｜Assistant｜></think>` 修为 `<｜Assistant｜><think>\n`；客户端即使残留 Off 设置也不能
  关闭强制推理；Ornith 与 GLM 沿用 checkpoint 中已经正确开启 `<think>` 的模板。DeepSeek
  V4.1 与三个 Qwen Package 声明 `mode: optional, default_enabled: true`。V4.1 专用引擎不再
  硬编码 `thinking_mode="chat"`，而是映射签名契约和请求的 `enable_thinking`。Checkpoint 与
  权重均不变。
- 开发规范要求新建或升级的 LLM/VLM Package 必须声明真实思考策略；App/Mini-Entry 不得按
  名称或偶然标签猜测，`required` 应禁用 Off，`none` 应隐藏 Thinking。发布测试必须覆盖
  Prompt、流式/非流式分流、缺失开标签恢复和多轮历史。
- 共享 Runtime 1.7.5 已完成 Developer ID 签名、Apple 公证、staple、Gatekeeper 与 Publisher
  签名，并先于八个依赖模型 Package 发布；九个制品的公网匿名回读均确认 exact bytes 与
  envelope 完全一致，Registry metadata version 176。隔离安装最终 Runtime 与 DeepSeek V4
  0.3.4 后 Worker 达到 running，依赖锁精确指向已发布 1.7.5 digest。生产 Cloud 暂不接受
  可选 `modelInstall` 外层投影，最终模型制品使用标准兼容开关省略该投影，Package 源码与签名
  `service.yaml` 保持真实声明，客户端 fallback 严格限于本次版本。完整回执见
  `docs/ai2apps-mlx-runtime-1.7.5-reasoning-contract-release.md`。App-Dev/Test 交互式多模型推理属于
  后续客户端部署验收，不改变本次已发布 Registry 制品。
- 发布后 App-Dev 实机发现 GLM 0.1.4 的 Cache-MoE recipe 漏掉强制的
  `engine.scope_pack`，ACPF 在 checkpoint 下载前 45% 报
  `Preparation engine.scope_pack must be Package-relative`。0.1.5 已补入绑定现有 profile
  SHA-256、模型 ID 与固定 revision 的 Package-owned scope pack；91 项定向回归通过，最终
  Chat ACPF profile 下限同步提高到 `>=0.1.5,<1.0.0`，Retry 会升级已安装的坏版 0.1.4；
  最终签名制品 SHA-256 为
  `dfc5761347bd1e7fc8a41a57a723460656c63694696821326a24ce64f9b1fdbd`。隔离安装精确 Runtime
  1.7.5 + GLM 0.1.5 后 Worker 达到 running，依赖锁正确。0.1.5 已使用精确版本授权通过标准
  live Shell BiDi 发布路径完成生产发布，submission
  `bee627d6-0aa4-423c-881c-33dbf8689fa7`，Registry metadata 177；匿名回读的制品字节与
  Envelope 均完全一致。固定 App-Dev Local 已单独重启并加载最新 Chat，安装向导可见 GLM，
  Profile 明确要求 `>=0.1.5,<1.0.0`；为避免未经请求下载约 181 GB checkpoint，验收停在确认前。
  详见 `docs/ai2apps-glm5-3-scope-pack-hotfix-0.1.5.md`。
- DeepSeek V4.1 实机随后暴露独立的流式解码缺陷：专用引擎使用
  `skip_special_tokens=True` 同时删除 `<think>`/`</think>` 边界，并把未完成 UTF-8 的临时
  U+FFFD 当成稳定前缀；下一个 token 修正前缀时又重放整段文本，导致正确的
  `reasoning_content` 同时重复进入 `content`。现已保留思考边界、显式排除 EOS、延迟 U+FFFD
  并强制 append-only delta；11 项 Runtime/Worker 回归通过。固定 App-Dev 已按规定脚本重建，
  仅重启 `app-dev` Local 后真实请求 `请只回答：你好` 的 UI 正文仅为 `你好`，持久化记录也
  确认推理与正文严格分离。此修复不追溯修改已发布 Runtime 1.7.5；Runtime 1.7.6 已从
  1.7.5 冻结发布源仅叠加该 decoder 文件，排除工作区无关原生二进制变化。Apple 公证
  `06b63e09-2d23-47c5-91b2-f6fbf7ea79a4` Accepted，staple/Gatekeeper 通过；生产 submission
  `8a9f69d0-4512-4e3b-bdbb-ad9c0cce2f98` 已发布，Registry metadata 178，匿名回读 artifact
  与 Envelope 完全一致。隔离安装 Runtime 1.7.6 + DeepSeek V4.1 0.1.1 后 Worker running，
  依赖锁精确指向发布摘要；无需修改 checkpoint 或模型 Package。大型 Runtime 暂沿用 1.7.5
  的 Cloud 单源，后续需在单独授权下补齐 GitHub/ModelScope 固定源与 Cloud 激活。详见
  `docs/ai2apps-deepseek-v41-thinking-stream-fix-2026-09-19.md` 与
  `docs/ai2apps-mlx-runtime-1.7.6-deepseek-v41-stream-release.md`。

### NXR-MODEL-PACKAGE-STREAM-CODEC-20260920：模型输出策略下沉到纯 Python Package（published）

- Runtime 与模型 Package 的边界已固化：Model Worker Package 只允许签名 Python 策略和数据
  资产；MLX/oMLX、tokenizer 原生实现、Metal kernel 与执行器继续由 Runtime 提供。Contract v1
  构建/验包及旧 Service Archive 验包都会拒绝 `.so/.dylib/.metallib/.node` 等原生载荷和
  Model Worker 的 `native_artifacts` 声明，错误码
  `model_worker_native_payload_forbidden`。
- Runtime 新增版本化 `ai2apps.model-stream-codec/v1` 及默认
  `PrefixTextStreamCodec`。`OmlxChatAdapter.create_stream_codec()` 默认返回 `None`，因此已发布
  Package 继续使用 Runtime 当前 decoder；以后新建或升级的 Package 可仅用纯 Python 覆盖
  token 前缀解码和 append-only delta，不需要复制或升级 Runtime 原生代码。DeepSeek V4.1 专用
  引擎已接入该 hook；当前模型 Package 全部不升版。
- Runtime 候选元数据升至 1.7.7，并新增 capability `model-stream-codec-v1`；模型 Package 手册已
  写入强制边界、API 示例、兼容策略及测试矩阵。69 项定向回归、Ruff 与 diff whitespace
  检查通过；未修改的 DeepSeek V4.1
  0.1.1 经标准构建器原样构建成功。标准 Runtime 构建器已产出 361,684,836-byte 的 ad-hoc
  1.7.7 开发制品，SHA-256 为
  `4a4d0d76c03246ca4bb1d7bd84d9aaa7bc452a0d711aa0d0942b9c833a909df8`，并由旧 Service
  Archive inspector 重新验包通过。
- 固定 `AI2Apps-app-dev.app` 已按标准脚本重建并保留 `app-dev` 数据；旧 App 归档为
  `AI2Apps-app-dev-20260920-000836.app`。深度严格签名验证、bundle/instance 身份、Bundle 内
  codec/hook 文件均通过；实时原生标题为
  `AI2Apps-App-Dev: App-Dev 127.0.0.1:51268`，Local 健康检查返回 `healthy`。
- Runtime 1.7.7 已完成 Developer ID 冻结；Apple 公证
  `b15b7da5-0eec-4afb-aad6-6279e131220d` Accepted，staple/Gatekeeper 通过。生产 artifact
  SHA-256 为 `f1b8d19e6befcb9c604bf975fd6dbdd3bb055db8a78fa83c17ef3e498dfc9408`，
  Cloud Submission `9b85c590-199c-4ec4-80e7-f87d10fc4392` 已发布，Registry metadata 179；
  匿名回读 artifact bytes 与 Envelope JSON 完全一致。当前模型 Package 与 checkpoint 均未升级。
  候选与生产回执分别见 `docs/ai2apps-mlx-runtime-1.7.7-model-stream-codec-candidate.md`、
  `docs/ai2apps-mlx-runtime-1.7.7-model-stream-codec-release.md`。

### NXR-QWEN36-TIERED-PRESPLIT-20260920：Qwen3.6 Tiered 预拆分专家 bank（published）

- Qwen3.6 SSD reader 会把 Top120 + Tail24 直接写入 `switch_mlp` 与
  `tail_switch_mlp`；文本模型 sanitizer 此前仍只接受 256-row 全量 bank 或 144-row 临时合并
  bank，因此把合法的 120-row 主 bank 误报为 checkpoint 损坏。VLM sanitizer 已有正确的预拆分
  兼容逻辑。
- Runtime 文本路径现与 VLM 对齐：当主 bank 数量等于 resident experts、tail bank 已存在且数量
  匹配时直接接受；全量 256 与旧 144-row 合并格式继续兼容。新增真实 Top120 + Tail24 回归。
- 34 项 Qwen3.6 定向测试通过；Cache-MoE Worker、Inference Runtime Package 与 Runtime builder
  的 24 项相关回归通过。另一个既存 DeepSeek 2-bit adapter 测试独立运行仍失败，与本差异无关。
- 已发布 Runtime 1.7.7 不可变，本修复归入 1.7.8 开发候选；Qwen3.6 0.3.4 模型 Package 与
  checkpoint 不需要升级。标准 Package Manager 已把 1.7.8 开发候选安装到 App-Dev，启动时
  原子激活新 Runtime 并把 Qwen3.6 等兼容模型锁迁移到候选 digest；实际 Qwen3.6 Worker 已确认
  从 1.7.8 路径运行，真实 Chat 请求返回 `40` 且 Prefill/Token Gen 指标非零，旧专家数量错误未复现。
- Runtime 1.7.8 已完成 Developer ID 签名、Apple 公证（Submission
  `54b2c19c-45d8-4648-a550-270a1b815feb`）、staple、Gatekeeper、Publisher 签名与 Cloud
  发布；Cloud Submission `319cad86-d84d-4992-a16a-8a0bb53dee77`，Repository metadata
  version 180。匿名回读确认 artifact bytes 与 envelope JSON 完全一致。正式回执见
  `docs/ai2apps-mlx-runtime-1.7.8-qwen36-tiered-presplit-release.md`。
- 同一生产制品已原样上传到 GitHub 固定 tag `package-runtime-omlx-v1.7.8` 和 ModelScope 固定
  revision `9a6411755593810876673cd594e085c169048f26`；两端元数据、匿名完整下载 SHA-256 与
  首/中/尾/单字节 Range 均通过，GitHub 为标准 206，ModelScope 为严格 `200 + Content-Range`。
  Cloud 进一步完成每个外部源的完整文件、45 个 8 MiB piece 与 48 次 Range 校验并激活：
  ModelScope `src_9a0c8006-02a1-4072-89b7-ac7dd2ba130b`，GitHub
  `src_7d273abf-119c-44df-afe9-5af509c82e69`。最终 Cloud + ModelScope + GitHub 三源均为
  active，Repository metadata version 182，Snapshot digest
  `ab0756465380540977ee446ad9cdb7aae7fb3ecdb1e7b2030572d0cacffe78d8`；匿名回读再次确认
  artifact bytes 与 Publisher envelope 精确一致。
- 2026-09-20 发布前综合复验发现两项 Installer 测试仍固定旧的 Qwen3.6 普通 Hugging Face
  仓库与 revision；产品代码和签名 Package 已正确使用 SSD 合同
  `Avdpro/Qwen3.6-35B-A3B-4bit-SSD@c6b2081c394f6c1270b243eb77292e70769af341`。
  仅将测试夹具和断言更新到现行合同后，下载/Checkpoint/Registry/Installer/Provisioning/
  Model Manager/Chat Adapter 合计 196 项全部通过；ACPF 成功确认、Discover 下载统计和传输
  进度 3 项 Node 测试全部通过。未修改产品运行行为或已发布 Package。

### NXR-RESTART-AI2APPS-LABEL-20260919：安装完成后的重启文案（ready）

- ACPF 安装向导、Discover 安装完成、Package 卡片待激活状态及 Chat 模型激活提示不再显示
  内部组件名 `Restart Local / 重启 Local` 或 `Restart local service / 重启本地服务`，统一改为
  用户可理解的 `Restart AI2Apps / 重启 AI2Apps`，
  避免被理解为重启整台电脑。英文、简繁中文、西班牙语、法语、日语、韩语、葡萄牙语和
  俄语资源已同步；Discover 内建 fallback 同步更新。
- 仅修改直接加载的 JavaScript 与本地化资源，刷新 Shell 页面即可生效，无需重建 App。

### NXR-DEEPSEEK-V4-SSD-AUTO-TIER-20260919：SSD Checkpoint 自动内存档位修复

- 状态：`ready`（Runtime 已完成 Apple 公证、Cloud 发布和 GitHub/ModelScope 三源激活；App-Dev 安装后的 `auto` 真实推理与 Chat 性能指标实机验收通过）。
- App-Dev 的 DeepSeek V4 Flash SSD checkpoint 使用新布局标识
  `ai2apps-ssd-checkpoint`；Runtime 自动档位估算只识别旧
  `ai2apps-backbone-expert-store`，因此把约 12.2 GiB 骨干误当完整模型，看到 Lean
  约 32.7 GiB 后错误判定三档均无效。修正后按骨干加 43 层外置专家计算完整模型约
  156 GiB；128 GiB 设备在保留 20% 系统/KV 空间后自动选择 Optimal Top60，估计驻留
  约 53.6 GiB。
- 受限 App 进程不能启动 `sysctl` 时，物理内存探测新增 POSIX page-count 回退，避免无
  MLX 的控制面误降为 8 GiB。旧布局、新 SSD 布局和 Full 外置专家注入均保留。
- 新增档位估算、128 GiB sysconf 回退和 SSD Full 注入回归；当前 66 项定向测试通过，
  真实已安装 checkpoint 的离线复算得到 Lean/Compact/Optimal 全部可用且推荐 Optimal。
  App-Dev 临时显式固定相同的 Optimal Top60 后，真实 Chat 冷启动请求成功返回 `40`，旧
  的无可用内存档位错误未再出现；首次请求约 51.7 秒，Prefill 约 3.0 tok/s、Decode
  约 5.1 tok/s。1.7.4 安装后需恢复 `auto` 再做最终真实验收。
  Runtime 1.7.4 已从正式 1.7.3 冻结源码只叠加上述三个 Runtime 文件构建；内部 DMG
  376,767,222 bytes，SHA-256
  `581ad359a7c107decc7f3ba6deb20d922c086ec3e02cf1118f8bcef5e579a7ed`，Developer ID
  签名与 DMG 完整性通过。Apple submission
  `19430ca1-eaed-494c-87e9-8f0ada32c06c` 已 Accepted；stapled DMG、Stapler、Gatekeeper
  通过。正式 Package 374,581,509 bytes，SHA-256
  `20efe8fb3c97c6bef997918028940da253090a76029b8cbc2b78ffc7ddb4bd4c`；Cloud submission
  `3aca5beb-2c5e-4c33-9345-ec27173c212d` published，Repository metadata 163。
- GitHub 与 ModelScope 公开制品已匿名完整下载，大小/SHA-256 与签名本地制品一致；抽样
  Range 字节一致，GitHub 为标准206，ModelScope为受限兼容的200+Content-Range。GitHub
  Source `src_e89f926a-f465-41ea-82ac-ada4743c5cf9` 已通过48-piece/full SHA/Range门并激活，
  Repository metadata 166、Snapshot
  `fee0a791efbec7b47831538620debd9b32b31f7962e9b516d13aa593c1d59988`。ModelScope 嵌套
  路径登记触发 Cloud INTERNAL_ERROR，未落库；改用既有正式 Runtime 已验证的根路径形状，
  ModelScope 复用同一 blob 产生不可变 revision
  `dc48b9b4c2e44135ad887986a5e60a827ae31fe6`。Source
  `src_5a8dc563-7939-4fd2-865c-897254024c31` 通过48-piece/full SHA及严格
  `http-200-content-range` 门并激活；最终 Repository metadata 167、三源 Snapshot
  `a02cd12584a4f02fe2b8fa5d507584c8034359df9a0dd00c31501d07eaed586a`。匿名 Registry
  回读确认签名、Envelope、本地制品字节完全一致，Cloud/GitHub/ModelScope 均 active。
- 横向审计确认同一布局误判会影响共用 DeepSeek V4 profile 的 4-bit/2-bit Package，
  1.7.4 已同时覆盖；DS V4.1、Qwen3.6、Ornith 不走该判断。GLM 与 Qwen Next 的后续
  Package 0.1.3 已完成真正的自动档位选择：128 GiB 保持 Balanced Top96/Top160，较低内存
  分别降到 Lean Top80/Top128，Qwen Performance 保持显式；低于 Lean 加标准系统/KV 预留
  时拒绝。发布门槛同步为 GLM 72 GiB、Qwen 64 GiB，均依赖 Runtime >=1.7.4。
  GLM submission `44e3091a-638c-459b-851e-10ef9f2b3764`、Qwen submission
  `ac46844c-34dc-4598-84f1-22bb37c6eab3` 均 published，Repository metadata 最终为165；
  SSD checkpoint distribution 未改。两套 Package/Contract/Discover 80项与发布/Runtime
  builder 32项通过，128 GiB 实机 resolver 均选择 Balanced，归档无权重或原生载荷。
- 2026-09-20 用户在 128 GiB App-Dev 环境完成最终实机验收：DeepSeek V4 Flash 在 `SCOPE auto` 下正常回复，界面显示 Prefill 0.55 tok/s、Token Gen 7.6 tok/s、Thinking 13.1 秒、Duration 46.1 秒及 SSD Pressure 指标。该证据关闭 `auto` 与 Chat 指标验收；不据此额外宣称 Rush 按压控制已验收。

### NXR-ADAPTIVE-DOWNLOAD-20260919：模型下载按吞吐量分源

- 状态：`ready`（实现、回归、真实分块下载对比及 App-Dev 完整模型下载验收通过）。
- Checkpoint 调度取消 piece index 轮流分源；先采样、再按已校验块的传输吞吐量 EMA 和在途请求数排序，异常或坏哈希源降级 30 秒但保留兜底。默认并发 4 → 8，允许显式 1–32；连接池至少 16、keep-alive 60 秒。探测并发有界、单探测超时 15 秒；下载用固定数量 worker，失败/取消等待所有 worker 清理。逐块哈希、落盘确认、跨文件组合回退与断点续传校验保留。
- Checkpoint/Acquisition/Registry/ACPF/本地化共 122 项测试通过。定向测试覆盖较低探测延迟但实际较慢的源、快速坏哈希源降级、取消后无残留请求，以及原有断点续传/范围响应/许可验证；真实 A/B 各取同一签名清单前 32 块（256 MiB），旧四并发轮流分源 29.59 MiB/s，新八并发自适应 29.27 MiB/s，均 32 块完整校验通过。本次网络未复现此前慢 ModelScope，不能声称实测固定倍数提速。数据仅在临时目录，未启动完整下载、未导入候选权重。
- 文件：`ai2apps/checkpoint_distribution.py`、`ai2apps/checkpoint_acquisition.py`、`tests/test_checkpoint_distribution.py`。已通过专属 Helper 重启 App-Dev Local，新 PID/boot ID 验证通过，bootstrap HTTP 200；已下载块保留。无需重建 App；未发布。
- 2026-09-20 用户完成完整模型下载、安装和启动验证；下载过程中自适应多源进度持续更新，完成后模型服务成功进入可用状态。

### NXR-DOWNLOAD-PROGRESS-20260919：ACPF/Discover 下载速度、ETA 与块内进度

- 状态：`ready`（实现、定向测试及 App-Dev 实际下载验收通过）。
- ACPF 与 Discover Package 安装显示最近 5 秒收到字节的平均速度、下载 ETA；续传/任务切换/重试回退重置采样，停滞时速度降至零，ETA 无估计时显示破折号。模型 HTTP Range 每次读取上报块内进度，按并发 piece 汇总并分离收到/已校验字节，失败重试清除临时计数；完整哈希校验不变。
- Package/模型逐块哈希与落盘移出 asyncio 主线程；界面轮询 500ms，进度过渡 500ms，减少块边界跳动。ETA 仅估算剩余下载，不包含安装/启动时间。
- 验证：Checkpoint、Registry、ACPF 与本地化定向回归 110 项全部通过，Node 前端采样行为测试通过，相关 diff whitespace 检查通过；新增块完成前进度与校验后计数、坏源重试不重复累计验证。后续补齐 DeepSeek V4.1 Flash 名称及说明的中英文翻译键，修复 Profile 新增文案未同步字典导致的本地化回归失败；不改 Profile 内容。
- 涉及 `ai2apps/checkpoint_distribution.py`、`ai2apps/packages/registry.py`、ACPF/Discover JS/CSS/template 与定向测试。App-Dev 需重启 Local 并刷新页面，无需为此重建 App；未发布或操作正在运行的下载。
- 2026-09-20 用户实机确认 ACPF 下载中的当前文件、块内百分比、当前/总字节、总进度、速度和 ETA 正确显示，并完成到安装成功状态。

### NXR-PUBLISH-LIVE-SESSION-20260919：发布工具在线读取授权会话

- `in_progress`：标准 Package 发布工具新增显式 `--browser-live`，复用已认证 Shell BiDi broker，核对 Local installation/instance、精确 Profile 和 scoped Cookie；不读 SQLite、不隐式回退、不输出协议/凭据、不结束共享浏览器会话。离线 SQLite 保留为互斥显式选项。更新发布规范，取消将退出 Shell/App 作为常规前置步骤。
- 15 项发布工具测试通过，覆盖 Cookie 名称/域/路径、歧义拒绝、编码校验、错误脱敏、隔离 Profile 和过滤 BiDi 命令；Dev Local 启动后保持 Shell 运行，`--browser-live --publishers-only` 和 `--list-only` 均真实成功，原 Publisher/key active。未读取 SQLite、未退出浏览器。在线工具验收完成；Runtime 1.7.3 与 App-Dev/Test 更新仍在进行。

### NXR-PACKAGE-CHAT-METRICS-20260918：Package Chat TPS 与 Rush 控制

- 2026-09-19：用户授权发布 Runtime 1.7.3、Apple 公证，并更新固定 App-Dev/Test，保留实例数据。1.7.3 manifest/SBOM 已同步；与正式 1.7.2 比对，源代码增量仅共享 Chat Adapter、Worker control endpoint 与 Host boost 路由。109 项回归通过。Dev Installation 会话缺发布权限，精确授权的 Dev Cookie 标准读取暂因数据库锁失败；未提交/发布、未替换实例。
- 候选已由正式 1.7.2 Runtime 源码快照叠加本次 3 文件构建，Developer ID/内外签名通过；Apple 已上传，submission `6212d14b-20c5-4460-933d-6c39f3ca77b5`。恢复记录见 `docs/ai2apps-mlx-runtime-1.7.3-chat-metrics-release.md`；尚无 Cloud submission。
- 后续：Apple Accepted/staple/Gatekeeper 通过，原 Publisher 签名包发布为 1.7.3，Cloud submission `99416633-5c2f-477a-9c8d-f4b986ace281`、metadata 162；匿名完整下载与本地 SHA/envelope 精确匹配。隔离 Qwen3.8 原包安装、依赖锁和 Worker 启动通过。App-Dev/Test 固定脚本重建、旧 App 归档和完整签名校验完成，未重置数据。App-Dev Discover 安装完成，显示 Local/Cloud 1.7.3 并执行 Restart Local。Test 新 App 已启动，等待用户登录后升级 Runtime。多源分发和真实 Chat/Rush 性能验收待完成；当前 Cloud-only，不宣称全流程验收完成。

- 状态：`in_progress`（代码与定向回归完成，待固定 App-Dev 重建后实机验证）。
- 修复：Package 模型目录从可信 checkpoint preparation recipe 声明 Cached-MoE 能力；Host Engine Boost 路由转发到已运行 Worker 的认证 control endpoint，不经过生成队列、不启动新引擎，实际引擎不支持控制/模型不匹配时拒绝。共享 OmlxChatAdapter 输出流式最终 usage 与原生速度；旧引擎缺原生 TPS 时附 Worker 观测估算及来源字段，Chat 缺统计显示“—”。
- 文件：`ai2apps/model_providers.py`、`ai2apps/model_worker/{omlx_chat,server}.py`、`omlx/server.py`、`ai2apps/web/templates/chat.html`、`tests/test_ai2apps_omlx_chat_adapter.py`。
- 分发：未修改模型 Package/权重。Qwen3.8 27B 继承共享 OmlxChatAdapter，统计修复由共享运行代码获得，不需单独修改模型包；其普通 VLM 引擎不因此获得 Rush。现有已运行 Worker 必须重启，App-Dev 因内嵌 omlx 路由变化需固定脚本重建。正式分发须把共享 Local/Worker 源码纳入相应 Desktop/Runtime 制品；未构建、未发布，不宣称旧安装已生效。
- 验证：共享 Chat Adapter、Model Provider、Worker、Chat UI 93 项通过；覆盖最终 usage 原生 TPS、已加载引擎控制/错模型拒绝、控制端点认证与无效参数/不支持引擎拒绝。相关文件 diff whitespace 检查通过。尚未实机验证长回复 Rush 按下恢复与速度数值。

### NXR-GALLERY-PAN-BOUNDS：图片查看器按实际溢出拖拽（ready）

2026-09-14 后续修正：用户实测发现图片缩小偏下且拖动留白不对称。查看区域改为绝对填充 stage，固定 minmax 网格并让图片以 object-fit:contain 填充明确尺寸，避免图片固有高度撑大网格；上下留白统一。允许所有 Zoom 下拖动，四边提供对称 48px 过拽余量，缩小到可容纳时对应轴重新居中；取消拖动 transform 动画以避免延迟。行为测试新增 25% 和正反方向边界对称验证；待实机视觉复核。

2026-09-14：Gallery/Imagine 共用图片查看器移除缩放百分比拖拽门槛，按图片实际渲染尺寸、Zoom 和可视区域计算可拖动轴及边界；缩放后校正位移，完整显示的轴保持居中。图片常态光标为 grab，拖动时为 grabbing。行为测试覆盖 75%、100%、125%、150%、200% 裁切拖动、边界限制及完整显示不拖动。纯前端修改，刷新页面生效，无需重建 App；待实机视觉验收。

### NXR-IMAGINE-GALLERY-VIEWER：输出图复用 Gallery 查看器（ready）

2026-09-14：Gallery 对话框提取为 `_gallery_preview_dialog.html`，Gallery 和 Imagine 共用模板及 Gallery 缩放/平移/下载逻辑。Imagine 输出图支持点击、Enter/空格打开只读查看，不要求先 Add to Gallery，不创建资产；隐藏重命名，限制同源 http(s) 内容，Esc 关闭并恢复滚动与焦点。只读 viewer 不初始化 Gallery 列表/API。`node tests/gallery_result_viewer.test.cjs` 与 JS 语法检查通过；待 App-Dev 页面刷新实机确认。纯前端改动无需重建 App。未修改模型 Package。

### NXR-FLUX2-KLEIN-9B：独立 9B 模型 Package（in_progress）

2026-09-15（发布完成）：9B 0.1.0 submission `747cac69-b127-4efe-b5cc-30fda6216899` published，Registry 138；权重 distribution published / Index 68 签名回读通过。正式 Package 37,886 bytes，SHA-256 `2ce8e4cdde2a0d15053c4e80d749144627d7b2d3429309cc7a490243c465b6b0`，匿名完整下载一致。41 tests passed，精确签名包独立 managed install + Runtime 1.6.2 Worker running。用户本轮明确延后真实媒体处理，不声称新出图验收。发布回执 `docs/ai2apps-flux2-klein-9b-0.1.0-release.md`。Package 发布任务完成；客户端有界安装映射仍需随未来 Desktop 候选验收，故本 ledger item 保持 in_progress。4B 未变。

2026-09-15（继续）：当前 Dev Cookie 发布查询成功，原 Publisher key 非秘密元数据指纹与 Cloud 匹配。补齐 conditional redistribution 的结构化许可/下载确认字段；标准构建器完成签名分发：21 files、34,722,772,164 bytes、4140 pieces，digest `sha256:6e9cfa02ae3a5f710f61479e2476e1653da1552ef957abe2ed076ce8393ac08d`。验证模式为 HF 完整本地字节对 MS 固定元数据，不声称双端完整下载。3 项 Package 测试通过。正在标准提交/审核，尚未声称 Package 发布完成；snapshot 移至 `/private/tmp/92196c8e11f7b6cf2b7493e037d8c5345c559216`。

2026-09-15：完整 HF snapshot 已下载，逐文件 SHA-256 与固定 MS revision 的 21 个文件全部匹配，共 34,722,772,164 字节（不是仅 LFS 元数据对比）。新增 9B 0.1.0 有界安装映射，保留 4B；新增独立身份、adapter 拒绝 4B、许可哈希/双源固定版本三项测试，3 passed（退出时沙箱 Metal 探测警告，不声称真实推理）。Installation 发布查询返回 active user session required；已打开固定 Dev App 的 Account→Security 管理员验证页面等待用户操作。尚未签名/发布，仍需原签名上下文、标准 distribution 构建/发布、managed smoke 和 Package 发布。

最新进展：用户接受上游许可后，官方 Hub 固定 revision 配置下载成功，GatedRepoError 阻塞解除。完整权重下载进行中，路径 `/private/tmp/ai2apps-flux2-klein-9b-source`。ModelScope 固定 revision `429fffab3014811a56c21359f408a155e0bda9e1`，标准分发模块确认 21 个必需文件均有最终 SHA-256，总计 34,722,772,164 字节。已补许可证全文及哈希、NOTICE、SBOM、source lock、pyproject 和分发构建规格；仍未签名或发布，未把元数据检查当作完整字节验证。最终构建时须使用以 HF revision 命名的 snapshot 目录。

2026-09-14：用户要求将 9B 作为独立于 4B 的模型发布，并保留现有 ACPF/Discover 许可展示确认。新增 `packages/ai2apps-model-flux2-klein-9b-mlx` 候选 0.1.0，Package/Service/model ID 独立；复用现有推理模块，adapter 仅接受 9B。4B 未修改。模型权重使用 FLUX Non-Commercial License，不能继承适配器代码的 Apache-2.0。ID/上游身份/JSON/YAML 和四个 Python 模块语法检查通过，未声称推理通过。

固定上游 revision `92196c8e11f7b6cf2b7493e037d8c5345c559216`；官方 Hub 客户端下载配置返回 `GatedRepoError`，当前账号访问不足。没有读取/输出 Cookie、没有签名或发布，没有填写占位 distribution ID。待获得上游权重访问后完成固定双源字节核验、完整许可证/SBOM/source lock、签名分发、客户端安装映射、真实 managed install 和 Package 发布。候选 README 明确标注不可发布状态。

当前生产基线：AI2Apps `0.1.5` Build `2259`；清单 SHA-256 `9ea49e72e57215baaa63d5489394c97c5daa417661dde9784530932c2783da74`

生产清单：`https://coder.ai2apps.com/updates/stable.json`

基线回执：`docs/ai2apps-desktop-0.1.5-build2259-release-2026-10-09.json`

候选 Build：尚未分配；构建时必须严格大于 `2259`

## 1. 用途

本文件只记录“当前生产 Release 之后，已经完成或正在进行、需要评估是否进入下一版
Desktop App 的工作”。它不是长期 Roadmap，也不代替 Git、测试报告或最终 Build 回执。

AI2Apps 经常从混合工作区构建，`git diff` 无法可靠回答某项工作是否已经进入上一版。
因此每项可能改变 Desktop 用户收到的 App、内嵌 Local、Helper、Shell、AceFox、更新器、
Runtime profile、安装行为或发布流程的工作，都必须在完成该项工作的同一轮登记到这里。

登记是默认自动动作，不需要用户另行说“加入台账”。执行开发工作的 Agent 必须在结束当轮
工作前创建或更新相应条目；即使功能尚未完成或被外部条件阻塞，也应分别以
`in_progress` 或 `blocked` 记录。只有未产生任何可发行改动的纯调查、讨论和诊断可以不登记。

## 2. 状态定义

| 状态 | 含义 |
| --- | --- |
| `in_progress` | 实现或验证尚未完成，不能进入 Release |
| `blocked` | 实现已基本完成，但存在明确的外部依赖或验收阻塞 |
| `ready` | 代码、测试、迁移和发布说明齐全，可以进入候选构建 |
| `deferred` | 已明确决定不进入下一版，必须写明原因和目标版本 |
| `included` | 已进入某个完成验收的 Build，并已复制到该 Build 回执 |

`included` 只能在最终公证 DMG、Cloud 发布和目标 Mac 端到端升级完成后填写，不能因为
源码合并、App 构建成功或上传完成就提前标记。

## 3. 下一版候选工作

### Shell 系统显示名称统一（2026-09-25）

- 状态：`in_progress`。仅修改 Dock 缓存标签不能修复 Cmd+Tab 名称；内嵌 bundle
  由 `AI2AppsShell.app` 改为 `AI2Apps.app`，其 CFBundleName/DisplayName/本地化名称统一 AI2Apps。
- 同步 Launcher、Helper 默认浏览器路径、构建、签名、校验与回归用例；保留各实例
  Bundle ID、Instance ID、数据、图标和窗口标题前缀。
- 旧 Dock 固定项须迁移到同一实例的新内嵌路径；重建后验证，不发布生产版本。
- 验证与交付：77 项 Swift、114 项 Shell 回归通过；Dev/App-Dev/Test 均已按标准脚本
  重建，App-Dev/Test release-app 校验通过。原 Dock 固定项已迁移新路径并清除旧 bookmark。
  App-Dev 实机系统名称与菜单为 AI2Apps，窗口仍保留 App-Dev 前缀，首页正常加载。

### Shell Dock 独立启动补齐 Helper（2026-09-25）

- 状态：`in_progress`，需要重建 App 并实机验收 Dock 冷启动。
- AceFox 原生 Shell 入口在启动浏览器前，打开同一外层 App 的嵌套 Helper；
  校验 Shell/Helper Bundle ID、Instance ID，以及沙箱模式的 App Group 一致。
- 使用精确 bundle 路径交由 LaunchServices 复用 Helper，不启动外层 Launcher，
  不使用新实例参数；Helper 的实例锁保留并发保护。
- 文件：`/Users/avdpropang/sdk/moz/acefox-firefox-153/browser/app/nsBrowserApp.cpp`。
- 注意：旧 Swift BrowserLauncher 已不在构建产物中，本次未修改该废弃入口。
- 验证：实际 `make -C obj-aarch64-apple-darwin/browser/app nsBrowserApp.o`
  编译通过；尚未重打包、签名或替换已安装 App，Dock 冷启动仍待端到端验收。
- 2026-09-25 更新：已重新链接并 `mach package`，通过标准脚本更新固定 Dev、
  App-Dev、Test，旧 App 各自归档且保留实例数据。三个内嵌 Shell 直接启动均已带起
  对应 Helper；Dev/App-Dev Local ready，App-Dev 实机标题与首页正确；Test 到达
  Local 登录页。App-Dev/Test 的 release-app 验证及深度签名检查通过。
- 本轮为当前开发工作树的内部实例更新，不是生产发布；其他 NXR 的未验收状态不变。

### NXR-SHARED-CHECKPOINT-CACHE：同机实例共享已验证 Checkpoint（ready）

- 2026-09-18：按用户要求将 Registry Checkpoint 的权重数据迁移为同一存储容器内的
  机器级内容寻址缓存；Dev、App-Dev、Test 和生产实例仍保留独立账号、Package 状态、
  HF Home、可写模型准备目录及 Worker 视图，但由 Supervisor 注入同一个
  `AI2APPS_CHECKPOINT_CACHE_ROOT`。下载按 distribution identity 使用跨进程非阻塞文件锁，
  获锁后重新检查完整只读 snapshot；并发安装相同 checkpoint 时只允许一个实例访问
  HF/ModelScope，其他实例直接命中共享结果。已有实例私有 `checkpoint-cache-v1` 作为一次性
  验证导入源，可无网络迁移到共享池。
- 实例“重置数据”继续删除该实例的 Support/Cache 根和 Worker 视图，但共享 Checkpoint 根位于
  `Library/Caches/AI2Apps/shared/checkpoint-cache-v1`，由路径边界显式保护；App-Dev/Test 重置
  对话框同步说明共享 Checkpoint 保留。升级前的实例私有缓存会在重置前原子移动到共享保留区；
  未重置的各实例旧缓存和保留区均作为全机验证导入源，另一实例已有同一 distribution 时不走网络。
- 2026-09-18 验收：Python Checkpoint/Provisioning/Shell 定向回归 200 项通过，Ruff 通过；Swift
  Contracts/Supervisor/Helper 全套 77 项通过。新增真实独立 Python 进程 `flock` 排他测试，并以
  两个 Acquisition Service 并发验证网络请求量等于单实例基线、结果为一次下载加一次 cache hit。
  固定 `AI2Apps-dev.app`、`AI2Apps-app-dev.app`、`AI2Apps-test.app` 均由规定脚本重建并通过签名/
  Release App 校验；Dev 与 App-Dev 已以新 Helper 和新 Local 重启。共享根已建立；存量缓存的
  后续整理与删除结果见下一条。
- 2026-09-18 本机存量整理完成：17 份实例 manifest 合并为 11 个唯一 distribution，
  242,531,923,853 逻辑字节全部完成共享端 size/SHA-256 复验；共享池最终有 11 个 manifest、
  11 个 snapshot，`du` 约 203GiB。复验 0 错误后删除 app-dev/dev/test/main 与三个历史
  dev-acpf 实例的 7 个私有 `checkpoint-cache-v1` 根，最终扫描无残留。迁移工具的成功删除与
  失败全保留测试 2 项通过，Ruff 通过；删除后 Punctuation distribution 强制断网 acquisition
  返回 `cache_hit=true`、`source_bytes={}`。完整回执见
  `docs/ai2apps-shared-checkpoint-consolidation-2026-09-18.md`。

### NXR-CHAT-SSD-CHECKPOINTS-20260914：对话模型自有 checkpoint 与 Runtime（in_progress）

- 2026-09-18（App-Dev 首次安装修正）：ACPF 使用正式 Package model ID 请求 Checkpoint，
  而 Cache-MoE Host 配方曾错误地以内部 `install_id` 作为主键，导致 DS4.1 安装在 55% 处报
  `unsupported AI2Apps model`。Host 现以正式 model ID 绑定分发清单，内部 `install_id` 仅用于
  Scope Pack 兼容校验，并保留 `service_key` 供完成后重启 Worker。SSD-ready 路径同时延后旧式
  expert-store 转换模块导入；签名 SSD Checkpoint 的下载和激活不再要求 Cloud 控制面的 Python
  环境安装 `mlx_lm`。89 项模型配方、Checkpoint 激活和 Provisioning 回归通过，Ruff 定向检查
  通过；新增 DS4.1 无 MLX Host 导入回归。App-Dev Local 已重启并实机重试，界面从两次失败
  进入 `Downloading model checkpoint`，HF 固定 revision 已实际返回 206，当前下载写入机器级
  共享 Checkpoint 缓存；总量约 475.27 GB，本机可用空间约 1.5 TiB。

- 2026-09-17（ModelScope严格Range客户端完成）：Cloud OpenAPI 1.50.0发布后，Local/Desktop
  Package与Checkpoint下载器共用严格单区间验证；仅可信ModelScope固定revision接受
  `200 + Content-Range`，精确校验offset/total/length/identity/body，普通200整文件拒绝且有界
  中止，piece/full SHA门不变。75项定向回归及Ruff/compile通过；真实Runtime 1.7.0 MS单源从
  piece 2恢复，45 pieces、373,748,488字节和完整SHA
  `b066700dcebec87012e93de01e6114db9f231b0a1c89642e97c50cd91a1ec3a7`通过；DS4.1 MS
  `experts/layer-0.bin`真实probe与4KiB字节对照通过。Installer扩展回归22通过、2个旧Qwen源断言
  失败，与本改动无关。该代码属于Desktop/Local控制面，已发布Runtime 1.7.0无需重建。MS正式
  Source已登记，Cloud v1.50.0完整验证通过；48次严格
  `http-200-content-range`、完整摘要和45-piece清单均匹配。Dev/App-Dev已加载当前源码，固定
  Test App已重建并通过包内源码等值、嵌入式导入与deep/strict签名验证。Cloud 随后部署策略
  修正；同一管理员step-up激活成功，Source revision 8、Repository metadata 154，匿名固定公钥
  验签确认Cloud/GitHub/ModelScope三源已公开。报告：
  `docs/modelscope-range-client-compatibility-2026-09-17.md`。
  - 后续审计确认该拒绝不是既有 Package 合同：普通 Package/Source 一直允许已完成 step-up 的
    系统管理员自审并写专用审计事件。Cloud 1.50.0 新增的
    `assertCompatibleSourceApprover` 仅对非 standard Range receipt 强制不同账号，来源是本项目
    需求文档误写的双人审批要求。已发布更正需求，要求恢复既有管理员 step-up 语义且保持全部
    Range/piece/完整SHA门禁：
    `docs/ai2apps-cloud-modelscope-range-activation-policy-correction-v1.md`。
  - Cloud生产镜像`ai2apps-cloud:range-policy-20260918`部署后，使用原Source、passed
    validation、digest、ETag和幂等键重试激活成功；Snapshot digest
    `49d0748f75606adf61397106ebcf197316a5d2c1530d9d41a0ac0d7fede515c2`。

- 2026-09-17（七模型发布及兼容性修正完成）：七套 SSD distribution、Runtime 1.7.0 与
  七个模型 Package 已按依赖顺序 published；最终 Repository metadata v153。
  匿名验收确认 DS4 4bit/2bit、Qwen3.6、DS4.1 的公开归档、Repository/Publisher 签名、
  SHA-256、大小、本地字节和 envelope 全部一致。GLM/Qwen Next/Ornith 0.1.1 被发现将
  AI2Apps Contract 最低版本误升到0.1.1，当前0.1.0客户端会拒绝安装；已修正为兼容
  `>=0.1.0 <2.0.0` 并使用原Publisher发布0.1.2。三份修正版均无权重/原生载荷，44项
  专项/Contract/Discover检查通过；全新匿名客户端逐个验证双签名、SHA/大小、本地归档
  字节和envelope一致。0.1.1保留为不可变历史但不可作为可安装交付，0.1.2均为最新版本。
  回执：`docs/ai2apps-chat-ssd-model-packages-release-2026-09-17.md`。

- 2026-09-17/18（Runtime 1.7.0 ModelScope 严格兼容与三源发布完成）：
  `ai2apps/runtime-omlx 1.7.0` submission
  `5553a51b-7cf2-48be-8d66-7e5466be7293` 已发布，Repository metadata 142；GitHub
  同字节制品经 Cloud 全量 SHA-256、Range 和 45-piece 验证后激活，Snapshot 143。
  ModelScope 同字节制品位于不可变 revision
  `18751703b53671cb2db926f9f8ed508a70df15b0`。Local/Desktop 已加入受限的严格
  `200 + Content-Range` 支持，Cloud OpenAPI 1.50.0 已部署对应
  `package-single-range-v2` 门禁。Source
  `src_3125a4d0-27d8-4cfc-a9f2-43b0ec8ad3a2` 经 validation
  `val_9f67323e-596d-46ef-92bb-13ca61e2b53b` 完成全量 SHA-256、大小和 45-piece 校验；
  receipt 记录 48 次 `http-200-content-range`。策略修正后 Source 已 active、revision 8；签名
  Repository Snapshot 154 已匿名确认公开 Cloud/GitHub/ModelScope 三源。发布脚本已增加现有
  Source 恢复验证动作，5 tests passed。Dev/App-Dev/Test 开发客户端均具备兼容能力，无需
  Desktop Release。

- 2026-09-17（Runtime 1.7.0 本地候选完成，外部发布待授权）：七套 SSD checkpoint 已在
  HF Avdpro / MS ai2apps 完成全文件双源验收。Runtime 已增加统一 schema/摘要/范围校验、
  无重复专家库直接激活、正式 DS4.1 文本/视觉 engine，并适配 Qwen Next Full/Cached、
  GLM、DS4 4bit/2bit、Qwen3.6 与 Ornith；八条真实 checkpoint smoke 通过。DS4.1 文本
  和视觉完整 logits SHA-256 与冻结参考一致。Runtime Package 元数据升至 1.7.0；Developer
  ID 签名 DMG 已通过 Apple submission `19de5929-dbb1-486f-a471-8b3038ec8b8b`，stapled
  SHA-256 为 `cf9a645e84c46711392b53d18855f86201fd32cca280dbd1f0c2d66b69748a32`。
  外层正式 Package 已签名并在全新临时实例安装通过，SHA-256 为
  `b066700dcebec87012e93de01e6114db9f231b0a1c89642e97c50cd91a1ec3a7`。Installation
  Cloud session 当前无 active user session；等待 1.7.0 精确 Cookie 读取授权后提交 Registry，
  再继续模型 Package。详见 `docs/ai2apps-mlx-runtime-1.7.0-ssd-checkpoint-signed-build.md` 和
  `artifacts/runtime-1.7.0/build-receipt.json`。

- L2持续训练目标已启动（in_progress）：以全40层真实miss为分母，主要48/次级64个专家总预取预算，目标新会话独立验收≥70%覆盖；先执行缺失加权、缓存/前轮路由输入、rank128/256/512验证集消融，已有测试集不参与调参。尚未达标或集成发布。计划 `docs/dsv41f-l2-continuous-training-plan-2026-09-16.md`。
  - 第一轮最高48预算31.74%；新增rank512无缓存对照32.15%，目标未达成。v3上一token逐层FFN状态pilot精确通过，90序列/16512行补采与分阶段训练运行中，另排队40条/5120行训练扩充。24条新主题会话仅预留，未用于选择。状态预测头可继承已有全局头，数值迁移差9.54e-7；实验尚无真实异步L2或TPS验收。
  - 后续rank1024无缓存验证集48/64预算覆盖33.26%/38.27%；状态小样本微调未超过同会话迁移基线，已将epoch0纳入模型选择以避免负收益。大批采集/训练继续运行，70%目标保持未完成。
  - 滚动提前1层复用官方Router并训练修正，同cohort顺序cap64覆盖51.64%，因果储备策略53.48%，尚无deadline/TPS验收。pre-attention单会话探针均值修正65.95%，仅128行且异步通知机制未验证；正在扩充40会话。大模型采集顺序调度，未同时加载双模型，未修改活动Runtime/Package。目标未达成。
  - 扩大pre-attention验证至1024行后cap64覆盖64.90%；仿射与分数校准未超过各自均值基线。已排队previous-attention因果特征pilot，含精确forward核验；仍为实验脚本/冻结采集快照，未改活动Runtime或Package，独立最终验收未开展。
  - 因果置信度与未来预算储备在2048行验证将cap64离线覆盖提高到71.50%（误读388.93MB/token），cap48为62.05%。仅验证集、同层attention前预测，SSD deadline/异步通知及独立验收均未证明，不标记目标完成，不改生产默认。
  - 完整40会话复核cap64离线覆盖71.35%、误读389.97MB/token。新增隔离Metal完成回调mailbox原型，65packet正确、通知早于synthetic GPU tail结束；尚未实测模型通知开销与SSD READY，不接入活动Runtime。
  - v5 previous-attention两会话精确核验完成，单会话Top6离线68.27%，扩展40会话已排队。真实模型异步通知窗口与输出一致性A/B正在隔离实验中执行；主推理、Runtime和Package均未切换。
  - 真实模型640对异步通知核验通过全部logits/缓存/SSD字节一致，稳态TPS差约0.5%；预测到真实route送达中位仅0.619ms，尚未证明SSD及时完成。提前1层预算策略覆盖提升到57.06%，仍未达目标；v5扩充采集已启动。
  - 提前一层逐特征ridge/逐层低秩模型完成小cohort对照，未超过共享模型57.06%；已启动54序列相同cohort共享/逐层模型训练与预算评估。仅实验训练代码，生产默认不变。
  - 扩大54序列训练完成，共享/逐层提前一层模型均约55.1%（验证cohort已扩大）；新增当前路由条件分支热启动精确，单独训练未超过基线，保留epoch0。v5完成后自动做预算评估，独立holdout仍未打开。
  - 有界跨token L2回放完成，256槽仅保留未消费预测时乐观覆盖60.55%；448槽诊断最高63.66%、有效载荷8.42GB、SSD总读取增加约30%。无deadline/实际footprint证明，未接入默认推理，70%目标仍未达到。
  - 新排序训练未超过基线；训练/验证覆盖67.81%/55.06%，已排队完整补采扩充后的预测器训练，最终holdout仍未使用。小批SSD延迟诊断排在v5采集后，所有改变保持实验隔离。
  - v5完整评估与训练层混合将同层离线覆盖提高到72.83%，但SSD小批实测单专家约1.42ms，超过0.62ms通知窗口，及时READY目标仍未证明；不作为默认方案。原v3采集已恢复，继续更早预测训练。
  - 驻留专家近似预测+精确重算的隔离探针通过logits/缓存/SSD字节一致。短块2/4在单16-token提示离线覆盖79.0%/74.2%，但未接预取且TPS降至3.88/4.13，不能部署或视为达标。原采集已恢复。
  - 真实短块预取已接原native SSD读取与备用槽零拷贝交换，16步精确logits/路由/逻辑缓存一致、峰值60.9GB。普通/严格F_NOCACHE Block4及时覆盖69.15%/68.36%，严格短测约5.65TPS。尚有40/token额外异步通知、未独立验收、未达70%，保持实验隔离。 下一轮显式实验开关对齐预测专家累加顺序并比较短块尾部策略；仅排队，未改默认Runtime。 后续20会话×128token真实预取成对验证已排队，严格65GB/精确输出检查，最终holdout保留。 增加隔离packed回读实验以替代额外通知；尚待模型验证，不作为默认。

- L2 rank128首次训练/独立测试完成（实验未发布）：3292288参数，10轮按验证loss选第9轮；测试集后35层总预算32/48个预取，分别覆盖10.68/13.47个真实miss/token，精度33.36%/28.05%，优于简单基线但误读量仍大。单头FP32隔离预测中位数0.228ms，不代表真实L2延迟/TPS；未接入Runtime。报告 `docs/dsv41f-l2-r128-training-2026-09-16.md`。

- L2 v2采集完成复核：116序列/20992有效行（训练12032、验证4480、测试4480），全量文件哈希与checkpoint一致，family与完全相同输入均无跨split重叠，峰值58.682GB。首版训练数据就绪，尚未训练或集成发布；真实多轮与模板分布限制仍保留。回执 `artifacts/dsv41-l2-v2-20260916/collection-audit.json`。

- 2026-09-16（in_progress，实验未发布）：启动预测 L2 v2 采样；独立冻结 legacy 无损前向，采全40层分数/Top6、上一轮归一化 hidden、当前 token embedding 及 L0/L1 驻留状态，在 token 完成边界导出。首批116序列，最多20992行，family隔离；短/长输入256行 pilot 的 token/logits/SSD字节/晋升/fence对照通过，峰值57.443GB，批量采集已启动。尚未训练或接入 Runtime，正常缓存7 TPS回归仍待执行。详见 `docs/dsv41f-l2-collection-v2-2026-09-16.md`。

- 2026-09-16（进度澄清，正常缓存回归待执行）：全 miss 的无损 Top6 3.190/3.214 TPS 使用32输入/32 Decode并逐层强制缓存失效；历史7.045/7.168 TPS使用2048输入/128 Decode、正常缓存，且在最新 window 准入修改之前测得。两者不可直接比较；最新代码的历史正常缓存 legacy/auto 配对回归尚未完成，不将全 miss 验收扩大为正常负载无退化结论。下一步固定历史 prompt、L0=8/L1=40、eviction_dual、Prefill64 验证正确性和完整 TPS。进度及边界已记录至 `docs/dsv41f-allmiss-cost-floor-2026-09-16.md`；本次仅文档更新，未发布。

- 2026-09-16（completed，实验未发布）：window 准入与首次miss退出已验证；32步全miss：Top2旧4.419–4.549、新4.701–4.782 TPS，Top4旧3.834/新4.013，自然Top6旧3.190/新3.214；全部logits/SSD/fence一致，新版1280次miss、零跨层构图，峰值约55.2GB。已入窗再突变全miss的总吞吐4.580，首窗口仍有一次推测成本，不能宣称逐token严格零额外成本。`DSV41_WINDOW_FORCE=1`保留固定窗口诊断。详见 `docs/dsv41f-allmiss-cost-floor-2026-09-16.md`。默认packet未改，未发布。

- 2026-09-16（completed，实验未发布）：零miss隔离测试确认连续路径缺少充分流水提交：同token逐层94.73ms、整40层84.83ms、逐层异步75.05ms，等效吞吐+26.2%；guarded40仍159.51ms。已加入可选 `DSV41_ASYNC_WINDOW=1`，真实Top2/window4/2048+128配对合并8.062→8.793 TPS（+9.1%），logits/SSD/晋升/fence全一致，Top2/4逐步状态通过，峰值约57.3GB。诊断数不等同端到端L2 TPS，默认packet未变。详见 `docs/dsv41f-allhit-pipeline-isolation-2026-09-16.md`。同时纠正统计说明：runner每token结算计数，仍在Decode计时内。

- 2026-09-16（completed，实验未发布）：Burst 跨层优化完成：按层保存/提交状态、Gate 发布停止屏障、首次 Gate 前原生调度、miss 后重组，以及可选 `--inference-mode window` 原生推测窗口。2048/128 正式 Top2 ABBA 合并 8.805→9.307 TPS（约+5.7%，旧版波动较大）；Top4 window2 8.077→7.568，无收益。全部 logits/SSD/晋升/fence 一致，15组逐步状态对照通过，峰值约57.3 GB。guarded 真正 GPU 停止仍慢，auto 保持 packet。新增 ABI 防止后端/bridge 混用；详见 `docs/dsv41f-burst-window-optimization-2026-09-16.md`。未变更 Runtime/Package 发布默认。

- 2026-09-16：历史 2048/128 锚点复核完成：无损 legacy/auto 为 7.045/7.168 TPS；历史 baseline/Prefill0 Top2 参数下为 8.912/8.884 TPS，logits/SSD/晋升/fence 同配置全一致。历史完整 10.107 尚未复现，约八成以上额外时间位于前16步；不能以尾段10.3代替完整值。自动 guarded 未证明净收益，已撤掉自动触发，auto 保持原生 packet，显式 guarded 与恢复诊断保留。详见 `docs/dsv41f-tps-anchor-recheck-2026-09-16.md`。未发布。
- 2026-09-16：新 packet 兼容性扩展验收完成：图像/历史消息、trace/route capture、Static/其它 L1 策略及形状、Burst 尾部/Prefill、实验 dispatch 默认选择新 packet，不再自动回退 legacy；原数学前向及维护逻辑保留。11 组/22 次运行、105 份 logits、605 份诊断张量及路由一致，SSD/晋升/fence 一致，峰值≤58.21 GB。跨层 guarded 仍有独立范围限制，未发布 Runtime/Package。报告：`docs/dsv41f-packet-compatibility-2026-09-16.md`。
- 2026-09-16：DS4.1F 独立纯文本入口默认切换到新 auto executor；旧路径保留 --inference-mode legacy，未验收的图像/诊断/实验参数组合明确回退旧路径，manifest 记录选择。入口切换验收通过：默认 auto 与显式 legacy 在默认 Prefill 配置下 8 步 Decode/9 份 logits 逐字节一致，SSD/缓存/晋升/fence 一致；4 项 CPU 入口选择与参数转发测试通过。正式 Runtime/Worker 尚未集成，未发布。
- 2026-09-16：miss/resume 退化路径优化验收完成：auto 在频繁 miss 时使用单次 packet＋原生 dispatch，首次跨层 miss 后当前 token 立即转入原生 tail。正常两轮均值 3.969→4.032 TPS；每层真实 miss 两轮 2.196→2.248 TPS，SSD 请求与 bank fence 一致，无新增同步。1,580 个状态张量切换对照一致，Natural/Burst Top2/4 logits 对照通过。实验入口默认 auto/block4，产品 Runtime 默认不变，未发布。报告：`docs/dsv41f-miss-resume-native-packet-2026-09-16.md`。
- 2026-09-16：DS4.1F GPU miss/resume 隔离实验完成：真实 Metal ICB 跳过与实际 miss 层恢复，支持无损及 Burst Top2/4。8 组共 520 份 logits 与原引擎逐字节一致，SSD 请求量/晋升/fence 保持一致，40 层边界通过。但 Decode 明显负收益（无损 4.002→2.803 TPS，最佳新窗口），默认仍为旧路径；不纳入 Runtime 发布，独立后端仅供后续研究。报告：`docs/dsv41f-gpu-miss-resume-implementation-2026-09-16.md`。 补充消融：旧流程仅开启受保护后端即降至 2.758 TPS（65 份 logits 一致），已定位整套执行包装具有主要退化，尚待分项优化。

- 2026-09-15：用户确认实验引擎默认采用每层Main40/Hot8＋eviction_dual零复制晋升，已更新run.py和AdaptiveModel默认及README；旧策略可用`--l1-policy baseline`显式选择，固定层扩容仍关闭。L0容量8/12/16共8次测试logits一致、峰值≤63.352GB，长Decode TPS基本持平，故保留Hot8。Prefill64仍需显式参数。此项为后续Runtime集成候选，未发布Runtime/Package；不显式指定策略/槽数的默认入口3步Decode验证通过：Main40/Hot8、eviction_dual零复制，4份logits与已验证参考精确一致；证据`artifacts/dsv41-default-l1-20260915/verification.json`。

- 2026-09-15：完整新旧L1主对照完成（本轮未改Runtime）：旧baseline16步＋Hot复用 vs 新双频次＋淘汰晋升＋零复制，Main40/Hot8固定，2例×AB/BA共8个新进程，全部logits一致，旧基线身份校验通过。128步4.664→4.716 TPS（+1.12%）、2083输入/512步4.787→4.844（+1.18%），四个配对方向均正但样本小，不宣称普遍/显著加速；读回和栅栏均下降，峰值≤57.354GB。该结果是整套策略净收益，不能用此前零复制局部对照4.03%/2.43%替代。详见 `docs/dsv41f-l1-end-to-end-comparison-2026-09-15.md`；默认和发布状态不变。

- 2026-09-15：DS4.1F 零复制槽位晋升已实现：L0/L1 改为逻辑角色，GPU 按物理槽索引读取；miss 覆盖旧 L1 槽，晋升原地保留权重，无 memcpy/GPU copy。修正 Natural/Burst 命中分类，复用现有读回及单一栅栏。8次128/512步配对 logits、逻辑晋升/命中/读取/同步计数一致；复制23.802/97.989GB→0，TPS4.510→4.692、4.888→5.007（+4.03%/+2.43%），峰值≤57.336GB。eviction_dual内部默认启用，--promotion-copy保留同策略对照，总体baseline默认未改。Burst Top2/Block1、Top4/Block4各32步copy/swap配对的logits、缓存、读取、同步及回滚统计全部一致；随机160次bank操作及旧native/LRU安全回归通过。详见 `docs/dsv41f-zero-copy-promotion-2026-09-15.md`。未发布。

- 2026-09-15：DS4.1F eviction_dual 已实现：仅 L0 淘汰时筛选；Natural/Burst 复用 miss 元数据读回和单一写入栅栏，零维护专用 GPU→CPU 边界。8次短/长配对 logits 完全一致，逐对读回/栅栏总次数均不增加；长读回55152→36967、栅栏17938→16567，少请求56.045GB，TPS4.859→4.823（无加速结论）。峰值≤57.351GB；仅opt-in，baseline默认不变。Burst Top2/Block1、Top4/Block4各32步回归通过；6项bank/native安全测试及2项策略回放/精度范围测试通过。详见 `docs/dsv41f-l1-eviction-promotion-2026-09-15.md`。未发布。

- 2026-09-15：L1 双频次及保护区/试用区策略已接入实验引擎 Natural/Burst，复用 Hot→Main 内存复制；保留 baseline 默认。独立回放晋升决策校验通过；12次128/512步配对所有 logits/输出一致，峰值≤57.343GB。长 Decode TPS：baseline 5.000、双频次4.858、试用区4.907；少读32.958/44.990GB，但未加速，新策略仅 opt-in。Burst双频次Top2/Block1及试用区Top4/Block4各32步通过，提交路由计数准确、晋升复用正常。详见 `docs/dsv41f-l1-runtime-policies-2026-09-15.md`。尚未发布 Runtime。

- 2026-09-15：DS4.1F Hot→Main晋升复用完成并默认启用，Natural/Burst共用；原生统一内存memcpy，缺失专家仍走原preadv，保留lazy consumer与GPU同步栅栏。4项复制/旧native测试＋原LRU测试通过；128步逐层诊断460次Hot晋升零SSD读取；自然路径8次128/512配对及Burst Top2/Block1、Top4/Block4回归均输出一致。128/512步分别少读9.006/34.706GB，峰值≤57.339GB；小样本TPS−0.30%/−2.23%，不宣称加速。旧native缺复制入口明确拒绝、不回退SSD；`--promotion-reread`仅诊断对照。详见`docs/dsv41f-hot-promotion-reuse-2026-09-15.md`。仅实验引擎与其native扩展，未发布Runtime。

- 2026-09-15：DS4.1F只增不减L1实验完成：40槽底座，8个训练边际收益较高层增至48，总1664槽；独立growth-v1 schema保留旧1600槽校验。5项CPU测试、5用例20次AB/BA通过，4116份logits摘要与本轮/上轮基线一致。Decode4.726→4.722TPS（−0.10%），命中70.904→71.464%，峰值57.337→58.553GB；native读取仅−0.65%，整体无明显收益，保持Main40默认，仅opt-in。详见`docs/dsv41f-l1-growth-results-2026-09-15.md`，未纳入Runtime发布。

- 2026-09-15：DS4.1F逐层L1形状研究完成：300条采样、60次真实容量校准、4096/512完整logits与持续会话检查通过；checkpoint绑定的opt-in向量、采集/因果回放已实现。用户将性能验收从240次缩减为5例×4次，全部输出一致，Decode4.471→4.434 TPS（−0.82%，重复运行有明显波动），性能组峰值57.352GB；验证回放读取仅−0.399%。保留Main40默认，不自动纳入发布，不宣称通过完整统计门槛。详见`docs/dsv41f-l1-shape-results-2026-09-15.md`；研究完成，正式Runtime集成仍未验收。

- 2026-09-15：新增默认未接入的direct-index Metal attention微基准原型，验证能否省掉KV gather；并开始逐层cache miss/I/O归因。微基准直接索引原型慢1.5–2.3倍，未接入Model。Main40/48容量A/B：128步各两轮129 logits一致；512步一对513 logits一致，Decode8.25→8.79 TPS、末128步8.71→9.29、命中88.83→92.50%，footprint57.28→63.22GB，仍保留Main40通用默认。详见`docs/dsv41f-indexed-attention-cache-ab-2026-09-15.md`。仅实验，不属于已启用Runtime优化。

- DS4.1F attention/indexer专项开始：抽取index评分/TopK、稀疏KV gather/SDPA边界用于Prefill与Decode分项诊断，默认运算不变；分组64/128/256六次2048/128完整模型A/B全部logits、tokens、cache计数一致，256分组Prefill仅+1.3%、Decode不变，保留64默认；非整除query合成边界最大差4.8e-7，7/8项逐位一致、全部有限。新增双阶段profile定位Indexer约0.063秒而稀疏attention约3.62秒（同步诊断非吞吐）。详见`docs/dsv41f-attention-profile-ab-2026-09-14.md`，未发布。

- DS4.1F Decode调度实验：新增legacy/shared/unsorted三路径，共享gate/up输入量化与三投影索引计划；暂保留legacy默认，待2048/128完整logits和吞吐A/B选择。仅实验代码，未发布Runtime。

- DS4.1F性能入口：逐层eval/日志改为默认关闭，新增`--layer-progress`诊断开关，`--trace`仍保留逐层求值；Router/专家覆写安全等待与每步预算检查不变。当前仅实验runner，2048/128按on/off/off/on四次A/B通过：全部129份logits、tokens、cache/promotion记录一致，Decode平均6.96→7.20 TPS（+3.43%），Prefill+1.88%，footprint峰值57.292GB；详见`docs/dsv41f-layer-progress-switch-2026-09-14.md`。尚未视为Runtime发布验收。

- 最新：GLM SSD候选114,160张量全字节验证完成，99文件/181.75GB；HF Avdpro与MS ai2apps双源上传已同时启动。Runtime新布局验收、固定远端版本和签名distribution仍待完成；没有删除GLM原始checkpoint或旧专家库。以下构建中/上传中条目为历史进度。

- 首批Qwen/DS4.1F双源文件集合、大小、SHA256已全部匹配（73/172文件），LFS属性差异已统一，HF/MS均固定不可变commit。分发spec已准备但尚未签名/发布；具体commit及摘要见迁移文档和dual-source-verification收据。

- DS4.1F 当前 MLX/CPU参考/分析入口已迁移至 SSD checkpoint；CPU Store 支持外置专家，重新导出工具禁止覆盖输入专家目录。使用 macOS sandbox 禁止访问原 checkpoint/旧expert-store进行文本、图像及多轮回放精度回归；9场景/28个完整logits输出全部逐位一致，CPU参考24张量SHA256一致，峰值58.22GB；结果写入 `artifacts/dsv41-ssd-only-regression-20260914`，详见 `docs/dsv41f-ssd-only-engine-validation-2026-09-14.md`。原生扩展仍需保留，正式 Runtime/Package 集成未完成。

- 用户接受沿用既有账号 HF Avdpro / MS ai2apps；四个首批仓库已创建，DS4.1F/Qwen Next 双源上传进行中，尚未完成远端摘要验收或发布。Qwen 模型卡已修正并在 MS 页面确认 Qwen Community License 1.0。

- 首批 DS4.1F/Qwen Next SSD-ready 候选已生成并完成全 tensor payload 校验；DS4.1F 文本/图像各4步完整 logits 与原布局逐位一致，相关8项测试通过。新增 external tensor 读取模块及实验加载适配；Qwen Full/Cached 外置张量加载钩子已接入，10项导出及加载测试通过，Qwen 原/新布局 × Full/Cached 已通过33+4 tokens短推理输出对照，使用既有 Runtime CPython3.11与极速SSD扩展；managed Worker、安装准备与多轮验收仍待完成。GLM fused-v2 专家存储已构建，SSD导出正在逐tensor验证；第45层MTP保留在backbone，两个导出测试通过。其余模型仍未验收。

- 用户授权升级 Runtime 和全部对话模型 Package，采用自有 checkpoint；MoE 使用无重复原专家的 SSD-ready 布局，非 MoE 保持原精度镜像。Qwen Next 必须继续支持 Full/Cached。
- 执行顺序：checkpoint 构建与字节/推理校验 → MS/HF 固定 revision 与签名 distribution → 新版 Runtime → 模型 Package；不得提前填写虚构 distribution ID。
- 已开始构建工具与迁移清单及断点续传工作；尚未升级现有 Package 版本或发布 Runtime。现有发布与安装数据不删除。
- DS4.1F 需正式 engine/Worker/视觉集成，现有 GLM/Qwen/DS4 需加载与准备层适配、原生 ABI 及真实 Package 回归。完成前不可纳入 Release。
- 依据：`docs/dsv41f-runtime-package-preparation-2026-09-13.md`；本轮进度：`docs/chat-checkpoint-migration-2026-09-14.md`。


### NXR-RELEASE-ALL-20260911：全量现有改动发布验收（in_progress）

- 用户最新收敛验收重点：本轮主要交付四个Image模型Package更新；真实音视频处理、Suite草稿恢复等后续验证延期，不作为本轮Image发布的新前置任务。保留Suite五项挂载通过证据，不将延期项标成已验证。继续保留直接影响Image安装的Desktop兼容前置（editing-only验证与四个新版本安装映射），不得因范围收敛跳过它。

- Suite 0.1.1实装挂载回归完成：Test2254 / port64004 下五个表单均正常显示，Host能力探测正常；Run `20260911T110555Z-28490` 为 SCOPED_PASS（5 passed / 0 failed / 0 blocked），测试账号已释放。关闭空白挂载故障，不等于真实媒体推理、草稿刷新恢复或完整Desktop发布通过；仍未生产发布。

- Suite 0.1.1最终候选已用原 key 标准签名，SHA `be5790b9d42191113a8a316fea2356d8dd58d34b85e37d7d68ebb4d8941439b0`，30,877字节；相关18项回归通过。Test 2254产品内验签一致，审计review/medium，Run `20260911T110555Z-28490` 等待用户在安装界面批准新版本。尚未确认安装、mount或真实推理，不算已发布。

- 用户明确授权将修复套件升级为0.1.1，沿用原 Publisher/key 做 Test 验收。已同步 Package、App、5个组件及 SBOM 版本，保留0.1.0历史制品；本次仍不是生产发布授权。

- 用户批准后的实际安装返回 `Same version already has another digest`，r2 未安装。旧0.1.0与新字节触发正常不可变版本保护；未关闭校验、删记录、重置实例或擅自改版本。Run `20260911T105258Z-27711` 五项按安装前置阻塞记录，等待明确将 Suite 测试升级范围扩展至0.1.1；没有生产发布。

- 沙箱适配续验收：相关150项回归通过（4.11秒）；Test 2254 标准构建/严格签名通过且内嵌代码摘要与源码相同。原 key 已签独立 r2 Test 候选，SHA `fe8f14e7acfac66ac9a150a4e35ff166dc7b78f9c05b5e29e9aa3cd6ec8811c1`。Run `20260911T105258Z-27711` 在真实 Discover 检查验签成功，正常审计 review/medium，停在用户安装批准；5项实际 mount 尚未执行，不标 ready，不发布生产。

- 用户已批准生产沙箱适配：新增验签资源内嵌交付、绑定当前 frame/mount 的 MessageChannel 媒体通道和 Host 隔离草稿存储，保留 opaque-origin/connect-src none。每次操作重新走现有 Broker 的 actor/mount/声明校验，不开放任意 URL；导航撤销通道。新增动态 JS 通道安全测试与资源路径/注入/体积回归；首轮相关35项及新增通道测试通过。Test 2254 标准重建中，实装验收未完成，不可据单测发布。

- 最新实装结果：用户确认安装后，Test 2253 能发现 Suite 全部5个 Mini-App，但5个实际挂载界面均空白。Run `20260911T101930Z-8823` 已结束：0 passed / 5 failed / 0 blocked，测试账号已释放。套件直接 fetch/localStorage 与生产 opaque-origin、connect-src none 沙箱不兼容；当前 Studio 消息集成只有 resize，缺少对应执行通道。初始空白的资源加载原因仍需浏览器证据确认；不得放宽 CSP 掩盖问题。需另行实施 mount-bound Host 通道、受验证资源交付和隔离草稿存储后重新签名/实装验收，尚未生产发布。详细证据见全量验收回执最新章节。

- Test-only 导入续验收：40项测试通过；最终 Test 2253 标准构建/签名校验通过，包内模块与源码 SHA 一致。实际 Discover 检查候选验签成功，正常审计返回 review/medium（Test 未配置本地 AI auditor）。Run `20260911T101930Z-8823` 已显示安装审批按钮，等待用户在产品 UI 明确批准；尚未安装、未报5项 mount 通过、未发布生产。

- 用户明确允许补齐 Test-only 候选导入入口：新增 `ai2apps/packages/test_candidates.py`、受现有 system-manage 授权保护的 API 与 Discover Test 面板。要求 Helper/test 身份及固定 Test 数据目录；从受信任 Registry snapshot 绑定 Publisher/key/namespace，原样验签后执行本地审计，按摘要明确批准安装；不写 Registry 发布/安装状态，记录 Test candidate 来源。首批 10 项隔离、验签、摘要确认与无安装副作用测试通过；Test 重建和真实 Suite 安装/5项 UI 复验仍待完成，不算已发布。

- 最新续验收：授权跨实例公开元数据查询后，在 binding-fix-v2 找到原 Suite key；标准构建器已生成独立 Test 候选，SHA-256 `96d361461b6edc8002364026b4a1474dacc0888e91ac816e2f0f96fa74a4b7c6`，29,742 字节，原公钥离线验签通过。当前 Dev Profile Cookie 经标准脚本认证成功，两个原 Publisher key 在 Cloud 均 active。没有新 submission 或生产发布。Test 本地入口仅支持旧内嵌签名格式，Contract v1 未发布候选缺少受支持的导入入口；不能伪造 Registry 已发布状态绕过。详见全量验收回执续记。

- 用户补充授权后已只读核对 dev：原 key 指纹无匹配，Package signing 元数据记录数为 0。旧 Suite 签名包有9个载荷与源码不同，不能替代当前验收。仍需定位原 key 的记录ID/namespace；未换 key、未新签名或发布，详见验收续记。

- Suite 续验收授权已收到：仅签名重建 0.1.0 并安装 Test，不读 Cookie、不发布生产。原签名 key `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc` 的公开记录不在当前 App-Dev 元数据中；读取 dev 原发布上下文元数据被权限检查拒绝，未绕过，待明确只读授权。独立的 Suite/Host/broker/workflow 33 项测试通过；未新签名或安装。详情见全量验收回执的授权续记。

- 本轮最终：合并回归 **2104 passed、6 deselected（476.44 秒）**；P0 **66 passed、0 failed、10 blocked**，测试账号已释放。5 个开发中主 App 与5 个缺少独立 Media Voice Suite 的 Mini-App 保持真实 blocked；尚待用户确认该套件 0.1.0 的 Test-only 签名安装授权。JUnit 已归档至 `.build/releases/acceptance-20260911T0816/`（完整路径见验收回执）。没有发布 Package 或正式 Desktop，没有提交/推送源码。

- 后续证据集中记录在 `docs/ai2apps-full-release-acceptance-2026-09-11.md`。扩展回归 681 passed；Package 契约 31 passed；合并回归 2103 passed，唯一失败为多步 Agent 用例 3 秒等待不足，保留全部断言的实测完成时间 3.379 秒，现仅该测试改为 10 秒上限且复验通过。最终合并重跑与 UI 队列仍在进行，尚未签发生产候选。新增测试诊断改动位于 `tests/test_ai2apps_agents.py`。

- 解锁后续验收：用户确认已解锁，CUA 精确连接 `com.ai2apps.desktop.test.shell`，登录表单可访问；标准 Harness 新 Run `20260911T081651Z-64291` 已恢复测试账号登录并执行 P0 UI 队列。旧 Run 的 blocked 结果保留，不覆盖为通过。
- 扩展 Runtime 回归发现 25 项旧契约断言失败（648 passed、6 deselected）：API-Key 网页登录/设置已经退役、统计信息不再暴露密钥、模型显示名规范更新、Shell 增加 Desktop 版本上下文、Chat 设置结构调整。测试现改为断言退役入口 410 且无 Session/设置副作用；模型与参数验证测试显式注入测试身份，不改变产品认证。涉及 `tests/test_audio_api.py`、`test_admin_api_key.py`、`test_admin_auth.py`、`test_admin_i18n_chat.py`、`test_server.py`、`test_server_main.py`。复验进行中，未据此推进生产发布。

- 用户在 Build 2250 内部候选后明确要求继续到完成发布，并选择将全部现有改动纳入本次发布验收。此授权覆盖现有源码的全量验收范围，不把未验收项自动改为 ready，也不授权绕过 Cloud 发布边界。
- 正式候选必须由提交并推送的干净源码重建；2250 保持不可变内部证据，不直接提升为生产版。测试数据、缓存和 `:memory:.ses` 不作为源码提交或产品载荷。
- 预检发现 packaged AceFox 未包含已实现的 PromptParent 品牌补丁；已用原 AceFox 工程的 `mach build faster` 与 `mach package` 刷新，包内已出现精确 Shell origin 和 useTitle 分支；未使用 Development overlay。
- 修复 Desktop builder 未携带根许可证说明的问题：App 的 `Contents/Resources/Licenses/` 现在保存 LICENSE、LICENSE-POLICY、NOTICE、TRADEMARKS 和 BSL 文本，标准 verifier 缺任一项即拒绝。没有修改许可证条款。
- 测试账号 Broker 标准 doctor 显示 configured/authorized；随后标准 Harness 尝试测试登录，未读取用户 Cookie、未重置 Test 数据。固定 Test App Build 2251 已通过标准构建与 verifier，旧 Test App 已归档。
- 全量回归 1466 passed、1 failed、4 deselected（434 秒）；失败是能力说明新增文案遗漏翻译。已补齐五组中英文 ACPF 键，相关翻译与许可证测试复验 3 passed。测试系统自身 81 passed。
- P0 Run `20260911T071647Z-57326`：46 passed、0 failed、30 blocked。UI 项被原生登录 fields-unavailable 阻塞；随后精确 Test Shell 的 CUA 检查确认 Mac 锁屏且自动解锁失败，需要用户手动解锁。不得以非交互检查代替 UI 通过。
- 本轮新增源码：`ai2apps/web/i18n/{en,zh}.json`、Desktop builder/verifier、`tests/test_desktop_release_licenses.py`。翻译修复发生在 Test 2251 打包后，最终候选仍需重建。真实 UI、推理、升级和 Cloud 发布仍未完成，四个模型 Package 尚未发布。
- 回退：保留 2250 内部制品与当前生产 2249；新候选未发布前不改变 stable。正式回退继续使用 Cloud 审计流程，不推送更低 Build。
- 验收更新：固定 Test App Build 2251 已构建并通过 verifier；全量回归 1466 passed、1 failed、4 deselected。失败为五组 ACPF 翻译键遗漏，已修复，相关翻译与许可证复验 3 passed。翻译修复晚于 Test 打包，正式候选必须重建。
- P0 Run `20260911T071647Z-57326` 为 46 passed、0 failed、30 blocked；标准测试登录 fields-unavailable，随后 CUA 精确检查 Test Shell 确认 Mac 锁屏且自动解锁失败。需要用户手动解锁，UI 不得算作通过。未重置 Test 数据，未读取用户 Cookie，四个模型 Package 与正式 Desktop 均尚未发布。

### Imagine Studio Ideogram JSON 提示词适配（2026-09-11）

- 状态：`in_progress`，未发布新 Package。
- 已撤掉公共平台的 `/ideogram-caption` 接口、聊天模型扩写模块与 Imagine Studio
  的模型专用 prompt 分支及对应临时测试。标准图片调用继续传原始 composed prompt；
  Ideogram 私有 JSON 适配应由 Package 承担，不引入公共平台聊天模型依赖。
- 使用已安装 Runtime 1.6.2、现有 Q4 缓存，1024×1024、seed=0、官方 Turbo 12
  参数实测：中文和英文最小 JSON 均为灰色拒绝画面，详细英文 JSON 成功熊猫吃竹子。
  三份输入均通过官方 CaptionVerifier，不能把格式通过等同于实际出图成功，
  也不能从上述对照认定额外 AI 扩写必需。补充对照：中英文固定模板均失败；
  完整中文 JSON 成功熊猫吃竹子；中文固定模板改用官方20步参数仍失败。
  共7次真实文生图，7份输入均通过官方格式校验。Package 更新门槛未通过，未改包或发布。
- 当前测试是直接调用 Package pipeline 的 GPU 测试，不等同于签名 Package 的沙箱安装验收。
- 源码变更：`ai2apps/api/imagine_studio.py`、`ai2apps/web/static/js/imagine_studio.js`、
  删除 `ai2apps/images/ideogram.py`，撤回 `tests/test_ai2apps_imagine_studio.py` 临时扩写测试。
- 测试证据：`ai2apps/docs/ideogram-json-probe-2026-09-11/README.md`，同目录保存
  7组 JSON、图片、报告、校验结果及测试脚本；未执行图生图或签名安装验收。
- 回归14/14通过，指定文件 diff 检查通过；经固定 app-dev Helper 重启 Local 生效，
  CUA 确认固定 Shell 在端口53496正常启动。
- 官方参考：https://github.com/ideogram-oss/ideogram4/blob/main/docs/prompting.md


### 图片模型公共 Checkpoint 布局验证（2026-09-11）

- 状态：`ready`（本次安装就绪误判修复；不代表所有模型推理验收）。
- 实机确认 Ideogram 四个嵌套权重已完成下载，但通用根 config/权重检查将其拒绝，
  Worker 配置 path=null，最终 ACPF 95% 报统一就绪超时。此前 Z-Image/FLUX 特例未覆盖它。
- 将适配器布局检查集中到 `ai2apps/checkpoints.py`，Ideogram 要求全部四份非空源权重，
  配置由 Package 提供；Qwen Image 的 mflux Runtime scheduler 与 Z-Image/FLUX 一致处理。
- 影响文件：`ai2apps/checkpoints.py`、`ai2apps/packages/supervisor.py`、
  `tests/test_checkpoint_runtime_components.py`。保留未知后端、缺分片和缺任意 Ideogram 组件的拒绝检查。
- 验证：布局、ACPF、Imagine 模型目录回归 55/55 通过。经固定 app-dev Helper 重启 Local，
  Ideogram Worker path 从 null 恢复，原失败会话经 UI Retry 达到 `ready / 100%`、error=null，
  安装弹窗自动退出，无需重下权重。Qwen 尚未实机推理；未把服务就绪等同于真实出图。
- 测试命令（仓库根）：`.venv/bin/python -m pytest tests/test_checkpoint_runtime_components.py
  tests/test_ai2apps_provisioning.py tests/test_imagine_model_catalog.py -q`。沙箱退出时有 Metal
  无设备的 atexit 提示，测试 exit=0；GPU 推理没有包含在这些回归中。


### FLUX.2 Klein ACPF 就绪判定补齐（2026-09-11）

- 状态：`in_progress`。FLUX Worker 已启动，但完整的签名分发没有 scheduler 目录，
  此前仅覆盖 Z-Image 的 Runtime 调度器判断导致 FLUX checkpoint path 为 null。
- 将豁免限定到 `flux2-klein/mflux-mlx-optimized` 精确组合；权重分片及其他组件仍需完整。
- 为两种后端参数化回归：可接受 Runtime scheduler，不接受未知后端或缺少权重。
- 用户截图已验证此前 Z-Image 本地图像编辑成功；本项单独验证 FLUX。
- 验证：两种后端回归 2/2 通过，diff 检查通过。已重启准确的 app-dev Local，
  实际 FLUX Worker 配置的 checkpoint path 从 null 恢复为现有分发目录，服务再次 ready；
  无需重新下载。ACPF UI 重试及真实 FLUX 出图尚待验收。

### Imagine Studio 配置后本地模型发现（2026-09-11）

- 状态：`ready`。
- 原因：前端读取 OpenAI `/v1/models`，却用该响应未提供的 `source_type` 等管理目录
  字段筛选，导致 ACPF 返回 ready 后本地图片模型仍不可见。
- 新增登录保护的 `/v1/platform/imagine-studio/models`，共用 ACPF 的 Package resolver，
  明确返回 checkpoint_ready、图片操作与几何能力，且不暴露 Worker 地址、凭据或本地路径。
  配置完成时直接刷新模型目录并传播请求错误，避免被无关的历史刷新覆盖。
- 文件：`ai2apps/api/imagine_studio.py`、`ai2apps/web/static/js/imagine_studio.js`、
  `tests/test_imagine_model_catalog.py`、`tests/test_ai2apps_imagine_studio.py`。
- 验证：模型目录权限、未下载/内部模型过滤、几何能力与现有 Imagine Studio 回归测试。

### ACPF 公共弹窗国际化（2026-09-11）

- 状态：`ready`。
- ACPF 接入现有 `window._t` 语言字典，补齐简体中文与英文；其他语言使用现有英文回退。
  覆盖公共状态、按钮、选择计数、下载进度、许可确认提示，以及全部内置 Profile 的中文
  标题、说明、档位标签与步骤文案。动态设备推荐理由也支持旧 Session 中已保存的文案。
  许可原文与第三方错误原文不作自动翻译。
- 文件：`ai2apps/web/static/js/capability_provisioning.js`、`ai2apps/web/i18n/en.json`、
  `ai2apps/web/i18n/zh.json`、`tests/test_acpf_localization.py`。
- 验证：全部内置 Profile 翻译覆盖、实际 JS 翻译函数中英文计数与旧计划理由测试 2/2
  通过；Node 语法检查及 diff 检查通过。Locale 字典启动时缓存，需要重启 Local。

### Z-Image MLX Checkpoint 就绪判定修复（2026-09-11）

- 状态：`in_progress`（代码与回归通过，待 UI 配置重试验收）。
- 原因：签名分发已完整落盘，但通用 Diffusers 检查要求 `scheduler/`；mflux Z-Image
  使用 Runtime 内建调度器，分发不包含该目录，导致 Worker Checkpoint 路径为 null，
  ACPF 在 95% 等待 60 秒后超时。
- 修复：仅针对 `family=z-image` 且 `implementation=mflux-mlx-metal-optimized`
  的 Worker 允许 Runtime 提供 scheduler；其他组件与索引分片检查保持生效。
- 文件：`ai2apps/checkpoints.py`、`ai2apps/packages/supervisor.py`、
  `tests/test_checkpoint_runtime_components.py`。
- 验证：相关测试 3/3 通过；真实 app-dev 已下载快照经修复后解析得到有效路径，
  无需重新下载。改动在 ai2apps 热挂载范围，仅需重启 Local。

### NXR-052：Gallery 图片列表右键菜单

- Mini-Entry 按钮调整（2026-09-11）：保留 Studio 素材栏外层“打开 Gallery App”入口，
  内层页头原打开按钮改为刷新当前目录，保留当前目录、搜索和类型筛选；加载或操作中禁用重复点击。
  导入按钮改用加号；导入和刷新均提供可见的 Hover Tip，键盘聚焦也显示提示，沿用中英文文案
  与无障碍名称。导入改为可聚焦按钮，点击调用隐藏文件选择器。
- 状态：`ready`
- 类型：Gallery Shell-App、Gallery Mini-Entry、资产集合操作。
- 用户可见变化：Gallery 完整页面与所有 Studio/AceFox Sidebar 使用的 Gallery Mini-Entry
  共用同一套图片右键菜单，提供打开、下载、重命名、删除、复制、粘贴和移动。移动会在菜单内
  展开可写目标集合；普通删除移入废纸篓，废纸篓中的删除保持永久删除确认。
- 交互与边界：复制/粘贴使用同源 Gallery 内部剪贴板，只保存受当前账户权限再次校验的 Asset ID，
  不读取或覆盖系统剪贴板，也不暴露宿主文件路径；粘贴把资产加入当前实体集合。Recent 与 Trash
  等虚拟/只读集合会禁用不成立的粘贴或移动操作。图片列表空白区也可打开菜单，使空集合能够接收
  已复制图片；鼠标右键和键盘 Context Menu / Shift+F10 均可打开。
- 需要进入 App 的文件：`ai2apps/web/static/js/gallery.js`、`ai2apps/web/static/css/gallery.css`、
  `ai2apps/web/templates/system_apps/gallery.html`、`ai2apps/web/templates/system_apps/gallery_mini.html`、
  `ai2apps/web/templates/system_apps/_gallery_asset_context_menu.html`、`ai2apps/web/i18n/en.json`、
  `ai2apps/web/i18n/zh.json`、`tests/test_ai2apps_gallery.py`。
- 当前验证（2026-09-11）：Gallery 专项回归 `8/8` 通过，JavaScript、英文/中文 JSON 与
  `git diff --check` 通过。固定 App-Dev 的 Local 通过认证 Helper 通道重启至端口 `57152`；实机
  确认完整 Gallery 与 Video Studio 内 Gallery Mini-Entry 均显示七项菜单，窄栏菜单没有溢出。
  复制动作成功写入内部剪贴板，切换到空 Public 集合后右键空白区仅启用粘贴；未对用户现有资产
  执行粘贴、移动、重命名或删除。
- Release notes 建议：Gallery 图片现在可在完整页面和 Studio 素材栏中通过右键快速打开、下载、
  重命名、删除、复制、粘贴或移动到其他集合。
- 纳入 Build：待定。

### NXR-051：AI Browser 九语言界面本地化

- 状态：`ready`
- 用户可见变化：Profile 管理页接入系统统一语言设置，覆盖简体中文、繁体中文、英语、日语、韩语、西班牙语、法语、巴西葡萄牙语和俄语。标题、说明、按钮、创建/删除弹窗、占位符、无障碍标签和操作结果共 40 项文案完整翻译；用户自定义名称保持原文。
- 错误提示补齐名称校验、登录失效/无权限、配置文件不存在、默认配置文件保护、服务不可用、超时、网络失败及无效请求；将后端已知错误与 HTTP 状态映射为本地化说明，未知错误保留 HTTP 状态而不直接显示未翻译的技术诊断。参数替换按字面插入名称，避免特殊字符或花括号被再次解释。页面标签标题也使用当前语言。
- 文件：`ai2apps/web/templates/system_apps/ai_browser.html`、`ai2apps/web/static/js/ai_browser.js`、`ai2apps/web/i18n/*.json`。
- 验证（2026-09-10）：JavaScript 语法及 diff 空白检查通过；九种语言各 32 个键完整性、Jinja 模板渲染、Node 模拟创建/启动/切换窗口/删除/HTTP 错误/默认 Profile 保护及特殊名称插值均通过；Browser Profile 专项回归 5 项通过。固定 App-Dev 路径的 Computer Use 连接超时，未完成实机视觉验收。模板和脚本刷新 Shell 生效；语言字典由 Local 缓存，现有进程可能需要从 Helper 菜单重启 App-Dev Local 后再刷新，不能仅凭静态刷新认定新翻译已载入。无需重建 App。
- Release notes 建议：AI Browser 现支持跟随系统语言显示完整的 Profile 管理界面。
- 纳入 Build：待定。

- 补充验证（2026-09-10）：9 种语言各 40 个键完整性检查通过；Node 执行级检查覆盖错误映射、结构化 422、网络错误、空白/超长名称阻止提交；英文和中文页面标签标题渲染通过。用户确认范围为 AI Browser 全部界面。

### NXR-050：Imagine Studio 模型选择器对齐 ACPF 安装入口

- FLUX 编辑保真修正（2026-09-11）：Imagine Studio 对本地 FLUX.2 Klein 编辑请求显式传递 use_kv_cache=false，覆盖 Image Edit、换风格、参考图和合影等共享请求路径；文生图、Cloud、其他本地模型不变。固定红杯原图/seed=0/4 步/Q8 对照：开缓存 9.2 秒明显改杯型，关缓存 12.8 秒基本保留原图几何与高光。静态 JS 刷新生效，不修改已签名 Package；增加 4B/9B 与非目标模型请求隔离回归。

- Z-Image 参数（2026-09-11）：开放本地 Z-Image 采样步数与重绘强度并保存到 Draft/Run；重绘百分比转换为 mflux 起始比例（默认 75% 重绘 → strength 0.25，8 步时执行 6 步），文生图仍默认 8 步；显示 Img2Img 能力说明，本地新 Run 使用本地标题。仅修改客户端，不修改已安装模型 Package。

- 输出栏滚动（2026-09-11）：标题统一为单行大号 Output；有结果时预览图片先随栏滚动、到顶部后 sticky 覆盖后续内容，保持 contain 完整显示，并限制预览高度不超过栏内可视高度。仅影响 Imagine Studio。

- 输出栏刷新按钮（2026-09-10）：新增中英文 Hover/键盘焦点提示，解释仅同步任务与结果、不重新生成或扣费；图标放大到 20px，按钮外框尺寸不变。

- 完成态修正（2026-09-10）：Gallery 按钮禁用绑定显式返回 boolean，避免缺少 adding/galleryAssetId 时 undefined 被绑定为 disabled；等待光标仅用于实际导入中。Run 进度条仅在 queued/running 显示。静态页面刷新生效，App-Dev 实测蓝杯 Artifact 成功加入 Gallery、侧栏出现缩略图、成功态进度条隐藏；新增缺省/空值/导入中/已导入禁用状态回归。

- 绘图目录补齐（2026-09-10）：新增 Ideogram 4 MLX Q4、Qwen Image 2512 和 Qwen Image Edit 2511，连同 Z-Image、FLUX 共五个独立 Checkpoint 选择项。Qwen 使用组件配置按各自文生图/编辑能力验证；保留内存兼容性、安装状态与许可证确认。专用 Actor Replacement 不支持通用绘图输入，不列入此能力。文件：`ai2apps/provisioning/profiles/imagine-studio.yaml`；需要重启 App-Dev Local 载入目录。相关回归 56 项通过，并新增与全部 `packages/*/service.yaml` 的通用 Image 模型清单对照检查（Imagine 专项 11 项再次通过）；新版五项列表尚未实机验收。
- 状态：`ready`
- 用户可见变化：Imagine Studio 的共享模型下拉菜单末项新增本地化“安装更多模型”，覆盖文生图、
  图片编辑、更换图片风格、参考图创作和合影等内置 AI Mini-App；纯本机且不使用模型的“调整图片”
  保持无模型选择器。入口在已有 Cloud/本地模型以及没有可用模型时均保留；无模型时先显示不可选的
  “暂无可用模型”占位，确保末项安装动作仍可被主动选择并触发。
- ACPF 行为：动作值 `__install_more__` 不作为模型 ID；选中后立即恢复原模型显示，再用
  `image.generation` Capability 和 `{ installMore: true }` 打开共享 ACPF 全量可信配置选择界面；
  “安装更多”模式强制使用多选，可在一次流程中选择多个兼容模型，不受能力档位默认单选模式影响。
  复用 ACPF 已安装项禁用、兼容性原因、确认、许可证、下载、恢复和完成回调；取消或失败不修改
  当前模型，安装完成刷新可用目录并保留仍有效的用户选择。
- 通知条修正（2026-09-10）：Imagine Studio 顶部通知条按工作区左右各留 18px，并在宽屏与
  工作区内容边缘对齐；取消反馈使用中性色并在 4 秒后消失，成功提示 4.5 秒、一般错误 8 秒后
  自动消失，同时保留手动关闭。新操作开始时会取消旧计时器，避免旧通知误清除后续提示。
- 文件：`ai2apps/web/templates/system_apps/imagine_studio.html`、
  `ai2apps/web/static/js/imagine_studio.js`、`ai2apps/web/static/css/imagine_studio.css`、
  `ai2apps/web/static/js/capability_provisioning.js`、
  `tests/test_ai2apps_imagine_studio.py`、`tests/test_ai2apps_provisioning.py`。
- 当前验证（2026-09-10）：Imagine Studio 与 ACPF 专项回归 `56/56` 通过，新增 Node 执行级测试确认
  动作项恢复原选择、以 `installMore=true` 唤起 ACPF，且不触发草稿保存；普通模型切换仍更新模型并
  保存草稿。两个 JavaScript 文件语法、Ruff 和 `git diff --check` 通过。固定 `AI2Apps-App-Dev`
  在端口 `52750` 热加载源码后实机确认：菜单动作恢复 `(Cloud) OpenAI · GPT Image 2`，ACPF 显示
  “选择要安装的模型”及 Z-Image/FLUX 多选项；取消后未下载、未安装，原模型仍保持选中。纯静态
  HTML/JavaScript 变更无需重建 App 或重启 Local。通知修正后重新挂载同一 App，实机确认取消提示
  左右留白、使用中性色，并在约 4 秒后自动从可访问性树和画面中消失。
- Release notes 建议：在 Imagine Studio 模型菜单中直接安装更多本地图像模型。
- 纳入 Build：待定。

### NXR-049：App Launcher 紧凑卡片与介绍悬停提示

- 状态：`in_progress`（实现与回归完成，待 App-Dev 实机视觉验收）
- 用户可见变化：卡片展示图标、名称及 Experimental 实验标记，移除冗余 Open 按钮、分类及实例状态正文；介绍复用 Dock 深色圆角 Hover-Tip，支持悬停与键盘聚焦，长文本自动换行，底部空间不足时向上显示。保留 Dock 固定操作和多窗口切换、新建入口。
- 卡片最小高度由 142px 降至 112px，名称间距缩小；搜索仍匹配介绍与分类。
- 用户反馈修正（2026-09-10）：恢复图标旁的 Experimental 实验标记及原有黄色样式；JavaScript 语法和 diff 空白检查通过。
- 布局修正（2026-09-10）：修复实验标记横排样式被误限定到 development 卡片的问题，所有卡片的图标行统一使用 flex 与底对齐，Experimental 位于图标右侧；恢复 development 图标灰色背景选择器的正确作用范围。选择器检查与 diff 空白检查通过。
- 文件：`ai2apps/web/static/js/shell.js`、`ai2apps/web/static/css/shell.css`。
- 验证（2026-09-10）：`node --check ai2apps/web/static/js/shell.js`、`git diff --check` 通过；仓库根目录执行 `.venv/bin/python -m pytest tests/test_ai2apps_shell.py -q`，114 项通过。退出时环境报告无 Metal device，不影响测试结果。Computer Use 连接固定 App-Dev/Shell 路径持续超时，未完成刷新及实机视觉验收；纯静态改动无需重建 App。
- Release notes 建议：精简 App Launcher 卡片，将应用介绍改为悬停提示。
- 纳入 Build：待定。

### NXR-048：Discover 模型安装兼容 Cloud catalog 详情结构

- 状态：`ready`
- Discover 内存口径跟进（2026-09-10）：卡片改读独立 `runtimeMemoryBytes`，
  既有 Package 依据 service.yaml 的 Lean/Compact 档位兜底；GLM 显示约 55 GiB。
  `minimumMemoryBytes` 保留安装整机门槛并与 Chat Profile 对齐（GLM 64 GiB）；
  缺少运行数据时显示“—”，不挪用整机门槛。签名 Profile 兼容可选运行内存字段。
  Discover + Registry 52 项测试通过，JS 语法检查通过；尚未重启 App-Dev 页面验收。
- 模型资源数据跟进（2026-09-10）：按不可变 Checkpoint 发布收据修正六项 Chat
  模型下载尺寸，并依据 Cached-MoE / VLM 实测修正内存估计；Qwen3.6 使用安装验收
  的约 19 GiB 与 Top120 内存记录。详情来源提示注明档位、峰值和系统门槛为估计；
  UI 二进制单位改为 GiB/MiB。证据和未核实项见
  `docs/discover-chat-model-profile-evidence-2026-09-10.md`。无需 Cloud 变更或重发旧 Package。
  验证：Discover + Registry 51 项通过，Discover JS 语法检查通过；尚未重启当前
  App-Dev 做页面验收。测试退出时出现 sandbox 无 Metal 设备的清理告警，测试退出码为 0。
- 重启续跑跟进（2026-09-10）：Discover 模型安装 ACPF 会话现在持久记录
  `returnTo`，Shell 在 Local 重启后自动返回 Discover；修复前已创建、没有该字段的会话也会
  依据受限的 App/Capability 身份兼容恢复。ACPF 遇到尚未安装的 restart-required Runtime
  依赖时，会在用户已确认的可信安装范围内先安装该依赖，再进入等待重启；重启后继续模型
  Package，不再循环提示安装 Runtime。等待重启说明改为蓝色信息提示，只有实际失败显示红色。
- 安装状态跟进（2026-09-10）：已安装接口现在把签名 `modelInstall` 声明与本机可用的
  Package Model/Checkpoint 状态关联，返回 `modelReady` 和已就绪配置 ID；Discover 卡片与
  详情只有在尚无可用 Checkpoint 或存在新版本时显示“安装模型”，当前版本已有可用配置时
  显示“已安装”。这保留了“只装 Package、稍后下载模型”的既有流程。
- 模型分类跟进（2026-09-10）：Text 是可重叠的能力分类；除原生 Text 模型外，声明
  `multimodal-conversation` 的多模态模型也会列入 Text，同时继续保留在 Multimodal。
  Local 的分页后端与 Discover 前端使用相同规则，不把仅图像生成等非对话模型误列为 Text。
- 用户可见变化：从 Discover 安装既有模型 Package 时，不再因按钮闪回并提示
  “The catalog release version is unavailable”而中止；Local 能从当前 Cloud catalog 详情的
  `package.latestVersion` 和 `package.displayName` 解析发行身份并进入 ACPF 安装流程。
- 根因与兼容边界：Cloud catalog 详情使用嵌套 `package` 摘要，Local 安装接口此前仅识别
  顶层字段、`latestRelease` 或签名 manifest。现在分类、模型评分、ACPF 安装计划和安装接口
  统一兼容嵌套摘要；既有官方 Package 继续使用受版本上限约束的内部映射，未来 Package
  仍必须在签名 manifest 中声明模型元数据，不要求逐个重发旧 Package。
- 文件：`ai2apps/packages/discovery.py`、`ai2apps/api/packages.py`、
  `ai2apps/provisioning/orchestrator.py`、`ai2apps/web/static/js/capability_provisioning.js`、
  `ai2apps/web/static/js/discover.js`、`ai2apps/web/static/js/shell.js`、
  `ai2apps/web/templates/system_apps/discover.html`、
  `tests/test_ai2apps_registry_v1.py`、`tests/test_ai2apps_provisioning.py`、
  `tests/test_ai2apps_shell.py`。
- 当前验证（2026-09-10）：使用与生产 Cloud 返回一致的 `package + releases` catalog 详情
  新增回归，模型安装计划与 ACPF 会话创建均通过；Registry 与 Discover 分类联合回归
  47 项通过；重启续跑跟进与 Provisioning、Shell、Registry、Discover 分类联合回归共
  206 项通过。固定 App-Dev 实机验收已确认：首次重启后自动返回 Discover 并下载、安装
  `ai2apps/runtime-omlx 1.6.2`；第二次重启仍自动返回 Discover，Runtime 显示为
  `Local 1.6.2`，模型 Service Package 完成并进入 Checkpoint 下载阶段，未再出现原依赖
  循环。为避免验证额外消耗约 17 GB 下载，确认进入 Checkpoint 阶段后主动取消测试会话。
  安装状态跟进后的联合回归共 207 项通过；在用户已完成 Checkpoint 的当前 App-Dev 实机上，
  Qwen3.8 卡片同时显示 `Local 0.3.2` / `Cloud 0.3.2`，操作按钮已变为禁用的“Installed”。
  模型分类跟进的 Discover/Registry 50 项范围回归通过；固定 App-Dev 实机的 Text 分类已
  同时显示 Qwen3.8 Flash Next、Ornith、GLM-5.3、Qwen3 VL、Qwen3.5 与已安装 Qwen3.8
  等带 `MULTIMODAL` 标记的对话模型。
- Release notes 建议：修复部分模型 Package 在 Discover 中点击安装后立即复原的问题。
- 纳入 Build：待定。

### NXR-047：Shell App 原生对话框品牌标题

- 状态：`ready`
- 用户可见变化：Shell 内页面的 `alert`、`confirm`、`prompt` 标题统一为 `AI2Apps`，不再显示页面 URL；保留原生阻塞、按钮和返回值语义。
- 实现：AceFox `browser/actors/PromptParent.sys.mjs` 依据父 Chrome 文档精确匹配 `chrome://browser/content/ai2apps/shell.xhtml`，设置原生 `title` / `useTitle`。普通浏览器、认证及 beforeunload 提示保持原逻辑。
- Development 构建：`apps/ai2apps-acefox/scripts/build-release-app.sh` 在现有仅 Development 的 Shell overlay 中同步匹配源码树的 `actors/PromptParent.sys.mjs`；生产必须使用包含该源代码修改的 AceFox 正式快照。
- 验证（2026-09-10）：15 项标题与边界检查通过，覆盖带实例 query/hash 的 Shell 地址；JavaScript / zsh 语法、diff 检查通过。通过固定入口重建 App-Dev，`verify-release-app.sh` 与 `codesign --verify --deep --strict` 通过；包内 PromptParent 与源码逐字一致，Development、app-dev、cloud、源码根合同正确。实机窗口标题为 `AI2Apps-App-Dev: M5Max-128G 127.0.0.1:58113`；Chat 的原生删除确认框窗口及标题正文实际显示 `AI2Apps`，未确认删除。alert / prompt 共用分支已检查，未分别触发实机输入场景。
- 纳入 Build：待定。

### NXR-046：Cloud 管理 Work complexity API Default

- 首次发送保留手选模型（2026-09-18）：空白 Chat 首发原先调用 startNewChat 后无条件采用系统默认，导致本地手选被覆盖。新增 initialModel 参数，仅首次发送创建会话时传入发送前的模型；显式 New Chat 仍遵循中等复杂度/API Default。会话、发送 sourceModel 和右侧显示保持一致；新增实际执行 startNewChat/sendMessage 的回归，模拟异步目录刷新覆盖并验证恢复手选，覆盖显式新建与已有会话。
- Mini-App 安装入口对齐（2026-09-10）：浏览器 Chat Mini-Entry 与 Studio Chat 共用模型安装菜单控制器，末项提供“安装更多模型”，动作立即恢复当前值、不写入手动偏好，进入 ACPF installMore 模式；安装完成刷新目录。Chat Mini 模板补载共享 ACPF 资源；Studio 无独立 mount 时通过标准 Shell launch 获取 Chat AppInstance，后端仍执行 actor/AppInstance 授权校验。未执行真实安装。
- 对话模型安装入口（2026-09-10）：Chat 对话模型下拉菜单末项新增“安装更多模型”，恢复当前模型后进入 ACPF installMore 模式，复用 text.chat.local 配置与确认流程。模型选择器统一规范写入 `docs/ai2apps-app-development-guide.md`，适用于 App/Mini-Entry/Mini-App，明确菜单内部末项、可用性、已安装禁选、取消保留选择与异步刷新验收。
- 切回 App 刷新修复（2026-09-10）：Chat 在局部变量完整组装包含 API Default 的目录后仅发布一次，避免异步间隙删除选中项；等待 Alpine 选项渲染后显式同步原生 select 值，防止 currentModel 未变而右侧误显首项 Claude。Browser/Studio Mini-Entry 原本已同步重建选项并赋值，本次额外保留异步加载期间最新的有效手动选择。
- 刷新修复验证：Chat UI、Browser Mini-Entry、Studio Mini-App Chat 共 43 项回归通过；App-Dev 原有对话刷新、最小化再恢复窗口后，顶部与右侧均保持 DeepSeek V4 Flash (API Default)，Knowledge 保持 Off。Mini-Entry 完成代码与回归检查，未新增真实推理请求。
- Mini-Entry 跟进（2026-09-10）：Browser Chat Sidebar 与 Studio Mini-App Chat 统一使用共享默认选择函数；已有手动选择优先，否则读取 `work_standard`，空值继承 Cloud API Default。兼容旧模型目录的 provider ID，同时保留独立 `cloud/ai2apps/` Points 路由；不把继承值写入手动偏好，无有效默认时不再自动选择首项。文件：`ai2apps/web/static/js/{chat_mini,mini_app_chat}.js`、`tests/test_ai2apps_chat_mini.py`。
- 状态：`in_progress`（Cloud 已部署，客户端定向回归通过；待桌面 UI 与实际 Work 端到端验收）。
- Chat 默认目录修复与实机复验（2026-09-10）：运行诊断确认策略 ID 为 `cloud/ai2apps/deepseek/deepseek-v4-flash`，旧目录仅返回 `cloud/deepseek/deepseek-v4-flash`，可用性检查因此拒绝默认选择。Chat 在目录存在对应模型时注册独立 API Default 项，复用能力元数据但保留专用 `cloud/ai2apps/` Points 路由及原有显式 provider 路由；不硬编码 DeepSeek、不将默认路由降级为 BYOK。临时诊断 UI 已移除。App-Dev 刷新与 New Chat 均实际选中 `DeepSeek V4 Flash (API Default)`，输入框启用，Knowledge 为 Off。Chat UI 与 Cloud defaults 共 44 项测试通过，新增目录兼容、路由保留、能力继承、去重及缺失目录测试；未发送真实推理请求，完整 Work 验收仍待完成。
- App-Dev 登录后 UI 验收（2026-09-10）：三档 Work 均实际显示 `Use API default — (Cloud) DeepSeek V4 Flash`，专用能力槽位保持 `Not assigned`，中档下拉目录包含 DeepSeek V4 Flash。Chat 的 Use Knowledge 实际为 Off；但首次打开与点击 New Chat 均未正确选中默认模型，顶部模型按钮缺失、输入框禁用，右侧原生下拉显示首项 Claude Sonnet 4.6，故 Chat 默认继承验收失败。未发送推理请求、未改用户模型配置；需定位并修复后复验，不得将单元测试通过视为本项 UI 通过。
- App-Dev 首启复验（2026-09-10）：经用户明确授权，停止精确 `app-dev` 进程，将其 support/cache 私有目录移入 `/Users/avdpropang/Library/Application Support/AI2Apps/app-dev-reset-backup-20260910-0019/` 后启动固定 App，其他实例及公共模型缓存未动。全新未登录实例成功生成 Cloud 默认策略缓存，未生成显式 `default-models.json`；Shell 显示 Core 用户登录页，后续 Chat/Model UI 验收等待用户重新登录。旧数据保留可恢复备份，未永久删除。
- 用户可见变化：未手选的三个复杂度档位动态继承 Cloud 默认 AI，界面显示继承模型；
  初始 Cloud 选择要求为 `deepseek/deepseek-v4-flash`，客户端不硬编码该模型。
- 实现：启动最多等待 3 秒拉取，每 5 分钟刷新；origin 隔离的原子缓存最长有效 24 小时；
  显式模型选择始终优先，空值恢复继承，专用能力槽位不变。Cloud 显式路由不被 BYOK 拦截。
- 文件：`ai2apps/cloud_defaults.py`、`ai2apps/model_manager.py`、`ai2apps/platform_runtime.py`、
  `ai2apps/cloud_gateway.py`、`ai2apps/api/cloud.py`、`ai2apps/web/static/js/dashboard.js`、
  `ai2apps/web/templates/dashboard/_models.html`、`tests/test_ai2apps_cloud_defaults.py`。
- Cloud 交接：`docs/ai2apps-cloud-api-default-model-requirements.md`；未修改或部署 Cloud。
- Cloud 回执（2026-09-10）：Cloud 项目已部署 OpenAPI 1.47.0；交接文档为 `/Users/avdpropang/sdk/ai2apps-cloud/docs/ai-defaults-client-handoff-v1.md`，生产回执为同目录 `ai-defaults-production-deployment-2026-09-10.md`。客户端侧匿名实测生产 `GET /v1/ai/defaults` 返回 HTTP 200、`Cache-Control: no-store`、revision `1` 和 `deepseek/deepseek-v4-flash`，Cloud 部署阻塞解除。未修改 Cloud 配置、凭据或数据。
- 验证（2026-09-09）：默认策略、Model Manager、Cloud Gateway、Local API 与存储/生命周期
  定向回归 79 项通过；补充 Local 策略读取接口合同测试后策略测试 10/10 通过
  （累计 80 个不同测试）。Dashboard JavaScript 语法和定向 diff 检查通过。
  尚未重启 App-Dev 或验证真实 Cloud 推理；Cloud 部署前无法完成端到端验收。
- Release notes 建议：任务复杂度默认模型可随云端配置更新，用户手动选择保持不变。
- Chat 跟进（2026-09-10）：Chat 初次选择和新建对话默认使用 Model App 的 `work_standard`；未设置时使用同一 Cloud 策略的 API Default，不再读取 health 默认模型。已有对话/手动选中的有效模型不被后台刷新覆盖；新建对话重新读取配置。默认策略缺失或目标不可用时不随意选列表首项，等待用户明确选择。
- Chat 文件与验证：`ai2apps/web/templates/chat.html`、`tests/test_chat_ui_overhaul.py`；33 项定向回归通过，覆盖中等复杂度优先、API Default 继承、空策略、别名、保留手选及不可用模型。Test 包尚未包含本次 Chat 默认选择与默认关闭 Knowledge 的改动。
- 客户端复验（2026-09-10）：在仓库根目录执行 `.venv/bin/python -m pytest tests/test_ai2apps_cloud_defaults.py tests/test_ai2apps_model_manager.py tests/test_ai2apps_cloud_gateway.py tests/test_chat_ui_overhaul.py -q`，84 项通过。覆盖默认继承且不写入显式选择、清空恢复继承、专用槽位、重启缓存、origin 隔离、24 小时过期、null 停用、404/非法响应/网络故障保留有效缓存、Points 路由不受同厂商 BYOK 拦截与 Chat 默认选择。首次从 `ai2apps/` 子目录执行因 `secrets` 遮蔽标准库导致收集失败，改为仓库根目录后通过；退出时有沙箱 Metal atexit 警告，不影响测试结果。尚未完成全新未登录桌面 UI、真实周期刷新及实际 Work 推理矩阵；不将 Cloud 自身推理回执视为 Desktop 验收。
- 纳入 Build：待定。

### NXR-044：App / Mini-App 控件补齐 aria-label

- 状态：`in_progress`
- 类型：System App / Mini-Entry HTML 可访问名称、Package Mini-App 动态按钮。
- 实现边界：按用户要求仅添加静态或 Alpine 绑定的 `aria-label`，动态角色按钮仅增加
  `setAttribute('aria-label', ...)`；原有元素、文字、样式、事件和业务逻辑保持不变。
- 覆盖：Chat Mini 消息输入；Voice 项目/片段字段、试听及弹窗按钮；Video 清除帧、
  工具栏与 Composer 按钮；Imagine 调整工具栏及预设名称；Gallery Mini 搜索/集合/上传入口；
  media-voice Package 角色删除按钮。已有合格名称的 Shell 主控件保持不变。
- 需要进入 App 的文件：`ai2apps/web/templates/system_apps/{chat_mini,readaloud,video_studio,imagine_studio,gallery_mini}.html`。
- Package 文件：`packages/ai2apps-media-voice-studio-suite/web/mini-app.js`；未来 Package 候选需要
  包含该修改，本轮不构建或发布 Package。
- 当前验证（2026-09-09）：共添加 52 处 aria-label；与修改前快照比对，去除新增属性后
  5 个模板逐字一致，Package JavaScript 仅新增一条属性设置。5 个 Jinja 模板、57 个
  Alpine aria-label 表达式和 Package JavaScript 语法检查通过；控件无重复 aria-label，
  新复用的翻译 key 均存在于中英文词典，定向 `git diff --check` 通过。
  未做实机可访问树验收，状态保留 `in_progress`。
- 剩余边界：只添加属性不能解决 Gallery 上传入口的键盘焦点问题；依用户限制未改动其
  hidden、tabindex、元素类型或事件。新增 Composer 播放和裁剪名称使用英文，完整本地化待后续处理。
- Release notes 建议：补充 App 与 Mini-App 的控件可访问名称，改善语义 UI 测试定位。
- 纳入 Build：待定。

### NXR-043：Discover Shell-App 卫星天线图标

- 状态：`ready`
- 类型：Desktop Shell、系统 App 导航图标。
- 用户可见变化：Discover 在 Shell Dock、App Launcher 与 AppUI 页面标题区不再使用容易与
  浏览器混淆的罗盘，统一改为用户最终选定的 Lucide `satellite-dish` 单色卫星天线图标。
- 实现边界：直接复用客户端已打包 Lucide `0.453.0` 的内置图标，不携带 Discover 专属 SVG
  注册或第二条渲染路径；按 Shell 的 `22px` 桌面、`20px` 移动显示与激活态反白规则渲染。
- 需要进入 App 的文件：`ai2apps/apps/system.py`、`ai2apps/web/templates/system_apps/discover.html`、
  `ai2apps/web/static/js/shell.js`、`ai2apps/web/static/js/ai2apps_icons.js`、
  `ai2apps/web/templates/base.html`、`tests/test_ai2apps_shell.py`。
- 当前验证（2026-09-09）：Shell 定向回归 `114/114` 通过；相关 JavaScript 语法与
  `git diff --check` 通过。早期自定义火箭候选暴露了切换 App 时无条件重建整个 Dock 的问题；
  普通 App/Home 切换现只原位更新 `is-current`，保留全部 SVG DOM，仅目录、Pin、排序或 Badge
  变化才重建 Dock。最终卫星天线改为内置 Lucide 后，不再依赖自定义图标注册与兜底轮询。
  固定 App-Dev 已通过 Settings 的标准重启入口从端口 `51358` 恢复到 `57179`；实机截图确认
  Dock 激活态和 Discover AppUI 页头均显示卫星天线。验收临时打开的 Settings 实例已关闭，
  Dock 恢复到操作前状态。
- Release notes 建议：Discover 使用新的卫星天线图标，在 Shell Dock 中更容易与浏览器区分。
- 纳入 Build：待定。

### NXR-042：全 App 统一模型显示身份

- 状态：`ready`
- 类型：Local API、Chat、Models、Coder、Knowledge、Mobile/Mini Chat 与 Studio
  模型选择器。
- 用户可见变化：所有模型显示名统一为
  `(Source) Provider · Model`，Source 仅使用 `Cloud`、`Local`、`BYOK`；比如
  `(Cloud) OpenAI · ChatGPT 5.6 Luna`、`(BYOK) OpenAI · ChatGPT 5.6 Terra`和
  `(Local) AI2Apps-MLX · Qwen 3.8 27B NVFP4`。
- 合同与兼容边界：模型路由 ID、默认选择和已保存配置均不变；Local API 新增
  结构化 `identity` 并保留 `id` 作为唯一调用键。AI2Apps Cloud 服务不需改动，
  现有 Model/Runtime Package 不需重发；Local 根据现有 Cloud provider 字段与
  Package `runtime.provider` 生成展示身份。
- 需要进入 App 的主要文件：`ai2apps/model_identity.py`、
  `ai2apps/model_providers.py`、`ai2apps/api/cloud.py`、`ai2apps/api/readaloud.py`、
  `ai2apps/api/video_studio.py`、`omlx/api/openai_models.py`、`omlx/server.py`、
  `omlx/admin/routes.py`及相关 Web 模型选择器。
- 当前验证（2026-09-08）：新增 Model Identity 契约回归 `7/7`；Model Provider、
  Chat UI、Imagine Studio、Video Studio、Read Aloud 与 Mini-App Chat 联合回归
  `94/94` 通过；Cloud Client 与 Desktop Shell 联合回归 `154/154` 通过。其他
  涉及完整 oMLX Engine 导入的组合测试在当前无 Metal 的命令执行环境中会被
  MLX 主动终止。三实例目标已纠正为 `main`、`app-dev`、`test`：普通
  `AI2Apps-dev.app` 不属于本次更新范围，误启动的 Dev 已停止；固定 App-Dev 与 Test
  已通过各自标准构建入口刷新并启动。App-Dev 运行于端口 `50951`，实机 Chat 模型选择器
  显示 `(BYOK) OpenAI · ChatGPT 5.6 Luna`；Test 运行于端口 `50829`，保持未绑定账户的
  登录初始状态。两者主 App 与内嵌 Shell 的图标一致，托盘角标资源分别保持 App-Dev
  单橙点与 Test 双紫菱形，严格深度签名检查和 App 图标回归 `4/4` 通过。
- Release notes 建议：Chat 和各 Studio 现在使用一致的模型名称，可直接识别
  Cloud、本地与本地密钥来源，以及实际推理服务商。
- 纳入 Build：待定。

### NXR-041：新设备默认名称使用芯片型号与统一内存

- 状态：`ready`
- 类型：Cloud 设备注册、Desktop Shell 启动信息。
- 用户可见变化：新 Installation 绑定 Core 账户时，设备名不再采用浏览器兼容字段
  `navigator.platform` 所返回的误导性 `MacIntel`；Local 从 macOS 读取 Apple Silicon 芯片型号和
  统一内存，并生成紧凑名称，例如 `Apple M5 Max`、128 GiB 对应 `M5Max-128G`。
- 兼容边界：已经注册或由用户重命名的 Cloud 设备继续使用已保存名称；硬件型号无法识别时回退
  到系统主机名，登录页请求失败时保留可编辑的 `Mac` 占位值。登录页通过既有本机
  `/v1/platform/client/bootstrap` 合同取得默认值，不新增 Cloud API 或浏览器硬件指纹接口。
- 需要进入 App 的文件：`ai2apps/api/client.py`、`ai2apps/web/static/js/login.js`、
  `tests/test_ai2apps_client_bootstrap.py`。
- 当前验证（2026-09-08）：Client Bootstrap 定向回归 `9/9` 通过，覆盖
  `M5Max-128G` 格式、未知硬件主机名回退和已注册设备名优先级；JavaScript 语法、Ruff 与
  `git diff --check` 通过。沙箱不允许读取宿主 `sysctl`，真实 App 中的实机值留待候选构建验收。
- Release notes 建议：新设备现在默认使用芯片型号和统一内存命名，更容易在设备列表中识别。
- 纳入 Build：待定。

### NXR-040：固定的 AI2Apps-test 发布态测试实例

- 状态：`in_progress`
- 类型：macOS Desktop 构建、Helper、实例数据生命周期。
- 用户可见结果：新增固定 `AI2Apps-test.app`，使用与正式版相同的 cloud Runtime、签名和
  Release App 校验链，但采用独立 `com.ai2apps.desktop.test` Bundle ID 和 `test` instance ID，
  因而不会读写正式版、`dev` 或 `app-dev` 的 User Data。旧测试 App 在替换前归档。
- 测试版专属能力：只有带签名 `AI2AppsAllowInstanceDataReset` 开关的 Helper 显示“重置数据…”；
  用户二次确认后停止 Local、关闭测试 Shell 和 Agent，删除 test 实例的 Application Support 与
  Caches 根目录并退出。公共 `~/.cache/huggingface/hub` 明确不属于删除目标。
- 自动化 fresh-install：Test Helper 的认证 loopback 控制通道新增 `instance.reset`，但仅在签名
  reset capability、固定 `com.ai2apps.desktop.test`、instance `test`、Harness actor 和显式
  `confirm_instance_id=test` 全部匹配时接受。CLI 的 `--fresh-install` 通过该操作复用菜单对应的
  `InstanceDataReset`，不在 Harness 中直接递归删除目录；失败时选定测试范围统一 BLOCKED。
- 托盘身份：Test 的四种 Helper 状态图标统一叠加左上角和右上角两个紫色菱形；保留原状态
  图案，同时与正式版无角标和 App-Dev 左上角单个橙色圆点明确区分。
- App 图标与 App-Dev：Test 主 App 与内嵌 Shell 的全尺寸 `.icns` 将球体上半部改为浅蓝色；
  App-Dev 对应区域改为淡紫色。构建期从原图各原生尺寸着色，保留渐变、黑色 Logo、边框和
  下半球。App-Dev 同时获得与 Test 相同的实例级“重置数据…”能力，只清理 `app-dev` 私有根。
- 安全边界：重置目标由 `InstancePaths` 生成并再次校验为两个互不嵌套的实例私有根；删除前
  拒绝目标及关键父目录中的符号链接。正式版和通用 `dev` 实例没有该菜单能力。
- 构建防回退：专用图标已从包装脚本参数提升为共享 Release 构建合同。任何入口只要使用
  Test 或 App-Dev 的保留身份字段，就必须使用完整固定身份；共享构建器自动强制对应色彩与
  托盘角标，并在签名前校验主 App/内嵌 Shell 图标一致及四种 Helper 状态角标完整。标准
  production、`main` 和通用 `dev` 构建反向禁止携带这些专用图标。签名后的主 App、Shell
  与 Helper 还会写入一致的 `AI2AppsIconContract`，通用 Release verifier 会再次按实例身份
  独立检查该合同和实际角标，避免其他构建入口绕过包装脚本。
- 需要进入 App 的文件：
  - `apps/ai2apps-acefox/scripts/build-test-app.sh`
  - `apps/ai2apps-acefox/scripts/build-app-dev-environment.sh`
  - `apps/ai2apps-acefox/scripts/build-release-app.sh`
  - `apps/ai2apps-acefox/scripts/tint_app_icon.py`
  - `apps/ai2apps-acefox/Sources/AI2AppsContracts/InstanceDataReset.swift`
  - `apps/ai2apps-acefox/Sources/AI2AppsHelper/main.swift`
  - `apps/ai2apps-acefox/Sources/AI2AppsHelper/HelperControlServer.swift`
  - `ai2apps/helper_control.py`
  - `ai2apps-test-system/src/ai2apps_test/accounts.py`
  - `ai2apps-test-system/src/ai2apps_test/cli.py`
  - `ai2apps-test-system/src/ai2apps_test/runner.py`
  - `apps/ai2apps-acefox/Tests/AI2AppsContractsTests/ContractsTests.swift`
  - `tests/test_ai2apps_shell.py`
  - `tests/test_ai2apps_app_icon.py`
  - `ai2apps-test-system/docs/test-app.md`
  - `docs/ai2apps-app-dev-environment.md`
- 当前验证（2026-09-08）：Swift Package 全量 `74/74`、Desktop Shell `111/111` 通过，新增
  用例确认私有 Support/Cache 会被删除、公共 HF cache 保留，并拒绝符号链接父目录；Shell 脚本
  语法与 `git diff --check` 通过。标准测试版构建入口已生成 689 MiB 固定
  `AI2Apps-test.app`，内部与最终路径两轮 `verify-release-app.sh` 及严格深度 codesign 均通过。
  签名元数据确认 Bundle ID `com.ai2apps.desktop.test`、instance `test`、Runtime profile `cloud`、
  无 Development 标记，且 Helper 的 reset capability 为 `true`。实机启动后 Helper、Local 与 Shell
  均发布 `test` 身份，Local 在自动端口 `58778` 达到 `ready`；Computer Use 可确认测试 Shell
  独立运行，但本轮辅助功能层读取托盘菜单超时，未执行具有永久删除效果的实际菜单确认操作。
  同日新增 Test 专属托盘身份后，Desktop Shell 回归仍为 `111/111`；四份最终 Helper SVG 均通过
  XML 校验并同时包含左右两个紫色菱形角标，固定 App 再次通过两轮 Release 校验和严格深度
  codesign。最后一个单角标制品已归档为 `.build/archive/AI2Apps-test-20260908-014259.app`。
  2026-09-08 后续图标预览与成品像素抽样确认 Test 浅蓝、App-Dev 淡紫均只改变上半球并保留
  原渐变。Test 与 App-Dev 已分别用标准固定入口重建，旧制品归档为
  `.build/archive/AI2Apps-test-20260908-020057.app` 和
  `.build/archive/AI2Apps-app-dev-20260908-020238.app`；两者严格深度 codesign 均通过，主 App
  与内嵌 Shell 图标着色一致，Helper 的签名 reset capability 均为 `true`。图标与 Shell 联合回归
  `116/116`、Ruff 和 `git diff --check` 通过。Computer Use 按精确固定路径启动两者后，Test 在
  端口 `65486`、App-Dev 在端口 `65341` 达到 `ready`，Helper、Local、Shell descriptor 分别发布
  正确的 `test` / `app-dev` 身份。为避免破坏长期实例数据，没有在验收中确认执行最终删除按钮；
  删除行为由 Swift 隔离、HF cache 保留及符号链接拒绝测试覆盖。
  2026-09-08 实机首次执行 App-Dev 重置暴露了只读制品目录兼容问题：已验证的 Runtime Package
  与模型 distribution 使用 `0555` 目录权限，Foundation 递归删除在这些目录停止，并以未本地化的
  `ContractError error 1` 弹窗结束。重置器现在先在两个实例私有根内逐层恢复目录所有者的
  `rwx` 权限，再执行删除；内部符号链接只作为链接删除且不会跟随，公共 HF cache 仍不在目标中。
  重置时 Shell/Agent 改为强制退出，避免已经确认重置后再次出现 AceFox 的 Quit 对话框；
  `ContractError` 同时提供可读错误描述。包含真实 `0555` 目录树、内部/父级符号链接及公共 cache
  保留的 Swift 全量回归 `76/76` 通过，Shell 回归 `112/112` 与 `git diff --check` 通过。共享修复已
  通过两个标准入口进入新的固定 App，原 Test 与 App-Dev 分别归档为
  `.build/archive/AI2Apps-test-20260908-022304.app`、
  `.build/archive/AI2Apps-app-dev-20260908-022429.app`；两个新包再次通过双层 Release verifier、
  严格深度签名检查并保留 reset capability。修复后的 App-Dev 按固定路径启动，在端口 `51853`
  达到 `ready`，三个 descriptor 均确认 `app-dev` 身份。
  2026-09-09 新增 `--fresh-install` 与受限 Helper reset 控制操作；Swift 全量回归 `76/76`、
  Helper 控制回归 `13/13`、Harness 全量回归 `41/41` 通过；顶层
  `./bin/ai2apps-test --fresh-install` 已验证会转换为 fresh-install 选择流程。固定 Test App 已通过标准
  `build-test-app.sh` 重建，双层 Release verifier 与严格深度签名校验通过；包内 Helper 已确认包含
  `instance.reset`、Harness actor 和显式确认字段。真实删除验收会清除 `test` 实例数据，留待用户
  明确启动 fresh-install 测试时执行。
- Release notes 建议：不适用；这是发布前测试环境，不进入正式用户 App。
- 纳入 Build：测试工具本身需随仓库保留；测试专属 Bundle 标记不进入正式 Build。

### NXR-038：重复启动同一实例时激活现有窗口

- 状态：`ready`
- 类型：macOS Desktop Launcher、实例生命周期
- 用户可见问题：同一个 AI2Apps 实例已经运行时，再次从 Finder 启动该 App 会继续尝试为同一
  Profile 创建 AceFox 进程，最终显示 Firefox“一次只能打开一个副本”的错误对话框，而不是回到
  已打开的 AI2Apps 窗口。
- 修复：Launcher 在启动 Helper 后、创建新 AceFox 进程前读取该实例的 Shell run descriptor；仅当
  PID、instance ID、Shell/Main bundle identity 和实时可执行文件身份全部通过校验时，直接激活该
  Shell 的全部窗口并成功退出 Launcher。身份不匹配或进程不存在时仍执行正常启动；更新后的 App
  handoff 明确绕过复用路径，继续完成新版本健康启动。
- 需要进入 App 的文件：
  - `apps/ai2apps-acefox/Sources/AI2AppsLauncher/main.swift`
  - `docs/ai2apps-desktop-next-release.md`
- 当前验证：Swift Package 全量回归 `72/72` 通过，`git diff --check` 和固定开发 App 的
  `codesign --verify --deep --strict` 通过。已由标准 `build-dev-app.sh` 重建固定
  `AI2Apps-dev.app`，旧版归档为 `AI2Apps-dev-20260907-232822.app`。实机首次启动 Shell PID
  为 `71397`、Local 端口为 `63049`；随后在 Finder 再次打开同一 App，原窗口被置于前台，
  Shell descriptor 的 PID 与发布时间均未变化，且未出现 Firefox 重复实例对话框。固定
  `AI2Apps-app-dev.app` 也已通过专用 `build-app-dev-environment.sh` 重建，旧版归档为
  `AI2Apps-app-dev-20260907-233506.app`；实机确认 `app-dev` 以 cloud Runtime 在端口 `63813`
  就绪，窗口标题为 `AI2Apps-App-Dev: M5Max128G · App-Dev 127.0.0.1:63813`，通用 `dev`
  实例仍独立运行在端口 `63049`。
- 纳入 Build：待定。

### NXR-034：源码挂载 Mini-App 的可执行开发 Sandbox

- 状态：`ready`
- 类型：App-Shell 开发基础设施、Package Mini-App 本地调试
- 用户可见问题：Development source mount 可以发现并挂载 Package Mini-App，但严格
  opaque-origin CSP 使受认证的外部 CSS/JavaScript 无法加载，页面只显示 Studio 的标题条；
  `connect-src 'none'` 同时阻止页面调用 mount-scoped Host Capability Broker。
- 修复：仅当 Entry 来源为 `development` 且 Runtime 显式设置
  `AI2APPS_ALLOW_DEVELOPMENT_RUNTIME=1` 时，sandbox 增加 `allow-same-origin`，并把
  `connect-src` 限制为当前 Local origin。已安装 Package、生产 Bundle 和未显式启用的
  Runtime 继续使用原 opaque-origin、`connect-src 'none'` 策略。
- 发行边界：该策略只用于源码态热开发；Package 发布前仍需实现并通过严格 sandbox 下的
  生产 Mini-App bridge/broker 验收，不得把开发例外带入正式制品。
- 需要进入 App 的文件：
  - `omlx/admin/routes.py`
  - `ai2apps/extensions/manager.py`
  - `tests/test_ai2apps_shell.py`
  - `tests/test_ai2apps_development_packages.py`
  - `docs/ai2apps-studio-mini-app-package-contract-v1.md`
  - `docs/ai2apps-app-development-guide.md`
- 当前验证：Development Package、Shell、Studio Capability Broker 和 Extensions 联合测试
  `146/146` 通过；关键 Ruff 规则和 `git diff --check` 通过。固定
  `AI2Apps-app-dev.app` 已通过标准脚本重建及签名验证，旧版本已归档；真实 App-Dev
  Studio 中五条 Media Voice Studio Suite Mini-App 均已显示完整交互内容，转写页面也已
  成功调用 mount-scoped Broker 并准确提示尚未配置模型，而不是停留在只有标题的空页面。
  独立的通用 `dev` 实例未被终止或改写。
- 纳入 Build：待定。

### NXR-035：Read Aloud Package Mini-App 草稿路由隔离

- 状态：`ready`
- 类型：App-Shell、Read Aloud、Package Mini-App 兼容性
- 用户可见问题：Read Aloud 打开 Package Mini-App 后，折叠或展开左右工作区会把 Package
  Mini-App ID 发送给仅接受内置定义的 Read Aloud draft API，右上角因此显示
  `Read Aloud Mini-App was not found`。
- 修复：宿主的延迟保存、直接保存和加载草稿都跳过 Package Mini-App；Package 页面继续通过
  自身状态和 mount-scoped Broker 管理任务数据，内置 Mini-App 的既有草稿机制保持不变。
  Read Aloud 脚本资源版本同时更新，避免 App-Dev 刷新后继续命中旧缓存。
- 需要进入 App 的文件：
  - `ai2apps/web/static/js/readaloud.js`
  - `ai2apps/web/templates/system_apps/readaloud.html`
  - `tests/test_ai2apps_studio_mini_app_client.py`
- 当前验证：Read Aloud 与 Studio Mini-App Client 回归 `9/9` 通过，JavaScript 语法和
  `git diff --check` 通过。固定 `AI2Apps-App-Dev` 刷新后，Audio Speaker Voice Replacement
  保持完整显示；连续切换输出面板不再出现 draft 404 或右上角红色错误。
- 纳入 Build：待定。

### NXR-036：Studio Package Mini-App 依赖状态采用真实 Capability Probe

- 状态：`ready`
- 类型：App-Shell、Read Aloud、Video Studio、Package Mini-App 能力发现
- 用户可见问题：Read Aloud 和 Video Studio 过去把 Package Mini-App 成功挂载直接解释为
  `Dependencies ready`，即使 Mini-App 的 mount-scoped Capability Probe 已明确报告模型未安装，
  宿主底部徽标仍会与页面内提示矛盾。
- 修复：共享 Studio Mini-App Client 新增 mount-bound capability probe；Read Aloud 和 Video
  Studio 按已声明能力的 `implemented`/`ready` 聚合结果显示依赖状态。未探测、探测失败或任一
  声明能力未就绪时均 fail closed 为 `Setup required`，成功挂载不再等同于依赖就绪。
- 需要进入 App 的文件：
  - `ai2apps/web/static/js/studio_mini_apps.js`
  - `ai2apps/web/static/js/readaloud.js`
  - `ai2apps/web/static/js/video_studio.js`
  - `ai2apps/web/templates/system_apps/readaloud.html`
  - `ai2apps/web/templates/system_apps/video_studio.html`
  - `ai2apps/web/templates/system_apps/imagine_studio.html`
  - `tests/test_ai2apps_studio_mini_app_client.py`
- 当前验证：Read Aloud、Video Studio、Studio Mini-App Client 与 Capability Broker 联合回归
  `27/27` 通过；三个 JavaScript 文件语法检查和 `git diff --check` 通过。固定
  `AI2Apps-App-Dev` 强制刷新并重新挂载 Audio Speaker Voice Replacement 后，页面内继续提示
  Detailed Transcription、MLX Demucs 和 MLX Seed-VC v2 尚未齐备，底部徽标同步显示
  `Setup required`，不再显示 `Dependencies ready`。
- 纳入 Build：待定。

### NXR-037：Studio/Mini-App 通用 ACPF Setup 按钮

- 状态：`ready`
- 类型：App-Shell、ACPF、Studio Package Mini-App 开发合同
- 用户可见结果：Read Aloud、Video Studio 与 Imagine Studio 的依赖徽标已统一为按钮；Package Mini-App 的
  `Setup required` 点击后直接进入 ACPF Profile 选择，不再要求用户离开 Studio 手工寻找模型。
  内置 Mini-App 同样沿用各 Studio 既有 ACPF 配置流程。
- 通用机制：共享 Studio Mini-App Client 从签名/校验后的 Mini-App requirements 读取主
  Capability，并以当前可信 Studio AppInstance 调用 ACPF。Package 只能声明语义能力，具体
  Runtime、Service Package、Checkpoint、版本和验证目标由 Host 内置 Profile 决定。Profile
  Registry 新增一个受信任 Profile 服务多个 Studio App ID 的兼容能力。
- 重启恢复修复（2026-09-07）：共享 Client 现在持久化最小化的 Mini-App 恢复上下文，并按
  `actionId=setup-mini-app` 区分 Package 配置与 Studio 内置模型配置。Runtime/Local 重启后，
  Read Aloud、Video Studio、Imagine Studio 会优先恢复原 ACPF Session、重新挂载发起配置的
  Mini-App，然后继续 Provider/Checkpoint 安装和 Readiness Probe；旧 Session 仍可按语义
  Capability 反推出来源 Mini-App。
- 真实旧 Session 修复（2026-09-07）：App-Dev Session
  `prv_fb601554b22f48dc82e47006aab6595d` 显示 Runtime 重启后的实际阻塞并非 Session 丢失，
  而是已发布的 `ai2apps/model-demucs-mlx 0.1.0` 在读取客户端版本上限绑定的 legacy
  `modelInstall` 之前被新制品校验提前拒绝；同时服务端 Session 列表没有返回带 return intent
  的 retryable failed Session。合同现仅对客户端内置白名单及其固定最高版本保留兼容，新的
  模型 Release 仍强制签名 `modelInstall`；服务端现在允许原 AppInstance 重新发现可重试失败。
  修复后精确重启 `app-dev` Local，刷新即恢复原“配置指定角色换声”面板；点击重试后三个模型
  Package 均通过校验并 finalizing，流程继续到 55% Sortformer Checkpoint 的 NVIDIA 许可确认页。
- Media Voice Profile：详细转写提供 Compact/Quality；音轨分离配置 MLX Demucs；音频和视频
  角色换声一次规划 oMLX Runtime、Detailed Transcription、MLX Demucs、MLX Seed-VC v2 及
  所需 Checkpoint/Service 验证；视频字幕配置详细转写，翻译作为可选 Capability 不阻断基础
  字幕工作流。探测失败继续 fail closed。
- ACPF 进度可读性与全量状态刷新（2026-09-07）：相同阶段、相同标题的组件合并为一行，
  例如 `下载所需模型 ×5`、`安装模型 Package ×3`，具体 Package/模型可按需展开；每组明确显示
  `已完成`、`进行中`、`失败` 或 `待处理`。运行对话框改为固定标题、固定底部总进度和操作按钮，
  只有中间步骤区域滚动。平台新增经过 Studio AppInstance 授权的批量 Capability Catalog Probe，
  Read Aloud、Video Studio、Imagine Studio 在目录加载、ACPF 恢复及安装完成后一次重算所有已安装
  Package Mini-App 的 readiness，不再只更新当前挂载项；旧 mount-bound Probe 与旧 Package 发现、
  安装机制保持兼容。
- 需要进入 App 的文件：
  - `ai2apps/provisioning/profiles.py`
  - `ai2apps/provisioning/profiles/studio-media-voice.yaml`
  - `ai2apps/api/studio_mini_apps.py`
  - `ai2apps/studio/capability_broker.py`
  - `ai2apps/web/static/js/capability_provisioning.js`
  - `ai2apps/web/static/js/studio_mini_apps.js`
  - `ai2apps/web/static/js/readaloud.js`
  - `ai2apps/web/static/js/video_studio.js`
  - `ai2apps/web/static/js/imagine_studio.js`
  - `ai2apps/web/static/css/capability_provisioning.css`
  - `ai2apps/web/static/css/readaloud.css`
  - `ai2apps/web/static/css/video_studio.css`
  - `ai2apps/web/templates/system_apps/readaloud.html`
  - `ai2apps/web/templates/system_apps/video_studio.html`
  - `ai2apps/web/templates/system_apps/imagine_studio.html`
  - `packages/ai2apps-media-voice-studio-suite/app.yaml`
  - `tests/test_ai2apps_provisioning.py`
  - `tests/test_ai2apps_studio_capability_broker.py`
  - `tests/test_ai2apps_studio_mini_app_client.py`
- 当前验证：Package Discovery、Provisioning、Capability Broker、Studio Client、Read Aloud、Video Studio、Imagine Studio、Media
  Voice Package 与 Development Package 联合回归 `123/123` 通过；关键 Ruff、五个 JavaScript
  文件语法和 `git diff --check` 通过。固定 App-Dev Local 已单独重启至端口 `62551`，普通
  `dev` 实例未改动。Read Aloud 重新加载带 cache-buster 的共享 Client 后，Detailed
  Transcription、Voice and Background Separation、Audio/Video Speaker Voice Replacement
  四项 Package Mini-App 在左侧列表同时显示完成标记；逐项切换确认底部均为
  `Dependencies ready`，说明一次 Catalog Probe 已更新整列状态。ACPF 的聚合函数、四态标记、
  固定头尾与仅中部滚动结构已有自动回归覆盖；当前真实音频依赖已全部就绪，因此未为视觉验证
  人为卸载 Package 或 Checkpoint。
- 纳入 Build：待定。

### NXR-001：Package 多源竞速、分片校验与断点续传

- 状态：`ready`
- 类型：客户端功能、下载可靠性、ACPF/Discover 共用基础设施
- 用户可见结果：Package/Runtime 安装可读取签名 Snapshot 中任意数量的
  `artifact.sources`，按 piece 并发竞速，坏源或停滞源不会阻塞其他源；支持校验后断点
  续传，并保留旧单源完整下载兼容。
- 需要进入 App 的文件：
  - `ai2apps/packages/registry.py`
  - `ai2apps/api/packages.py`
  - `ai2apps/provisioning/orchestrator.py`
- 发行测试：
  - `tests/test_ai2apps_registry_v1.py`
  - `tests/test_ai2apps_provisioning.py`
- 已完成验证：相关 pytest `63/63` 通过；Ruff 通过；生产 Cloud 单源 Range fixture
  piece hash 匹配；旧单源 fallback 测试通过。
- Cloud 依赖进展（2026-09-03）：ModelScope `HEAD` 缺少 `Content-Length` 的严格
  `GET bytes=0-0` 回退已经部署生产；Cloud 使用生产校验器完成 457,410,846 字节制品、
  全量 SHA-256、piece manifest 与 Range 预检，265/265 测试通过。此项只解除服务端
  校验兼容阻塞，不代表外部 Source 已进入匿名 Snapshot。
- Source 发布进展（2026-09-03）：GitHub Source 已由 step-up admin 正式激活；公共
  Repository Snapshot v101 已匿名确认发布 Cloud + GitHub。ModelScope 正式复验的新
  validation 已完整通过；Cloud 状态转换热修上线后，该 Source 已由 step-up admin 正式
  激活。公共 Snapshot v102 的签名和 pin 验证通过，匿名清单已包含 Cloud、ModelScope、
  GitHub 三源；三个源的首个 8 MiB Range 均返回 `206`，大小和 piece SHA-256 完全一致。
- 客户端生产实测（2026-09-03）：使用当前客户端实现从公共 Snapshot v102 下载
  `ai2apps/runtime-omlx 1.5.7`，55 个分片全部完成，Cloud 与 GitHub 均实际成为过竞速
  胜出源；最终文件大小为 457,410,846 字节，完整 SHA-256 为
  `b7f5e0bddcf285908ddd75465c02bdd35a9f6aa90690c739054a75295ea4bd49`，与签名清单一致。
  ModelScope 本次因速度未胜出，但其独立 Range 206 和分片摘要验证已经通过。
- 后续 UI 复验发现客户端为每个 Range 请求发送了并非源站真实 ETag 的合成
  `If-Range: "sha256-…"`。ModelScope CDN 因条件不匹配按 HTTP 规范退回完整 `200`，
  因而在客户端竞速中被淘汰；GitHub 返回 `206` 掩盖了该问题。客户端已移除合成
  `If-Range`，继续以不可变 Source URL、精确 `Content-Range`、分片 SHA-256 和最终
  完整 SHA-256 为校验边界。
- 全新隔离 Dev App UI 验收（2026-09-03）：从零安装 `ai2apps/runtime-omlx 1.5.7`；
  ModelScope CDN 实际返回 `206 Partial Content`，并实际成为部分 piece 的竞速胜出源；
  Runtime 完成后自动进入重启、Package、Checkpoint、验证和启动流程，最终
  Provisioning Session 为 `ready / 100%`，Qwen3.8 27B NVFP4 已在 Chat 中连续完成两次
  本地推理。
- 客户端专项测试（2026-09-03）：Registry 与 Provisioning 共 63 项测试通过，覆盖多源
  竞速、超过并发数的候选源、停滞源淘汰、坏源回退、已验证分片断点恢复和旧单源兼容。
- 客户端全量回归（2026-09-03）：已将 App Catalog、Checkpoint 进度回调、Chat/Fusion
  UI、FLUX.2 4B 发布范围、Local Session 认证、Knowledge Service、Runtime 1.5.7 与
  Browser Agent 无 Dock 行为的旧测试断言同步到当前合同；AI2Apps Python `1146/1146`
  与 Swift `69/69` 通过。
- Build 2249 对照：直接检查 Build 2249 已公证 DMG 内嵌
  `AI2AppsLocal/app/ai2apps`，上述三项客户端实现未包含在 2249 中。
- 源码可复现性（2026-09-03）：`ai2apps/provisioning/orchestrator.py` 与
  `tests/test_ai2apps_provisioning.py` 已随本轮 development checkpoint 纳入版本控制，不再
  依赖 dirty-tree 隐式打包。
- 发行验证：全新隔离 Dev App 的 UI 安装与本地模型推理验收已完成。
- Release notes 建议：Package 与 Runtime 下载现支持多源竞速、逐分片完整性校验和断点
  续传；单个镜像不可用时可自动由其他镜像继续。
- 纳入 Build：待定。

### NXR-002：ACPF 安全复用用户已有 Hugging Face Checkpoint

- 状态：`ready`
- 类型：客户端功能、模型安装、磁盘与网络复用
- 用户可见结果：ACPF 在实例私有缓存未命中时，会只读检查当前 macOS 用户的标准
  Hugging Face Hub 缓存；若存在 Package 固定的 repo/revision，则仍按 Cloud 签名的
  Checkpoint Distribution 清单逐文件校验大小与 SHA-256，校验通过后纳入 AI2Apps 的
  私有安全缓存，不再重复下载模型权重。
- 安全边界：`HF_HOME`、Token、Worker 缓存及可变状态继续保持实例隔离；外部 Hub
  仅作为候选输入，不能绕过许可确认、签名清单、固定 revision 或完整哈希校验。
- 需要进入 App 的文件：
  - `apps/ai2apps-acefox/Sources/AI2AppsContracts/InstanceIdentity.swift`
  - `apps/ai2apps-acefox/Sources/AI2AppsSupervisorCore/LaunchPlan.swift`
  - `ai2apps/packages/supervisor.py`
  - `ai2apps/model_installer.py`
- 发行测试：
  - `apps/ai2apps-acefox/Tests/AI2AppsSupervisorCoreTests/SupervisorCoreTests.swift`
  - `tests/test_ai2apps_installer.py`
  - 全新隔离 Dev App 从 ACPF 安装 Qwen3.8 27B NVFP4；Runtime/Package 从零安装，
    Checkpoint 必须命中现有全局 HF cache 并完成校验导入，不得产生 21.83 GB 网络下载。
- 当前验证（2026-09-03）：重新构建的全新隔离 Dev App 从零完成 Runtime 与 Package
  安装；Checkpoint 阶段识别标准 Hugging Face Hub 缓存中的固定
  `unsloth/Qwen3.8-27B-NVFP4@16b6615a…`，仅访问 Cloud 签名 Distribution 清单，未产生
  21.83 GB 模型文件网络请求；逐文件校验及私有缓存导入完成，Provisioning Session 为
  `ready / 100%`，Chat 中本地模型连续两次返回 `OK`。
- 纳入 Build：待定。

### NXR-003：Local 重启后去重 ACPF 进度对话框

- 状态：`ready`
- 类型：客户端 UI、ACPF 状态恢复
- 用户可见问题：ACPF 安装 Runtime 后按提示重启 Local，恢复中的同一 Provisioning
  Session 会短暂显示两份内容相同的进度对话框；任务完成后两份都会消失，不影响安装
  或模型启动，但会造成重复反馈。
- 复现结果（2026-09-03）：全新隔离 Dev App 安装 Qwen3.8 27B NVFP4 时稳定复现一次。
- 根因与修复（2026-09-03）：Chat 的 Alpine `x-data` 对象包含自动执行的 `init()`，
  模板又通过 `x-init="init()"` 显式执行一次，导致重连后两次调用 ACPF `resume()`；已移除
  Chat 的重复显式初始化，并在 ACPF 公共库中增加跨调用的 Session-ID runner 注册表，
  重复 `resume/ensure` 共享同一 Promise、poller 和 overlay，终态后自动释放。
- 自动化验证：JavaScript 语法检查通过；Provisioning 与 Shell 合同测试 `142/142`
  通过；`git diff --check` 通过。
- UI 验收（2026-09-03）：使用 clean2 隔离实例将已备份 Session 临时恢复为待处理状态，
  通过认证 Helper 控制通道真实重启 Local，端口从 `60296` 切换至 `60581`；重启前后
  同一 Session 均只显示一个对话框。验收后已精确恢复该 Session 的原始 `ready / 100%`
  状态，未改动 Runtime、Package、Checkpoint 或全局 Hugging Face 缓存。
- 纳入 Build：待定。

### NXR-004：托盘 Helper 复用并激活对应 AI2Apps 实例

- 状态：`ready`
- 类型：客户端可靠性、Helper、实例生命周期
- 用户可见问题：从托盘选择“打开 AI2Apps”时，如果正在运行的开发版 App 在重新打包后
  被移动到归档路径，Helper 的严格路径校验会把同一实例误判为不存在，并尝试再启动一个
  AI2Apps App 实例。
- 修复方向：继续以 `run/shell.json` 的实例 ID 和 PID 为首选定位；严格路径校验未通过时，
  仅允许同一 Shell bundle ID、同一主 App bundle ID、同一 `AI2AppsInstanceID` 且实时
  可执行文件与其实际 Bundle 一致的存活进程作为激活回退。找不到可信对应进程时才启动
  新实例。
- 需要进入 App 的文件：
  - `apps/ai2apps-acefox/Sources/AI2AppsHelper/main.swift`
  - `apps/ai2apps-acefox/Sources/AI2AppsSupervisorCore/ShellProcessIdentityValidator.swift`
- 发行测试：
  - `apps/ai2apps-acefox/Tests/AI2AppsSupervisorCoreTests/ShellProcessIdentityValidatorTests.swift`
  - 对已被开发构建脚本移动到 `.build/archive/` 的运行实例执行托盘“打开 AI2Apps”，确认
    只激活原 PID，不产生第二个 Shell 进程。
- 当前验证（2026-09-03）：Swift `71/71` 通过；真实开发实例 PID `54855` 的
  `proc_pidpath` 已处于 `.build/archive/AI2Apps-dev-20260903-120936.app`，而
  `run/shell.json` 仍指向稳定的 `.build/AI2Apps-dev.app`，严格路径校验按预期失败；新回退
  校验确认该进程的 Shell bundle ID、主 App bundle ID、`AI2AppsInstanceID=dev` 与实际
  Bundle 可执行文件全部一致。修复后的 Helper 已从稳定开发 App 启动，当前 dev 实例仍仅有
  一个 Shell 进程。
- Release notes 建议：托盘“打开 AI2Apps”现在会可靠激活当前 Helper 对应的已有窗口，
  仅在该实例确实未运行时才启动新窗口。
- 纳入 Build：待定。

### NXR-005：账户密码最小长度统一为 8 位

- 状态：`ready`
- 类型：客户端兼容性、账户安全策略、Cloud 合同对齐
- 用户可见结果：注册、登录、密码重置以及管理员、设备和组织操作中的密码再认证统一接受
  8–128 个 UTF-8 字节的密码；7 字节密码仍会被拒绝。客户端与 Cloud 对中文、emoji 等
  非 ASCII 密码使用相同计数方式。
- 安全边界：不改变密码哈希、密钥存储、验证码、速率限制、权限检查或 step-up 有效期。
- 需要进入 App 的文件：
  - `ai2apps/password_policy.py`
  - `ai2apps/api/auth.py`
  - `ai2apps/api/cloud.py`
  - `ai2apps/api/packages.py`
  - `ai2apps/api/upstreams.py`
  - `ai2apps/web/templates/login.html`
  - `ai2apps/web/templates/system_apps/account.html`
  - `ai2apps/web/templates/system_apps/discover.html`
  - `ai2apps/web/static/js/discover.js`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
- Cloud 生产依赖（2026-09-03）：以实际生产 `1.39.0` 为基线完成同步发布，OpenAPI
  升至 `1.40.0`；主线提交 `f2032b1b19add0aa4d8dd0d219c86a3df436e6f1`，生产端口
  `3246`，容器 healthy、零重启。Node 24 干净容器全量测试 `273/273`，Trivy
  High/Critical 为 0，无数据库迁移，生产仍为 47 个迁移；7/8 字节边界、登录、管理员
  二次验证、owner reauth、公开合同与权限边界验收通过。旧容器和数据库/Nginx 备份已
  保留为回滚点。完整回执：
  `/Users/avdpropang/sdk/ai2apps-cloud/docs/account-password-policy-production-deployment-2026-09-03.md`。
- 发行测试：`tests/test_ai2apps_password_policy.py`，以及 Account、Local Auth、Cloud API、
  Package 和 Upstream 相关回归测试。
- 客户端验证（2026-09-03）：密码策略边界测试 `16/16`，包含 13 个请求模型的 OpenAPI
  长度合同、8 字节注册/登录成功、7 字节拒绝和非 ASCII UTF-8 边界；Account、Local Auth、Upstream、Package、
  Shell 相关回归合计 `169/169` 通过。Ruff、JavaScript 语法与 `git diff --check` 通过。
  首轮沙箱内 Package 回归有 8 项因禁止绑定临时回环端口失败，在允许本机 loopback bind
  后独立重跑 `30/30` 通过；旧管理员测试收集时的 MLX Metal 初始化 abort 属于无 GPU
  沙箱限制，不是本项断言失败。
- 纳入 Build：待定。

### NXR-006：固定且隔离的 App-Shell App 开发环境

- 状态：`ready`
- 类型：开发构建基础设施；不改变生产 App 的默认构建参数或运行行为。
- 开发结果：新增固定的 `AI2Apps-App-Dev` 环境，使用
  `.build/AI2Apps-app-dev.app`、Bundle ID `com.ai2apps.desktop.appdev` 和实例
  `app-dev`；它可与通用 `AI2Apps-dev.app`/`dev` 实例同时运行。
- 隔离边界：App Dev 构建内嵌 `cloud` Runtime、`omlx` 与依赖快照，不引用仓库
  `.venv`；受信任的 `ai2apps` 源码从当前工作树热挂载，日常 HTML/CSS/JavaScript 修改刷新
  页面即可生效，Python App/API 修改只需重启 Local。`omlx` 与依赖始终锁定到 Bundle，且
  Local 启动计划会剥离继承环境中的源码路径，只接受 Development Helper 从签名 Bundle
  合同显式注入。数据库、配置、日志、Cookie、浏览器 Profile、端口和缓存继续按实例隔离；
  不注册 Login Item，不读取生产更新清单。
- 托盘辨识：`app-dev` Helper 的普通、工作中、可更新和更新就绪图标均在标准图标左上角
  增加橙色圆点；生产 App 与通用 `AI2Apps-dev.app` 保持原图标。2026-09-03 重建后确认 Bundle
  内四个 SVG 均只包含一个开发圆点、XML 有效，严格签名验证通过；新 App 冷启动后 Helper、
  Shell 和 Local 已就绪，Local 端口为 `63716`。
- Shell 辨识：固定构建把主 App、AceFox Shell 及其所有本地化 Bundle 名称统一设置为
  `AI2Apps-App-Dev`；若上游 Shell `Info.plist` 不含 `CFBundleDisplayName`，构建时会显式补建，
  使 macOS 左上角应用名称不再回退为 `AI2Apps`。2026-09-03 最终 Bundle 已确认主 App 与
  Shell 的 `CFBundleName`/`CFBundleDisplayName` 以及本地化名称全部一致，严格签名验证通过；
  冷启动后 Helper、Shell、Local 均正常就绪，Local 端口为 `64163`。
- Shell 标题快照修复：定位到 packaged AceFox 的 `browser/omni.ja` 落后于通用 Dev App
  使用的当前 `shell.mjs`，旧快照没有 Local-aware 标题函数。App Dev 构建现在只在
  Development 模式下把匹配 AceFox 工作树中的当前 Shell 资源覆盖进 staged
  `browser/omni.ja`，并将标题前缀设置为 `AI2Apps-App-Dev`；生产构建默认不启用覆盖。最终
  Bundle 解包确认包含 Local-aware 标题函数及目标前缀，严格签名验证通过；真实 UI 冷启动
  验收的窗口标题为 `AI2Apps-App-Dev: MacIntel · AI2Apps 127.0.0.1:65050`，macOS 应用菜单名
  同时为 `AI2Apps-App-Dev`。
- 需要进入 App 的文件：
  - `apps/ai2apps-acefox/scripts/build-release-app.sh`
  - `apps/ai2apps-acefox/scripts/build-app-dev-environment.sh`
  - `apps/ai2apps-acefox/scripts/runtime-entrypoint.sh`
  - `apps/ai2apps-acefox/Sources/AI2AppsHelper/main.swift`
  - `apps/ai2apps-acefox/Sources/AI2AppsSupervisorCore/LaunchPlan.swift`
  - `apps/ai2apps-acefox/Sources/AI2AppsSupervisorCore/LocalProcessSupervisor.swift`
  - `apps/ai2apps-acefox/Tests/AI2AppsSupervisorCoreTests/SupervisorCoreTests.swift`
  - `apps/ai2apps-acefox/README.md`
  - `docs/ai2apps-app-dev-environment.md`
- 验证（2026-09-03）：Shell 脚本语法和 `git diff --check` 通过；最终构建通过
  `verify-release-app.sh` 和 `codesign --verify --deep --strict`。最终 Bundle 确认显示名为
  `AI2Apps-App-Dev`、Bundle ID 为 `com.ai2apps.desktop.appdev`、实例为 `app-dev`、
  Development 标记为 true、Runtime profile 为 `cloud`，且不存在生产 Update Manifest
  URL。最终 Bundle 冷启动后 `app-dev` Helper/Local/Shell 分别使用独立 PID，Local 就绪于
  自动端口 `63219`，运行描述指向固定 App 路径。
- 热挂载验证：Swift 全量 `72/72` 通过，新增测试确认未授权继承环境不能注入开发源码目录；
  使用内嵌 Python 验证 `ai2apps.__file__` 指向当前仓库、`omlx.__file__` 指向 App Bundle。
  Jinja 模板目录与静态资源目录均解析到当前仓库，且模板环境 `auto_reload=true`。
  在 Bundle 构建完成后向仓库新增静态探针，运行中的 Local 立即返回探针内容；删除后同一
  URL 立即返回 `404`，证明静态资源无需重建或重启即可刷新生效。
- 纳入 Build：不适用；这是本地开发环境入口，生产构建保持原默认值。

### NXR-007：Chat 显式控制 Knowledge 上下文

- 状态：`ready`
- 界面精简（2026-09-10）：删除 Chat 左侧对话列表底部重复的 Settings 按钮及空页脚，保留右侧 Settings 入口；新增单一设置入口回归断言。
- 推理署名（2026-09-10）：左下角新增低对比度说明，最终文案为“AI2Apps local inference built on oMLX”／“AI2Apps 本地推理，基于 oMLX 构建”，替换 powered by 以明确基础与扩展开发关系；明确限于本地推理以免误指 Cloud Provider。覆盖全部 9 种语言，保留右侧唯一 Settings 入口。
- 类型：客户端 UI、Chat 上下文控制、Knowledge Mini-Entry
- 用户可见结果：Chat 右侧选项栏的 Thinking 区块新增“使用 Knowledge”开关；关闭后，
  当前 Chat 的普通模型回复和 Agent Run 均跳过 Knowledge 检索。右侧展开箭头可直接打开
  Knowledge 侧边栏，并优先复用当前对话中已经存在的 Knowledge Mini-Entry。Thinking 与
  Use Knowledge 标题下的辅助说明暂时隐藏，以保持右侧设置栏紧凑。Chat 顶部的 App
  Mini-Entry 选择器只展示实际声明了 Mini-Entry 的 App，不再列出无法嵌入对话的 App。
- 状态边界：开关按 Chat 保存并同步到后端 Session metadata；新建及旧版未记录该字段的
  Chat 默认关闭（2026-09-10 调整），已保存的显式开关状态保持不变，分支 Chat 继承来源 Chat 的选择。开关只控制是否检索，不会
  删除或改写用户已经选择的知识桶。
- 需要进入 App 的文件：
  - `ai2apps/web/templates/chat.html`
  - `ai2apps/web/i18n/*.json`
  - `tests/test_chat_ui_overhaul.py`
- 验证（2026-09-03）：Chat UI、Shell、Knowledge、附件和工具调用相关测试共 208 项中
  207 项通过；唯一失败是既有 `chat.model_tab` 静态断言，与本项改动无关。专项的
  Knowledge 开关、全语言文案和右侧栏回归测试通过；补充验证空白新 Chat 尚未生成
  Session 时也可直接挂载 Knowledge Mini-Entry。固定 `AI2Apps-app-dev.app` 已刷新并在
  实机窗口确认开关可切换、右箭头可打开 Knowledge 侧边栏；`git diff --check` 通过。
- Release notes 建议：Chat 现在可以按对话显式开启或关闭 Knowledge，并可从 Thinking
  设置一键打开 Knowledge 侧边栏管理参与回答的知识桶。
- 纳入 Build：待定。

### NXR-008：Base App 恢复 Runtime-backed Audio API

- 状态：`ready`
- 类型：客户端回归修复、Audio Package Gateway、Chat TTS
- 用户可见问题：使用 `cloud` Runtime profile 的 inference-free Base App 安装并准备好
  TTS Runtime、模型 Package 和 Checkpoint 后，Chat 的“朗读”仍返回裸
  `404 Not Found`。
- 根因（2026-09-04）：`omlx.server` 为避免启动时导入 MLX，在 `cloud` profile 下跳过了
  整个 `audio_routes`；这同时误删了本应由 Base App 保留并代理到独立 Runtime Worker 的
  `/v1/audio/*` Package Provider Gateway。请求未进入已 ready 的 TTS Worker。
- 相关问题：Chat 会保留或自动选择 `checkpoint_ready=false` 的音频模型。本次实际准备的是
  Qwen3-TTS CustomVoice 8-bit，但界面选择了尚未准备的 Base 5-bit。
- 修复方向：将旧进程内音频引擎的 MLX/PCM import 保持为按需加载，在 Base App 中始终注册
  OpenAI-compatible Audio Router；Chat 自动选择模型时优先使用已经准备好的 checkpoint。
- 需要进入 App 的文件：
  - `omlx/server.py`
  - `omlx/api/audio_routes.py`
  - `ai2apps/web/templates/chat.html`
  - `tests/test_cloud_runtime_profile.py`
  - `tests/test_ai2apps_audio_packages.py`
- Cloud 边界：Base App 对未匹配到已安装 Package 的旧进程内音频模型明确返回 `503`，
  不再尝试导入 MLX；Runtime-backed Package 请求仍在此判断前正常路由。
- 自动化验证（2026-09-04）：Cloud profile 无 MLX import、Audio Router 注册、未知模型
  边界与 Chat 就绪模型选择合同共 `14/14` 通过；TTS、STT、STS 与 Voice 完整 Audio 回归
  `154/154` 通过（另有 6 项按测试配置 deselected）；`git diff --check` 通过。
- 实机验证（2026-09-04）：固定 `AI2Apps-app-dev.app` 完成重建与严格 Bundle 验证，Local
  就绪于端口 `61817`。Chat 自动选择已准备的 `Qwen3 TTS 1.7B CustomVoice 8-bit`，朗读
  正常开始并结束；Base App 向端口 `61844` 的 TTS Runtime Worker 连续两次发送
  `/v1/audio/speech`，均返回 `200 OK`。未知非 Package 模型探针返回预期 `503`。
- Voice 配置显示与偏好修复（2026-09-04）：原生 `<select>` 不再保留通过 `x-show` 隐藏的
  “Not supported”占位选项，动态创建的 TTS、角色与 Emotion 选项显式同步当前值；支持
  Emotion 的模型会显示真实选择。角色、速度和 Emotion 现在按 TTS 模型记住上次选择，
  没有历史偏好时分别使用首个可用角色、速度 `1` 与自然的 `neutral`。固定 app-dev 热加载
  实机确认 CustomVoice 显示名不再错位，Emotion 从错误的 “Not supported”恢复为
  `neutral`，选择 `happy` 后刷新仍为 `happy`。偏好同时写入实例专属浏览器 Profile 的
  loopback Cookie，在 Local 端口变化后仍可恢复；不同实例的 Profile 继续保持隔离。
- ASR 转写修复（2026-09-04）：Qwen3-ASR Runtime 1.5.7 在请求未指定 `max_tokens` 时仍向
  后端显式传入 `None`，覆盖模型自带的 `8192` 默认值并触发 `NoneType` 与整数比较错误。
  修正后的 Runtime Adapter 会省略未设置的可选参数，STT Engine 也会防御性过滤 `None`；
  Base App Gateway 对已安装的 Qwen3-ASR 1.5.7 临时补入其原生默认值，因此用户无需等待
  新 Runtime Package 发布即可恢复识别。Adapter 与 Package Gateway 专项测试 `25/25`
  通过，`git diff --check` 通过。首次只重启 Local 后实机仍复现，进一步确认 app-dev 只热挂载
  `ai2apps`，`omlx` 固定来自 Bundle，因而 Base Gateway 修复并未加载；随后已重建并严格
  签名验证固定 `AI2Apps-app-dev.app`，确认三处修复均已嵌入，切换到新 Bundle 的 Helper
  PID `10642` 后再次通过认证控制通道重启 Local。新 Local PID `10895`、端口 `53492`、
  状态 `ready`。完整旧进程内 STT 测试在当前无 Metal 设备的沙箱中无法运行，没有将该
  环境限制误记为产品失败。
- 开发 Build（2026-09-04）：通用 `AI2Apps-dev.app` 与固定 `AI2Apps-app-dev.app` 均已按
  各自规定脚本完成包含跨端口 Voice 偏好持久化修复的最终重建，签名验证后替换稳定路径，
  旧 Bundle 已归档；重启后 `dev` 与 `app-dev` 分别在独立 Local 端口 `65132`、`65117`
  ready。
- Release notes 建议：修复安装本地语音模型后 Chat 朗读仍显示 `Not Found` 的问题。
- 纳入 Build：`AI2Apps-dev.app`、`AI2Apps-app-dev.app`。

### NXR-009：Chat 右侧栏状态持久化

- 状态：`ready`
- 类型：客户端 UI 回归修复、Chat 工作区偏好。
- 用户可见问题：用户打开或关闭 Chat 右侧设置栏后刷新页面，界面会重新使用窗口宽度
  推导的默认状态，丢失用户刚才的选择。
- 修复（2026-09-04）：Chat 初始化时优先恢复当前浏览器 Profile 保存的右侧栏展开状态，
  每次切换后立即更新；没有历史状态时才继续使用原有的响应式默认值。偏好同时写入
  `localStorage` 和同 Profile 的 loopback Cookie，因此页面刷新以及 Local 端口变化后均可
  恢复；Terminal 内嵌 Chat 仍强制隐藏侧栏，且不会覆盖普通 Chat 的偏好。
- 需要进入 App 的文件：
  - `ai2apps/web/templates/chat.html`
  - `tests/test_chat_ui_overhaul.py`
- 验证（2026-09-04）：Chat UI 与 Shell 专项回归 `134/134` 通过，覆盖保存、恢复、
  跨端口 Cookie 与 Terminal 隔离；固定 `AI2Apps-app-dev.app` 实机先后确认“关闭后刷新仍
  关闭”和“打开后刷新仍展开”，`git diff --check` 通过。
- Release notes 建议：Chat 会记住右侧设置栏的展开或关闭状态。
- 纳入 Build：待定。

### NXR-010：Discover 模型一级分类与能力子分类

- 状态：`ready`
- 类型：客户端功能、Discover UI、Package 构建合同、Cloud Registry 查询合同。
- 用户可见结果：Discover 将模型从普通 Service 中独立出来，并提供文本、语音、多模态、
  图像、视频和向量子分类；语音分类继续按“全部语音 / TTS 语音合成 / ASR 语音识别”筛选，
  模型卡片直接显示 TTS 或 ASR 任务标签，并显示模型大小、最低内存、速度、能力及评分来源。
  模型安装会先选择具体模型配置，再通过持久化 ACPF Session 安装依赖与 Provider Package、
  下载 Checkpoint、处理许可确认并验证服务；“仅安装 Package”保留为详情页高级入口。
- 旧包兼容：客户端内置按 Package ID 和最高旧版本约束的对照表，当前已发布模型无需重建或
  重新发布；同一 Package 的下一版本以及新的模型 Package 必须在签名 `ai2apps.json` 声明
  `discovery.kind/categories/tasks`、完整 `modelProfile` 和 ACPF 安装索引 `modelInstall`。旧资料
  明确标为估算，新版本不会继承旧模型的大小、评分或安装索引。
- 需要进入 App 的文件：
  - `ai2apps/packages/discovery.py`
  - `ai2apps/packages/contract_v1.py`
  - `ai2apps/packages/registry.py`
  - `ai2apps/api/packages.py`
  - `ai2apps/provisioning/orchestrator.py`
  - `ai2apps/web/static/js/capability_provisioning.js`
  - `ai2apps/web/static/js/discover.js`
  - `ai2apps/web/templates/system_apps/discover.html`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
- Cloud 依赖：`docs/cloud-discover-model-categories-requirements.md` 与
  `docs/ai2apps-cloud-package-discovery-schema-requirements.md`；客户端在 Cloud 支持服务端
  过滤前提供最多 100 个 Service 结果的兼容过滤，完整分页验收后方可改为 `ready`。
- 文档与测试：`docs/model-worker-package-manual.md`、
  `tests/test_ai2apps_discover_categories.py`。
- 当前验证：Package 合同、旧版本映射完整性、下一版本强制声明、非模型 Service 防冒充、
  目录模型/普通 Service 分离、Audio Package、Model Provider 及 Registry 回归 `82/82`
  通过；Ruff、JavaScript 语法、i18n JSON 和 `git diff --check` 通过。固定 App Dev 完整
  重启后 Local 端口从 `59995` 更新为 `60762`，实机确认 Discover 出现“模型”一级分类及
  全部模型、文本、语音、多模态、绘图、视频、嵌入二级分类；“语音”筛选只展示对应模型，
  模型卡片正确显示 `MODEL` 与 `SPEECH` 标识。仅重启旧 Helper 管理的 Local 会继续使用
  Bundle 内快照；完整退出并重开固定 `AI2Apps-app-dev.app` 后源码热挂载正常生效。随后在
  Local 端口 `61759` 实机确认语音任务栏及卡片 TTS/ASR 标签；选择 TTS 后仅保留 Fish
  Audio、CosyVoice、Qwen TTS、VibeVoice 等语音合成模型。模型资料合同进一步覆盖现有
  28 个模型的版本受限估算映射、正整数大小/内存、1–5 评分和基准来源；专项测试 `11/11`
  通过，相关回归 `86/86` 通过。Local 端口 `64151` 实机确认模型卡片以两列紧凑指标显示
  大小、内存、速度、能力，并把旧表数据明确标记为“估算”；普通 Service 卡片不显示指标。
  Discover 模型安装改造后的 Package 合同、Registry API、ACPF 编排、Audio Package 与 Model
  Provider 联合回归 `123/123` 通过，Ruff、JavaScript 语法及 `git diff --check` 通过；固定 App
  Dev 完整重开后 Local 端口为 `57310`，原生窗口标题、`app-dev` 隔离身份和模型安装 API 路由
  均已核验，模型卡片按钮显示为 `Install model`。实机没有触发真实 Package 或 Checkpoint 下载。
- Release notes 建议：Discover 新增独立模型目录，可按文本、语音、多模态、图像、视频和
  向量能力快速筛选，并可直接比较大小、内存、速度和能力；现有模型无需重新安装。
- 纳入 Build：待定。

### NXR-011：Video Studio Phase 1.1 Shell 与 Run 工作区

- 状态：`in_progress`
- 类型：客户端 UI、Video Studio、任务恢复与重试。
- 用户可见结果：Video Studio 统一使用 Mini-App 术语；文生、图生和参考素材入口在切换时
  保留各自草稿；左右栏可折叠并在窄窗口中作为抽屉打开；生成结果栏显示当前 Run、执行
  步骤、模型 revision 和历史记录，失败、取消或过期的 Run 可从服务端冻结输入安全重试。
- 状态边界：Run 与历史继续以服务端持久任务为事实来源；`localStorage` 只保存当前
  Mini-App、左栏模式、折叠状态和所选 Run 等 Shell 展示偏好，不保存 Prompt 或媒体正文。
- 需要进入 App 的文件：
  - `ai2apps/api/video_studio.py`
  - `ai2apps/video/tasks.py`
  - `ai2apps/web/templates/system_apps/video_studio.html`
  - `ai2apps/web/static/js/video_studio.js`
  - `ai2apps/web/static/css/video_studio.css`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
  - `docs/ai2apps-studio-app-ui-design-standard-v1.md`
- 发行测试：
  - `tests/test_ai2apps_video_studio.py`
  - `tests/test_ai2apps_video_tasks.py`
- 当前验证（2026-09-04）：JavaScript 语法、中英文 i18n JSON、Ruff 和 `git diff --check`
  通过；按当前正式 schema v69 隔离并行迁移改动后，Video Studio Shell、API 与任务回归
  `17/17` 通过，包含冻结文字与图片输入 Retry。固定 App Dev 的 UI 控制接口连续超时，
  Chrome 与内置浏览器访问当前 Local 均停在登录页，因此登录后桌面与窄屏视觉验收仍待完成。
- Release notes 建议：Video Studio 现在会分别保留三个内置 Mini-App 的创作草稿，支持
  可折叠与窄屏工作区，并提供更完整的 Run 详情、历史和安全重试。
- 纳入 Build：待定。

### NXR-012：AceFox 本地文件原生路径

- 状态：`in_progress`
- 类型：AceFox 平台能力、本地文件、内存效率与安全边界。
- 用户可见结果：用户从 Finder 拖入文件或通过系统文件选择器打开文件时，AI2Apps Local
  页面可从同一个磁盘后备 `File` 对象读取真实路径；视频等大文件可以把路径交给本地服务
  流式处理，无需先调用 `FileReader` 或 `arrayBuffer()` 将完整内容放入 JavaScript 内存。
- 安全边界：保留 Firefox 原有 `mozFullPath` 的 `ChromeOnly` 限制；新增的
  `mozAI2AppsFullPath` 只允许当前已由 Helper 验证并启动的精确
  `http://127.0.0.1:<port>` Local origin 读取。Shell 在重连前和退出时撤销 origin，普通网页、
  其他 loopback 端口和无效配置均得到 `SecurityError`；纯内存 `File` 返回空路径。
- 需要进入 App 的 AceFox 文件：
  - `dom/webidl/File.webidl`
  - `dom/file/File.h`
  - `dom/file/File.cpp`
  - `modules/libpref/init/StaticPrefList.yaml`
  - `modules/libpref/moz.build`
  - `browser/components/ai2apps/content/shell.mjs`
- 发行测试：
  - `dom/file/tests/test_ai2apps_native_path.html`
  - 使用 Finder 拖拽与系统文件选择器分别选择一个大视频，确认两条入口得到相同真实路径，
    且 App 处理期间 JavaScript 堆不随视频大小线性增长。
- 当前验证（2026-09-04）：Firefox 启用测试的完整 `mach build` 与 release
  `mach build binaries` 成功；新增 headless Mochitest 的磁盘路径、内存文件和跨 origin 拒绝
  `4/4` 通过，其中分别覆盖拖拽列表与文件输入列表。开发 App 实机拖拽/文件选择及大视频
  内存曲线验收尚待完成。通用 `AI2Apps-dev.app` 与固定 `AI2Apps-app-dev.app` 已基于重新打包的
  AceFox 快照完成重建、临时签名与严格 Bundle 验证；重启后两个 Local 分别健康运行于
  `51851`、`51861`，原生窗口标题分别绑定 `dev` 与 `app-dev` 环境。
- Release notes 建议：AI2Apps 现在可直接引用通过拖拽或文件选择器打开的本地大文件，降低
  视频、音频等素材进入本地工作流时的内存占用。
- 纳入 Build：待定。

### NXR-013：Read Aloud Studio v1 对齐

- 状态：`in_progress`
- 类型：客户端 UI、Read Aloud、Studio Run/Artifact、Gallery 资源交付与任务恢复。
- 用户可见结果：Read Aloud 左栏统一使用 Mini-App 术语并加载五个版本化内置描述符；
  右栏升级为可恢复的 Run Workspace，展示状态、总进度、Step、音频 Artifact 和历史，
  支持取消、失败重试、原生下载和保存到 Gallery；单句试听与整项目渲染使用同一持久任务链。
- 状态与安全边界：创作表单按 AppInstance 和 Mini-App 保存服务端草稿；Run、Step 和
  Artifact 以服务端数据库为事实来源；Gallery 音频经用户、Installation、AppInstance 和
  consumer 绑定的短期 Resource Handle 交付，不暴露宿主文件路径。`localStorage` 仅保存
  当前 Mini-App 这一展示偏好。
- 响应式与可访问性：桌面三栏支持独立折叠；中等宽度降级为两栏；Mobile 提供
  Mini-Apps / Create / Output 分层导航；补充键盘素材选择、焦点样式、进度语义和图标按钮标签。
- 需要进入 App 的文件：
  - `ai2apps/api/readaloud.py`
  - `ai2apps/readaloud/tasks.py`
  - `ai2apps/studio/repository.py`
  - `ai2apps/gallery/repository.py`
  - `ai2apps/api/gallery.py`
  - `ai2apps/storage/migrations.py`
  - `ai2apps/platform_runtime.py`
  - `ai2apps/web/templates/system_apps/readaloud.html`
  - `ai2apps/web/static/js/readaloud.js`
  - `ai2apps/web/static/js/gallery.js`
  - `ai2apps/web/static/css/readaloud.css`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
- 发行测试：`tests/test_ai2apps_readaloud.py`、`tests/test_ai2apps_readaloud_tasks.py`、
  `tests/test_ai2apps_gallery.py`、`tests/test_ai2apps_platform_storage.py`。
- 当前验证（2026-09-04）：Read Aloud、渲染任务和 Gallery 专项回归 `18/18` 通过，平台
  schema/迁移关键用例 `5/5` 通过；Python 编译、Ruff、JavaScript 语法、中英文 JSON 和
  `git diff --check` 通过。平台存储联合回归在进入与本改动无关的 MLX 服务生命周期用例时
  因当前沙箱无 Metal 设备中止。固定 `AI2Apps-app-dev.app` 的 Local 已通过受认证 Helper
  控制通道重启，最终端口 `64314` 返回平台健康 `ok`、数据库与目标 schema 均为 v70；
  实例数据库确认五张 Studio/Gallery 表及 Read Aloud 的 Mini-App/placement/model revision
  列均已落地，OpenAPI 已公开 Read Aloud `mini-apps`、`drafts` 和 `runs` 路由。
- Release notes 建议：Read Aloud 现在以 Mini-App 组织创作入口，语音生成会保存为可恢复、
  可下载、可加入 Gallery 的 Run 和 Artifact，并改进窄屏与键盘操作体验。
- 纳入 Build：待定。

### NXR-014：Imagine Studio Mini-App 与持久 Run 工作区对齐

- 状态：`ready`
- 类型：客户端 UI、Imagine Studio、Studio Run/Artifact、Gallery Resource Handle、草稿恢复。
- 用户可见结果：Imagine Studio 的三个现有创作入口升级为版本化内置 Mini-App；Studio Shell
  明确分离左侧 Mini-App/素材发现区、中间受信任 Adapter 创作面和右侧 Run 工作区。右栏统一展示
  Run、Step、Artifact、进度、错误、取消、重试、原生下载和加入 Gallery，旧生成历史会投影到新的
  Run/Artifact 模型中，避免升级后丢失结果。
- 状态与安全边界：创作草稿按用户、AppInstance 与 Mini-App 持久保存；Run、Step、Artifact 以
  平台数据库为事实来源；Gallery 拖放仅传递 Asset Reference，由服务端签发绑定 consumer App 与
  AppInstance 的短期 Resource Handle，再触发标准 `gallery.asset.drop`，不向 Mini-App 暴露宿主路径。
- 响应式与发现体验：左右栏可独立折叠；窄屏提供 Mini-Apps / Create / Output 分层导航；Mini-App
  发现区支持搜索、状态与版本展示、收藏和最近使用，并补充键盘焦点样式。
- 需要进入 App 的文件：
  - `ai2apps/api/imagine_studio.py`
  - `ai2apps/api/gallery.py`
  - `ai2apps/gallery/repository.py`
  - `ai2apps/studio/repository.py`
  - `ai2apps/storage/migrations.py`
  - `ai2apps/config.py`
  - `ai2apps/apps/system.py`
  - `ai2apps/web/templates/system_apps/imagine_studio.html`
  - `ai2apps/web/static/images/imagine-studio/styles/*.webp`
  - `ai2apps/web/static/js/imagine_adjust.js`
  - `ai2apps/web/static/js/imagine_style_catalog.js`
  - `ai2apps/web/static/js/imagine_studio.js`
  - `ai2apps/web/static/css/imagine_studio.css`
- 发行测试：`tests/test_ai2apps_imagine_studio.py`、`tests/test_ai2apps_gallery.py`、
  `tests/test_ai2apps_platform_storage.py`。
- 当前验证（2026-09-04）：Imagine Studio、Gallery 与 schema/迁移专项回归 `17/17` 通过；Python
  编译、JavaScript 语法与 `git diff --check` 通过。固定 `AI2Apps-app-dev.app` 的 Helper、Local 与
  Shell 已按 `app-dev` 身份重启，Local 确认 schema v70，新 Shell 连接端口 `49372`；实机验收确认
  新版 Mini-App 发现区和 Render workspace 已加载，旧 `CURRENT PIPELINE` 界面不再出现。测试退出时
  nanobind 报告当前沙箱没有 Metal 设备，但 pytest 结果为成功，且该提示与本项非模型 UI/存储改动无关。
- 后续修正（2026-09-04）：Cloud 模型目录 ID 在进入 Imagine Studio 时统一规范为
  `cloud/ai2apps/<provider>/<model>` Gateway ID，修复裸 `openai/gpt-image-2` 被误判为未启用本地
  Provider、导致图片生成返回 `404 Image model is not enabled` 的问题；Imagine Studio 与 Cloud
  Gateway 回归 `18/18` 通过，并在 App-Dev 中重新挂载确认 Cloud 图片模型恢复为可生成状态。
- 鉴权修正（2026-09-04）：Imagine Studio 按模型来源拆分请求路径；Cloud 模型改走
  `/v1/platform/cloud/ai/images/*`，由平台注入当前 Principal 对应的 Cloud Device 身份，本地 Package
  模型继续使用 `/v1/images/*`。修复低层兼容端点丢失用户身份后返回
  `401 AUTHENTICATION_REQUIRED` 的问题；相关回归 `18/18` 通过，并在端口 `51861` 的 App-Dev
  中重新挂载确认鉴权错误横幅消失、Generate 恢复可用。
- 草稿兼容修正（2026-09-04）：加载旧草稿时将裸 Cloud 模型 ID 迁移到规范 Gateway ID，避免
  无匹配 `<option>` 时浏览器错误回退到目录第一项。实机确认先前的旧 GPT Image 2 草稿曾因此
  被切换到 Google Gemini 3.1 Flash Image；该 Google Provider 当前由 Cloud 返回 502，本地不
  篡改其服务状态，当前 App-Dev 草稿恢复选择 GPT Image 2。
- 长任务可靠性修正（2026-09-04）：实机日志确认 GPT Image 2 Cloud 请求已返回 `200` 且 Cloud
  Request 状态为 `completed`，但原同步浏览器请求在大体积 Data URL 返回前断开，界面仅显示
  `NetworkError`，成功图片也未进入历史。Cloud 图片生成现由 Local 后台执行持久 Run：提交接口
  立即返回 `202`，服务端持有 Cloud 请求、校验并落盘图片、创建 Artifact 后更新 Run 终态；前端
  只轮询短请求，并会在页面重新挂载后继续监控进行中的 Run。Cloud Device 身份头与幂等键均由
  服务端传递；本地 Package 模型仍使用原本的前端直连流程。Imagine Studio 与 Cloud Gateway
  回归 `18/18` 通过，Ruff、Python 编译和 JavaScript 语法检查通过。固定 App-Dev 的 Helper、
  Local 与 Shell 已按 `app-dev` 身份重启，Local 在端口 `55538` 以 schema v70 就绪；实时 OpenAPI
  已公开后台执行路由，Imagine Studio 已重新挂载。扩展联合回归在前 `45` 项通过后，仍于既有
  MLX 服务生命周期用例因当前沙箱无 Metal 设备退出。
- Google Provider 外部阻塞（2026-09-04）：后台 Run 上线后，GPT Image 2 使用相同提示词、
  `1536x1024 / auto / png` 参数成功并持久化 Artifact；Google Gemini 3.1 Flash Image 随后由
  Cloud 明确返回 `502 AI_PROVIDER_ERROR`，证明不是 Desktop 断线、鉴权或落盘问题。Cloud 修复、
  模型目录能力与生产验收要求已记录在
  `docs/cloud-google-gemini-image-provider-repair-requirements.md`；在 Cloud 完成修复前不建议继续
  让用户付费重试该 Google 模型。
- Google Provider 对接完成（2026-09-04）：Cloud 已以 OpenAPI `1.41.0`、数据库迁移 48 部署
  Google 正式 `generationConfig.imageConfig` 合同。Desktop 不再按模型名硬编码尺寸能力，改从
  顶层 `imageOptions` 渲染固定画幅、质量和输出格式；Google 的非方形尺寸继续以
  `1536x1024 / 1024x1536` 作为 3:2、2:3 请求别名，并在 UI 明示实际像素由模型返回决定。
  后台 Run 以响应的 `image.size`、`image.format` 和 Data URL MIME 保存实际尺寸与 JPEG 文件，
  同时在 Artifact 元数据保留请求尺寸/格式。专项回归 `18/18` 通过；固定 App-Dev 在端口
  `61299`、schema v70 就绪，实机目录确认 Google 仅有 Auto 质量以及 Auto、1:1、3:2、2:3
  尺寸选项。尚待用户授权一次生产付费生成，验证 Run、Artifact 落盘与刷新恢复。
- Google 尺寸文案修正（2026-09-04）：按产品要求，Google 尺寸下拉不再显示 Cloud 协议层的
  `1536x1024 / 1024x1536` 兼容别名，而显示当前生产真实输出 `1264x848 / 848x1264`；选项
  内部值仍使用 Cloud 接口要求的 3:2、2:3 兼容别名，避免提交不受支持的像素值。方形继续显示
  `1024x1024`，旁注明确这些是 Google 当前的 1K 输出尺寸。
- Image 核心风格选择（2026-09-04）：将原高级设置中的 5 项纯文字下拉升级为跨 Mini-App 的
  Image 核心能力，默认保持“无风格”；文生图、图片编辑与参考图创作共用同一个选择和状态，
  切换 Mini-App 时不再被各自草稿覆盖。对话框按写实、艺术绘画、现代视觉、游戏/动漫四类展示
  51 种风格及对应示例图，并在应用后把所选风格提示词追加到所有生成或编辑请求。素材复用自既有风格库，
  修正了重复微距、Modern 拼写以及巴洛克/哥特中文错位，补入 8 位像素风格；51 张 256px PNG
  转为随 App 发布的 WebP，体积由约 9.7 MB 降至约 1 MB。旧草稿的简版风格 ID 会自动映射，
  选择状态保存为 Imagine Studio 级偏好，同时继续写入 Run 和 Mini-App 草稿以支持追溯与旧数据迁移；
  对话框支持取消、Escape、遮罩关闭、键盘焦点与窄屏双列布局。
  Imagine Studio、Cloud Gateway 与图片 API 专项回归 `20/20`、两份 JavaScript 语法和
  `git diff --check` 通过；固定 App-Dev 端口 `61299` 实机确认 51 张缩略图加载、分类切换、
  风格选择和应用后主界面回显正常，并确认在 Image Edit 选择 `Realism` 后切换到 Reference
  Creation 仍显示同一风格，验收未触发图片生成。
- 调整图片 Mini-App（2026-09-04）：新增版本化内置 `ai2apps.imagine.adjust-image`，在本机使用
  Canvas 对单张图片进行非 AI、非破坏性参数调整。支持原始比例及 1:1、4:3、3:4、16:9、9:16
  中心裁剪，左右旋转、水平/垂直翻转，以及曝光、鲜明度、高光、阴影、对比度、亮度、饱和度、
  自然饱和度、黑点、颜色平衡、色温、色调、锐度、清晰度、噪点消除和晕影；支持实时预览、
  撤销、重做和复原。预览限制长边以保证交互流畅，完成时按裁剪后的原始分辨率重新渲染无损 PNG，
  并保存为标准 Run/Artifact，可继续下载或加入 Gallery；整个调整过程不调用 Cloud 或本地 AI 模型。
  Imagine Studio、Cloud Gateway 与图片 API 联合回归 `21/21`，两份 JavaScript 语法、
  Python 编译和 `git diff --check` 通过；通过标准 App-Dev builder 刷新固定开发 App，
  旧 App 已归档为 `AI2Apps-app-dev-20260904-222136.app`。端口 `55270`（重载后 `56956`）实机确认
  Mini-App 数由 6 增至 7，调整工作区、全部 16 项参数、裁剪比例与旋转/翻转入口正常。
  实际导入 3456×2234 和 512×512 图片验收时，发现 AceFox 不支持通过
  `fetch(data:)` 将 Canvas Data URL 转回 Blob，已改为纯本地 Base64 解码；复测完成旋转、
  512×512 PNG 导出、Run 成功状态和 Artifact 落盘，重载并重新打开
  Imagine Studio 后仍可恢复该 Run、预览和 Artifact。
  后续修正 Gallery 新图导入的调整状态边界：用户拖入或更换图片时重置旋转、
  翻转、裁剪和色彩参数，只有恢复同一草稿的 Gallery 素材时才恢复已保存的调整。
  大图保存链路进一步改为直接从 Canvas 异步生成二进制 PNG Blob，再切成 192 KiB 小块经
  专用 JSON 结果接口顺序上传，绕开 AceFox 中会中断 Canvas Blob/multipart 请求的路径；
  同时避免先生成大体积 Data URL、再 Base64 解码成文件所造成的额外内存峰值。服务端限制
  单块与整图大小、隔离 App Instance/Actor/Installation，并清理十分钟未完成上传；Cloud 图片
  结果仍保留 Data URL 与原 multipart 接口的兼容路径。Imagine Studio 专项回归 `9/9`、
  JavaScript/Python 语法和 `git diff --check` 通过；标准 App-Dev builder 已刷新固定开发 App，
  旧 App 归档为 `AI2Apps-app-dev-20260905-001852.app`。端口 `51468` 实机以 1264×848、
  饱和度 100、自然饱和度 57 的草稿复测，Run 成功、Artifact `image/png` 落盘且下载链接可用。
- 调整方案与批处理（2026-09-05）：调整图片工作区新增 `Lock adjustment`，开启后更换或拖入
  新图会沿用当前裁剪、变换和 16 项调色参数；选择已保存方案也会自动保持参数。支持命名保存、
  更新、选择以及在管理对话框中改名/删除本机持久化方案。`Done and save` 同行新增批量处理，
  可从多个本地文件、一个本地目录或当前 Gallery 集合取图，并选择覆盖原图/原 Gallery 资产，
  或另存到用户选择的本地目录/当前 Gallery 集合；本地目录与文件路径只来自 AceFox 对当前认证
  Local origin 暴露的用户选择结果。批量渲染复用单图调整引擎，保留输入格式，目录另存保留相对
  层级；本地写入使用同目录临时文件、fsync 与原子替换，Gallery 覆盖保留原 Asset ID 和 Collection
  关系，覆盖前有不可撤销确认。调整方案、锁定和当前选择同时进入用户/AppInstance/Mini-App 范围
  的持久草稿，避免 App-Dev Local 端口变化时因 origin 更换而丢失。Imagine Studio 专项回归
  `9/9`、Ruff、Python/JavaScript 语法与 `git diff --check` 通过；标准 builder 两次刷新固定开发 App，
  最终旧 App 归档为 `AI2Apps-app-dev-20260905-005151.app`。端口 `56219` 实机保存“跨端口持久方案”
  并启用锁定，Local 重启到 `56441` 后方案选择、名称和 Lock 状态均恢复；方案管理和批量处理对话框
  的三个来源、覆盖/另存以及目录选择入口均完成实机 UI 验收。批量本地另存、覆盖与 Gallery 原位
  替换由 API 自动化覆盖，测试使用临时文件，不改动用户原图或 Gallery 资产。最终图片签名、MIME
  与扩展名校验加固加载后，固定 App-Dev 再次重启至端口 `56747` 并保持正常连接。
- 模型裁剪预设（2026-09-05）：调整图片的 Crop 下拉补充当前 OpenAI 与 Google 图片模型尺寸。
  方形显示共享的 `1024×1024`，OpenAI 横竖图显示 `1536×1024 / 1024×1536`，Google 横竖图
  使用生产实际返回的 `1264×848 / 848×1264`。裁剪引擎按各尺寸的精确宽高比执行中心裁剪，
  Google 不以近似 `3:2 / 2:3` 代替实际比例；输出仍保留裁剪后源图分辨率，不做无意放大。
- 更换图片风格 Mini-App（2026-09-05）：新增内置 `ai2apps.imagine.style-transfer`，接收一张原图、
  一个必选的 Image 核心风格和可选补充说明，通过标准图片编辑 API 生成风格转换结果。工作流提示词
  明确保留主体身份、姿态、构图、几何与关键内容，只重绘材质、光线、色彩和纹理；输入图比例继续
  匹配模型支持的最近输出尺寸。该 Mini-App 将具备图片编辑能力的 OpenAI 模型排在首位，新草稿
  默认选择 OpenAI；用户手动选择并保存过其他模型时尊重其草稿，不强制覆盖。未选择目标风格时
  禁止提交，补充说明允许为空；Run、Artifact、重试、下载及加入 Gallery 复用现有持久工作区。
  Imagine Studio 专项回归 `9/9`、Ruff、JavaScript 语法与 `git diff --check` 通过。因运行中的旧
  App-Dev Development Bundle 未提供源码热挂载，按标准 builder 刷新固定开发 App，旧 App 归档为
  `AI2Apps-app-dev-20260905-011632.app`；清理构建前遗留 Local 后，新固定 App 在端口 `60070`
  启动。实机确认 Mini-App 数由 7 增至 8，入口、单图必选、目标风格必选、可选补充说明、
  OpenAI GPT Image 2 默认选择及禁用提交状态均正常；验收未上传图片或触发付费生成。
- 合影 Mini-App（2026-09-05）：新增内置 `ai2apps.imagine.group-photo`，在 Cloud 单次最多四张图片
  的现有合同内提供 3 个人物 Slot 和 1 个可选背景图 Slot，并支持用背景文字替代背景图。生成区增加
  独立的背景描述、气氛、姿势与互动字段，以及复用 Image 核心风格选择器的可选视觉风格；至少需要
  两张人物图，且背景图/背景描述必须有一项。合成提示词明确输入角色顺序、每个人只出现一次、保持
  人物身份与面部特征、禁止合并/复制/遗漏/新增人物，并要求统一光线、比例、透视、阴影、视线和
  人体结构。该 Mini-App 与更换风格一样优先排列 OpenAI 图片编辑模型，新草稿默认选择 OpenAI，
  手动保存过的模型仍由草稿恢复。人物、背景及结构化描述会随 Mini-App 草稿和 Run 输入持久化，
  Gallery 背景素材使用稀疏 Slot 保存，刷新后不会被错误恢复为人物图。Imagine Studio 专项回归
  `9/9`、Ruff、JavaScript 语法与 `git diff --check` 通过；标准 builder 刷新固定开发 App，旧 App
  归档为 `AI2Apps-app-dev-20260905-055523.app`。新固定 App 在端口 `64136` 启动，实机确认 Mini-App
  总数增至 9、四个语义化 Slot、三项结构化输入、OpenAI GPT Image 2 默认选择和提交禁用状态正常；
  验收未选择用户图片或触发 Cloud 付费生成。
- Gallery Mini-Entry 恢复修正（2026-09-04）：实机确认 Gallery API 与 Mini-Entry 页面正常，
  失败来自外层 Shell 强制刷新前遗留的旧 mount token，导致 Imagine Studio 的 Host Bridge 请求
  30 秒无响应；强制刷新后标准 Mini-Entry mount 成功并创建 `app_mounts` 记录。Imagine Studio
  现在会在恢复到 Assets 视图时主动挂载 Gallery，并在 Host Bridge 无响应或宿主不支持挂载时降级
  到同源第一方 Gallery Mini-Entry，避免显示永久失败卡片；用户手动重试会先清理旧 URL 与 mount ID。
  Imagine Studio 与 Gallery 联合回归 `15/15`、JavaScript 语法、Ruff 和 `git diff --check` 均通过；
  端口 `61299` 实机强制刷新后保持 Assets 视图，并自动恢复 Gallery Mini-Entry，无需再次切换 Tab。
- Studio 横向修正（2026-09-04）：检查所有 Gallery Mini-Entry 消费方后，确认 Video Studio 与
  Read Aloud 仍有相同的 Host Bridge 超时失败路径；两者现与 Imagine Studio 一致，在恢复到
  Assets 视图时主动挂载，在 Host 无响应或不支持挂载时降级到同源第一方 Gallery Mini-Entry，
  并在 Retry 前清理旧 URL 与 mount ID。仓库内三个 Studio 的 Gallery 挂载恢复策略现已统一。
  三个 Studio 专项回归 `20/20`、三份 JavaScript 语法检查、Ruff 与 `git diff --check` 通过；
  端口 `61299` 实机确认 Read Aloud 与 Video Studio 均可挂载 Gallery，Video Studio 在保持
  Assets 视图强制刷新后也会自动恢复 Mini-Entry。
- AceFox Sidebar Gallery 修正（2026-09-04）：实机确认 AceFox Sidebar 直接加载的 Gallery
  Mini-Entry 正常显示并绑定当前 `bidi_context`，不经过 Web Shell `mountMiniEntry`，因此不会复现
  Studio 的 Host Bridge 超时；但其“打开完整 Gallery”和素材预览错误依赖不存在的 Web Shell
  bridge，前者点击无反应、后者会显示不支持预览。Gallery 现会在 Browser Sidebar 环境使用同源
  新标签页打开完整 Gallery 或指定素材预览，同时保留 Desktop Shell 原有 bridge 行为。AceFox
  实机切换回 Gallery 重新加载脚本后，“打开完整 Gallery”已成功新建标签页并加载完整页面；Gallery、
  Imagine Studio、Read Aloud 与 Video Studio 联合回归 `28/28` 通过，JavaScript 语法、Ruff 与
  `git diff --check` 通过。
  Sidebar 当前仍未创建平台 `app_mounts`，后续需按浏览器控制架构将其升级为 mount-bound Gateway
  session；本次没有放宽 BiDi、Profile、Context 或身份校验。
- Gallery Shell-App 图标更新（2026-09-09）：以最终选定的 B3 概念替换原
  `gallery-horizontal-end` 图标，使用等高横向三图叠层、左侧前景图、放大太阳和较细的太阳/山形
  内部线条。自定义图标通过共享 Lucide 注册表接入，Shell Dock、App Launcher、Gallery 完整页面
  与 Mini-Entry 使用同一 `gallery-stacked-horizontal` 标识，不改变其它系统 App 图标。Gallery 与
  Shell 合同回归 `121/121` 通过，JavaScript 语法、Ruff 与 `git diff --check` 通过；固定 App-Dev
  的 Local 已通过受认证 Helper 控制通道从端口 `57781` 重启至 `50476`，实机确认 Shell Dock
  已渲染 B3 图标且 Gallery 可正常打开。后续用户截图证明首次验收误把空图标容器识别为图形：
  Lucide 内置注册表实际被冻结，旧缓存中的首版注册脚本未能注册 B3，因而呈现为空色块。图标现由
  独立 `window.ai2appsIcons` 注册表和共享渲染器处理，并提升静态脚本版本参数以强制淘汰旧缓存；
  修复完成前不得沿用首次实机验收结论。最终在端口 `51358` 的固定 App-Dev 中强制刷新复验，确认
  Shell Dock 的普通态/选中态以及 Gallery 完整页面页头均实际显示 B3 的三张横向叠图、太阳与山形
  线稿，不再是空色块；修复后 Gallery 与 Shell 合同回归 `122/122` 通过。
- Release notes 建议：Imagine Studio 现在以 Mini-App 组织图像创作，并将每次生成保存为可恢复、
  可重试、可下载及可加入 Gallery 的标准 Run 和 Artifact；同时改进素材边界、发现能力和窄屏体验。
- 纳入 Build：待定。

### NXR-015：oMLX Runtime 1.6.0 Detailed Transcription 能力合同

- 状态：`ready`
- 类型：Runtime Package、高级语音转写基础设施。
- 用户可见结果：oMLX Runtime 新增独立的
  `audio-detailed-transcription-v1` capability，为字幕、会议转写的 Qwen3 ASR、
  forced alignment、VAD 和说话人分离流水线提供 Runtime 版本边界。
  该能力不加入 Chat STT 选型，原有 `audio-stt` 合同保持不变。
- 版本与依赖：Runtime 从 `1.5.7` 升至 `1.6.0`；MLX Detailed
  Transcription 候选 Package 的 Runtime 下限同步收紧为 `>=1.6.0,<2.0.0`。
- 体积精简：Runtime 只内嵌 `ai2apps/model_worker` 而不再复制整个 Host
  源码树；移除 Python tests/cache、xgrammar 仅供链接的静态库，以及归 Host
  所有的 ModelScope、Selenium 和 MCP 客户端。MLX、MLX-LM/VLM、MLX Audio、
  sherpa-onnx、通用 ONNX Runtime、PyAV 和 xgrammar 运行时动态库全部保留。
- 发布边界：Host 的 dedicated model type/route 已随 Runtime 候选完成；三个新
  checkpoint distribution 仍为后续门禁。Runtime 1.6.0 已生成 Developer ID
  签名、Apple 公证及 Publisher 签名候选，但当前工作树非 clean，本轮未提交
  Registry，不将本地签名候选冒充已发布 Runtime。
- 需要进入 Runtime/Package 的文件：
  - `packages/ai2apps-runtime-omlx/service.yaml`
  - `packages/ai2apps-runtime-omlx/ai2apps.json`
  - `packages/ai2apps-runtime-omlx/META/runtime-manifest.json`
  - `packages/ai2apps-runtime-omlx/META/sbom.spdx.json`
  - `experiments/mlx_whisperx/package_candidate/service.yaml`
  - `experiments/mlx_whisperx/package_candidate/ai2apps.json`
- 验证（2026-09-04）：Runtime/Package/Model Worker 合同与 MLX Detailed
  Transcription 候选测试 `109/109` 通过，`git diff --check` 通过。标准
  Runtime 构建器已生成精简后的
  `ai2apps-runtime-omlx-1.6.0-development.ai2service`，大小 `361,983,771`
  字节，完整 SHA-256 为
  `fed092398e6e5c502a8ed4bccb74b696b4d187504163e774687e11aa9bd429b0`，
  Package digest 为
  `sha256:64b0a6522caedf21fe5eeede73ee66ca40d61b87bf69335abd64abf523071c11`。
  相比精简前同版本开发件的 `436,977,802` 字节，减少 `75,581,675`
  字节（`17.3%`）。
  归档反向解析确认 service/descriptor/SBOM 版本一致为 `1.6.0`、新 capability
  存在、DMG 固定路径正确；实际挂载 DMG 后的 Bundle 与外层 DMG 均通过
  `codesign --verify --deep --strict`，Bundle Info.plist 版本为 `1.6.0`，并确认已内嵌
  Qwen3-ASR `max_tokens=None` 修复和独立
  `/v1/audio/transcriptions/detailed` Worker 路由。从签名 Bundle 内实际导入
  MLX、MLX-LM/VLM、MLX Audio、STT/TTS Engine、sherpa-onnx、ONNX Runtime、
  PyAV 和 xgrammar 全部通过，并确认 Host-only 模块不存在。
  同日正式候选 DMG 已完成 Developer ID 签名与 Apple 公证，submission
  `938e8163-7319-4bd9-b5ce-abfdeba34216` 为 `Accepted`，staple 与 Gatekeeper
  验收通过；最终 DMG 大小 `384,756,624` 字节，SHA-256 为
  `1ae8c38aab38c98f68c6d7eb9c2167bebcb6ecaedce94a812a48808547bc5505`。
  公证件内 Python 为 `3.11.10`，全盘无 cp313/Python 3.13 路径，四个 oMLX
  自定义扩展均为 cp311 且 ABI probe/Direct-L1 symbol 通过。外层正式候选
  `ai2apps-runtime-omlx-1.6.0-production.ai2service` 已由现有正式 Publisher key
  签名，大小 `382,501,589` 字节，SHA-256 为
  `ce4f946b4f3a9f90f5e68e07d1d8a965e4ba1634a89fe895dfd6ca2a9c03a9a5`；离线
  envelope 验证和包内 DMG 等值校验通过。完整收据见
  `docs/ai2apps-mlx-runtime-1.6.0-detailed-transcription-signed-build.md`。
  Runtime 随后以 submission `cb038b5f-2cac-4bda-93ad-f90eaa42f5d3` 完成审核和
  Registry 发布；GitHub 与 ModelScope 相同字节镜像均通过 Cloud 的完整 SHA、Range
  和 46-piece 校验并激活。最终签名 Repository Snapshot v107 同时包含 Cloud、
  ModelScope、GitHub 三源；匿名真实客户端完成多源竞速下载，ModelScope 与 Cloud
  均实际赢得分片，组装后的完整摘要和 Publisher 签名验证通过。发布回执见
  `docs/ai2apps-mlx-runtime-1.6.0-detailed-transcription-release.md`。
- Release notes 建议：oMLX Runtime 新增独立的高级语音转写能力基础，
  用于字幕和会议转写，不影响 Chat 现有语音输入。
- 纳入 Build：待定。

### NXR-016：MLX WhisperX Detailed Transcription Package

- 状态：`ready`
- 类型：Model Package、Host 模型合同。
- 用户可见结果：新增独立字幕/会议转写模型类型，组合 Qwen3-ASR、Qwen3
  ForcedAligner、MeetingEnergyVAD 与 Sortformer，输出逐词/逐字时间戳、匿名说话人、
  语速及明确的高级能力 provenance；不会出现在 Chat STT 选项中。
- Package：正式源码位于 `packages/omlx-model-detailed-transcription/`，Package ID
  `ai2apps/model-detailed-transcription-mlx`；0.1.1 已发布，当前沙箱兼容修正版为
  `0.1.2`，依赖已发布的
  `ai2apps/runtime-omlx >=1.6.0,<2.0.0`，不内嵌任何 checkpoint。
- Checkpoint：0.6B/1.7B ASR、ForcedAligner、Sortformer 均使用匹配本 Package model
  identity 的 distribution，并已完成 HF/ModelScope 字节一致的 Publisher 签名构建、
  Cloud 发布与匿名回读。Sortformer 使用 NVIDIA Open Model License 的条件式下载同意与署名合同。
- Host：新增 `audio_detailed_transcription` 模型类型、默认 endpoint 与音频能力验证；
  ForcedAligner/Sortformer 以隐藏的 `audio_processing` 内部模型声明，避免暴露为用户可选
  Chat 模型。Cloud 当前仍拒绝新的签名 Discover 字段，因此 0.1.2 使用版本上限明确的
  Desktop legacy mapping；Cloud 升级需求已记录在
  `docs/cloud-discover-model-categories-requirements.md`。
- 验证：流水线、Package 合同、Model Worker 路由、现有音频 Package、Discover mapping
  与发布脚本的 0.1.2 联合回归 `136/136` 通过；无权重 Contract v1 测试构建通过。首次生产提交
  `7e1b05e1-6c8c-4e8f-b613-57054e978af6` 已验签和批准，但发布门禁正确拒绝 compact
  模型复用另一个 model identity 的 0.6B distribution；该不可变提交不能发布，需为
  detailed-transcription compact identity 新建同权重 distribution 后替换提交；该新增
  distribution 已发布并通过公共索引 v46 匿名验证。0.1.1 随后以 submission
  `ce41c54f-7672-4d64-a4ef-495377e2932d` 发布，公共 Registry 与完整 artifact 下载摘要
  验证通过；真实 Runtime/Package 安装成功，但首次推理确认 Package 对上传路径调用
  `Path.resolve()` 会在 macOS 沙箱中因 `/tmp` → `/private/tmp` 返回 500。0.1.2 已移除
  canonicalization、补充 multipart 布尔字符串解析，并让 smoke 显式关闭 diarization，
  随后使用正确的注册 Publisher 私钥完成 0.1.2 签名；正式发布 submission 为
  `ab93f656-e5e9-4360-bdc5-a11d2ccce717`，Repository Snapshot 为 v109。匿名目录确认
  latest=0.1.2、installable=true、无 blocker，完整下载 SHA/大小与本地发布件一致，
  envelope 逐 JSON 相同。直接使用公共下载 artifact 再次完成 Runtime 1.6.0 中英文
  managed-service 推理：英文 9/9 对齐且文本完整正确；中文 18/19 对齐，ASR 遗漏参考
  文本中的“我”一字。完整回执见
  `docs/ai2apps-mlx-whisperx-detailed-transcription-0.1.2-release.md`。
- 纳入 Build：待定。

### NXR-017：跨 Distribution 复用相同 Checkpoint 文件

- 状态：`ready`
- 类型：Desktop/Local Checkpoint 安装与缓存基础设施。
- 用户可见结果：不同 Package 或模型 identity 的 checkpoint distribution 只要声明了
  相同文件 SHA-256，AI2Apps 会从共享内容寻址 blob 缓存复用已验证文件；全部命中时不再
  请求 Hugging Face/ModelScope，部分命中时只下载缺失文件或跨文件 piece 的必要片段。
- 安全边界：每次 acquisition 仍先完成签名 manifest、许可证同意和 distribution identity
  校验；复用前重新校验 blob 类型、大小与完整 SHA-256。新 distribution 仍生成独立、只读的
  metadata/snapshot 视图，文件内容通过硬链接共享，不合并或绕过 Registry identity。
- 需要进入 App 的文件：
  - `ai2apps/checkpoint_acquisition.py`
  - `ai2apps/checkpoint_distribution.py`
- 自动化验证：Checkpoint acquisition/distribution、Registry、发布策略、安装器与共享缓存
  联合回归 `91/91` 通过；Ruff 与 `git diff --check` 通过。新增用例覆盖跨 distribution
  全量命中零网络，以及部分文件命中时只请求缺失文件。
- 真实验证（2026-09-04）：在全新隔离缓存中先导入普通 Qwen3-ASR 0.6B distribution
  `dist_ai2apps_qwen3_asr_0_6b_4bit_313d8501_v1`，随后请求 Detailed Transcription 的
  `dist_ai2apps_detailed_transcription_qwen3_asr_0_6b_4bit_313d8501_v1`；第二次 acquisition
  返回 `cache_hit=true`、`source_bytes={}`、checkpoint 源请求 `0`，9 个文件共
  `712,778,752` 字节全部复用，两个只读 snapshot 的文件 inode 完全一致。
- 发行边界：这是 AI2Apps Desktop/Local 代码变更；不需要升级 oMLX Runtime、模型 Package
  或重新发布既有 checkpoint distribution。
- Release notes 建议：已安装模型的相同 checkpoint 文件现在可以跨 Package 安全复用，
  减少重复网络下载和磁盘占用。
- 纳入 Build：待定。

## 4. 发布流程工作

### NXR-021：纯 MLX Seed-VC v2 零样本音色转换

- 状态：`ready`（Runtime 1.6.2、模型 Package 与 HF/MS 双源 checkpoint 均已发布并匿名验收）
- 类型：oMLX Runtime 音频 API、Model Package、Apple Silicon 零样本音色转换。
- 用户可见结果：`POST /v1/audio/process` 新增请求作用域 `reference` 音频以及
  `mode/diffusion_steps/guidance_intelligibility/guidance_similarity/length_adjust` 控制；
  Seed-VC v2 的 timbre 与 AR voice 两条路径均已用纯 MLX 跑通，不需要预训练用户音色。
- 安全边界：Torch 仅用于可信离线权重转换；Model Worker 只读取 Host 分配的 safetensors，
  参考音频只属于当前请求，不能注入 checkpoint 路径，也不会自动持久化为 Voice Profile。
- 需要进入 App/Runtime 的文件：`ai2apps/model_worker/audio_capabilities.py`、
  `omlx/api/audio_routes.py`。
- Model Package：`packages/omlx-model-seed-vc-v2/`；实验与验证：
  `experiments/mlx_seed_vc/`、`docs/ai2apps-mlx-audio-model-package-development-plan.md`。
- 当前验证：HuBERT、ASTRAL、AR、双 CFG CFM DiT、CAMPPlus、BigVGAN 均完成官方权重
  数值对照；Qwen3-ASR 恢复完整中英文原句。M5 Max 上 10 步英文/中文 RTF 分别为
  `0.1607`/`0.1476`，峰值 MLX 内存约 `4.54`/`5.23 GB`；签名 Runtime 1.6.0 自带
  Python 3.11 的 Package-layout 冒烟 RTF `0.3484`、峰值 `3.345 GB`，确认无需新增底层
  Python/MLX 依赖。Runtime 1.6.1 已加入 request-scoped reference multipart、双 CFG 参数
  路由和显式 `audio-reference-input-v1` 能力声明；Package/能力声明/API 联合回归
  `50/50` 通过。同一 11.04 秒 Ryan→Serena 任务的听感与 RMVPE 复核确认，Seed-VC v2
  音色相似度优于当前 RVC 候选，但逐帧相对基频变化的 MAD 为 `14.98 cents`（10 步）和
  `14.42 cents`（30 步），高于 RVC 70/80 轮的 `8.22/9.00 cents`；关闭 cosine sway
  后仍为 `14.54 cents`。固定上游提交与原始 checkpoint 的官方 Torch/CPU 同任务 30 步
  对照为 `15.49 cents`，MLX 并未放大中位基频抖动；Torch 的 90 分位逐帧误差较低
  （`58.82` 对 `73.60 cents`），仍需扩大样本验证少数突变帧。该任务 Torch RTF
  `2.0588`，MLX RTF `0.1878`，MLX 约快 11 倍。因此当前颤音主要是无显式 F0 条件的
  checkpoint/生成路径边界，不是简单增加扩散步数、关闭 sway 或 MLX 数值精度可以消除，
  后续应评估显式 F0 稳定化方案。
- 发布结果（2026-09-05）：`ai2apps/model-seed-vc-v2-mlx 0.1.0` 已正式发布，artifact
  SHA-256 为 `070db748df6e4aa395120a2a5f3391eb2476e44f8f7e959af14246474af513d2`；完整
  checkpoint distribution `dist_ai2apps_mlx_seed_vc_v2_2122cee1_v1` 已固定到 HF
  `2122cee1…` 与 MS `f1c5ab39…`，16 个文件、267 个分片、`2,236,581,603` 字节。
  匿名客户端验证 checkpoint index v51、Repository snapshot v117、Publisher 签名、artifact
  SHA-256 及本地/公开 envelope 完全一致；全新隔离 Platform base 中与 Runtime 1.6.2 一同
  安装后服务为 `active`。完整回执：
  `docs/ai2apps-mlx-seed-vc-v2-0.1.0-release.md`。
- Package 收敛（2026-09-05）：已生成可复现的最终复合 checkpoint 上传布局，15 个文件共
  `2,236,581,275` 字节，布局清单 SHA-256 为
  `cefd682aa86b79fe7388eb2b825d94d82a037b1a3f9fdef1ae82b1b76e572c4a`；模型卡、GPL-3.0
  许可证、第三方 NOTICE、SPDX SBOM 与 source lock 已加入 Package 源。Worker 默认档由
  10 步改为已完成 Torch/MLX 对照的 30 步，保留 10 步 fast 与 30 步 AR voice 档，并增加
  guidance/length-adjust 范围校验。最终目录的 30 步 multipart Worker 冒烟已在 Metal 上通过。
  同时修复了异步 Worker 在线程池缺少 MLX CPU/GPU stream 的真实崩溃：模型现在线程内加载，
  并使用 thread-local 双设备 stream。最终发布增加根 `config.json` 以满足通用 Host checkpoint
  完整性检查；Package 绑定上述已发布不可变双源 distribution，不内嵌权重。
- Release notes 建议：新增在 Apple Silicon 上离线运行的 Seed-VC v2 零样本音色转换，支持
  请求内参考音频、快速 timbre 与 AR voice 两种模式及独立语义/音色引导。
- 纳入 Build：待定。

### NXR-022：oMLX Runtime 1.6.2 原生音色训练协议

- 状态：`ready`（Runtime 1.6.2 已完成签名、公证、发布和三源匿名验收）
- 类型：oMLX Runtime、Model Worker 协议、Apple Silicon 本地音色训练。
- 用户可见结果：Host 新增 `POST /v1/audio/voices/train`，Runtime Worker 新增有界、可取消的
  `audio_voice_training` operation，并通过 `audio-voice-training-v1` 显式声明支持；模型
  Package 可以在安装前要求该协议，不会把 1.6.1 的推理 Runtime 误判成可训练环境。
- 安全边界：训练输入为一个受大小限制的 multipart ZIP；具体模型 Adapter 继续负责成员类型、
  数量和解压大小校验。Worker 不接受任意 checkpoint 路径，进度、取消和结果均沿用既有协议。
- 数值合同：RVC 默认训练精度统一为 FP16，使用 FP32 Adam 主权重和动量；BF16/FP32 保留为
  显式选项。
- 需要进入 Runtime/Package 的文件：`omlx/api/audio_routes.py`、
  `ai2apps/model_worker/server.py`、`packages/ai2apps-runtime-omlx/`，以及 RVC Package 的训练
  Adapter 与 CLI 默认值。
- 当前验证：Runtime/Model Worker/Provider/资源与构建器联合回归 `71/71` 通过；Metal 环境下
  audio route/STT 回归 `37/37` 通过（4 项按选择器排除）。
- 发布结果：Runtime 1.6.2 已完成 Developer ID 签名、Apple 公证、Publisher 签名和 Registry
  发布；GitHub/ModelScope 双外部源均通过完整 SHA-256、Range 和 45-piece Cloud 预检并激活。
  匿名生产下载器验证 Snapshot v115、完整 Package 和 Publisher 签名通过。发布回执：
  `docs/ai2apps-mlx-runtime-1.6.2-voice-training-release.md`。完整 RVC 与 Seed-VC v2 Package
  已于同日完成发布和匿名验收。
- 纳入 Build：待定。

### NXR-020：MLX-RVC 音色转换与通用参数转发

- 状态：`ready`（Runtime 1.6.2、完整训练/推理 Package 与 HF/MS 双源 checkpoint 均已发布）
- 类型：oMLX Runtime 音频 API、Model Package、Apple Silicon 本地音色转换。
- 用户可见结果：`POST /v1/audio/process` 可向签名音频处理 Package 转发
  `task/profile/semitones/retrieval_rate/protect/speaker_id/seed`；MLX-RVC 已跑通
  ContentVec、RMVPE、检索、特征保护、Flow 与 NSF 解码器的纯 MLX 音频到音频路径。
- 安全边界：生产推理不加载 pickle、Torch、torchaudio 或 FAISS；旧 `.pth`/`.index` 只在
  可信离线构建环境转换为带哈希的 safetensors。Worker 只读 Host 分配的固定 checkpoint，
  请求不能注入本地模型路径。
- 需要进入 Runtime 的文件：`omlx/api/audio_routes.py`。
- 实验与设计文件：`experiments/mlx_rvc/`、
  `docs/ai2apps-mlx-audio-model-package-development-plan.md`。
- 当前验证：官方模型逐模块数值对照通过；最终 RVC v2/48 kHz checkpoint 与 3399×768
  检索库已完成安全转换并跑通中英文。M5 Max 128 GiB 上 60 秒分块 RTF `0.0357`、MLX
  峰值约 6.20 GB，相比整段约 18.42 GB 降低约 66.3%。Package、Sandbox 与听感/说话人
  相似度验收尚未完成。新增 Qwen3-TTS CustomVoice `serena` 合成测试音色：48 条中文、
  24 条英文，共 370.8 秒；在固定 RVC 上游修订上使用 MPS 完成 v2/48 kHz/RMVPE 100 轮
  训练并构建 12954×768 检索库。独立 `ryan` 合成源经纯 MLX 转换的 11.04 秒冒烟 RTF
  `0.0990`，输出 11.02 秒、无非有限值或削波；Qwen3-ASR 回听保持整句结构，仅有两处
  近义词替换。该资产明确标注为 synthetic test voice，尚未发布 checkpoint 或 Package。
  现已新增 Package-owned 原生 MLX 训练链：原始 WAV 的 ContentVec/RMVPE/频谱缓存、Posterior
  Encoder、正向 Flow、NSF Generator、RVC v2 九路判别器、BF16 优化、进度/取消以及直接输出
  safetensors Voice Bundle。370.8 秒 Serena 数据完成 100 轮、1800 次 G/D 更新耗时
  `667.57s`，约为 Torch/MPS 的三分之一；全网络训练未通过 ASR 内容门禁，已明确拒绝作为
  交付候选。默认 `safe` 模式冻结 `enc_p` 与 Flow，10 轮/180 步耗时 `58.02s`，独立中文
  回听保留完整句式，仅有两处近音替换。检索改用矩阵式精确 L2 后，36936 向量推理峰值从
  64.9 GB 降至 5.85 GB，RTF 从 `0.205` 降至 `0.0448`。新增
  `audio_voice_training` Worker operation 和 `/v1/audio/voices/train` 路由；因此训练功能需要
  下一版 Runtime 协议，1.6.1 仍只提供推理。
  最终标准档采用 30 轮 safe adaptation：540 次 G/D 更新耗时 `184.70s`，独立 Qwen3-ASR
  回听仅有“语义→语音”一处近音替换；保留全部 36936 个检索向量时推理 RTF `0.0436`、
  峰值 5.85 GB。听感复核发现该候选较 Torch 对照低约 10.4 dB，并有更明显颤音，因此已撤销
  质量候选资格。根因修复现已补回固定上游的 48 Hz 高通、3.7 秒重叠切片、混合峰值归一化和
  `128-bin log-mel L1 × 45` 重建损失；旧实现使用未归一化原始音频及非等价多分辨率频谱损失。
  直接全 FP16 训练首轮产生 NaN；改为 FP16 前后向、FP32 Adam 主权重/动量并增加非有限值
  快速失败后，10 轮/360 步稳定完成，耗时 `136.24s`。同句输出 RMS 从 `-31.19 dBFS`
  恢复到 `-24.00 dBFS`，峰值 `-5.79 dBFS` 与 Torch 的 `-5.78 dBFS` 基本一致，纯 MLX
  推理 RTF `0.0428`。随后完成确定性 30 轮/1080 步训练，用时 `418.38s`；同句输出 RMS
  `-22.95 dBFS`、峰值 `-5.70 dBFS`、RTF `0.0418`，音高误差帧差 MAD 为 `8.43 cents`
  （旧 MLX 为 `12.34`，Torch 对照为 `9.12`）。10/20/30 轮试听均已保留；该修复候选仍需
  用户听感和内容回听验收。训练器现已增加滚动完整断点：保存 G/D、FP32 主权重、两个 Adam
  状态、epoch/step 与固定配置；单片段 1→2 轮恢复与连续 2 轮的 353 个导出张量逐项完全一致。
  可恢复 60 轮轨迹完成 2160 步，用时 `858.65s`，并保留 30/40/50/60 轮试听；60 轮同句
  RMS `-23.17 dBFS`、峰值 `-2.53 dBFS`、音高误差帧差 MAD `8.40 cents`。后续 100 轮可从
  60 轮状态仅续训 40 轮。尚待 Package 清单、沙箱端到端与签名发布。
  已实际从 60 轮完整状态恢复并续训到 100 轮/3600 步，新增 40 轮用时 `577.47s`，与前段
  合计 `1436.12s`。100 轮同句 RMS `-24.27 dBFS`、峰值 `-7.93 dBFS`、RTF `0.0417`；
  音高误差帧差 MAD 从 60 轮 `8.40`、70 轮 `8.22` 上升至 100 轮 `10.56 cents`，因此不按
  epoch 自动认定最终最优，保留 60/70/80/90/100 供听感、ASR 内容和说话人相似度联合选型。
- Release notes 建议：本地音频处理 API 新增模型无关的音色转换控制参数，为 MLX-RVC 与
  后续 MLX-Seed-VC Package 提供统一入口。
- Package 收敛（2026-09-05）：首版推理 Package 选定用户听感更自然的 native MLX e70
  Serena 合成测试音色，并把 voice、ContentVec、RMVPE 合并为一个原子 checkpoint；最终
  上传布局 14 个文件共 `974,917,451` 字节，布局清单 SHA-256 为
  `fab82f57d0fa9378774aa29e5153c38205a517818fe5bafcd711ef90e93b510d`。模型卡明确 synthetic
  voice 边界，MIT 许可证、NOTICE、SPDX SBOM、source lock 和可复现 staging 脚本已加入。
  最终目录的 `audio_process` Worker 冒烟已在 Metal 上通过，并与 Seed-VC 一同修复线程池
  MLX stream 崩溃。最终原子 checkpoint 又加入 MLX 训练 G/D 初始化、根配置及通用 Host
  safetensors 标记，共 19 个文件、169 个分片、`1,410,906,582` 字节；双源 distribution
  `dist_ai2apps_mlx_rvc_serena_e70_training_738acad9_v1` 固定到 HF `738acad9…` 与 MS
  `643998a0…`。`ai2apps/model-rvc-mlx 0.1.0` 已正式发布，artifact SHA-256 为
  `fd000d66f963ba40034ac6330ac83ea9d639b3814843b001050de52c8813e3ed`；匿名 checkpoint
  index v51 与 Repository snapshot v117 验证通过，全新隔离 Platform base 中精确发布 digest
  与 Runtime 1.6.2 一同安装后为 `active`。完整回执：
  `docs/ai2apps-mlx-rvc-0.1.0-release.md`。
- 纳入 Build：待定。

### NXR-023：模型 Package discovery 的 Cloud v1 兼容桥接

- 状态：`ready`（0.1.0 兼容桥接已验证；Cloud schema 升级需求已落盘）
- 类型：Desktop/Local Package 发现兼容、Cloud 合同对齐。
- 背景：本地 Package Contract v1 已要求新模型 Package 签名携带顶层 `discovery` 与
  `modelProfile`，但生产 Cloud 当前 schema 将这两个字段判为 additional properties。首次 RVC
  提交在创建 submission 前被拒绝，因此未产生重复或悬挂发布。
- 兼容处理：RVC 与 Seed-VC v2 的 `0.1.0` 使用现有的显式、版本上限 legacy map，分别声明
  `voice-conversion/voice-training` 与 `voice-conversion/voice-cloning`；下一版本不会自动沿用。
  `tests/test_ai2apps_discover_categories.py` 与音频/Package/Checkpoint 联合回归共 `89/89`
  通过，两个 Cloud v1 兼容 artifact 随后成功发布并完成匿名验证。
- Cloud 边界：未从本仓库修改 Cloud 代码。所需 schema、存储、公开投影和验收用例已写入
  `docs/ai2apps-cloud-package-discovery-schema-requirements.md`，交由 Cloud 项目升级；升级后新版本
  应恢复由签名 manifest 直接携带元数据。
- 需要进入 App 的文件：`ai2apps/packages/discovery.py`。
- 纳入 Build：待定。

### NXR-019：通用音轨分离能力声明合同

- 状态：`ready`
- 类型：Model Package 合同、音频能力发现、未来 Video/Meeting Pipeline 基础设施。
- 用户可见结果：音频处理模型可以用签名 `audio_capabilities` 声明原生 stem 和稳定输出
  profile；调用方能够区分模型原生四声部、pipeline 派生的对白/背景双轨和未来更强模型的
  原生对白、音乐、音效、环境声输出，不再根据模型名称推测能力。
- 安全与兼容边界：继续使用 `audio_processing`/`audio_process`，不新增 Runtime operation；
  未声明 profile 默认拒绝。fallback 必须显式声明默认 profile，派生输出必须携带
  `derivation`，不能把 vocals 静默冒充原生 dialogue。
- 需要进入 App 的文件：
  - `ai2apps/model_worker/audio_capabilities.py`
  - `ai2apps/checkpoints.py`
  - `docs/model-worker-package-manual.md`
- 实验及设计文件：
  - `experiments/mlx_demucs/capabilities.py`
  - `experiments/mlx_demucs/pipeline.py`
  - `docs/ai2apps-mlx-audio-model-package-development-plan.md`
- 当前验证：能力声明、Model Provider 与 MLX-Demucs 实验联合测试 `50/50` 通过；Ruff、
  compileall 与 `git diff --check` 通过。中文夹具通过 `music_4stem` profile 实际生成四个
  等长 44.1 kHz 立体声 WAV，并返回 native/direct provenance。正式 Package 收敛过程中
  发现公开 `mlx-community/demucs-mlx` 使用 `htdemucs.safetensors` 与
  `htdemucs_config.json` 配对，而 Host 过去只承认根 `config.json/config.yaml`。完整性检查
  已增加严格的同 basename `*_config.json` 配对规则，任意不匹配配置仍 fail closed；对应
  回归和真实 checkpoint 验收已纳入发布门禁。`ai2apps/model-demucs-mlx` 0.1.0 及
  `dist_ai2apps_mlx_demucs_htdemucs_d4519e24_v1` 已正式发布；干净实例使用 Runtime 1.6.2
  和公开双源 distribution 完成 Managed Service Sandbox 推理，9 秒输入返回 HTTP 200
  及包含双轨 WAV/JSON 的 ZIP。Package 匿名回读通过 Repository snapshot v120。
- Release notes 建议：音频处理模型现在可以声明可发现、可校验的音轨分离拓扑，并明确
  区分模型原生输出与流水线派生输出。
- 纳入 Build：待定。

### NXR-018：Video Studio「提取音轨」Mini-App

- 状态：`ready`
- 类型：客户端功能、Video Studio、Mini-App、Gallery Resource Handle、Studio Run/Artifact。
- 用户可见结果：Video Studio 新增版本化内置 Mini-App `ai2apps.video.extract-audio 1.0.0`；
  用户可以从 Gallery 选择/拖入视频或直接导入本地视频，在设备上提取第一条音轨，获得可播放、
  下载及保存回 Gallery 的独立 WAV 文件。该流程不要求安装视频或语音模型，也不调用 Cloud。
- 执行与安全边界：Finder 拖入或系统文件选择器提供 `mozAI2AppsFullPath` 时，页面仅把已选择
  文件的路径交给同源 Local 服务，后端验证绝对路径、普通非空文件与 `video/*` 类型后由 PyAV
  直接流式读取，不再先把大视频装入 JavaScript Blob 或复制到 Gallery；没有原生路径的浏览器
  环境继续回退到 Gallery 导入。Gallery 输入仍使用绑定用户、Installation、AppInstance 和
  consumer App 的短期 Resource Handle。PyAV 将音轨本地解码为 48 kHz、16-bit、立体声 PCM
  WAV；结果写入 durable Workspace Artifact，Run、草稿和 Artifact 元数据均不持久化源绝对路径。
- 恢复与导出：Mini-App 输入草稿按 AppInstance 持久保存；Run 历史、进度、错误及 Artifact 由
  平台数据库恢复；失败/取消 Run 可重试，结果支持播放器、原生下载和 Gallery Artifact 导入。
- 需要进入 App 的文件：
  - `ai2apps/api/video_studio.py`
  - `ai2apps/video/audio_extraction.py`
  - `ai2apps/video/tasks.py`
  - `ai2apps/web/templates/system_apps/video_studio.html`
  - `ai2apps/web/static/js/video_studio.js`
  - `ai2apps/web/static/js/gallery.js`
  - `ai2apps/web/static/css/video_studio.css`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
- 发行测试：`tests/test_ai2apps_video_studio.py`、`tests/test_ai2apps_video_tasks.py`、
  `tests/test_ai2apps_gallery.py`。
- 当前验证（2026-09-04）：Video Studio、视频任务与 Gallery 联合回归 `26/26` 通过；Ruff、
  JavaScript 语法、中英文 Video Studio i18n `203` 键一致性和 `git diff --check` 通过。使用
  H.264 + AAC 的真实 MP4 冒烟输入成功生成 RIFF PCM、48 kHz、16-bit、立体声 WAV；固定
  `AI2Apps-app-dev.app` 重新启动 Development Source 环境后，最终 Local 端口 `58158` 健康、schema
  v70，OpenAPI 已公开 Mini-App、草稿、Run、取消和音轨执行路由；实机三栏 UI 显示四个已安装
  Mini-App，「Extract Audio」中栏输入、就绪状态和右侧 Audio Run 工作区布局均正常。
- 原生路径增量验证（2026-09-05）：联合回归仍为 `26/26` 通过；新增用例确认绝对本地路径可
  直接完成 WAV Artifact、相对路径被拒绝，且源绝对路径不进入 Run 或 Artifact 元数据；Ruff、
  JavaScript 语法与 `git diff --check` 通过。同步修正 Workspace Artifact 写入：Studio Run ID
  不再错误写入只引用 Agent Run 的 Workspace `artifacts.run_id` 外键，Studio 与结果的关联仍由
  `studio_artifacts` 保持。
- Release notes 建议：Video Studio 现在可以在本地从视频提取独立音轨，并将结果播放、下载或
  保存到 Gallery，无需配置生成模型。
- 纳入 Build：待定。

### NXR-024：Video Studio 多轨 Video Composer Mini-App

- 状态：`ready`
- 类型：客户端功能、Video Studio、Mini-App、本地媒体编辑、聊天控制。
- 用户可见结果：Video Studio 新增 `ai2apps.video.composer 0.2.0`；支持图片/视频/音频多轨、
  轨内多片段、片段移动与左右裁切、9 px 边界/播放头磁吸、分割、速度与音量调整、淡入淡出、
  轨道静音/锁定、画面叠层顺序、预览区直接移动/缩放图层、透明度、横竖画布、快速预览、
  撤销/重做、键盘快捷键、持久草稿、后台 Run、取消、MP4 下载及保存到 Gallery。
- 聊天编辑：可使用已安装对话模型把自然语言规划成最多 20 个白名单操作；发送给模型的上下文
  只包含画布、轨道、片段 ID 与编辑参数，不包含本地路径。模型结果在浏览器端执行严格字段、
  数值范围、目标 ID 与淡化时长校验，任一操作失败则整批回滚；无模型时支持常见的速度、音量、
  淡入淡出、分割、删除和画中画确定性指令。
- 执行与安全边界：原生文件选择/拖入优先使用实际本地路径，由同源 Local 立即登记成绑定
  actor、Installation 与 AppInstance 的不透明 Source ID；路径和文件指纹只保存在权限为 0600
  的私有后端记录中，草稿、Run、Artifact 和聊天上下文均不出现路径。普通浏览器回退为 Gallery
  导入与 Resource Handle。渲染完全使用 App Runtime 内嵌 PyAV、NumPy 与 Pillow，生成 H.264 +
  AAC MP4，不依赖系统或 Homebrew `ffmpeg` 可执行文件；音频按片段窗口解码，避免把长源文件
  整段载入内存。
- 需要进入 App 的文件：
  - `ai2apps/video/composer.py`
  - `ai2apps/api/video_studio.py`
  - `ai2apps/web/templates/system_apps/video_studio.html`
  - `ai2apps/web/static/js/video_studio.js`
  - `ai2apps/web/static/css/video_composer.css`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
- 发行测试：`tests/test_ai2apps_video_composer.py`，并与 Video Studio、Video Tasks、Gallery
  回归联合运行。
- 当前验证（2026-09-05）：H.264 + AAC 真实媒体源完成双视频轨叠层、速度、透明度、音视频
  淡化与混音渲染，输出同时包含可解码视频和音频流；Source ID 跨 AppInstance 不可读取，公共
  响应和 Run/Artifact 不泄露路径。Composer、Video Studio、Video Tasks 与 Gallery 联合测试
  `29/29` 通过；覆盖 Composer、Video Studio、Video Tasks、Runtime Video、Shell 与聊天路径的
  扩展回归 `150/150` 通过；Ruff、JavaScript 语法和 `git diff --check` 通过。固定
  `AI2Apps-app-dev.app` 已按标准流程重建并通过 release verification 与严格 codesign 校验；实机
  使用原生文件选择器导入 H.264 + AAC MP4，草稿可在 Local 重启后恢复，最终在端口 `51127`
  完成带视频和音频的 1 秒 MP4 Workspace/Studio Artifact，播放器加载至 100%，Run 显示
  `Completed`，并提供 `Download MP4` 与 `Add to Gallery`。实机同时发现并修正了 Studio Run ID
  误写 Workspace Agent Run 外键的问题，新增回归断言防止复发。
- 预览交互修复（2026-09-05）：拖动期间不再深拷贝项目并继续修改失效的 Clip 引用，而是持续
  更新当前项目中的同一 Clip，仅在指针结束时保存一次；位置拖动允许画面部分移出画布且始终
  保留 16 px 可见区域，因而全画布大小的 Clip 也能移动。补充 `pointercancel` 清理、禁用触摸
  默认手势，并把右下角缩放柄扩大至 18 px。Composer、Video Studio 与 Shell 联合回归
  `113/113` 通过；App Dev 端口 `52667` 实机拖动后坐标由 `(0,0)` 更新为 `(297,171)`，缩放后
  尺寸由 `640×479` 更新为 `478×358`，位置和大小均连续生效。
- 连续拖拽二次修复（2026-09-05）：确认响应式字段本身在首次移动后会使 Alpine 的
  `x-for` 预览层重构并取消当前 pointer stream。位置与缩放现在采用两阶段提交：手势期间仅更新
  稳定 DOM 图层的百分比样式并保持 Pointer Capture，松开或取消时才一次性写回 X/Y/W/H、刷新
  响应式项目并保存草稿，因此下方 Inspector 数值不会在拖动中触发页面重构。
- Composer 素材与时间线交互增强（2026-09-05）：图片可从文件或 Gallery 导入视频轨道，默认
  时长 1 秒并可从两端继续调整；预览图层双击恢复素材原始像素尺寸。工具栏和轨道表头提供明确的
  新增 Video/Audio Track 入口，Gallery 与本地文件可直接投放到指定轨道和时间点。时间刻度文本
  不再接收 Pointer Event 或被选中，刻度空白区支持按住横向拖动播放头。Clip 整体移动和左右裁切
  均以同轨片段边缘、播放头或零点为候选执行 12 px 磁吸，Snap 开关可即时禁用；磁吸时显示高亮
  反馈。时间线移动、裁切以及预览位置/大小调整全部采用手势期间 DOM 更新、结束时响应式提交，
  避免 Inspector 更新打断 pointer stream。图片真实渲染和 Composer/Video Studio/Gallery 联合
  回归 `18/18` 通过，Ruff、JavaScript 语法和目标文件 `git diff --check` 通过。固定 App Dev 已按
  标准流程重建并运行于端口 `59941`：实机确认新增 Video Track 后出现 `Video 3`；刻度拖动把
  播放头从 `0.02s` 连续更新到 `3.64s`；时间线 Clip 单次拖动从 `0.02s` 更新到 `1.82s`；预览
  图层单次拖动令 X/Y 从 `137/121` 更新到 `283/238`，双击后 W/H 从 `640×479` 恢复为素材原始
  `32×32`。自动化驱动器未能跨 Gallery iframe 生成可用的原生 HTML5 DataTransfer，因此指定
  轨道 Gallery 拖放以模板/脚本集成断言覆盖，图片登记、1 秒默认时长与 1.5 秒可调时长则由真实
  Pillow/PyAV 渲染测试覆盖。
- 跨轨移动（2026-09-05）：时间线 Clip 拖动升级为横纵二维手势；纵向经过同类型且未锁定的轨道
  时，目标轨即时高亮，Clip 以稳定 DOM `translateY` 跟随，横向时间磁吸改为使用目标轨的片段
  边界。松手后一次性提交 `start` 与 `trackId`；视频不能误入音频轨、音频不能误入视频轨，锁定轨
  也不会成为目标。Composer 与 Video Studio 回归 `10/10` 通过，JavaScript 语法、Ruff 和目标
  文件 diff 检查通过。固定 App Dev 刷新后实机把首个 Clip 从 `Video 1` 纵向拖到 `Video 2`，
  Inspector 的 Track 同步显示 `Video 2` 且 Start 磁吸为 `0`；随后使用 Undo 恢复测试前草稿。
- 时间线编排约束、群组与颜色（2026-09-05）：同轨 Clip 在前端所有入口和后端 Project 校验层
  均禁止时间重叠；向左移动遇到前一片段即停止，向右移动或延长时波纹推动后续冲突片段，首尾
  相连的连续片段会链式跟随，缩短时也会向左收拢。拖入已有时间位置、Inspector 数值编辑与聊天
  编辑同样执行约束。支持 Shift 连选相邻片段、Command/Ctrl 增减选择、组成/取消 Group；群组
  保持成员相对时间并作为整体在同轨或跨轨移动。Clip 支持颜色选择，新素材按区分度较高的调色板
  轮换默认色，群组在时间线上有连接标识。新增 Project 重叠拒绝、Group/颜色序列化与 UI 集成
  覆盖；Composer、Video Studio、Video Tasks、Gallery 联合回归 `31/31` 通过，时间线算法独立
  验证覆盖左移碰撞、右移波纹、相连链与群组整体移动；Ruff、JavaScript 语法和目标文件 diff
  检查通过。固定 App Dev 因验收时 Mac 锁屏未能完成本轮 GUI 复验，源码由开发环境热挂载，待
  下次解锁后刷新即可使用。
- Composer Chat 面板临时隐藏（2026-09-06）：当前内嵌 Chat 区域不再参与布局，Clip Inspector
  改为占满底部宽度；聊天计划与编辑逻辑暂时保留，供后续迁移为独立 Chat MiniEntry 时复用。
  首次实机验收仍出现 Chat，确认并非浏览器缓存，而是固定 App Dev 的旧包仍在提供过期的内嵌
  WebUI，未实际命中当前源码热挂载。已通过 `build-app-dev-environment.sh` 标准入口重建固定
  `AI2Apps-app-dev.app` 并重启；新 Local 端口 `52717` 返回当前 Composer 脚本，实机界面已出现
  Group/Ungroup 与颜色功能且不再包含 Chat 控件。重建通过 release verification，运行后的固定
  App bundle identity、`app-dev` instance、Development/source-root/cloud Runtime 合同及严格
  codesign 校验均通过。
- Clip Inspector 可读性修复（2026-09-06）：经两轮 App-Dev 实机视觉复核，最终将标题、字段
  标签和输入值分别从原有 10/7/9 px 调整为 16/11/13 px，输入控件增高到 36 px，桌面布局从
  每行四项降到三项；同步提高文字、边框和禁用状态的对比度并增加蓝色键盘焦点轮廓。标题栏
  操作按钮使用单行居中的弹性布局，在空间不足时整组换行，避免 Group/Ungroup/Split 文本越出
  按钮边界。
- Composer 帧网格时间基准（2026-09-06）：Clip Inspector 的 Start/Duration 固定显示三位小数，
  并分别显示起始帧号和持续帧数。项目 FPS（默认 30）成为时间线结构编辑的最小单位；本地或
  Gallery 素材插入、拖放、Clip/Group 移动、左右裁切、播放头定位、分割、Inspector 输入、磁吸、
  ripple 推动及旧草稿恢复均统一量化到帧边界。后端在 Project 校验入口再次按 FPS 归帧，确保
  聊天编辑或其它客户端提交的亚帧小数不会进入渲染时间线。
- Composer Clip 关键帧（2026-09-06）：视频/图片 Clip 可在当前播放头所在帧添加多个关键帧，
  每帧保存 X/Y、宽高和透明度；目标关键帧可选择硬过渡、线性过渡或柔性缓入缓出。Inspector
  提供帧列表、选择、属性编辑和删除，时间线 Clip 显示菱形关键帧标记；预览区拖动、缩放及双击
  恢复素材尺寸会编辑当前选中的关键帧。关键帧使用 Clip 相对整数帧持久化，后端校验唯一性和
  Clip 范围，PyAV 导出使用与前端相同的插值语义；裁切会重映射或移除受影响关键帧，分割会将
  关键帧分配到左右片段并保持分割点的画面状态。已通过固定 App-Dev 环境重建与实机 UI 验证：
  Clip 可在播放头添加 F0 关键帧，Inspector 可编辑属性、删除关键帧，并可在硬过渡、线性和柔性
  三种模式间切换；重启后的 App-Dev Local 运行于 `127.0.0.1:54667`。
  - 固定端点关键帧（2026-09-06）：每个视频/图片 Clip 会自动拥有 `start` 与 `end` 两个端点关键帧，
    分别锁定在首帧与最后一个有效帧；界面以锁形图标区分且禁用删除，起始关键帧无前序画面，
    因此固定为硬过渡。调整 Clip 长度时结束关键帧自动随尾帧移动，裁切与分割会为结果片段重建
    正确的端点状态；后端保存校验也会补齐并归位端点，旧草稿可直接迁移。
  - 预览变换语义（2026-09-06）：播放头正好命中关键帧时，预览层以橙色边框和「关键帧」标记
    提示局部编辑，移动、缩放及双击恢复尺寸只写入当前关键帧；播放头位于两帧之间时，改用青色
    边框和「整个片段」标记，平移会给 Clip 基础位置及全部显式关键帧位置施加相同偏移，缩放会按
    宽高比例更新 Clip 与全部显式关键帧尺寸。关键帧的 X/Y、宽高、透明度允许留空，留空字段在
    预览和 PyAV 导出中均继承上一个关键帧的已解析值，Inspector 以占位值提示当前继承结果。
  - 淡化职责收敛（2026-09-06）：关键帧透明度成为视频画面淡入淡出的唯一机制，PyAV 导出不再
    把 Clip 的 Fade 参数额外乘入画面透明度，避免与关键帧动画叠加产生非预期结果。原 Fade 参数
    仍保留用于音轨包络与快速预览音量，Inspector 和中英文提示统一改名为「音频淡入/淡出」，且
    仅对含音频素材显示；聊天规划提示也明确这两个字段只影响音频。
  - 播放头磁吸与端点保护（2026-09-06）：在时间刻度或预览进度条拖动播放头时，会按同一 12 px
    阈值吸附到任意 Clip 的起点和终点，并以蓝色播放头反馈命中状态；关闭 Snap 后立即恢复逐帧
    移动。新增 `Cmd/Ctrl+N` 快捷键快速开关磁吸，工具栏提示同步标明快捷键。首尾关键帧的删除
    保护扩展到端点标记及首尾帧位置双重判断；选中关键帧时按 Delete/Backspace 只尝试删除当前
    关键帧，不再误删 Clip，端点帧保持锁定。后端仍会在收到缺失端点的数据时自动补回固定首尾帧。
    在轨道上单击 Clip 时，如果播放头位于片段范围之外，会比较与片段起点、终点的距离并跳转到
    更近的一端；播放头已在片段内时保持当前位置，实际拖动 Clip 时也不会触发这次跳转。
  - 关键帧位置与多选拖动（2026-09-06）：关键帧 Inspector 增加整数帧位置输入，普通关键帧可在
    Clip 内部帧之间移动，拒绝占用已有关键帧的帧位，并同步移动播放头；固定首尾关键帧的帧位置
    输入保持禁用。轨道多选后，拖动已选 Clip 会保留当前选择，并把与它在同轨排列中前后相邻的
    已选 Clip 组成临时移动块；无需素材边界恰好逐帧贴合，块内相对间隔保持不变。被动跟随的已选
    Clip 计入移动块尾边界，继续按现有 ripple 规则推动后方未选 Clip，从而维持同轨不重叠约束。
  - 轨道工具栏整理（2026-09-06）：移除预览上方重复的添加视频/音频轨按钮，只保留轨道区入口；
    Undo/Redo 以及每条轨道的静音、锁定、删除按钮提供不会被时间线裁切的浮层 Hover Tip 和无障碍
    标签。删除含 Clip 的轨道前显示可撤销确认，空轨道仍可直接删除。新增轨道时若当前选中了 Clip，
    会插入到该 Clip 所在轨道之后并重新编号轨道层级；没有选中 Clip 时仍追加到末尾。
    - Hover Tip 定位修复（2026-09-06）：提示层改为传送到页面顶层，脱离 Composer 的裁切上下文；
      水平方向使用真实指针位置并补偿 App Shell Mini-App 挂载偏移，垂直方向保持在控件上方 6 px，
      同时在窗口左右各保留 88 px 安全边界。固定 App Dev 重建后，新 Local 端口 `55529` 实机确认
      Undo 提示框与按钮中心对齐；Composer 专项测试 `10/10`、JavaScript 语法及 diff 检查通过。
  - 视频轨输出语义（2026-09-06）：视频轨的首个控制由音量图标改为眼睛图标，Hover Tip 明确为
    「隐藏/显示视频轨道」；音频轨继续使用扬声器图标和「静音/取消静音」。隐藏视频轨只关闭画面
    合成，素材自身的音频仍参与快速预览和 PyAV 导出混音；静音音频轨则继续完全排除其声音。
  - Clip 蒙版图（2026-09-06）：视频/图片 Clip 可从 Inspector 导入或从已登记图片素材中选择独立
    蒙版，草稿和渲染请求仅保存受作用域保护的不透明 `maskSourceId`。蒙版在快速预览和 PyAV 导出
    中始终拉伸至 Clip 当前画面尺寸；带 Alpha 的图片仅以 Alpha 通道决定可见度，没有 Alpha 的
    图片转换为亮度蒙版，黑色完全透明、白色完全不透明、中间灰度形成半透明。蒙版与原素材 Alpha
    及关键帧透明度相乘，API 在导出前验证蒙版 Source 存在且确实为图片。
  - 项目文件、素材替换与变速 ripple（2026-09-06）：Composer 工具栏新增打开、保存、另存为，
    使用 `.ai2video` JSON 项目文件；文件仅包含时间线结构和 AppInstance 作用域内的不透明 Source
    ID，不记录媒体真实路径。Local 以 4 MiB、严格 schema、绝对路径和素材作用域校验为边界，并
    通过同目录临时文件原子替换保存；自动草稿保留最近项目文件路径，`Cmd/Ctrl+S` 与
    `Cmd/Ctrl+Shift+S` 分别执行保存和另存为。Clip Inspector 可在同类已登记媒体源之间替换素材，
    保留布局、蒙版和关键帧，新源较短时复用右边界 ripple 收缩。视频/音频 Clip 的 Speed 编辑以
    保持源片段范围不变为语义，自动按 `旧时长 × 旧速度 ÷ 新速度` 对齐帧网格重算 Duration；变慢
    推后重叠/相接的同轨后续 Clip，变快向左收拢相接链，聊天变速指令使用相同路径。Composer 专项
    测试 `10/10` 通过，Ruff、JavaScript 语法、英文/中文 JSON 与 `git diff --check` 通过；固定
    `AI2Apps-app-dev.app` 已按标准流程重建，并彻底重启 Helper、Local 与 Shell。新 Local 运行于
    `127.0.0.1:59781`，实机确认 Open/Save/Save as 均正确本地化、旧的预览区加轨按钮已移除，选择
    Clip 后可见 Media source、Speed 与帧对齐 Duration 控件。
- Release notes 建议：Video Studio 现在可以在本地完成多轨视频剪辑、音轨拼接、图层合成与
  MP4 导出，并可通过聊天指令安全地批量调整时间线。
- 纳入 Build：待定。

### NXR-025：禁止 Local 修改已签名内嵌 Python Runtime

- 状态：`ready`
- 类型：Desktop Helper、Runtime 完整性、签名稳定性。
- 内容：`LocalLaunchPlan` 现在强制设置 `PYTHONDONTWRITEBYTECODE=1` 与
  `PYTHONNOUSERSITE=1`，并忽略父进程对这两个值的覆盖。Local 启动后不再向已签名的内嵌
  `site-packages` 写入 `__pycache__/*.pyc`，也不会加载用户 site-packages。
- 原因：Video Composer 实机验收发现，内嵌 Python 首次启动生成 `sitecustomize.pyc` 会改变
  Helper 的 sealed resources，使启动前通过的 `codesign --verify --deep --strict` 在启动后失败。
- 验证：Supervisor Core `72/72` 单元测试通过并覆盖两个强制环境变量；固定 App Dev 重建后，
  启动前与启动后均通过 `codesign --verify --deep --strict`，新 Helper/Local 在端口 `52667`
  健康运行，内嵌 site-packages 未再生成 `sitecustomize*.pyc`。
- 需要进入 App 的文件：
  - `apps/ai2apps-acefox/Sources/AI2AppsSupervisorCore/LaunchPlan.swift`
  - `apps/ai2apps-acefox/Tests/AI2AppsSupervisorCoreTests/SupervisorCoreTests.swift`
- 纳入 Build：待定。

### NXR-026：Mini-App ACPF 启动请求校验修复

- 状态：`ready`
- 类型：App-Shell Mini-App、ACPF 启动可靠性。
- 用户可见问题：Read Aloud 的直接配置入口会提交带 `returnTo` 但没有合法
  `resumeToken` 的 Intent，触发 ACPF 请求模型 422；Video Studio 在进入 ACPF 前保存的
  私有草稿包含后端严格 schema 未声明的 `pipelineId`，因此同样在配置档位界面出现前失败。
- 修复：Read Aloud 为每次非 Probe 配置请求生成稳定的非空恢复 Token，已有动作 Token
  继续优先复用；Video Studio 的 ACPF 私有草稿只提交后端声明并实际恢复的字段，不再携带
  冗余 `pipelineId`。
- 需要进入 App 的文件：
  - `ai2apps/web/static/js/readaloud.js`
  - `ai2apps/web/static/js/video_studio.js`
- 发行测试：
  - `tests/test_ai2apps_readaloud.py`
  - `tests/test_ai2apps_video_studio.py`
  - `tests/test_ai2apps_provisioning.py`
- 验证（2026-09-06）：JavaScript 语法检查通过；Read Aloud、Video Studio 与 ACPF
  专项回归 `53/53` 通过。固定 `AI2Apps-app-dev.app` 强制刷新后，实机分别从 Train
  Character 的“Configure voice environment”和 Text to Video 的“Configure generation
  environment”打开 ACPF 配置档位对话框，不再出现 `Request validation failed` 或
  `Video Studio draft is invalid`；验证停在档位选择并取消，没有启动安装或下载。
- Release notes 建议：修复 Read Aloud 与 Video Studio Mini-App 无法打开本地模型配置的
  问题。
- 纳入 Build：待定。

### NXR-027：已安装 Package 的统一 Studio Mini-App Registry 与可信挂载

- 状态：`ready`
- 类型：App-Shell 平台、Package 兼容扩展、Studio 扩展机制。
- 用户可见结果：已安装且启用的普通 App Package 可以在签名覆盖的 `app.yaml` 中用可选
  `mini_apps` 一次声明多个 Mini-App 及其 Studio placements；Video Studio、Read Aloud 与
  Imagine Studio 的既有 Mini-App 列表接口通过统一 Registry 合并内置项和已安装项。平台新增
  通用 discovery/mount API，挂载时复用 AppInstance、`app_mounts`、资源摘要校验、权限检查与
  现有 constrained/sandbox CSP 路由。Video Studio、Read Aloud 与 Imagine Studio 已接入共用
  客户端：Package Mini-App 会出现在已安装列表中，选中后以 Registry 返回的受限
  `content_url` 加载其中栏 WebUI。
- 向后兼容：没有 `mini_apps` 的旧 App Package 行为不变；Cloud 仍发布和下发既有
  `ai2apps.package-manifest.v1`、`type: app` 制品，不需要新的 Package 类型或 Cloud API。
  内置 ID 保留；多个 Package 的同 ID 冲突会从发现结果隐藏并拒绝挂载，不能覆盖内置实现。
- 安全边界：Package Mini-App 不允许 `host-adapter`，只允许 `schema`、`safe-html` 或
  `sandbox`；入口必须存在于签名文件索引；挂载要求匹配的 Studio AppInstance，session 和
  actor 权限继续由现有 Extension Manager 校验。
- 需要进入 App 的文件：
  - `ai2apps/extensions/archive.py`
  - `ai2apps/extensions/manager.py`
  - `ai2apps/studio/registry.py`
  - `ai2apps/api/studio_mini_apps.py`
  - `ai2apps/api/router.py`
  - `ai2apps/api/video_studio.py`
  - `ai2apps/api/readaloud.py`
  - `ai2apps/api/imagine_studio.py`
  - `ai2apps/web/static/js/studio_mini_apps.js`
  - `ai2apps/web/static/js/video_studio.js`
  - `ai2apps/web/static/js/readaloud.js`
  - `ai2apps/web/static/js/imagine_studio.js`
  - `ai2apps/web/static/css/studio_mini_apps.css`
  - `ai2apps/web/templates/system_apps/video_studio.html`
  - `ai2apps/web/templates/system_apps/readaloud.html`
  - `ai2apps/web/templates/system_apps/imagine_studio.html`
  - `docs/ai2apps-studio-mini-app-package-contract-v1.md`
- 发行测试：
  - `tests/test_ai2apps_extensions.py`
  - `tests/test_ai2apps_video_studio.py`
  - `tests/test_ai2apps_readaloud.py`
  - `tests/test_ai2apps_imagine_studio.py`
  - `tests/test_ai2apps_platform_api.py`
  - `tests/test_ai2apps_studio_mini_app_client.py`
- 验证（2026-09-06）：合并后的 Registry、Extension、三个 Studio、客户端和平台 API 专项
  回归 `55/55` 通过；新增用例覆盖已安装 Package
  discovery、Studio mount、content URL、旧 Mini-Entry/移动回退、未索引/特权入口拒绝、内置
  ID 保留及多 Package 冲突；四个 JavaScript 文件语法检查、专项 Ruff 与 `git diff --check`
  通过。当前工作树另有
  Video Studio Mini-App Chat 改动使既有 `test_video_studio_uses_first_party_surface_and_async_video_api`
  关于 `await this.generate()` 的断言失败；该行不属于本项改动，发布候选合并时需由对应改动处理。
- 当前边界：本项建立统一发现和可信 WebUI 挂载路径；跨 Package 的 Run/Step/Artifact、
  Asset-drop、Capability Broker 与 Coder 模板仍按后续独立合同推进。
- Release notes 建议：Studio 现在可以从已安装的兼容 Package 发现并安全挂载 Mini-App，
  同一 Package 可向多个 Studio 提供多个创作入口。
- 纳入 Build：待定。

### NXR-028：Mini-App Chat 对话控制机制

- 状态：`ready`
- 类型：App-Shell 平台、Studio UI、模型 Tool 调用、安全协议。
- 用户可见结果：Video Studio、Read Aloud 与 Imagine Studio 会根据当前 Mini-App 的
  `ai2apps.mini-app-chat/v1` 能力显示 Chat 入口；Chat-Mini-Entry 在每轮读取 Mini-App 提供的
  System Prompt、当前状态 Context 和白名单 Tool，通过对话更新可见草稿或启动当前操作。
  三个 Studio 的全部现有内置 Mini-App 均已接入。每个内置 Mini-App 另有独立 `help.md`；
  帮助正文不进入常驻 Context，只有模型判断用户在询问用法、输入、设置或故障排查时，才通过
  保留的 `read_mini_app_help` Tool 按需加载。Studio 左侧的 Mini-Apps、Assets、Chat 标签保持
  单行等分布局；Chat-Mini-Entry 将当前 Mini-App 说明与模型选择拆成两行，模型下拉框独占整行。
- 安全边界：模型没有通用 DOM、JavaScript、HTTP、文件系统或浏览器 Tool；同源且 channel
  绑定的 iframe 协议只允许调用当前合同中的 Tool，Studio 在执行前重新校验当前 Mini-App、
  Tool 名和参数。生成、渲染、导出等操作由 Studio 侧强制二次确认；能力扩张继续进入既有
  Capability Broker，浏览器操作继续遵守 WebDriver BiDi 单协议边界。
- 帮助边界：Tool 不接受资源路径，只能读取当前 Mini-App 绑定的 Markdown；Package 的帮助
  文件必须进入签名文件索引，内置与 Package 帮助均限制为 32 KiB，普通对话不加载正文。
- Package 扩展：签名 `app.yaml` 可声明可选 `chat` 合同；安装时校验 System Prompt、
  `studio-bridge` Context transport、签名 `help.md`、Tool 名、JSON object input schema 与确认策略。未声明
  Chat 的 Package Mini-App 不显示入口。
- 定义定位：Mini-App-Chat 是建议能力，不是 Mini-App 安装、发现、挂载或运行的强制条件；
  建议作者至少采用 Help-only 配置（按需 `help.md`、最小 Context、`tools: []`），需要对话控制时
  再增加状态与操作 Tool。
- 需要进入 App 的文件：
  - `ai2apps/studio/mini_app_chat.py`
  - `ai2apps/studio/registry.py`
  - `ai2apps/extensions/archive.py`
  - `ai2apps/web/static/js/mini_app_chat.js`
  - `ai2apps/web/static/js/chat_mini.js`
  - `ai2apps/web/static/js/video_studio.js`
  - `ai2apps/web/static/js/readaloud.js`
  - `ai2apps/web/static/js/imagine_studio.js`
  - 三个 Studio 模板与 `ai2apps/web/static/css/mini_app_chat.css`
  - `ai2apps/web/static/help/mini_apps/*/help.md`
  - `docs/ai2apps-mini-app-chat-architecture.md`
  - `docs/ai2apps-studio-mini-app-package-contract-v1.md`
- 发行测试：
  - `tests/test_ai2apps_mini_app_chat.py`
  - `tests/test_ai2apps_chat_mini.py`
  - `tests/test_ai2apps_video_studio.py`
  - `tests/test_ai2apps_readaloud.py`
  - `tests/test_ai2apps_imagine_studio.py`
  - `tests/test_ai2apps_extensions.py`
- 验证（2026-09-07）：五个相关 JavaScript 文件通过 `node --check`，Python 合同模块通过
  编译与 Ruff 检查；Chat Mini、三个 Studio、Mini-App Chat 合同和 Extension 专项回归 `55/55`
  通过。实时合同同时执行 16,000 字 System Prompt、64 KiB Context、64 个 Tool、Tool 名、
  object input schema 与确认策略上限校验；切换 Mini-App 会清空旧对话上下文。帮助正文通过
  `read_mini_app_help` Tool 懒加载，不随 System Prompt 和状态 Context 常驻发送。2026-09-07 已在
  `AI2Apps-App-Dev` 的 Read Aloud 窄侧栏实机刷新验证：三个入口同排，模型选择为独立全宽行。
- Release notes 建议：Studio 的每个内置 Mini-App 现在都可以通过专属 Chat 入口理解当前
  草稿，并在显式 Tool 与确认边界内按自然语言修改设置和执行工作。
- 纳入 Build：待定。

### NXR-029：Discover 独立 Mini-App 目录

- 状态：`ready`
- 类型：Discover UI、App Package 构建合同、Mini-App Registry 索引、Cloud 查询合同。
- 用户可见结果：Discover 一级筛选调整为 `All / Apps / Mini-Apps / Agents / Models / Services`；
  Mini-Apps 拥有效率、图像、视频、音频、文档、自动化、开发和工具等独立二级目录，并允许
  Package 使用可扩展分类。一个 App Package 可同时显示一张完整 App 卡片和多张 Mini-App
  组件卡片。
- 生命周期边界：Mini-App 仍不是新的 Package 类型；组件卡片的安装、升级、签名验证、权限、
  回滚和卸载全部绑定所属 App Package。已安装旧 Package 直接从本地已验证 `app.yaml` 生成组件
  目录，不要求重新安装。
- Package 合同：构建器从 `app.yaml.mini_apps` 自动生成签名 `ai2apps.json.miniApps` 投影，包含
  canonical component ID、名称、版本、生命周期、Catalog 分类和 Studio placements；手写索引
  与 App 定义不一致时拒绝构建，安装时再次交叉校验。
- 需要进入 App 的文件：
  - `ai2apps/packages/contract_v1.py`
  - `ai2apps/packages/registry.py`
  - `ai2apps/web/static/js/discover.js`
  - `ai2apps/web/templates/system_apps/discover.html`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
  - `docs/ai2apps-studio-mini-app-package-contract-v1.md`
  - `docs/ai2apps-cloud-mini-app-discovery-requirements.md`
- 发行测试：`tests/test_ai2apps_discover_categories.py`、`tests/test_ai2apps_registry_v1.py`、
  `tests/test_ai2apps_extensions.py`。
- 当前验证（2026-09-07）：合同、Registry、Extension、Coder 与 Discover UI 联合回归 `89/89` 通过；
  Ruff、JavaScript 语法、i18n JSON 与 `git diff --check` 通过。Cloud 尚需按交接文档接受并索引
  新的签名 `miniApps` 字段，客户端在此之前保留 App Package 查询兼容路径。固定 App Dev 已
  完整重开至 Local 端口 `56501`；实机确认一级 `Mini-Apps` 以及效率、图像、视频、音频、文档、
  自动化、开发和工具二级目录均正常显示。当前生产 Cloud 尚无 `miniApps` 索引，因此目录按
  预期显示为空，不伪造独立 Package。
- Release notes 建议：Discover 新增独立 Mini-Apps 目录，可按任务领域查找组件；安装仍安全地
  复用所属 App Package，不产生重复 Package 或版本。
- 纳入 Build：待定。

### NXR-031：Discover 统一游标分页

- 状态：`ready`
- 类型：Discover UI、Catalog 查询兼容层、Cloud 分页合同。
- 用户可见结果：Discover 的 Apps、Mini-Apps、Agents、Models、Services 与混合 All 目录统一使用
  24 条首屏和显式“加载更多”；搜索词或分类改变时从第一页开始，返回旧组合时恢复已加载内容与
  下一页游标，避免重复请求和滚动内容丢失。
- 兼容边界：Desktop 接受 `nextCursor`、`next_cursor` 及分页 envelope；旧 Cloud 返回满页但不返回
  游标时，Desktop 自动按旧接口上限预取 100 条并在本地以 24 张卡片分页，避免升级过渡期隐藏
  既有 Package。追加结果按卡片稳定 ID 去重，Mini-App 使用 `packageId#componentId`。
- Cloud 交接：`docs/ai2apps-cloud-discover-pagination-requirements.md` 要求 Cloud 提供查询绑定的不透明
  游标、混合 All 排序、模型原生过滤以及 Mini-App 组件级分页。Cloud 升级前，Mini-App 仍可按
  Package 页展开，模型仍使用 Local 兼容过滤，因此页面数量可能不足 24，但不会破坏现有目录。
- 需要进入 App 的文件：
  - `ai2apps/web/static/js/discover.js`
  - `ai2apps/web/templates/system_apps/discover.html`
  - `ai2apps/web/i18n/en.json`
  - `ai2apps/web/i18n/zh.json`
  - `docs/ai2apps-cloud-discover-pagination-requirements.md`
- 发行测试：`tests/test_ai2apps_discover_categories.py`、Catalog API 与 Cloud Client 回归。
- 当前验证（2026-09-07）：Discover、Registry 与 Cloud Client 联合回归 `86/86` 通过；JavaScript
  语法、i18n JSON 和 `git diff --check` 通过（沙箱退出时仅有预期的 Metal unavailable 提示）。
  固定 App Dev `AI2Apps-App-Dev: M5Max128G · App-Dev 127.0.0.1:56501` 曾以 6 条试验页长完成
  游标追加、加载态和去重验收；最终产品页长已按用户确认恢复为 24，相关 Discover 定向测试
  `20/20` 与 JavaScript 语法检查再次通过。
- Release notes 建议：Discover 的每个目录现在都可按需加载更多 Package，同时保留当前筛选和
  已加载结果。
- 纳入 Build：待定。

### NXR-032：App Dev 重启 Local 保留实时源码根

- 状态：`ready`
- 类型：App Dev Helper、Local 进程监督器；仅影响固定开发环境。
- 问题：Helper 首次启动会把已验证的 `AI2AppsDevelopmentSourceRoot` 传给
  `LocalProcessSupervisor`，但用户选择重启 Local 后，`replaceSupervisor()` 重建监督器时漏传该
  参数，导致新 Local 静默退回 App 内嵌旧源码。表现为 Discover 新筛选和分页在重启后消失。
- 修复：Helper 在生命周期内保留已验证的开发源码根；首次启动和每次重建监督器现在统一经过
  `makeLocalSupervisor()`，由该唯一入口同时注入控制凭据、Development Runtime 标记和源码根，
  避免两段重复构造逻辑以后再次漂移。生产 App 没有 Development 标记，源码根仍为 `nil`，不会
  获得源码挂载能力。Python 回归门禁还会要求 Helper 只保留一个底层 Supervisor 构造点，并确认
  首次启动与重启都调用同一工厂。
- 需要进入 App 的文件：
  - `apps/ai2apps-acefox/Sources/AI2AppsHelper/main.swift`
  - `tests/test_ai2apps_helper_control.py`
- 当前验证（2026-09-07）：唯一 Supervisor 工厂重构后，Swift Helper/Supervisor 全量测试 `72/72`
  通过；Helper 控制与 Discover 回归门禁 `28/28` 通过。固定 App Dev 已再次通过
  `build-app-dev-environment.sh` 重建并完成签名/Release App 校验。首次启动端口 `56108` 的 Discover
  显示当时配置的首屏、Mini-Apps 和 `Load more`；随后通过受保护 Helper 接口真实执行
  `local.restart`，新进程端口 `56624` 再次打开 Discover 仍显示相同内容，确认重启继续使用当前
  开发源码。
- Release notes 建议：不适用；这是开发环境可靠性修复。
- 纳入 Build：App Dev 环境专用，不进入生产 Build。

### NXR-030：Media Voice Studio Suite 五条 Mini-App 执行链路

- 视频字幕分段校对（2026-09-30）：Video Subtitles Mini-App 从一次性“转写后直接导出/烧录”改为
  `extract → review → render` 两阶段。第一阶段列出所有带时间范围的字幕段落，用户可逐段修改文本或
  清空以移除字幕；第二阶段以校对文本执行可选翻译、SRT/WebVTT/ASS 导出和 MP4 烧录。新的
  `subtitle_action`/`subtitle_segments` 只经过当前 mount-bound MessageChannel，Host 将 UTF-8 JSON
  限制为 2 MiB，并重新校验 1–10000 段、时间范围、顺序、单段文本和 speaker，只保留公开字段；
  修改后不会重新转写，也不会信任 Package 提交的 word/provider 内部数据。最终烧录视频继续进入
  Video Studio 共用 Preview & Output，Mini-App 不新增私有播放器或输出历史。相关 Package、
  Broker、媒体工作流和 Host bridge 回归 `109/109` 通过，Ruff、JavaScript 语法与
  diff 空白检查通过。固定 `app-dev` Local 已通过认证 Helper 控制通道单独重启，端口从
  `51397` 切换到 `52306`；实机 Video Studio 已加载 Package Mini-App 的“提取字幕段落”入口。
  本轮未执行真实长视频模型推理，不宣称字幕质量或烧录速度已完成实片验收。
  后续布局修正（2026-09-30）：校对面板改为无 Step 标记的独立内容区，排在处理链路之前；
  删除“同时生成烧录字幕的视频” Checkbox，提取后在处理链路底部分开显示“生成字幕文件”
  和主操作“生成字幕视频”，只有后者传入 `burn_in=true`。
- 安装入口位置修正（2026-09-10）：按用户澄清，删除 STT/TTS 下拉框下方按钮，将“安装更多模型”放在两个下拉菜单末尾。动作项不写入 audioSettings，触发 ACPF 前立即恢复实际模型值，取消安装不改变原模型。新增执行实际 JavaScript 的动作项与正常选择回归测试。
- 安装更多模型（2026-09-10）：Chat STT/TTS 选择器下新增本地化入口，进入 ACPF 全部能力配置列表；新增 installMore 浏览模式避免已有可用模型时提前返回，已安装 Checkpoint 对应项显示“已安装”并禁选，全部已安装时仍可查看列表但无法继续安装。保持 ACPF 原有确认、许可证和下载流程。变更涉及 Local Python，App-Dev 需重启 Local 后验收。
- Chat 语音模型可用性修复（2026-09-10）：STT/TTS 列表只保留已就绪模型，综合目录、管理目录和运行状态排除缺权重、隐藏、加载失败项；Package 需明确 checkpoint_ready 才显示，已安装但尚未驻留内存的普通模型不因 loaded=false 被误排除。旧选项不可用时回退至可用项，无可用项则清空。新增实际 JS 判定回归测试，避免未安装 Base/VoiceDesign 仍可选择后才报 Checkpoint is not installed。
- 状态：`ready_for_package_rebuild`
- 类型：Studio Package、Local Capability Broker、语音模型调用。
- 用户可见结果：`ai2apps/media-voice-studio-suite 0.1.0` 在一个普通 App Package 中交付五个
  音视频 Mini-App；其中“录音文本记录”已可从 Read Aloud 或 Video Studio 的可信 mount
  调用本地 MLX WhisperX Detailed Transcription Compact/Quality，显示分段时间和匿名说话人，
  并允许用户为角色指定名称后导出 JSON。“人声和背景音分离”也已可通过同一 Broker 调用
  capability contract 匹配的 MLX Demucs provider，选择二轨/四轨 profile 并下载包含 WAV stems
  与 `separation.json` 的 ZIP。视频字幕可生成 SRT/WebVTT/ASS、调用现有 Standard 模型路由翻译、
  输出双语字幕并选择烧录 MP4。录音和视频角色换声采用两阶段交互：先识别匿名说话人，再使用
  授权参考声音只替换所选角色并保留其他对白、背景和原视频画面。
- App Shell 边界：该 Package 是纯 Mini-App provider，声明 `navigation.launcher: false`，不再作为
  独立 App 出现在 App Launcher、Dock、App 建议或 Mobile App 列表；五个 Mini-App 仍只通过其
  Read Aloud / Video Studio placement 发现和挂载。真正提供独立顶层 App 的混合 Package 保持
  默认可启动。
- 安全边界：Host 每次调用重新核验 actor、mount、Studio、Mini-App canonical ID、Provider
  App、有效 Package digest 和声明能力；详细转写只允许固定模型配置，音轨分离只选择已验证
  capability contract 明确支持所选 profile 的 `audio_processing` provider。媒体在 Host 中
  规范化为有界 PCM WAV，Mini-App 不取得 Worker endpoint、checkpoint 路径或任意本地路径。
  参考换声只选择 capability contract 声明 `reference_audio` 的 provider，并在 Host API 再次
  强制校验权利确认；视频字幕和音轨替换只使用内嵌 PyAV，不启动外部 ffmpeg。
- 需要进入 App 的文件：
  - `ai2apps/studio/capability_broker.py`
  - `ai2apps/studio/media_workflows.py`
  - `ai2apps/studio/__init__.py`
  - `ai2apps/api/studio_mini_apps.py`
  - `packages/ai2apps-media-voice-studio-suite/*`
  - `docs/ai2apps-studio-mini-app-package-contract-v1.md`
- 发行测试：
  - `tests/test_ai2apps_studio_capability_broker.py`
  - `tests/test_ai2apps_studio_media_workflows.py`
  - `tests/test_ai2apps_media_voice_studio_suite.py`
  - `tests/test_ai2apps_studio_mini_app_client.py`
  - `tests/test_ai2apps_extensions.py`
- 当前验证（2026-09-07）：Broker mount/digest/声明约束、详细转写、Demucs、Seed-VC provider
  probe、WAV 规范化、目标角色时间窗替换、背景保留、SRT/VTT/ASS、CJK 字幕烧录、MP4 音轨替换、
  JSON/ZIP/WAV/MP4 artifact 透传、multipart API、Registry 和 Extension 回归共 `85 passed`；Ruff、
  JavaScript 语法和 `git diff --check` 通过。Package Contract 重复构建字节一致，并修复 App Package
  误将自身 `dist/` 制品再次打包的递归问题。固定 `AI2Apps-App-Dev` 已重启并在真实 OpenAPI
  中加载三类 Studio Mini-App mount/capability 路由。正式 Publisher 签名制品与 envelope
  已使用注册公钥指纹离线验签通过，详见
  `docs/ai2apps-media-voice-studio-suite-0.1.0-signed-build.md`。正式候选使用显式的旧 Cloud schema
  兼容构建：外层不携带可选 `miniApps` 搜索投影，五个组件仍全部保留在已索引、已签名的
  `app.yaml`，安装后发现机制不变。Cloud 组件级 Discover 仍按已交付需求后续升级；真实
  checkpoint 端到端运行在 Package 安装后继续作为发布验收。
- App Launcher 修复验证（2026-09-08）：新增 `navigation.launcher: false` 的 manifest 类型校验和
  Launcher catalog 过滤；确认 provider Package 从 `list_apps()` 消失后，其 Studio Mini-App 仍可
  发现、创建 provider AppInstance 并完成可信 mount。Extension、Development source mount、
  Media Voice Suite、Capability Broker、Mini-App client 与 Shell 回归 `158/158` 通过，Ruff 与
  `git diff --check` 通过。现有 0.1.0 已签名候选早于该 manifest 改动，正式发布前必须按标准
  Package runbook 重新生成签名制品与 receipt，不得继续使用旧候选。
- Studio 原生 UI 对齐（2026-09-09）：五个 Package Mini-App 的共享 WebUI 已改用与内置 Studio
  一致的白色中性表面、紧凑标题、分隔线区块、表单密度、黑色主按钮和标准状态色；capability ID
  默认折叠为可展开的“所需能力”诊断信息。Read Aloud、Video Studio 与 Imagine Studio 的宿主
  标题栏在 Package iframe 挂载时固定置于其上方，不再落到内容底部。变更只涉及 UI Entry 与
  Studio 外围布局，没有放宽 sandbox、mount、CSP、Capability Broker 或签名安装边界；五个入口
  统一使用版本化静态资源，并新增视觉契约回归门禁。相关 Studio、Package、源码热挂载与
  Extension 回归 `60/60` 通过，JavaScript 语法和 `git diff --check` 通过；固定
  `AI2Apps-App-Dev: M5Max-128G 127.0.0.1:57115` 已通过强制刷新实机确认标题、依赖按钮、折叠能力
  信息和 Package 工作区顺序正确，并抽查 Video Speaker Voice Replacement 与 Detailed
  Transcription 两个入口共享同一视觉层。
- Package 单滚动面修复（2026-09-09）：新增 source-bound、版本化且高度有界的
  `ai2apps:mini-app-resize/v1` 协议，Package UI 用 `ResizeObserver` 报告内容高度，三个 Studio
  宿主按当前 iframe 的 `contentWindow` 核验消息后扩展中栏。宿主标题与 Package 内容现在随 Studio
  页面一起滚动，不再保留压缩可用面积的 iframe 内层纵向滚动；未实现协议的旧 Package 仍保留
  620px 兼容高度和内部滚动，不改变既有 Package 可用性与安全边界。共享 Client、三个 Studio、
  Media Voice Package、源码热挂载和 Extension 联合回归 `60/60` 通过，两个 JavaScript 文件语法及
  `git diff --check` 通过；固定 App-Dev 已强制刷新并重新挂载 Detailed Transcription，确认新版
  resize Client 与 Package Entry 同时加载。
- Release notes 建议：音视频语音套件现在提供五个可执行 Mini-App：角色化详细转写、音轨分离、
  录音角色换声、可翻译/烧录的视频字幕，以及保留画面的视频角色换声。
- 纳入 Build：待定。

### NXR-033：Development Bundle 直接热挂载 Package 源码

- 状态：`ready`
- 类型：客户端开发体验、Package/App/Mini-App 基础设施
- 用户可见结果：开发 App Package 时不再需要先构建、签名并安装 `.ai2app`；固定
  `AI2Apps-App-Dev` 和重新构建后的通用 `AI2Apps-dev.app` 可从当前仓库
  `packages/<package>/` 直接发现 App 与 Studio Mini-App。HTML/CSS/JavaScript 刷新生效，
  `app.yaml` 在重新读取目录时热加载。
- 安全与兼容边界：只在 Helper 同时提供 Development Runtime 标记和 Bundle 固定绝对源码根
  时启用；只扫描 `packages/` 的非符号链接直接子目录；源码资源继续经过 AppInstance 权限、
  sandbox 和路径边界检查。开发挂载不创建 Package Store 安装记录，生产 Helper、签名安装、
  Cloud Registry 和旧 Package 机制保持不变。
- 需要进入 App 的文件：
  - `ai2apps/extensions/development.py`
  - `ai2apps/extensions/manager.py`
  - `ai2apps/platform_runtime.py`
  - `apps/ai2apps-acefox/scripts/build-dev-app.sh`
  - `docs/ai2apps-studio-mini-app-package-contract-v1.md`
  - `docs/ai2apps-app-development-guide.md`
  - `docs/ai2apps-studio-app-ui-design-standard-v1.md`
- 发行测试：
  - `tests/test_ai2apps_development_packages.py`
  - `tests/test_ai2apps_extensions.py`
  - 在固定 `AI2Apps-App-Dev` 中从源码发现 Media Voice Studio Suite，打开 Package Mini-App，
    修改源码并刷新确认实时生效。
- 当前验证（2026-09-07）：开发源码加载器已通过真实 Media Voice Studio Suite manifest
  校验并发现 5 个 Mini-App；Package/Extension/Studio 合同回归 `62/62` 通过，确认资源热修改、
  `app.yaml` 热加载、重复资源请求不产生定义 revision 写放大、无安装记录以及缺少
  Development Runtime 标记时 fail-closed；新增同一数据库先挂载源码、再无标记重启的回归，
  确认旧 development 定义会被停用。Ruff、Shell 语法、`git diff --check` 均通过。
- 标准流程文档（2026-09-07）：非内置 Mini-App 的规范生命周期已统一为“App Package 源码
  合同 → Development source mount → 真实 Studio 热修改联调 → 签名制品 → 干净实例安装态
  回归 → 标准发布”。Package 主合同、通用 App 开发指南和 Studio/Mini-App 设计规范均已建立
  交叉入口，并明确源码态不是可信安装身份、不能替代签名制品与安装态 Release Gate。
- 实机验收（2026-09-07）：固定 `AI2Apps-App-Dev` 仅重启 Local 后运行于端口 `58279`；
  Video Studio 从源码显示 Media Voice Suite 的 4 个视频相关 Mini-App，并成功把 Detailed
  Transcription 挂载为 sandbox。临时把 `app.yaml` 名称改为 `SOURCE HOT RELOAD` 后刷新即在
  界面出现，恢复源码并刷新后正常还原；平台数据库中该 App 的 development source 定义为
  enabled，`interactive_packages` 安装记录为 0。通用 `AI2Apps-dev.app` 也已用标准脚本重建，
  旧 App 可恢复地归档为 `AI2Apps-dev-20260907-131241.app`，新 Bundle 通过严格 codesign，
  主 App 与 Helper 均固定源码根；新 `dev` Local 在端口 `59685` 启动并同样确认 development
  定义启用、正式安装记录为 0。
- 纳入 Build：待定。

### NXR-037：AI2Apps Official Cloud Connector 双许可证边界

- 状态：`ready`
- 类型：发行许可、Cloud Connector、品牌治理。
- 用户可见变化：AI2Apps 客户端与本地 Runtime 继续默认使用 Apache-2.0；客户端内的
  Official Cloud/OpenAI Connector 从本版本起采用 BSL 1.1。仅连接 AI2Apps 官方 Cloud
  的生产客户端无需商业授权；实现、连接或提供替代 Cloud 服务需要另行取得商业授权。
- 转换规则：本版本的 Change Date 为 `2029-09-07`，届时 Connector 自动转换为
  Apache-2.0。既有 Apache-2.0 版本不追溯撤销授权。
- 商标边界：软件许可证不授予 AI2Apps 名称、Logo、图标或其他来源标识的权利；允许依法
  进行真实、指称性兼容说明，但修改版不得造成官方、合作、认证或背书混淆。
- 需要进入 App 的文件：`LICENSE-POLICY.md`、
  `LICENSES/AI2APPS-CLOUD-CONNECTOR-BSL-1.1.md`、`TRADEMARKS.md`、`NOTICE`、
  `README.md`、`README.zh.md`、`pyproject.toml`、`docs/CONTRIBUTING.md`，以及许可证
  清单列明的五个 Cloud Connector Python 文件。
- 当前验证：许可证元数据、文件级 SPDX 标识、英文/中文说明及发行 NOTICE 已对齐；
  setuptools 已成功解析 Core Metadata 并把全部许可证文件加入 wheel manifest，wheel 的后续
  native build dependency gate 因本机缺少 `cmake>=3.27` 停止；`git diff --check` 通过。
- 纳入 Build：待定。

### NXR-039：未完工内置 App 的 Launcher 开发中状态

- 状态：`ready`
- 类型：App Shell、产品可用性边界。
- 用户可见变化：Sharing、Environment、Messager、Bench 和 Agents 继续显示在 App Launcher 中，但卡片统一
  置灰并显示本地化的“正在开发”，不能点击、Pin 到 Dock 或从旧实例入口打开。
- 安全与兼容边界：内置 manifest 使用显式 `navigation.status: development`；Shell 启动函数、
  App Runtime 启动入口和内置 App 直达路由均拒绝启动，Messager 同时从 Mobile 可启动目录和
  App 建议中排除。其他内置 App 以及 `navigation.status` 缺省为 `active` 的第三方 App 行为不变。
- 需要进入 App 的文件：`ai2apps/apps/system.py`、`ai2apps/extensions/archive.py`、
  `ai2apps/extensions/manager.py`、`omlx/admin/routes.py`、`ai2apps/web/static/js/shell.js`、
  `ai2apps/web/static/css/shell.css` 和 `ai2apps/web/i18n/*.json`。
- 发行测试：`tests/test_ai2apps_extensions.py`、`tests/test_ai2apps_shell.py`。
- 实验标记补充（2026-09-10）：Terminal 与 Coder 的 manifest 新增独立的
  `navigation.experimental` 标记，由目录 API 传到 Launcher，在 App 图标右侧显示本地化的
  “实验 / Experimental”徽标，与图标底部对齐；名称独立成行。仍保持 active，允许正常启动与 Pin。涉及
  `ai2apps/apps/system.py`、`ai2apps/extensions/manager.py`、`omlx/admin/routes.py`、
  Shell JS/CSS 与九种语言文案。按用户要求仅修改源码，未更新、启动或测试 App。
- Agents 补充（2026-09-10）：`ai2apps.agents` 复用开发中状态，在 Launcher 置灰并显示
  本地化的 “In development”，禁用启动与 Pin；同步调整目录状态和直达入口回归。
  Shell 回归 `114/114` 通过，`git diff --check` 通过；尚未做运行中 App 的界面验收。
- Bench 补充（2026-09-09）：`ai2apps.benchmark` 复用开发中状态，Launcher 置灰并显示
  “In development”（随界面语言本地化）；同步调整目录状态与直达入口回归。
  Shell 回归 `114/114` 通过，`git diff --check` 通过；尚未做运行中 App 的界面验收。
- 当前验证（2026-09-08）：App/Extension 与 Shell 契约回归 `135/135` 通过；相关 Python 文件
  Ruff 通过，九种语言 JSON 全部可解析，Shell JavaScript 语法及 `git diff --check` 通过。
- 纳入 Build：待定。

### NXR-040：Read Aloud 更名为 Voice Studio

- 状态：`ready`
- 类型：App Shell、品牌命名与本地化。
- 用户可见变化：内置 `ai2apps.readaloud` 的产品展示名统一为 `Voice Studio`，中文显示名
  同步为“语音工坊”；Launcher、Studio 页头、项目弹窗、辅助功能文案及运行反馈不再显示
  旧品牌名 `Read Aloud`。
- 兼容边界：App ID、路由、模块名、持久化表和既有项目数据继续使用 `readaloud` 身份，
  本次仅变更用户可见品牌与默认标题，不触发数据迁移。
- 需要进入 App 的文件：`ai2apps/apps/system.py`、`ai2apps/api/readaloud.py`、
  `ai2apps/readaloud/tasks.py`、`ai2apps/web/templates/system_apps/readaloud.html`、
  `ai2apps/web/static/js/readaloud.js`、`ai2apps/web/i18n/en.json`、
  `ai2apps/web/i18n/zh.json`，以及对应产品/Studio 规范与回归测试。
- 当前验证（2026-09-09）：Ruff、英中 JSON、JavaScript 语法和 `git diff --check` 通过；
  Read Aloud/Shell 合同回归 `121/121` 通过。固定 `AI2Apps-App-Dev` 的 `app-dev` Local 已
  通过实例专属 Helper 控制通道重启，实机确认 Dock、Quick Start、活动 App、Studio 页头、
  副标题及辅助功能导航均显示 `Voice Studio`，URL 与 App ID 仍为 `ai2apps.readaloud`。
- 纳入 Build：待定。

### NXR-045：Chat 云端多模态模型图片上传能力判断

- 状态：`ready`
- 用户可见结果：修复 GPT 5.6 Luna 等云端模型在运行状态表中缺少 `vlm` 标记时，Chat 隐藏图片上传入口的问题。
- 实现：图片输入判断同时读取模型目录类型、模型能力声明和运行状态；保留目录返回的原始 capabilities，识别图片输入与识图能力。纯图片生成能力不会开启图片输入。
- 文件：`ai2apps/web/templates/chat.html`、`tests/test_chat_ui_overhaul.py`。
- 验证：执行实际 JavaScript 判断函数，覆盖目录 VLM、数组及对象能力、明确关闭、纯文本、图片生成和运行状态回退。
- Test 验证（2026-09-09）：通过固定 `build-test-app.sh` 重建并启动 `AI2Apps-test.app`（0.1.0 / Build 2195，当前工作区快照）；包校验和深层严格签名校验通过，包内 Chat HTML 与工作区逐字节一致，`test` Local `/health` 返回 `healthy`。保留实例数据，旧包已归档；尚未进行真实图片发送验收。本次不是生产发布。
- 纳入 Build：待定。

### NXR-046：Video Studio 模型下拉框接入“安装更多模型”

- 状态：`ready`
- 类型：Video Studio、内置 Mini-App、ACPF 模型配置入口。
- 用户可见变化：文生视频、图生视频和参考素材视频 Mini-App 共用的模型下拉框在末尾新增
  本地化“安装更多模型”；没有可用视频模型时仍可直接进入安装流程。
- 交互与兼容边界：该菜单项仅作为操作，不写入 Studio 草稿、Shell 状态或视频生成请求；
  选择后立即恢复原模型，并以 `installMore: true` 启动共享 ACPF，已有模型就绪时也不会被
  `already_ready` 快速路径跳过。安装完成后刷新完整模型目录并保留仍有效的原选择，取消或
  失败同样不改变选择；并发刷新只允许最新请求发布结果。Package Mini-App 的质量/Profile
  下拉框不是模型 ID 选择器，继续通过 mount-bound Capability Setup 使用 ACPF。
- 需要进入 App 的文件：`ai2apps/web/templates/system_apps/video_studio.html`、
  `ai2apps/web/static/js/video_studio.js`、`ai2apps/web/i18n/en.json`、
  `ai2apps/web/i18n/zh.json`、`tests/test_ai2apps_video_studio.py`。
- 当前验证（2026-09-10）：Video Studio 与 ACPF 回归 `51/51` 通过；Ruff、英中 JSON、
  JavaScript 语法和 `git diff --check` 通过。
- 纳入 Build：待定。

### NXR-052：Studio Mini-App 列表可读性提升

- 状态：`ready`
- 类型：Imagine Studio、Voice Studio、Video Studio 界面样式。
- 用户可见变化：三个 Studio 左侧 Mini-App 列表的主图标由 14–15px 放大到 18px，标题由
  10px 放大到 12px，说明文字由 8px 放大到 10px；Imagine Studio 的补充信息和收藏图标
  同步适度放大。
- 布局边界：不改变 Mini-App 卡片的宽度、最小高度、内边距、网格列、图标容器尺寸或列表
  间距，仅调整卡片内容的字体、行高与 SVG 尺寸。
- 需要进入 App 的文件：`ai2apps/web/static/css/imagine_studio.css`、
  `ai2apps/web/static/css/readaloud.css`、`ai2apps/web/static/css/video_studio.css`。
- 当前验证（2026-09-10）：Video/Voice/Imagine Studio 回归 `25/25` 通过；样式合同检查确认三类
  卡片仍保持原有 `62px`、`58px`、`70px` 最小高度以及原有宽度、内边距、网格列和图标容器。
  固定 `AI2Apps-App-Dev: M5Max-App-Dev 127.0.0.1:62433` 已逐一打开三个 Studio 实机验收，
  左侧图标和文字明显增大，卡片尺寸、排列和单行截断保持正常。
- 纳入 Build：待定。

- 右侧状态统一（2026-09-10）：三个 Studio 的列表使用深灰色下载图标表示依赖待准备，
  可用条目显示收藏星标（未收藏浅灰、已收藏深灰）；规划条目显示灰色不可用标记。
  Voice/Video 新增独立收藏按钮与本地持久化，点击收藏不切换当前 Mini-App；Imagine 保留
  原有收藏存储。卡片尺寸保持不变。涉及上述 CSS 以及三个 Studio 模板、Voice/Video JS。
  回归 `25/25`、JS 语法与差异检查通过；App-Dev（端口 49562）确认新版模板加载、Voice
  就绪条目显示星标而缺依赖条目显示灰色下载图标，Video 收藏切换不会改变当前 Mini-App。

- 列表顶部简化（2026-09-10）：Imagine Studio 移除搜索与“全部 / 收藏 / 最近”筛选区，
  直接展示已安装列表，与 Voice/Video 保持一致；列表不再受隐藏筛选条件影响，保留原有
  可用项优先顺序和卡片收藏。同步更新 Studio 手册与现有模板回归。

- 三列独立滚动（2026-09-10）：共享 `ai2apps/web/static/css/studio_mini_apps.css` 将三个
  Studio 限制在宿主视口内，工作区三列独立滚动；左栏选择区固定，列表占据剩余高度并可
  滚到底。修复 Imagine 列表被裁切；窗口变窄时输出不再堆叠到页面下方。Package 内容
  高度协议保留，内容扩展只影响中栏滚动范围。手册第 4.1 节同步更新，并替代此前整页
  滚动的要求。App-Dev 已实测 Imagine 列表到底，顶部选择区与其它列位置保持不变。
  Voice 三列布局与 Video 中栏独立滚动已实机确认；三个 Studio 回归 `25/25` 通过，
  `git diff --check` 通过。

- Coder 入口统一（2026-09-10）：Voice/Video 列表末尾说明文字替换为与 Imagine 一致的
  全宽“在 Coder 中创建”按钮，使用相同 Shell 启动入口并传入当前 Studio placement。
  涉及两个 Studio 模板/JS、共享 Studio CSS、英中文案，手册同步补充。

- Header 统一（2026-09-10）：三个 Studio 使用共享 64px Header，左侧图标与名称，右侧
  依次为刷新/左栏/右栏图标按钮；移除副标题与云端/本地徽标。Imagine 本地模型配置移到
  中栏模型设置下方，Voice 中栏重复开关移除。涉及三个模板、共享 CSS、英中文案，
  手册第 4.2 节记录尺寸、状态、本地化及移动端规则。
  三个 Studio 已在固定 App-Dev 实机确认 Header 对齐及 Image 模型配置入口位置；
  更新旧副标题断言后，Voice 回归 `8/8`，Video/Imagine 回归 `17/17` 通过，JSON 与差异检查通过。

- Mini-App Header 精简（2026-09-10）：三个中栏只显示名称与信息展开入口，版本/来源/说明
  收进详情；移除重复创建标题、常驻就绪徽标，保留配置及 Run 操作。Imagine 补齐白色卡片。
  涉及三个 Studio 模板、共享 CSS、英中文案；Mini-App 开发合同及设计手册同步记录规范。
  实机确认 Voice 单标题及信息展开、Image 白色卡片与直接输入布局；更新旧重复标题断言后
  Video/Voice 回归 `14/14`、Imagine 回归 `11/11` 通过，差异检查通过。

### NXR-PROCESS-001：建立下一版 Release 滚动台账

- 状态：`ready`
- 类型：发布治理；不改变 App 二进制功能。
- 内容：建立本文件，并将登记、构建门禁、归档和重置规则加入 `AGENTS.md` 与
  `docs/ai2apps-desktop-release-runbook.md`。
- 验收：未来 Desktop 发布必须先逐项处理本文件，不再仅根据工作区 diff 临时整理范围。
- 纳入 Build：不适用；随下一次源码提交生效。

### NXR-ZIMAGE-BASE：独立普通版 Z-Image Package（ready）

- 2026-09-11 最终 App 验收通过（覆盖下方历史阻塞）：port 59377 重启后 ACPF Retry 达到 ready，无重复下载。Imagine Studio 真实 Base / 1024² / 30 步 / CFG4 文生图成功；result isr_6a08567f2ff94a419bc9117e8863d297，Artifact imagine-text-to-image-ffa5f17d.png。Add to Gallery 成功；完整页面刷新恢复模型/参数/图片/成功 Run/Artifact，截图目视通过。首次约五分钟含量化缓存创建，不作为暖态性能指标。97 项回归通过，发布包未改动，无剩余 App 验收门禁；未来 Desktop Build 仍须纳入本地 validator、profile、discovery 与 UI 改动。

- 最新验收（覆盖下方历史阻塞）：App-Dev 重启后已安装正式 Package、下载全部 19.13 GiB 权重，Service running / health ok。95% 校验误判原因为普通版 Runtime scheduler 未进入精确后端合同；已补 (z-image, mflux-native-cfg)，保留缺失分片拒绝检查。Base ACPF verify 已与签名 Service 的 image-generation 能力名对齐。97 项回归通过。仍须再重启 Local 加载修复，再重试现有安装并验证 App 出图/刷新恢复；Helper 自动控制连续超时，等待用户重启。已发布包未改动；此前发布认证阻塞已解除。

- 0.1.0 和对应 checkpoint 已发布，Registry128 / Index63；最终包 SHA256 1650f2b5723e73af4ab267fb5c984cbeee9faf5ebc3c4e8d005f63b5760d7ac1。详见 docs/ai2apps-z-image-base-0.1.0-release.md。
- 新增版本有界 discovery/install/profile 兼容映射，标准 smoke 工具支持独立模型验签公钥；最终签名包独立 Sandbox 启动通过，43 项测试通过。当前 App-Dev 须重启 Local 加载映射后完成最终 App 安装/出图；历史认证阻塞已解除，Cookie 授权已关闭。

- 新增 packages/ai2apps-model-z-image-base-mlx，固定官方普通版 checkpoint；30 步、CFG 4、negative_prompt，使用原生 mflux CFG 管线，不复用 Turbo fusion。
- Imagine Studio 排除普通版的 Turbo 专用参数，保留 Turbo 不变；仅声明文生图，不宣传指令编辑。
- 2026-09-11：真实官方普通版 Q8 / 1024² / 30 步 / CFG 4 出图通过，166.278 秒、Metal 峰值 17,950,257,918 bytes；双源 17 文件共 20,538,488,386 bytes SHA-256 一致。ACPF 独立普通版入口、CFG/negative prompt 控件与草稿恢复已接入，19 项回归通过，JS 语法与 diff 检查通过。
- 发布门禁：Installation 会话查询 Publisher 返回 active user session required；等待本次 Package/Checkpoint 发布的浏览器 Cookie 授权及管理员验证。尚未发布、尚未完成真实签名安装/Sandbox/App 出图验收；不得进入发布候选。32 GiB 内存门槛为基于实测峰值的保守估计，未声称在 32 GiB 机器实测。
- 回退：移除新 Package 和前端普通版排除条件；不涉及已有 Turbo 安装数据。

## 5. 构建下一版前的强制门禁

### NXR-INTERNAL-2250：图像能力配套内部候选（in_progress）

2026-09-11 用户明确授权当前混合工作区的 dirty-tree 内部测试候选；不授权自动 stable 推送或四个模型包发布。Build 2250 内部 App/DMG 已通过标准构建、Developer ID 签名、包体一致性及 2249→2250 内部候选资格检查，未安装、启动、公证或上传；生产仍保持 2249。Swift 76 项通过；Python 首轮 1337 通过/6 个旧静态断言失败，修正后对应模块共 162 项复测通过。候选内 Python 验证 editing-only 与四个新版本映射均通过，未知未来版本继续拒绝；关键源码与包内文件哈希一致。65 个原台账标题仍仅作为内部测试范围，blocked/in_progress 不提升；仍待真实界面、升级及推理验收。详见 `docs/ai2apps-desktop-build-2250-internal-candidate.md`。

### NXR-IMAGE-CAPABILITY-SPLIT：图像操作能力收紧与 Package 升版（Package published / Desktop pending）

2026-09-12 最新状态：用户明确说明当前仍为开发阶段、没有真实生产用户，解除生产 Desktop 升级前置。四个既有签名制品已通过标准脚本发布并回读确认 published：Z-Image Turbo 0.1.3、Ideogram 4 0.1.2、Qwen Image 0.1.2、FLUX.2 Klein 0.1.4。Repository metadata 131→134。本次不发布 Desktop、不扩展音视频测试；新版 Host 验证器及安装映射仍需纳入未来 Desktop。旧版客户端限制不视为已修复。完整 submission 和摘要见 `docs/ai2apps-image-capability-release-2026-09-11.md`。下方未发布记录为历史状态。

最新状态（覆盖下方早期未签名记录）：用户明确追加签名授权后，四个候选已通过标准构建器签署；343 项最终回归通过。四个最终签名包分别在独立临时实例完成验签、安装、Runtime 1.6.2 依赖锁定及 Managed Worker readiness。没有创建生产 submission，未声称真实出图或公开 Registry 验收完成。摘要及剩余客户端生产门禁见 `docs/ai2apps-image-capability-release-2026-09-11.md`。Cloud 查询仍只用授权 App-Dev Cookie；既有 Keychain 私钥仅由构建器用于签名，未导出。

本次追加 Host 修复：缺少 modelInstall 的兼容格式按专用版本有界安装映射检查，不再混用旧 discovery 范围；新兼容版本的 fallback 核对实际 Service 模型，历史包维持原有校验行为。未知未来版本继续拒绝。该修复必须纳入配套 Desktop。

- 四个目标：Z-Image Turbo 0.1.3、Ideogram 4 0.1.2、Qwen Image 0.1.2、FLUX.2 Klein 0.1.4；尚未签署/发布，旧 dist 保留不变。
- Host 接受 editing-only 合同；Turbo/Ideogram 编辑禁用策略同时作用模型目录和 JSON 调用；Qwen Edit 与生成版分开；参考图数量在合同、前端和 Host 调用前校验；ACPF 分离 image.generation/image.edit，并修正 Qwen Service 验证能力名。
- 模型权重 revision/distribution 不变，无新权重下载要求。新 Qwen editing-only 声明要求包含本次校验修复的 Desktop 客户端；旧客户端不得被宣称已兼容。
- 发布使用本次用户授权的 App-Dev Cookie；签名仍需标准构建器的既有 Publisher 私钥，当前未读取 Keychain。待测试、签名安装及生产发布验收。
- 回归：核心 129 项通过；扩展合同/模型发现 186 项通过（Metal 导入需要非沙箱测试环境）。Node 语法检查通过。没有新签名制品或生产 submission。
- 发布门禁：旧 Host 拒绝 editing-only 合同；Qwen 必须先有兼容 Desktop 发布或可靠的客户端版本门禁。当前公共 ai2apps 版本约束不能区分该修复，不发布虚假 generation 能力来绕过。Cloud 尚不接受 modelInstall 时，其他新版本也需要随 Desktop 下发有界安装映射。签名权限与 Cloud Cookie 登录权限分开处理。


发布负责人必须逐项执行：

1. 匿名读取生产 `stable.json`，确认本文件基线 Build 仍是当前生产 Build；不一致时先更新
   基线和回执引用。
2. 为每个 `ready`/`blocked` 项明确决定：纳入、修复后纳入或 `deferred`。不得默默遗漏。
3. `blocked` 项不得进入候选，除非阻塞已解除、证据已补齐并改为 `ready`。
4. 将每个拟纳入项映射到具体源码文件、测试、配置/迁移、用户可见 Release notes 和回退
   方式。
5. 对上一版最终 DMG 的实际内嵌内容与候选 staging App 做内容差异核对；不要只比较 Git
   commit，尤其不能把未跟踪文件当作可重现来源。
6. 正式发布要求所有拟纳入文件已提交并推送，工作树满足 Desktop Runbook 的 clean-tree
   门禁。任何 dirty-tree 例外都必须重新获得明确批准。
7. 在 Release notes 与 Build 回执中逐项引用本文件的 NXR ID。

如果候选构建包含本文件未登记的用户可见或安全相关差异，停止构建，先补登记和测试证据。

## 6. 发布完成后的归档与重置

当新 Build 完成端到端验收后：

1. 将所有实际纳入项的 NXR ID、说明、测试和例外复制到该 Build 的不可变发布回执；
2. 把对应项状态改为 `included`，填写纳入 Build；
3. 保留 `deferred` 项并更新目标版本，不得丢失；
4. 将本文件生产基线更新为新 Build、生产清单摘要和新回执；
5. 从“下一版候选工作”移走已经归档的 `included` 详情，只保留新基线之后的开放项；历史
   事实以 Build 回执为准；
6. 重新匿名核对 `stable.json`，确认台账基线与生产一致。

台账更新本身必须和导致状态变化的源码或发布回执一起进入版本控制，不能只存在于聊天记录。

<!-- Checkpoint migration status: HF DS4.1F / MS Qwen SDK uploads completed, remote integrity gates pending. User explicitly confirmed HF Avdpro / MS ai2apps. HF Qwen metadata fix committed successfully at a1de2bbd1727b3c46162a0f8bd426316e6f8dd37; approval block resolved. MS DS4.1F remains uploading. See docs/chat-checkpoint-migration-2026-09-14.md. -->

### NXR-VIDEO-STUDIO-READY-PROVIDER：优先恢复已安装的视频模型（ready）

- 状态：`ready`
- 类型：Video Studio、ACPF、模型选择恢复。
- 用户可见结果：设备已经安装并验证 OpenVDN DMD8 等视频模型时，重新打开 Video Studio 会
  直接恢复一个已就绪的模型，不再因为 ACPF 推荐的高规格 H3 8-bit 尚未下载而显示“当前设备
  没有经过此 App 验证的本地配置方案”并再次要求配置。
- 根因与修正：Provider 目录和共享 Checkpoint 均正常；OpenVDN DMD8 及其 H3 4-bit 基座已经
  被 Worker 标为 `ready`。旧的首次选择逻辑只检查推荐模型 ID 是否存在，未检查它是否就绪，
  因而在 128 GiB 设备上优先选中尚未安装的 H3 8-bit。现在仅在推荐项已就绪时优先选它；否则
  先选任一已就绪模型，再回退到推荐或目录首项，以保留无模型设备进入安装流程的行为。用户
  选定及 ACPF 安装完成后的模型 ID 会写入 Video Studio Shell 状态；刷新或重开后仍可用时直接
  恢复；初始化空 Mini-App 草稿也不再覆盖刚恢复的模型 ID，例如不会把已选择的 OpenVDN
  DMD8 降回仅作为依赖安装的 H3 4-bit 基座。
- 需要进入 App 的文件：`ai2apps/web/static/js/video_studio.js`、
  `tests/test_ai2apps_video_studio.py`。
- 纳入 Build：待定。

<!-- HF Qwen 73 / DS 172 files checked: only Hub-added .gitattributes differs, all other SHA256/size values match. Normalize metadata before distribution signing; not a completed publication gate. -->

### NXR-SHARED-CHECKPOINT-REUSE：跨实例共享 checkpoint 复用修正（runtime_published）

- 2026-09-18：App-Dev 安装 DeepSeek V4.1 Flash 时错误重新下载 475.27GB。根因是首次整理只扫描
  实例 cache，漏掉仓库 `artifacts/chat-checkpoint-migration-20260914` 的已验证 SSD checkpoint；
  该快照也没有 `.ai2apps/distribution.json`，因此安装器无法识别。现已通过正式本地导入工具对
  171 个分发文件完成签名清单和 SHA-256 校验，并以 APFS clone/hardlink 形式发布到机器共享
  `checkpoint-cache-v1`；App-Dev Worker 目录与共享快照 inode 一致，不占用第二份 475GB。
- 修正大快照复用：共享 cache 检查和 Worker 物化移出 asyncio 事件循环；取消 provisioning 会
  同时取消底层 runner，避免界面取消后继续下载；首次完整 SHA 后写入只读 inode/device/size/
  mtime 收据，后续快速复核，任一身份变化都会退回完整 SHA。安装界面在复核阶段显示
  “Checking shared checkpoint cache”，不再把本地扫描误报为网络下载。
- 修正 SSD 完整性边界：`.gitattributes` 是 Hub 仓库元数据，Checkpoint Distribution 明确不
  分发；旧 `ssd-checkpoint.json` 即使记录它，Runtime 也不再把它当作推理载荷。其它声明文件、
  metadata digest、专家清单和模型布局检查保持严格。
- 2026-09-18 Runtime 1.7.1 候选完成：104 项 Runtime/Checkpoint/Installer/Provider 定向回归通过；
  Apple 公证请求 `9c90a4aa-728b-4863-8a42-11c38cb60636` Accepted，staple/Gatekeeper 通过；
  最终 Publisher 签名 Package SHA-256 为
  `df6f95e37a8e48073597b2aa6a5d2aa86c4e4be2f872c34a989d666290f19982`。精确签名制品在隔离实例
  安装成功，DS4.1 Worker 达到 running；1.7.1 内置 CPython 对真实共享 DS4.1 快照完成检查，
  `.gitattributes` 缺失时仍正确通过全部推理载荷、metadata digest、专家清单和布局门禁。
- App-Dev 与 Test 已通过规定脚本重建、release-bundle 与 deep/strict 签名验证；App-Dev 已以
  `app-dev` 实例重启，原生标题为 `AI2Apps-App-Dev: HunterPoints 127.0.0.1:53678`。ModelScope
  不可变 revision `75866a48aa1c36cd1f2c646feeda98a449b2c77e` 的大小/SHA、四段匿名
  `200 + Content-Range` 字节和完整匿名下载均匹配。GitHub 同一草稿的前两次精确资产上传在服务端
  保存阶段返回 HTTP 500，失败 starter 已清理；第三次上传成功并发布为
  `package-runtime-omlx-v1.7.1`，GitHub 摘要、四段 HTTP 206 和完整匿名下载均匹配。详见
  `docs/ai2apps-mlx-runtime-1.7.1-shared-checkpoint-release.md`。
- Runtime 1.7.1 已正式发布：submission `13bd374a-066c-48f3-988b-fce01504cebd`、review
  `8d983fe2-c232-493d-9eab-308e299b45eb`；GitHub 与 ModelScope 两个不可变 Source 均完成
  分片验证和激活。最终 Repository metadata 为 157，snapshot digest 为
  `92b35944484e26cfd4786bfaf88940a1f9f0648450b5e6c6a04acf69f4ef8252`；全新匿名客户端验证
  Package 精确字节和 Publisher envelope 均与本地最终制品一致。App-Dev Discover 已显示
  `Local 1.7.0 / Cloud 1.7.1` 和 Upgrade 入口。
- 纳入 Build：Runtime 1.7.1 及下一版 Desktop；无需模型 Package 或 Checkpoint 重发。Runtime
  发布闭环完成；下一版 Desktop 的正式纳入和升级验收由 Desktop Release 流程继续跟踪。
- 2026-09-18 App-Dev 实机 Retry 暴露后续权限边界：共享 Distribution 已正确复用，但 Worker
  视图整体只读，SSD 激活阶段仍需写入 Package-owned Scope profile 与 `ai2apps-model.json`，因而在
  `.ai2apps/scope-assets` 返回 `EACCES`。安装器现仅在元数据提交事务期间临时开放模型根目录与
  `.ai2apps` 的 owner-write；权重、专家和其它 payload 文件始终只读，提交完成或异常退出都会恢复
  原始目录权限，新生成的 Scope/manifest 文件在只读视图内也恢复为只读。新增 DS4.1 只读
  Distribution 激活回归；Checkpoint/Runtime 56 项通过，扩展安装套件 80 项中 78 项通过，另两项为
  既有 Qwen 测试仍断言已被 SSD Checkpoint 替换的旧仓库身份，与本修正无关。App-Dev 已对现有
  475.27GB 共享快照完成原地激活，没有重新下载；生成的 manifest、Scope asset 与模型目录均恢复
  只读。Local 重启后真实本地 DeepSeek V4.1 对话对 `20+20` 返回 `40`，不再出现
  `SSD checkpoint is not activated`。该激活逻辑属于 Desktop Local，而非安装的 Runtime；Runtime
  1.7.1 无需重发，修正必须纳入下一版 Desktop Build。

### NXR-ORNITH-FULL-SSD：Ornith SSD Full 专家注入修复（released_verified）

- App-Dev 实机发现 Ornith 0.1.2 的默认 Full 分支关闭 Qwen3.6 外部专家策略，SSD backbone
  因缺少已拆出的 40 层三组专家张量而报告 `Missing 120 parameters`。Ornith 0.1.3 候选在 Full
  模式配置 256 专家 Flesh 注入；Runtime 1.7.2 候选让 Full/Flesh 使用规范 expert ID 0..255，
  不再错误要求只为缓存档位训练的 Top120 Scope profile 包含 Top256 排名，并同步修正文本
  Qwen3.6 Full 路径的无效零 tail 参数。
- 46 项 Runtime/Qwen3.6/Ornith/Package 定向回归通过。临时隔离 Worker 使用当前正式 SSD
  checkpoint 完成真实 Metal Full 加载和 30-token 响应，原 120 参数错误消失，最终答案为 `40`。
- Runtime 1.7.2 已完成 Apple 公证、staple、Gatekeeper、Publisher 签名和 Registry 发布；
  Ornith 0.1.3 也已签名并发布。Runtime 最终 Package 为 375527678 bytes，SHA-256
  `2ec01b8d5bd37b362d7b95fa98a7253d3f2251b0495d0c0599ac0be88240f501`。Cloud、ModelScope、
  GitHub 三源均已通过完整 SHA/大小/piece/Range 校验并激活，最终 Repository metadata v161。
  App-Dev 安装精确发布制品后复用了现有 Ornith checkpoint；Worker 元数据确认为默认 Full，
  真实 Chat 对 `20+20` 返回 `40`，原 120 参数缺失未复现。该修复已由独立 Runtime/模型
  Package 交付，不要求新 checkpoint 或 Desktop 重发。详见
  `docs/ai2apps-mlx-runtime-1.7.2-ornith-full-ssd-candidate.md` 与
  `artifacts/runtime-1.7.2/build-receipt.json`。

- Experimental L2 prefetch: L2_RECYCLE_CANCELLED reclaims cancelled unread reservations while retaining the 64 actual reads/token cap. Scheduler unit checks pass; model performance validation pending. Production defaults unchanged.

- Experimental L2 credit-limited notices merge hit/miss metadata readbacks and spend only saved boundaries on early notifications; all-hit host IDs are masked. Exact model and timing checks running; production Runtime unchanged.

- L2 credit notification prototype adds bounded adjacent-layer batching; strict32-token model validation in progress. Production unchanged.

- Experimental L2 startup notification can replace duplicated first-layer cache-hit readback; strict exact-routing/parity and boundary-count gates added. Model validation running; production unchanged.

- L2 experimental entry now resolves its resident predictor relative to its source location to support frozen acceptance snapshots. Independent test running against isolated copies; no production activation.

- L2 isolated independent acceptance completed:24 unseen conversations,70.3071% timely miss coverage, cap64 reads/token,62.971GB sampled peak, exact main output parity, counted route readbacks/notifications never exceed baseline per token; pooled TPS+7.44%, waste82.03MB/token, total expert SSD reads+7.84%. Confidence interval crosses70%; see `docs/dsv41f-l2-independent-acceptance-2026-09-16.md`. Experimental legacy-path result only; production miss-resume/vision/Package integration remains unaccepted and defaults unchanged. Prior “running” bullets above are historical status, superseded by this result.

- L2 follow-up research in progress: residual-depth predictor trainer and serial two-seed ablation added, with identity initialization and train/validation family separation. Scope and remaining cross-layer L2/SSD scheduling work recorded in `docs/dsv41f-l2-next-experiments-2026-09-16.md`; no Runtime defaults or Package activation.

- L2 cross-layer research prototype (2026-09-17): isolated READY snapshots, bounded staging reads, GPU staging-use flags, proposals piggybacked on existing window completion, conditional invalid-suffix notifications, and optional host/command-buffer timing diagnostics added under `resume_probe/`. A copied diagnostic runner now includes lazy KV roots in its existing completion evaluation and supports fixed input token sequences. Early incorrect smoke runs are retained and excluded; corrected Block6 matches legacy golden logits for8decode steps. The27-case development matrix is running; no production activation or broad correctness/performance claim yet. Residual-depth results documented in `docs/dsv41f-l2-depth-ablation-2026-09-17.md` show no repeatable gain.

- L2 three-direction development experiments completed (2026-09-17, experimental/deferred; supersedes earlier running status): all 21 optimized-window cases completed; exact Top6 legacy-logit gates and <65GB sampled footprint passed. Residual depth has no repeatable gain; cross-layer L2 candidates remain slower than packet control. Deadline lead1 improved the separate paired development probe by ~2.3%, not a production claim. Lazy prefill KV-root fix stays in isolated runner; no production Runtime/default/Package activation. See `docs/dsv41f-l2-three-direction-results-2026-09-17.md`; long-context and independent acceptance remain required before release.

- L2 window regression correction (2026-09-17, in_progress, isolated experiment): restore previous packet/window admission and first-miss native-tail fallback in resume_probe; packet fallback retains L2 READY consumption and fused prediction delivery. Add discarded-suffix counters. Performance/parity gates pending; no production activation.

- L2 window regression correction completed in isolated experiment (2026-09-17; supersedes in_progress above): restored old admission and first-miss packet tail; normal/all-miss paired full TPS +1.33%/−0.35% (equivalent within observed variation), exact golden logits, zero discarded suffix in low-hit runs. Same-token all-hit 2/4-layer execution 86.46/81.64ms vs packet92.02ms; zero SSD, exact output. Four predictor transition gates passed (rank64 dtype retry recorded). Production/default Runtime unchanged; long-context L2/Burst integration remains deferred. See `docs/dsv41f-l2-window-recovery-2026-09-17.md`.

- Always-resume executor correction (2026-09-17, in_progress, experimental): user requires no packet admission/fallback. Added explicit resume mode that uses GPU guarded continuation on every segment and resumes current MoE after every miss; GPU router-visit instrumentation added. Correctness and all-miss performance not yet accepted; previous adaptive fallback result is not evidence for this requirement. No production activation.

- Always-resume follow-up (2026-09-17; semantics verified, performance not accepted, experimental/deferred): full40 controller has no packet admission/fallback; normal4token142MISS+4DONE and all-miss2token80MISS+2DONE, exact logits/KV/Engram, GPU each layer once. CPU still reconstructs skipped suffixes: full40 no-diagnostic0.580TPS, not releasable. Added isolated v3 backend integer-key/resource-declaration cache and async guarded submit; 18-case gates pass, speed goal still fails. Docs `dsv41f-always-resume-2026-09-17.md` supersede interpreting adaptive recovery as fulfillment. No production Runtime/Package switch.

- Forward-only ICB continuation (2026-09-17, in_progress, isolated experiment): token graph/Metal commands are captured once, real Router misses patch only the current six slot indices and replay the remaining captured groups. Removes suffix rebuilding and rollback snapshots; adds token-scoped Residency Sets, pooled ICB/parameter storage, exact replay ranges, and deferred allocation retirement compatible with normal MLX donation. Natural four-token logits and full state match packet reference exactly; all-miss diagnostics show one graph and one GPU execution per layer, zero packet fallback, 40 MISS + DONE per token, <65GB sampled peak. Frozen 32-token ABBA performance gate is running; no production Runtime, Package or default activation. See `artifacts/dsv41-resume-replay-20260917/`.

- Captured continuation outcome (2026-09-17; supersedes in_progress above): retained isolated v12 after full-state parity and Metal validation smoke. No repeated suffix construction, no packet fallback, exact per-layer execution and <65GB peak. Frozen ABBA still fails non-regression: all-miss 2.00977 vs 2.05591 TPS (-2.24%); natural 3.95339 vs 4.84065 TPS (-18.33%). Later native-prefix/event/residency/retirement/submission variants did not establish a passing gate and are archived outside the retained implementation. No production/default switch. Report: `docs/dsv41f-captured-continuation-2026-09-17.md`; retained binary/source receipt: `artifacts/dsv41-resume-replay-20260917/retained-receipt.json`.


### NXR-VOICE-SHARED-OUTPUT-20260923 — ready

- Voice Studio: one host-owned Quick Read-style Preview & Output across all built-in and Package Mini-Apps.
- Common owner-scoped 20-result Artifact history, stable selection across Mini-App changes, shared audio export/drag; video and JSON outputs supported.
- Package transcription and speaker replacement publish through the host; separation WAVs and native ZIP Save As retained.
- Private Line caches and character reference files remain outside output retention. Contract fixed in the Studio Mini-App Package specification.
- Validation: 54 focused pytest checks passed, both Node scope/bridge suites passed, three JavaScript syntax checks and git diff whitespace check passed. Native UI smoke is pending: App-Dev currently holds a completed unsaved transcript, so it was not restarted/refreshed. Source/API refresh requires app-dev Local restart; no Runtime publication required.


### NXR-TRANSCRIPT-EXPORT-EDIT-20260923 — ready

- Package text exports in Voice Studio go through a mount-authorized host Artifact endpoint and native Shell Save As, including JSON, Markdown and SRT.
- Transcript segments support text and speaker correction. Draft save/restore includes results; exports use current edits. Text corrections invalidate old word alignment while preserving segment times.
- Host draft/export payloads bounded to 4 MiB; filename/media types allowlisted and JSON validated. Shared Preview & Output receives exported artifacts.
- Verification: 29 focused pytest checks passed; Node transcript-edit and host-bridge suites passed; JavaScript syntax and diff whitespace checks passed. Native Save As dialog smoke remains pending. Existing App-Dev result is kept intact; activation requires Local restart and refresh after preserving that result.


### NXR-MEDIA-VOICE-MINIAPP-ORDER-20260923 — ready

- Reordered the Media Voice Studio Suite manifest and placement priorities: Voice and Background Separation first, Detailed Transcription second, remaining Mini-Apps unchanged.
- Validation: parsed app.yaml and verified declaration/placement order for Voice Studio and Video Studio. App registration changes require app-dev Local restart; no Runtime rebuild or publication.


### NXR-QUICK-READ-CHARACTERS-20260923 — ready

- Quick Read Actor selector includes Characters, uses the selected character's bound model, and persists selection in its existing draft.
- Backend resolves the owner-scoped profile; reference clones use validated private reference materials and multipart speech, designed voices use saved instructions. No project is created; outputs retain the shared Studio history/export/drag flow.
- Verification: 12 ReadAloud API tests and the Node scope/Quick Read suite passed, including designed voice, clone reference multipart, bound-model override and cross-owner rejection; JavaScript syntax and whitespace checks passed. Native UI generation was not run. Requires app-dev Local restart for API changes; no Runtime rebuild.


### NXR-VOICE-SENTENCE-CHUNKING-20260923 — ready

- Shared bounded speech invocation for Quick Read (including Characters), Character design/clone previews, and Audiobook Lines/full-dialogue inputs.
- Deterministic punctuation/word-aware splitting without rewriting; 300 weighted units (CJK weight 3) per request, sequential generation with identical voice/expression/reference settings, single merged WAV output. Partial failures/cancellations never publish intermediate audio.
- Long-Line cache signature includes the segmentation policy so old long-form audio is regenerated; short Line caches remain compatible.
- Verification: 65 tests passed across sentence splitting, WAV concatenation/order, configuration/reference preservation, failure/cancellation, ReadAloud API/tasks and Character training; git diff whitespace check passed. Real-model long-text listening validation not performed. Source/API Local restart required, no Runtime release.


### NXR-VIDEO-COMPOSER-LARGE-IMPORT-20260923 — ready

- Video Composer keeps the authorized AceFox native-path fast path, but no longer falls back to Gallery's 64 MiB general import when that path is unavailable. A dedicated AppInstance-scoped endpoint streams browser-selected image, video, or audio media into private Composer storage and returns only the existing opaque source ID.
- The fallback is bounded at 20 GiB, writes in 1 MiB chunks with private permissions, removes partial/invalid files, and leaves Gallery's global 64 MiB policy unchanged. Imported source paths remain absent from API responses and saved Composer project documents.
- Validation: Video Studio and Composer targeted regression `17/17` passed; JavaScript syntax, Ruff, and diff whitespace checks passed. App-Dev Local was restarted onto port `55001`, the Shell reconnected, and Video Composer reopened without the stale 64 MiB error. Native selection of the user's original large file was not repeated because that file was not available to the test harness.


### NXR-VIDEO-COMPOSER-TIMELINE-ZOOM-20260923 — ready

- Video Composer timeline zoom now ranges from 2 to 120 pixels per second instead of stopping at 18. The ruler and grid automatically use 1-second cells at normal zoom, then 2-, 5-, and 10-second cells as the timeline is zoomed out.
- The ruler fills the entire visible timeline rather than stopping shortly after the last clip. Short clips use a smaller visual minimum at overview zoom, and the selected zoom level persists as a Shell display preference.
- Validation: native App-Dev checks confirmed 10-second cells at 2 px/s, 5-second cells at 6 px/s, and the 2-second scale tier at 12 px/s. Video Studio and Composer regression `17/17`, JavaScript syntax, both localization JSON parses, and diff whitespace checks passed.


### NXR-VIDEO-COMPOSER-OUTPUT-GEOMETRY-20260923 — ready

- Video Composer preview now preserves the configured canvas aspect ratio for both landscape and portrait projects instead of flattening portrait canvases against a fixed height cap.
- Export uses the same centered `contain` geometry as the browser preview when a clip's visual box and source media have different aspect ratios, including masks and animated position/size states.
- Validation: Video Studio and Composer regression `18/18`, JavaScript syntax, Ruff and diff whitespace checks passed. Native App-Dev force-refresh preserved the existing 48.83-second draft and confirmed the 1080p 9:16 preview is a true portrait canvas; the project was restored to its original 720p 16:9 setting afterward.


### NXR-VIDEO-SUBTITLE-SHARED-OUTPUT-20260923 — completed

- Video Subtitles and Translation still returns its ZIP bundle, while a requested burn-in MP4 is also persisted as a Video Studio Run/Artifact and sent to the host Preview & Output player.
- Package Mini-Apps no longer inherit Composer/Extract Audio output mode from the previously selected built-in Mini-App; unrelated generation history is hidden while a Package output is active.
- Video Studio restores the latest successful Package video Artifact after a page or Local restart, scoped to the selected Mini-App.
- Subtitle burn-in now runs through `asyncio.to_thread`, so PyAV/libx264 frame rendering and encoding no longer block Local health checks or trigger the Helper's three-strike automatic restart.
- Video subtitles now request word timestamps while retaining the punctuated ASR segment text. Cue splitting prefers complete sentence endings, then clause punctuation near the four-second/42-unit target, and only uses a roughly 5.6-second/52-unit hard fallback when no natural boundary exists. Chinese translation explicitly preserves punctuation and restores missing sentence-ending marks as full-width `。！？`. Burn-in uses measured pixel widths, at most two lines, adaptive font sizing, long-token splitting, and horizontal/bottom safe margins so captions stay inside the video frame.
- When the ASR segment itself contains no punctuation, the subtitle workflow now invokes the installed `ai2apps.model.punctuation-restorer/default` CT-Transformer before cue splitting. This supplies semantic sentence boundaries instead of asking the length limiter or translator to infer them after the text has already been cut.
- Verified in App-Dev with `IceCreamNoST.mp4`: the persisted `IceCreamNoST-subtitled.mp4` reopened in the host player with visibly burned-in English subtitles; 29 focused tests, Ruff, and JavaScript syntax checks pass.
- Async burn-in, punctuation restoration, cue segmentation, word-timestamp timing, translation punctuation, and caption-boundary regression coverage brings the focused suite to 42 passing tests.


### NXR-DETAILED-TRANSCRIPTION-LANGUAGE-NORMALIZATION-20260923 — in_progress

- Voice Studio Detailed Transcription failed after successful ASR when Qwen3 ASR returned the full
  language name `English`; the 0.1.2 pipeline forwarded it to Qwen3 ForcedAligner, which accepts a
  language code such as `en` and raised `UnsupportedAlignmentLanguageError`.
- Package 0.1.3 normalizes detected language names and locale tags to supported alignment codes and
  also accepts canonical full names at the aligner boundary. The experimental baseline and formal
  Package source remain byte-aligned for the changed runtime modules; the Desktop legacy Discover,
  profile and install mappings are version-bounded through 0.1.3.
- Validation so far: all 61 MLX WhisperX tests and all 75 Package/provisioning lifecycle tests
  passed, including the live failure shape (`English` from ASR before forced alignment); Ruff,
  formal/experimental runtime-source equality and diff whitespace checks passed. The registered
  Publisher signed 0.1.3 production artifact is 31,382 bytes at SHA-256
  `44ab6c4ab6d9b9ed9fa6c27186edbf06750680e34bba1f70acb66cc9380999c2`; Cloud submission
  `4a4cb7c0-dcfd-4a33-92b8-488bb09bdc6f` is published at Repository Snapshot 193, and anonymous
  download verified exact artifact bytes and envelope JSON.
- App-Dev upgraded to 0.1.3, then correctly requested the missing Compact checkpoint. The Models
  license challenge was created, but its dynamically generated Tailwind `z-[10000]` class was not
  present in the built CSS, leaving the NVIDIA Sortformer confirmation behind the still-open model
  dialog while that dialog displayed `Starting…`. The dashboard now assigns the challenge overlay
  an explicit DOM z-index and has a source regression assertion. License acceptance and the final
  real App-Dev transcription retry remain pending user action.
- Requires Package 0.1.3 delivery plus the next Desktop Build for its version-bounded discovery map;
  no Runtime rebuild or checkpoint redistribution is required.


### NXR-DETAILED-TRANSCRIPTION-PUNCTUATION-PRESERVATION-20260923 — ready

- Root cause: Qwen3-ASR already returned native punctuation and casing, but Qwen3 ForcedAligner
  rebuilt every `Segment.text` from timestamp-bearing lexical units. Punctuation has no duration and
  was absent from those units, so alignment replaced values such as `Come on, Joey!` with
  `come on joey` before subtitle segmentation and translation.
- Package 0.1.4 keeps the ASR transcript as the authoritative display text while continuing to use
  forced alignment for `words[].start/end` and segment timing. The previous hallucination safeguard
  remains active only when normalized aligned-text coverage falls below 65 percent; punctuation,
  whitespace and casing differences alone never rewrite the transcript.
- English and Chinese punctuation/casing regression coverage was added. Formal Package and
  experimental aligner sources are byte-identical; 185 pipeline, Package, provisioning, Worker and
  Studio tests pass, as do Ruff and diff-whitespace checks. Runtime and checkpoint distributions are
  unchanged.
- The 0.1.4 source now carries signed discovery/profile/install metadata; the production artifact
  uses the Runbook's bounded legacy `modelInstall` projection compatibility for current Cloud. The
  first attempt with a mismatched historical Keychain record was rejected before a submission was
  created. The existing registered key was then identified without exposing secret contents and used
  for the successful publication; no alternate Publisher, key, Package ID or version was created.
- Package 0.1.4 is published as submission `cb49e7b6-eb88-4597-9715-ade6dcb71688` in Repository
  Snapshot 194. Anonymous verification returned exact artifact bytes and exact envelope JSON for
  SHA-256 `6ab0086aaec6ef30e6aa56f0bb6568235a9beff0b97608b74c9bdd64cab81bf8`.
- The real App-Dev media inference regression remains a separate acceptance step because it requires
  upgrading the installed Package and exercising the locally licensed checkpoints with user media.
  After restarting App-Dev Local to load the new Python module, Discover resolved the version-bounded
  install plan and no longer displayed the untrusted-plan error; 40 focused catalog/install fallback
  tests pass. No Runtime or checkpoint redistribution is required.


### NXR-VIDEO-SUBTITLE-OUTLINED-TEXT-20260923 — ready

- Video Studio burn-in subtitles no longer draw a translucent black rounded backdrop. Captions now
  use white glyphs with a scale-aware thick black outline, starting at 3 pixels and increasing with
  the selected font size.
- The existing two-line cap, adaptive font sizing, horizontal safe area and bottom safe area remain
  in force; wrapping measurements include the outline width so the stroke stays inside the frame.
- Validation: 37 Studio media-workflow and asynchronous capability-broker tests pass, including a
  pixel-level regression for white fill, black outline and unchanged backdrop; Ruff passes. This is
  Host Python code, so App-Dev requires a Local restart but no App or Runtime rebuild.
- Follow-up configuration is implemented for `ai2apps/media-voice-studio-suite 0.1.2`: the Video
  Subtitles Mini-App exposes Small, Standard, Large (default), and Extra Large font presets plus
  outline or translucent-box background styles. The mount-bound invocation passes only validated
  enums to the Host; layout jointly measures font size, outline width or box padding, wrapping and
  safe areas, and adaptively shrinks when needed rather than clipping or truncating the frame.
- Validation after adding the Package UI and broker contract: 79 focused media workflow, broker,
  Package, sandbox-document, test-candidate and Studio bridge tests pass; Ruff, JavaScript syntax and
  diff-whitespace checks pass. A further 10 Package-development-mount regressions passed after the
  production compatibility adjustment.
- Package 0.1.2 is published as submission `caa0b6b5-1ed4-42e8-b539-f048da3bd997` in Repository
  Snapshot 195. Anonymous verification returned exact artifact bytes and exact envelope JSON for
  SHA-256 `40d6425c1021b65c7de9c9584986ab4644ef68a661b6911c6e7a2ab198cbabe0` (32,164 bytes).
  The initial full package-metadata attempt exposed the production Cloud's missing nested
  `package.localizations` and `package.license` schema support and was rejected before submission;
  those values remain in the signed `app.yaml`/indexed `LICENSE`, and the Cloud requirements handoff
  now records the gap. The published outer manifest also uses the established
  `--omit-mini-app-catalog` compatibility form.
- App-Dev does not need this Package installed: its trusted Development Bundle source-mounts the
  repository Package directly with `distribution=development` and hot-refreshes its resources.
  Installed Dev/production environments use the published Package and must upgrade to 0.1.2 to see
  the new controls. No Runtime or checkpoint redistribution is required.
- Post-publication App-Dev smoke found that the Host frame's explicit FormData allowlist had not
  been extended for `subtitle_font_size` and `subtitle_background`; the frame therefore rejected
  the first new option as `Invalid or duplicate field` before reaching the API. Both names are now
  allowlisted, all three Studio templates use the `media-style-fields-v2` cache key, and a bridge
  regression verifies that both values cross the opaque Package boundary. The focused Host bridge,
  client, broker and Package suite passes 36/36. This is a Desktop Host correction; the already
  published Package 0.1.2 bytes are unchanged and do not require republishing.


### NXR-TRANSCRIPT-PRIMARY-FORMAT-20260923 — ready

- Detailed Transcription passes the selected JSON/Markdown/SRT primary format through the host bridge and validated invocation API. The saved shared-output Artifact matches that selection while the editor still receives structured JSON.
- Export button label tracks the selected format, including restored drafts. Existing JSON exports/history are preserved.
- Validation: 31 focused pytest checks passed, including all three output formats and structured editor payload preservation; Node host bridge and transcript editing checks, JavaScript syntax and git whitespace checks passed. Local restart required for API changes, no Runtime rebuild.


### NXR-VIDEO-AUDIO-TRANSLATION-MINIAPP-20260923 — ready

- Media Voice Studio Suite is advanced to source version 0.2.0 with a sixth Video Studio Mini-App, `Video Audio Translation`, for single-narrator/explainer videos. The user selects source/target languages and one already verified Voice Studio Character; Phase 1 deliberately does not diarize or map multiple speakers.
- The mount-bound Host Broker owner-scopes the Character catalog and exposes only safe identity/readiness fields. It transcribes and punctuates source speech, splits sentence-sized cues, translates them, synthesizes the selected Character through the shared bounded Voice Studio speech path, removes the source dialogue stem, preserves the Demucs background stem, and remuxes an MP4 into Video Studio's host-owned Generation result.
- The new ACPF profile installs/verifies only Detailed Transcription and MLX Demucs. Character-specific TTS remains bound to the user's existing Voice Studio preset and is validated at invocation time; no Character material, checkpoint path, Worker endpoint, Cookie, or browser storage crosses into the Package frame.
- Validation: the final combined suite has 116 focused Package, provisioning, Host bridge, client, media-workflow and capability-broker tests passing, including timeline mixing, single-Character dispatch, non-diarized transcription, background-stem selection, temporary original-voice cloning, ASR back-listening and MP4 publication contracts. Ruff, Python/JavaScript syntax and whitespace checks pass. The exact `app-dev` Helper Control channel restarted only App-Dev Local (the `dev` boot ID remained unchanged), and the live source-mounted Video Studio shows 10 Mini-Apps, opens Video Audio Translation, and loads the owner-scoped Character selector without the previous `Not Found` error.
- Package 0.2.0 is formally published as submission `a8f0664e-7729-4158-ae08-89518e4fd94f`, review `617ed92b-157d-4cab-9e63-84bf0c6c8c05`, in Repository metadata version 196. The 37,292-byte artifact SHA-256 is `78bb7f0e76bdead49ad9b873e161b820886efb2ba895a2151f93c4775f2efc02`. Anonymous Registry verification returned exact artifact bytes and exact envelope JSON. The Dev browser session was used only through the standard live publication script for this exact release; App-Dev Cookie/state was not read. See `docs/ai2apps-media-voice-studio-suite-0.2.0-release.md`.


### NXR-VIDEO-AUDIO-TRANSLATION-TIMELINE-FIT-20260924 — ready

- Video Audio Translation now measures every synthesized sentence against its original ASR start/end window. An overflowing sentence first receives one meaning-preserving concise-translation retry; if the selected Character model declares native speed control, the Host then regenerates at the bounded speed needed for that slot.
- Any remaining overflow is compressed to the exact slot with a phase-vocoder time stretch that preserves pitch. Mixing always starts each sentence at its own source timestamp and never serializes it behind the previous sentence, eliminating cumulative drift and chipmunk-style resampling.
- Validation: all 56 focused Studio media-workflow and capability-broker tests pass. New regressions cover concise-translation-before-speed ordering, exact independent clip windows, silence between cues and preservation of a 440 Hz pitch after 2x compression. Ruff passes. This is Host Python code and requires only an App-Dev Local restart, not an App or Runtime rebuild or Package publication.


### NXR-VIDEO-AUDIO-TRANSLATION-PROGRESS-20260924 — ready

- Video Audio Translation now reuses the authenticated Studio invocation/SSE progress channel used by Video Subtitles. Its six cards report audio extraction, narration transcription, text translation, per-sentence Character synthesis, background preservation and final muxing; completed cards show a checkmark and the active card shows its own phase percentage.
- Character synthesis advances by completed sentence count, while mixing and MP4 muxing publish separate late-stage updates. The Host retains aggregate progress for event ordering and terminal detection, with capability-specific phase ranges for the six-stage workflow. Failure marks only the active phase.
- The Host and Package static cache key advances to `pipeline-progress-v3`. Validation: 68 focused Broker, media-workflow, Host bridge, Mini-App client and Package tests pass; Ruff and both JavaScript syntax checks pass. App-Dev requires a Local restart plus refreshed Video Studio; no Runtime rebuild or Package publication is required for the source-mounted development instance.


### NXR-VIDEO-AUDIO-TRANSLATION-ASR-VERIFICATION-20260924 — ready

- Video Audio Translation adds an optional `ASR 回听校验` checkbox. Capability probing enables it only when the local Detailed Transcription ASR model is ready; otherwise it is unchecked and disabled, and the Host bridge accepts the new field only through the existing mount-bound allowlist.
- When enabled, every synthesized Character sentence is transcribed locally and compared with the intended translated text after punctuation/spacing normalization. A low-score or empty result is regenerated up to two times; after three rejected attempts the workflow stops with the sentence number and verification details instead of exporting silent or garbled narration. The acceptance threshold is `0.62` so ordinary ASR wording variation does not cause excessive rejection.
- Validation: 70 focused Broker, media-workflow, Host bridge, Mini-App client and Package tests pass, including a failed first synthesis followed by a successful ASR-verified retry. Ruff lint, Python/JavaScript syntax and whitespace checks pass. Host/Package cache keys advance to `dubbing-asr-v4`; App-Dev needs a Local restart and page refresh, with no Runtime rebuild or model Package publication.


### NXR-VIDEO-AUDIO-TRANSLATION-ORIGINAL-VOICE-20260924 — ready

- Video Audio Translation adds `原始音色 · 临时克隆` alongside saved Voice Studio Characters. Selecting it reveals a Host-filtered TTS model selector containing only executable single-reference voice-cloning providers; `安装更多模型…` restores the previous selection and invokes ACPF with `installMore` for the mount-declared optional `audio.voice_clone` capability.
- ASR back-listening now canonicalizes Chinese spoken numerals before similarity scoring, so equivalent forms such as `54.99` and `五十四点九九` no longer exhaust retries or fail an otherwise valid dubbing run.
- After transcription, the Host evaluates contiguous narration windows for duration proximity to ten seconds, speech density, audibility and clipping, then pairs the selected source WAV slice with exactly its ASR text. The reference remains request-scoped, is reused for each translated sentence, and is never written to Characters, Gallery or Package storage.
- The mount bridge exposes only a safe voice-clone model catalog and validated `voice_clone_model_id`; model paths, Worker endpoints and reference media remain Host-owned. Character mode is unchanged, and original-voice mode keeps the existing concise-translation, model-speed, pitch-preserving timeline fit and optional ASR back-listening stages.
- Validation: 116 focused provisioning, capability-broker, media-workflow, Host bridge and Package tests pass, including ten-second clear-window selection, model catalog filtering, Video Studio ACPF profile resolution, `installMore` forwarding and request-scoped reference synthesis without Character access. App-Dev needs a Local restart and page refresh; no Runtime rebuild or Package publication is required for the source-mounted development Package.


### NXR-VIDEO-SUBTITLE-TRANSLATION-COUNT-RECOVERY-20260923 — ready

- Video subtitle translation no longer rejects an entire run when the configured translation model merges or splits subtitle items in a JSON batch. The Host retains ownership of cue count and timing: a mismatched multi-item response is automatically retried by recursively dividing the batch, while a model-split single cue is safely rejoined before target-language punctuation restoration.
- Invalid non-string response structures and empty single-cue translations still fail closed. The recovery applies to both Video Subtitles and the single-narrator Video Audio Translation pipeline because they share the bounded Host translation path.
- Validation: all 109 focused Package, provisioning, Host bridge, client, media-workflow and capability-broker tests pass. New regressions cover a four-item batch returned as three items and a single cue returned as two fragments; Ruff and diff-whitespace checks pass. This is Host Python code and requires only an App-Dev Local restart, not an App or Runtime rebuild.


### NXR-STUDIO-MINIAPP-PIPELINE-PROGRESS-20260923 — ready

- Video Subtitles now reports real coarse pipeline progress for audio extraction, transcription, translation, subtitle layout and export. Completed cards show a checkmark; the current card shows a spinner and the Host-reported overall percentage; failures mark the active stage without falsely completing later stages.
- The immediate Studio Host creates an actor-, installation-, mount- and capability-bound invocation ID, subscribes to a no-store SSE stream, and forwards validated events through the existing private MessagePort. The opaque Package frame receives no Cookie, credential, mount-controlled URL or arbitrary EventSource access. Records are short-lived and bounded; navigation closes active streams.
- Live acceptance exposed three delivery defects: both the server stream and the Studio Host bridge treated a phase-level `completed` event as terminal after audio extraction, while the progress record retained only its newest event. Terminal detection at both layers now requires either failure or `completed` at 100%; the bridge regression explicitly keeps a 15% phase completion stream open. The record keeps a bounded 128-event replay window, every publication yields a scheduling point for StreamingResponse delivery, and audio decoding runs through `asyncio.to_thread` instead of blocking the Local event loop. The shared bridge asset cache key is advanced to `pipeline-progress-v2`, so later stages remain individually observable instead of all appearing complete when the final response arrives.
- Pipeline cards display `phasePercent` (0–100% within the active step) instead of the aggregate workflow percentage. The SSE event retains aggregate `percent` for ordering and terminal detection. Subtitle burn-in now reports throttled frame-level progress from the worker thread back to the event loop, so the layout/burn step advances continuously rather than appearing frozen at the former aggregate 75% marker. Package resources use the `pipeline-progress-v2` cache key.
- Validation: all 109 focused Package, provisioning, Host bridge, client, media-workflow and capability-broker tests pass, including SSE completion, invocation header binding, stage ordering and Package cache-key coverage. Ruff, Python/JavaScript syntax and diff-whitespace checks pass. The exact `app-dev` Helper Control channel restarted App-Dev only after the user's active 14:52 subtitle run completed; the `dev` boot ID remained unchanged. Live source-mount smoke opened the refreshed Video Subtitles Mini-App at the new App-Dev port with the five-stage Pipeline intact. No App or Runtime rebuild is required.


### NXR-QUICK-READ-ASR-CHECK-20260924 — ready

- Quick Read defaults to optional ASR back-listening for each bounded speech segment, including Character voices. Uses the video translation text normalization/similarity policy (0.62), maximum three total generation attempts.
- Keeps highest-scoring audio on verification exhaustion, continues subsequent segments, and persists warnings in the shared output Artifact metadata. ASR unavailability/errors warn and preserve generated speech; cancellation still propagates.
- Validation: 39 focused Python tests and Quick Read Node suite passed; API-to-ASR integration and final sentence-level retry changes separately rechecked (12 API + 13 chunking tests). Includes retries, best-result retention, continued subsequent generation, ASR error fallback and cancellation. Real-model listening not performed. App-dev Local restart required, no Runtime release.


### NXR-QUICK-READ-ASR-MODEL-UI-20260924 — ready

- Fixed Quick Read ASR checkbox alignment with scoped flex/checkbox sizing and separate help text.
- Checking ASR reveals a model selector with automatic/installed ASR choices and Install new model via speech-recognition ACPF. Selection persists in the Quick Read draft and is honored by the backend; unavailable explicit selections warn instead of silently switching.
- Validation: 12 ReadAloud API tests passed (explicit ASR choice over first available model), Node Quick Read/ACPF selection suite passed, JavaScript syntax and whitespace checks passed. Live UI not refreshed; API changes require app-dev Local restart, no Runtime rebuild.


### NXR-INDEXTTS-CLAUSE-CHUNKING-20260924：IndexTTS 长句分段

- 状态：`ready`。Host 统一 speech 调用对注册模型 ai2apps.model.indextts25/* 使用 120 加权字符预算（约 40 中文字），优先句号/逗号边界，逐段 ASR 校验与最多 3 次生成保持不变；其他模型仍为 300。
- Characters、Quick Read、Audiobook 共用此策略；受影响的长 Line 缓存指纹更新。无需修改或发布 Runtime，仅 Python Host 重启后生效。
- 调查：IndexTTS 引擎未设置固定 max_mel_tokens，vendored infer 按文本 token 动态计算；内部默认 120 文本 token 分段仍可能让截图长句整句执行。当前不能排除模型提前 EOS 或 ASR 误判；不宣称已完成真实音频质量验收。

- 验证：41 项 speech chunking / readaloud API / render tasks 测试通过；截图文本拆成 4 段且完整还原。未执行真实模型音频质量 A/B，需重启 App-Dev Local 后验收。

### NXR-INDEXTTS-EMPTY-AUDIO-RECOVERY-20260924：IndexTTS 无内容长音频细分恢复

- 状态：`ready`。IndexTTS 校验未通过且音频超过 10 秒、ASR 无有效文字或 PCM 接近静音时，减半该段文本预算再生成，最多细分两层；子段继续最多 3 次 ASR 校验生成，成功替换原空白段，失败回退原音频并警告、继续后文。未启用 ASR 时仅按音频静音检测恢复。
- 保留参考音频、语速和其他生成参数；递归请求和 ASR 请求使用不同 ID；非 IndexTTS 不变，Line 缓存策略版本更新。Host Python 修改，重启 Local 生效，无需 Runtime 发布。

- 验证：50 项相关回归通过（49 项初次全组，追加无 ASR/取消测试及缓存调整后 38 项 speech/tasks 复验）；覆盖 >10 秒边界、空 ASR/静音、非 IndexTTS 不拆、普通识别不匹配不拆、子段失败回退、深度上限、继续后文及请求 ID 隔离。未执行真实模型音频验收。

### NXR-AUDIOBOOK-INDEXTTS-ASR-20260924：Audiobook IndexTTS 校验及细分恢复

- 状态：`ready`（受下述工程 ASR 开关与选择控制）。单行与整段对话生成共用 IndexTTS ASR 校验、最多三次生成及超过 10 秒空白音频的两层细分恢复。使用已就绪 audio_stt 模型，通过后台调用链路；无 ASR 时保留静音恢复并警告。Quick Read 和 Audiobook 共用 ASR verifier。
- 警告随行音频私有缓存保留，单行 Artifact 和整段合并 Artifact 经宿主共用 Preview & Output 展示；合并警告标记 Line 序号。已有 IndexTTS 缓存策略升级，避免复用未经校验的旧音频。仅 Host 修改，重启 Local 生效。


### NXR-AUDIOBOOK-ASR-SETTINGS-20260924：Audiobook 工程 ASR 设置

- 状态：`ready`。工程新增默认开启的 ASR 开关与模型选择，含 ACPF 安装新模型入口；Schema 77 持久化设置，单行和整段渲染请求快照使用工程配置。关闭后不调用 ASR，IndexTTS 长静音恢复保留；指定模型不可用时警告而不偷偷切换。
- ASR 配置进入 Line 缓存指纹；警告保留于私有缓存并通过共用 Preview & Output 显示。需重启 App-Dev Local 执行数据库迁移并刷新页面，无需 Runtime 或 Suite Package 更新。

- 验证：52 项 ASR/生成/API 回归通过；后续设置开关与缓存回归通过，Node 测试覆盖工程 ASR 选择及安装回填，平台存储迁移测试清单更新至 77。未执行真实模型音频/UI 现场验收。

### NXR-AUDIOBOOK-ASR-FIELD-MAPPING-20260924：修复勾选后 ASR 模型菜单隐藏

- 状态：`ready`。项目 API 显式 camelCase 映射遗漏 asr_verification/asr_model_id，导致前端保存返回后丢失显示条件和已选模型。补齐 asrVerification/asrModelId 映射，覆盖新建、保存与重新读取工程的真实 API 回归。需重启 Local；无需额外数据库迁移或 Runtime 更新。

### NXR-QUICK-READ-SPEED-20260924：Quick Read 原生及保持音高变速

- 状态：`ready`。Quick Read 新增 0.5–2 倍速度输入，默认 1 倍并随草稿保存；后端按实际角色绑定模型判断原生速度能力，在支持范围内传 speed，否则在生成/ASR/合并完成后用已有 PyAV atempo 做保持音高的时间伸缩。试听、下载和共用输出历史使用同一份调整后音频，不重复变速；1 倍不处理。
- API 拒绝超范围/非有限速度；输出保持 PCM WAV 24kHz，保留 64 MiB 限制。Host 变更，重启 Local 并刷新页面生效，无需 Runtime/Package 发布。

- 验证：18 项 API/音频测试通过（新增速度请求影响旧计数断言，隔离后该项复验通过）；合成 440Hz 音频覆盖 0.5/0.75/1.25/2 倍，时长符合比例且音高保持；JS 语法和跨 Mini-App 输出选择测试通过。未做真实人声主观试听验收。

### NXR-CHECKPOINT-HF-CREDENTIAL-FALLBACK-20260924：默认 HF 凭据及下载源降级

- 补充修复：Helper 强制隔离 HF_HOME/HF_TOKEN_PATH，SDK 默认读取仍落到实例目录。Host 下载器现优先 SDK/App 凭据，缺省时仅在 Helper 隔离启动下只读用户 XDG_CACHE_HOME/huggingface/token（默认 ~/.cache/huggingface/token）。不修改环境、不复制凭据、不传入 Worker；异常/无效内容按缺凭据降级。58 项 acquisition/distribution 回归通过，新增隔离环境完整下载链路、优先级、只读及无效文件测试。需重启 Local，新请求生效；不打断当前 MS 下载。

- 状态：`ready`。Checkpoint acquisition 在显式 Token 缺省时使用 huggingface_hub.get_token 读取标准 HF 环境/本地配置，不读取浏览器 Cookie、不复制或输出 Token；仅传入 HF adapter。
- 源初始化缺凭据不再阻断其他源；探测不可用或传输失败继续现有备用源流程。脱敏、按 provider 去重的 Warning 随 download 进度传给 ACPF，以提示样式显示。所有源不可用仍失败；许可确认、Range 与分片/整文件哈希校验不变。
- 验证：52 项 checkpoint acquisition/distribution 测试通过，覆盖默认/显式 Token 优先级、缺 Token、HF 403、超时、全源失败、MS 不带 HF Authorization 及警告无 Token。JS 语法检查通过。未执行真实账户下载；需重启 App-Dev Local 并刷新界面，无需更新模型 Package。

### NXR-IMAGINE-FLUX4B-RECOMMENDATION-20260924

- 状态：`ready`。Imagine Studio image.generation 与 image.edit 在所有兼容的 16 GiB 及以上 Apple Silicon 默认推荐 FLUX.2 Klein 4B，不再限制到 24 GiB 以下；Z-Image Turbo 保留可选但不再推荐，9B 保留手动选择。无需 Package 发布，重启 Local 后新 ACPF 会话生效。
- 验证：Imagine Studio 14 项及 provisioning 原有 46 项测试通过；新增推荐测试覆盖 16/24/32/48/128/256 GiB 的生成和编辑场景。

### NXR-IMAGINE-MINI-APP-I18N-20260924

- 状态：`ready`（本轮完善现有中英文，其他系统语言仍回退英文，未宣称十语言全覆盖）。全部内置 Imagine Mini-App 共用翻译表；表情包工坊与商品摄影棚的引导、整组确认/进度、场景、光线、构图、占位符、风格开关统一使用翻译键，不再在模板里判断语言。
- 补齐共享 Output/Chat、画质、规划中/依赖状态、加载/错误提示、调整导出阶段和聊天工具标题。模型指令、用户草稿、参数与输出记录不因切换语言改写。静态前端刷新生效，无需 Runtime 或 Package 发布。
- 验证：中英文全部翻译键/占位符一致性、模板引用完整性、全部 Mini-App 元数据、双向语言切换及草稿保持测试；Sticker/Product 行为测试与 JS 语法检查通过。其他八种语言待确认扩展范围。

### NXR-IMAGINE-PORTRAIT-20260924：内置单人人像 Mini-App

- 状态：`ready`（实现与自动化回归完成；2026-09-26 用户确认 Imagine 新功能已验收，不重复付费生成）。新增 Portrait / 人像摄影棚，无需安装 Package；中英文支持，位于表情包工坊之后。复用 image_edit 模型筛选、Cloud 上传确认、Run/Artifact、共享 Output 与 Gallery。
- 三种模式：Photo-ID（背景色、衣着、模型能力约束的比例/尺寸，固定头肩构图且不应用全局视觉风格）、杂志封面（封面风格、取景、可选刊名）、生活写真（场景、光线、取景、姿势气氛）。提示官方证件合规、生成文字和身份保真的限制。
- 衣着 Custom 显示必填第二 Slot，严格用于服装参考，第一 Slot 必须有人物照。切回预设清除服装图，发送仅包含可见参考；Custom 筛除不支持双图的模型。独立草稿与参考恢复，生成时配置锁定，尺寸与生成指令分离。
- 验证：14 项 Imagine Studio API 回归及 Portrait、i18n、Sticker、Product Node 测试通过；覆盖模式指令隔离、双图顺序、隐藏参考不发送、人物必填、模型筛选、草稿、中英文、目录注册及持久化。JS 语法通过；未调用付费生成。需重启 App-Dev Local 并刷新页面（不要为部署中断现有下载），无需重建 App/发布模型 Package。

### NXR-IMAGINE-SUBMITTED-PROMPT-20260924

- Prompt 输入框默认高度从 180px 缩为 120px（约 2/3），保留纵向拖动调整；纯 CSS，刷新生效。

- 布局调整：Prompt 编辑区放入淡灰色 Generate 容器内部，位于生成说明/按钮行下方，移动端纵向排列；不改变提交和编辑逻辑。新增模板结构回归，Prompt 请求测试通过。刷新页面生效。

- 状态：`ready`。内置 Image AI Mini-App 的生成区增加中英文完整 Prompt 预览/编辑；随参数实时计算，手动编辑可恢复自动，参数变化清除覆盖（界面明确说明），空白/超过 32000 字符禁用生成。Adjust Image 为本地像素调整，不显示模型 Prompt。
- 编辑内容按 Mini-App 草稿保存，异步恢复参考图期间不丢失覆盖。Cloud/Local 都使用点击生成时的同一文本快照，Run input.submittedPrompt 记录原文；图片、尺寸等仍为独立请求字段。表情整组逐张按当前表情重组，沿用共享结果流程。
- 验证：新增 Node 测试覆盖自动更新、手动编辑/恢复、参数失效、中英文切换、长度限制、草稿数据及真实请求构造的 Cloud/Local 原文一致；原有 Portrait/i18n/Sticker/Product 回归和 API 测试。纯前端刷新生效，无需 Package/Runtime 更新，未调用付费生成。

### NXR-IMAGINE-OUTPUT-SLOT-DROP-20260924

- 状态：`ready`。Output 显式拖出当前成果 ID/实例及兼容 Gallery 的 URL；所有内置 Mini-App 的共用图片 Slot 接收成果，读取原图为 File 后进入既有 setReference 流程，含多参考槽、合影背景、Portrait Custom 衣着和 Adjust Image。无需先存 Gallery。
- 拒绝跨实例、未知成果、非同源/非历史图片内容 URL 和非支持图片 MIME；生成或调整导出期间不接收新拖入。保留原有本地文件、Gallery 素材拖入及 Gallery 拖出。此路径按本地上传图片处理，刷新后需重新选图。
- 验证：Node 遍历全部就绪内置 Mini-App 的每个图片 Slot；覆盖双向 Gallery 兼容、原生文件、跨实例/外部 URL/未知成果/404/错误 MIME、忙碌锁。Portrait 和 Prompt 请求回归通过，JS 语法及 diff 检查通过。纯前端刷新生效，未执行现场鼠标拖动验收。

### NXR-IMAGINE-EXTRACT-ITEMS-20260924

- 状态：`ready`（实现及自动测试完成；2026-09-26 用户确认 Imagine 新功能已验收，不重复付费生成）。内置提取物品 / Extract Items，单图输入、image_edit 能力、OpenAI 优先；支持整套穿着、衣服、上衣、裤子、裙子、连衣裙、鞋、包及必填描述的 Custom。中英文界面/帮助、草稿与 Prompt 联动编辑，生成时锁定输入。
- 默认生成去除人物/背景的白底独立物品参考图，整套衣着平铺于一张图；忽略共享视觉风格，明确 AI 重建非精确抠图、遮挡推测、无透明保证。复用 Run/Artifact、Output/Gallery 和图片 Slot 拖拽，可用于 Portrait Custom 衣着参考。
- 验证：14 项 Imagine API 回归通过；Extract Items、i18n、Product、Output 全 Slot、Prompt 请求 Node 测试通过。未调用付费生成。需重启 App-Dev Local 并刷新；无需 Package 发布或 App 重建。

### NXR-IMAGINE-TRY-ON-20260924

- 状态：`ready`（代码及自动测试完成；2026-09-26 用户确认 Imagine 新功能已验收，不重复付费生成）。新增内置 Try On / 试穿试用，两个必填图片 Slot，第一张仅作人物身份、第二张仅作物品。支持穿戴、使用、手持三种互动，原姿势/站/坐/行走/Custom 与原背景/白棚/街景/公园/室内/Custom；自定义描述必填。
- 筛选双参考 image_edit 模型，OpenAI 优先；忽略全局视觉风格保持原貌，明确非真实尺码/合身度保证。中英文界面/帮助、独立草稿、完整 Prompt 编辑、生成时输入锁定、共享 Run/Artifact/Output/Gallery，支持提取物品结果直接拖入。
- 验证：14 项 Imagine API 回归；Try On 双输入/模式/自定义校验/模型筛选/草稿/i18n/Cloud 请求图片顺序测试以及 i18n、全 Slot 拖入、Product、Extract Items 测试通过。未调用付费生成；重启 App-Dev Local 并刷新生效，无需 Package 发布或 App 重建。


### NXR-CHARACTER-ASR-INSTALL-20260926：角色参考克隆 ASR 空状态安装入口

- 状态：`ready`。Characters 参考克隆始终显示 ASR 模型菜单，不依赖模型/素材数量或自动转写开关。包含安装更多模型入口，调用 ACPF audio.speech_recognition 并清除旧模型限制，安装后刷新并选中可用模型；取消保留选择。
- 用户选择随草稿保存，并用于自动/单条/批量参考音频转写。沿用复选框对齐样式。Host HTML/JS 修改，App-Dev 刷新生效；截图中的 general Dev 需要纳入后续 Desktop 构建，非 Suite Package/Runtime 更新。
- 验证：Node 前端回归覆盖无模型时安装、回填选中、取消和自动选择；JS 语法检查通过。

### NXR-DEV-REBUILD-20260926：更新固定 Dev App

- 状态：`ready`。按用户要求通过 build-dev-app.sh 重建固定 AI2Apps-dev.app，沿用 patched AceFox 153 和既有 .venv/bin/omlx 开发入口；身份 com.ai2apps.desktop.dev、instance dev、Development=true、源码根保持不变。
- 旧 App 自动归档为 .build/archive/AI2Apps-dev-20260926-011755.app；只退出已确认的 dev Shell/Helper/Local，未复制或重置实例数据，未替换 App-Dev/Test/生产 App。
- 构建及 codesign --verify --deep --strict 通过。已启动新 App，Shell PID 48198、Local PID 48200，127.0.0.1:62593/health 返回 healthy。包含当前源码的角色 ASR 模型菜单修复；未发布 Desktop/Package/Runtime。

### NXR-CHARACTER-DESIGN-LABEL-20260926：创建方式设计生成汉化

- 状态：`ready`。Characters 创建方式按钮移除硬编码 Design，使用 readaloud.character.design 翻译键；简体中文显示“设计生成”，英语保持 Design。翻译 JSON 和模板检查通过；刷新页面生效，无需重建或 Runtime/Package 更新。


### NXR-VOICE-DESIGN-CONFIGURE-20260926：修复设计模型配置入口能力错配

- 状态：`ready`。configureDesignModel 从 audio.speech_generation 改为 audio.voice_design，保留所选模型 ID 与 voice_design 操作约束；避免 VoxCPM2 被普通 TTS 候选列表过滤后误报 unsupported。声音设计 Profile 补入 Qwen3 VoiceDesign 5-bit（非默认推荐），继续优先 VoxCPM2。
- 验证：前端回归断言配置按钮能力 ID，Profile 回归覆盖三种设计模型；Host JS 与 Profile 修改，重启 Local 并刷新生效，无需 Runtime/Suite Package 发布。

### NXR-VIDEO-MODEL-RECOMMENDED-STEPS-20260926：按视频模型自动配置采样步数

- 状态：`ready`。Video Studio Provider 能力响应把签名模型元数据中的 `recommended_steps` 合并到有效 `videoCapabilities.defaults.steps`；切换视频模型或自动选择新的可用模型时，采样步数随模型推荐值更新，不再沿用固定的 20。
- 当前 MiniMax H3 Package 的 LightX2V 4-step、LightX2V 8-step、OpenVDN DMD 8-step、OpenVDN Stage-B 50-step 会分别自动配置为 4、8、8、50；未声明推荐值且能力中也未声明默认步数的标准 H3 等模型统一使用 20。普通刷新和草稿恢复不覆盖用户已保存的手动调整。
- Host Python/Video Studio JavaScript 修改；重启 Local 并刷新页面生效，无需更新 H3 Model Package 或 Runtime。

### NXR-VIDEO-STUDIO-TOASTS-20260926：提示信息悬浮与自动消失

- 状态：`ready`。Video Studio 的成功和错误提示改为固定悬浮 Toast，不再占据文档流或把三栏工作区向下挤动；保留关闭按钮和淡入淡出效果。
- 成功/普通提示显示 4.5 秒，错误提示显示 12 秒；新提示会取消旧计时器，页面卸载时清理计时器。错误使用 assertive `alert`，普通提示使用 polite `status`。纯 HTML/CSS/JavaScript 修改，刷新页面生效，无需重启 Local、更新 Package 或 Runtime。

### NXR-VIDEO-MULTIPART-UPLOAD-TYPE-20261001：修复图生视频素材被忽略

- 状态：`ready`。视频生成 Host 的原始 multipart 解析改为识别 Starlette 实际返回的 `UploadFile` 类型，避免 FastAPI 子类判断把 `first_frame`、`last_frame` 和参考素材静默丢弃后误报 `Multipart part is missing`。
- 新增真实 ASGI multipart 回归，覆盖 JSON `request` 字段与 `first_frame` 文件名、内容和 MIME 类型。底层 Host Python 修改，无需更新模型 Package。
- App-Dev 部署纠正（2026-10-01）：首次只重启 Local 后仍复现，因为 `omlx/` 属于 App-Dev 内嵌 Runtime，不在热挂载的 `ai2apps/` 源码范围；随后仅停止固定 `app-dev` 的 Local、Helper 和 Shell，使用 `build-app-dev-environment.sh` 重建固定 App，旧版归档为 `AI2Apps-app-dev-20261001-070818.app`。已确认新包内 `omlx/server.py` 使用 Starlette `UploadFile`，`verify-release-app.sh` 和 `codesign --verify --deep --strict` 通过，新实例以 Build 2239、端口 55230 启动。后续 `omlx/` 修改必须重建 App-Dev，不能只重启 Local。

### NXR-MINIMAX-H3-MULTIPART-BOOLEAN-20261001：图生视频 fast 布尔值兼容

- 状态：`published_pending_appdev_validation`。MiniMax H3 Model Package 适配器接受 Worker multipart 协议的规范文本布尔值 `"true"` / `"false"`，使带首尾帧或参考素材的 H3 任务与 JSON-only 文生视频保持相同语义；继续拒绝 `"yes"` 等非规范值。
- 根因已由 App-Dev 失败任务确认：Host 任务中 `fast` 为原生 `false`，带图片调用转为 multipart 后按 HTTP 表单契约成为文本 `"false"`，H3 0.9.0 仅接受 Python `bool` 而在模型加载前返回 400。通用 Host/Worker 协议不改动。
- `ai2apps/model-minimax-h3 0.9.1` 已正式发布；不改模型 ID、Checkpoint Distribution、权重、Runtime 依赖或推荐步数。Artifact SHA-256 `4a3e137db64db3da0d8fdb29d63e3dbca344229f006e4f95095541e2ff114b47`，submission `08272d73-8099-4cab-ab24-28caced7e6d5`，Repository metadata 228；匿名回读确认制品字节和 envelope 均精确一致。
- 适配器定向回归 18 项通过；完整 MLX 套件在当前无 Metal 子进程中于收集阶段中止，不视为断言失败。Discover 已显示 App-Dev 本地 0.9.0 / 服务器 0.9.1；用户选择自行升级，升级后待重试原 OpenVDN DMD8 图生视频 Run 收口。
- App-Dev 首次点击“安装模型”被错误拒绝：0.9.1 签名制品实际包含完整 `modelInstall`，但当前 Cloud catalog 投影未回传该字段，本地可信兼容表又仅放行至 0.9.0。已把 MiniMax H3 的本地可信安装映射精确扩展到已发布且逐字节验证的 0.9.1，未来 0.9.2 仍保持拒绝；Discover 分类/安装计划回归 `66 passed`。该 Python 改动需重启固定 `app-dev` Local 后再安装。
- 已通过固定 `app-dev` Helper 认证控制通道只重启 App-Dev Local，端口 `55230 → 59998`；重新打开 Discover 后安装计划错误提示消失，本地 0.9.0 / 服务器 0.9.1 显示正常。按用户要求未代为执行安装，仍待用户升级并重试原 Run。

### NXR-VIDEO-COMPOSER-GALLERY-PREVIEW-20260929：Gallery 单击只预览

- 状态：`ready`。Video Composer 内嵌 Gallery Mini-Entry 的单击与键盘打开操作只进入 Gallery 素材预览，不再把素材自动添加到时间线；拖入指定轨道和 Composer 的显式导入入口仍会添加素材。
- 仅修改 Video Studio 前端消息路由，刷新页面生效，无需重启 Local、更新 Package 或 Runtime。新增静态回归防止 Gallery 的 `asset-selected` 消息再次触发 Composer 导入；固定 App-Dev 强制刷新后实机单击图片素材，Gallery Preview 正常打开，时间线 Clip 数保持不变。

### NXR-ARTIFACT-UNICODE-DOWNLOAD-20260929：中文 Artifact 文件名下载

- 状态：`ready`。修复 Workspace Artifact 下载接口把中文文件名直接写入 Latin-1 响应头而触发 500 的问题；非 ASCII 文件名改用 RFC 5987 `filename*=utf-8''...`，ASCII 文件名保持原有 `filename="..."` 兼容格式，并清除 CR/LF。
- 该问题会让已成功生成的视频播放器拿到错误响应而误报“不支持的视频格式和 MIME 类型”，视频内容本身并未损坏。中文 MP4 文件名下载与音频格式回归 2 项通过，Workspace API Ruff 与 diff 检查通过。已通过固定 Dev Helper 重启 `dev` Local；现有 `宣传视频-1.mp4` 无需重新生成，实机播放器识别 16 秒时长并从 0:00 正常播放到 0:01。

### NXR-VIDEO-COMPOSER-FREEZE-FRAME-20260929：播放头插入静帧

- 状态：`ready`。片段属性工具栏在“在播放头分割”左侧新增“插入静帧”：播放头位于所选、未锁定的视频 Clip 内时，从对应源视频时间提取 PNG，并在同一轨道插入默认 2 秒的静帧 Clip。
- 播放头在 Clip 中间时自动分开左右片段，右半段及同轨后续 Clip 整体后移 2 秒；位于首尾时在对应边界插入。静帧继承当前位置的尺寸、位置、透明度、缩放与蒙版，不含音频，支持撤销和后续时长调整。Composer 13 项、JavaScript 语法及 diff 检查通过；固定 Dev 实机提取 `F0.png` 并生成 60 帧／2.000 秒 Clip，随后撤销恢复原项目。纯前端及本地 Composer 素材导入路径，刷新页面生效。

### NXR-VIDEO-COMPOSER-SPEED-RETIME-20260929：连续变速时长修复

- 状态：`ready`。Composer 视频／音频 Clip 的速度上限继续从 8× 提高到 20×，前端输入、聊天编辑范围和 Python 合成模型保持一致。
- 速度输入不再通过 `x-model` 先改值并依赖一次性的焦点快照；每次 change 都作为独立可撤销操作，以修改前的 `时长 × 旧速度` 固定源片段跨度，再计算新时长，并沿用轨道 Trim 规划推移或回收后续 Clip，避免同一输入框连续改速后时长与速度脱节。
- Composer 14 项回归、JavaScript 语法、Ruff 与 diff 检查通过；固定 Dev 实机在同一输入框连续执行 `4× → 8× → 2× → 8×`，时长稳定对应 `314f → 157f → 628f → 157f`，随后三次撤销恢复为原始 `4× / 314f`。
- 20× 上限扩展继续通过上述 14 项 Composer 回归及前后端静态检查，测试模型可接受并保留 `speed=20`；固定 Dev 强制刷新后现场输入 `20×`，界面正确显示 `20× / 63f / 2.100s`，随后撤销并在 Local 重启后确认项目恢复为原始 `4× / 314f / 10.467s`。

### NXR-VIDEO-COMPOSER-PROJECT-SAVE-NEW-20260929：可靠保存与新建项目

- 状态：`ready`。Video Composer 首次保存和“另存为”不再依赖 `webkitdirectory` 从非空文件夹中的子文件反推路径，也不再绕到受管项目目录；Local 先把 `.ai2video` 序列化为当前用户的 Workspace Artifact，再通过同源 Artifact 下载链接交给 Shell，使 AceFox 按桌面统一策略弹出原生“另存为”面板并由用户选择完整路径。已经从磁盘“打开”的项目仍可用“保存”直接写回其已授权原路径，“另存为”继续走原生面板。
- 工具栏新增“新建”按钮；有片段时先确认，再重置项目、素材引用、播放头、选择与撤销历史并立即持久化新的自动草稿，已经写入磁盘的项目文件不受影响。
- Composer 14 项回归、JavaScript、双语 JSON、Ruff 与 diff 检查通过；固定 Dev 已确认“新建”会先显示保护性确认。迁移并强制刷新后，现场分别点击“另存为”和无外部路径项目的“保存”，两者都打开了 macOS 原生“另存为”面板，默认文件名均为 `宣传视频-1.ai2video`，位置选择与文件类型正常。两次面板均选择取消，原项目内容保持不变。
- 兼容迁移会清除短暂受管目录实现写入草稿的内部 `documentPath` 绑定，使受影响项目下一次点击“保存”也重新进入 Shell 原生“另存为”面板；恢复副本本身不会被删除。
- 工程打开同时支持 AceFox 原生路径和浏览器文件流：Shell 能提供 `mozAI2AppsFullPath` 时由 Local 直接读取原文件；能力尚不可用或授权缺失时，页面把不超过 4 MiB 的 `.ai2video` 文档上传给同源 Local 解析，不再错误提示“需要在 AI2Apps Desktop 中打开项目文件”。文件流打开没有可持久化的原路径，因此后续“保存”会安全地进入原生“另存为”面板，不会误写其它位置。
- 打开修复验证：Composer 14 项回归、JavaScript、Ruff 与 diff 检查通过；固定 Dev Local 重启至 `63655` 后，使用系统文件选择器打开 `/Users/avdpropang/Documents/ai2apps/promotion/宣传视频-1.ai2video`，界面显示“已打开”，并正确恢复项目名、1080p 画布、5 条轨道和 149.27 秒时间线。

### NXR-VIDEO-COMPOSER-TEXT-EFFECTS-20260930：文字样式、描边与投影

- 状态：`ready`。Video Composer 文本层新增可组合的加粗、斜体、下划线和删除线，以及可独立启用的描边与投影效果；描边支持像素宽度、颜色及纯色/模糊羽化模式，投影支持颜色、透明度、扩散/模糊范围和 X/Y 距离。
- 快速预览与最终导出使用同一组工程字段；Pillow 合成器按“投影 → 描边 → 文字 → 装饰线”顺序生成透明文字层，以字体轮廓扩展实现跨中英文字形的稳定加粗，并对整层执行斜切变换实现斜体，同时为模糊、偏移和斜体外扩预留边界，避免效果被裁切。旧工程缺少新增字段时使用关闭效果的兼容默认值。
- 需要进入 App 的文件：`ai2apps/video/composer.py`、`ai2apps/web/templates/system_apps/video_studio.html`、`ai2apps/web/static/js/video_studio.js`、`ai2apps/web/static/css/video_composer.css`、中英文 i18n 及 Composer 回归测试。
- 验证：Composer 14 项回归、JavaScript、Ruff、双语 JSON 与 diff 检查通过；固定 Dev Local 再次重启至 `55889` 后，临时添加文本层确认检查器完整显示默认关闭的“加粗 / 斜体 / 下划线 / 删除线”“描边”和“投影”，随后立即撤销，原工程内容不变。渲染回归同时覆盖四种可组合文字样式、羽化描边、投影透明度/模糊/偏移及旧字段默认兼容。
- 2026-10-01 描边方向修复：快速预览使用 `paint-order: stroke fill` 并把用户设置的外描边宽度换算为两倍的浏览器居中描边，显式设置文字填充色；最终 Pillow 合成改为从扩展字形中减去正文蒙版，只合成字形外圈后再在顶层重绘正文。实色和羽化描边均不会再侵占或遮住文字本身。新增像素回归分别验证两种描边的正文纯色像素完全不变、字形外侧仍存在描边，Composer 回归增至 17 passed；JavaScript、Ruff 与 diff check 通过。固定 Dev Local 重启至 `58170`，实机在 17.20 秒文本层确认白色正文完整覆盖蓝色外描边。

### NXR-VIDEO-COMPOSER-RENDER-TIME-PROGRESS-20260930：按合成时长持续显示导出进度

- 状态：`ready`。Video Composer 不再在逐帧合成阶段长期停留于 15%；PyAV 渲染器按实际完成帧数约每一秒回报一次已合成秒数和总秒数，Run 百分比同步在 15%～88% 区间推进，随后进入 Artifact 保存阶段。
- 运行区会将结构化进度详情本地化显示为“已合成 x 秒 / 共 y 秒”（英文为 `Rendered xs / ys`）；旧的已完成 Run 和非合成阶段详情保持兼容。
- 需要进入 App 的文件：`ai2apps/video/composer.py`、`ai2apps/api/video_studio.py`、`ai2apps/web/templates/system_apps/video_studio.html`、`ai2apps/web/static/js/video_studio.js`、中英文 i18n 及 Composer 回归测试。
- 验证：Composer 14 项回归通过，真实 PyAV 编码测试确认进度从 0 秒单调推进到工程总时长；JavaScript 语法、Ruff、双语 JSON 和 diff 检查通过。固定 Dev Local 已重启至 `56500` 并重新打开 Video Composer，原 `宣传视频-1` 工程仍保持 5 轨道、164.73 秒，未为验收重复触发该长工程导出。

### NXR-VIDEO-COMPOSER-MEDIA-CROP-20260930：媒体区域裁剪、形状与向内羽化

- 状态：`ready`。Video Composer 的视频和图片 Clip 新增非破坏性四边裁剪，四个方向按源素材百分比设置；裁剪区域继续服从 Clip 的位置、尺寸、缩放、透明度和关键帧布局，双击恢复尺寸时使用裁剪后的素材宽高。
- 裁剪形状支持矩形、椭圆和圆角矩形；圆角矩形可设置圆角像素，三种形状均支持向内羽化像素。快速预览先裁取源区域并保持比例放入 Clip，再应用形状和羽化；最终 PyAV/Pillow 合成使用相同顺序，并可继续与已有蒙版图相交组合。
- 预览画面支持直接调整取景：按住 Cmd/Ctrl 滚轮会围绕当前裁剪中心缩放源素材，按住 Cmd/Ctrl 拖拽会在固定显示区域内平移源素材。播放头位于关键帧时操作写入该关键帧，否则同一变换应用到 Clip 基准和已有显式裁剪关键帧。
- 视频和图片素材在预览区拖动右下角尺寸手柄时，默认锁定源素材横纵比，并根据横向或纵向的主拖动方向等比缩放；拖动过程中按住 Shift 才允许宽高独立变化。普通 Clip 和关键帧尺寸编辑使用相同规则，聚光遮罩等非媒体层仍可自由调整形状。
- 媒体 Clip 选中后同时绘制两层几何反馈：高对比实线外框表示 Clip 在画布中的实际位置和显示窗口尺寸，内层虚线贴合经裁剪后实际有内容的矩形、椭圆或圆角矩形区域。实线外框使用常驻的真实顶层 DOM 覆盖元素绘制，不依赖 `:has()` 伪元素重绘；尺寸手柄上的 Cmd/Ctrl 和 Shift 只解释为缩放模式，不再触发多选切换而取消当前 Clip 选中。因此外框在 Cmd/Ctrl 实时拖动以及拖动结束后都持续显示，也不会被视频或图片内容遮挡；Clip/关键帧编辑继续使用青色/橙色区分，模式标签位于外框左上角，尺寸手柄位于外框右下角。
- 裁剪现在拥有独立的“裁剪缩放”参数，可在 Clip 基准状态和关键帧中单独输入；预览和导出统一按源素材像素到画布像素的绝对倍率布置。按住 Cmd/Ctrl 拖动右下角手柄时可以自由改变显示窗口宽高，不受横纵比约束；操作只锁定裁剪左上角和拖拽前的裁剪缩放，右/下裁剪边界按新窗口尺寸重算，因此会先继续展示原素材，只有窗口真正越过原素材右边或底边后的剩余区域才保持透明。该计算同时适用于 Clip 基准状态和关键帧；新增的裁剪窗口版本标记会在打开旧工程时执行一次迁移，修复旧 Cmd/Ctrl 逻辑已写入的过大右/下裁剪值；更旧的工程没有裁剪缩放字段时会先根据原尺寸和裁剪区域推导等价倍率。
- 四边裁剪、裁剪形状、圆角和向内羽化均进入统一关键帧状态；连续数值服从硬切/线性/柔性过渡，形状在到达目标关键帧时切换。新 Clip 和拆分后的 Clip 只在起始关键帧写入完整状态，结束关键帧的所有位置、尺寸、透明度、缩放及裁剪参数默认留空并继承上一关键帧。
- 旧工程缺少新字段时自动使用四边 0%、矩形、0 像素羽化的兼容默认值；新导入素材和插入静帧会初始化或继承完整裁剪状态。
- 需要进入 App 的文件：`ai2apps/video/composer.py`、`ai2apps/web/templates/system_apps/video_studio.html`、`ai2apps/web/static/js/video_studio.js`、`ai2apps/web/static/css/video_composer.css`、中英文 i18n 及 Composer 回归测试。
- 验证：Composer 15 项回归通过（覆盖源区域裁取、裁剪关键帧插值/离散形状切换、空结束帧继承、椭圆/圆角形状与向内羽化像素、绝对裁剪缩放与超出窗口的透明像素），JavaScript 语法、Ruff、双语 JSON 和 diff 检查通过。固定 Dev Local 已重启至 `64606` 并打开 Video Composer；已恢复原工程并选中 `DeepSeek.mov` 目视确认顶层橙色布局外框、右下手柄和迁移后的取景画面正常显示；Cmd/Ctrl 不再触发取消选中、真实 DOM 外框、旧裁剪窗口迁移、右/下边界重算和裁剪缩放输入均由静态契约测试覆盖。

### NXR-AVATAR-SOURCE-CANVAS-20261001：原图尺寸数字人视频

- 状态：`prototype_verified`，不纳入当前 Desktop 发版。新增 `ai2apps/avatar/composition.py` 通用原图回贴组件，按裁剪逆变换在原画布预乘颜色插值与边缘融合；首个接入为 AVTR 开发入口。模型仍以 512×512 推理，输出保留原图宽高；不包含人物抠像。正式模型 Package 与 Mini-App 尚未接入本变更。
- 原图输出为默认，可选 `--output-mode crop` 保留 512²；编码器支持任意宽高，偶数使用 4:2:0，奇数使用保留精确尺寸的 4:4:4（播放器兼容性较少）。仅逐帧提交全画布，队列有界。
- 5 项画布/真实编码回归与原有 3 项编码回归、Ruff 通过；真实权重生成横幅 1920×1080 与竖幅 1080×1920 各 2 秒/50 帧，耗时 4.91/5.09 秒，其中回贴 0.168/0.227 秒，无回退。音画轨道、尺寸、帧数和抽帧目视检查通过；详细限制与复现见 AVTR README。

- 2026-10-01 Alpha 读取修复：AVTR 预处理先应用 EXIF，再使用原图 Alpha 合成 RGB（默认黑底），避免直接丢弃透明度暴露白色边缘；修正角落人物样片的素材合成。6 项画布/Alpha/编码回归与 Ruff 通过；重新生成 1920×1080、2 秒样片，生成 4.87 秒、无回退，抽帧确认明显白色轮廓已消除。

### NXR-AVATAR-CONTROLS-NEXT：数字人转头、注视与情绪控制

- 状态：`planned`，用户已确认作为下一版内容；目前仅完成计划，不是已实现或当前 Desktop 发布候选。
- 范围：优先 AVTR 的小幅姿态、注视目标、表情通道与情绪预设；通用能力协商、Mini-App 时间轨道及 Composer 目标对接。摄像头用户追踪作为独立实时实验，达到性能门槛才开放。
- 计划与验收：`docs/ai2apps-avatar-controls-next-version-plan.md`，包括 M0–M5、坐标/时间语义、口型保护、真实权重测试和安装发布门槛。
- 依赖：现有裁剪/回贴 Host 改动先完成 Desktop 交付；初期复用现有 Runtime，不预先新增专用 Runtime。不得将本条与已验证回贴功能的发布状态混淆。

### NXR-AVATAR-PACKAGE-CANVAS-20261001：通用回贴与 AVTR Model Worker

- 状态：`ready`。Host 通用裁剪/回贴实现与验证完成，待纳入 Desktop Release；三个相关 Package 已正式发布，不能将此等同于生产 Host 已升级。
- 范围：Host 使用系统 Vision + Pillow 定位和裁剪，处理原图尺寸、EXIF/Alpha、视频回贴与音轨；Mini-App 默认 source 分辨率。覆盖 AVTR、FlashHead Lite/Pro、EchoMimic。AVTR 0.1.0 依赖现有 Runtime >=1.8.5，无 OpenCV/ONNX/另一个模型 Package 源码依赖；EchoMimic 0.1.2 修复通用 multipart 引用并补齐签名安装/发现声明；Avatar Suite 0.1.2 增加原图尺寸标签并修复最低 Package 契约版本声明。
- 验证：44 项 Python 回归、6 项独立画布回归、两组前端测试通过。四个模型均完成真实 Runtime 的 1920×1080 偏置人像生成/回贴。AVTR 与 EchoMimic 正式签名字节完成独立 Managed Service 安装、权重校验、真实推理、停止/重启/卸载；Suite 完成签名兼容制品安装。
- 发布：AVTR 0.1.0 / EchoMimic 0.1.2 / Avatar Studio Suite 0.1.2 已发布；Repository Snapshot 232，AVTR Distribution Index 96，HF/MS 两端完整下载 SHA-256 验证。无需新增 Runtime。Suite 按标准手册省略可选 miniApps catalog 投影，完整签名 app.yaml 保留。
- 回执：`docs/ai2apps-avatar-packages-release-2026-10-01.md` 与同名 JSON。Host 源码需随 Desktop Build 交付，App-Dev 的 Python 热挂载环境需重启 Local 才生效。


## SoL-Refiner 独立 MLX 原型（2026-10-01）

- 状态：`ready`（独立研究原型），尚未纳入 Desktop/Runtime 发布候选。
- 范围：`experiments/sol_refiner_mlx/`；独立虚拟环境、官方 LTX-2.3 One-Step 权重加载、视频 Transformer、Gemma 文本条件、VAE、latent 上采样与单步推理。
- 用户要求：先独立实现，不依赖当前 Runtime。没有修改 Runtime 依赖、App Bundle、Worker 或生产服务。
- 发布边界：未来接入 Package/Video Studio 时再评估 Runtime 与 Desktop 变更；当前实验不可作为已验证的生产能力。

- SoL 原型验证（2026-10-01）：13 项跨框架数值测试通过；真实权重 VAE 编码/解码/上采样 BF16 相对 L2 误差 0.80%/0.91%/1.41%。干净推理环境确认没有 Torch、Diffusers、ltx_core_mlx、omlx、ai2apps。M5 Max 128 GiB 完成 33 帧、25 fps、512²→1024²，推理 15.48 秒，MLX 峰值分配 25.91 GiB。尚未验证 CUDA 端到端画质等价、4K 或长视频；产物无音轨。独立源码放在仓库根 experiments 下，不进入 ai2apps App 热挂载源码。

- SoL 优化（2026-10-01，`ready` 独立实验）：默认 Gemma/DiT 逐层释放，完整新提示词流程 kernel physical footprint 从 26.33 GiB 降至 7.00 GiB（约 -73%）；重复完整/缓存条件输出均与保留权重基线 MP4 SHA-256 一致。新增 macOS 内核历史峰值记录、`--retain-weights` 对照及可选 `--vae-decode-conv conv2d` 时间分块解码。快速解码未裁剪像素相对 L2 差异 0.81%，保持实验选项；耗时重复测量漂移明显，不承诺稳定提速。19 项数值/分块边界回归、Ruff 通过，结果和复现命令存于 `experiments/sol_refiner_mlx/results/optimization-benchmarks.json`；不涉及 Runtime 或 Desktop 制品。
- SoL 长度与分段测试（2026-10-01）：33/65/129 帧放大到 1024²，kernel footprint 7.09/11.92/22.60 GiB，耗时 13.25/26.75/57.53 秒；33 帧复测 14.69 秒。65 帧拆成两个 41 帧窗口、重叠 17 帧并在中间两帧融合，单段峰值约 8.55 GiB、总推理 37.82 秒；仅完成单个人像短片探针，未实现生产流式分段或普适时序质量认证。记录见 `experiments/sol_refiner_mlx/results/length-and-segmentation.json`；无 Runtime/Desktop 产品改动。


## NXR-VIDEO-UPSCALING-SOL-20261001

- Status: Runtime 1.8.7 and SoL model Package 0.1.0 published and anonymously verified; Host Desktop integration remains in_progress.
- Integration handoff (2026-10-02): `docs/ai2apps-sol-refiner-video-upscaling-integration.md` documents the published Worker contract, Host background file invocation, model profiles, and pending Video App/Mini-App bridge, ACPF and task/output integration. Later release updates below supersede the original candidate gates.
- Scope: separate `video_upscaling` model type and `/v1/videos/upscalings` Model Worker operation; SoL-Refiner MLX 0.1.0 candidate with bounded overlapping video windows and audio passthrough.
- Host changes: model catalog validation, operation routing, and resource budgets. These require evaluation for the next Desktop release; a Runtime upgrade alone does not update the installed Host catalog.
- Runtime: 1.8.7 published and anonymously verified; exact signed package installed with FlashHead Worker running. Receipt: `docs/ai2apps-runtime-1.8.7-release-2026-10-01.json`. External mirror activation remains pending.
- Validation: 49 unit/contract tests and standard adapter harness passed. Runtime dependency GPU runs passed for 9 and 65 frames; the 65-frame 512-to-1024 run retained all frames in 34.69 seconds. Signed model managed-service invocation and checkpoint Distribution/full dual download remain pending.

- SoL release gates: full dual checkpoint validation precedes Distribution/model publication. LTX/Gemma terms are presented by ACPF and Discover at checkpoint installation; only the installing user may confirm. Publisher acceptance is not a publication gate, and release QA must not manufacture a real user consent record. Runtime GitHub source awaits independent activation review; ModelScope mirror returns HTTP 200 Content-Range and has not been registered under the current strict-206 runbook.

- Model adapter follow-up: queued cancellation and stop now prevent queued GPU work from starting; 26 model Package tests pass. Signed installed inference/lifecycle script is optional QA requiring an actual consenting installer; it is not a request for publisher acceptance on behalf of downstream users. Five focused conditional-license tests pass, covering manifest binding, consent before checkpoint IO, and provisioning consent persistence.

- NXR-VIDEO-UPSCALING-SOL-20261001 update: implementing a recommended 28.71 GB fixed-default profile and optional custom-prompt profile sharing video tensor hashes (about 28.33 GB additional text). Blank prompts use the default; unsupported custom prompts fail with an install instruction rather than being ignored. Derived checkpoint upload, signed Distribution, package installation QA and publication remain in progress.

- Compact SoL progress: 31 Package tests, 6 cache/consent tests and two-profile adapter harness pass. Standard-only 65-frame 512-to-1024 segmented GPU run preserves 65 frames (34.46 s under concurrent load). HF derived weights are uploaded at 751edf5618ccfb8b9e6cae557de9071694cb6ec7 and all remote sizes/digests verified. ModelScope upload/full dual readback and signed installed QA/publication are still pending. No installer consent has been fabricated.


## Encore MLX 数字人原型（2026-10-02）

- ID: `NXR-ENCORE-MLX-A2V`
- Status: `in_progress`; 实验组件，不能纳入可用模型或生产 Package。
- Scope: `ai2apps/experiments/encore_mlx/`。上游固定为 `shaohua-pan/Encore@1790b0e7f69b0ded811de36104651c366dd79686`，保留上游许可证。复用 LTX 实现经验，补齐音视频 Transformer block、双向交叉注意力、split RoPE、文本 AdaLN、门控及 Encore 紧凑路由偏置。
- Validation: 官方未修改 PyTorch CPU block 对照 MLX Metal，12 组随机小尺寸 FP32/BF16 视频/音频结果通过；FP32 相对 L2 最大约 1.55e-7，BF16 最大约 0.00506。覆盖有无路由、相同/不同模态头数、每 token timestep。严格 FP32 对照需 `MLX_ENABLE_TF32=0`。结果和命令见 `block-parity.json`、`source-lock.json`。
- 权重只读取固定 revision 的公开 safetensors 头部；Encore routing_table 实际存储为 `[6144]`。尚未下载模型 payload、执行真实权重推理或测量整模型性能。
- Remaining: 权重映射/LoRA、音频编码、完整条件与 RoPE、Res2s 采样、单段真实推理、跨段封装、Package/Host 接入。现阶段没有 Runtime/Cloud/生产制品变更。


## Video Composer 动态人物扣像（2026-10-02）

- ID: `NXR-VIDEO-COMPOSER-PERSON-MASK`
- Status: `ready`; not published.
- Composer Clip 蒙版扩展为静态蒙版图和动态人物扣像两类；项目保存扣像模型、提示帧/点、阈值、羽化和生成后的逐帧蒙版素材。预览与 PyAV 导出按源素材时间（含 `sourceStart` 和播放速率）同步灰度视频蒙版。
- 默认模型为内置 `apple.vision/person-segmentation`。Desktop Runtime 新增签名分发的 `ai2apps-person-mask` Swift 工具，使用 Apple Vision `VNGeneratePersonSegmentationRequest` 逐帧生成软灰度 MP4 蒙版；App、Helper、Shell 身份不变。
- 可选模型从 Package 模型目录的 `video_segmentation` 能力动态发现。已存在的 `ai2apps.model.sam21-mlx/small` 自动出现，并通过标准 Model Invocation 边界调用；其点提示、阈值和羽化参数由 Composer UI/项目保存。未来同能力 Package 无需新增 Composer 专用模型 ID 分支。
- Packaging: `build-release-app.sh` / `build-dev-app.sh` 构建并放置原生工具，`verify-release-app.sh` 强制检查工具存在；App-Shell 开发环境仍必须使用固定 `build-app-dev-environment.sh` 流程。
- Packaging hardening: Runtime 源码装配现在明确排除 `ai2apps/.build`、`.pytest_cache` 和 `.ruff_cache`；本次检查发现 `.build` 为约 195 GB 的本地缓存，若不排除会被错误复制进 Desktop App。该目录仍保留在工作区，没有删除用户缓存。
- Verification hardening: 非沙箱 Runtime 的嵌入 Python 健康检查启用 `PYTHONSAFEPATH=1`，避免从任意调用方当前目录导入同名模块（本次从 `ai2apps/` 调用时，项目的 `secrets` 包会遮蔽标准库 `secrets`）。
- Validation: Swift 工具 product 编译通过；Composer、Video Studio 和 video-segmentation capability 共 30 项测试通过，其中覆盖动态视频蒙版跨帧变化。固定 `AI2Apps-app-dev.app` 已按专用流程完成重建和替换，`com.ai2apps.desktop.appdev` / `app-dev` / Cloud Runtime 身份、原生工具可执行性、完整深度签名和新 Local 启动均通过验证。当前机器处于锁屏状态，无法补做真人素材的可视化 UI 验收；系统 Vision 在锁屏下对合成测试源返回不可解码，因此该项不作为代码与制品就绪的阻塞，但正式 Desktop 发布前仍应使用真实人物视频完成一次 Apple Vision 与 SAM 2.1 的预览/导出人工验收。

### Encore 实权重组件验证与测速（2026-10-02，NXR-ENCORE-MLX-A2V）

- 新增原始权重映射与 BF16 Encore LoRA 融合；按固定 revision 的 Range 下载首层和音频编码器切片，保留提取摘要，不声称整 checkpoint 摘要验证。
- 真实首层权重对照官方 Torch block：视频相对 L2 0.006806、音频 0.008004；输入仍为合成 hidden states，不是实际生成视频。
- Apple M5 Max / 128 GiB，首层 BF16 热运行中位数：1088 视频 token + 190 音频 token 为 0.06260s；4352 + 190 为 0.23604s。MLX 峰值分别约 2.57/3.81 GB。这是单层、单次前向结果，不能作为整模型时延、整模型内存或出片速度。报告 `ai2apps/experiments/encore_mlx/block-benchmark.json`。
- 已实现 causal audio encoder（log-mel 到 latent），真实权重 FP32 对照依据上游公式转写的 Torch functional reference，33/34 帧相对 L2 < 4.51e-7；505 mel 帧编码热运行约 0.013s。尚未完成波形预处理验证，也未使用官方完整音频类作为参考（现有 Torch 2.14.1 无匹配 torchaudio 包）。
- 未生成 Encore 视频样片；画质、口型和端到端速度均未验证。剩余完整 Transformer 条件/输入输出、音频文本连接器、Res2s/引导采样及视频流水线。保持 in_progress，禁止将组件计时作为产品性能发布。

### Encore 完整 A2V 流水线接入中（2026-10-02，NXR-ENCORE-MLX-A2V）

- 已增加完整 48 层 Transformer、原权重 VAE 映射、双模态文本 connector、波形 log-mel、两阶段 Res2s 和 CLI 流水线；此时尚未完成完整权重推理，不可标记 ready。
- 时间/位置条件检查 8 项通过；RoPE 官方对照最大差为 0。Res2s 使用官方原始函数体、受控零噪声比较，最终 BF16 输出相对 L2 为 0。
- 正在下载固定版本原始 Encore/LTX 权重并准备出片。用户要求持续推进到数字人可用再确认；不得把组件通过或 MP4 编码成功作为完成验收。

### Encore real-video acceptance in progress (2026-10-02, NXR-ENCORE-MLX-A2V)

- Pinned full Encore/LTX/distilled/upscaler payloads downloaded; independent full SHA-256 audit remains pending. Supersedes the earlier header-only state.
- Real MLX two-stage outputs: M5 Max 128 GiB, 512x512, 49 frames in 77.56s (text cache hit); 121 frames in 149.69s (includes 4.86s text encoding). MLX peak about 48.31GB. Driving audio preserved.
- Quality gate FAILED: unrelated confetti/background graphics recur across portraits, prompts and seeds; mouth motion sometimes insufficient. Successful MP4 encoding is not avatar acceptance. Do not publish this candidate.
- Real fused-weight conditioning vs official Torch: relative L2 <=0.00548; first block through output head 0.01339. Text conditioning is under further investigation.
- Worker contract: multipart, cancellation, controlled output, validation; 3 tests pass. Removed runtime imports from sibling SoL experiment source; reused LTX/Gemma primitives include provenance hashes. Actual Worker/Host end-to-end acceptance remains pending.
- Status remains in_progress. No Package, Runtime, Cloud or production publication.

- 2026-10-02: User explicitly authorized publishing compact SoL profiles without waiting for first full ModelScope readback. Release uses the standard metadata_verified builder: pinned HF local bytes plus verified remote HF hashes and authoritative MS file sizes/SHA-256. Full MS readback is incomplete and is not claimed. Package signature, installed sandbox QA, inference and installer consent checks remain required.

- Compact SoL metadata verification completed: default 28,705,240,872 bytes (22 files), custom 57,037,306,792 bytes. Both signed Distributions submitted and review requested. Default submission 56d23428-d732-4354-baaf-f7af806cfbb7; custom submission 0ea3933b-3b56-4d50-b7f5-9db71fd4aeac. Cloud approval requires renewed administrator verification; no Distribution/model publication has occurred. Resume these IDs, never resubmit. Dev Account Security administrator form identified for user handoff; no password accessed.

- NXR-VIDEO-UPSCALING-SOL-20261001: both compact Distributions are published and anonymously verified. Signed installed QA caught a progress protocol mismatch; corrected the Package engine to emit phase/current/total. Model publication remains pending repeated signed installed QA.

- SoL-Refiner MLX 0.1.0 compact dual-profile Package and both Distributions published and anonymously verified. Signed installed QA covered both profiles, audio, cancellation, restart and uninstall using isolated developer fixtures; production installer consent remains required. See docs/ai2apps-sol-refiner-0.1.0-release-2026-10-01.json. Host catalog changes still require the next Desktop release.

### Encore / existing SoL cross-check (2026-10-02, NXR-ENCORE-MLX-A2V)

- Supersedes earlier pending details: all four full checkpoint SHA-256 values verified against pinned official LFS metadata; Worker unit checks now 12 passing. Native PyAV audio mux validated. Actual Worker/Host acceptance still pending.
- Official Torch Transformer substituted into stage two reproduces particles using shared native-fused weights/conditioning/sampler; this does not rule out shared pipeline errors. Original upsampler FP32 relative L2 3.04e-6; official speech encoder FP32 1.43e-6, BF16 0.02835. HQ artifacts also occur at 1024 square.
- User requested comparison with existing successful LTX upscaling. Same Encore portrait-tight first-stage output passed through unchanged SoL one-step inference: 49 frames, 512 square, 8.267s for SoL, excluding Encore stage one and initial decode. Five sampled frames show no prior confetti; blinking and mouth motion retained. This is diagnostic evidence, not lip-sync acceptance or total avatar latency.
- SoL differs in specialized weights, AdaIN, sigma 0.725, single denoise and isolated video modality. Official Encore has no AdaIN; do not blindly copy this operation into its official path. Report: ai2apps/experiments/encore_mlx/sol-cross-check.json. Local audiovisual sample: ai2apps/.build/encore/sol-cross-check/avatar.mp4.
- Status remains in_progress; next checks are full temporal/lip-sync acceptance and remaining Encore stage-two conditioning/fusion/sampler differences. No public release or Cloud change.

- NXR-VIDEO-UPSCALING-SOL-20261001 (2026-10-02, in_progress): preparing unpublished SoL Package 0.1.1 with no artificial input edge limit, adaptive latent-aligned temporal windows, and resource_limited/null pixel capability contract. Host catalog and geometry-based resource reservations must ship with the next Desktop. 0.1.0 remains the published version; weights/Distribution IDs are unchanged. Real 4K and window-boundary tests are pending.

- NXR-VIDEO-UPSCALING-SOL-20261001 (2026-10-02, implementation ready; Desktop/package publication pending): 0.1.1 signed candidate `b1f8d016f7451a0778c9f5bed49c94e40e0476c47ea2db7908b1bc67853ee23e`, 94,987 bytes. 165 relevant tests passed. 4K 17-frame execution preserved all frames (MLX peak 14.07 GiB); signed managed installation additionally verified 4K with audio, custom prompts, cancellation, restart and uninstall. 65-frame 2K adaptive run peaked at 13.04 GiB, took 325.45 seconds with concurrent load; do not claim a speedup. See `docs/ai2apps-sol-refiner-0.1.1-validation-2026-10-02.json`. Candidate keeps Runtime 1.8.7 and existing weights; new Host null-limit parsing and media-derived resource reservations must ship together. No Cookie accessed and no 0.1.1 Cloud submission created in this turn.

- NXR-VIDEO-UPSCALING-SOL-20261001 (2026-10-02): SoL-Refiner MLX 0.1.1 published with user-authorized Dev session. Submission `b7e7ddcb-cb81-4e0c-9838-ffe92ffe70f3`; SHA-256 `b1f8d016f7451a0778c9f5bed49c94e40e0476c47ea2db7908b1bc67853ee23e`; 94,987 bytes. Anonymous Registry metadata v239 download and signature verified; Dev Discover card/details show 0.1.1 and Publisher AI2Apps. Exact signed-artifact installation QA was completed before publication. Host/Desktop changes remain pending; Runtime 1.8.7 and weight Distributions unchanged. Receipt: `docs/ai2apps-sol-refiner-0.1.1-release-2026-10-02.json`.

### Encore lip-sync rejection and controlled probes (2026-10-02, NXR-ENCORE-MLX-A2V)

- User explicitly rejected lip synchronization. SoL-cleaned visual frames are not avatar acceptance. Status remains in_progress and quality_failed; no default model changes or publication.
- Added local research probes: ai2apps/experiments/encore_mlx/probe_audio_drive.py and measure_mouth.swift. Five matched 121-frame/24fps first-stage cases completed (native output 256 square): speech, silence, guidance 3->9, exact transcript, clean audio modality sigma=0. All remain almost closed-mouth and fail usable speech motion. Last three are diagnostic experiments, not new defaults.
- Same-seed speech/silence pixel MAE 1.7416/255, no identical frames: some audio dependence exists, but it does not produce usable speaking motion. Vision inner-lip geometry is only a gross-opening diagnostic, not a phonetic sync score.
- Audio mux audit: both streams start at zero and last 5.041667s; best source/AAC waveform lag zero, correlation 0.999586. Do not offset audio to conceal this generation failure.
- Report: ai2apps/experiments/encore_mlx/lipsync-investigation.json. Probe Python passes Ruff fatal-error checks; Swift measurement compiled and ran on all 121 frames of all five samples. Concurrent local inference makes these runs unsuitable as performance benchmarks.
- Remaining: official Gemma QAT repository access/equivalence, complete original first-stage condition comparison, full native/reference prediction comparison on actual inference inputs, then phonetic and Worker/source-canvas acceptance. Core default inference, App, Runtime and Cloud are unchanged this turn.

- NXR-IMAGE-UPSCALING-SOL-20261002 (in_progress): add image_upscaling as a distinct core operation, direct PNG/JPEG/WebP pixels to PNG with orientation/color handling and preserved resized alpha, shared SoL weights. Model Package 0.1.2 and Runtime worker-route update are being prepared; Host model discovery, resource reservation and ACPF profile will be updated. No image-support release has been published yet.

### Official Gemma QAT verified; prior text-weight hypothesis excluded (2026-10-02, NXR-ENCORE-MLX-A2V)

- User confirmed repository access. Downloaded google/gemma-3-12b-it-qat-q4_0-unquantized at 68f7ee4fbd59087436ada77ed2d62f373fdd4482; all five original shards pass official LFS SHA-256 checks. No upload/publication.
- All 626 language_model.model.* tensors actually used by text encoding are exactly equal to the previously reused pinned SoL text weights. Four actual positive/negative video/audio conditions are elementwise equal. Different shard digests arose from file layout; they did not prove different used parameters.
- Official-directory 121-frame/24fps/512-square run completed. Complete stage-one latent is also elementwise equal to the prior matched speech case. Final video still contains confetti-like artifacts and fails lip-sync acceptance. Therefore missing/different Gemma QAT weights do not explain this sample's failure.
- Added explicit --gemma/--output overrides to the research probe; Ruff fatal-error checks pass. Report: ai2apps/experiments/encore_mlx/gemma-qat-verification.json. Local output: ai2apps/.build/encore/qat-121/avatar.mp4. Observed full time 162.46s, peak MLX 48.31GB; diagnostic run, not a release benchmark.
- Supersedes prior Gemma-access blocker. Continue complete official first-stage condition/native prediction checks and audio-motion debugging. Status in_progress/quality_failed; no App/Runtime/Cloud release or production default changes.

- NXR-IMAGE-UPSCALING-SOL-20261002（2026-10-02 续）：图片核心 operation、模型目录能力验证、Host 根据真实图片尺寸/EXIF 的资源预留、Imagine/Video ACPF profiles 已实现；173 项相关测试通过。原生图片探针 513×341→1026×682 为 4.49 秒/1.45 GiB MLX 峰值，1920×1080→3840×2160 为 12.83 秒/2.99 GiB，两项 RGBA alpha 均精确符合 Lanczos 放大。SoL 0.1.2 已签名（SHA-256 c3b9a51f5f1fb57c9e135f86a4babb79d7a2280329687117c972ab8f55a3d7ee）；Runtime 1.8.8 已签名、公证及 Gatekeeper 验证（SHA-256 28aa0b680a3897388fde3177ecee1e2cfc35eea9feb44a6593b1523d1159c511）。正在最终签名安装验收；两个候选尚未发布，Host 仍待 Desktop Release。原权重 Distribution 不变。新增 `docs/ai2apps-sol-refiner-image-upscaling-integration.md`，App/Mini-App bridge/UI 对接不属于已完成范围。

- NXR-IMAGE-UPSCALING-SOL-20261002（验收完成，发布待认证）：Runtime 1.8.8 + SoL 0.1.2 最终签名安装成功。标准版 4K RGBA PNG、自定义提示词 1026×682 RGBA PNG、9 帧 256×256 含音轨 MP4 均 HTTP 200；两种图片 alpha 精确符合 Lanczos。取消 HTTP 499（约 1.05 秒）、重启、停启、卸载通过。新增 Host EXIF/防伪造尺寸调度测试通过，累计 174 项相关测试。回执 `docs/ai2apps-sol-refiner-0.1.2-validation-2026-10-02.json`。Installation session 返回 active user session required；本次未读取 Cookie、未创建 submission，等待 Runtime 1.8.8 与模型 0.1.2 的精确 Dev 会话授权。Host/Desktop 和 Mini-App 接入仍待后续发布/验收。

- NXR-IMAGE-UPSCALING-SOL-20261002（Package published / Desktop pending）：用户明确授权后，通过标准 Dev live 发布链先发布 Runtime 1.8.8（submission `83ba0f57-f26f-4cc7-acfe-0d00af3a24a4`，Snapshot 240），匿名完整下载/验签后发布 SoL 0.1.2（submission `729d5ffb-6820-4cb4-90c3-c997264dd621`，Snapshot 241）。最终 list-only 两者均 published；Dev Discover 显示两个准确版本。最终字节与已通过真实签名安装/图片视频推理的候选完全一致。回执 `docs/ai2apps-runtime-1.8.8-release-2026-10-02.json`、`docs/ai2apps-sol-refiner-0.1.2-release-2026-10-02.json`。Runtime 暂用已验证 Cloud 单源，镜像验证和独立激活补齐计划、无第二台 Mac 验证限制已记录。模型权重不变。本次精确 Dev Cookie 授权已结束；Host 核心能力/ACPF 仍需 Desktop 纳入，Mini-App bridge/UI 仍需接入，不声称已部署客户端。


### Encore official CPU reference (2026-10-02, NXR-ENCORE-MLX-A2V)

- Added research-only run_official_cpu.py, pinned dependency list and explicit official-cpu-fp32.patch. Uses upstream commit 1790b0e7f69b0ded811de36104651c366dd79686, original checkpoints, official loader/fusion, Gemma, torchaudio, VAE, Res2s and video encoding; no native MLX inference imported. Latest remote HEAD could not be verified due network timeout.
- CPU BF16 matrix benchmark was 8.24s versus FP32 0.00965s for the tested shape. The complete reference uses FP32 compatibility edits and CUDA synchronization no-op. This is not an unmodified CUDA/BF16 reproduction. First FP32 attempt exposed mixed dtype in the upstream sampler/loader; compatibility patch now casts the full Transformer and sampler state consistently.
- Structural audit: all 4,186 expected Transformer tensors present with matching shapes, 1,344 Encore LoRA A/B pairs matched. No missing tensor found; structural checks do not establish release quality.
- Actual official CPU prompt contexts versus native BF16 relative L2 0.0040-0.0071. Actual official image conditions re-encoded with mapped MLX FP32 VAE agree within 4.4e-6 relative L2; audio encoder 1.35e-6 and log-mel 8.19e-7. Reports are ai2apps/experiments/encore_mlx/official-cpu-{context,input}-parity.json.
- Full official CPU reference completed: 49 frames, 512-square, 24fps, 1695.37s total, 100 model forwards, exit 0. Official final decoding and MP4 audio mux completed. All 49 final frames inspected in a contact sheet: no obvious prior confetti, but lips remain mostly closed; quality still fails. First-stage official latent viewed through native decoder also has mostly closed lips. Mouth-opening proxy ranges stage1 0.0423-0.0771, final 0.0713-0.1013; not phonetic alignment scores.
- Additional native BF16 run with same source image/stereo audio/prompt/negative prompt/seed number/size/frames/steps/strengths completed in 80.31s, peak MLX 48.31GB, and visibly reproduces confetti. Precision, preprocessing, RNG and fusion differ, so no isolated numeric root cause claimed. Next separate official A2V mouth-motion/configuration investigation from native second-stage divergence.
- Receipt: ai2apps/experiments/encore_mlx/official-cpu-reference.json. CPU clip: ai2apps/.build/encore/official-cpu-fp32-49-v2/avatar.mp4; matched-input native: ai2apps/.build/encore/native-cpu-matched-49/avatar.mp4. Ruff fatal-error checks pass. Status remains in_progress/quality_failed. No production defaults, App, Runtime or Cloud changed; no Package published.

### Imagine Studio built-in Upscale Image (2026-10-02, NXR-IMAGINE-UPSCALE)

- Added bilingual built-in `ai2apps.imagine.upscale-image`, after Adjust Image. One shared image Slot accepts file/Gallery/Output drag; native 2× PNG output, seed and optional custom-model prompt, source/output dimension preview. No Mini-App Package installation required; models use existing `image.upscaling` ACPF (Runtime >=1.8.8, SoL >=0.1.2).
- Host-owned scoped multipart Run endpoint invokes `image_upscaling` through ModelInvocationContext and native-file background invocation. Model catalog includes this capability even for video-primary SoL. Reuses shared history/Artifact/Output/Gallery; does not expose Worker URLs or tokens. Duplicate queued submissions rejected, cancellation uses invocation callback, orphaned running tasks after Host restart become retryable failures.
- Verification: 14 Imagine Studio Python tests pass, including fake invocation at 13×9→26×18, model/seed validation, shared artifact persistence, duplicate rejection and restart recovery. Node upscaling, i18n, cross-Mini-App Output drop, Product Studio ordering and submitted-prompt tests pass. Python exit emitted existing headless Metal teardown warning (exit 0). No real SoL inference or native UI acceptance performed this turn.
- Status: implemented, App-Dev Local restart and live UI/inference acceptance pending. Python Host change needs Local restart; no bundle rebuild or Package/Cloud publication performed. Include Host/UI/help in future Desktop candidate.


### Avatar odd-dimension playback fix (2026-10-02, NXR-AVATAR-ODD-CANVAS-PLAYBACK)

- Status: in_progress; Desktop Host change, not a model-weight or Runtime change. User-reported FlashHead Lite output artifact art_780f9936fdd94c079d887d307ec25a11 is 1200x675 H.264 High 4:4:4 Predictive/yuv444p. Its original 512-square result is yuv420p; both fully decode with ffmpeg, but the Shell reports the source-canvas artifact unplayable.
- ai2apps/avatar/video_composition.py now always encodes yuv420p, extending the bottom/right edge by one pixel for odd height/width. Existing source content and audio are retained. Odd-size regression checks updated for 322x182 from 321x181 and browser-compatible pixel format/profile.
- Existing content-addressed artifact remains unchanged. Compatible recovery copy generated locally at ai2apps/.build/avatar-playback-fix/NewsRoom-compatible.mp4 (1200x676, audio stream copied). Seven avatar canvas regression tests passed (1.80s). Recovered file fully decodes and is H.264 High/yuv420p, AAC unchanged. Imported via current Dev Gallery UI as gala_e1b57bf8d7374584a61aedccb0c4fa54, NewsRoom-compatible.mp4. Same Dev Shell played to 14s and paused at 23s without playback error. Existing output artifact remains unchanged; source fix requires Host restart/adoption in next Desktop build; no release published.


### Web Agent optional result reading and summary (2026-10-03, NXR-AGENT-OPTIONAL-RESULT-SUMMARY-20261003)

- Status: implemented and live App-Dev accepted. Adds typed boolean input conditions and bounded read_results client SDK helper using native BiDi. Reads up to three distinct result pages by default (maximum five attempted pages), records blocked/failed pages, restores the search page, then summarizes only actual article evidence with source URLs. False skips reading and preserves the search list. Review exposes conditions and inputs; revision prompt preserves existing steps and query bindings.
- Fixed restored Review revision submission: use source_revision instead of missing lightweight recipe.revision. Fixed page-access controls outside viewport and clipped partial rectangles. Deduplicate final redirected URLs.
- Fixed durable Cloud AI invocation: resolve current actor from server-derived Session owner, verify installation/membership epoch, use existing Cloud model gateway authorization. No browser Cookie forwarding, new browser-control protocol, or Cloud-side code change. Local model provider remains unchanged.
- Validation: 33 Python compiler/platform/result-reading tests, 36 Node browser/input/scope/recovery/parameter tests, Ruff on changed feature modules. Additional Agent model stream regressions run.
- Live exact app-dev Shell: original recipe arec_81181b6d29954c06b898f94bac0a1355 revised from v2 (3 steps) to v3 (5 steps), adding boolean summarize, read_top_results and ai.transform. Final run run_1337b4153a864bee973aeab98bb95f9f completed with three distinct rendered pages, zero read failures, final summary and exactly those three source URLs; result visibly present in Sidebar. Earlier acceptance failures exposed offscreen dismissal and internal HTTP 401, both corrected and re-tested.
- Host restarted through exact app-dev Helper; static resources refreshed. No bundle rebuild, Package publication, production or sibling checkout change. Include Host/compiler/SDK/UI in future Desktop candidate.


### Agent unified entry and model selection (2026-10-03, NXR-AGENT-UNIFIED-MODEL-SELECTION-20261003)

- Status: implemented. Removes duplicate run/build Tabs, preserves saved-Agent editing below unified run/Review entry. Build/revision model selector defaults to system work_standard, supports task strength or specific catalog model. AI-step Review/editor controls persist simple/standard/complex and use existing per-tier execution routing. Strength changes create a new recipe revision and invalidate prior Review approval; failed saves restore the displayed controls. Editor preserves conditional branches and skipped transitions.
- Validation: 4 model-selection tests (specific model, default/selected Task, all three execution routes, revision conflicts); 17 Agent platform tests; 16 Mini-Entry tests; 36 Node browser/parameter/navigation/input/result-reading regressions passed. JavaScript syntax, Chinese/English JSON, and Ruff checks passed. Restarted only app-dev Local. Live app-dev sidebar confirms no mode Tabs, medium builder default, and AI-step strength dropdown inside restored Review. No Cloud, bundle rebuild, or production publication. Task strengths follow system defaults; identical defaults select the same actual model.

### Agent builder visual conversation model filter (2026-10-04, NXR-AGENT-VISION-MODEL-FILTER-20261004)
- Status: implemented. Specific builder models must support both conversation/text output and visual input according to catalog capability metadata; excludes image-generation-only, audio, embedding, text-only and unknown models. Declared non-chat endpoints and explicit conversation=false are excluded. No model-name heuristic.
- System Task choices remain at the top in high/medium/low order, medium selected by default, resolving work_complex/work_standard/work_simple at invocation. Static Mini-Entry version advanced to agent-model-selection-6.
- Validation: 3 filter/order regression tests plus 4 parameter tests passed; JS syntax passed. Refreshed only the app-dev sidebar; live dropdown shows high/medium/low followed by 9 visual conversation models, with image/speech generators removed. No Python restart, bundle rebuild, Cloud change or publication.

### Browser Agent authoring attachments and file parameters (2026-10-04, NXR-AGENT-ATTACHMENTS-20261004)
- Status: implemented. Reuses owner-bound Gallery imports/content URLs for creating Agents with attachments. Authoring receives bounded document text and native multimodal image inputs. Distilled/compiled Agents expose file reference object parameters; runtime forms support replacement uploads or HTTP(S) URLs, and stored assets are resolved against the current owner at run creation. No transient blob URLs in durable Source or IR.

- Validation: 36 Python tests passed across attachment ownership/context, API distillation with file parameters, model routing, Agent platform and builder; 8 Node model-selection/parameter tests passed. Ruff, JavaScript syntax and Chinese/English JSON checks passed. Restarted only app-dev Local for Python changes. Live upload interaction remains unverified; refresh the Sidebar to load agent-attachments-7. No bundle rebuild, Cloud changes or publication. Up to 8 attachments; images up to 8 MiB, other files up to 25 MiB. External HTTP(S) URLs remain references and are not fetched by the host; Blob URLs and file bytes are not persisted as parameter values.

### Portrait creative themes (2026-10-05, NXR-PORTRAIT-THEMES-20261005)

- Horror cameo expansion: added The Shining, The Conjuring, Ringu, Ju-On, Scream, Halloween, A Nightmare on Elm Street and Silent Hill (24 cinema themes total including generic genres). Each has bilingual scene/outfit/action presets. Horror-specific prompts emphasize atmosphere and preserve the user's identity without injury, gore or involuntary monster/mask transformation; other film prompts are unaffected. Theme/Portrait/i18n/submitted-prompt regressions cover these presets. Static refresh only; real-generation and live visual acceptance pending.

- Film cameo expansion: added 12 named film-world presets (Star Wars, Titanic, Alien, Terminator, The Matrix, Harry Potter, The Lord of the Rings, Pirates of the Caribbean, Jurassic Park, Interstellar, Inception, Back to the Future), retaining the four generic genres. Each includes bilingual linked scenes/outfits/actions. Prompts cast the input person as an original guest character, preserve their identity instead of an actor's face, and exclude titles/credits/watermarks. Regression covers 16 unique cinema presets and cameo/identity instructions. Static refresh only; no real inference or live visual acceptance performed.

- Career expansion: expanded from 6 to 26 professions with bilingual scene/outfit/action presets (education, research, engineering, technology, legal, healthcare, aviation, rescue, creative, hospitality and other services). Existing custom controls, clothing references and identity-preservation instructions remain unchanged. Regression asserts 26 unique careers and exercises all themed prompts/localizations. Static refresh only; real image generation not tested for these new presets.

- Added five built-in Portrait modes: professional portrait (six professions including news anchor, reporter and astronaut), sports (20 disciplines), movie still (four genres), Chinese-style portrait (three themes), celebrations/greetings (four occasions).
- Each theme provides bilingual linked scene/outfit/action options. Changing theme resets incompatible choices; custom scene/action require text, custom outfit reuses the second clothing-only image Slot and model reference validation. Sports default to full-body framing. Optional greeting text is confined to celebration mode. Shared final Prompt and saved drafts include these settings; no extra size selector or Mini-App Package.
- Static UI/JS only: refresh Imagine Studio; no Host restart, bundle rebuild, Cloud change or publication. Existing Portrait, i18n and submitted-prompt Node tests pass; theme-specific regression covers presets, bilingual labels, resets, custom references, draft restore and prompt invalidation. Live visual and real-generation acceptance remain pending.

### Portrait size selector deduplication (2026-10-04, NXR-PORTRAIT-SIZE-20261004)

- Removed Portrait's duplicate aspect-ratio/size selector. Keep the shared Model / Canvas size / Quality controls and existing custom dimensions; no request or stored draft changes.
- Added a regression asserting exactly one shared size selector and no Portrait duplicate. Static template change only; refresh Imagine Studio, no Local restart or bundle rebuild required. Included in next Desktop candidate.

### Shared Gallery file picker and Agent attachment drag/drop (2026-10-04, NXR-GALLERY-PICKER-20261004)
- Status: implemented. Added reusable AI2AppsGalleryPicker.open with collection/search filters, multiple selection, selection limit, explicit confirm/cancel and focus restoration. Agent authoring supports native file multi-selection, Finder file drops, Gallery single/multiple asset reference drops and the shared Gallery picker. Runtime file parameter forms also offer Gallery selection. Gallery drag exports selected asset IDs while retaining the existing single-asset payload.
- Gallery references are resolved through the owner-authenticated asset API; imported file uploads reuse Gallery storage. Duplicate asset references are removed and the 8-attachment limit is checked before import. Agent static version agent-attachments-8 and Gallery gallery-attachment-dnd-2. No browser-control protocol, Python, Cloud or bundle changes.
- Validation: 13 Node tests passed (picker multiple selection, limits, cancel/focus restoration, drag payload validation, Agent reference lookup/deduplication and existing model/parameter tests); JavaScript syntax and both localization JSON checks passed. 16 Python Mini-Entry regressions also passed. Live app-dev Sidebar confirms attachment/Gallery buttons and drag hint; opened shared picker, selected two Gallery images, confirmed both appeared as attachments and dialog closed, then removed the temporary attachment references. Native Finder drag has not been manually exercised.

### General Agent tool error continuation (2026-10-05, NXR-TOOL-ERROR-CONTINUATION-20261005)

- Status: implemented_and_verified_in_source. Added stdlib-only `tool_recovery.py` policy, explicit no-dispatch `ToolErrorAction`, and General Agent opt-in to paired, durable model-visible failures. Invalid JSON/aliases/questions and no-effects tool schema/timeouts/provider/output/availability errors can request a new model decision. Preserve approval, identity checks, cancellation and uncertain write protection. Share a three-error recovery budget; no automatic tool replay or change to other executors' defaults.
- Memory retains failed paired rounds and recognizes legacy schema-error records. Gateway now also redacts injected secrets in output-schema failure messages. 25 new recovery tests cover mixed batches, actual deadline expiry, bounds, writes, cancellation, secret redaction, non-opted-in executors, and host restart without replay.
- Validation: 101/101 broad regressions and 40/40 final recovery/control/checkpoint tests passed (117 distinct tests); standalone Python -I policy checks, scoped Ruff, compile and diff checks passed. Acceptance receipt: `docs/tool-error-continuation-acceptance-2026-10-05.json`; source comparison and boundaries: `docs/ai2apps-tool-error-continuation.md`.
- Running Dev/App-Dev/Test not refreshed in this turn. No Cloud, bundle or production publication. Real-model recovery success rates and complete upstream parity remain unverified.

### Tool recovery instance activation (2026-10-05, NXR-TOOL-RECOVERY-ACTIVATION-20261005)

- Status: activated_and_verified. Rebuilt all three fixed Apps through `build-dev-app.sh`, `build-app-dev-environment.sh` and `build-test-app.sh`; each previous Bundle archived by its builder. Restarted only the selected instances, preserving their separate state.
- Dev / App-Dev / Test Local PIDs 48843 / 62202 / 79913, ports 55358 / 55610 / 55979; all health checks passed. All three strict deep code signatures passed; complete release-shaped Bundle verifiers passed for App-Dev and Test. Fixed bundle/instance identities preserved, App-Dev remains Development/cloud with disabled updates and trusted repo source mount, Test remains non-Development/cloud with no source mount.
- Seven tool-recovery integration source files embedded in App-Dev and Test match the accepted repo source byte-for-byte; all source hashes from the 117-test acceptance remain unchanged. Dev uses the fixed repo runtime/source contract. Live native App-Dev title verified as `AI2Apps-App-Dev: App-Dev 127.0.0.1:55610`. Memory API and reader registrations remain present in all three.
- Receipt: `docs/tool-recovery-instance-activation-2026-10-05.json`. No production publication or real-model failure/recovery test; runtime activation is confirmed through fresh process/identity/health and verified source contracts.

### Native App/Mini-App development Harness (2026-10-05, NXR-NATIVE-APP-DEVELOPMENT-20261005)

- Status: implemented_verified. Added a standard-library Python draft core and owner-bound AI2Apps App/Mini-App tools with native Coder UI. Read-before-edit SHA checks, exact text replacement, bounded search/read, Runtime Python commands with background continuation, manifest validation, safe static preview, source conflict detection and reviewed write-back reuse existing Agent memory/tool recovery and process sandbox. Voice Studio authoring retains host-owned Quick Read output.
- Acceptance: 111 Python regression tests plus final 20 native-development/process tests pass (123 distinct Python tests); isolated standard-library core has 12 passing tests, Node UI has 4. Actual macOS Seatbelt verifies managed Runtime Python and original/foreign project read denial. App/Mini-App generation, failing-test repair, restart follow-up, ownership, stale revision and explicit apply covered. Ruff, compileall, JS syntax and scoped diff checks pass.
- Live App-Dev native entry and model/task/review panel accepted on the isolated Native Harness UI Acceptance Project at 127.0.0.1:59153. No real-model quality benchmark, automated visual debugging, full host Bridge preview, deletion write-back, installation or publication. Per-file atomic apply retains backups and progress journal; not a multi-file transaction. Dev/Test not rebuilt for this feature.
- References: docs/ai2apps-native-app-development.md; docs/native-app-development-acceptance-2026-10-05.json. DeepSeek MIT source pinned to 5badb15009ae1756c3afe0ae0cef1faafc290ccc. No Cloud changes or production publication.

### Coding sub-Agent cooperation (2026-10-05, NXR-CODING-SUBAGENTS-20261005)

- Status: implemented and tested in App-Dev. Independent analyst/tester/reviewer/worker snapshots, host-bound workspace/permissions, durable async start/status/wait/cancel/followup and worker merge. Waiting releases global capacity even at concurrency=1, survives restart and settles one original tool result. Root shared budgeting preserves uncertain usage, reports remaining tokens and typed exhaustion; early memory compaction uses a soft trigger without lowering the existing admission ceiling.
- Coder shows role/stale/evidence/logs/usage, restores the owned latest task after a Local port change, and selects App/Mini-App previews. Native draft HTML embeds bounded local classic JS/CSS to avoid opaque-frame resource 401s; no same-origin, credential, network or publication privileges are added. New subdirectory component registration is explicitly checked against validation IDs. Generic Tool listing caches service metadata only within one list call and filters coding-only tools before reads; execution authorization is unchanged.
- Validation: 155 distinct pytest checks, 12 isolated standard-library checks and 9 Node UI checks passed, including actual macOS Seatbelt, single-slot waiting, any/all wakeup, group capacity, cancellation/restart, parent capability intersection, forged IDs, migration and patch preflight. Real DeepSeek/Terra attempts, App repair and new Mini-App are recorded; both cases required explicit bounded follow-up Runs after initial budget/context limits, so no single-Run success claim. Counter preview 0→1 and Text Stats hello world→11 characters/2 words verified; original fixture remained unchanged until reviewed Apply. Module/async/remote preview and Host Bridge/mobile acceptance remain outside this static preview guarantee.
- Activation: fixed App-Dev Local restarted through Helper; live title AI2Apps-App-Dev: App-Dev 127.0.0.1:59092. No App rebuild, Cloud change, production publication or sibling instance data merge.
- Design/evidence: docs/ai2apps-coding-subagents-development-plan.md and docs/coding-subagents-acceptance-2026-10-05.json. SQLite migrations 78/79 preserve prior tasks and narrowly upgrade the builtin coding executor.

### Agent Sidebar refresh clears previous results (2026-10-05, NXR-AGENT-REFRESH-RESULTS-20261005)
- Status: implemented. Explicit title-row refresh clears displayed AgentRun/result/handoff and cached AI presentations before reconnecting; initialization skips completed history restoration for explicit refresh. Initial mount still restores history, and active/resumable runs retain their controls. Static version agent-refresh-results-9; no stored run deletion, Python restart, bundle rebuild or Cloud changes.
- Validation: focused Node refresh regressions verify completed result clearing, unchanged initial restoration and retained active run controls; related parameter/Gallery tests and JavaScript syntax passed.

### Agent result heading clear icon (2026-10-05, NXR-AGENT-RESULT-CLEAR-20261005)
- Status: implemented. Added an eraser icon directly after the execution-result title with Chinese/English accessible label and tooltip. Click clears the current displayed run/result/handoff and cached AI presentation through the existing renderRun(null) path; stored execution history remains intact. Static version agent-clear-result-10.
- Validation: JavaScript syntax and existing refresh/result-clear regression tests passed. Static-only change; no Python restart, bundle rebuild or Cloud changes.

### Native Sidebar toolbar refresh (2026-10-05, NXR-SIDEBAR-REFRESH-20261005)
- Status: implemented. Explicit toolbar refresh reloads the selected Mini-Entry with a fresh context revision and refresh marker; automatic context notifications keep their existing navigation semantics. Agent initialization uses the marker to suppress restoring completed results. Implemented as a checked-in packaged AceFox transformation in the standard App builder. Chinese/English tooltip now describes refreshing the current panel.
- Validation: 19 focused Python tests and 2 Node refresh regressions passed; packaged sidebar JavaScript syntax passed. Fixed App-Dev rebuilt through build-app-dev-environment.sh; verify-release-app.sh and deep strict codesign verification passed. Live native title verified as AI2Apps-App-Dev: App-Dev 127.0.0.1:52217. Live Browser initially restored completed run_1337b4153a864bee973aeab98bb95f9f; clicking native toolbar refresh reloaded Agent Mini-Entry with the refresh marker and removed the displayed run/result/handoff.

### Builtin App Developer executor migration (2026-10-05, NXR-APPDEV-EXECUTOR-MIGRATION-20261005)
- Status: implemented. Startup migrates only the legacy host-owned ai2apps.app-developer definition from builtin:general-agent to builtin:coding-parent before registration. Package-owned or unknown executor records retain existing ownership conflict checks. This resolved an App-Dev restart blocker discovered during Sidebar refresh verification.
- Validation: scoped/idempotent migration regression passed; App-Dev Local startup completed after restart and the Shell reconnected. No Cloud or other instance data changes.

### Native Sidebar actions menu (2026-10-05, NXR-SIDEBAR-SITE-DATA-20261005)
- Status: implemented. Replaces toolbar refresh with an actions menu containing refresh and native site-data deletion. Uses the active HTTP(S) page's schemeless site and Firefox ClearDataService; clears cookies/site data and caches, including partitioned storage. Internal pages disable deletion. Native confirmation identifies the domain; result dialogs report success or incomplete cleanup. Includes Chinese/English labels.
- Validation: 3 native-menu behavior tests and 3 packaging regressions passed; native JavaScript, Python and locale JSON syntax checks passed. App-Dev rebuilt via the fixed builder; release verification and deep strict codesign verification passed. Live UI verified menu items, disabled deletion on about:newtab, current example.org domain, and cancellation of the native confirmation without deletion. Actual user website data was not deleted during verification. Existing broad omlx/admin/routes.py lint failures remain outside this change.


### Avatar Package localization (2026-10-05, NXR-AVATAR-I18N)

- Implemented source changes in packages/ai2apps-avatar-studio-suite: nine complete catalogs matching Host languages (en, zh, zh-TW, ja, ko, fr, es, pt-BR, ru), localized HTML titles/labels/accessibility strings, model setup and resolution options, known generation preset labels, input validation, job states and submission errors. Removed hard-coded Chinese CSS-generated slot text. Package and Mini-App declaration names/descriptions localized.
- Studio bridge includes locale in the authenticated mount handshake and sends locale updates when Host document language changes. Package reads mount locale query for initial rendering, normalizes regional variants, and falls back to English. Language updates retain selected media/model/preset/resolution. Existing shared output ownership unchanged.
- Corrected API error extraction for error/message and detail forms: decoded audio duration limit failure now reports the selected model limit in the UI language. Unknown upstream errors retain their original diagnostic text.
- Validation: nine-language completeness/placeholders/HTML-key/fallback Node test, input/drag/model setup + language-switch + duration-error Node test, and mount bridge Node test pass. 19 Host client/avatar tests pass; sandbox Metal shutdown warning is unrelated to these CPU/UI tests.
- Source implementation complete; signed Package rebuild/publication and installed-instance UI acceptance pending. Existing version identifiers and signed dist artifacts untouched this turn. Host change requires next Desktop scope assessment; no production publication performed.


### Avatar input audio recording and preview (2026-10-05, NXR-AVATAR-AUDIO-SLOT)

- Source implementation: Avatar Mini-App supports Host-owned microphone recording with start/stop/use/discard, elapsed time and automatic duration limit. Discard preserves existing input. Generation and input replacement are disabled while recording. Finder/Gallery/Output imports and recordings share a filename/size/duration/native audio preview inside the audio slot; no autoplay. Audio metadata is read locally, with decoding fallback for unknown container duration and clear unsupported-preview errors. Nine locales updated.
- Host recorder is loaded by Video Studio only and exposed through the existing mount-authorized avatar capability bridge. It releases microphone tracks after stop, error, cancellation, navigation, frame removal and late permission completion. Limits: selected model duration with 0.25s encoding margin, Host hard cap 600s and 100 MiB. Input recordings never enter generated output history.
- Microphone self-permission scoped to first-party Video Studio HTML and its Shell frame, in addition to existing Chat scope. Package frames still cannot request microphone access. Package resource CSP now permits media-src blob: for local input preview while retaining connect-src none and opaque-origin production sandbox. Changes to omlx/admin/routes.py require embedded component adoption/rebuild per release workflow.
- Validation: recorder lifecycle/auto-stop/denial/late permission cleanup Node tests; audio slot filename/duration/record/use/discard and existing drag/model/locale/error Node tests; all nine locale catalogs; avatar bridge tests pass. 31 Host/security/avatar tests pass. Actual microphone and installed Package UI acceptance, signed Package build/publication and Desktop adoption remain pending. Existing installed Packages have not been modified.

### NXR-AVATAR-PACKAGE-013 (2026-10-05)

- Status: Package 0.1.3 published, Snapshot 248; Desktop Host rollout remains pending. Nine-language names/UI and audio slot recording/preview included. Existing Publisher/key retained. Public signed download and clean-instance installation passed; four Node suites and 31 Python tests passed. Receipt: docs/ai2apps-avatar-suite-release-2026-10-05.md.
- Host recording bridge, sandbox Blob media CSP and localized Studio labels remain separate Desktop changes; publishing this Package does not publish the Desktop.

### Compact Gallery picker asset cards (2026-10-05, NXR-GALLERY-PICKER-COMPACT-20261005)
- Status: implemented. Shared Gallery picker matches Gallery Mini-Entry with a compact responsive square thumbnail grid, image/video previews, video badges, audio/file icons, single-line ellipsized names and stable selection borders. Hover or keyboard focus shows the full name in a black tooltip with white text, constrained to the viewport and hidden on scroll or reload. Static version gallery-picker-3; no App rebuild needed.
- Validation: JavaScript syntax and all five existing Gallery picker regressions passed. Refreshed the live app-dev Browser Sidebar and visually verified the three-column square grid, single-line names, black/white full-name tooltip and loaded video frame preview. No attachments were added; the existing prompt was preserved.

### Agent attachment preview cards (2026-10-05, NXR-AGENT-ATTACHMENT-CARDS-20261005)
- Status: implemented. Agent composer attachments now use compact 96px square image/video previews, audio/file icons, single-line filenames, black/white full-name tooltips and top-right remove buttons. Existing owner-authenticated Gallery content references and attachment submission remain unchanged. Static version agent-attachment-cards-12; no rebuild required.
- Validation: JavaScript syntax passed. Live app-dev Sidebar refreshed; original prompt and selected Gallery attachment restored and visually verified as an image thumbnail with single-line name and top-right remove button.

### Requested Weibo navigation (2026-10-05, NXR-WEIBO-NAVIGATION-20261005)
- Status: implemented. Agent exploration recognizes 微博/Weibo as explicit navigation intent for weibo.com, weibo.cn and m.weibo.cn (including normalized www). Opening these requested sites no longer triggers generic confirmation merely because the task/description mentions publishing. Other operation confirmation rules remain unchanged. Static version agent-weibo-navigation-13.
- Validation: all 10 navigation confirmation tests pass, including publishing-preparation wording and lookalike host rejection. Existing active exploration was not refreshed or resumed; updated code loads on the next Sidebar refresh.

### WebAgent login assistance and shared enhanced DOM (2026-10-05, NXR-WEBAGENT-LOGIN-DOM-20261005)
- Status: implemented in source. Exploration now sees bounded cleaned DOM and element references instead of counts alone. The Sidebar and browser.snapshot share one snapshot script (visible HTML, Shadow DOM, stable refs, sensitive field masking); observation, analysis and target resolution use it through authenticated WebDriver BiDi. No new semantic browser transport.
- Login entry is permitted as a prerequisite of requested publishing; QR/credentials challenges enter needs_user. Manual continue and same-site login-change monitoring resume with original goal, attachments and evidence. Merely opening a site cannot complete a publishing task; actual publish/send action is required and the planner must verify visible success.
- Validation: 36 scoped Python tests passed, navigation/login monitoring Node tests passed, shared snapshot regression added; source syntax checks passed. Live app-dev Local restart and authenticated Weibo end-to-end acceptance pending; no post published during verification. Python changes require exact app-dev Local restart; no App rebuild required.

### NXR-H3-AVATAR-TIMELINE-20261005

- 2026-10-06 completed model release: H3 0.10.0 accepted SHA 5d87670df8f672497f6129c4c400428688dbed97447f74e56877255206cc05d9 formally published, submission 1701c811-203a-469b-9227-b1a56f19b90e, Snapshot 255. Anonymous complete download and signatures verified; previous Cloud blocker resolved through audited withdrawal. Added Host ACPF Turbo/Base50 profiles requiring Runtime >=1.8.8, H3 >=0.10.0 and 64 GiB; 23 Avatar/Canvas regressions and scoped diff check passed. Model Package is shipped; this Host profile change must be included in the next Desktop release. No Desktop rebuild/publication this turn. Existing Mini-App can discover installed H3 models without a Mini-App update. Cookie authorization for this release is now exhausted.

- Final local accepted artifact: H3 0.10.0 SHA 5d87670df8f672497f6129c4c400428688dbed97447f74e56877255206cc05d9, 215634 bytes. Both installed portrait models infer successfully; restart/uninstall/common Avatar discovery pass. Cloud corrected submission twice returns internal_error, old approved unpublished candidate cannot be rejected by current review endpoint. No corrected submission listed; Cloud handoff: docs/ai2apps-h3-avatar-cloud-publication-blocker.md. ACPF entries remain pending public release. Developer contact-sheet inspector now bounds sampling for one-second clips. Full receipt: docs/ai2apps-h3-avatar-package-0.10.0-release.md.

- Publication resumed with explicit Dev Cookie authorization. Turbo and Base50 auxiliary Distributions are published and signature verified (checkpoint Index 106/107). Initial Package publication correctly rejected a Base50/Distribution identity mismatch; retained submission 32a6d1c0-acdc-44f5-bf09-54865f251a5b remains unpublished/approved (Cloud refuses rejection outside review-pending). Corrected source now uses separate model-bound Distributions with identical pinned weight bytes; both installed-model inferences are under final validation. Package ID/version/Publisher unchanged.

- Packaging audit: added portrait refinement components to the source SBOM, pinned code provenance and removed a dangling attribution file reference. Signed weight assets and published model declarations remain unchanged; final packaging still awaits the new Distribution publication.

- 2026-10-05 latest: end-image anchored 60-second motion now retains lighting; Worker enables it. H3 1569.60 s / 29.980 GB, automatic refinement on Runtime 1.8.8 144.33 s / 4.369 GB. Exact 60-second audio/video, four speech intervals all -1 SyncNet frame, confidence 4.467–5.710. Base50 refined short also -1 frame. 26 Worker plus 72 common/timeline/media tests passed. Dual-source auxiliary Distribution signed and fully re-downloaded (1,536,290,232 bytes); not yet published. Scoped Cookie authorization pending because Installation sessions unavailable. Final Package build/install/publication and ACPF activation remain pending; old local native-only archive must not be published. No Desktop/Cloud deployment.

- Latest long acceptance: 60-second/1440-frame H3 motion completed, PTS exact, improved seams; late lighting drift still fails visual acceptance. Actual installed Runtime 1.8.8 auto refinement completed in 161.12 s / 4.369 GB peak. Four speech intervals remain offset -1 frame. Original-image plus latent-context anchoring is now an explicit research flag under a second 60-second test; not enabled by default. Dual-source refiner assets uploaded and full-download verification underway; no registry submission. Detailed receipt: docs/ai2apps-h3-avatar-validation-2026-10-05.json.

- P3 update: native English Base50 and silent preroll also fail. Added pure-MLX YuNet/BiSeNet automatic mouth preprocessing to the unshipped MuseTalk source, preserving source licenses. BiSeNet CPU parity against upstream: 100% label agreement, max logit error 4.34e-5. Automatic English refinement and 60-second updated continuation remain under acceptance. Existing Runtime reused; no production change.

- Latest acceptance: signed local candidate 0.10.0 installed with Runtime 1.8.8 and completed 68-frame English inference in 107.19 seconds. English lip sync failed; do not publish this candidate as accepted. Direct-latent 30-second run completed in 814.38 seconds with improved visual detail; five-frame VAE boundary holdback implemented and unit-verified, real updated long run pending.
- P3 investigation repaired unshipped MuseTalk media PTS, stereo preservation, full-track mux and ceil video coverage. Real AAC pulse/correlation regression passed (22.05 kHz, at most two samples of delay); this is part of the future model Package review scope. No current Desktop or public model release changed.

- Status: in_progress. Plan: docs/ai2apps-h3-avatar-technical-plan.md. Host timeline and offline evaluation tooling added; model implementation lives in /Users/avdpropang/sdk/minimaxh3/ai2apps-package, to ship as a separately versioned Package.
- Fixed driving PCM, correct clean audio timestep, protected video prefix, exact frame/sample timeline, PyAV assembly, cancellation and persistent hashed segment cache implemented. No dedicated Runtime dependency identified; installed Runtime 1.8.8 has required libraries.
- Validation: 33 timeline tests; latest latent-continuation, Worker routing, mask and real PyAV tests 14 passed. Base/LightX2V short Chinese SyncNet offset 0, confidence 3.0–3.7, calibrated against upstream example. Negative reversed-audio control scores lower. All-silence mouth behavior remains a limitation.
- First 30-second/720-frame/5-window real run: 957.29 seconds, MLX peak 29.98 GB; cumulative visual drift and visible seams fail quality acceptance. Direct chunk-aligned latent continuation implemented and under real comparison. Do not advertise long-video quality as accepted.
- Source candidate 0.10.0 includes two portrait aliases with distinct upstream IDs; signed archive and isolated installed Runtime inference passed, quality acceptance pending. No Cloud or Desktop release performed.
- Reproducible tools: experiments/h3_avatar/run.py and syncnet_evaluate.py. Development-only SyncNet/Vision tools are excluded from the Package.

### WebAgent shared snapshot URL fix (2026-10-05, NXR-WEBAGENT-SNAPSHOT-URL-20261005)
- Status: implemented. Corrected enhanced snapshot helper loading from the nonexistent /static path to the Admin static route /admin/static. Bumped Agent Mini-Entry browser client cache version to browser-shared-snapshot-10. This fixes exploration failing before its first action with Cannot load shared browser snapshot helper.
- Validation: shared snapshot regression now asserts the exact Admin resource URL and passes; JavaScript syntax passed. Static-only repair, Sidebar refresh sufficient; no App rebuild or Local restart needed for this repair.

### WebAgent ordinary input payload repair (2026-10-05, NXR-WEBAGENT-INPUT-PAYLOAD-20261005)
- Status: implemented. Normalizes explicit input text/content/value fields to arguments.value. Exploration rejects missing input payloads before returning an executable step and asks the planner to repair with the user-supplied text. Planner prompt documents the exact input schema. Frontend treats missing ordinary input text as failed for replanning, rather than needs_user; credential/CAPTCHA guards retained. Static version agent-input-payload-15.
- Validation: 7 Python input/parameter/login tests pass, including malformed input repaired to the exact supplied Weibo text; Node payload, shared snapshot and input target/Enter tests pass. Python normalization changes require app-dev Local restart, static changes require Sidebar refresh. Live publishing not performed.

### Codex persistence event-loop isolation (2026-10-06, NXR-CODEX-PERSISTENCE-20261006)
- Status: implemented in source. Codex synchronous update callbacks now run on worker threads, preserving ordered completion including cancellation; stream output updates are coalesced at 250 ms with complete output flushed at interaction and completion boundaries. Todo conversation binding and output-file writes also move off the event loop.
- Validation: 7 scoped tests pass, including a real SQLite write-lock regression proving the event loop remains responsive and a 100-delta coalescing/final-output test. Native localhost MCP transport passes. This removes a reproduced blocking risk; the exact cause of the earlier live health-check timeout remains unconfirmed.
- Activation: Python-only change, exact app-dev Local restart required; no App rebuild or production publication.

### Sidebar Agent results bound to Tab (2026-10-06, NXR-AGENT-TAB-RESULTS-20261006)
- Status: implemented. Restore/resume only AgentRuns with the current explicit BiDi browsing context. Unknown or other-Tab results are excluded, including same-URL Tabs. Tab changes clear the result card and presentation cache; stale run polling responses cannot restore it. Same-Tab navigation retains its results. Static cache version agent-tab-results-16.
- Validation: Node Tab-identity regression and existing input payload/target tests pass; JavaScript syntax passes. Static-only activation requires Sidebar refresh; no Local restart or App rebuild. Live native Tab-switch acceptance pending.

### WebAgent login popup handoff (2026-10-06, NXR-LOGIN-POPUP-HANDOFF-20261006)
- Status: implemented. Login entry click immediately enters user assistance, recording only newly opened BiDi contexts with the original Tab as opener. Pending login blocks repeated actions; resumption requires the popup to close and original page to be nonempty without login controls. Inline login also pauses. Existing same-origin read-only watcher resumes only after this gate passes; credentials remain user-owned. Static version agent-login-popup-17.
- Validation: 9 scoped Node tests pass including opener filtering, popup/empty-page/pending-login gates, Tab results and ordinary input. JavaScript syntax passes. Sidebar refresh required; no rebuild or Local restart. Live authenticated login acceptance pending; no credentials entered or post published.


### NXR-H3-AVATAR-LONG-JOBS-20261006

- 2026-10-06 latest: H3 model Package 0.11.0 formally published (Snapshot 261). All eight variants passed cross-window tests. Signed installation, queue reconstruction, explicit cancel/retry, and separate Local process restart passed; the resumed process invoked only segment 1 and preserved segment 0 SHA-256. Service stop/restart/uninstall passed. ACPF now exposes all eight portrait variants with >=0.11.0 and removes obsolete 8/60-second descriptions. Host feature changes still require a future Desktop release; Package publication does not ship Host code. Receipt: docs/ai2apps-h3-avatar-0.11.0-release.md.

- FL2VA Q8 两窗口 9 秒检查通过：216 帧，时长/PTS 正确，接缝连续，SyncNet -40 ms/confidence 4.602；耗时 46.66 分钟、MLX 峰值 35.76 GB。六种已完成跨窗口，余下 StageB50/FL2VA Q4。

- DMD8 两窗口 9 秒检查完成：216 帧、时长与 PTS 正确、接缝视觉连续；0–4/5–9 秒 SyncNet 均 -40 ms，confidence 6.041/3.860，保留后段较低置信度说明。耗时 8.83 分钟，MLX 峰值 41.19 GB。跨窗口已有五种通过，剩余三个 50 步变体继续。

- LightX2V 8 步两窗口 9 秒验收通过：216 帧、时长/PTS 正确，接缝视觉连续，SyncNet -40 ms/confidence 4.901；耗时 8.11 分钟、MLX 峰值 29.98 GB。已有四种变体通过跨窗口，剩余四种继续。

- Ref2VA Q8 两窗口 9 秒检查通过：216 帧、音视频时长精确、PTS 误差 0；接缝连续，跨接缝 SyncNet 0 ms/confidence 7.785；耗时 43.82 分钟、MLX 峰值 35.76 GB。其余变体跨窗口测试继续，签名安装/恢复验收仍待执行。

- Ref2VA Q4 真实两窗口 9 秒验证通过：216 帧，音视频均 9 秒，PTS 误差 0；接缝帧差 1.062（全片 p95 1.283），跨接缝 SyncNet -40 ms/confidence 7.470。总耗时 43.17 分钟，MLX 峰值 19.21 GB；直接 Worker 原型证据，签名安装验收仍待执行。

- Mini-App 模型选择脚本验收通过：由目录提供八个 H3 入口，逐项选择后请求保留正确 avatar_model_id/strict preset，69 秒音轨通过前端检查，未就绪模型禁用生成。未改 Mini-App 产品代码；这不是新 Package 的实际安装证明。

- 变体真实短片进度：8/8 完成；全部 24 帧且 PTS 无误，每种均匀抽样 12 帧检查通过。余下七变体的 9 秒两窗口验证已启动，尚未视为安装或发布验收。

- 输入配额：分段模型的总时长按现有 100 MiB 传输边界和 16 kHz 单声道 PCM16 标准化格式计算，上限 3276 秒；避免界面承诺 3600 秒而提交时超过大小限制。此为整项任务的资源配额，8 秒仅为内部生成窗口。

- Status: in_progress. Private continuation packets and the sequential runner are now connected to VideoTask behind an explicit signed `avatar_segments` capability. Task creation pins the Package digest/model contract; per-window calls release the scheduler lease, validate exact decoded frames and predecessor state, and mux the original audio once. Retry copies only the same actor's terminal-task packets and validates them again. Graceful shutdown requeues unfinished segmented tasks.
- Worker source now supports one-window H3 motion with exported latent state, global-time MuseTalk refinement, and silent segment packets. Eight H3 aliases are routed internally; Ref2VA uses reference-image conditions instead of FL2VA keyframes. These new aliases and segmented capabilities are not yet advertised by a published Package.
- Validation so far: 44 Host queue/packet/mux tests passed; existing Worker/audio regression 35 passed. Real Whisper features for four intervals of a 60-second track, including the 30-second boundary, exactly match whole-track features (maximum error 0). Real 187-frame segment refinement completed in 23.20 seconds with exact 24 FPS timestamps and no intermediate audio track. Host shutdown/restart test passed (45 Host tests total). A real two-window 9-second render completed in 261.20 seconds: 216 frames, exact audio/video duration, zero timestamp errors, cross-seam SyncNet offset -40 ms/confidence 5.211. A fresh 69-second render completed in 2225.39 seconds: 11 windows, 1656 frames, exact 69-second video/audio duration, no timestamp error. Four SyncNet samples including 30/60-second boundaries and tail have offset -40 ms and confidence 4.701–5.669.
- 续作补充：区分 Host 关闭与用户取消；关闭期间到达的用户取消不会被重新入队。模型 Package 改变后重试不复制旧模型缓存。Host 音轨读取改用标准库 WAV，最终拼接用已有 PyAV 流式解码，未引入 soundfile 依赖；双声道尾部和 AAC 起始对齐实编码测试通过。八个变种的 Worker 本地文件依赖预检通过，统一真实推理脚本已落盘；69 秒任务完成后串行运行各变种 smoke。
- Host 兼容性：新增已实现功能标识 `avatar.segmented-jobs.v1`。下一版 H3 必须在内层 service compatibility.features 要求它；旧 Host 按既有机制拒绝安装，新 Host 允许安装，避免长任务被旧单次请求路径执行。无需扩展 Cloud Contract 顶层字段。
- Scope remaining: all-variant quality/speed acceptance, UI variant selection, public signed contracts and new model Package. Existing published 0.10.0 artifacts remain unchanged. Plan: docs/ai2apps-h3-avatar-technical-plan.md.

### NXR-AGENT-WINDOW-PLANNER-20261006
- Status: implemented; supersedes NXR-LOGIN-POPUP-HANDOFF-20261006 keyword-based pause/closure gate.
- Related windows are discovered through native BiDi originalOpener relationships and read with the shared cleaned DOM client. The planner receives original/related documents and opened-window evidence, chooses the observed browsing context, and decides user assistance from document state. No login keyword pause or mandatory popup closure remains.
- Runtime rejects unrelated/closed context selections and blocks repeated identical clicks while related windows are open; credential input protection remains. Assistance polling forwards changed document evidence back to the AI rather than declaring login successful.
- Validation: targeted JavaScript window/input/tab and assistance-monitor tests, JavaScript syntax checks, Python login planning API regression.
- Activation: restart exact app-dev Local for Python planner changes, refresh Agent Sidebar for static client changes. Live Weibo login/publication acceptance remains pending.

### NXR-PROFILE-LAUNCH-FASTPATH-20261006
- Status: implemented and activated in fixed App-Dev.
- Native Shell uses complete authenticated Local Profile metadata directly when opening/focusing a browser. Removes the redundant default-Profile actor query and sequential account-status fetch from the launch critical path; legacy metadata-free requests retain their compatibility lookup.
- Local broker logs queue, Shell handling and total handoff milliseconds without account/Profile names or credentials. Timeout errors now distinguish an unclaimed request from one accepted by Shell.
- Validation: 3 native Shell harness tests (including a never-resolving account query), JavaScript syntax check, 7 Profile API/Test Center regression tests and 2 timing-log tests passed.
- Fixed App-Dev rebuilt through build-app-dev-environment.sh, archived previous bundle, passed verify-release-app.sh and codesign --verify --deep --strict. Confirmed app-dev/cloud/development/source-root contracts, packaged fast path, and live title AI2Apps-App-Dev: App-Dev 127.0.0.1:60134.
- Live default Profile launch succeeded: queue 2927.6 ms, native Shell handling 73.6 ms, total handoff 3001.2 ms (request 5dcfcb691f70b46fc31abfb905e165cb, 2026-10-06 05:08:33). Browser New Tab visibly opened. This is one measured post-change launch, not a controlled before/after benchmark; remaining queue/startup variability is separately observable.


### NXR-AGENT-TYPED-PARAMETERS-20261006
- Status: implemented and activated; live empty-page image-publication acceptance passed after app-dev Local restart (port 51394, PID 1355).
- Exploration planner requires a concrete assistance_kind for needs_user, repairs preview/ordinary approval requests, and explicitly self-checks authorized compose/upload/publication steps. Existing sensitive-input, CAPTCHA, legal and consequential-action gates remain.
- Recorded compose/search values become post_text/query with type, title and description. Upload filenames no longer become redundant text inputs; upload steps bind a variable-length attachments file array. Re-inference upgrades generated VALUE_n fields and legacy file bindings while preserving still-used reference parameters.
- Parameter definitions offer file and file-array types and descriptions. Run editors provide image/video preview cards, add/remove files, multi-select file/Gallery selection and array item editors. Owner-bound metadata resolution validates each stored file; supplied paths are not trusted.
- Validation: 17 Python parameter/attachment/upload/planner regression tests and 19 Node native-upload/array/confirmation tests passed; JavaScript syntax passed. Live App-Dev Sidebar shows parameter description field, file-array type and its dedicated multi-file editor; legacy single attachment displays preview and removal controls. Live acceptance on 2026-10-06 18:06 started at about:newtab, automatically navigated, uploaded 封面参考.png, entered exact post_text, sent once, and verified the new post with its image; no ordinary-operation confirmation or login handoff occurred. Review v2 approved for recipe arec_2186303385334c9a83261d8fb7f189fa. Published evidence: https://weibo.com/7015980724/RlqUV0TbW. Dedicated attachments file-array editor and post_text type/description verified live. One transient textarea not_found recovered automatically; planner performed three repetitive pre-send inspections.

### NXR-AGENT-BLANK-NAVIGATION-20261006
- Status: implemented and activated; live navigation and image-publication acceptance passed after exact app-dev Local restart.
- Live empty-page image-publication test exposed broad current-page normalization dropping its only open step. Removal is now limited to a redundant same-URL initial open in a multi-step HTTP(S) recipe. Blank-page navigation is preserved.
- Planner distinguishes open navigation from page_access consent/access handling; executor rejects page_access carrying a navigation URL rather than recording false success. Exploration failures display provider/preflight diagnostics already supplied by the API.
- Validation: actual Source normalizer/compilation regressions (2 passed), JavaScript syntax check. Earlier pre-restart test stopped after no-op page_access retries without publication. After restart, open from about:newtab succeeded; the authorized one-post test completed at https://weibo.com/7015980724/RlqUV0TbW, with exact text and supplied image visually verified. No duplicate publication; generated recipe Review v2 approved. Replay of the saved recipe was not run to avoid another post.

### NXR-AGENT-REVIEW-LIFECYCLE-20261006
- Status: implemented; Sidebar static refresh applied; Python projection activation and final live verification pending exact app-dev Local restart.
- Live investigation confirmed recipe arec_2186303385334c9a83261d8fb7f189fa was already committed at revision 3 into adraft_85ac9c7f5be441199c099ce89b8d6a70. Review projection incorrectly mapped committed to awaiting_review, and the pre-commit exploration checkpoint restored the stale Recipe. The repeated approval conflicted with the committed repository state.
- Preserve approval for tested and committed recipes, expose recipe_status, and make approving the same already-approved revision idempotent. Sidebar renders committed as added to website Agent, disables repeated approval/revision/inference and hides duplicate commit actions. Approval and commit synchronize durable exploration checkpoints; restored checkpoints reconcile with the current server status.
- Approval buttons display submitting progress. API failures scroll their message into view rather than hiding it above a long Review panel.
- Verification: 3 Node lifecycle/checkpoint/error-feedback regression tests, 1 Python actual Review projection regression, and JavaScript syntax check passed. Existing posted Weibo was not changed; no additional publication performed for this fix.

### Local event-loop blocking investigation (2026-10-06, NXR-LOCAL-LOOP-BLOCKING-20261006)
- Status: implemented and activated in app-dev Local PID 10531 / port 57055. Watchdog captured repeated provider_status → ModelShareProviderManager.status → _eligible_model → resolve_package_model → list_package_models stalls, including synchronous SQLite service/package reads and checkpoint validation. Status now scans the catalog once and reuses eligibility/shareability results; GET projection runs in a worker thread. No stale-cache or authorization changes. Bounded watchdog records only Python file/line/function locations, no locals/payloads, at most once per 30 s.
- Validation: model-sharing regression plus concurrent slow-status/health tests pass. Live 15-sample health latency 1.8–36.7 ms; Helper stayed ready; no blocked-loop warnings in the first 2m42s after activation. CPU spot sample 10.6% versus 87.6% before investigation, indicative rather than a controlled benchmark. No Desktop rebuild or production publication; long-running/multi-client acceptance remains a future release check.


### NXR-AGENT-TEST-PARAMETER-LABEL-20261006
- Status: implemented. Agent parameter editor heading changed from 本次运行参数 to 测试运行参数; matching English label is Test run parameters.
- Validation: both localization JSON files parse successfully and the shared label key matches the requested text. Static localization change needs Sidebar refresh only.


### NXR-AGENT-EDITOR-COMPILED-STEPS-20261006
- Status: implemented. Saved Agent editor loads persisted generations and shows complete compiled step IR under each source step. Active generation takes precedence; selection uses capability and step IDs rather than position. Missing output is explicit; edits or source revision mismatch mark the displayed output as previous compilation. Successful compilation updates the display.
- Validation: 4 Node generation-selection, legacy Source-only compilation, stale-output and draft-navigation isolation tests passed; JavaScript syntax and localization JSON checks passed. Live App Dev Sidebar refreshed on port 61916: reopening the saved Weibo Agent compiled its Source-only revision and displayed all 8 steps with full compiled IR. No Agent run or Weibo publication occurred. Save now compiles persisted Source for inspection; this does not activate the generation. Static Sidebar refresh is sufficient; no Local restart or Desktop rebuild needed.

- NXR-AGENT-EDITOR-COMPILED-STEPS-20261006 follow-up: compiled step IR now uses native details/summary, collapsed by default and expandable by clicking its heading. Missing compilation remains plain status text. JavaScript syntax check passed; static refresh only.

- NXR-AGENT-EDITOR-COMPILED-STEPS-20261006 follow-up: step cards also use native details/summary, collapsed by default, showing only name and operation description. Expanding reveals existing editing/actions and the independently collapsed compiled IR. Summary follows name/description edits. JavaScript syntax and 4 compilation display regression checks pass; static refresh only.

### NXR-AGENT-STEP-EXECUTION-OPTIONS-20261006
- Status: implemented. Every Sidebar step now exposes compile enablement and Simple/Standard/Complex AI strength. Enabled maps to adaptive execution (compiled action first, bounded AI recovery on failure); disabled maps to interpreted execution (fresh cleaned DOM and related windows drive a bounded AI action loop). Browser-step tier metadata persists into IR; interpreted goals need no deterministically recognizable operation. Generation validation/security envelopes remain mandatory. Existing semantic ai.* steps and agent.call retain their runtime contracts.
- AI planning uses the chosen tier without automatic escalation, resolved arguments and supplied attachments, fresh state before each action, and prior failure evidence to avoid repeating partially completed publication/upload. Restricted/needs_user outcomes do not trigger automatic recovery; previews do not invoke AI; recovery stops after 8 actions. Model/API errors return explicit retryable evidence.
- Validation: 7 Node tests passed (including 4 existing compilation-display cases); 9 Python compiler/model-selection regressions passed. JavaScript syntax and targeted diff whitespace checks passed. No live Weibo publication or full browser acceptance performed. Imported Python/API changes require app-dev Local restart from Helper, then Sidebar refresh; no Desktop rebuild is required.

### NXR-AGENT-EDITOR-CONTEXT-LEASE-20261006
- Status: implemented. Agent editor now holds the existing native Sidebar context lease throughout editing, including asynchronous saved-draft loading. Editor and execution leases are independent: completing a test does not release an open editor; closing the editor does not release an active test. Individual-step tests also hold an execution lease until completion. Context events received while protected are deferred instead of clearing run/exploration state, and the latest deferred context applies when both leases are released.
- Behavior: editing/testing remains bound to the originating tab; related windows opened by the Agent remain available through existing BiDi window observations. Closing the editor after testing restores normal active-tab following. Explicit Sidebar refresh remains a reload escape hatch.
- Validation: 10 Node checks passed (3 new lease/context protection cases plus 7 compilation/execution regressions); JavaScript syntax and targeted whitespace checks passed. No native/browser build changes and no live browser acceptance in this turn. Refresh Sidebar once to load the static update; no Local restart required for this change.

### NXR-AGENT-CONDITION-BRANCHES-20261006
- Status: implemented. Condition/classifier steps show true, false and failed transitions; ordinary steps retain success/failed. Compiler accepts string outcomes true/false; classifier routes each explicitly, with legacy success-compatible true routing. Model failure and malformed classifier output follow failed instead of false. Planner documentation now describes the distinct boolean branches.
- Loop correctness: repeat visits to ordinary AI data steps use fresh per-iteration call IDs, preventing stale model-result reuse. Existing backward transitions and the 100-action cap remain; dedicated counters, foreach/index variables, continue/break and structured loop editing are not implemented in this item.
- Validation: 7 condition/loop Python tests, 9 compiler/model-selection Python regressions, 4 result-reading regressions, and 10 Node Sidebar editor/execution tests passed. JavaScript syntax and targeted diff checks passed. No live browser test/publication. Restart app-dev Local from Helper and refresh Sidebar for Python/runtime changes; no Desktop rebuild required.

### NXR-AGENT-LOCAL-VARIABLES-20261006
- Status: implemented. Capability-local JSON-schema variables now support typed defaults or input-derived initial expressions, deterministic assign/condition steps, typed vars bindings and array indexing. Compiler validates declarations/expressions and preserves variables into capability IR; planning/model Source normalization understands the new operations. Browser exploration is explicitly restricted from proposing pure local workflow steps. Invalid capability exports now report compilation errors instead of raising IndexError.
- Runtime: restricted AST interpreter, no eval/exec or browser/model calls for local steps. Assignments commit atomically; conditions return true/false/failed. Replay rebuilds local state from fixed IR/input and recorded actions without repeating submitted browser actions. Child invocations initialize isolated variables. Existing 100-step budget remains; expression, variable count and JSON data limits bound local work.
- Sidebar: selectable step types; variable name/type/title/description/default-or-expression editor; dedicated assignment rows and condition expression/branch fields; local variables in browser input binding and Agent-call mapping. Pure local single-step preview/run and initial-variable APIs are owner-scoped, schema-checked, and do not mutate saved Source. Test state can be reset. Source/IR and legacy capability migration retain variable definitions. AI steps retain selected tier and instruction/schema editing; ordinary compilation/fallback contracts remain.
- Validation: 47 Python tests passed across local variables/API, replay, child scope, conditions, compilation modes, calls and model selection; 14 Node tests passed for local editor/bindings, saved compilation, tab leases and execution options. JavaScript syntax, localization JSON parsing and targeted diff whitespace checks passed. No live browser acceptance or publication in this turn. Documentation: ai2apps/docs/agent-local-variables.md. Restart app-dev Local from Helper, then refresh Sidebar; no Desktop rebuild required.
- Scope: loops use explicit condition/assignment/backward transitions; no standalone foreach visual container or structured break/continue editor is added.

### NXR-AGENT-GOOGLE-LOOP-ACCEPTANCE-20261006
- Status: implemented and live verified. Nested dict/list variable bindings now retain capability-local vars; browser read_results accepts an explicit typed items binding without overwriting it from earlier extraction. Compiler validates explicit items, new_tab and bounded delay_ms. Sidebar forwards tab/pacing options to the existing BiDi SDK.
- SDK: Google search H3 results include external destinations and opaque /goto links, while Google navigation links remain excluded. Optional temporary-tab reads use native BiDi create/navigate/close and restore the originating context; cleanup runs even on read failures. Existing same-tab reading remains compatible. Static SDK cache version advanced.
- Live acceptance: app-dev run run_638f864da57f4f3b9b0a9b2801cda4a4 completed in approximately 44 seconds. Google query site:developer.mozilla.org WebDriver BiDi, 3 result pages read (1110, 444, 2324 text characters). Variable index ended at 3; check outcomes true/true/true/false. Native tab inventory confirms no MDN result tab remains. Each browser action waited 2500 ms; pages waited 3000 ms before reading and 3000 ms after closing. Evidence: ai2apps/docs/agent-google-loop-test-20261006.json.
- Validation: 40 Python tests and 15 Node tests passed; JavaScript syntax checks passed. Temporary live UI hook and served test files removed; reproducible driver retained under ai2apps/tests/fixtures/google_loop_test_driver.js. App-dev Local restarted through authenticated Helper control for Python fixes. No Desktop build or publication.

### NXR-WEB-AGENT-FOUNDATIONS-V1-20261007
- Status: implemented. Eight version-pinned global capabilities are discoverable even from a blank page: web.ensure-login, web.read-page, web.extract-list, web.fill-form, web.upload-files, web.wait-state, web.clear-blockers and web.light-explore. Existing agent.call resolves trusted built-in IR, typed defaults/input/output schemas and generation pins without owner-store lookup or caller-supplied executable IR. Generation/exploration prompts describe selection, site-specific preference, authentication prerequisites and explicit outcome/context handling.
- SDK: native BiDi temporary-tab reading/stability waits, explicit context tracking, cleanup/restore, public-address validation including redirected URLs, and Readability with cleaned-DOM fallback. Reuses the exact existing licensed Readability source through client-side script.callFunction. No semantic browser backend or JSWindowActor interaction added.
- AI primitives: blocker cleanup repeatedly observes and classifies before each observed dismissal, bounded by max_dismissals and existing total step budget. Cookie rejection/necessary-only and dismissal of promotions/payment offers preferred; no payment, legal acceptance or paywall bypass. Login/CAPTCHA uses concrete durable assistance. Light exploration and form preparation restrict permitted actions and actual-target labels against publishing, purchasing, deletion and submission. Upload uses existing authorized Gallery asset arrays and hidden file-input support.
- Validation: 56 Python tests passed across foundations/calls/variables/conditions/model selection, followed by 14 foundation tests passing after adding two blocker failure/budget cases (58 distinct Python cases covered overall). 28 Node tests passed across SDK foundations/result reading and Agent call/editor/execution/local-variable regressions. JavaScript syntax and targeted whitespace checks passed. App-dev Local restarted through authenticated Helper; live fixed Shell recovered with title AI2Apps-App-Dev: App-Dev 127.0.0.1:57973 and connected state. No live end-to-end acceptance of all eight capabilities, Desktop build, or publication.
- Documentation: ai2apps/docs/web-agent-foundations-v1.md. SDK/Sidebar static refresh loads the client changes. First version uses AI for semantic form/blocker/exploration judgments; extraction heuristics target search/article lists, and complex site lists should use website capabilities.

### NXR-WEB-FOUNDATIONS-GOOGLE-ACCEPTANCE-20261007
- Status: live verified for web.extract-list and web.read-page. Explicit Google workflow compiled with version-pinned agent.call steps, typed result array, local index and conditional loop. Run run_3885e5e6af68453890be4417185604ba completed in approximately 38 seconds; extracted 5 results and read the first 3 MDN documents, 873/3656/2205 characters. All three used Readability, returned distinct read_context IDs and tab_closed=true, and restored the same Google context. Loop outcomes true/true/true/false; final index 3.
- Native accessibility inventory verifies only original New Tab and Google search Tab remain. Temporary served test script and Sidebar injection removed; refreshed native Sidebar verifies normal Agent UI restored. Reproducible fixture retained at ai2apps/tests/fixtures/google_foundation_test_driver.js; evidence at ai2apps/docs/agent-google-foundations-test-20261007.json. JavaScript syntax and targeted whitespace checks passed.
- Scope: test exercises real runtime child capability resolution and client SDK execution with an explicit workflow, not AI automatic Agent generation. No blocking overlay, login, CAPTCHA or paywall appeared, so those capability paths were not live tested in this run. No production publication or Desktop rebuild.

### NXR-WEB-FOUNDATIONS-BLOCKER-COMPOSITION-20261007
- Status: implemented. web-foundations/2 composes read-page as native BiDi open/retain -> agent.call clear-blockers in the returned context -> extract/close. Cleanup failure routes through a dedicated temporary-tab close step before failure. Light-explore calls clear-blockers before exploration and permits only that capability as a nested read-only AI call when new navigation reveals blockers. Catalog descriptions expose this behavior. Pinned v1 calls preserve legacy IR.
- Call compiler accepts explicit browser_context; runtime propagates it to child actions with client-side related-context authorization intact. Sidebar isolates nested call checkpoints from outer exploration calls, preventing outer run reuse/deletion. SDK phased finish/close verifies tracked context ownership, avoids repeat navigation, restores original tab and validates public destinations.
- Validation: 60 Python tests passed across foundations/calls/locals/conditions/model selection. 16 Node tests passed across SDK foundations/calls/AI execution, including phased tab handling, failure cleanup, and nested-call isolation. JavaScript syntax and targeted diff checks passed. No live blocker-site acceptance performed in this turn. Updated ai2apps/docs/web-agent-foundations-v1.md. Restart app-dev Local and refresh Sidebar; no Desktop rebuild/publication.

### NXR-WEB-FOUNDATIONS-SEARCH-ACCEPTANCE-20261007
- Status: in_progress. Real Google v2 loop completed three MDN reads through open -> clear-blockers -> read/close, restoring the search context (~62 seconds; run_3aa80fe052184209b7826798b800aca0). Evidence saved in ai2apps/docs/agent-google-foundations-v2-test-20261007.json. No actual overlays appeared.
- Weibo live testing exposed and fixed Firefox wildcard-host scope parsing, missing read-only search-input support (only observed search fields), and internal model-dispatch HTTP 403 caused by the synthetic ai2apps.internal Host being rejected by PublicDeviceBoundary. Agent model/presentation fallback dispatch now retains the actual Local base URL; external Host denial and existing authentication remain intact. AI execution preserves model failure details. Light-explore planning explicitly disallows recursive/delegating calls except clear-blockers; s.weibo.com search navigation shares the explicitly requested Weibo authorization.
- Validation so far: 39 Node tests passed; local-dispatch regression passed with PublicDeviceBoundary and external Host denial. Broader Agent Platform suite: 16 passed, 2 failed on existing unrelated normalization/privacy-expectation assertions (redundant open and cleaned text sample forwarding); those paths were not changed here. Weibo acceptance still in progress. Python API fix applied after restarting exact app-dev Local through Helper; static Sidebar refresh only for JavaScript. No Desktop rebuild/publication.

- NXR-WEB-FOUNDATIONS-SEARCH-ACCEPTANCE-20261007 completion: Weibo full-site search for 数字人 passed on run_70b811e3f1704b3abb0ddeb9d58a1558. Returned the first three post authors, summaries and exact post links; all three authors and post URLs were matched against observed cleaned-DOM items, and returned context equals the real observed context. Existing authenticated Profile reused; no login assistance, posting or likes. Evidence: ai2apps/docs/agent-weibo-foundations-v2-test-20261007.json. No actual overlay appeared; anonymous/login/blocker dismissal and automatic Agent generation were not exercised.
- Follow-up fixes: interpreted steps set verify_goal_with_ai so current-page list extraction cannot prematurely complete a larger goal; malformed planner JSON receives one bounded same-tier repair. AI extraction keeps newest structured DOM evidence, removes duplicate snapshots, preserves observed links and context, and uses valid JSON within a 40k evidence budget. This fixed the observed author omission/misattribution caused by raw JSON head/tail truncation. Temporary live-test exports/loader removed and formal Sidebar refreshed.
- Final validation: 39 targeted Node tests passed; 3 new Python regressions passed (Local/public Host boundary, malformed JSON repair + AI goal verification, and structured evidence/context preservation). Broader earlier Agent Platform run remains 16 passed / 2 unrelated existing assertions failed, as recorded above. Status: implemented with Google and authenticated Weibo live acceptance complete.


### NXR-WEBAGENT-JSON-REPAIR-20261007：统一模型 JSON 修复

- 状态：`implemented_activated_app_dev`。共享严格 JSON 解析、修复提示和两次修复预算，规划、Agent 编译/Review、结果展示及 durable ai.extract/ai.classify/ai.transform 接入。JSON 格式与结构错误共用预算，最多三次模型调用；保持所选模型。
- 修复只重新请求模型，不执行/重放浏览器动作。Durable 修复使用稳定独立 call_id，恢复时复用已完成调用，修复次数写入步骤证据；预算耗尽走既有失败分支。HTTP/模型调用失败不作为 JSON 修复重试。
- 最终相关回归 63 项通过，新增展示修复和严格非有限数字解析专项共 6 项再次通过（合计 64 个不同用例）；两项先前已记录的无关旧断言显式排除。模型升级回归更新为初次加两次修复失败后才升级。git diff --check 通过。只重启 app-dev Local，新 PID 88900、端口 53871，health HTTP 200；模型测试为坏输出替身，未声称 DeepSeek 实机验收。没有 Cloud 改动、未发布 Desktop。


### NXR-WEBAGENT-STEP-CONVERSATION-20261007：步骤 AI 对话修改

- 状态：`implemented_activated_app_dev`。步骤编辑新增独立 AI 对话区，支持多轮、模型强度、建议预览和显式应用；不自动保存/执行。
- 新增仅返回建议的 /agent-steps/revisions 接口，绑定选中能力与步骤，保留步骤名称及其他 Source，仅替换选中步骤后编译校验整个流程，接入统一两次 JSON/结构修复预算。
- 应用前比较编辑器快照，拒绝过期建议；对话文本使用 textContent，失败保留输入。10 项前端测试、8 项 Python/API/JSON 修复测试通过，JS 语法及 scoped diff 检查通过。仅重启 app-dev Local，新 PID 14170、端口 53788、health 200；/admin/static/js/agent_mini.js 返回 200 并包含新入口。未宣称真实模型或视觉端到端验收，未发布 Desktop。


### NXR-AI-BROWSER-WORKSPACE-20261008：三栏工作台与任务调度

- 2026-10-09：AI Browser 提示条改为视窗顶部 fixed 悬浮层，不随滚动、不占工作台布局空间；成功提示 5 秒、错误提示 8 秒自动关闭，重复提示重置计时，支持手动关闭并在页面销毁时清理定时器。静态资源版本更新；JavaScript 语法检查、17 项工作台测试及提示替换/超时/手动关闭验证通过。前端刷新生效，无需重建 App。

- 2026-10-09 情报中心后台编排迁移完成：公用 WebAgentInvocation + Browser Task admission、schema 87 内部程序持久化、Local Collector 原子 claim/job、后台定时和编译规则复用/验证；前端 HTTP 提交、共享 SSE 观察。旧无能力导出 Agent 自动绑定兼容入口，多能力必须明确选择；后台 Cloud 模型复用既有 actor 身份入口；取消终态禁止被迟到错误复活。总架构与 ai2apps/docs/webagent-background-migration.md 明确为全 App 共用机制。47 项 Python、9 项 Node 定向回归通过。App Dev 真实 run 84ca46ee61314ec985a90b785aa56712 在离开情报页面后完成：跳过16条、读取3篇、生成3篇、知识库同步28→31；4个子Task completed，编译复用4次、fallback/learning_calls均0、来源读取21.757秒。微博第二篇定位失败保守中断，取消后部分结果保存，不宣称所有社交站点验收成功。已重启 app-dev Local、刷新前端，未发布、未改Cloud服务端。

- 2026-10-09（in_progress）：补齐情报中心后台迁移，新增公用 `WebAgentInvocation`、持久内部程序表（schema 87，与同时进行的 visitor_spaces v86 保持连续）、Local `IntelligenceCollector`、原子 claim/job、后台定时与 actor 模型调用；前端采集改为 HTTP 提交及共享 SSE 观察。站点规则复用/漂移回退和后台候选验证、社交来源冷却/筛选纳入统一 Task。架构文档明确所有 AI2Apps App 的公用 WebAgent 机制。定向测试、真实采集及恢复验收进行中，未发布。


- 2026-10-09：情报中心旧采集入口修复 Profile 只绑定容器、不自动打开 initial_url 时无法找到专用页面的问题：按 launch 返回的 user_context/referenceContext 显式新建隔离 Tab，校验容器一致，失败关闭自建页面。JS 检查及情报浏览器/规则复用 Node 11 项通过，真实腕表频道更新验收完成：检查 20 条、跳过重复 13 条、读取及生成 3 篇；规则复用 4 次、回退/学习请求均为 0，采集耗时 13.3 秒。情报中心 collect 仍为前端编排，不能视作完整后台采集迁移完成。

- 2026-10-09：修复后台执行情报中心既有 site_extraction Agent 时新 Tab 保持 about:blank 导致 site_scope 拦截：列表规则按已授权 origin/path 初始化目标页，当前位置匹配时不重复导航；正文规则缺少 URL 时沿用规则目标。导航前后均保留作用范围检查，预检不导航。新增空页/复用/预检/越界/重定向及正文兼容回归；22 项后台与情报 Agent 测试通过。已重启 app-dev Local；原有 Fratellowatches 情报列表 Agent 真实网站验收完成，纯编译提取成功返回 20 条，未修改 Agent 配置。

- 2026-10-09：任务详情移除“查看运行记录”与常驻“打开任务页面”按钮，自动展示运行输出，避免手动读取记录把结果替换成完整内部 Run JSON。仅人工协助或中断检查时显示“前往页面处理”。静态页面刷新生效；JS 语法检查及工作台 Node 17 项通过。未重建或发布。

- 2026-10-09 后台执行迁移完成（本项此前的 in_progress 记录为历史阶段）：Local Runner 接管新 AgentRun、能力队列及 Schedule/Workflow 共用的 durable 浏览器动作；前台改为 HTTP 指令 + SSE 观察，禁用 Local-owned 任务的前端领取/执行/响应。共享原生 BiDi SDK 保留 actor/Profile userContext 登录状态，迁入导航/稳定等待、拟人输入、200K 分段、上传入口拦截、规则提取与后台模型规划；动作日志恢复已完成结果，结果未知暂停且禁止重放，人工协助/动态确认持久化。
- 原生宿主：Helper 支持无 Local HTML 的 app-shell 冷启动，使用与 Launcher 一致的私有进程/automation 描述；关闭 Shell UI 卸载 HTML、保留 protected BiDi/Profile 生命周期，重新打开固定 App 恢复前台。修复冷启动监听就绪竞态与并发启动；未复制 Cookie/数据库，未使用独立磁盘 Agent Profile替代现有登录状态。
- 验证：86 项定向 Python、28 项 Node、Swift 77 项 Testing + 2 项 XCTest 全通过；原生 AceFox 本地测试站端到端通过（200K Unicode 完整分段输入、入口点击上传、结构化列表、HTTP 客户端关闭后队列完成、SDK 断开重连）；现有 watchesbysjx 能力在关闭 Shell 后两次由 Local 完成并保存 19 条结果。仅 Helper 启动时的无 Local HTML 冷启动/BiDi 验收通过。固定 `AI2Apps-app-dev.app` 按标准脚本重建，app-dev/com.ai2apps.desktop.appdev/cloud/Development/source-root/禁用生产更新合同由 builder 验证，`verify-release-app.sh` 与 `codesign --verify --deep --strict` 通过，活体窗口标题含 App-Dev 与 Local 地址。
- 迁移文档：`ai2apps/docs/webagent-background-migration.md`。通用完整测试集仍有已有 fixture 与模型调用/JSON repair/抽取函数依赖不一致，不冒充全项目通过。未发布生产，未改 Cloud。定时任务复用后台入口，未在用户数据中新增测试 Schedule；法律同意/验证码等仍需要人工，停止 Local/Helper 或任务原页面消失会中断任务，不等同于关闭工作台。

- 2026-10-09 后台迁移继续（in_progress）：Local Runner 已接管新运行、能力队列和 Schedule 的 durable 浏览器交互；HTTP 命令 + SSE 运行观察，前端 claim/执行入口关闭；Helper 新增同一 app-shell Profile 原生宿主冷启动，关闭 UI 卸载 HTML 并保留 native BiDi 生命周期。Swift 79 项测试通过，Python/Node 定向回归进行中，尚未完成 App Dev 重建与原生端到端验收，不可标记迁移完成。

- 2026-10-09 后台迁移继续（in_progress）：新增 Local 私有共享 BiDi SDK、actor 规划服务、动作持久化日志、后台 Runner 骨架及 schema v84；尚未切换前端执行权，宿主生命周期/队列/恢复/真实浏览器验收未完成。25 项定向 Python 测试通过；未重启/重建 App Dev，未发布。

- 2026-10-09 后台迁移第一阶段，状态 `in_progress`：BrowserTask 状态与工作台事件同事务落库，SSE actor 隔离、初始一致快照、Last-Event-ID 重放、断开释放订阅；新增 Local 生命周期 TaskMonitor，独立于工作台请求更新 Run 终态/等待/失效租约。工作台取消 5 秒全量轮询，用单一 EventSource 更新任务；元数据通过主动刷新、focus 与编辑器修改通知刷新，状态消息不重复携带大输入。
- 本阶段 22 项 Python（任务/SSE/调用兼容）与 40 项 Node（工作台/拟人输入/恢复/情报中心）定向检查通过；新增后台无 HTTP 查询投影测试。未重启、重建或发布，未做真实 AceFox 无 Shell 运行验收。浏览器动作仍由前端执行；Helper 独立磁盘 Profile 与 Shell userContext 不是相同登录态，禁止直接替换或复制状态。完整后台动作、Profile 宿主、Schedule 与人工协助迁移尚未完成，见 `ai2apps/docs/webagent-background-migration.md`。

- 2026-10-09：长文本输入改为混合分段：500 字以内保留键盘输入，超过阈值每段最多 8192 Unicode 字符通过 BiDi script.callFunction 调用浏览器 insertText 编辑命令；拟人模式仅保留最多 16 个逐字字符和 120–300ms 段间停顿，快速模式直接分段。系统剪贴板不读写，纯文本不会按 HTML 执行。输入前校验编辑器与 maxlength，绑定焦点/节点，逐段检查普通输入框内容，最终校验后才 Enter；失败不自动重复，finally 清理绑定。验证：长文含 Unicode/200K 模拟输入、截断/焦点变化/maxlength、短输入、BiDi 恢复与情报规则复用 Node 19 项通过。真实网站富文本兼容性未实测；不支持 insertText 的编辑器明确失败。静态 SDK 更新，刷新 Shell 即生效，无需重启 Local/重建 App。

- 2026-10-09：Domain 新增 Agent 快速/拟人执行模式（用户隔离持久化，schema 83，默认拟人）。共享 BiDi SDK 按当前网站读取配置，拟人鼠标采用 smoothstep 加减速分段移动，输入按 Unicode 字符分批逐字执行、删除 2000 字截断，并加入操作间隔；上传先拦截文件控件 click/showPicker，点击可见上传入口后向捕获控件提供文件，超时/异常清理拦截且不自动重复点击。长文暂完整分批打字，不触碰系统剪贴板。快速模式省去额外间隔与逐字等待。验证：浏览器/工作台/情报复用 Node 31 项、Domain API/情报规则 Python 12 项通过；上传真实站点端到端尚未验证。需重启 App Dev Local 应用迁移并刷新页面，无需重建 App。

- 2026-10-09：能力新增独立“工作目标/指导”，与简短能力说明分离；空白回退到 Agent 指导。编译时将有效指导固化到对应能力及步骤，浏览器解释执行、失败回退和 AI 数据步骤使用该上下文；旧单流程转换保留指导。验证：能力指导/元信息/基础能力 Python 20 项通过，编辑器与运行上下文 Node 测试通过。Python 更新需重启 App Dev Local，编辑器刷新即可加载。

- 2026-10-09：能力运行参数页顶部增加“返回 Agent”按钮，按当前能力所属 agent_id 返回对应详情，不依赖之前选中的 Agent；按钮不提交表单、不启动任务。JavaScript 语法检查通过，刷新 Shell 生效。

- 2026-10-09：新建能力改为原生模态对话框，下拉选择标准或自定义能力；仅自定义显示名称/说明输入，名称必填，确认后添加并关闭，取消/Escape 不修改现有能力。12 项能力交互与 Recipe 编辑 Node 测试及 JS 语法检查通过，刷新 Shell 生效。

- 2026-10-09：能力模板选择默认隐藏，点击“＋新能力”才展开创建区域，明确提供“创建能力”和“取消”；仅选择模板不修改当前能力，取消不变更 Source，创建后关闭区域。4 项能力编辑交互测试及 JS 语法检查通过，刷新 Shell 生效。

- 2026-10-09：修正能力名称/说明编辑、删除按钮及标准类型选择误放入隐藏 Review 面板的问题，移至共享 Agent 编辑器能力选择下方，普通编辑与探索审核均可见；新增模板归属回归验证，3 项能力编辑测试通过。刷新 Shell 生效。

- 2026-10-09：AI 浏览器侧栏 Agent 和 Domain 卡片“打开”统一进入详情页，展示 Agent 状态及全部能力，显式选择运行/编辑；未启用 Agent 提供启用入口，通过现有编译校验后启用 generation，不自动运行任务。制作草稿提示先审核保存。多能力不再默认打开编辑器。16 项 workspace Node 测试通过；静态资源刷新 Shell 生效。

- 2026-10-09：统一 Agent 编辑器支持能力名称/说明编辑、确认删除及旧单能力 Source 无损升级；新增能力从既有内置能力目录选择或自定义，标准项带入输入输出 Schema 与固定版本 agent.call 步骤，避免重复导出同名能力及新增 ID 冲突。9 项 Node 能力操作/Recipe 编辑测试及 JS 语法检查通过。刷新 Shell 生效，无需重建。

- 2026-10-08：Agent 创建与编辑字段统一为“工作目标/指导”（英文 Work goal / guidance），创建提示明确可提供步骤、预期结果和参数指导；中英文 JSON 解析验证通过。仅本地化文案修改，刷新 Shell 生效。

- 2026-10-08：创建 Recipe/探索沉淀时使用系统 work_simple 模型概括能力名称与说明，保存 capability_metadata 并用于网站能力转换；完整工作目标独立保留，不受命名影响。命名响应校验，模型失败返回可重试错误；无低强度模型时沿用原始元数据。能力元数据、附件沉淀、Recipe 编辑及目标约束相关 23 项测试通过；Python 修改需重启 App Dev Local。

- 2026-10-08：Agent 编辑器展开步骤卡片外框从 1px 加粗至 2px，并加深为 #a8a29e，突出编辑区域；折叠状态保持原样。仅 CSS 与缓存版本修改，刷新 Shell 生效。

- 2026-10-08：统一 Agent 编辑器步骤卡片名称增加本地化序号前缀“步骤-x: ”/“Step-x: ”，重排后按当前顺序更新；仅显示层修改，不改变步骤名称及引用。JavaScript 语法检查通过，刷新 Shell 生效。

- 2026-10-08：Domain 独立持久保留，删除最后一个 Agent/制作草稿不再移除网站；空 Domain 详情显示“删除 Domain”，确认后显式删除，服务端原子检查非空网站并拒绝删除。数据库迁移 82 补全历史网站登记；后续工作台读取及归档保留登记，显式删除后不再从历史归档重建。验证：browser workspace / recipe archive Python 9 项、workspace Node 15 项通过。App Dev 需重启 Local 并刷新 Shell，无需重建。

- 2026-10-08：移除左侧每个 Domain Agent 列表末尾重复的“＋ 新建 Agent”，节省导航垂直空间；保留 Domain 主面板“创建 Agent”。已检查目标按钮唯一移除且主面板入口保留。静态 workspace-22，仅刷新 Shell。

- 2026-10-08：补齐可运行（active）网站 Agent 的 Domain 删除入口，原显示条件只覆盖 editing/compiled。active 使用“删除 Agent”与带名称确认，删除前读最新 revision 后复用 owner-scoped archive API，维持 CAS 与重复请求保护。工作台 14 项 Node 测试通过，覆盖 active 按钮条件、确认名称与归档版本。静态 workspace-21，仅刷新 Shell；本次未删除用户现有 Agent。

- 2026-10-08：修正 Domain 中已提交网站 Agent 的草稿误标。compiled 网站 Agent 显示“已编译 · 待启用”，删除入口与确认文案为“删除 Agent”；只有 Recipe/编辑草稿称“删除草稿”，active 显示“可运行”。不改变提交或启用语义。工作台 13 项 Node 测试及 JS 语法检查通过。静态 workspace-20，仅刷新 Shell。

- 2026-10-08：修复通过 Review 后点击加入网站智能体反复使审核失效。共享编辑器挂载时记录表单标准化后的 Source 基准，以对象键排序/数组原序签名判断真实修改；显示时补齐默认字段与 JSON 键顺序变化不再触发 PATCH/版本递增。同步编辑的审核提示采用同一判定；实际编辑仍保存新版本并使审核失效。Recipe 编辑/Review 生命周期 10 项 Node 测试及 JS 语法检查通过，新增默认字段、键序和审核后实际 commit 请求测试。静态 agent-step-chat-66，刷新 Shell 生效，无需重启/重建。

- 2026-10-08：修复 Domain 草稿删除偶发 revision changed。删除确认前重新读取 actor-scoped 当前草稿记录并使用最新 revision，避免后台轮询更新后卡片回调仍持有旧对象；同草稿请求去重并禁用按钮。确认期间真正发生版本冲突仍保持 CAS 保护，不自动重试删除，刷新列表并显示中文操作提示；已不存在的 Recipe 仅刷新。工作台 12 项 Node 测试及 JS 语法检查通过，覆盖旧对象/新版本、取消、重复点击与 409 不重试。静态 workspace-19，仅刷新 Shell 生效。

- 2026-10-08：Domain 草稿卡片增加“删除草稿”按钮及带名称的确认框，取消不发请求。Recipe 新增 actor-scoped `/agent-recipes/{id}/archive`，校验 expected_revision，使用既有 discarded 状态移出列表并保留原始 Source；拒绝删除 committed Recipe。普通未启用草稿复用已有 archive API。删除后移除同草稿编辑 iframe 并刷新 Domain；已启用 Agent 不显示此入口。工作台 11 项 Node、Recipe 删除/编辑 3 项 Python 与 JS 语法检查通过。静态 workspace-18；需重启 AppDev Local 并刷新 Shell，无需重建。

- 2026-10-08：修复探索制作保存后 Domain 中不可见。AI 浏览器工作台同时读取 `/agent-recipes`，将未提交的制作草稿按 site_key/site_scope 列入 Domain 导航与卡片，标注“制作草稿 · 待审核”，点击通过 recipe_id 恢复原共享编辑器（参数/变量/步骤/Review），避免误当普通 draft_id。已有 committed_draft_id 的记录不重复显示；未改变 Review/提交流程。工作台 10 项 Node 测试及 JS 语法检查通过，新增保存 Recipe 列出和恢复测试。静态缓存 workspace-17，只需刷新 Shell。

- 2026-10-08：AppDev 13:04:45 日志确认探索调用 `/agent-calls/runs` 被旧试运行占用的 Default Profile 并发名额拒绝。补齐该接口的 ValueError 映射，返回 422 `invalid_agent_invocation` 和具体中文原因，避免变成未处理 500 / Internal server error；保留 Profile 并发隔离，不自动取消其他任务。新增真实 API 容量冲突回归测试；WebAgent 调用与工作台共 16 项测试通过。既有目录测试明确设置双调用容量，独立容量测试保持默认每 Profile 单任务。Python 变更需重启 AppDev Local 生效，无需重建。

- 2026-10-08：修复探索后试运行复用已失效 BiDi Tab（`no such frame`）的问题。新试运行/探索前使用原连接的 `browsingContext.getTree` 验证缓存上下文，缺失时仅在所选 Profile 创建新 Tab；并发准备共用同一 Promise，禁止采用无关页面。Mini 编辑器同步更新上下文并释放旧客户端。执行中浏览器异常回报 pending interaction 为 failed，避免残留 waiting_input；不在另一页面自动重放执行中动作。静态资源版本 agent-step-chat-65 / workspace-16。
  - 验证：Node workspace、recipe editor、AI list output、Profile selection、browser request failure 共 19 项通过；两个 JS 语法检查通过。尚未在真实 AppDev 页面完成端到端复测；静态修改只需刷新 Shell，无需重建 App。

- 2026-10-08 等待状态与 AI 步骤结果续修：工作台 waiting_input 根据 pending interaction 区分等待浏览器响应/等待协助/等待确认，人工协助显示具体 prompt，不修改底层 run 生命周期。修复 executeAIStep complete 丢弃真实执行结果、固定返回当前 URL 的旧缺陷；优先回传实际成功动作结果，提取列表步骤保留 authored_operation，若只观察到 DOM 而未产生结构化 items，则完成前执行列表提取，已有 items 不重读。真实 checkpoint 确认本次 source 是 extract_list，但解释执行输出仅 outcome/context/url；最近完成判断改动暴露此原有路径。10 项 Node 工作台/AI 结果与 16 项 Python 等待分类/编译/Source 回归通过，JS 语法及 scoped diff 检查通过。静态缓存更新；需重启 Local 并刷新，旧 IR 需重新编译；未修改已有 Recipe/运行结果，真实页面试运行待验证。

- 2026-10-08 open 页面就绪等待：原生 BiDi navigate(wait=complete) 返回后默认再等 3000ms，并调用共享 SDK 稳定性等待（最多额外 10 秒，要求非空页面；不能把稳定的空文档判为就绪）。open 编译结果默认 delay_ms=3000，可显式覆盖 0–30000ms，生成规范化保留显式值；旧 IR 执行也使用相同默认。4 项 Node 导航顺序/默认与覆盖/空文档测试及 12 项 Python 目标/编译/Source 编辑回归通过，JS 语法与 scoped diff 检查通过。Mini-Entry/SDK 缓存版本更新；静态刷新加载执行逻辑，编译/API 默认变更需重启 Local。真实网页端到端等待效果待复测，无 Cloud 或原生重建。

- 2026-10-08 重复基础能力提取续修：真实 app-dev 探索记录出现两个不同名 web.extract-list 调用，参数和 17 条完整结果完全相同，仅轮播使 DOM 计数改变。沉淀去重覆盖 builtin:web:extract-list，按相同参数、相同结果及结果 page_url 判定，不依赖名字/自然语言 target/DOM 长度；有页面或实际结果变化仍保留。相同提取再次被规划时，在执行前单独进行目标完成核对，继续必须提供目标原文中的未满足要求与证据缺口，禁止以轮播/重新确认作为理由。已只读复放本次四步 checkpoint，最后一对判为重复；28 项目标/模型调度/附件沉淀回归通过，scoped diff 检查通过。真实模型重跑待验证，未改用户已有 Recipe/Checkpoint，Python API 需重启 app-dev Local 生效，无原生重建/Cloud 改动。

- 2026-10-08 探索完成条件修正：移除依赖“当前页面”等措辞和字段名集合的自动完成捷径，统一由目标、范围、输出及执行证据进行 AI 判断；结果证据增加非空数量、字段类型与有限样本，约束已满足目标后立即结束。移除直接生成 Prompt 强制正文读取/可选总结、假设页面就绪，以及按措辞自动删除显式导航的处理；Review 允许 URL 参数/变量绑定。沉淀仅保守合并紧邻同名、同目标/参数（允许重述已有字段）、页面指纹衔接一致且实际结果完全相同的列表读取，页面/结果变化仍保留。28 项目标/探索模型调用/附件沉淀/Source 编辑 Python 回归通过，scoped diff 检查通过；真实模型探索待复测。Python API 修改需单独重启 app-dev Local 生效，无 Cloud 或原生包改动，不自动改写既有用户 Agent。

- 2026-10-08：修复 Recipe 全流程 AI 修改 Prompt 强制诱导可选 read_results/摘要的问题，改为仅按工作目标与本次反馈修改，列表目标提取后直接结束并返回列表；明确 done/failed/pause 为系统结束目标，不可作为步骤名。编译器增加 reserved_step_name 硬校验，多能力复用同一校验；无效旧流程仍允许提交 AI 修改修复。统一编辑器新增可见可编辑工作目标（source.description），保存后作为修改 Prompt 的当前权威目标，同时保留原始目标上下文。12 项前端、6 项 Python 测试通过，语法/diff 检查通过。Python Local 重启及页面刷新后生效；未自动改写用户现有错误流程，实机新模型修改待复测。

- 2026-10-08：工作台 Agent 编辑器新增带二次确认的“重新开始”。已保存草稿重新读取，探索制作清除当前流程/测试结果并返回目标输入，保留目标/附件/Profile；确认后只取消本编辑器关联运行，取消失败保留编辑器内容，旧探索 checkpoint 标记 cancelled 防止自动恢复。忙碌期间禁用按钮；不删除已保存 Agent。20 项相关 Node 回归通过（最后创建页标题补齐另跑 4 项重置回归），JS/diff 检查通过。静态刷新生效，真实确认/取消操作待实机复测。

- 2026-10-08：AI 浏览器探索制作/编辑测试新增浏览器 Profile 选择，继承工作台初始选择，显示 Profile 名称；显式浏览器动作时按所选 Profile 延迟创建独立测试页。同一编辑器按 Profile 隔离并复用会话，切换保留 Agent 内容，断开旧客户端并清除局部测试状态；运行/探索未结束时禁止切换。Recipe 和普通试运行传递 profile_key 至并发管理。16 项前端测试、双语 JSON/JS 语法及 scoped diff 检查通过；静态刷新生效，无需重启或重建，真实多 Profile 登录状态实机复测待完成。

- 2026-10-08：探索 Recipe 试运行完整化 run_id 调度回执后再驱动浏览器，并保留已创建运行 ID，重复点击继续非终态运行而非占用第二个并发名额；传递实际 profile_key。Recipe 运行并发 ValueError 返回可读 409，不再暴露 500；操作错误滚动到提示。8 项前端及 2 项 API 回归通过。App Dev 现场旧 run_513a18dad700489fba65a0a42444c999 仍 waiting_input，第 0 步原生浏览器交互待处理；点击继续尚未推进，不宣称实机恢复。JS 刷新、Python Local 重启后生效，无需原生重建。

- 2026-10-08：修复探索制作审核重绘时 replaceChildren 移除共用 Agent 编辑器，导致 AI 调整返回新版本后步骤/参数消失并显示 null。保留编辑器 DOM，跨版本更新内容，同版本保留未保存编辑；脚本缓存版本更新。7 项 Recipe 编辑器/审核生命周期 Node 测试及 JS 语法检查通过，含模拟真实 DOM 查询的跨版本回归；静态刷新生效，无需重启，实机完整调整流程待复测。

- 2026-10-08：探索 Recipe 审核复用普通 Agent 的完整编辑面板，统一参数/局部变量/步骤类型/图跳转/编译折叠/AI 单步修改及调试；移除独立编译前后文本卡片与重复测试参数表单。新增受认证 PATCH /agent-recipes/{id}/source，按 owner/revision 保存完整 Source、重新投影编译结果并清除旧批准，允许保存待修复配置但批准/运行仍要求编译有效。审核/整体 AI 修改/试运行/提交前同步编辑内容，试运行用统一输入并支持结束返回 Shell；单步调试使用未保存临时 Draft，未审核不进入已保存菜单；workspace recipe_id 恢复统一编辑器。20 项 Node 回归和 1 项 Python API 测试通过，覆盖共享面板/未保存编辑保持/完整参数变量图保存/旧批准失效/乐观锁/非法跳转及试运行输入。资源 agent-step-chat-57；需重启 App-Dev Local 并刷新，当前用户审核现场未刷新；实机新界面及完整模型调试链路待复测。Test 下次重建。

- 2026-10-08：Domain 创建智能体改为独立宽版布局，仅 workspace_create 生效：Domain/创建标题说明、模型标签与选择同行、大任务目标输入、附件按钮并列、主按钮靠右；窄容器自适应，浏览器侧栏保持原布局。资源 agent-step-chat-56；8 项工作台/创建入口测试、JS/diff 检查通过；App-Dev 实机刷新并打开 watchesbysjx.com 创建页，AX/截图确认新布局完整展示且未启动探索。

- 2026-10-08：Domain 新建 Agent 先输入自然语言目的与测试附件，再显式启动探索制作；不预建空草稿、不提前打开浏览器，复用既有探索/提炼/审核/提交编辑流程。已保存 Agent 编辑入口不变。8 项工作台/创建入口 Node 测试与 JS/diff 检查通过，未实测模型探索。资源 agent-step-chat-55/workspace-13；App-Dev 刷新生效，Test 下次重建。

- 2026-10-08：网站提取规则 origin/path 独立可选，缺省、null、空字符串或空白不限制对应范围，直接提取任务当前页面；填写时继续精确校验，显式 path 对列表/正文统一生效。保留 selector 与规则格式校验，不更改已保存规则。SDK 14 项回归通过，新增实际执行 DOM 提取函数的空范围/单独范围/范围不匹配覆盖；JS 语法及 diff 检查通过。编辑器缓存 browser-foundations-18，App-Dev 刷新生效，Test 需下次重建。

- 2026-10-08 将编辑器单步/全部“预演”改为“检查步骤”：受认证的 /agent-source/check 纯静态校验当前编辑 Source，复用编译器检查配置与跳转；不保存、不创建 generation/run、不调用 AI 补全、不连接或操作网页。逐步显示错误/通过，全部检查汇总；提示说明配置合格不代表真实网页执行成功。前端缓存 agent-step-chat-54，新增 Python/Node 测试各 1 项通过。Python API 需重启 Local，Test 内嵌源码需下次重建。

- 2026-10-08 用户要求同步重建 Dev/Test：Dev 已通过固定 build-dev-app.sh 完成替换并归档旧 App，固定 com.ai2apps.desktop.dev/dev 身份及原生 focus_shell 处理检查通过；Test 已通过固定 build-test-app.sh 完成重建及旧 App 归档；verify-release-app.sh、Dev/Test codesign --verify --deep --strict 均通过，Test 固定 com.ai2apps.desktop.test/test、cloud Runtime、非 Development 合同及嵌入新版 Local 聚焦 API/原生处理检查通过。两实例已恢复启动，Dev 127.0.0.1:63969 与 Test 127.0.0.1:64378 健康检查均 200，实机主窗口已进入首页。仅退出这两个实例的准确 Bundle/Local 进程，未修改或合并实例数据，App-Dev 保持独立。

- 2026-10-08 `implemented_appdev_rebuilt`：WebAgent 工作台手动试运行在终态调用受 Desktop Shell 会话保护的原生 Shell 聚焦通道；原生打包 transform 扩展现有生命周期 broker 的 focus_shell 动作，仅聚焦本实例主窗口，不重新导航。后台任务及等待协助不触发，切换编辑对象后旧测试不抢窗口。7 项 Python/Node 回归测试通过，原生 transform 匹配当前 shell.mjs 且通过 JS 语法检查。用户授权后已用固定 build-app-dev-environment.sh 完成重建并重启；verify-release-app.sh 和 codesign --verify --deep --strict 通过。确认固定 bundle ID、app-dev instance、Development/source-root/cloud Runtime 合同，以及 packaged shell.mjs 包含 focus_shell 分支；实机原生标题 AI2Apps-App-Dev: App-Dev 127.0.0.1:56276，AI 浏览器已恢复打开。完整 WebAgent 测试结束自动返回窗口的实机流程待复测。

- 2026-10-08 Agent 编辑/调试模式隐藏执行结果下方的知识桶、发送到对话及保存到知识库控件；切换模式及运行状态时统一同步，普通运行模式仍可使用。前端缓存版本 agent-step-chat-52，JS 语法和 scoped diff 检查通过，静态刷新生效。

- 2026-10-08 WebAgent 试运行结束后自动滚动并聚焦结果区；无输出时定位运行状态，失败/取消定位错误提示。仅在终态触发，忽略已切换的旧运行，避免轮询过程中打断编辑。前端缓存版本升至 agent-step-chat-51；2 项聚焦目标回归测试及 JS 语法检查通过，真实 App 滚动效果待刷新验证，无需重启 Local。

- 2026-10-08：修复“试运行全部”后端丢弃测试输入：BrowserAgentRunCreateRequest 增加 input 字段，create_draft_run 向执行器传递 request.input，替代固定空对象。create_ir_run 在 schema 校验前统一深拷贝默认值并由显式输入覆盖，非法输入返回 422。验证：14 项 Python 测试通过，新增真实 API 参数转发测试及默认值/显式覆盖/非法值断言，diff 检查通过；测试退出时沙箱 Metal 不可用清理告警但退出码 0。Python 变更需重启 App-Dev Local，未操作用户运行现场。

- 2026-10-08：修复情报中心已验证列表规则在编辑器单步执行报 invalid_extraction_step：SDK 的提取执行接受 compiled/adaptive 两种先执行规则模式，仍拒绝 interpreted、规则类型/operation 不匹配及非法格式。规则漂移转为 not_found 供既有 adaptive AI 回退处理。只读核实用户规则 #content /archives/ 保留，模式被编辑器设为 adaptive。资源 browser-foundations-17 / agent-step-chat-50。验证：16 项 SDK/情报规则回归通过（新增同一 list 规则两种模式执行及负例），JS 语法/diff 通过；未实测网站，未刷新用户编辑现场。

- 2026-10-08：修复 open 编译拒绝已声明 string 输入参数完整引用（如 ${input.url}）；保留缺失/未知参数、相对地址及脚本 URL 拒绝。单步规划规则校验失败时复用步骤 AI revision/JSON repair 链路，按自然语言与声明参数补全后保存并重新验证；整 Agent 编译失败时对当前能力步骤走同一补全路径再编译。新增 open/read_page 目标网址可见属性与 read_page 类型选项。资源 agent-step-chat-49。验证：19 项 Node 回归、12 项 Python Agent Builder 测试、动态 URL 与 4 类非法 URL 断言通过；Python 退出时有沙箱 Metal 不可用清理告警，退出码 0。未真实调用模型/执行网页，未重启 App-Dev Local，Python 更新需重启生效。

- 2026-10-08：修复单步预演/运行保存草稿重绘后卡片折叠，按步骤名称保留展开状态；单步准备、执行结果和异常在当前步骤操作区直接显示并保持展开，避免顶部提示不可见。资源 agent-step-chat-48。验证：JS 语法、diff 检查、工作台 6 项回归、单步执行成功/规划异常状态与上下文锁恢复断言通过；未实际执行用户网页或刷新编辑现场。

- 2026-10-08：步骤类型与名称控件统一为 13px 字号及相同行高，类型下拉采用 700 粗体；使用更具体选择器避免通用 input 字号覆盖。资源 agent-step-chat-47。验证：diff 检查通过；未刷新用户编辑现场，视觉待验证。

- 2026-10-08：步骤类型与步骤名称改为等宽两列同行布局，保留可见 label，统一控件高度并限制最小宽度，减少展开编辑的垂直占用。资源 agent-step-chat-46。验证：JS 语法与 diff 检查通过；未刷新用户编辑现场，视觉待验证。

- 2026-10-08：步骤成功/失败/判断为假跳转由自由文本改为下拉菜单，包含当前能力全部步骤（序号及名称）和 done/failed 两个 Agent 结束结果，支持回跳循环。名称编辑同步刷新候选项；无效历史目标保留并标记“目标步骤不存在”，避免静默替换为结束结果。资源 agent-step-chat-45。验证：JS 语法、diff 检查与工作台 6 项回归通过；未刷新用户编辑现场，实际交互待验证。

- 2026-10-08：步骤编辑为原先仅有 aria-label/placeholder 的属性补充持续可见 label，包括步骤名称、自然语言步骤、子 Agent 能力及参数 JSON、AI 指令/输出 schema、输入绑定/固定值；保留已有标签避免重复，参数绑定切换时同步隐藏固定值标签。字段标题统一 12px。资源 agent-step-chat-44。验证：JS 语法、diff 检查及工作台 6 项回归通过；未刷新用户编辑现场，视觉待验证。

- 2026-10-08：修复编译步骤 Checkbox 被通用文本输入框全宽/高度及 grid 标签样式撑大：为 Mini-Entry Checkbox 固定 16px 尺寸，编译选项采用独立 flex 同行标签。资源 agent-step-chat-43。验证：JS 语法与 diff 检查通过；未刷新用户编辑现场，实际视觉待刷新验证。

- 2026-10-08：参数定义组之间分割线加深为 2px 暖灰色，上下内边距增至 18px，末组不显示底线。资源 agent-step-chat-42。验证：diff 检查通过；未刷新用户编辑现场。

- 2026-10-08：参数定义新增上移/下移按钮，与删除并列，边界禁用；使用 inputs.x-ai2apps-order 数组保存添加/手动调整顺序，避免规范化 JSON 的 sort_keys 改变显示顺序。编辑、测试参数与工作台调用表单统一读取顺序；旧数据按现有顺序回退，新参数追加末尾，删除过滤失效键。资源 agent-step-chat-41 / workspace-11。验证：JS 语法、工作台 6 项回归、排序 JSON 往返及移动/删除/追加顺序断言、diff 检查通过。未刷新用户编辑现场。

- 2026-10-08：参数删除引用错误提示增加关闭按钮（含无障碍标签）与 12 秒自动消失；重复尝试清理旧计时器并重新计时，手动关闭同样取消计时器。资源版本 agent-step-chat-40。验证：JS 语法与 diff 检查通过；未刷新用户编辑现场。

- 2026-10-08：参数删除被引用保护拦截时，在该参数删除按钮附近显示持久错误提示，列出引用步骤名称（含局部变量），并滚动至可见位置，避免顶部通知不可见导致按钮无响应的错觉。实际只读核实 Fratellowatches 情报正文 extract 步骤 arguments.url 引用 ${input.url}；未删除用户参数。资源版本 agent-step-chat-39。验证：JS 语法及工作台 6 项 Node 回归通过；未刷新用户编辑现场，现场交互待验证。

- 2026-10-08：Agent 参数删除防误操作：删除按钮增加明确提示/无障碍名称，二次确认显示参数显示名及键名，并说明定义/默认值随保存移除；检查当前编辑内容中步骤和局部变量引用，包含参数重命名后的引用及嵌套属性，仍被引用则阻止删除。增加中英文文案；资源版本 agent-step-chat-38。验证：JS 语法、中英文 JSON 解析、变更 diff 检查通过；未操作用户参数或刷新编辑现场。

- 2026-10-08：Agent 参数定义编辑新增持续可见的参数名、显示名称、说明、类型、默认值标签，使用原生 label 关联输入控件，填写值后仍能辨认字段含义；改善字段间距与多参数分隔。普通侧栏与工作台编辑器共用。资源版本 agent-step-chat-37。验证：JS 语法及 diff 检查通过；保留用户未保存编辑现场未刷新。

- 2026-10-08：AI 浏览器嵌入的 workspace_editor 专注当前 Agent，隐藏通用指令执行表单与“我的智能体”标题/列表，移除编辑区多余分隔；保留模型选择、运行状态/结果、Agent 编辑与测试控件。普通浏览器侧栏不受影响。CSS/JS 资源版本 agent-step-chat-36。验证：模板解析、JS 语法、变更 diff 检查通过；未刷新现有编辑现场。

- 2026-10-08：Domain 中间栏 Agent 卡片增加独立“打开”按钮，保留“编辑”；单一活动能力进入调用参数界面，未启用或多能力 Agent 进入编辑器，不启动浏览器、不发起任务。资源版本 workspace-10。验证：工作台 Node 回归 6 项通过，包含活动能力/草稿打开路由；JS 语法、模板解析、diff 检查通过。

- 2026-10-08：拆分 Domain 行的展开与选中交互：独立箭头按钮只展开/收起 Agent 列表，名称/图标区域只选择网站并切换中间栏；增加当前 Domain 高亮、展开状态和键盘可聚焦按钮及无障碍标签。资源版本 workspace-9。验证：Jinja 模板解析及变更 diff 检查通过；保留用户编辑现场未刷新。

- 2026-10-08：修复 AI 浏览器刷新图标每 5 秒闪动：将后台同步锁与手动刷新展示状态分开，自动同步不禁用/旋转按钮；手动刷新仍显示进度，并复用正在进行的同步，避免重复请求。资源版本 workspace-8。验证：工作台 Node 测试 5 项通过（新增静默同步、手动进度、请求去重验证）；JS 语法及 diff 检查通过。未刷新用户已有编辑现场。

- 2026-10-08：按用户反馈加宽 AI 浏览器左侧导航：桌面最大宽度 260→300px，1100px 以下 200→230px，850px 以下 180→210px；移动端仍纵向排列。资源版本 workspace-7，变更 diff 检查通过。保留当前未保存编辑现场，未刷新。

- 2026-10-08：编辑 Agent 不再复用任务启动路径，不启动浏览器、不跳转网页、不抢浏览器焦点；通过同源宿主回调延迟到预演/运行/选取页面元素时准备测试上下文，去重并复用同一编辑器测试会话。保存、编译和选择参数无需浏览器。资源版本 workspace-6 / agent-step-chat-35。当前编辑器已打开；自动审批因刷新可能丢失未保存编辑状态而拒绝刷新，保留现场，尚未验证修复后的现场点击。验证：工作台 Node 回归 4 项通过，覆盖编辑零启动、重复编辑不启动、并发测试准备只启动一次及会话复用；两个 JS 文件语法及变更 diff 检查通过。

- 2026-10-08：修复 Domain 导航仅列出已启用能力、遗漏已保存但未启用 Agent 的问题。保留活动能力目录作为运行入口；为没有活动导出的 Agent 增加编辑入口，并区分“已编译 · 待启用”/“待编译”，不自动启用编译产物。前端资源版本 workspace-5。验证：`node --test ai2apps/tests/ai_browser_workspace.test.cjs` 3 项通过（覆盖编译未启用、编辑草稿、多能力无重复及点击进入编辑）；JS 语法及变更文件 diff 检查通过。

- 2026-10-08：AI 浏览器视觉对齐首页与 Studio：使用暖灰画布、独立白色圆角三栏、64px 标题栏与黑色图标，统一中性色分段切换、主按钮、表单、任务状态和空态；保留 Domains / Profiles 两个 Tab 与现有任务/Agent 行为，补齐窄屏布局和键盘焦点样式。前端资源版本更新为 workspace-4；只需刷新 Shell 页面，无需重启 Local 或重建 App。
  - 验证：Jinja 模板解析、`node --check ai2apps/web/static/js/ai_browser.js`、变更文件 `git diff --check` 通过；在固定 App Dev Shell（端口 62009）刷新，实际截图确认新标题栏、三栏卡片与 Profiles 切换。未执行 Agent、发布内容或修改 Profile 数据。

- 2026-10-08 Domain 图标：schema v81 持久保存添加网站时提取的 favicon。解析首页 icon/apple-touch-icon 声明并回退 favicon.ico，使用现有公开地址/重定向/实际 peer 校验、限时和大小限制；图像归一化为 64px PNG，不加载活动 SVG，不读取浏览器 Cookie。工作台返回本地缓存图标，左栏缺失时显示默认图标；既有 Domain 重新添加可补取。9 项工作台/图标测试通过，JS 语法及差异检查通过。Python API 和 schema 变更需下一次 App-Dev Local 重启生效，无需重建 App。

- 2026-10-08 UI 调整：左栏改为 Domains / Profiles 两个互斥 Tab，各自显示对应列表和添加入口。仅切换导航列表，不重建中间编辑器/执行器，不改变中间当前内容。静态资源版本提升，JavaScript 语法和差异空白检查通过。

- 状态：`implemented_and_verified_in_source`，App-Dev 已激活，未发布 Desktop。AI Browser 改为 Domain/能力和 Profile 导航、参数调用/编辑/状态、跨 Domain 当前任务与最近结果三栏。复用原 Agent Mini-Entry 编辑和执行器，导航切换隐藏独立 iframe，不销毁编辑状态；支持类型参数和文件数组选择。
- Local schema v80 新增账号隔离的持久任务队列、全局/Profile 配额、原子准入、固定编译 generation、租约、中断/恢复/取消。默认当前账号全 Domain 共 4 个，每 Profile 1 个，上限 16；侧栏/API 根 WebAgent 同样准入，嵌套能力共享名额。所有未结束任务均列出，另保留最近 200 条终态记录。旧单能力 Agent 的目录默认能力名称与调用器兼容。
- 浏览器控制继续走原生 BiDi Gateway。Shell Profile bootstrap 返回 opaque userContext，新增 bind 只解析 Profile 绑定；SDK 用 getTree/create/navigate 绑定专用任务 Tab 和读取 Profile Tab 数量，不按焦点或 URL 猜测。原生改动位于 `sdk/moz/acefox-firefox-153/browser/components/ai2apps/content/shell.mjs`；下一次生产 AceFox 快照必须包含此修改。
- 固定 App-Dev 构建脚本已完成构建，verify-release-app 和 codesign --verify --deep --strict 通过，实时原生窗口标题符合 App-Dev 合约。仅通过准确 app-dev Helper 重启 Local；未修改其它实例数据。GUI 验证三栏、能力参数、真实 Profile 状态、队列启动专用浏览器页以及任务失败归档。
- 验证：31 个 Python 相关测试及 12 个 Node 测试通过；后续增加历史记录不能遮蔽活动任务的回归测试。只读实测旧 Fratellowatches Agent 已启动并执行，其自身步骤走失败分支，不能记为采集成功；实际编辑器导航保留依靠 Node 回归验证，未声称完整线上采集/编辑验收成功。
- 当前执行器需要 AI Browser App 保持打开；Local 持久队列不是无 UI 的后台 browser worker。90 秒租约、15 秒续约，失联在下次查询/准入时暂停并保留名额，不自动重放未知发布动作。情报中心直接 SDK 采集不是 WebAgent 根运行，暂不在此队列。旧调用方没有 Profile key 时保守计入 default。说明：`ai2apps/docs/ai-browser-workspace.md`。


### NXR-GALLERY-PREVIEW-GESTURES-20261008

- 状态：`implemented_and_verified_in_source`，未发布 Desktop；iPhone Safari 双指实机验收待补。
- Gallery / Studio 共用大图预览支持双指以触点中心缩放（25%–600%）、双指平移和松开一指后连续单指拖动，保留桌面鼠标拖动及原有缩放/复位按钮。图片视口接管触摸，视频/音频原生控件不变；关闭、切图及复位清理手势状态。
- 修改 `ai2apps/web/static/js/gallery.js`、`gallery.css`、共享预览模板及消费者资源版本。静态改动刷新 Mobile Shell 即可，无需重启 Local 或 Cloud 变更。
- 验证：新增 5 项手势回归（触点锚定、单/双指切换、缩放上下限、取消/捕获丢失、模板接线），连同 Gallery 长按/拖拽共 10 项 Node 测试通过；JS 语法及 diff 检查通过。未声明真实 iPhone 手势已验收。


### NXR-MOBILE-OUTPUT-COLLAPSE-20261008

- 状态：`implemented_and_verified_in_source`，iPhone Safari 实机待复测，未发布 Desktop。
- Mobile Imagine Studio Output 图片随结果面板滚动逐步缩小到 112px，继续吸顶；回到顶部恢复原高度，图片保持 contain，点击大图及素材操作不变。仅 Mobile 生效，桌面保持原样。
- 缩小高度以等量底部 margin 保留滚动布局尺寸，避免高度变化反馈导致滚动位置跳动；响应面板尺寸变化和移动/桌面断点切换。变更共享 studio_mobile.js/CSS 及资源版本，无需重启 Local。
- 验证：Studio Mobile 11 项 Node 测试通过，覆盖缩小、下限、返回顶部、Safari 负滚动偏移、桌面恢复及现有导航/输出流程；JS 语法和 diff 检查通过。未声称 iPhone 实机视觉验收完成。


### NXR-MOBILE-REMOVE-SWITCHER-BUTTON-20261008

- 状态：`implemented_in_source`，未发布 Desktop。
- 按用户要求移除 Mobile Shell 顶栏 App Switcher 按钮；保留底部导航、Apps 入口、连接状态、Owner 退出及现有应用挂载状态逻辑。
- 修改 `ai2apps/web/templates/mobile.html`，刷新 Shell 生效，无需重启。已检查模板差异及 diff 空白，未新增低价值测试。


### NXR-MOBILE-HOME-QUICK-STUDIOS-20261008

- 状态：`implemented_in_source`，未发布 Desktop。
- Mobile Home 快速启动在原有前四项基础上加入 Imagine、Voice/readaloud、Video 三个 Studio，按 App ID 去重，仅展示服务端目录中实际可用的应用，沿用现有启动逻辑。
- 修改 mobile.js 与 mobile.html 资源版本；刷新 Shell 生效。JS 语法、6 项 Mobile 导航回归及 diff 检查通过。


2026-10-08 SenseVoice 43917最终清理修复标准Docker/Host回归exit0：源码摘要匹配，长短转录/取消恢复/鉴权及drain-resume通过，回执 artifacts/sensevoice-real-cancel-r2/host-receipt.json；签名安装发布仍待完成。


### NXR-MOBILE-APP-ACCESS-20261009

- 状态：`in_progress`。设备设置及现有权限收紧已实现并通过测试；自建 App 通用资源/Bridge 接入被自动审批拦截，等待用户明确授权，Cloud 未变更。尚未重启 Local 或发布 Desktop。
- 账户 → 设备 → 远程访问增加 Mobile 可用应用列表，Owner 本机控制开关，普通成员和 Owner Mobile 租约不能管理。schema v85 的 mobile_app_access 按 Installation/App 保存开关；内置七 App 保持原默认，自建默认关闭并提示待接入。
- 目录、挂载列表、启动/聚焦、原生页面及 App/Studio 专属接口检查设备策略。保留现有公网白名单，未新增公网资源路径。共享 Studio 素材/模型依赖按 Studio 使用范围保留；不授予其它用户身份、不自动取消已启动任务。
- 修改 ai2apps/api/remote.py、remote/mobile_apps.py、owner gateways、omlx/admin/routes.py、账户模板/JS/CSS/中英文、schema/config。Python 与 schema 改动需按既定流程重启 Local；无须重建 App。
- 验证：53 项 Python 测试通过（持久化、Installation 隔离、Owner 设置、非 Owner/手机管理拒绝、目录过滤、关闭后直接打开/重开/API 拒绝、既有 Owner/Studio 回归）；账户 JS 语法、Jinja/JSON 解析通过。无 iPhone 实机验收声明。
- 交接与审批范围：ai2apps/docs/mobile-app-access-gateway-2026-10-09.md。


#### NXR-MOBILE-APP-ACCESS-20261009 后续：Owner 自建 App 通道

- 用户已明确批准本人 Owner 登录会话范围的通用通道，安全边界实现已通过自动审批；此前“等待明确授权”阻塞解除。
- 新增绑定 Mobile sandbox mount/实例/访问者/启用策略的资源通道及仅 context 方法的 Bridge；公网上要求已验证 Cloud Owner 租约，旧配对会话不能代替，任意方法/额外负载默认拒绝。Shell 对 opaque iframe 加 sandbox 并在服务端握手通过后确认加载。
- 通用目录/启动动态检查 Mobile sandbox 声明，默认由 AI2APPS_MOBILE_PACKAGE_GATEWAY_READY=1 就绪开关控制；Cloud 未部署时不开通自建 App。未开放管理接口、通用代理或新推理权限。
- 第一阶段为无需后端能力的 Package 页面；模型/文件/Agent 等能力 Bridge 仍未实现，不能声明全部自建 App 可用。状态保持 in_progress，Cloud 路径部署与实机验收待完成，目标 Local 未重启。
- 验证：55 项 Python、6 项 Node 通过（新安全通道、匿名/撤销/跨实例/Origin/未授权方法、既有 Owner Studio）。新增就绪门控后重跑 Owner/policy 测试。Cloud 合同已更新 ai2apps/docs/mobile-app-access-gateway-2026-10-09.md。


#### NXR-MOBILE-APP-ACCESS-20261009：Cloud 部署后 Dev 激活

- Cloud mobile-app-access-gateway-20261009-v1 已核对。Ready 增加基于可信运行描述路径的同实例配置文件，严格 schema/失败关闭，显式环境变量优先；避免 Helper 环境过滤导致开关丢失。
- 仅 dev 配置并通过标准 HelperControlClient 重启；PID80734、端口62813、boot8dadc33c-ef75-481f-bbd7-42a9f76a7171。App-Dev/Test 未操作。Chrome 真实 Owner 重新进入 Mobile 成功；Dev 账户远程访问 Mobile 列表实际可见。
- 44 项 policy/gateway/lease 测试通过。当前无独立 sandbox Package 可测，已询问测试对象；真实 Package、实机租约矩阵和 iPhone Safari 未完成，不将此条记为全面验收。

### NXR-INTELLIGENCE-SOURCE-AGENTS-20261009：信息源指定读取 WebAgent
- 状态：`implemented`。列表/正文各自绑定 owner-scoped、已启用、编译兼容的单入口 WebAgent generation；默认自动学习复用，指定版本失效不静默降级。统一后台 Task 保持来源 Profile、冷却与历史去重。配置接口、编辑回显、启停保留字段和返回结构检查已接入。
- 验证：7 项 Python 定向测试与 3 项 Node 自动规则回归通过；JS 语法与 diff 检查通过。旧 API 全量测试 7 项因假 runtime 缺 intelligence_collector 失败（后台迁移后旧测试未适配）。标准 Helper 已重启 App Dev Local，App Dev 64721 原生来源设置显示两个选择器，已启用 Agent 列表加载通过；真实指定 Agent 采集尚未验收。无重建、无发布。

### NXR-INTELLIGENCE-IMAGE-RECOVERY-20261009：统一采集后补图
- 状态：`implemented`。确认最新 Fratello 两篇文章入库无图片，编译正文规则未开启图片选项。新规则显式提取图片，所有正文路径在入库前归一封面与图集，缺图时通过原来源 Profile 的共享 Task 最多补读一次；保留文字，记录成功/未发现/失败数量，社交补读仍有间隔。
- 验证：7 项 Python 定向检查通过，覆盖复用已有图片、缺图恢复、不替换正文、无图与异常不丢失文章。已请求标准 App Dev Local 重启，App Dev 65506 历史 Tudor/Armin Strom 两篇已通过原 Profile 补提取，入库 21/6 张图片并设置封面，原生详情已验证；自动分支由定向测试覆盖，本轮未另跑整频道采集。无重建或发布。

### NXR-INTELLIGENCE-KNOWLEDGE-CHAT-20261009：关联知识库参与频道对话
- 状态：`implemented`。当前 principal 在频道关联桶内使用系统混合/全文检索，空关联不全库检索，失权/删除明确报错；文章和知识库片段统一引用编号，去重同步文章，无文章也可回答。界面显示知识库引用及可展开的版本片段快照。
- 验证：8 项对话与知识库定向测试通过，JS 语法及 diff 检查通过；真实模型端到端未验收。通过标准 Helper 重启 App Dev Local，未重建或发布。详见 ai2apps/docs/intelligence-center-v1.md。

### NXR-INTELLIGENCE-ENTITY-CATEGORIES-20261009：实体分类展示
- 状态：`implemented`。实体类型筛选及数量、仅看已关注、按频道记住选择；腕表默认产品，AI 默认模型。加入 model 类型和旧产品模型兼容，档案保持跨频道共享。4 项 Node 与 7 项 Python 检查通过；App Dev 51940 原生腕表频道默认选中产品13（全部20），品牌2、人物2、事件1分类和仅看已关注控件显示正常。通过标准 Helper 重启 Local，无重建或发布。

### NXR-INTELLIGENCE-ENTITY-SELECTION-20261009：实体分类选中样式
- 状态：`implemented`。修复实体分类 active 规则被 #intel-app 通用按钮样式覆盖；以 aria-pressed 匹配更高优先级的深色底、反白文字及勾选标记，悬停保持选中态。CSS diff 检查通过。仅静态样式，刷新 Shell，无需重启或重建，未发布。

### NXR-INTELLIGENCE-CATEGORY-FOLD-20261009：频道相关分类排序与折叠
- 状态：`implemented`。移除实体“全部”分类，默认只显示当前分类和展开按钮；展开按频道名称/关注内容规则排序，腕表为产品、品牌、人物优先，AI 模型置后；AI 频道模型优先，体育频道事件优先。选择后收起，保持每频道选择记忆，旧全部偏好回退频道默认。5项 Node 检查及语法/diff 检查通过；App Dev 51940 原生验证仅显示当前分类、腕表展开顺序、选择产品后收起均通过。仅刷新 Shell，无重启、重建或发布。

### NXR-INTELLIGENCE-AI-TAXONOMY-20261009：AI 规划频道实体分类
- 状态：`app_dev_verified`。删除前端关键词固定排序，频道创建由 AI 规划开放分类名、边界、顺序和默认项；分类及实体归属存频道，实体本体保持共享。已有频道可通过 AI 规划实体分类建立/重规划，采集和实体整理后增量分类。保留单项折叠与无“全部”交互，未归类实体可在待分类查看。9项 Python、3项 Node 定向检查通过；App Dev 53775 真实AI为腕表生成8类并归类20实体（含独立制表师与工坊、机芯与复杂功能），保留AI给出的默认项与顺序，折叠/展开通过。首次Cloud 502未写入半成品，重试成功。无重建或发布。

### NXR-INTELLIGENCE-ENTITY-DISMISS-20261009：实体不感兴趣与持续排除
- 状态：`implemented`。实体卡片/详情增加不感兴趣，owner 范围跨频道隐藏并停止机会输出；持久保存名称/别名排除，后续抽取命中时跳过且补记新别名，人工归属重定向也尊重忽略。提供已忽略列表及恢复，原文章保留。11项 Python、3项 Node 定向检查通过（含忽略/恢复 API、跨频道后续别名排除）；App Dev 54943 卡片不感兴趣按钮及已忽略入口显示通过，未替用户选择要忽略的真实实体。无重建或发布。

### NXR-INTELLIGENCE-DISMISS-CONFIRM-20261009：实体偏好布局与防误触
- 状态：`implemented`。详情不感兴趣移至关注复选框同一行，显式 type=button 避免误提交；列表和详情共用确认弹窗，说明实体名称、所有频道范围、阻止重入和恢复入口，取消不发请求。4项 Node 检查通过，语法/diff通过。仅前端刷新，无重启、重建或发布。

### NXR-INTELLIGENCE-ENTITY-IMAGES-20261009：实体相关图片
- 状态：`implemented`。动态汇集实体引用文章/帖子封面及正文图片，去重并保留来源；列表封面、详情图片集、放大及现有 Gallery 导入，支持指定封面、确认移除关联并持久排除。原文章不变，沿用微博受保护图片代理与原 Profile。12项 Python、5项 Node 定向测试通过，覆盖 owner 隔离、封面切换、重新采集后的排除保留、取消移除无写入。通过标准 Helper 重启 app-dev Local，未重建或发布。

- App Dev 58866 原生界面验证：实体列表封面、详情8张相关图及来源/封面/移除按钮可见；放大图片实际加载成功，现有加入图库入口可用。未修改用户真实图片偏好。

### NXR-INTELLIGENCE-ENTITY-IMAGE-GROUPS-20261009：实体图片按文章聚合
- 状态：`implemented`。实体详情图片按来源文章/帖子分组，每组只显示一次来源标题和图片数，组内图片保留放大、设为封面、移除关联操作。仅前端展示调整，5项 Node 回归和语法检查通过；无需重启或重建，未发布。

### NXR-INTELLIGENCE-RULE-TOGGLE-20261009：实体规则输入按需展开
- 状态：`implemented`。机会条件/关注规则改为复选框，未勾选时隐藏输入和保存按钮；已有规则默认展开，收起保留内容。名称、别名、关注状态独立自动保存，串行保存并更新 revision，规则仍显式保存。5项前端回归和语法检查通过。仅静态前端，无重建或发布。

### NXR-INTELLIGENCE-ENTITY-SIDEBAR-20261009：右侧实体详情
- 状态：`implemented`。实体列表点击后保留中间列表和选中高亮，右侧新增实体详情页签，承载设置、图片、实体对话及事实；删除返回实体列表按钮。详情事件独立绑定，频道切换清空选择，离开实体/机会页恢复右侧对话或文章。6项 Node 回归及语法/diff检查通过。仅模板/前端刷新，无重建或发布。

- App Dev 58866 已刷新验证：点击 Mirage Miroir 后实体列表仍在，右侧实体详情展示名称、规则及10张图片；无返回列表按钮。

### NXR-INTELLIGENCE-COMPACT-ENTITY-IMAGES-20261009：紧凑实体图片网格
- 状态：`implemented`。实体详情缩略图改为112px高、128px最小列宽、8px间距，去除卡片内层留白；封面/移除按钮叠加图片底部，hover或键盘focus-within显示，触屏常显，保留原确认机制。纯CSS，diff检查通过，无重启、重建或发布。

### NXR-INTELLIGENCE-ENTITY-RELEVANCE-20261009：实体提及与图片归属
- 状态：`implemented`。AI抽取增加substantive/mention及证据理由，不按提及次数晋升；正式列表默认隐藏mention和旧待整理记录，可显式查看并关注晋升。图片只接纳AI依据提供的图片说明匹配的有效ID，无说明/不确定不兜底；保留手选封面及排除。抽取检查点升级并包含图片变化，旧文章可重新整理且保留共享实体ID。14项Python和6项Node检查通过。标准Helper重启App Dev，无重建或发布。


### NXR-PLATFORM-SEARCH-AGENT-20261009：平台通用网页搜索 WebAgent

- 状态：implemented，待真实 Google/Bing 联网验收及后续 Desktop 发布评估。
- 新增内置 `builtin:web:search` / `web.search`，Google 优先，导航失败或结果不可用转免费 Bing 网页搜索，双引擎不可用失败；查询编码、1–50 条上限、标题/链接/摘要、跳转还原及去重。
- 使用共享 Local Browser Task 与 compiled/BiDi 路径，无前台执行依赖、无每次 AI 调用；可信 Local `WebAgentInvocation` 支持内置能力调用。现有 HTTP research Tool 暂不改变；Google API provider 为后续扩展，凭据进入平台秘密存储。
- 文档：`ai2apps/docs/platform-search-agent.md`；验证：49 项 Python 回归、3 项 DOM 搜索结果测试。Python 修改需重启 app-dev Local；无需重建 App。

- 后续完善：已有相同文章版本的档案走保留名称/引文的相关性复核，优先于未建档文章；原始抽取名称错误提示定位具体名称。复核保留全部人工归属后的事实。批次失败仍刷新已保存结果。15项Python、7项Node通过。App Dev真实AI复核：帝舵Black Bay Ceramic=mention、0图片；Supermarine Full Ceramic=substantive、10图片；Mirage Miroir=substantive、3图片。旧档案44条事实已复核。随后未建档DUG文章因模型组合名称不在原文中而被校验拒绝，新文章批量整理未全部完成，已有复核结果已保存。无发布。

### NXR-INTELLIGENCE-ENTITY-NAME-EDITOR-20261009：按需编辑实体名称
- 状态：`implemented`。实体详情默认隐藏名称/别名表单，点击标题展开并聚焦名称；编辑区右上角×收起并将焦点返回标题。切换实体恢复收起，保留原自动保存，更新后同步详情标题。纯前端，7项Node回归及语法/diff通过，无重启、重建或发布。

### NXR-INTELLIGENCE-ENTITY-DETAIL-FOLDS-20261009：实体详情折叠区
- 状态：`implemented`。与实体对话、事实时间线、纠正归属改为独立原生details，默认收起；同一实体操作重绘保留展开状态，切换实体恢复收起。时间线保留数量，纠正归属提示先勾选事实，研究反证入口自动展开对话。7项Node回归、语法及diff检查通过。纯前端，无重启、重建或发布。

### NXR-INTELLIGENCE-ENTITY-RULE-FOLD-20261009：关注规则统一折叠样式
- 状态：`implemented`。机会条件/关注规则移至时间线之后、纠正归属之前，使用同款默认收起details，移除原复选框。规则独立表单只保存rule；时间线事实通过form属性关联归属表单，避免嵌套表单且保持批量移动。7项Node回归、语法/diff检查通过。纯前端，无重启、重建或发布。

### NXR-INTELLIGENCE-RELATED-ARTICLE-LIST-20261009：实体相关文章与原文浏览
- 状态：`implemented`。相关图片区改为相关文章列表，从事实引用聚合（含无图文章），文章下保留对应实体图片；多来源展示单独入口。标题通过现有Profile生命周期服务和原生BiDi打开原文、激活标签并保留页面，沿用来源Profile，不改变实体详情。缺失信息源明确提示，不切换到错误Profile。8项Node回归及语法/diff检查通过。纯前端，无重启、重建或发布。

### NXR-INTELLIGENCE-RELATED-ARTICLE-META-20261009：相关文章卡片元信息
- 状态：`implemented`。文章卡片标题独立一行，下一行左侧来源名（无名称回退域名），右侧图片图标及数字；保留多来源原文入口、无障碍图片数量说明与下方缩略图。8项Node回归及语法/diff检查通过。纯前端，无重启、重建或发布。

### NXR-INTELLIGENCE-RELATED-TITLE-ELLIPSIS-20261009：相关文章标题单行省略
- 状态：`implemented`。相关文章卡片标题单行显示，溢出省略号；原生title悬停提示显示转义后的完整标题。前端语法/diff检查通过。纯前端，无重启、重建或发布。

### NXR-INTELLIGENCE-RELATED-TITLE-TOOLTIP-20261009：页面内完整标题提示
- 状态：`implemented`。替换Shell中未显示的原生title提示，用页面内tooltip，在标题hover或focus-within时立即显示完整换行标题，保持单行省略；提示文本转义，通过aria-describedby关联。语法/diff检查通过。纯前端，无重启、重建或发布。

### NXR-INTELLIGENCE-ENTITY-FILTER-ROW-20261009：实体筛选同行显示
- 状态：`implemented`。显示提及记录/待整理与仅看已关注置于同一flex行，统一对齐及间距；极窄空间允许换行。语法/diff检查通过。纯前端，无重启、重建或发布。

### NXR-INTELLIGENCE-SOURCE-RECOMMEND-POSITION-20261009：信息源推荐入口位置
- 状态：`implemented`。AI推荐信息源从频道顶部操作区移到信息源列表工具栏，紧接添加信息源右侧，仅信息源页显示；沿用原按钮事件与忙碌状态。语法/diff检查通过。模板/前端刷新，无重启、重建或发布。

### NXR-INTELLIGENCE-CHANNEL-CHAT-ENTRY-20261009：精简频道对话入口
- 状态：`implemented`。宽屏隐藏“立即更新”旁重复的“频道对话”按钮，使用右侧栏入口；850px 及以下侧栏隐藏时保留打开对话按钮。CSS 定向 `git diff --check` 通过。纯前端，无重启、重建或发布。

### NXR-INTELLIGENCE-HEADER-STATUS-CLEANUP-20261009：精简频道首页状态说明
- 状态：`implemented`。移除频道首页定时采集说明及常驻知识库关联/同步计数；同步失败时仍提供错误与重试入口。操作区与内容导航保留 20px 间距。JS 语法及定向 diff 检查通过；纯前端，无重启、重建或发布。

### NXR-INTELLIGENCE-CHANNEL-ACTIONS-20261009：频道操作入口调整
- 状态：`implemented`。撰写稿件移至稿件列表顶部，去掉空列表重复入口；立即更新改为频道设置左侧图标。更新/设置使用自定义 Hover-Tip，支持键盘焦点，避免 Shell 原生 title 提示不显示。无频道时隐藏图标组，保留更新禁用逻辑。JS 语法及定向 diff 检查通过；纯前端，无重启、重建或发布。

### NXR-INTELLIGENCE-NAV-COUNT-SPACING-20261009：导航计数间距
- 状态：`implemented`。频道导航按钮文字与计数间距统一为 2px（按反馈进一步收紧），移除计数额外左边距，避免与通用按钮 gap 叠加。定向 diff 检查通过；纯 CSS，无重启、重建或发布。

### NXR-INTELLIGENCE-SECTION-COUNT-SPACING-20261009：栏目计数间距
- 状态：`implemented`。补齐文章栏目筛选按钮的计数间距：移除通用 7px gap 与 4px 左边距叠加，改为统一 2px，与上层导航一致。定向 diff 检查通过；纯 CSS，无重启、重建或发布。

### NXR-INTELLIGENCE-SECTION-DRAG-ORDER-20261009：文章栏目拖拽排序
- 状态：`implemented`。实际栏目支持拖拽前后插入，全部/待归类固定；通过 owner-scoped PUT sections/order 持久化到频道，校验完整无重复 ID 集合。保留栏目 ID 与文章归属，失败提示并维持原顺序。存储持久化/无效集合/用户隔离定向测试通过，JS 语法检查通过。需重启 App Dev Local 加载 API；不重建或发布。

### NXR-INTELLIGENCE-MANUAL-IMPORT-20261009：手动收录文章
- 状态：`implemented`。更新右侧增加加号及 Hover-Tip；支持 Profile/BiDi URL 读取与 20MB PDF/doc/docx/md/txt/图片上传。正文保留、AI 归类、频道内 URL/文件去重、关联知识库同步；附件 owner 隔离与 MIME 实测判定。图片按原图收录，无 OCR；扫描 PDF 无文字明确失败。3 项 Python 定向测试、7 项卡片测试、JS 语法和 diff 检查通过。App Dev Local 重启加载，无重建或发布；尚未进行原生 Shell 上传实测。

### NXR-INTELLIGENCE-IMAGE-SUMMARY-CHOICE-20261009：图片收录可选 AI 总结
- 状态：`implemented`。图片上传要求显式选择总结/仅原图；总结通过现有模型调用链发送视觉输入，生成标题摘要正文并标注 AI 图片总结。重复原图可原位升级，失败不静默降级。4 项收录定向测试通过（含 opt-in 和原位升级），JS/diff 检查通过；真实视觉模型效果未实测。App Dev Local 重启加载，不重建发布。

### NXR-INTELLIGENCE-CHANNEL-DIALOG-LAYOUT-20261009：频道设置三段式对话框
- 状态：`implemented`。频道创建/设置对话框加宽至 760px（窄屏自适应），总高度不超过 90dvh，标题和操作栏固定，中间字段区域独立滚动；错误提示位于底栏。定向 diff 检查通过。纯 HTML/CSS，刷新生效，无重启重建或发布。

### NXR-INTELLIGENCE-SECTION-EDITOR-20261009：频道栏目管理
- 状态：`implemented`。频道设置支持栏目名称/说明编辑、添加、确认删除；随频道原子保存，取消不提交。最多 32 项，校验非空/唯一名称及 ID；删除保留文章转待归类，栏目快照防覆盖并发修改，采集中阻止修改。7 项栏目与手动收录回归测试通过，JS 语法/diff 检查通过。App Dev Local 重启加载，无重建或发布。

### NXR-INTELLIGENCE-I18N-20261009：情报中心多语言
- 状态：`implemented`。接入系统语言包，完成简体中文/英文 UI、日期格式和错误提示；其他 UI 语言暂按系统机制回退英文。静态文案翻译不改写文章、实体名或用户输入。频道独立保存 AI 输出语言，支持中简/中繁/英/日/韩/法/德/西/葡巴/俄，后台采集沿用；新频道栏目与实体分类规划传递语言设置。25 项 Python 和 18 项 Node 回归检查通过，最终补丁后 5 项语言/分类测试通过，定向 diff 检查通过。原生 Shell 语言切换和真实模型多语种输出尚未实测。App Dev Local 重启加载，无重建或发布。

### NXR-AI-BROWSER-I18N-20261009：AI Browser 与 WebAgent 编辑器多语言补齐
- 状态：`implemented`。补齐简中、英文、繁中、日文、韩文、法文、西班牙文、巴西葡语、俄文的工作台、Domain/Profile 管理、任务/并发设置、删除确认、附件/参数、能力编辑、步骤与 Review/探索提示；后台固定任务标签在客户端按语言显示，用户内容保持原文。修正并发设置中与后台执行机制不符的关闭 App 提示。
- 验证：51 项 Node 定向测试通过，包含九语言键覆盖/动态类型与状态/占位符一致性、英文后台标签显示、工作台与能力编辑及步骤运行回归；九语言共 18 个模板渲染通过，1503 个渲染后的 Alpine 表达式语法检查通过。更新旧测试夹具以提供 structuredClone 和步骤指导上下文，并验证附件绑定复制语义。JS 语法和定向 diff 检查通过。
- 生效方式：刷新 App Dev Shell 页面加载模板、脚本与语言资源；无需 Local 重启或 App 重建。未进行全部语言的原生 Shell 逐页视觉检查，未发布。

### NXR-AI-BROWSER-COMPACT-DOMAIN-MODE-20261009：紧凑网站执行模式设置
- 状态：`implemented`。执行模式标题与下拉框同行，移除通用表单 label 的上下 22px 留白；说明独立显示，区域内边距压缩为 12px/16px，下拉框按内容宽度显示。窄屏或长翻译允许自然换行；显式 label 关联与说明 aria-describedby 保留可访问性。
- 验证：2 项九语言覆盖/占位符与运行标签回归通过，定向 diff 检查通过。纯 HTML/CSS，刷新 Shell 页面生效，无需 Local 重启或 App 重建；未发布。
