# Package Event Hook 用户授权：实现与验收

2026-11-02。协议与使用方式见 [用户授权 v1](package-event-hooks-user-consent-v1.md)。

已实现签名声明校验、宿主申请/审阅/原子授权、App 与 Mini-App 身份隔离、前台 SDK/端口投递、固定宿主后台处理、AaAT 详情、暂停/恢复/撤销、兼容升级及重新授权，以及 System Control 与 Messager 管理界面。Schema 105。安装、声明或 Package 返回值都不能代替用户决定。

## 验证

- 最终 Package 专项 22 项通过（16.70 秒）：真实临时签名归档经正式安装器安装；验证安装不授权、通用保存接口不能绕过同意、前台元数据与详情分离、缓存重新授权、后台固定处理器/站内通知、App/Mini-App 隔离、真实 Studio mount HTTP、SDK 签名资源内联、暂停恢复、撤销、到期、兼容升级、不兼容升级和回滚、拒绝幂等、签名声明拒绝及申请配额。
- 订阅/执行/动作相关回归 74 项通过（80.72 秒）；安装、现有 App/Mini-App AaAT 导出及详情 owner 回归 62 项通过（38.24 秒）。这些集合有重叠，不合计为独立用例数。
- 前端协议与消息端口 10 项通过：宿主显式点击、关闭保留待办、文本安全渲染、决定响应丢失的相同请求 ID 重试、App SDK 父窗口/mount 校验、全局管理的版本化暂停、实际 MessageChannel 消费成功后确认及失败重投。
- 额外检查五类畸形声明形状均返回验证错误；前端语法、Python 编译及本次文件差异空白检查通过。
- 完整回归曾出现 843 通过/1 失败：既有参数交接在读事务中先读后写，遇到 SQLite 快照升级冲突。三个写入入口改用已有写事务模式，版本/确认/取消保护不变；新增并发写入回归，与原交接/表单测试共 22 项通过（29.72 秒）。修复后的完整 AaAT 门禁 845 项全部通过（429.33 秒，退出码 0）。

## 固定开发实例

在各自活动任务为空后，经标准 Helper 独立重载 Local。未重建 App、未修改身份、未混用数据。最终核验：

| 实例 | Local PID | 端口 | Schema |
| --- | --- | --- | --- |
| Dev | 86132 | 55202 | 105 |
| App-Dev | 86147 | 55246 | 105 |

App 与 Helper 的源码根都为 `/Users/avdpropang/sdk/omlx-moe-cache`；运行导入的 Package/Hook/执行/Studio/Broker/API 模块路径均来自该 checkout。八份 JS/CSS 资源逐字节匹配当前源码，四项 AaAT 详情 Tool 已启用。匿名访问授权与 Hook 管理接口均为 401。

原生客户端分别使用确切 `com.ai2apps.desktop.dev.shell`、`com.ai2apps.desktop.appdev.shell` 验收。Dev 英文和 App-Dev 中文的 System Control → 事件订阅管理窗口正常；Dev Messager 自动化页显示 Package 申请/授权区、原有暂停规则及运行监控。最终 App-Dev 原生标题为 `AI2Apps-App-Dev: App-Dev 127.0.0.1:55246`。新审批弹窗的决定与重试由 DOM 夹具验证，没有在真实用户数据上自动批准申请。

两个开发实例的 Package requests/grants/audit/detail_reads 都是零条；没有给现有 Package 新增授权。原有验收规则维持暂停。

## 证据范围

签名和安装流程是真实代码，测试 Package 来自独立临时目录；事件和 AaAT 业务返回为明确夹具。没有第三方线上 Package 全流程、付费模型、好友回复或微信外发验收。没有修改 Cloud，也没有发布 Package 或 Desktop。测试进程可能输出既有无 Metal 设备退出警告，相关测试退出码为 0。

[完整收据](acceptance/package-event-hooks-20261102/receipt.json) 记录源码摘要、测试日志、激活与界面证据边界；[两实例校验](acceptance/package-event-hooks-20261102/live-instances.jsonl) 包含资源摘要。
