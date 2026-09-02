# AI2Apps Site Agent P2/P3 实现与验收

状态：MVP 已实现  
日期：2026-08-29

后续 P4.0 Discovery 与版本治理实现见
`docs/ai2apps-site-agent-p4-0-discovery-package-governance.md`。

## 1. 统一阶段口径

- P2：Site Agent Package、Discovery、安装时本地编译、升级/回滚与标准发布输出。
- P3：健康监测、失败分类、漂移熔断、模型辅助修复、增量状态、后台调度、Knowledge 写入和跨 App 依赖。

早期自适应架构文档曾将 Discovery 标为 P1、Drift 标为 P2；该编号只表示底层研究顺序。本实现以
产品阶段口径为准。

## 2. P2 已实现

### 2.1 Package 契约

Site Agent 继续使用 Contract v1 `.ai2agent`，不创建第二种包格式。签名 Agent entrypoint 中增加：

```yaml
web_agent:
  schema: ai2apps.web-agent-package/v1
  site_key: example.com
  source: {}
  permissions: [browser.read]
  tests: []
  publisher_hint: {}
```

- `source` 是发布、审计和本地编译的权威数据；
- `publisher_hint` 永远是不可信输入，不会直接执行；
- Registry 外层权限必须覆盖内层 Site Agent 权限；
- 安装器拒绝 Cookie/Storage、任意网络、动态代码和密码/OTP 读取模式；
- 本地编译、Fixture 和 Validator 通过后才生成 generation。

### 2.2 安装与版本

- 已安装 Agent Package 可按规范化 hostname 和 capability 确定性匹配；
- 用户必须明确授予 Package 声明的权限；
- 首次安装建立 actor-scoped Package binding 和本地 generation；
- 升级产生候选 generation，不静默替换已有稳定 generation；
- 旧 generation、Package digest、Publisher 和授权记录完整保留，可回滚；
- 一个网站仍只对应一个 Site Agent，Package 内操作映射为 Capabilities。

### 2.3 Discovery 与发布

- Agent App 新增 Discovery 页面，同时显示已安装候选和 Cloud Registry 结果；
- 查询不调用模型；本地使用 site/capability 精确过滤；
- Agent Studio 可导出标准 Contract v1 source directory 和未签名 `.ai2agent` 候选；
- 正式签名、提交、审核、发布继续使用
  `scripts/build_signed_registry_release.py` 和
  `scripts/publish_signed_registry_artifact.py`。

## 3. P3 已实现

### 3.1 健康与漂移

每个 `actor + draft + capability` 保存：成功/失败计数、连续失败、最近错误类别、结构指纹、
健康评分、最近成功时间和 Circuit 状态。失败分类顺序覆盖用户接管、网络/渲染、策略拒绝、
结构/Selector/Schema 漂移和普通执行失败。

一次结构失败进入 `suspect`；三次连续结构失败进入 `drifted` 并打开一小时 Circuit，阻止后台
任务持续浪费页面、模型和 Token。登录、条款、CAPTCHA、付费墙进入 `needs_user`，不作为漂移
自动修复。

### 3.2 增量 Site State

- URL 或站点 ID 是 Item 主键；标题、发布时间、摘要和正文生成 fingerprint；
- 成功且通过输出 Schema 的 Run 才原子更新 checkpoint；
- 记录 new、updated、missing 和 item_count；
- 首次运行以及 generation 变化进入 calibration，并抑制批量“新增”；
- 新旧主键覆盖不足时 calibration 失败，不覆盖上次健康 State。

### 3.3 修复

- 手工、轻量模型和高级模型修复都生成不可变候选 generation；
- 模型只接收白名单结构证据，不接收页面正文、截图、URL query、Cookie 或凭据；
- Repair 不得改变 site scope、增删 Capability 或提高效果等级；
- Candidate 必须再次通过编译、Fixture、Schema 和 Validator；
- 激活 Repair 后状态为 `local_patched`，Site State 进入 calibration；
- 原 generation 保留，可用既有 generation API 立即回滚。

### 3.4 调度、Knowledge 与 App

- Schedule 仍只创建普通 AgentRun；
- 每个 Schedule 支持 1–16 并发上限和失败预算，超过预算自动暂停；
- 成功的定时结果可幂等写入指定 Knowledge Bucket；
- App 可以声明 capability/site/provider dependency；
- Capability Resolver 在调用时应用显式 Provider pin；
- News、Chat、Knowledge、Workflow 使用同一个 capability invoke API。

## 4. 新增 API

```text
GET  /v1/platform/site-agent-packages
GET  /v1/platform/site-agent-discovery
POST /v1/platform/site-agent-packages/{package_key}/provision
POST /v1/platform/agent-drafts/{draft_id}/package-source

GET  /v1/platform/agent-health
GET  /v1/platform/agent-drafts/{draft_id}/site-state
POST /v1/platform/agent-drafts/{draft_id}/repairs
POST /v1/platform/agent-drafts/{draft_id}/repairs/model
POST /v1/platform/agent-repairs/{repair_id}/activate

GET  /v1/platform/agent-app-dependencies
POST /v1/platform/agent-app-dependencies
```

## 5. 数据迁移

Platform schema v62 新增 Package binding、Capability health、Site State、Repair candidate、App
dependency 和 Run→Knowledge 幂等写入记录；Schedule 增加 Installation、并发和失败预算字段。

## 6. 安全不变量

- Browser 操作仍只通过受保护的透明 WebDriver BiDi Gateway；
- Package/模型/页面都不能获得原始 BiDi endpoint 或 credential；
- Publisher Hint 不执行；
- 付费墙、CAPTCHA、法律条款不会被自动绕过或接受；
- Repair 不原地修改签名 Package；
- 正式发布不通过浏览器自动化、临时 curl 或 Cloud 数据库写入。
