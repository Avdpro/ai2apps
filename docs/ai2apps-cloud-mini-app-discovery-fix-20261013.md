# Cloud 交接：Mini-App 分类与历史索引修正

日期：2026-10-13。状态：**待 Cloud 实施与部署**，不是已上线接口说明。
本文优先于旧 Mini-App discovery 需求稿中的分类与兼容建议。本次仅修改文档，未改 Cloud 或客户端。

## 1. 问题与交付目标

Mini-App 安装载体仍为 `package.type=app`，不新增 Package 类型或安装生命周期。
当前 Discover 从响应的 `miniApps` 展开组件卡片；Cloud 历史 schema 拒绝该字段，一些包使用
`--omit-mini-app-catalog` 发布，远端仅剩 App 类型，Mini-App 分类因此为空。
安装后从本地 app.yaml 恢复组件，不等于未安装时的远端目录可发现。

历史证据见 `ai2apps-avatar-suite-release-2026-10-05.md`、
`ai2apps-yue2-audio-packages-release-2026-10-06.md`、
`ai2apps-media-voice-studio-suite-0.2.1-release.md`；部署前须重新探测当前 Cloud，不能仅凭旧失败记录判断现状。

必须同时交付：新包 schema/投影校验、旧包可信回填、查询与缓存一致性、客户端协议交接。
不能只放宽 schema；不要求旧包重签、升版或用户重装。

## 2. Schema 与可信输入

对齐 Desktop `ai2apps/packages/contract_v1.py` 的 `validate_mini_app_catalog` 和
`mini_app_catalog_from_app_manifest`，固定源码提交并建立跨端 golden fixtures。

- 顶层 `miniApps` 仅允许 App Package；省略合法，出现时为 1–64 项数组，不用空数组替代省略。
- 必填：`componentId`、`displayName`、`version`、`lifecycleKind`、`categories`、`placements`。
- 可选：`description`、`icon`；当前 v1 不额外注入 `localizations` 等未定义字段。
- ID 遵循既有 canonical ID 校验；组件 ID 包内唯一；版本遵循既有 semver。
- 名称 1–160 字符，描述最多 2000；生命周期为 `clip|project|live_session`。
- categories 为 1–8 个无重复 lower-kebab 标识，placements 为 1–16 个无重复宿主 ID。
  分类允许扩展，不能把当前 UI 标签集固化为封闭枚举；icon 使用既有 lower-kebab 校验。
- 从 `app.yaml.mini_apps` 推导投影；显式 miniApps 必须与之结构一致，不符返回
  `mini_app_catalog_mismatch` 等结构化错误，不能静默删字段或优先信任一方。

先验证 artifact 大小/摘要、Publisher envelope 与文件索引，再读取索引覆盖的 app.yaml，
校验该文件摘要。复用可信制品解析，限制解压大小/文件数，拒绝路径穿越、重复路径和链接逃逸，
安全解析 YAML，不运行包内代码。禁止按名称、简介、ID 后缀或客户端自报字段猜测组件。

## 3. 旧包回填：不修改签名内容

1. 对已发布且可见的 App releases 做 dry-run 清单，至少核查音频生成、媒体语音、数字人套件；
   实际范围以 Cloud release 清单为准，不限三个硬编码 ID。
2. 按原始 `packageId + version + artifactSha256` 验证既有不可变制品。
3. 从签名文件索引覆盖的 app.yaml 推导组件及 launcher 可见性，写入**独立派生目录索引**。
   不向旧 manifest 插字段，不改 archive、envelope、版本、digest、下载 URL 或历史审核记录。
4. 保存 package/version、artifact/app.yaml 摘要、提取器版本、索引 revision、操作者/时间和结果。
   任务幂等、可续跑；失败条目隔离并报告，不猜测、不绕过验签。
5. 普通 App 保持原行为。发布、撤销、回滚同步更新索引，不能混合不同版本组件。
6. 审核后原子切换新目录 revision，失效 search/recommendations/detail/CDN 缓存。
   若进入签名 Repository 元数据，生成新签名版本，禁止覆盖旧 Snapshot。
   回退恢复前一索引或向前发布修正 revision，不触碰 Package 字节。

