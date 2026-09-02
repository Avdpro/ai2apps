# AI2Apps Desktop 更新清单：Cloud 生产改造需求

状态：Ready for implementation v1.0  
日期：2026-09-02  
Cloud 域名：`https://coder.ai2apps.com`  
客户端协议：`apps/ai2apps-acefox/docs/update-distribution.md`

## 1. 目标与边界

Cloud 生产环境需要为 AI2Apps macOS App 提供公开、稳定、可灰度控制的更新清单：

```text
GET https://coder.ai2apps.com/updates/stable.json
```

Cloud 只托管不超过 1 MiB 的控制清单，不代理、不缓存回源 DMG，也不参与 App
安装。DMG 和配套 release record 分别发布到 ModelScope 与 GitHub Release；客户端
负责断点续传、镜像切换、SHA-256、Developer ID、notarization、版本门禁和安装回滚。

本需求不新增账户态接口，不上传设备标识、cohort ID 或更新结果。清单读取必须匿名，
不得依赖 AI2Apps 登录、Cookie、Device credential 或用户所在地上报。

## 2. P0：生产上线必需能力

### CLOUD-UPDATE-001：公开清单端点

必须实现：

```http
GET /updates/stable.json HTTP/1.1
Host: coder.ai2apps.com
Accept: application/json
```

成功响应要求：

```http
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Cache-Control: public, max-age=60, must-revalidate
ETag: "<content-digest-or-deployment-version>"
Content-Length: <1..1048576>
```

约束：

- 中国境内和境外网络均可匿名访问；
- 支持 `GET`，建议同时支持 `HEAD`；
- 不设置 Cookie，不返回 HTML，不跳转到登录页、ModelScope 或 GitHub；
- 正常路径只允许 `200`；没有有效清单时返回 `503`，不得用 `200` 返回空对象；
- body 必须是完整 UTF-8 JSON，压缩与否均不得改变实体语义；
- 不得对该路径套用账户级、设备级或低阈值单 IP API 限流；
- CDN/WAF 规则不得拦截 macOS `URLSession` 的默认 User-Agent；
- TLS 证书链和域名必须符合普通 macOS 系统信任，不使用私有 CA。

验收：在中国电信/联通/移动至少各一个网络及一个境外网络连续请求，均得到相同的
有效 schema；无 Cookie、无认证、无重定向，响应体不超过 1 MiB。

### CLOUD-UPDATE-002：清单 schema 与发布校验

Cloud 发布任务必须在替换生产对象前校验：

- `schema_version == 1`、`channel == "stable"`；
- `releases` 数量为 `0...32`；空数组表示当前不向任何客户端提供更新；
- `bundle_identifier == "com.ai2apps.desktop"`；
- `instance_id`、Runtime profile、架构、最低 macOS 版本和正整数 Build Number 合法；
- `rollout.percentage_basis_points` 位于 `0...10000`；
- DMG 和 metadata 均包含 `url`、`urls`、`filename`、`size`、`sha256`；
- `url` 必须等于 `urls[0]`，用于兼容已发布的单源客户端；
- `urls` 包含 1 至 4 个互不重复的 HTTPS URL；生产首版必须同时包含
  ModelScope revision URL 和 GitHub Release URL；
- URL 不含账号密码，文件名不含路径穿越，SHA-256 是 64 位小写十六进制；
- 同一 artifact 的所有镜像必须对应同一文件名、大小和 SHA-256；
- release record 必须标记 `notarization.status == "stapled"`，并与 DMG Build、
  Bundle ID、实例和摘要配对；
- 声明的 ModelScope revision/tag 与 GitHub Release tag 必须不可变，禁止使用
  `master`、`main`、`latest` 或可覆盖对象路径。

建议对 artifact 声明域名做显式 allowlist，首版只允许经确认的 ModelScope 仓库和
AI2Apps 官方 GitHub organization/repository，避免发布账号被利用后把客户端引向任意
下载域名。

验收：格式错误、单源遗漏、HTTP URL、重复 URL、非 stapled release record、摘要
不一致和可变 revision 的清单都无法进入生产。

### CLOUD-UPDATE-003：双源可用性预检

发布清单前，流水线必须对 ModelScope 和 GitHub 两套 artifact 执行：

1. 匿名访问稳定 URL并跟随 HTTPS 重定向；
2. 对 DMG 发送非零或小范围 `Range` 请求；
3. 要求返回 `206 Partial Content` 和准确 `Content-Range`；
4. 校验远端 `Content-Length`/完整文件大小；
5. 校验完整 SHA-256 与本地最终发行物一致；
6. 下载并校验 release record 的大小和 SHA-256；
7. 确认链接不依赖发布者 Token、Cookie 或短期写死的 `auth_key`。

ModelScope 清单内保存稳定的 `resolve/<immutable-revision>/...` URL。平台生成的临时
下载 URL 只能作为运行时重定向结果，不得写入 `stable.json`。GitHub 使用固定
Release tag 的 `/releases/download/<tag>/...` URL。

