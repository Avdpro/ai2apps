# AI2Apps Package 标准发布流程

本文是 AI2Apps Package 的唯一标准发布手册，适用于 App、Agent、纯 Python/Node
Service、模型 Service，以及包含 macOS 原生代码的 Runtime Package。

目标是让任何 Agent 都沿用已经验证过的发布链路：

1. 校验源码、版本和依赖；
2. 生成不可变的 Package Contract v1 发布物；
3. 使用 AI2Apps Publisher Ed25519 密钥生成 detached envelope；
4. 通过本机 AI2Apps Local 会话直接调用 Cloud API；
5. 提交、申请审核、批准并发布；
6. 为大型 Package 配置并验收 Cloud、ModelScope、GitHub 多源分发；
7. 使用 submission ID 恢复中断的发布，不重复试错。

不得使用浏览器自动化或 Discover WebUI 代替本流程。WebUI 只用于人工查看结果。

## 1. 发布原则

- 每个 `package ID + version` 对应唯一、不可变的字节内容。发布后需要修正时必须增加版本。
- 不得为了绕过失败临时更换 Package ID、Publisher、Publisher key 或版本。
- 不得在聊天、命令行、日志或文档中输出 Publisher 私钥、Apple App 专用密码、Cookie 或 Cloud token。
- 原生 Runtime 必须同时通过 Apple Developer ID、Hardened Runtime、notarization、staple 和 AI2Apps Publisher 签名。
- 普通 Package 只需要 AI2Apps Publisher 签名；若内部带 Mach-O、`.dylib`、`.so`、可执行 Node addon 等原生载荷，仍按原生 Runtime 规则处理。
- 有依赖关系时先发布 Runtime，再发布依赖它的模型或 Service Package。
- Cloud 制品地址是永久兼容源。较大的 Package 原则上还应至少配置 ModelScope 和
  GitHub 两个外部源，即形成 Cloud + ModelScope + GitHub 三源分发；小型 Package
  可以只使用 Cloud，旧单源 Package 继续兼容。
- 所有外部源必须指向与 Cloud 制品逐字节相同的不可变文件，并通过完整 SHA-256、
  文件大小、Range 和逐 piece 校验；不得使用 mutable branch、latest 地址、带临时
  token 的 URL 或重新打包后的镜像文件。
- 发布中断后先查询现有 submission，再使用其 ID 恢复；不要重新提交同一发布物。
- Agent 读取浏览器 Cookie 前，必须获得用户对本次发布的明确授权。授权仅限指定 Package，不得复用到别的发布任务。

## 2. 固定工具

在仓库根目录执行：

```bash
cd /Users/avdpropang/sdk/omlx-moe-cache
```

只使用以下入口：

| 工作 | 标准入口 |
| --- | --- |
| 构建普通 Contract v1 Package 并生成 envelope | `scripts/build_signed_registry_release.py` |
| 验证 MS/HF 字节并生成 checkpoint distribution envelope | `scripts/build_checkpoint_distribution.py` |
| 校验公网签名 Index 和 distribution envelope | `scripts/verify_checkpoint_distribution_publication.py` |
| 构建并签名 oMLX Runtime 内层 DMG | `scripts/build_omlx_runtime_dmg.py` |
| 将已公证 Runtime DMG 封装成 Package | `scripts/build_omlx_runtime_package.py` |
| 查询 Publisher/Submission，提交、审核、发布 | `scripts/publish_signed_registry_artifact.py` |

不要临时编写 `curl`、手工拼 multipart 请求或直接改 Cloud 数据库。Cloud API 契约变化时只修改并测试上述脚本，本手册的调用方式保持稳定。

## 3. 发布前输入

每次发布开始前必须明确以下值；未知时先查询，不要猜：

```bash
PACKAGE_SOURCE=/absolute/path/to/package-source
ARTIFACT=/absolute/path/to/package-id-version.ai2service
PUBLISHER_ID='<cloud publisher id>'
PUBLISHER_KEY_ID='<publisher key id>'
PUBLISHER_KEY_SECRET='<SecretBackend record id>'
INSTANCE_ID='dev'
BASE_PATH="$HOME/Library/Application Support/AI2Apps/instances/$INSTANCE_ID/data"
SECURITY_INSTANCE_ID='<installation_id from the current AI2Apps client bootstrap; local_...>'
KEYCHAIN_NAMESPACE='<SecretBackend namespace used when the Publisher key was saved>'
```

