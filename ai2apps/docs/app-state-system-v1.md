# 系统级 App-State v1：可移植界面设置

2026-11-05，B2 首版已实施。开发顺序见 [Bot 类型计划](bot-types-development-plan-v1.md)。本机制面向所有 App/Mini-App 的逐步接入；当前参考实现是 Imagine Studio 布局，以及文生图、修图、风格转换、参考图创作和合影五个内置 Mini-App 的图像设置。另已接入情报中心、Todo、Gallery 和知识库的首批导航/视图合同。它为 ASC-Bot 提供基础，尚未开放 ASC-Bot 创建。

## 状态分层与所有权

既有 `app_instances.state_json` 及升级快照继续保存 App 实例内部状态；Studio 草稿继续由所属 Studio 保存正文、素材和业务参数。App-State 是 owner 声明的可移植设置投影，不复制实例数据库、完整草稿、DOM、localStorage 或运行 Context，也不替代现有 App Chat 的 UI 命令/确认协议。

系统层负责版本化合同、严格校验、用户/安装/实例隔离、命名预设与恢复回执。所属 App 负责哪些字段可移植、当前模型/资源/选项是否有效、未保存编辑检查及原子界面恢复。通用层不识别模型名、风格名、业务 Tool 或页面结构。

恢复设置不执行生成/提交/上传/付款，不安装 Runtime/模型，不传递 App/Bot Access，不恢复 Task、Session、审批或登录。App-State 数据不是指令或执行授权。后续 ASC 先打开目标 App/Mini-App，再恢复设置，实际任务仍从目标 App 原业务入口启动。

## 可移植数据格式

```json
{
  "schema": "ai2apps.app-state/v1",
  "target": {
    "app_id": "ai2apps.imagine-studio",
    "mini_app_id": "ai2apps.imagine.style-transfer",
    "contract_version": 1
  },
  "values": {
    "model_id": "cloud/example/image-model",
    "style_id": "ghibli-256-png",
    "width": 1536,
    "height": 1024,
    "quality": "high",
    "format": "png"
  }
}
```

示例模型/风格仅说明结构，使用时必须由目标 App 校验实际目录，不能根据示例推断已安装。主 App 的 `mini_app_id` 为 null。数据中没有安装 ID、实例 ID、端口、DOM 选择器、机器路径或挂载凭据；同一份数据可在不同端/实例解读，接收端必须重新授权和验证。

单份合同/数据最多 16 KiB、嵌套最多 16 层；禁止 NaN、保留原型键和 schema 外部引用。合同使用闭合 JSON Schema，所有导出字段均须明确标注 `x-app-state: portable`，并作为完整快照的必填字段；未知字段、缺字段和无效类型拒绝，不默默丢弃或填默认值。嵌套对象也必须闭合。

安全来自字段白名单与 owner 验证，不靠扫描敏感词。不得把密码、凭据、用户正文、素材引用、审批、任务或安装路径标为可移植。SDK 在发送值前检查字段集合，防止误把完整草稿发给保存 API；后端再次校验后才持久化。

## 可信注册与版本

`apps/app_state.py` 提供 `StateContract` 与 `AppStateService`，不包含具体 App 标识。`apps/state_setup.py` 是可信组合入口；参考 owner 位于 `studio/app_state.py`。不同/任意 App 标识采用同一合同，不能从用户数据指定 Python 模块、校验器或迁移函数。

合同包含 App/Mini-App 稳定 ID、版本、名称、字段 schema、支持的客户端及排除字段。注册后深拷贝 schema；重复注册同一目标拒绝。描述返回合同摘要 hash，恢复准备与确认复核同一摘要。

未知版本默认拒绝。需要迁移时，owner 注册源版本到当前版本的纯数据迁移，并由调用者在 validate 请求显式选择 migrate。迁移只接收 values，返回内容仍经过当前完整 schema 校验；迁移不改变目标身份、不授予权限、不调用业务。SDK 不静默迁移或更换模型；消费者先获得明确迁移后的当前版本数据，再恢复。

当前只允许可信宿主代码注册。第三方 Package 的签名 manifest/Host SDK 声明和挂载绑定尚未开放，不能通过普通 HTTP 请求注册合同；这部分后续沿现有 Package 安装与宿主合同接入，不把本首版误写为所有已安装 Package 已支持。

## 后端 API 与隔离

平台路径前缀：`/v1/platform/app-state/instances/{instance}`。

