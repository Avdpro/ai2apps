# AI2Apps Gallery 产品、技术与开发计划 v1

状态：第一阶段开发中  
日期：2026-08-25  
所有者：AI2Apps Local Runtime / Shell  
系统 App ID：`ai2apps.gallery`

## 1. 产品定义

Gallery 是与 Chat 同级的 AI2Apps 内建系统 App，也是所有 AI 产物的本地资产中枢。它统一保存图片、视频、音频、网页、文档和其他文件，并通过集合索引、系统级边栏、拖放和 Host Bridge 向其他 App 提供访问能力。

Gallery 不是 Finder 文件夹的镜像。实体内容由 Gallery 统一管理；“最近”“下载”“公开”“个人”和项目目录是资产索引或规则视图。同一资产只保存一次，可以同时出现在多个集合中，并在不同集合中拥有独立顺序。

一句话定义：

> Gallery = Local Object Store + Asset Catalog + Collections + System Picker/Drop Target。

## 2. 目标与非目标

### 2.1 v1 目标

- 注册为 `ai2apps.gallery` 内建系统 App，用户级单例，默认固定在 Shell 导航。
- 导入本地文件并以 SHA-256 内容寻址保存；相同用户的相同内容复用实体 Blob。
- 支持图片、视频、音频、网页、文档与通用文件。
- 提供“最近”“下载”“公开”“个人”“废纸篓”等系统集合，以及自定义/项目集合。
- 支持集合内手动排序、复制索引、移动索引和从集合移除。
- 区分“从集合移除”“移到废纸篓”“永久删除”。
- 支持预览/下载内容，并为后续跨 App 拖放提供稳定 Asset ID 与 URL。
- 提供完整 Gallery Entry；随后提供 Shell 级 Gallery Mini-Entry。

### 2.2 暂不纳入第一阶段

- Cloud OSS 同步和跨设备内容复制。
- 对公网直接发布本地 Blob；“公开”首版只保存发布意图，不自动穿透网络边界。
- 视频转码、波形、网页构建和复杂缩略图流水线。
- Finder 扩展、macOS Quick Look 扩展和系统照片图库导入。
- 多用户共享集合与协作排序。

## 3. 核心概念与不变量

### 3.1 Asset

Asset 是用户看到并引用的资产记录，包含稳定 ID、显示名、媒体类型、种类、大小、内容哈希、元数据、来源和生命周期状态。Asset 引用一个内容寻址 Blob。

不变量：

- Asset ID 在内容存在期间保持稳定。
- 文件名不是身份；内容哈希才用于 Blob 去重。
- 不同用户不能通过哈希推断或访问彼此资产。
- 普通 App 只获得授权 Asset 的引用或导出结果，不获得 Gallery 根目录路径。

### 3.2 Blob

Blob 是实体字节，首版位于 AI2Apps 管理的 `platform/artifacts/gallery/sha256/<prefix>/<digest>`。写入采用临时文件、`fsync` 和原子替换；数据库只在 Blob 成功落盘后提交记录。

### 3.3 Collection

Collection 保存 Asset 索引，不拥有 Blob。集合分为：

- `system`：最近、下载、公开、个人、废纸篓。
- `custom`：用户自建集合。
- `project`：项目专用集合，可在元数据中记录项目来源。

“最近”是按资产时间动态生成的规则视图；其余集合可包含显式索引。一个 Asset 可出现在多个集合。

### 3.4 Collection Item

Collection Item 是 Collection 与 Asset 的关系，保存 `position` 与加入时间。手动排序只改变该关系，不修改 Asset。

### 3.5 删除语义

- 从集合移除：只删除一个 Collection Item。
- 移到废纸篓：Asset 状态变为 `trashed`，普通集合不再返回它，原索引保留以便恢复。
- 恢复：Asset 回到 `active`，原集合索引重新可见。
- 永久删除：数据库删除所有索引和 Asset；只有不存在其他 Asset 引用同一 Blob 时才删除实体 Blob。

## 4. 系统架构

```text
AI2Apps Shell
├── Gallery Dock / Navigation Entry
├── Gallery Mini-Entry（Shell 级持久边栏）
├── Gallery Full Entry（完整管理界面）
└── Host Bridge
    ├── openSidebar
    ├── pickAssets
    ├── saveArtifact
    └── revealAsset

AI2Apps Platform
├── Gallery API
├── Gallery Repository
├── SQLite Catalog
├── Content-addressed Blob Store
└── Event Store
```

