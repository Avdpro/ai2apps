# Bot 的 App/Mini-App 单开关授权

2026-11-04。Bot 的 App 访问权限由 Read/Write 两级简化为 `enabled`，每个授权目标只有允许访问/不能访问。此变更仅属于 Messager owner，不改变 General/Chat 的授权，也不删除 Tool 自身的读写副作用声明。

## 界面与接口

- Access 中 App、Mini-App 分组不变；每项一个“允许访问”开关。关闭保留条目，删除通过现有确认框移除，添加默认启用。
- 申请卡显示真实 App/Mini-App 图标、名称与任务上下文，不展示读写选项。点击“允许此 Bot 访问”持久授权目标并继续原普通调用；拒绝仍回接原交互。
- 设置 `PUT /messager/bots/{bot_id}/app-access` 的 apps 项为 `{app_id, enabled}`。申请 `POST /app-access/requests/{run_id}/{interaction_id}` 只接受 request_hash，目标由宿主解析，不由客户端指定。
- App 与 Mini-App 独立，父 App 不隐式授权 Mini-App，Mini-App 不授权兄弟。移除组件保留可识别的禁用/移除入口，不再获得执行权。新 Bot 沿用 Gallery、Messager、Todo、AI Browser 四个默认 App，统一为访问开启。
- 按用户的开发阶段要求，不增加旧 Read/Write 升级、迁移、兼容字段或首次升级确认流程；旧字段不是新授权输入。

## 执行边界

访问开启允许该目标全部普通 AaAT，包括读取、普通写入和配置内 AI/API 使用。特殊确认独立：付款/购买、破坏性、敏感及未知副作用、含义不明确的 billing、owner 显式 confirm 仍需单独批准。ai.usage 继续遵循既有账户、模型配置和预算，不等于购买或充值。Owner 参数确认与资源归属检查不变。

授权绑定 actor+Bot、目标身份与当前声明审阅哈希。旧后台/排队任务不因新增访问而扩展冻结的 Provider/version；撤权使旧 epoch 失效并停止相关执行，重新开启不自动恢复原任务。系统/Hook 的有限接口权限独立存在，关闭目标时一并撤销该目标已有接口授权，不能绕过关闭状态。Bot 间使用和协作许可独立。

## 实现与验证

实现集中在 messager/app_access.py、Messager API、Access 设置模板与信息流交互卡；共享 Agentic 未增加业务分支。验证区分真实 SQLite/Run/Interaction/权限服务与确定性模型/业务输出夹具，浏览器夹具覆盖单开关保存、关闭保留、独立 Mini-App 和精确原请求回接。开发实例使用标准 Helper 空闲重载，不重建 App，不改图片消息组件。
