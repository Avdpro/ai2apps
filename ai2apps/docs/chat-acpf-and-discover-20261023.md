# Chat 中的 ACPF 与 Discover 能力发现（2026-10-23）

## 本轮实现

参数表单的 owner `install` 声明现在可在 Desktop Chat 内启动现有 ACPF。
卡片复用 capability_provisioning 的步骤、许可挑战、进度、重启及失败重试组件，
不创建第二套安装任务。配置档位通过原 ACPF select_profile 校验；许可仍需显式确认。

`parameters/setup/session` 的 GET 从 provisioning_sessions 恢复当前配置，POST 在
用户点击配置后创建；`/{action}` 仅允许 confirm/retry/select-profile/cancel/acknowledge-return。
所有操作先校验 Run、actor、Installation、待处理表单、选定 Provider/version 和 owner install。
服务器派生 actionId；不接受客户端指定 ACPF session、App ID、计划或执行回调。
会话绑定不依赖 localStorage。关闭视图只停止观察，不取消已确认安装；Local 启动恢复
继续使用原 ACPF.startup/resume_if_possible。只有 ready 可以确认返回，重新读取表单后
仍须正常提交业务参数，配置卡片不能替代业务确认。

Mobile 的受保护控制网关仅新增 GET setup/session。Mobile 可以观察现有配置进度，
发起配置、许可确认、安装、重启与重试仍需 Desktop。本轮未扩展手机安装权限。

Discover owner 导出一个 `discover.packages` AaAT，复用现有 Registry content_catalog
按用户目标搜索 App/Mini-App。固定最多 10 项；返回有界元数据和明确的 unverified
Agent 支持状态。目录文本是不可信证据；requirements.capabilities 不是能力导出。
共享 General Agent 没有新增 App、Tool 名称或数字人业务分支。

## 尚未完成的发现安装闭环

当前 Discover AaAT 只读推荐，实际安装继续使用 Discover 原有签名 Package 安装界面。
没有实现从推荐卡片直接安装任意 App/Mini-App，也没有宣称安装后即可 AaAT 调用。
现有目录尚不能完整提供可信的 App/Mini-App AaAT exports 与任务匹配契约；PackageRuntimeBinder
也不会仅凭目录 JSON 注册任意 App AaAT。Cloud 所需变更见 cloud-discover-capabilities-requirements-20261023.md。
在该契约和本地隔离生命周期适配补齐前，不自动执行新装 Package 的业务。

## 验证记录

- tests/test_chat_provisioning.py：任意两个 owner 的持久绑定、重复创建、恢复、版本守卫、保留草稿与业务未提交。
- tests/test_discover_aaat.py：只读推荐、裁剪、空结果/不可用、不将依赖推断为导出。
- tests/chat_provisioning_browser.test.cjs：真实浏览器中的内嵌卡片、显式确认、视图解绑、已完成会话恢复；安装引擎为 fixture。
- 原参数配置、前端表单及 AaAT 边界回归。App-Dev 已在固定实例真实执行 discover.packages（数字人关键词），返回 not_found 且未启动安装；英文 avatar 查询返回 3 项（avatar-studio-suite、model-echomimic-v3-mlx、model-flashhead-mlx），均明确 unverified。Quick Read 真实配置卡片在原 Chat 内显示，刷新恢复原参数，切换到 Qwen3 TTS 0.6B 方案后仍等待确认；两次方案会话均已取消，没有下载 Checkpoint、接受许可或提交朗读。

## 恢复边界

ACPF 的安装恢复不等于业务模型推理恢复。等待表单仍受原 Run deadline、取消和版本约束；
若等待已过期，不绕过守卫恢复业务调用。卡片目前属于待处理交互，终态历史不新增安装操作入口。

最终验证：后端 17 项、前端单元 22 项、浏览器 3 项通过；AaAT 边界门禁 255 项通过。App-Dev Run run_1d3ddfe892514180aee1308582991dee，配置 prv_19c83b695c544ca78b53a625973192e6（已取消）。许可交互和安装进行态/完成态恢复使用浏览器 fixture；未在真实 App-Dev 下载新模型或执行服务重启安装。

激活核验：固定 app-dev 使用当前 checkout，App 与 Helper 的 DevelopmentSourceRoot 均为
/Users/avdpropang/sdk/omlx-moe-cache；Local 日志记录 services/builtin_apps.py 和 api/chat.py
从该 checkout 导入，最终端口 53912 的 agent_parameter_forms.js、capability_provisioning.js
及 capability_provisioning.css 与源码逐字节相同。Python 修改经标准 Helper 重启激活。
