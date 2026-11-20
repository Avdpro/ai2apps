# 情报中心 ZIP 导入导出 v1

日期：2026-11-01。

## 使用

顶部“导入 / 导出”提供全部频道导出、当前频道导出、ZIP 导入；移动版进入频道后在更多菜单中提供当前频道导出和 ZIP 导入。

导入先预览新增、合并、保留、冲突数量，再确认提交。ZIP 最大 128 MiB。预览绑定备份内容及目标数据快照；目标频道发生变化时重新预览。其他频道更新不阻断导入，目标频道正在采集时拒绝导入。

## 数据与合并

- 包含频道及栏目、信息源、完整文章正文和图文块、原文缓存、稿件、偏好、静态聊天与更新历史，以及所选文章关联的实体证据和机会线索。全量导出还保留无文章证据的实体关注对象。
- 本地手动上传的原始文件一起打包并按 SHA-256 校验。远程图片保持原网址；**本版不是远程图片离线备份**，导出不会访问原网站。
- 频道优先按导出来源身份匹配，再匹配同名频道。同名不唯一时拒绝，先重命名。已有频道保留本地设置，栏目按名称映射并补充新增栏目。
- 信息源按规范化 URL、类型及社交查询条件去重。新导入来源暂停，并重新绑定默认分身；不迁移 Profile、浏览器生成 Agent 和社交运行租约。
- 文章按来源身份、同源本地 ID、相同内容以及唯一的“标题＋完整来源集合”匹配；部分来源重叠或主题相似不自动合并正文。
- 冲突文章／稿件保留本地版本，导入内容另存 `_transfer_conflicts`。文章详情提供“导入冲突版本”文本查看；完整图文结构仍保存在数据包和冲突记录中。稿件冲突本版保存在数据中，不覆盖正在编辑的本地稿件。
- 实体按稳定身份或唯一的名称／别名与类型匹配，补充不重复的事实、别名和属性，保留本地设置。
- 重复导入使用稳定来源标识和内容摘要去重；通过另一台设备再次导出也保留原来源身份。
- 新频道自动更新关闭、知识库绑定清空；已有频道保持本地设置。导入不启动采集、模型生成、知识同步或发布。执行历史不恢复成正在运行任务。

ZIP 中包含格式和版本声明及 `intelligence.json`，附件位于受校验的 `attachments/<sha256>`。不直接解压任意路径、不导入账号身份，不包含 Cookie 或登录凭据。事务失败回滚数据库并清理本次新建附件。

## 接口与实现

所属 App API：`GET /intelligence/backup?channel_id=…`、`POST /intelligence/backup/preview`、`POST /intelligence/backup/import`。沿用当前用户与 App 访问检查；导入需提交预览返回的 `expected`。与系统路由组合后的前缀为 `/v1/platform/intelligence`。

实现位于 `intelligence/transfer.py`，UI 在原情报中心页面中，不新增 AaAT 业务分支或 Cloud 行为。Python 修改需要重启对应 Local，静态资源刷新生效。

## 验证

新增 transfer 与 API 回归覆盖全量／单频道、重复与转手导入、正文冲突、栏目与实体映射、附件归属、目标运行保护、预览数据／备份变化及非法包；既有文章图文、API 回归共同验证。桌面 1200px／移动 390px 的独立浏览器夹具验证上传、预览、确认和文本安全；不等同于对用户真实数据执行导入。

## 最近范围与离线 HTML（2026-11-01）

导出入口现在先打开设置窗口，可选择全部／当前频道，全部／最近 24 小时／最近 7 天／自定义时间，新增及内容更新／仅新增，以及 ZIP／单频道 HTML。日期控件使用设备本地时间，提交转换为带时区 UTC；筛选区间为 `[开始, 结束)`。

最近 ZIP 仍然是可独立导入的数据包，包含筛选文章的完整正文、图文结构、原件及所需来源缓存／偏好／可完整引用的关联稿件和实体证据。频道／栏目及信息源定义保留；不携带无关的聊天、更新日志或过滤历史。阅读／收藏／反馈不会使旧文章进入最近列表。新增封面或图片变化会写入独立的 `content_updated_at`，不改变实体事实所使用的正文版本时间；旧数据按已有创建／更新时间回退。