说明：

- `INSTANCE_ID` 必须是当前已登录、已完成管理员验证的 AI2Apps 实例。
- `BASE_PATH` 是该实例的 `data` 目录，不是实例根目录，也不是仓库目录。
- `SECURITY_INSTANCE_ID` 是当前实例公开 client bootstrap 返回的
  `installation_id`（格式为 `local_` 加 32 位十六进制字符），不是 `dev` 等实例别名。
  `--security-instance-id` 必须使用此值；使用实例别名会导致 scoped Cookie 名称无法解析。
- `KEYCHAIN_NAMESPACE` 必须和保存 Publisher 私钥时使用的 SecretBackend namespace 一致；它不一定永远等于实例 ID，发布前应从既有成功发布配置或 Publisher 上下文确认。
- `PUBLISHER_KEY_SECRET` 是安全存储中的记录 ID，不是私钥内容。
- 正式发布物放在 Package 自己的 `dist/` 或专门的 release 目录，不覆盖旧版本。

若本次计划配置外部源，还应在开始前明确并记录：

```text
MODELSCOPE_ARTIFACT_URL=<immutable ModelScope revision URL>
GITHUB_ARTIFACT_URL=<immutable GitHub Release tag URL>
```

这里的 URL 是不包含凭据的最终公开下载地址。上传时使用的 ModelScope/GitHub 凭据
只能从各自的安全凭据存储读取，不得写入 Package、envelope、命令日志或发布收据。

## 4. 发布前检查

### 4.1 工作树和清单

确认本次 Package 的变更、版本和依赖：

```bash
git status --short
git diff --check
```

检查 Package source 至少包含有效的 Contract v1 manifest，并按类型包含需要的：

- `META/sbom.spdx.json`
- license、来源链接和署名
- 平台、CPU 架构和最低 macOS 版本约束
- Runtime dependency 的 Package ID 和最低/精确版本
- 安装、启动、health、stop、upgrade、uninstall 契约

模型 checkpoint 不应打入模型 Service Package；Package 只声明 checkpoint 来源、固定 revision、校验与准备流程。
自 2026-08-27 起，新构建或重新签署的模型 Package 还必须为每个
`models[].weights` 声明 Registry 发布的 `distribution_id`。标准构建器会拒绝
缺少该字段的模型 Package；不得填写占位 ID。历史已安装 Package 仍可沿用旧下载
链路，只有在真实 distribution 完成签名和发布后才能升级。

模型 Package 升版前，必须固定两个 Hub 的 immutable revision。默认流程只需要已有的 HF
固定 revision 快照；构建器读取 ModelScope 的权威文件清单、大小和最终文件 SHA-256，不下载
第二份模型：

```bash
./.venv/bin/python scripts/build_checkpoint_distribution.py \
  --spec "$PACKAGE_SOURCE/META/checkpoint-distribution-<variant>.json" \
  --huggingface-root /absolute/path/to/pinned-hf-snapshot \
  --output /absolute/path/to/dist_<id>.envelope.json \
  --publisher-id "$PUBLISHER_ID" \
  --publisher-key-id "$PUBLISHER_KEY_ID" \
  --keychain-secret "$PUBLISHER_KEY_SECRET" \
  --keychain-namespace "$KEYCHAIN_NAMESPACE"
```

默认 `metadata_verified` 模式要求 HF 本地文件与 MS 元数据的选中文件集合、大小、逐文件
SHA-256 完全一致，并从 HF 字节按规范顺序生成全局 piece hashes；任何差异或任一 MS 文件缺少
SHA-256 都会拒绝生成签名 envelope。首次建立镜像关系、定期审计或元数据不完整时使用双端
完整下载模式：