职责边界：

- Full Entry/Mini-Entry：浏览、选择、排序和操作界面。
- Shell：全局入口、挂载生命周期、当前 App 上下文与拖放编排。
- Gallery API/Repository：资产、集合、权限、事务和所有权校验。
- Blob Store：实体文件、完整性与回收。

## 5. 系统 App 与 Mini-Entry

Gallery 使用用户级单例 AppInstance。完整 Entry 为 `ai2apps:system/gallery`。Mini-Entry 复用相同实例和服务，首版声明标准 `sidebar` placement；Shell 级持久侧栏在 Mount 协议扩展后启用。

目标挂载语义：

```yaml
instances:
  mode: singleton
  scope: user
entry:
  kind: host
  resource: ai2apps:system/gallery
mini_entry:
  kind: host
  resource: ai2apps:system/gallery-mini
  placements: [sidebar]
presentation:
  shell_sidebar:
    persistent: true
    singleton: true
```

Mini-Entry 是 Gallery 的紧凑表面，不是 Gallery 服务本身。关闭边栏不会停止服务或删除选择状态。

## 6. 数据模型

### 6.1 `gallery_assets`

- `id`
- `owner_user_id`
- `name`
- `kind`: image/video/audio/web/document/file
- `media_type`
- `content_hash`
- `size_bytes`
- `storage_key`
- `source_app_id`, `source_ref`
- `metadata_json`
- `status`: active/trashed
- `created_at`, `updated_at`, `trashed_at`

同一用户、同一内容哈希、同一显示名复用 Asset；Blob 可以被同一用户的多个 Asset 记录引用。

### 6.2 `gallery_collections`

- `id`
- `owner_user_id`
- `name`
- `kind`: system/custom/project
- `system_key`: downloads/public/personal/trash，普通集合为空
- `sort_mode`: manual/created_desc/name
- `metadata_json`
- `created_at`, `updated_at`

### 6.3 `gallery_collection_items`

- `collection_id`
- `asset_id`
- `position`
- `added_at`

## 7. API v1

基址：`/v1/platform/gallery`

- `GET /collections`：列出系统和用户集合，包含数量。
- `POST /collections`：创建 custom/project 集合。
- `GET /assets?collectionId=&kind=&status=`：列出资产；无集合时为最近视图。
- `POST /assets/import`：multipart 导入文件，并可加入目标集合。
- `GET /assets/{id}/content`：同源鉴权预览/下载。
- `POST /collections/{collectionId}/assets/{assetId}`：复制索引到集合。
- `DELETE /collections/{collectionId}/assets/{assetId}`：从集合移除。
- `PUT /collections/{collectionId}/order`：提交完整顺序。
- `POST /assets/{id}/trash`、`POST /assets/{id}/restore`。
- `DELETE /assets/{id}`：永久删除。

后续 Host Bridge：

- `ai2apps.gallery.openSidebar(options)`
- `ai2apps.gallery.pickAssets(options)`
- `ai2apps.gallery.saveArtifact(options)`
- `ai2apps.gallery.revealAsset(assetId)`

## 8. 安全与隐私

- 所有查询和变更都强制绑定 `RequestPrincipal.actor_user_id`。
- 内容接口不接受任意磁盘路径；只通过 Asset ID 解析受管 storage key。
- storage key 必须解析在 Gallery Blob 根目录内。
- 上传大小首版受平台资源导入上限约束，流式计算哈希，不把大文件整体读入内存。
- 文件名经过净化；响应使用安全的 `Content-Disposition`。
- `public` 是权限/发布意图，不等于无需认证的下载 URL。
- 永久删除前进行引用检查，避免删除仍被其他 Asset 使用的 Blob。
- Gallery 事件写入统一 Event Store，便于审计来源和删除行为。

## 9. UI 信息架构

完整 Entry：

```text
左栏                  顶部工具栏                  内容区
最近                  搜索 / 类型筛选             网格或列表
下载                  排序 / 新建集合              资产卡片
公开                  导入                        多选操作
个人
项目
自定义集合
废纸篓
```

资产卡片提供预览、类型、名称、大小和时间；多选后可复制/移动到集合、移到废纸篓或导出。首阶段优先实现浏览、导入、集合切换与删除生命周期。