响应可以在 release 展示对象上返回派生 miniApps，但与原始签名 manifest 分离；不得冒称该字段
原本就在 Publisher 签名 manifest 内。目录索引不授予权限，安装仍验签并核对真实 App 定义。

## 4. 分类与 API：分两步交付

以下为目标契约，新增字段/参数须由 Cloud 回交 OpenAPI 后与 Desktop 对齐，不宣称已支持。

| 内容 | Apps 分类 | Mini-Apps 分类 | 安装目标 |
| --- | --- | --- | --- |
| 无 Mini-App 的普通 App | App 卡片 | 无 | App Package |
| launcher 为 false 的纯 Mini-App 提供包 | 不显示普通 App 卡片 | 每组件一张 | 同一个 App Package |
| launcher 可见且有独立入口的混合包 | 一个 App 卡片 | 每组件一张 | 同一个 App Package |

launcher 缺省沿用当前默认可见语义。不能仅凭 miniApps 非空隐藏混合包。
All 按上述可见卡片混排；Installed 必须保留父包管理/升级/卸载入口。

### A：先补齐当前客户端能消费的目录信息

搜索、推荐、详情和指定版本查询返回同版本 miniApps，历史投影来自上述可信回填。
保留 Package 响应形状及 `type=app` 的底层载体语义：当前 Mini-App 页也使用这个过滤，
不能突然改成仅返回 launcher App。建议增加独立展示字段 `appNavigation: {launcher:false}`，
来源为签名 app.yaml，不放入旧 Contract manifest；最终字段名由 OpenAPI 确认。

### B：协调客户端接入原生内容过滤与组件分页

建议支持 `content=app|mini-app`、`mini_app_category`、`studio`，与已有模型过滤共存。
组件检索包括 ID、名称、描述、分类和宿主；先过滤后分页。
组件响应提供稳定键 `packageId#componentId`、父包版本、组件版本与父包兼容性；
多宿主/多分类命中不重复同一卡片，不同父包同组件 ID 不合并生命周期。

提供明确能力标识或版本协商区分“Package 列表 + miniApps”和“组件卡片列表”，不向旧客户端
发送会再次展开的组件响应。card schema 与能力发现方式随 OpenAPI 交接，Desktop 显式接入。
组件协议的 limit 表示过滤后的卡片数，支持 24，超过 100 条可完整遍历；不能依赖预取 100 个 App。
游标绑定目录快照、完整查询/排序及可见性上下文，无重复遗漏，末页 null，过期/错用有结构化错误。
参照 [分页要求](ai2apps-cloud-discover-pagination-requirements.md)。

## 5. 安全与生命周期

Publisher、权限、平台约束、下载/签名、审核、安装、升级、回滚、卸载均继承父 Package。
组件版本不是独立 release，不合成组件 artifact URL。多个组件卡片不能导致重复安装父包。
匿名/登录、发布/撤销与逐页可见性校验沿用 Registry 规则，索引不能泄露未发布内容。

## 6. 验收与回执

- 新 App 默认构建含 miniApps，submit/review/publish 全链通过；非法类型、重复 ID、越界字段、
  投影不符及被篡改/未索引 app.yaml 被拒绝。
- 历史套件组件与原签名 app.yaml 一致，artifact/envelope 摘要及版本不变；在干净未安装实例可发现。
- 普通 App、纯组件包、混合包满足分类表；分类、宿主、关键词组合检索正确。
- A 模式在旧 Desktop 补齐元数据；B 模式在适配后的 Desktop 验证 Apps 排除纯组件包、All 混排、
  超过 100 个组件完整翻页。明确区分两种模式，不把 A 宣称为 B 已完成。
- 组件安装/升级/卸载操作父包；升级/撤销无遗留索引，旧客户端下载安装兼容。
- 回填重复运行无重复记录、部分失败可续跑、缓存失效与索引回退通过。

Cloud 回交部署版本/OpenAPI、schema/响应样例、能力协商方式、dry-run 与回填成功失败清单、
前后摘要、索引 revision、匿名检索/分页测试及回退证据。
Desktop 后续接入 launcher 分类、原生过滤和组件分页；本次文档修订不代表这些已实现。