```bash
./.venv/bin/python scripts/build_checkpoint_distribution.py \
  --verification-mode full_dual_download \
  --spec "$PACKAGE_SOURCE/META/checkpoint-distribution-<variant>.json" \
  --huggingface-root /absolute/path/to/pinned-hf-snapshot \
  --modelscope-root /absolute/path/to/pinned-ms-snapshot \
  --output /absolute/path/to/dist_<id>.envelope.json \
  --publisher-id "$PUBLISHER_ID" \
  --publisher-key-id "$PUBLISHER_KEY_ID" \
  --keychain-secret "$PUBLISHER_KEY_SECRET" \
  --keychain-namespace "$KEYCHAIN_NAMESPACE"
```

输出收据中的
`distributionId`、`manifestDigest`、文件数、piece 数和总字节数必须进入发布记录。
`*.verification.json` 以不同 builder ID 明确记录 `metadata_verified` 或
`full_dual_download`，不得混淆两种证据强度。

Cloud 生产环境自 OpenAPI `1.23.0` 起已提供 checkpoint submission/review/publish API。
使用现有安装 session 提交并申请审核（两个动作可在同一命令明确指定）：

```bash
./.venv/bin/python scripts/publish_checkpoint_distribution.py \
  --base-path "$BASE_PATH" \
  --security-instance-id "$SECURITY_INSTANCE_ID" \
  --envelope /absolute/path/to/dist_<id>.envelope.json \
  --verification-receipt /absolute/path/to/dist_<id>.envelope.verification.json \
  --request-review
```

Reviewer 使用同一脚本的 `--list-review` 查询队列，以 `--submission-id`、
`--decision approved|rejected` 和 `--note` 作出决定；Publisher 在批准后使用
`--submission-id ... --publish` 发布。脚本不会隐式审核或发布。只有公网 distribution
端点可读取该 envelope，且新的签名 Index 已包含它之后，才允许同步升级
`service.yaml`、`ai2apps.json` 的 Package 版本和 `weights.distribution_id`。

公网回读必须使用不带用户 Cookie 的 Local trust 路径：

```bash
./.venv/bin/python scripts/verify_checkpoint_distribution_publication.py \
  --distribution-id "$DISTRIBUTION_ID" \
  --envelope /absolute/path/to/dist_<id>.envelope.json \
  --cache-root /absolute/path/to/clean-verification-cache
```

### 4.2 测试

至少执行与 Package 相关的单元测试、Package 审计和真实 managed-service smoke test。Service Package 的生产验收要求见：

- `docs/service-package-sandbox-development-guide.md`
- `docs/model-worker-package-manual.md`

不得因为本地源码方式可以启动，就跳过安装真实 `.ai2service` 后的验证。

### 4.3 查询当前 Publisher 和 Submission

优先使用安装实例的 Cloud session，不读取浏览器 Cookie：

```bash
./.venv/bin/python scripts/publish_signed_registry_artifact.py \
  --base-path "$BASE_PATH" \
  --security-instance-id "$SECURITY_INSTANCE_ID" \
  --publishers-only

./.venv/bin/python scripts/publish_signed_registry_artifact.py \
  --base-path "$BASE_PATH" \
  --security-instance-id "$SECURITY_INSTANCE_ID" \
  --list-only
```

查询结果必须确认：

- Publisher ID 正确；
- Publisher key 状态有效；
- `PUBLISHER_KEY_SECRET` 元数据中的 `fingerprintSha256` 与 Cloud 返回的
  `PUBLISHER_KEY_ID` 指纹完全一致；只匹配 key ID 或 Secret 记录名不够；
- Cloud session 属于预期账户/组织；
- 不存在相同 Package/version 的进行中 submission。

如果安装实例 session 无权审核/发布，执行第 7 节的管理员会话步骤，不要尝试其他认证手段。

## 5. 构建普通 Package

普通 Package 包括不携带原生载荷的 App、Agent、纯 Python/Node Service 和模型 Service。

```bash
./.venv/bin/python scripts/build_signed_registry_release.py \
  --source "$PACKAGE_SOURCE" \
  --output "$ARTIFACT" \
  --publisher-id "$PUBLISHER_ID" \
  --publisher-key-id "$PUBLISHER_KEY_ID" \
  --keychain-secret "$PUBLISHER_KEY_SECRET" \
  --keychain-namespace "$KEYCHAIN_NAMESPACE"
```

成功后固定生成两个文件：

```text
<artifact>.ai2service
<artifact>.ai2service.envelope.json
```

