# 一搜到底 / Search All

开发 Package：`packages/ai2apps-search-all`（仓库根目录），App ID `ai2apps.search-all`，Package ID `ai2apps/search-all`。使用既有 Web-Agent Mini-App Package 合同与 AI Browser 的“应用”入口，不新增安装类型。

## 使用

输入关键词、勾选 Google、Bing、DuckDuckGo、Brave、Wikipedia、小红书、X、微博、B站、YouTube 中的一个或多个来源，设置每源结果上限（1–20，默认 10）及已有浏览器分身（下拉选择，默认选择默认分身）。点击搜索后各来源分别提交公用后台 Task；队列按全局及 Profile 并发限制执行，前端通过宿主现有 SSE / MessageChannel 接收状态，网页关闭不终止已提交任务。登录或验证在 AI Browser 任务栏打开对应任务继续；不自动绕过验证。

默认勾选 Google 和中文 Wikipedia。Google、Bing、DuckDuckGo、Brave 是独立来源和独立后台 Task；各自失败不会切换到另一来源，只有用户勾选的来源会执行。平台通用搜索 Agent 的 Google → Bing 回退策略保持不变。社交来源读取可见搜索结果，不保证完整历史、无限滚动或登录墙之后的数据。Wikipedia 使用中文搜索；其它语言可后续作为独立设置扩展。

## 执行与结果

每个来源的 Source 含明确站点范围、独立输入 Schema 及 compiled open/extract_list 步骤。公用 BackgroundPage 的 native BiDi helper 读取 DOM；Mini-App 不操作浏览器、不持有 Gateway 凭据、不直接调用模型或搜索 API（API 调用由后台 Task 执行）；AI 整理通过公用后台 Task 的 ai.transform 执行。页面结构未匹配显示失败，不把空提取当成成功；页面明确表示无结果时返回成功空列表。登录/验证码返回 needs_user。

Google/Bing/DuckDuckGo/Brave 使用独立站点选择器及语义标题链接 fallback；DuckDuckGo 的 observed uddg 跳转链接还原为目标链接，Brave 读取网页结果卡片；社交/Wikipedia 使用站点选择器加受限文章/帖子链接 fallback。站点变动时可更新 helper，不需改 Task 系统。X 对可见帖子文本执行关键词字面检查，排除搜索页混入的无关时间线建议；不执行语义扩展。API 搜索配置与快速模式见下文“搜索模式”。

界面按来源交替合并结果。以链接身份去重，移除片段和常见追踪参数进行比较；X/Twitter 以 status ID、小红书以笔记 ID 比较，保留原始访问链接（含必要访问参数）。相同标题的不同页面保持独立。每条记录的 sources 包含请求来源、实际 provider及该来源的原始 URL，可导出 JSON。去重在展示层完成，各后台任务的原始结果保持原样。Google 的 opaque signed `/goto` 链接保留页面实际链接；无法获知真实目标时，不能与其它来源的目标 URL 合并。

结果使用 textContent 和校验过的 HTTP(S) 链接渲染，拒绝含凭据或可执行协议的链接。任务授权、幂等提交、取消、状态、Profile 隔离及结果读取均复用公用机制。本次页面的合并视图在刷新后不保存；独立任务仍可在公用任务历史查看。

## 分类卡片与 AI 整理

结果按网页、帖子、视频分组，每组默认显示前三条，“展开另外 N 条”查看剩余项。网页展示标题及内容提要；X/小红书/微博显示实际可见正文（最多四行）、作者和可见互动数；YouTube/B站展示预览图、时长、发布时间、播放及点赞等已观测信息。搜索页未提供的字段不显示，不推算或补造互动数；YouTube 搜索页通常没有点赞数。预览图只接受无凭据 HTTPS URL，不发送来源 referrer。