| 操作 | 接口 | 语义 |
| --- | --- | --- |
| 合同读取 | GET `/contract?app_id=...&mini_app_id=...` | 当前可信合同；未接入明确返回 unsupported_target |
| 校验/显式迁移 | POST `/validate` | `{packet,migrate:false}`；只验证便携 schema，不表示模型/运行环境就绪 |
| 保存预设 | POST `/presets` | `{name,packet,request_id}`；同一请求幂等，冲突拒绝 |
| 查询预设 | GET `/presets?app_id=...&mini_app_id=...` | 当前 actor/installation 的同目标预设，最近 100 条 |
| 准备恢复 | POST `/applications` | `{packet,request_id,base_revision,contract_digest}`；prepared 不表示界面已变化 |
| UI 回执 | POST `/applications/{id}/complete` | `{packet,status:ui_applied|failed}`；校验原 actor/installation/实例、原数据指纹与合同 hash |

所有接口使用原 app.use 检查和 AppInstance ownership/access 守卫，目标 App 必须与实例真实定义一致。状态记录按 actor + installation 隔离。Mobile 还检查目标 App 的 Mobile enabled；仅六条明确路径通过原 owner Studio Gateway 暴露，未导出管理员 API 或任意代理。响应 no-store。

数据表 `portable_app_state_presets` 保存安全投影，`portable_app_state_applications` 保存请求/指纹/UI 回执。它们是预设与界面确认记录，不是第二套业务 Task 或状态时钟。`ui_applied` 仅说明宿主 UI 的回报，不证明任何业务执行或授予后续操作权。

Desktop/Mobile 连接同一 Local 时，命名预设按相同 actor/installation 可见；不同实例仍各自通过实例守卫。跨独立安装不自动同步；可移植格式不代表已有 Cloud 同步、独立云宿主或远程执行能力。

## 公共 SDK 与接入步骤

Desktop 基础模板和 Mobile App 基础模板提供 `window.AI2AppsAppState`；未注册的 App 不产生隐式状态。

1. owner 在可信后端注册 `StateContract`，明确字段及客户端支持。
2. 当前界面注册 `register({target,instanceId,capture,validate,apply,revision,dirty,setBusy,needsApply})`。
3. `capture` 只返回声明字段；`revision` 提供本地草稿/素材/执行状态戳，仅 hash 上传，不暴露其私有正文。
4. `validate` 必须在不修改界面的情况下检查完整设置，包括真实模型、风格、尺寸及当前操作是否允许恢复。未知项解释原因，不替换。
5. `apply` 必须由 owner 实现原子配置提交及失败回滚，不发业务请求、不自动提交；异步准备应在此前完成。`setBusy` 暂时阻止用户在提交临界区编辑。
6. 返回 binding 支持 `export()`、`save(name)`、`presets()`、`restore(packet,{requestId,confirmConflict})` 和 `dispose()`。`panel(binding)` 是可复用的命名预设界面。页面卸载时释放 binding。

不同设备使用相同语义字段，owner 可映射不同的选择器/控件；不得保存屏幕坐标或机器特有控件路径。Mini-App 与主 App 独立注册，父 App 合同不自动覆盖任意子组件。Package frame 不能借全局 SDK 绕过既有 sandbox/Bridge 或调用未导出的宿主接口。

## 恢复顺序与失败

整体验证合同/版本 → owner 无副作用预检 → 检查草稿 → 必要时由用户明确确认 → 再验本地 revision → 后端记录 prepared → 再验 revision → owner 原子恢复 → UI 回执。

脏编辑默认保留；只有确认界面上的“恢复这些设置”才继续，且确认期间发生新变化也必须重新操作。参考实现保留提示词与素材，只替换声明的设置。恢复提交临界区禁止生成和切换组件。

相同 request_id 不重复提交 UI；参数变化拒绝。当前界面已经是目标值时返回 unchanged。回执丢失时告知“设置已恢复但回执未确认”，不自动重试/回滚。请求有 15 秒等待上限；关闭页面、版本变化、目标不匹配和不可用配置均明确报错。未来主动推送到另一个窗口须建立独立的受控 mount 交接，不能用本 API 假装已改变另一窗口。

## 参考接入与验收

- Imagine Studio 主合同：左右栏折叠和左栏视图，不包含 Chat/会话状态。
- 五个图像 Mini-App 的共同设置合同：model_id、style_id、width、height、quality、format。当前端必须已打开指定 Mini-App。width/height 同为 null 表示模型支持的自动尺寸，不能只缺一个维度。模型、格式、质量、风格和画布由原 owner 目录/尺寸校验检查，不做模型替换。
- 恢复继续由 Imagine 原首选项/草稿机制保存，输出/素材/任务生命周期不变。SDK 回执是 UI 确认，不把草稿网络保存或生成宣称为已完成。
- App 顶部“状态预设”可保存和恢复当前目标；在上述五个图像 Mini-App 中管理当前组件设置，其它支持的内置页面管理布局。Package 页面不展示未经接入的预设入口。