脚本输出的 `packageId`、`version`、`sha256` 和 `size` 是本次发布收据的第一部分，应保存到发布记录中。

如果 `.ai2service` 已由专用构建器产生，只允许在原路径上签 envelope：

```bash
./.venv/bin/python scripts/build_signed_registry_release.py \
  --artifact "$ARTIFACT" \
  --output "$ARTIFACT" \
  --publisher-id "$PUBLISHER_ID" \
  --publisher-key-id "$PUBLISHER_KEY_ID" \
  --keychain-secret "$PUBLISHER_KEY_SECRET" \
  --keychain-namespace "$KEYCHAIN_NAMESPACE"
```

`--artifact` 与 `--output` 必须指向同一个文件，这是防止签错发布物的安全限制。

## 6. 构建含原生代码的 Runtime Package

以 oMLX Runtime 为标准实现。它采用“两阶段”流程，禁止把未公证的 DMG 放入正式 Package。

### 6.1 构建 Developer ID Runtime DMG

```bash
RUNTIME_SOURCE=/Users/avdpropang/sdk/omlx-moe-cache/packages/ai2apps-runtime-omlx
RUNTIME_LAYERS=/absolute/path/to/packaging/_export
RUNTIME_VERSION='<new runtime version>'
INTERNAL_DMG=/absolute/path/to/AI2Apps-oMLX-Runtime-${RUNTIME_VERSION}-internal.dmg
FINAL_DMG=/absolute/path/to/AI2Apps-oMLX-Runtime-${RUNTIME_VERSION}.dmg
SIGN_IDENTITY='Developer ID Application: <identity from security find-identity>'

./.venv/bin/python scripts/build_omlx_runtime_dmg.py \
  --layers "$RUNTIME_LAYERS" \
  --output "$INTERNAL_DMG" \
  --version "$RUNTIME_VERSION" \
  --sign-identity "$SIGN_IDENTITY"
```

Apple identity 必须从本机 Keychain 的有效 `Developer ID Application` identity 取得，不要把证书名称写死到脚本。

### 6.2 公证与 staple

首次配置公证凭据时让 `notarytool` 交互读取 App 专用密码：

```bash
xcrun notarytool store-credentials ai2apps-notary \
  --apple-id avdpro@me.com \
  --team-id 84XL5V265N
```

不得把 App 专用密码放在命令行。提交的是内部候选的副本，保留原始不可变候选：

```bash
cp "$INTERNAL_DMG" "$FINAL_DMG"
xcrun notarytool submit "$FINAL_DMG" \
  --keychain-profile ai2apps-notary \
  --wait
xcrun stapler staple "$FINAL_DMG"
xcrun stapler validate "$FINAL_DMG"
spctl --assess --type open --context context:primary-signature -v "$FINAL_DMG"
```

若已有另一个有效 Keychain profile，可显式替换 `ai2apps-notary`；不创建重复 profile。

### 6.3 封装并签署外层 Package

```bash
./.venv/bin/python scripts/build_omlx_runtime_package.py \
  --source "$RUNTIME_SOURCE" \
  --layers "$RUNTIME_LAYERS" \
  --output "$ARTIFACT" \
  --prepared-dmg "$FINAL_DMG" \
  --prepared-signing developer-id \
  --team-id 84XL5V265N \
  --keychain-secret "$PUBLISHER_KEY_SECRET" \
  --keychain-namespace "$KEYCHAIN_NAMESPACE" \
  --publisher-id "$PUBLISHER_ID" \
  --key-id "$PUBLISHER_KEY_ID"
```

构建器会验证 staple、Developer ID Team ID 和 Runtime 结构，并生成外层 Package 及 Publisher 签名。任何验证失败都必须回到对应阶段修复，不能关闭检查。

## 7. 获取本次发布所需的管理员会话

提交本身通常可使用 Installation Cloud session。批准和发布需要当前账户具备相应 Publisher 权限，并可能要求刚完成的管理员 step-up。

标准步骤：

1. 启动固定开发 App：`apps/ai2apps-acefox/.build/AI2Apps-dev.app`；
2. 确认当前实例 ID 和发布账户；
3. 用户在 **Account → Security → Administrator verification** 中自行输入管理员密码并验证；
4. Agent 不得询问、读取、代输或保存管理员密码；
5. 如果 API 脚本必须使用浏览器会话，Agent 先请求一次明确授权，例如：

   > 允许读取当前 AI2Apps 会话 Cookie，仅用于发布 `<package id> <version>`。

