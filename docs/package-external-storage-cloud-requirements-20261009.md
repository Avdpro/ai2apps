# 大型 Package 外部存储：Cloud 变更需求

> 2026-10-09 更新：Linux Runtime 主路线调整为小型签名安装描述与客户端受管共享环境，见 `spark-runtime-install-descriptor-cloud-requirements-20261009.md`。本大包外部存储需求继续保留，但不再是 Linux Runtime 发布的唯一方案。

状态：2026-10-09 用户提出的新方向，待 Cloud 工程实现部署；当前生产合同未改变。本工程不修改 Cloud 代码。

## 生产合同复核

- 2026-10-09再次匿名实时复核，仍为v1/4,294,967,296字节/multipart，未公布external-only能力；回执 `spark/artifacts/runtime-public-upload-capabilities-20261009-r3.json`。客户端未猜测或绕过尚未交付的Cloud合同。

- 2026-10-09：匿名实时读取生产 /v1/registry/runtime-upload-capabilities，仍返回schema v1、artifact/file/expandedZip均4,294,967,296字节、multipart /v1/platform-runtime-submissions；未公布external-only提交能力。回执 spark/artifacts/runtime-public-upload-capabilities-20261009-r2.json。此公开合同不能支持用户新提出的>4GiB HF/MS-only发布，等待Cloud工程交付新schema及验收回执；不能仅放宽客户端或向旧路由上传。

## 产品规则

- 允许 Package 超过现有 4 GiB 限制。容量与官方 Runtime / 原生代码权限分别校验，保留 Publisher 签名及安装审计。
- 最终签名制品超过 1 GB 必须同时存放于 Hugging Face（HF）和 ModelScope（MS）；Cloud 只保存目录、签名、校验清单与审计记录，不保留二进制对象、不代理用户下载。
- 本需求将 1 GB 定义为十进制 **1,000,000,000 字节**，按最终分发制品压缩大小判定；等于阈值不强制外部托管。此值不同于旧合同 1 GiB，接口必须明确整数 bytes。
- 小包保留现有 Cloud 路径，也可选择外部存储。不自动提高普通上传的 25 MiB 上限。
- 外部存储降低 Cloud 成本，不降低用户下载量。依赖版本统一、Torch/CUDA 栈合并与按需层继续推进。

## 已核实的合同差异

发布手册第 6.4 节及客户端 `ai2apps/packages/contract_v1.py` 当前限制官方 Runtime 4 GiB、普通包 1 GiB；第 9 节要求 Cloud 永久源及 MS / GitHub 镜像。新策略需允许大包没有 Cloud 源，并以 HF + MS 替代三源要求。部署前不将旧手册改写为已支持。

## Cloud 实施要求

1. 既有发布流程增加外部制品提交模式：提交 Publisher 签名 envelope、精确大小/SHA-256、两个固定 revision 来源，无需先上传大文件至 Cloud。复用现有 Publisher/key、Package ID/version、管理员验证、审核及 submission 查询/恢复；不能建立旁路发布器。
2. 能力发现返回合同版本、外部托管阈值、来源类型、最低客户端协议，以及制品、单文件、解包总量各自的有界上限。建议首期外部制品至少支持 32 GiB，最终值由 Cloud 和客户端共同确定；不采用无限上限。嵌套 Runtime 解包、文件数、路径与磁盘占用也需独立校验。
3. Registry 支持无 Cloud fallback 的 external-only 制品。Cloud 仍发布可信元数据 snapshot；同版本制品字节不可变，来源变更不改变摘要。不能把 checkpoint distribution 冒充可执行 Runtime Package。
4. 发布前双源各自通过固定 revision、完整 size/SHA-256、分块摘要及首/中/尾/单字节 Range 校验。Cloud 可有界流式读取、在隔离临时盘扫描，但不能保留长期对象、备份或缓存；临时文件必须有容量预算、到期及故障清理。“不占云空间”指无持久制品副本，审核仍有流量和临时资源成本。
5. 两源必须提供同一最终制品。公开清单不得包含凭据或临时签名 URL；验证 HTTPS、重定向及目标地址，拒绝内网目标。保留现有 MS 严格 `200 + Content-Range` 兼容模式；HF 实际 Range / 重定向行为以验收为准。
6. 标准发布脚本支持外部提交、查询和失败恢复。对超过阈值的 Cloud 二进制上传，在接收主体前拒绝并返回结构化错误和阈值；不能先存进去再提醒。小包仍遵守现有权限/上传限额。
7. 新合同通过客户端能力或最低版本控制推荐和安装。客户端直接从 HF / MS 下载，断点续传、逐块验哈希、完整验签并可切源。双源均故障时可重试失败，不偷偷回源 Cloud。

## 存量、许可证与回滚

- 新发布先实施；存量包逐个补齐并验证双源，再发布来源 snapshot。旧客户端兼容、回滚及存量迁移验收完成前，不删除现有 Cloud 原件。
- 存量对象、历史版本、缓存和备份清理需独立执行并核实，不能仅修改来源就宣称已释放存储。
- 回滚暂停新合同发布/推荐，保留不可变外部对象和元数据；不自动把大包重新上传 Cloud。旧合同包继续原路由。
- 分发须符合制品许可证；安装用户的许可声明仍由各安装者作出，开发者同意不转授其他用户。

## 验收和交付

- 阈值 -1 / 等于 / +1 字节；超过 4 GiB 真制品提交、审核、发布、下载、安装；大整数、断点续传、源切换和磁盘不足均覆盖。
- 错摘要、单源、可变 revision、损坏尾段、Range 被忽略、异常重定向必须失败；权限、安装审计、安全解包及失败清理保持通过。
- 证明没有持久 Cloud 二进制对象、用户下载不经 Cloud 代理；报告审核流量和临时盘峰值。
- 交付 OpenAPI 版本、精确 schema、能力发现样例、标准发布脚本对接说明、兼容和回滚回执。客户端再升级容量/下载/安装合同，完成 Spark 真 Runtime 验收。

按需层另见 `spark-runtime-optional-layers-cloud-requirements-20261009.md`。本需求可独立上线；按需层用于降低用户实际下载量。