任一主镜像预检失败时默认禁止扩大灰度。是否允许在已有版本的应急场景下以单镜像
继续服务，必须由发布负责人显式审批并留下审计记录。

### CLOUD-UPDATE-004：原子发布与可恢复性

生产发布顺序必须是：

```text
签名/公证 App
  -> 上传并校验 ModelScope
  -> 上传并校验 GitHub Release
  -> 生成 stable.json
  -> schema/双源预检
  -> 原子替换 Cloud 对象
  -> CDN purge/revalidate
  -> 多地域验收
```

要求：

- 客户端只能看到旧清单或新清单，不能看到写到一半的文件；
- 保留至少最近 20 次生产清单、操作者、发布时间和内容 SHA-256；
- 回退操作是重新发布一个已审计清单，而不是在原文件上进行非原子编辑；
- 发布后主动清理该 URL 的 CDN 缓存，目标两分钟内全球收敛；
- manifest 发布失败不能删除或覆盖上一份有效清单；
- Cloud 数据库不是必需组件，优先使用带对象版本或原子 rename/replace 的静态存储。

验收：并发持续读取期间发布新清单，所有响应都能完整解析且只出现旧、新两种内容
摘要；模拟发布中断后旧清单仍可用。

### CLOUD-UPDATE-005：灰度操作与紧急暂停

Cloud/Release 运维需要支持以下动作：

- 首次发布 Build 时以 `percentage_basis_points = 0` 上线；
- 按 `100 -> 500 -> 2000 -> 5000 -> 10000` 等审批节奏扩大灰度；
- 扩大同一批 cohort 时保持 `rollout.id` 不变；
- 更换 Build 或明确重新抽样时才改变 `rollout.id`；
- 紧急暂停时把比例改为 `0`，或从 `releases` 中移除候选 Build；
- 不通过清单发布更低 Build，不执行远程自动降级；修复必须发布更高 Build。

必须提供一个不依赖重新部署 Cloud 应用代码的发布入口。推荐使用受保护的 CI/CD
workflow 或内部 Release 工具；不要求增加公网写 API。生产写权限需最小化，至少保留
操作者、审批者、前后内容摘要和变更原因。

紧急暂停验收目标：从批准操作到境内外 `stable.json` 都返回暂停后的清单不超过
两分钟。

## 3. P1：生产可靠性与区域优化

### CLOUD-UPDATE-006：监控与告警

至少监控：

- `/updates/stable.json` 境内、境外探测成功率和延迟；
- 非 `200`、JSON 解析失败、body 超限和证书错误；
- 当前清单 Build、rollout ID、比例、内容 SHA-256 和发布时间；
- ModelScope/GitHub artifact 的匿名访问和 Range 探测；
- CDN 命中率、回源错误和流量异常。

告警不得记录下载 URL 重定向中的临时签名查询参数。当前客户端没有上报安装结果，
Cloud 访问日志只能证明清单被读取，不能当作下载或安装成功率。

### CLOUD-UPDATE-007：境内外镜像顺序优化（可选）

首版可返回统一清单并按 `urls` 顺序故障切换。如果生产测试显示境外访问 ModelScope
明显慢于 GitHub，可在同一个公开 URL 下提供两份内容等价的区域变体：

```text
中国境内：ModelScope -> GitHub
中国境外：GitHub -> ModelScope
```

区域变体只能调整 `url`/`urls` 顺序；Build、rollout ID、灰度比例、文件名、大小和
SHA-256 必须完全一致。CDN 必须按境内/境外分区缓存，禁止把某一区域响应混入另一
区域缓存。若无法可靠隔离缓存，则保持统一静态清单，不实现此优化。

## 4. Cloud 交付物

Cloud 项目交付时应提供：

1. 生产 `GET /updates/stable.json` 与可选 `HEAD`；
2. staging 环境的同协议端点或可替换 manifest URL；
3. 清单 schema validator 和双源预检任务；
4. 受保护的发布、扩灰、暂停与回退 workflow；
5. CDN 缓存/purge 配置；
6. 境内外探测、dashboard 和告警；
7. 发布与紧急暂停 runbook；
8. 一份验收记录，包含响应头、清单摘要、双源 Range/摘要验证和收敛时间。

## 5. 联调验收用例

Cloud 与 Desktop 至少共同完成：

1. `0%` 清单：符合条件的 App 不下载候选；
2. `100%` 清单：App 选择正确 Build；
3. ModelScope 正常：从第一镜像完成下载；
4. ModelScope 失败：同一 `.part` 自动切换 GitHub 并继续下载；
5. GitHub 失败：已下载并校验的 ModelScope artifact 仍可安装；
6. 某镜像内容被篡改：SHA-256 失败且不会进入 staging；
7. 清单发布中断：客户端仍读取上一份完整清单；
8. 紧急暂停：两分钟内境内外都不再向新客户端暴露候选；
9. App 完成签名、notarization、Build、健康检查和回滚全链路验收。

验收通过后，Cloud 团队将生产 URL、发布 workflow 和 runbook 交给 Desktop Release
负责人；Desktop Release 负责人不得手工修改生产对象绕过 validator。