6. 获得授权后，只把准确的当前 profile `cookies.sqlite` 路径传给发布脚本。脚本以 SQLite read-only/immutable 模式读取所需 cookie；不得复制数据库、打印 cookie 或自行执行 SQL 导出。

Cookie 数据库位于当前实例的 `browser-profiles` 下，但 profile 名称由 AceFox 生成。必须根据当前实例和当前运行 profile 确认准确文件，禁止从多个 `cookies.sqlite` 中碰运气。授权在本次指定 Package 发布结束后立即失效。

## 8. 通过 Cloud API 发布

### 8.1 首次提交并完成发布

不需要浏览器管理员会话时：

```bash
./.venv/bin/python scripts/publish_signed_registry_artifact.py \
  --base-path "$BASE_PATH" \
  --security-instance-id "$SECURITY_INSTANCE_ID" \
  --artifact "$ARTIFACT" \
  --envelope "$ARTIFACT.envelope.json" \
  --review-note "Verified Package Contract, signature, tests, and release metadata."
```

已按第 7 节获得 Cookie 读取授权且确实需要管理员浏览器会话时：

```bash
BROWSER_COOKIE_DB='/absolute/path/to/current/profile/cookies.sqlite'

./.venv/bin/python scripts/publish_signed_registry_artifact.py \
  --base-path "$BASE_PATH" \
  --security-instance-id "$SECURITY_INSTANCE_ID" \
  --browser-cookie-db "$BROWSER_COOKIE_DB" \
  --artifact "$ARTIFACT" \
  --envelope "$ARTIFACT.envelope.json" \
  --review-note "Verified Package Contract, signature, tests, and release metadata."
```

该命令依次执行：

1. submit；
2. request review；
3. approve review；
4. publish。

输出 JSON 中的 `submission_id` 与 `published` 是发布收据的第二部分，必须保存。日志和收据不得包含 Cookie、token 或私钥。

### 8.2 从已有 submission 恢复

如果 submit 已成功、后续步骤失败，先执行 `--list-only` 找到对应 Package/version 的 submission ID，然后恢复：

```bash
SUBMISSION_ID='<existing submission id>'

./.venv/bin/python scripts/publish_signed_registry_artifact.py \
  --base-path "$BASE_PATH" \
  --security-instance-id "$SECURITY_INSTANCE_ID" \
  --browser-cookie-db "$BROWSER_COOKIE_DB" \
  --submission-id "$SUBMISSION_ID" \
  --review-note "Resuming verified release after an interrupted publication request."
```

恢复时不传 artifact/envelope，也不重新 submit。若不需要 Cookie，删除 `--browser-cookie-db` 参数。

## 9. 配置 Package 多源分发

多源配置是 Package Release 发布完成后的独立分发步骤，不属于 Publisher envelope，
也不改变已经发布的 Package ID、版本、artifact SHA-256 或 Publisher 签名。Cloud 会为
源列表生成新的、经过签名的 Repository Snapshot；客户端只有在验证该 Snapshot 后才会
使用其中的 `artifact.pieces` 和 `artifact.sources`。

### 9.1 何时配置

- Cloud 源始终存在，不能被外部镜像替代或禁用。
- 小型 Package 可以保持 Cloud 单源，旧客户端和旧 Package 继续使用原有完整下载路径。
- Runtime、携带原生依赖的 Service，或其他下载体感明显的较大 Package，原则上至少增加
  ModelScope 和 GitHub 两个外部源。此时公开源列表至少包含 Cloud、ModelScope、GitHub
  三个源，以同时覆盖中国境内与境外网络。
- 如果大型 Package 暂时无法满足双外部源要求，可以先以 Cloud 单源发布，但必须在发布
  收据中记录例外原因和补齐计划，不能伪造未验证的镜像地址。

### 9.2 外部制品要求

1. 将发布时已经生成并签名的同一个 `$ARTIFACT` 原样上传，不重新压缩、注入元数据或
   再次签署内容。