测试覆盖任意 App 身份、严格 schema/版本、显式迁移、私有字段拒绝、owner/实例/Mobile disabled、幂等/回执篡改、编辑竞态、丢失回执不重放、桌面/手机界面确认、精确参数和素材保留。验证与加载记录如下。

## 后续推广

逐个 owner 接入其它 App/Mini-App，不默认序列化全部现有字段。新增 owner 使用同一 SDK/API 和自己的原业务校验；增加资源引用必须另行设计跨端资源解析和授权。B3 ASC-Bot 消费本合同，负责打开目标与交接，不把 App-State 变成任意脚本引擎。命名预设的批量管理、保留/分页、Package 声明和跨安装同步另行推进。


## B2 实施与加载记录（2026-11-05）

- 后端合同、任意 owner 身份、实例守卫、Mobile 精确路由及原 owner Studio 路由验证共 71 项通过；最后增加 no-store 和合同检查后，10 项 App-State 测试再次通过。
- SDK、原 Imagine 参数交接及 Mobile 导航相关 JavaScript 验证共 18 项通过。浏览器夹具在 1280×800 和 390×844 两个视口验证保存、取消冲突、精确恢复、素材保留及零生成调用，2 项通过。夹具不代表真实模型执行或真实手机设备验收。
- 原生 App-Dev 实际打开 Imagine 的“状态预设”面板，核对入口、名称输入与设置范围说明后关闭；没有在用户实例创建预设、生成图片或启动 Task。完整恢复由上述浏览器夹具覆盖，真实设备上的跨端恢复仍可继续人工验收。
- Mobile 静态资源增加三个精确许可条目，因此通过标准 `build-app-dev-environment.sh` 重建固定 App-Dev，原 App 已按标准流程归档；构建内置 release 校验及 `codesign --verify --deep --strict` 通过。最终 Python 变化通过 Helper 空闲检查后重启 Local，没有重启 Dev 或中断其它实例。
- App/Helper 元数据均指向当前 Git checkout，实例为 app-dev、Runtime 为 cloud；已检查 Local 实际 App-State API 导入路径、四份 served 资源逐字节匹配及嵌入 Mobile 静态资源。证据见 [source-verification.json](acceptance/app-state-b2-20261105/source-verification.json)。重建后原生窗口标题符合 `AI2Apps-App-Dev: App-Dev 127.0.0.1:<port>`。
- 本阶段没有修改 General Agent、AaAT 路由/声明、交互或结果策略，未重复完整 AaAT boundary gate；已运行本次合同和 owner 路由验证。没有 Cloud 代码或发布变更。

B2 公共基础与首批参考接入已完成。所有 App/Mini-App 的逐个接入、Package 声明接入、跨安装同步和 B3 ASC-Bot 消费仍是后续工作。


## Agent continuation 与 App-State 的统一（2026-11-05）

“在 App 内继续”采用同一个 App-State binding 的 `restore()`，不再在 `openParameterHandoff()` 中维护一套 model/size/quality/format/style 的直接赋值逻辑。五个内置图像 Mini-App 共用 owner 的 capture/validate/apply 和同一份尺寸/模型校验、版本守卫、并发检查、冲突确认、原子恢复及回滚。初始化先挂载 App-State，再接收/处理待交接意图，缺少 SDK 时明确失败，不回退到旧的字段赋值路径。

层次关系：

- App-State 负责配置合同及 UI 提交，供预设、continuation 和后续 ASC-Bot 共用。
- continuation 保留唯一的 Run/Interaction 归属、素材引用、提示词、任务绑定、取消/版本及真实结果回传协议。映射设置的适配器属于 App，不在 General Agent 添加业务规则。
- owner 在当前可信 handoff 的局部作用域内为同一个 apply 回调提供私人内容；只有原素材读取接口获取资源。App-State packet、预设和 UI 回执不保存提示词、素材引用或 Run/Interaction 授权。UI request_id 用原交互 ID 加本次明确操作的随机值区分重试，不代表授权。

同一 Mini-App 已打开时，不再重复选择并提前清空素材。目标草稿有编辑时，沿同一个冲突对话框明确说明：本次交接将替换设置、文字和素材，但不会执行；拒绝保持原草稿。目标不同则先由原 Mini-App 导航保存/加载各自草稿，再检查目标草稿。预设恢复依然只替换设置、保留正文和素材。

`needsApply()` 是 owner 提供的“本次有设置之外的受控内容需要提交”标志，用于防止相同设置导致新交接的提示词/素材被误跳过；它不绕过 schema、版本、授权、冲突确认或 revision 检查，不传到后端授予权限。普通预设不用此标志。每次用户明确重新发起交接创建新的 UI application 请求；不自动重放失败、取消或回执未知的操作。原交互 ID 对已导入草稿继续去重，重新打开保留用户修改。