所有已提交来源结束后，将去重后的标题、片段及帖子正文作为不可信数据交给独立 `review` 公用后台 Task（`ai.transform`，普通模型配置的 standard 档）。根据查询相关性、信息量及域名的推断可信度在每类内重排，并将网页标题/提要及推荐理由翻译为宿主传入的当前语言。只整理已有搜索片段，不自动读取全文；可信度是推断，未经独立验证。原始帖子、视频标题/正文保持原语言，AI 不参与生成 URL、来源或互动指标。

结果输入最多 200 条，每条网页摘要最多 500 字符、帖子正文最多 700 字符供排序参考；完整可见正文仍用于卡片展示。AI 必须返回每个输入 ID 恰好一次；遗漏、重复、未知 ID 或无效数据会被拒绝，保留原始结果并提示未完成 AI 整理。整理失败不影响已经成功的搜索 Task。导出 JSON 保留去重来源、观测元数据、翻译及推荐理由。

整理的提交由当前 Mini-App 在收到各来源终态后触发；关闭界面不终止已经提交的搜索/整理 Task，但在搜索完成前关闭界面不会自动补交整理任务。合并展示与这次排序结果刷新后不恢复，原始 Task 历史继续保留。

## 验证

分类卡片：48 项 Python、23 项 Node 回归通过，覆盖模型返回 ID 的遗漏/重复/未知值、保留原始来源与互动数、没有片段时拒绝生成正文事实、YouTube 视频身份去重、B站标题与统计文本分离、视频 SPA 有界等待及登录/验证保护。App Dev 搜索 mechanical watches：Brave、B站、YouTube 三源和独立 AI 整理 Task 全部完成，显示 4 条网页与 6 条视频结果；网页提要为中文，视频预览/时长/播放数可见，各类前三条和其余展开入口已确认。首次 YouTube 空白加载已通过有界等待修正并复测成功；本轮 X/小红书未做登录态在线验收，字段读取由 DOM 回归验证。B站标题修正在模拟 DOM 上回归通过。


新增 DuckDuckGo / Brave：43 项 Python、14 项 Node 测试通过。App-Dev 实际搜索 mechanical watches，两源各返回 3 条，合并去重后为 5 条；重复链接保留两源来源标记，两 Task 完成并关闭任务页面。

App-Dev 实际验证：Google 与 Wikipedia 双源搜索合并显示 6 条结果，微博返回 2 条。Task 使用 compiled 步骤并完成独立页面清理。小红书本次页面无可提取笔记，按失败处理；X 本次返回无关内容，最终字面关键词过滤有回归覆盖，尚未宣称这两个来源在线验收通过。登录与验证码 needs_user 分支由自动化测试覆盖。39 项 Python、10 项 Node 测试通过。

`node --test ai2apps/tests/search_all_results.test.cjs ai2apps/tests/site_search_results.test.cjs ai2apps/tests/platform_search_results.test.cjs`

`.venv/bin/python -m pytest ai2apps/tests/test_search_all_mini_app.py ai2apps/tests/test_platform_search_agent.py ai2apps/tests/test_web_agent_mini_apps.py ai2apps/tests/test_browser_background.py -q`

Package 发布必须走标准签名与发布脚本；开发 source mount 不代表已发布。

## Search diagnostics, advertising and retained pages

The Mini-App offers `exclude_ads` (default on) and `retain_pages` (default off).
Observed sponsored placements are removed by the native BiDi DOM reader when
ad exclusion is enabled. The shared AI review also classifies clearly promotional
content; normal product mentions, reviews and shopping comparisons are not
inherently ads. If review fails, observed ad filtering still applies, but semantic
advertising classification is unavailable and the UI reports the review failure.

Source failures project the durable browser-action diagnostic code, without
sending captured DOM/private page text to the UI. The result view explains login,
verification, navigation, provider-rate errors and unrecognized markup with
suggested next actions. X simple multiword queries match terms independently;
advanced queries are left to X's own search parser. SPA reads have bounded retries.