这是按时间范围导出，不是维护基线的变更日志；不传播删除、取消收藏等操作，也不会自动融合两个分支的正文。仍沿用既有导入预览和冲突保留规则。

离线 HTML：

- 仅单频道；可同样筛选时间范围。包含频道说明、栏目筛选、文章目录、全文搜索、文章正文、段落图片及来源链接。
- 图片以 Data URL 直接写入每个图片标签的 src，不依赖 JavaScript 注入，因此禁用脚本的手机文件预览也能显示。同一地址只读取一次、复用转换结果；同图多个显示位置可能重复写入文件，以换取无脚本兼容性。原有段落位置保留，其余图片在“更多文章图片”中查看。
- 默认阅读版：自动转正，最长边 1600px，适度压缩并剥离原始元数据；原图版保留受支持的原始图片数据。
- 封面和图片仅从所选已保存文章读取。复用受限公开 HTTP 客户端，无 Cookie、登录／验证码／视觉协助流程；本地图片严格按当前用户原件引用读取。失败列入 HTML 缺失清单，可手动打开公开原图链接，不静默加载外链图片。
- HTML 不包含聊天、偏好、稿件、运行日志或可导入的业务数据库；它是阅读／分享格式，恢复仍使用 ZIP。
- 文本和链接转义，图片仅允许经过验证的栅格格式；拒绝 SVG、脚本和私网目标。所有必要 JS/CSS 内嵌，CSP 限制脚本与网络访问。离线浏览器测试确认无外部请求。

导出生成复用 `intelligence.export` System Task；不占 Web-Task 名额，也不调用模型。页面关闭／刷新不取消后台任务；通过最近导出接口和原任务引用恢复查看，显式取消走既有 System Task 取消机制。Local 重启时未完成导出会标记中断，不声称跨进程恢复尚未保存的图片读取；可以重新发起导出。

生成文件保存在当前用户私有目录。下一次导出时按最多 20 份／7 天清理旧文件；没有后续导出时不声称定时删除磁盘文件。下载需要当前用户与 App 访问权；已清理的文件返回 410。单个文件上限 128 MiB，单图片读取上限 8 MiB／10 秒，图片最大 4000 万像素，HTML 最多 1200 个不同图片地址／5000 篇文章／2000 万正文字符；图片收集总时限 10 分钟，最多同时读取 4 张。达到图片容量限制时列为缺失，整个 HTML 超限则明确失败，建议缩小范围。

新增接口：

- `POST /intelligence/exports`：严格校验格式、范围、图片质量及稳定请求 ID，创建后台任务；同请求 ID 改参拒绝。
- `GET /intelligence/exports`：当前用户最近 20 次导出，支持页面重新打开后的恢复。
- `GET /intelligence/exports/{id}`：状态、进度和有界结果摘要。
- `POST /intelligence/exports/{id}/cancel`：取消原任务。
- `GET /intelligence/exports/{id}/file`：下载已完成且未过期的文件。
- 旧 `GET /intelligence/backup` 保持兼容，并支持 `since`、`until`、`changes=created|updated`。

实现：`intelligence/html_export.py`、`intelligence/export_jobs.py`，在既有 Intelligence System Task 注册组合中挂接；不修改共享 Agent／AaAT／调度器的执行规则。

### 移动激活与下载补充

Dev 与 App-Dev 的 Python 接口分别生效；共享静态源码已更新不代表另一实例已重启。2026-11-01 手机导出 404 已追踪为 Dev 未激活，现两实例均已核验。手机文件链接通过当前挂载的资源 URL，下载响应保留附件标记；刷新情报中心即可加载。详情见 `acceptance/intelligence-mobile-export-fix-20261101/README.md`。

### 目录与无脚本预览（2026-11-01）