Mini-Entry：

- 宽度 300–420 px。
- 顶部为最近/集合切换和搜索。
- 中部为紧凑缩略图网格。
- 支持拖出、点击插入当前 App、展开完整 Gallery。
- 选择模式显示“插入 N 项”，普通模式显示资产操作。

国际化：

- 完整 Entry、Mini-Entry 和 Preview 共用 AI2Apps 的 `t()` / `window.t()` 翻译字典。
- 首版完整支持简体中文与英文，并跟随 AI2Apps 全局语言设置切换。
- 系统集合使用稳定的 `system_key` 存储，名称只在显示层本地化；用户创建的集合名保持原文。
- 其他语言缺少 Gallery 专用翻译时继承英文回退，避免显示翻译键。

## 10. 开发阶段与验收

### Phase 1：系统 App 与本地资产核心

- [x] 产品/技术方案与边界。
- [x] 注册 `ai2apps.gallery` 系统 App 和 Host Entry。
- [x] SQLite 资产、集合、索引迁移。
- [x] 内容寻址导入、去重、列表、内容读取与删除生命周期。
- [x] Gallery REST API。
- [x] 基础完整 Entry：集合导航、网格、导入和删除。
- [x] 用户目录删除（仅移除目录索引，保留资产；系统目录受保护）。
- [x] 完整 Entry、Mini-Entry、Preview 及动态通知的中英文国际化。
- [x] Repository/API/System App 针对性测试。

验收：登录用户可以打开 Gallery，导入文件，在个人/公开/自定义集合中建立索引，排序、预览、移除、回收、恢复和永久删除；另一用户无法读取这些资产。

### Phase 2：Shell Dock 与 Gallery Mini-Entry

- [x] Gallery Mini-Entry Host 资源（现有 Conversation sidebar placement）。
- [ ] Shell 固定 Gallery 按钮和可调整宽度边栏。
- [ ] Shell 级 singleton/persistent mount scope。
- [ ] 在 App 切换后恢复集合、滚动和选择状态。
- [ ] `openSidebar`、`pickAssets`、`revealAsset` Bridge。

验收：用户在 Chat 或其他系统 App 中可随时展开同一个 Gallery 边栏，并选择资产返回当前 App。

### Phase 3：跨 App 拖放与产物自动入库

- [ ] Gallery 拖入：浏览器文件、Finder 文件、App Artifact。
- [ ] Gallery 拖出：Asset 引用、下载 URL、浏览器 File、桌面临时导出。
- [ ] Chat、Video Studio、Read Aloud 和 Image Service 生成完成后自动登记。
- [ ] 来源 App/Run/Prompt/Model 元数据和“在来源中打开”。

验收：生成产物无需重复复制即可出现在 Gallery；拖到 Chat 后仍引用同一 Asset。

### Phase 4：预览流水线、网页资产与公开发布

- [ ] 图片缩略图、视频 poster、音频波形与网页截图。
- [ ] 复合 Web Asset（入口、资源清单、源项目、构建产物）。
- [ ] 发布授权、公开链接、撤销和访问审计。
- [ ] 存储配额、垃圾回收、完整性扫描和备份策略。

## 11. 测试策略

- Migration：空库、升级、外键、唯一约束。
- Repository：去重、用户隔离、集合排序、删除/恢复、Blob 引用回收。
- API：认证、参数校验、上传限制、内容响应和错误 envelope。
- Shell：系统 App 可见性、Host Entry、成员权限、Mini-Entry 恢复。
- UI 静态契约：App ID、API 地址、拖放与关键操作存在。
- E2E：导入 → 加入两个集合 → 重排 → 从一个集合移除 → 回收 → 恢复 → 永久删除。

## 12. 待决策项

- “下载”集合是导入来源标签，还是所有导出到 Downloads 的操作历史；v1 暂按显式集合处理。
- “公开”是否只允许属于 Core 用户；v1 允许每个用户维护自己的发布意图，真正发布时再做角色校验。
- 系统生成 Artifact 是迁移为 Gallery Asset，还是由 Gallery 建立外部 backing reference；Phase 3 决定并提供迁移工具。
- Shell 同时允许几个系统级侧栏；Phase 2 默认只允许一个，Gallery 占用专用快捷入口。