私人内容导入与配置提交处于同一 owner 临界区：暂缓草稿自动保存，保留原字段与素材引用，读取失败恢复原内容，成功后才释放旧预览并保存新草稿。App-State `ui_applied` 只确认 UI 恢复；只有原 continuation `link/complete` 对真实生成任务和产物校验后，Agent 才能恢复为 `executed_in_app`，不会再次生成或计费。

验证与最终加载记录见 [整合验收记录](acceptance/app-state-continuation-20261105/acceptance.md)；本段取代 B2 初版中 continuation 尚未整合的状态说明。


## 情报中心、Todo、Gallery、知识库接入（2026-11-05）

四个 App 继续使用同一个 `AppStateService`、API、SDK `register/restore/panel` 和预设存储，不增加第二个恢复器。声明分别由 `intelligence/app_state.py`、`todo/app_state.py`、`gallery/app_state.py`、`knowledge/app_state.py` 所有；组合入口只负责可信注册。

| App | 首批便携字段 | 明确不包含 |
| --- | --- | --- |
| 情报中心 | channel_id、tab、article_filter、article_type | 栏目/文章选中项、搜索词、频道/源配置、正文、对话、采集和导出任务 |
| Todo | directory_id | 聚合目录、任务选中项、搜索/高级筛选、列宽、任务内容、执行器、权限和计划；导出前须打开普通目录 |
| Gallery | collection_id、kind、view（grid/list） | 搜索词、选中素材、素材内容、剪贴板、导入/移动/排序操作 |
| 知识库 | bucket_id、kind、view（ask/library） | 搜索词、输入正文、问答会话、askBucketIds、模型、知识条目、语义索引配置 |

这些 ID 是导航定位符，不是素材、凭据或执行授权。它们只在接收 Local 仍有相应可访问对象时有意义。owner 在恢复前和实际提交前通过原有只读 API 核对目录/频道/集合/知识分类，禁止按名字猜测或回退到第一个对象。新建或删除对象后会重新读取目录，避免使用过期页面列表。跨独立安装没有 ID 映射或自动同步；目标缺失明确失败。

情报中心、Gallery 和知识库的完整 App 页面沿用各自 Desktop/Mobile 共享界面；浏览器侧栏 Mini-Entry、素材 picker/preview 不注册完整 App 合同。Todo 的桌面与独立手机列表界面注册同一个 directory_id 合同；手机详情 frame 不重复注册。各端独有设置不静默翻译成其它功能。没有 App 实例的独立页面不显示一个无法使用的预设按钮。

入口统一为顶部“状态预设”。恢复只读取目标数据并更新视图，不创建/启动 Task、不导入/移动素材、不采集频道、不发问、不配置索引，也不安装模型。Gallery 搜索词及知识库输入草稿保留，且不写入预设。知识库有活动搜索时先要求处理搜索，避免恢复触发隐式语义检索；有编辑器/操作运行时先完成或保存。Todo 不自动放弃未保存任务编辑；情报中心不跨频道搬运未发送的对话或活动 handoff。

恢复中的内容读取失败由原 owner 向共享 SDK 传播，保持原视图或回滚；不把错误 toast 当作 UI 恢复成功。后台列表加载在 owner 提交临界区暂停，避免覆盖同一次配置提交。浏览器往返缓存保留的页面不主动销毁仍有效的 binding。

Mobile Gateway 的 App-State 请求按 URL 中真实 AppInstance 的归属解析目标 App，并检查该 App 的 Mobile enabled；不再要求额外启用某个 Studio。六条原有精确路径及 app.use/actor/installation/instance 守卫保持，未新增管理员代理或写入业务 API。

验证：84 项后端合同/owner/Mobile 路由检查、28 项相关 JavaScript 检查、10 项 Desktop/Mobile 尺寸浏览器夹具，以及原情报中心 Mobile 分页导航用例通过。原分页夹具补齐导出模块已存在的只读 `/exports` 初始读取，保持精确请求清单及禁止自动模型操作的断言，未改导出业务逻辑。App-Dev 四个原生入口和面板已逐个打开并关闭；没有保存用户测试预设或执行真实任务。详情见 [接入验收记录](acceptance/app-state-core-apps-20261105/acceptance.md)。

## B3 ASC-Bot 消费者（2026-11-05）

状态预设面板增加「创建快捷 Bot」。ASC 消费器保存同一 export packet，经可信宿主打开实际目标实例，再调用同一 owner binding.restore；Agent continuation 与 ASC 不各自维护参数赋值逻辑。SDK binding 可提供 activate 和 configureDependencies，注册完成发出 ai2apps:app-state-registered 供等待中的消费者继续。依赖安装只通过 owner 既有 ACPF，安装后显式重试并重新验证原配置，不自动提交。详见 [ASC-Bot B3](asc-bot-b3-v1.md)。