Retained pages remain owned by Local background Tasks, including after closing
the Mini-App. The authenticated host SDK offers `retainedTasks()` and
`pages(taskId, 'list'|'focus'|'close')` as Task lifecycle operations. These do not
accept arbitrary browsing-context IDs or expose a browser command catalog.
Each call revalidates the current mount, actor and Mini-App caller; native BiDi
only activates/closes Task-owned contexts in the recorded browser Profile.
Active Tasks and unfinished cleanup cannot be closed through this interface.
Page closure is verified against native `browsingContext.getTree`.

The UI restores retained Task references after reload, provides source-page
buttons (also on result origin badges) and a close-all button. Before the next
search it checks which pages still exist and offers **close and search**, **keep
and search**, or **cancel** in a dialog. Manually closed tabs are excluded. Closing
search pages never closes unrelated user tabs. Source execution and AI review
remain on the shared background Task queue with SSE updates.

### X 连续加载、原帖打开和翻译

X 搜索在后台通过 native BiDi 滚动最多 12 轮，跨虚拟列表按原帖 URL 去重，达到用户设置数量或连续三轮没有新增结果时停止。设定数量为上限而非保证值；广告过滤和站点可见结果可能减少最终数量。返回 scan_stop_reason 记录停止原因。前三张卡片仍仅为默认展示，其余通过展开显示。

结果链接通过宿主 openResult(taskId, url) 打开既有原生浏览器分身窗口。后台重新校验 actor、mount、Mini-App caller，并只允许当前 Task 实际观察到的 HTTPS URL；不依赖 iframe 的 target=_blank 或仍存在的搜索页。

共享 AI review 判断帖子 source_language，语言不同于应用 locale 时返回忠实 translated_content。卡片显示“已翻译”与来源语言，同时可展开原文，原帖 URL、互动数据和来源不变。翻译依据已采集正文（最多 2400 字符），不补造被截断内容；review 失败时保留原文并显示失败提示。

小红书搜索列表不提供完整正文。共享后台 SDK 顺序点击已观测笔记链接，最多读取 20 篇，每篇仅等待有界渲染时间；读取笔记自身的正文、作者、日期与可见点赞/收藏/评论数，然后通过原生浏览器后退返回已访问搜索列表，确认恢复后继续。遇登录/验证交由公用 Task 协助流程，不自动重试未知点击。未读正文明确标记，不用列表标题充当内容。查看原帖保留观测链接的站点参数，在所选分身中打开。

2026-10-12 App-Dev 复验：小红书“机械腕表”三篇连续读取全部 detail_read，正文长度 47/305/36 字符，点赞/收藏/评论分别 40/15/3、169/64/51、508/285/38。卡片展示作者、正文、日期与指标；点击“宇宙带着三枚新机芯，强势复兴”的查看原帖，在 Default 新 Tab 打开同一笔记并核对正文与 169/64/51。入口按同站笔记 ID 匹配有可点击区域的实际链接，保留新观测参数，并等待列表恢复渲染。导航采用 native wait=none，随后进行既有有界内容稳定性检查；无不确定操作自动重放。31 项 Python、9 项搜索 DOM Node 回归通过。

### 小红书封面

小红书帖子卡片显示封面。共享后台 SDK 读取实际图片链接，同时对已加载封面区域使用 native BiDi captureScreenshot 生成 JPEG DataURL，优先展示页面像素副本，避免图片 CDN 外链限制和重复下载；截图仅包含封面区域。单图 DataURL 上限 400,000 字符，每源累计上限 2,000,000 字符；读取失败继续正文，回退到合法 HTTPS 图片链接。不另建磁盘图片缓存；像素副本与公用 Task 输出使用同一保留周期，页面合并视图仍为本次搜索。前端拒绝 SVG/HTML DataURL；AI 排序不接收图片，只保留原始封面字段。

封面在线验收：App-Dev“机械腕表”三篇均读取封面 DataURL（34,827 / 72,523 / 89,743 字符）并取得正文；截图确认卡片封面、四行正文与指标显示正常。Task 页面自动关闭后封面继续可见。29 项 Python、18 项 Node 回归及 search.js 语法检查通过。