2. ModelScope URL 必须固定到不可变 revision；GitHub URL 必须使用
   `/releases/download/<immutable-tag>/...`。不得使用 branch、`latest`、可覆盖 tag 或
   含访问 token/临时签名参数的 URL。
3. 每个外部源都必须支持匿名 HTTPS、`HEAD`、单 Range `GET`、正确的 `206`、
   `Content-Range`、`Content-Length` 和 identity encoding。
4. 上传后分别验证完整文件大小和 SHA-256 与 `$ARTIFACT` 完全一致，并验证首段、中段、
   尾段及单字节 Range。任一项不一致都不得注册或激活该源。

外部源的可信依据始终是已发布 Package 的完整摘要和 Cloud 生成的 piece hashes，不是
ModelScope/GitHub 的文件名、仓库身份或 HTTP 状态码本身。

### 9.3 注册、审批和激活

源管理使用 Cloud OpenAPI `1.39.0` 的受保护接口：

```text
GET  /v1/admin/registry/packages/{namespace}/{name}/versions/{version}/sources
POST /v1/admin/registry/packages/{namespace}/{name}/versions/{version}/sources
GET  /v1/admin/registry/packages/{namespace}/{name}/versions/{version}/sources/{sourceId}
POST /v1/admin/registry/packages/{namespace}/{name}/versions/{version}/sources/{sourceId}/activate
POST /v1/admin/registry/packages/{namespace}/{name}/versions/{version}/sources/{sourceId}/disable
POST /v1/admin/registry/packages/{namespace}/{name}/versions/{version}/sources/{sourceId}/validate
POST /v1/admin/registry/packages/{namespace}/{name}/versions/{version}/sources/rollback
```

固定流程如下：

1. `GET .../sources` 读取当前 source revision 和 ETag；
2. 分别注册 ModelScope 和 GitHub 不可变 URL，每次 mutation 使用唯一
   `Idempotency-Key` 和最新 `If-Match`；
3. 轮询注册结果的 `statusUrl`，等待完整预检进入 `pending_approval`；
4. 由不同于注册操作人的 reviewer/admin 使用 `validationId`、`validationDigest` 和最新
   source ETag 激活；不得由同一操作人自审自批；
5. 每激活一个源后重新读取最新 ETag，再处理下一个源；
6. 保存 source ID、kind、不可变 URL、validation digest、激活操作人与审批人、新的
   Repository Snapshot digest，作为多源发布收据。

Cloud 预检必须覆盖 DNS/HTTPS/重定向白名单、HEAD、Range、size、完整 SHA-256 和逐 piece
SHA-256。不得直接修改 Cloud 数据库、已有 Release 行或已经签名的 Snapshot，也不得为了
绕过预检降低校验条件。

### 9.4 多源验收与回退

激活后必须匿名回读 Package Release 和最新 Repository Snapshot，并确认：

- `artifact.downloadUrl`/`artifact.url` 仍是原 Cloud 兼容地址；
- `artifact.pieces` 完整，`artifact.sources` 只包含 active 源，并至少包含 Cloud；
- 大型 Package 的公开源列表包含 Cloud、ModelScope、GitHub 三种来源；
- 新 Snapshot 签名验证成功，源列表、piece 清单和 Package 完整摘要属于同一个 Snapshot；
- 客户端能在一个源超时、DNS 失败、错误返回 `200` 或 piece 损坏时，由其他源继续下载；
- 完成后仍执行完整文件 SHA-256 和 Publisher 签名校验，再进入安装。

外部源异常时只禁用受影响的 source，并使用最新 ETag、受限原因和独立审计发布新的
Snapshot；Cloud fallback 必须保持可用。需要整体回退源集合时，使用保留的
`snapshotDigest` 调用 sources rollback，产生一次受审计的向前发布，不修改旧 Snapshot。

## 10. 依赖 Package 发布顺序

发布一组相关 Package 时固定采用拓扑顺序：

1. 原生 Runtime；
2. 共用 Service/Runtime dependency；
3. 模型或功能 Service；
4. 依赖这些 Service 的 App/Agent。

每发布一层都应在 Cloud/Discover 中验证版本已经可解析，再发布下一层。模型 Package 的 dependency 必须指向刚验证过的 Runtime 版本范围。不得先发模型，再期望未发布的 Runtime 自动出现。