HTML 导出新增 `include_toc` 布尔参数，默认 true；界面“包含目录”仅在 HTML 格式显示。取消时彻底省略目录 nav 和“返回目录”链接，每篇文章使用默认关闭的原生 details 卡片，summary 只有可用封面（无封面则回退到可用文章图片）与标题。点击图片／标题即可展开正文；原生折叠不需要 JavaScript。

旧 HTML 将图片放在 JSON 池中，由脚本补充 img.src；实际 AI 频道导出虽包含9张图、0读取失败，但脚本禁用的预览显示0张。现改成直接 src，已在同一文件的诊断副本中验证9张全部解码。原文件不自动修改，需重新发起导出。仅刷新后下载旧任务文件仍是旧文件。

### 导出格式收敛（2026-11-01）

按用户要求移除整页 Data URL 生成模式，只保留可导入 ZIP 和离线 HTML。移除复制链接、文本附件和 data-url 获取接口；旧格式请求校验失败，旧 Data URL 导出下载返回 410，历史记录不自动删除。普通 HTML 中的内嵌图片仍保留 Data URL src，以维持离线阅读能力。分享托管由后续“分享作品”Mini-App 负责，参见 [需求文档](share-works-mini-app-requirements-v1.md)。

### 图片恢复与登录署名（2026-11-01）

图片原地址失败后，有界解析 WordPress 图片代理内显式上游地址及 Cloudflare 图片变换路径，继续由安全公开 HTTP 客户端验证目标、重定向、大小和解码；无来源网站特例。本次11张失败代理图片只读实测全部从原站恢复。原图已删除或受访问限制时仍可能失败。

阅读 HTML 不包含缺图清单、错误计数或占位提示。owner 隔离的任务结果保留 missing_images，导出对话框展示具体原因和恢复数量，重新打开仍可查看。

提交导出时，通过当前浏览器登录的 Cloud 客户端读取账号显示名，验证账号 ID 等于请求 owner；可信显示名保存到内部任务上下文，公开请求不可指定署名，幂等比较排除内部字段。无法获得显示名时使用通用 AI2Apps 署名，并在对话框提示，不再使用“本地用户”，也不回退到邮箱或用户 ID。

### 折叠卡片阅读交互（2026-11-01）

无目录 HTML 卡片左上角显示蓝底白字未读绶带，展开后改为深灰底白字已读；当前文档会话内收起仍保持已读，不写本机阅读状态或向服务端回传。英文输出对应 Unread / Read。点击展开后，正文起点若在屏幕下方，向下平滑滚动至视口中段，露出正文；遵循减少动态效果设置。只有 CSP 精确 SHA-256 允许的固定本地脚本，无外部资源、搜索脚本或存储依赖。

禁用 JavaScript 的文件预览仍使用原生 details 和内嵌图片阅读，CSS 在展开时显示已读绶带；自动滚动和收起后保持已读需要脚本支持。带目录的完整文章模式保持不变。

标题与 AI2Apps 署名组成左侧文字块，右侧内嵌项目现有 logo-dark.svg；Desktop 72px、Mobile 56px。无需联网或脚本显示，点击 Logo 打开 AI2Apps 官网。

页面底色加深为 #e9edf3，卡片保持白色。未读/已读绶带以45度斜跨左上角；标题块仅显示导出日的日历日期，字号19px，不显示筛选日期跨度或时间。篇数/图片数另起一行，文章自身日期元数据保留。

### Adaptive reading HTML images (2026-11-01)

Reading-quality HTML is rendered once at its normal image quality. If its actual UTF-8 size exceeds 12 MiB, non-cover images are re-encoded from the already loaded bytes as WebP quality 62, longest edge 720px (no upscaling), and the HTML is rendered again. Only smaller encodings replace an image. Every article's displayed cover (including fallback covers and deduplicated aliases) is protected. Images still fill the reading width while preserving aspect ratio. Original-quality exports remain byte-preserving. This is a best-size pass, not a guarantee that the final HTML is below 12 MiB; covers and text may keep it larger. Export results include initial_size and images_compacted, and the dialog reports the compacted image count.

