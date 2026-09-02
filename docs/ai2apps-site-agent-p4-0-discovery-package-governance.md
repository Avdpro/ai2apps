# AI2Apps Site Agent P4.0：Discovery 与 Package 生命周期治理

状态：客户端 MVP 已实现  
日期：2026-08-29

## 1. 范围

P4.0 把 P2 的“可以发现和安装”补成一个可运营的客户端闭环：

1. 以 `origin + path + capability + output schema` 精确查询 Cloud Registry；
2. 在 Agent App 内完成下载、Repository/Publisher 验签、审核确认、权限确认和本地编译；
3. 首次安装可直接激活，升级只产生候选 generation，不静默替换稳定版本；
4. 用户可以显式激活、固定版本、解除固定和回滚；
5. 每次安装、候选、激活、回滚和策略变化都写入本地审计记录。

P4.1 的匿名健康聚合、云端兼容性测试与修复回传，以及 P4.2 的团队共享和多 Agent
Workflow 不属于本阶段。

## 2. Discovery

客户端调用现有 Registry 搜索端点，并同时发送：

```text
type=agent
agent_kind=site-agent
origin=https://example.com
path=/news
capability=web.article_feed
output_schema=ArticleList/v1
```

同时保留 `q=site capability schema` 兼容字段，旧 Cloud 可以继续返回全文搜索结果。搜索过程
不调用模型。Agent App 展示签名 Publisher、版本、权限和兼容元数据，并提供
`Review & install` 操作。

## 3. 安装事务

Registry 安装接口执行以下顺序：

1. 读取可信 Repository metadata；
2. 下载并验证 Artifact digest、Repository 签名和 Publisher 签名；
3. 执行既有 Package audit/compatibility/dependency 检查；
4. 校验 `ai2apps.web-agent-package/v1`；
5. 显式检查用户授予的权限；
6. 忽略 Publisher Hint，在本机从 Source 重新编译并运行 Fixture/Validator；
7. 建立 actor-scoped binding 和不可变 generation。

首次安装没有旧 binding 时激活；已存在稳定版本时，新版本保持 `installed` 候选状态。如果权限
确认、本地验证或编译失败，客户端恢复先前的 Package 激活状态。

## 4. 版本治理

- `manual`：默认策略。下载和编译升级候选，但必须由用户显式激活。
- `pinned`：固定到当前已安装版本；其他版本可以下载审查，但不能激活。
- `activate`：同时激活签名 Package 和其对应的本地 generation，保留旧版本。
- `rollback`：选择 retained digest 显式恢复；若原策略为 pinned，固定版本随回滚目标移动。

Binding 保存 Package digest、Source snapshot、权限、编译 digest、Publisher、策略、固定版本和
激活时间。生命周期审计不保存浏览页面、Cookie、凭据或模型 Prompt。

## 5. API

```text
GET  /v1/platform/site-agent-discovery
POST /v1/platform/site-agent-registry/{namespace}/{name}/install

GET  /v1/platform/site-agent-packages/{package_key}/lifecycle
POST /v1/platform/site-agent-packages/{package_key}/policy
POST /v1/platform/site-agent-packages/{package_key}/activate
POST /v1/platform/site-agent-packages/{package_key}/rollback
```

P2 的本地 Package provision 和导出 API 保持兼容。

## 6. 数据迁移

Platform schema v63 为 Site Agent binding 增加 Source snapshot、更新策略、固定版本和激活时间，
并新增 `agent_site_package_events` 审计表。

## 7. 安全不变量

- 不执行 Publisher Hint；
- 不绕过 Contract v1 验签和 Package audit；
- 不因下载新版而切换当前稳定 generation；
- 不允许固定到未安装版本；
- 激活与回滚必须同时校验 actor、Package key、digest 和 generation；
- Cloud 只索引签名 Artifact 内的不可执行 metadata。