小红书有封面时采用左图右文：左侧 2:3 竖版封面区域使用 contain，不裁掉完整封面；右侧为作者/原帖、标题、四行正文、日期与互动指标。窄屏缩小封面并保持左右布局，无封面时内容占满卡片。

选择小红书、X 或微博时，搜索表单动态提醒用户先在当前所选浏览器分身中登录，切换来源或分身时同步更新。提示说明分身登录状态独立，遇登录/验证码在任务栏打开任务继续；该提示不代表系统已核验网站登录态。

### 搜索源排序

选择 X 后提供最新（默认）/热门；选择小红书后提供综合（默认）/最新/最多点赞。只给相应源的 Task 传递枚举参数，使用共享 SDK 的原生站点控件切换并核验选中态，不伪造高赞结果。X 没有独立高赞选项。采集完成后的 AI 推荐排序仍依据相关性与信息量，和站点采集排序是两个阶段。

## 搜索模式（2026-10-12）

默认“优选”；“自定义”保留原来的搜索源、上限、站点排序、广告过滤及保留页面配置。“快速”和“优选”只显示查询、模式、分身及运行入口，快速另有“配置搜索 API”。配置由当前 Search All mount 和 actor 授权，密钥进入平台秘密存储，HTTP 配置响应不返回密钥。

快速：配置 Google Custom Search 或 SerpAPI Google/Bing 时，通过 `fast_api` 的只读 `search.api` compiled 步骤调用固定服务地址，仍走公用后台 Task/日志/SSE；API 操作不创建浏览器页面。没有配置时明确显示“未配置 API，本次使用 Google 网页搜索”，执行原来的 Google 网页能力。已配置 API 调用失败时提示检查密钥、访问权限或额度，不静默改用网页，也不回传可能包含密钥的请求 URL。API 返回普通自然搜索标题、链接和摘要；结果继续走原有合并、卡片和整理流程。