Exported no-contents HTML cards use immediate passive Pointer Event feedback. A short tap retains the subtle background for at least 120ms without delaying native expansion; an 8px movement, cancellation, blur or hidden page clears it. Desktop :active remains a hover-device fallback. Existing HTML files and hosted snapshots must be regenerated to receive this script.

Collapsed card layout: the old 34px summary-top spacer is removed. A cover card's corner ribbon may overlap its image. A text-only card reserves 52px at the title's left edge for the ribbon, and displays an escaped summary (body fallback) clamped to three lines with an ellipsis. The preview is hidden once expanded so the full article summary is shown only in the content.

### Link-preview metadata and custom sharing cover

HTML exports include an explicit head with description, Open Graph website/site/title/description/image/type/dimensions and Twitter summary-large-image/title/description/image tags. The export dialog optionally accepts a local raster cover up to8MiB/40Mpixels; the owner API strips metadata, transposes orientation and stores a600px JPEG in the existing owner-private attachment store. The export task receives only the owner-resolved attachment reference. Default: first rendered article cover in exported order, then a PNG rasterization of the existing AI2Apps SVG logo. The social thumbnail is independently bounded to600px, leaving reading covers unchanged.

The offline HTML embeds the thumbnail in its metadata. Share Works preparation materializes embedded OG/Twitter cover bytes as one hashed JPEG in the immutable publication directory and replaces only those metadata content values with a same-site absolute HTTPS URL. The confirmation snapshot/manifest includes this generated file, and normal public hash/image verification covers it. No network fetch is added to preparation; body images remain embedded. Existing exports and prepared/published snapshots are unchanged. This improves generic link-preview metadata; actual WeChat rendering/caching still requires physical-client acceptance, and no WeChat JS-SDK/domain-signature service is introduced.

Use “Use default cover / 使用默认封面” to clear a previously selected file. Changing to ZIP/all channels hides the HTML-specific cover control. Uploaded images stay owner-private until the user explicitly publishes a reviewed Share Works snapshot.

### Save completed exports to Gallery

Completed HTML and ZIP exports show “保存到 Gallery / Save to Gallery” beside Download. The owner endpoint `POST /intelligence/exports/{task_id}/gallery` checks current Intelligence access, exact Task ownership/kind/completed status, channel ownership and SHA-256 before importing through GalleryRepository. The resulting owner-private Gallery asset contains a source App/Task reference; Gallery's existing content-hash/name dedup handles repeated clicks. This is an independent Blob copy that survives the temporary export's cleanup. It does not publish the file. Changed, expired, unfinished and other-owner export references are rejected.

### AaAT: intelligence.export_html

Resolve an owned channel using discovery or intelligence.channels, then invoke with `channel_id`. Optional parameters: `hours` (1–720, default24), `quality` (`reading` default, or `original`), `include_toc` (defaultfalse). The default scope is rolling24hours, selecting new/content-updated articles by content timestamps, not confirmed source publication dates. AaAT and the App share submission and verified-output services and the existing `intelligence.export` System Task. Images use the original export fetch/embedding path, including adaptive compression and sharing cover fallback. No browser, login assistance, fresh collection, automatic Gallery save or public upload occurs.

The host-owned Session/Installation/invocation identifies a stable export request; its first window is frozen on replay, changed invocation arguments reject, and retries do not create another export. Progress follows the original Task; cancellation cancels that Task, failure/timeout is not a successful file. Only completed SHA-256-verified HTML is copied to the caller Session through Workspace import/dedup and returned in `files[].url`, allowing the existing generic Chat attachment projection and “分享作品 / Share Works” preparation to consume it. Public publication still requires that owner's separate confirmation.

AaAT review: business defaults, declaration, validation and result semantics live in Intelligence owner adapters. No shared Agent execution/routing/result-policy code changes are needed. The adapter uses existing Session authorization, System Task observation/cancellation and Workspace/Gallery services; there is no new execution queue, permission grant or automatic effectful fallback. Fixture scheduler/model tests are distinct from live-model acceptance. Mandatory boundary regression is recorded in the implementation receipt.
