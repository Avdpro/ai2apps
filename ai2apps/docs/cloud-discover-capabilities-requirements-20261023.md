# Cloud 交接需求：按目标发现可安装的 App/Mini-App 能力

状态：待 Cloud 项目评审实现。本仓库不修改或部署 Cloud 代码。

## 目标

Desktop 已有 Discover 目录查询；新增 discover.packages AaAT 可以只读按词搜索。
下一阶段需要根据用户目标准确推荐可安装能力，用户选择后使用现有签名安装流程，
安装完成重新发现真实注册的 AaAT。目录推荐本身不授予安装或调用权限。

## 目录契约

在已发布、签名绑定的 Package release 元数据中提供可验证的能力导出摘要：
- Package ID、精确版本、Publisher、manifest digest、发布/撤回状态。
- App/Mini-App 的真实身份、宿主/placement、提供能力、范围、输入/输出素材类型。
- AaAT 声明版本、导出接口版本、是否支持 Agent 调用；UI-only 必须明确。
- 独立列出 requirements，不从依赖推断提供能力，不依据名字猜测。
- 平台/架构、Runtime 版本、内存/存储与下载大小、许可/收费、数据处理位置及权限摘要。
- zh/en 展示文案和原始 Package 详情入口；未知字段用 unknown，不能默认为支持。

目录索引必须来自已验证的发布 artifact，并绑定 release/digest，不能允许发布者通过
可变描述文本伪造可执行导出。执行权仍由本地安装器校验 artifact 与实际运行隔离协议。

## 查询

扩展现有 Registry discoveryCapabilities 宣告支持的查询特性；客户端按特性协商，
旧服务器继续按关键词搜索并返回 agent_support=unverified，不静默假装语义匹配。
在现有 content catalog 中支持任务/能力、输入输出类型、设备兼容性等筛选或排名；
返回多个候选及机器可读匹配理由、排除理由、稳定分页和精确 release 信息。
对撤回、无兼容 release、过时索引、权限不足明确报错；不要把它们解释为零候选。

## 安全与安装

搜索只读；不因查询自动安装、批准权限、接受许可或发起业务。继续使用原 signed Registry
下载与校验、审计、权限 review、依赖安装及 restart 流程，不新增任意 URL/脚本执行接口。
用户选择必须绑定版本/digest；安装时若版本发生变化须重新审核。目录变化不自动执行新业务。

## Cloud 验收

不同 Publisher/Package、App 与 Mini-App、UI-only 与 AaAT exports、多个候选、中文与英文、
设备不兼容、旧服务兼容、撤回/过期 release、缺失字段、分页与恶意描述均有覆盖。
requirements.capabilities 不能被当成 provides。安装前后版本和 digest 必须一致。

## 本地后续工作

Cloud 完成后，本地再消费该契约，补齐 Package 隔离运行时的声明验证和 Provider 生命周期映射，
以及推荐选择→安装 review→ACPF/重启→重新发现→恢复原草稿的持久交接。
这不是仅增加一个 Cloud 字段便完成的功能；不能在 General Agent 写业务特判弥补缺口。

## 2026-10-23 状态更新

Cloud 需求已实现并部署，OpenAPI 1.77.0。以 Cloud 项目的
`docs/discover-capabilities-client-handoff-2026-10-23.md` 为最终接口合同。
Desktop 接入进展与仍缺的执行适配器见 [客户端接入记录](discover-capability-client-integration-20261023.md)。