Google 官方 API 仅适合仍有访问权限的既有账号；Bing 原 Web Search API 已停止服务，因此 Bing API 入口由用户配置 SerpAPI 第三方服务，不冒充官方免费 API。参见 [Google 官方说明](https://developers.google.com/custom-search/v1/overview) 和 [微软停用公告](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement)。配置第三方服务时查询会发给该服务，界面明确显示其名称。

优选：先提交 `plan` 能力，以普通配置的 simple 模型执行 `ai.transform`，选择 1–3 个已支持来源、每源 3–10 条、X 热门/最新和小红书综合/最新/最多点赞，以及当前语言的短理由。菜谱等生活实践类任务优先考虑小红书高赞/综合，演示需求考虑视频源；事实类优先网页/Wikipedia，时效讨论优先社交最新。模型结果必须通过来源白名单、数量及枚举校验，失败时提示，不执行未知来源或替用户改查询。然后每个来源仍独立提交原有后台 Task；浏览器分身登录态要求保持不变。策略与结果整理是两个独立 AI 步骤。

在线验收：菜谱优选实际选择小红书最多点赞、B站和 Google；B站/Google 与整理 Task 完成，合并 12 条。小红书未核验最多点赞，本轮未计成功；排序核验失败已改为明确来源失败，附“自定义综合/其他来源”的建议，不再抛成占住队列的浏览器中断。64 项 Python 与 21 项 Node 回归通过；有效 API 凭据在线请求尚未验收，密钥隔离/日志脱敏/API 无 Tab 的 journal 路径由回归覆盖。

最终 App-Dev 界面确认：模式下拉含快速/优选/自定义；快速出现 API 配置按钮与无 API 时 Google 网页提示，配置对话框为服务下拉/密码输入/Google 引擎 ID，未输入测试密钥；自定义恢复来源、数量、广告及保留页面等选项。

## 用户自定义搜索源

自定义模式的来源列表末尾提供“＋”。对话框只需填写网站 HTTPS URL，使用当前所选浏览器分身；公用 `discover_source` 后台 Task 打开网站、检查实际控件，以 standard 档 AI 总结名称/说明/类别并识别搜索入口。保存校验实际控件引用与同源访问；不能识别时说明登录/验证码或入口问题，不凭空添加一个可用源。

配置持久化在本机平台 SQLite 的 `custom_search_sources` 表，按用户隔离、相同 URL 去重、最多 30 个，可用来源旁的 × 移除。不存网页 localStorage/IndexedDB。重启 Local 或重新挂载 Mini-App 后读取同一数据库配置。前端仅提交完成的分析 Task ID，不能上传任意 Source、代码或扩大网站范围。

自定义查询采用宿主固定流程：打开原 URL → 有界 AI 找到搜索入口、输入原查询并执行站内搜索 → 从实际可见链接中筛选结果。所有执行继续使用公用后台 Task、native BiDi 与站点范围/协助机制；结果进入既有合并去重、来源卡片、翻译排序和可选总结。优选模式也可选这些用户来源；快速 API 模式保持原有行为。初版是自适应搜索，识别到搜索入口不保证任意网站或未来查询都成功，登录/验证码/反爬与复杂跨域跳转仍可能需要协助。

实测：从 `https://en.wikipedia.org/wiki/Main_Page` 自动添加来源，重载 App-Dev Local 后来源仍在；独立搜索 DeepSeek 成功返回两条真实条目链接，并正常完成中文摘要与来源展示。在线发现并修复控件 role 为 null 的后台异常。95 项 Python 与 22 项 Node 回归通过。

各源列表提取现在继承公用 Mini-App 的有界网页结构恢复：先运行编译规则；结构/加载不匹配时，native BiDi 读取最多 100 个实际可见链接，AI 在 45 秒内选择候选 ID，后台校验后复制真实标题、正文片段、封面与链接。正常编译成功不额外调用恢复 AI；来源排序核验失败、服务不可用、登录或验证码不自动放宽。回退结果标记 `layout_recovery_partial`，不能保证完整互动数或任意改版都可恢复；未知/空选择和模型不可用仍明确失败。详细要求见仓库 `docs/ai2apps-web-agent-mini-app-package-contract-v1.md`。

## 可选原文总结与可信来源评估

搜索及原有排序完成后，网页结果提供“AI 总结要点”和“找出更可信结果”两个按钮；只在用户选择后执行，不自动阅读全文。按已有相关性排序取最多 5 个网页候选，最多成功阅读 3 篇，每篇正文最多 6000 字符。原文读取、AI 分析和引用封装属于同一个 `summarize` 公用后台 Task，提交后不依赖前端继续打开；使用本次搜索的浏览器分身。

候选附带原搜索 Task ID。Broker 验证 Task 属于当前 actor/Mini-App 且已完成，并确认每个 URL 是该搜索实际观察的结果；不能借总结入口提交任意链接。只导航允许的公开 HTTP(S) 页面，每个 URL 继续受 Source scope/公开地址验证；使用既有 native BiDi Readability/访问协助。付费或受限页面跳过，保留失败原因；登录/验证仍需在任务栏协助。没有成功读到正文则任务失败，不把搜索摘要充当正文。

AI 使用 standard 档，指令要求只依据实际读到的文本、给事实要点引用、比较一手证据/可识别作者与出版方/引用/时效/交叉一致性，说明冲突、有限阅读和不确定性。域名声誉或热度不单独证明真实性。“更可信”仅在本次读到的文章内比较，不是全网独立事实核验。证据不足时不推荐。

模型只产生 `source_id` 引用，不产生链接；最终 Task 把分析结果和读取器的原始来源绑定，前端拒绝未知引用、重复来源、空正文和危险 URL。引用按钮经原有 `openResult` 在对应分身打开实际观察过的原帖/文章入口。JSON 导出包括结论和引用元数据，不导出正文。新搜索清理旧总结，取消新搜索保留已有报告。

按钮当前针对网页文章；原始帖子/视频仍由其现有结果卡片展示，不将未读取的视频内容或搜索列表标题当作文章原文。

验收：86 项 Python 和 22 项 Node 回归通过，覆盖来源 Task 授权、逐 URL 作用范围、付费受限跳过与默认兼容、可信读取结果封装、未知引用拒绝、空正文和危险链接拒绝及旧搜索流程。App-Dev 实测 `Python asyncio documentation`：Google 搜索/排序完成，用户点击总结后一个后台 Task 成功读到 3 篇原文，生成中文要点、官方文档优先的可信度理由和 6000 字符/未独立核实的限制说明。引用按钮在 Default 打开 `https://docs.python.org/3/library/asyncio.html`，已核对实际文档；测试引用 Tab 已关闭，用户原有 Tab 保留。按钮、报告和引用布局经 AX 与原生截图确认。
## 2026-10-19：Agentic 与 Mini-App 共享确认流程

当前入口使用 `web/workflow.js`，替代旧版点击优选后立即搜索的提交处理器。
第一次点击“优化搜索词”只运行共享准备 Task；展示优化词和推荐原因后，用户选择模式，
编辑搜索词和来源，再点击“搜索”。优选和自定义共用来源复选框，快速使用已配置 API 或 Google。
准备记录、确认回执和后端 Run 与 Agentic 参数表单共用，不能以模型 JSON 伪造确认。

确认后显示来源搜索进度、文章列表及逐篇正文阅读进度，随后自动根据已读正文总结并保留引用。
当前最多读取五篇、每篇 12000 字符；读取失败单列，全部无正文时失败。刷新恢复草稿或观察
原 Run，不重新搜索；原搜索页面保留/清理确认继续复用共享任务生命周期。
这一流程替代下文历史版本的“优选立即执行”和手动点击原文总结行为。


### 启动草稿读取与保存（2026-10-22）

公共 WebAgent SDK `draft()` 返回 JSON 字符串或 `null`，不是 HTTP 的 `{value: ...}` 包装。首次使用没有草稿时按空状态启动；已有字符串先解析，再由一搜到底校验工作流标识。保存必须使用公共 `ai2apps.mini-app-draft/v1` envelope，`miniApp=ai2apps.search-all`、`workflowSchema=search-workflow/v1`；业务准备状态仍由 Mini-App 拥有。恢复只观察原任务，不重新提交搜索。兼容已有 `search-workflow/v1` 业务对象的只读恢复。

本次修复仅在所属 UI 适配公共 SDK 契约，不修改 AaAT 发现、路由、授权、后台执行或共享草稿入口。验证使用 SDK 空值/字符串夹具及 Chrome 手机视口，未冒充真实手机运行记录。

### 逐来源展示、手动总结与 Agent 对话（2026-10-22）

Mini-App 搜索只执行确认后的来源搜索。所属 WebMiniAppAdapters 在每个来源完成及其 Google 地址解析完成后发布该源的结果，标准进度内容保留所有已完成来源的交错去重列表；人工协助和普通浏览器等待使用原 Task 状态。一个来源等待不再使其它来源的结果不可见。最终结果和中间结果复用同一 owner 合并方法。

Mini-App 的“帮我总结”单独启动持久 Search workflow Run，冻结当前服务器核验过的搜索结果，复用 Web Reader、正文证据与引用验证；不重新搜索。Agentic `web.search` 默认仍按原契约完成搜索、正文阅读和总结。总结动作和状态查询均验证 Mini-App mount、actor/Installation、App scope、原 Session/confirmation，客户端不能指定任意正文 URL 或伪造搜索结果。

“在 Chat 中继续（Agent）”只在明确点击时创建新 Chat 线程，携带最多 50 条已观察结果（标题、URL、摘要、来源、Browser Task）与搜索 Run 引用。上下文以 USER 参考资料保存，标记 untrusted，不提升为 system prompt、工具声明或购买授权；线程启用 Agent 模式，等待用户输入后才执行。创建使用请求 ID 幂等并选中新线程，复用 ChatRepository 的 actor/client-scope 归属。Desktop/Mobile 经目标 Shell 重新读取所选线程，已有任务继续归公用后台所有。未对 General Agent 添加站点、商品或购买特例。

验证：同一来源集合中一个 wait_task 夹具挂起时，已完成源的结果已出现在进度；真实 Chrome 手机视口验证列表、手动总结和 Chat 点击入口。后台 Run 夹具验证搜索不自动读正文、总结不重搜、引用来自实际读到的证据、Chat 新线程及幂等、无自动 Agent/购买执行、Session 隔离。UI 外部网页和模型为夹具，不代表真机外部站点购买验收。

## DeepSeek Search（2026-10-24）

新增受信任声明 `deepseek`，使用官方独立 Search API；复用 Model Manager 已保存的官方 DeepSeek BYOK，不要求启用某个聊天模型。只有当前 Installation 的活动 core/owner 可复用该凭据。官方地址须为 https://api.deepseek.com 或其 /v1 形式；自定义代理和 Cloud 模型不能冒充官方 BYOK。Key 只在后台请求前解析，不进入 Package/Task/模型输入/返回值。

正常模式下 BYOK 可用即加入 Search All 与 AaAT 的候选，快速模式优先 DeepSeek。请求前复核身份、配置、精确站点作用域、query 1–128 字符及系统/Task 隐私模式。隐私模式下禁止外发到该搜索 API，模型整理仍沿公共隐私路由；不静默截断查询、不在失败后改走付费 Cloud。结果沿公共 Task / 逐源进度 / 合并与手动正文总结流程；首版不接 Fetch。Desktop/Mobile 使用同一 Package 页面。

Cloud OpenAPI 1.78.0 已接入：优先官方 BYOK；没有 BYOK 时探测 Cloud 能力，按明确确认的价格版本与费用上限执行。成功且非空收取 1 Point；失败、超时、空结果不收费。未知请求只回读同一 request_id，不自动重发或切换来源。隐私模式阻断外发。Desktop/Mobile 与 AaAT 共用 owner 业务服务和确认守卫；付费同意默认不勾选。快速搜索可直接准备原始搜索词，无需 LLM 优化；费用确认独立显示。详见 [Local 接入与验收](deepseek-cloud-search-local-acceptance-20261024.md)。

### 重复搜索与确认隔离（2026-10-24）

Mini-App 每次明确点击搜索提交稳定 request_id，owner 在同一作用域内创建独立执行 preparation，复用已经完成的规划 Task。原确认永不改写；相同请求重放复用同一 preparation / Run，改参重放仍拒绝。正在运行的搜索或总结不能被复制为新的执行。Agent Run 所有的确认不得通过此 App 入口复制，继续原 AaAT 确认守卫。旧客户端无 request_id 时保留原确认幂等行为。

Desktop/Mobile 草稿持久化尚未确认收到响应的提交体，冻结条件并允许用户按同一提交重试；收到确认后才切换到新执行记录。页面更新后旧 Package 版本的草稿重新进入准备阶段，保留搜索文本，不绕过 digest 守卫。


## 搜索读取的无人值守策略（2026-10-24）

Search All和其搜索结果Web Reader适配器统一使用 `stop_on_assistance=True`：登录、验证码、同意、未知弹层等人工等待都视为单页不可读，通过TaskTree取消该子任务，父搜索不转发求助入口，也不等待用户。每来源/每页10秒内完成或失败；在同一次已确认搜索结果中有限补位，保留成功正文。无可读来源时结束为失败，不伪造摘要或绕过访问控制。独立交互式Web Reader原有needs_user接口兼容；不是搜索任务的交互可保留协助。

详见 [时间预算与无人值守策略](bounded-search-reading-20261024.md)。