## 11. 发布后验证

发布命令成功并不等于交付完成。必须执行：

1. 用 `--list-only` 确认 submission 为 published；
2. 在 Discover 刷新，确认 Package ID、版本、Publisher、类型、平台和最低系统版本正确；
3. 在受支持的干净实例安装；
4. 验证 dependency 自动解析和升级；
5. 验证 Package audit/用户批准流程；
6. 对 Service 验证 startup、readiness、health、调用、stop、restart 和 uninstall；
7. 对模型验证 Registry distribution、断点续传、逐 piece/文件校验、Worker 快照激活
   和一次真实推理；
8. 配置了多源时，分别验证 ModelScope、GitHub、Cloud 的完整字节与 Range，并在中国境内、
   境外或等价网络条件下验证竞速、单源故障切换和断点续传；
9. 对原生 Runtime 在另一台满足最低 macOS 版本的 Mac 上验证 Gatekeeper 与加载；
10. 保存发布收据：commit、Package ID/version、artifact SHA-256、size、Publisher key ID、
    submission ID、外部 source/validation/Snapshot 摘要、发布时间和验证结果。

## 12. 失败处理表

| 错误/现象 | 正确处理 | 禁止做法 |
| --- | --- | --- |
| Cloud session 不存在或过期 | 重新登录正确实例，再查询上下文 | 尝试读取其他实例 token |
| 管理员验证过期 | 让用户在 Account 中重新验证 | 询问或代输密码 |
| Cookie unavailable | 确认当前实例/profile；重新获得本次授权 | 扫描并试用所有 profile |
| Publisher/key 不匹配 | 查询 Publisher 上下文，使用原正确 key | 临时新建 Publisher/key |
| 相同版本已存在 | 比较 SHA；相同则停止重复发布，不同则提升版本 | 覆盖不可变版本 |
| digest/size/signature 不匹配 | 重新构建 envelope，确认签的是同一 artifact | 手改 envelope JSON |
| 已 submit、审核/发布失败 | 使用 submission ID 恢复 | 重新 submit |
| Runtime 未 notarize/staple | 回到 Apple 公证阶段 | 关闭 Runtime 校验 |
| dependency 无兼容版本 | 先发布依赖或修正版本/平台约束 | 移除依赖检查 |
| Package audit 要求批准 | 在产品 UI 中展示并让用户明确批准 | 自动绕过审计 |
| 网络超时 | 查询 submission 判断请求是否已成功，再决定恢复 | 盲目重复发布 |
| 外部源 size/SHA/piece 不一致 | 禁止激活，重新上传同一 artifact 后重新预检 | 修改 envelope 或接受近似一致的文件 |
| 外部源不支持 Range/返回 `200` | 禁止激活或禁用该源，保留 Cloud fallback | 把完整响应写入 partial offset |
| 已激活外部源故障 | 禁用单个故障源并发布新 Snapshot | 删除或覆盖 Package Release |
| source revision/ETag 冲突 | 重新读取最新 sources 和 ETag 后重试当前 mutation | 忽略 `If-Match` 强行覆盖 |

## 13. Agent 执行清单

Agent 每次发布只按下面顺序行动：

- [ ] 阅读本手册和仓库 `AGENTS.md`；
- [ ] 明确 Package ID、版本、source、artifact、Publisher/key、实例；
- [ ] 检查版本、依赖、平台约束、SBOM、license；
- [ ] 执行相关测试和真实 Package smoke test；
- [ ] 查询 Publisher 与已有 submission；
- [ ] 普通 Package 走第 5 节，原生 Runtime 走第 6 节；
- [ ] 保存构建输出的 SHA-256/size；
- [ ] 需要管理员浏览器会话时先取得本次明确 Cookie 授权；
- [ ] 使用第 8 节脚本发布或恢复；
- [ ] 大型 Package 按第 9 节上传并激活 ModelScope + GitHub 外部源；
- [ ] 按依赖拓扑逐层发布；
- [ ] 完成第 11 节验证并报告 Package 与多源发布收据。

只要某一步失败，就在该步骤内诊断并修复。不得切换到 WebUI、临时 `curl`、手工数据库写入或另一套签名方式。
