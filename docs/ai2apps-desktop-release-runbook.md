# AI2Apps Desktop 完整发布 Runbook

状态：当前正式流程，适用于 Apple Silicon (`arm64`) Desktop App

更新频道：`stable`

清单地址：`https://coder.ai2apps.com/updates/stable.json`

GitHub：`Avdpro/ai2apps`

ModelScope：`ai2apps/desktop-releases`

本文是 AI2Apps Desktop 从源码到用户收到更新的权威操作手册，覆盖：构建 App、
Developer ID 签名、制作 DMG、Apple 公证与 staple、上传 GitHub/ModelScope、生成双源
清单、交给 Cloud 原子发布、灰度、验收和回退。Package/Runtime/模型包发布不使用本文，
继续使用 `docs/ai2apps-package-publication-runbook.md`。

`docs/ai2apps-desktop-next-release.md` 是本手册配套的唯一“下一版 Release 台账”。任何需要
评估是否进入下一版 Desktop 的工作都必须在实现当轮登记；每次构建前必须完整读取并逐项
关闭，不能只依赖 Git diff、聊天记录或记忆确定 Release 范围。

## 1. 不可变发布约束

- 产品名固定为 `AI2Apps.app`，Bundle ID 固定为 `com.ai2apps.desktop`，实例固定为
  `default`。
- 当前只发布 `arm64`，不生成 Intel 或 Universal 版本。
- 当前不启用 App Sandbox：`SANDBOX_MODE=0`。Firefox 内容进程沙箱、Developer ID、
  Hardened Runtime、递归验签和公证仍然必须保留。
- 正式 App 必须使用 `RUNTIME_PROFILE=cloud`。这里的 Cloud Runtime 是在干净 Mac 上
  启动控制平面所需的精简 Runtime，不能因为 DMG 体积变大而删除。它不包含完整 MLX
  推理 Runtime。
- 签名身份固定为 `Developer ID Application: Avdpro Pang (84XL5V265N)`，Team ID 固定为
  `84XL5V265N`。
- Build Number 必须为正整数且严格递增；版本号和 Build Number 分别来自
  `CFBundleShortVersionString` 与 `CFBundleVersion`。
- 正式候选必须经过 App/DMG 签名、Apple notarization、staple、Gatekeeper、大小和
  SHA-256 校验。只签名但未公证的候选只能用于显式的内部测试，不能写入生产清单。
- GitHub 必须使用 `Avdpro/ai2apps` 的不可变 Release tag；ModelScope 必须使用
  `ai2apps/desktop-releases` 的不可变 commit revision。禁止在清单中使用 `main`、
  `master`、`latest` 或临时签名下载 URL。
- 生产清单必须同时包含 ModelScope 和 GitHub 两个完全相同的 DMG/metadata 源。
- 不直接编辑生产 `stable.json`，不直接写 Cloud 数据库或清单存储。必须经 Cloud
  项目的校验、双源预检、审计和原子发布流程。
- 不在命令、日志、文档或聊天中打印 Apple app-specific password、ModelScope token、
  GitHub token、Cookie 或下载重定向中的临时签名参数。

## 2. 发布前输入和源码门禁

以下路径以仓库根目录为当前目录：

```bash
cd /Users/avdpropang/sdk/omlx-moe-cache
```

需要准备：

1. 已读取 `docs/ai2apps-desktop-next-release.md`，其生产基线与当前匿名
   `stable.json` 一致，并已对每个开放 NXR 项作出纳入或延期决定。
2. 已打包的、包含两个 `omni.ja` 且带 AI2Apps shell patch 的 `Acefox.app`；不能使用
   普通 AceFox 或 objdir 开发 App。
3. 已导出的 Runtime layers，默认位于 `packaging/_export`，至少包含
   `cpython-3.11` 和 `framework-control-plane`。
4. Developer ID Application 证书及私钥已在登录钥匙串中可用。
5. `ai2apps-notary` 公证凭据已保存到钥匙串。
6. `gh auth status` 对 `github.com` 的账号是 `Avdpro`，且具有仓库 Release 权限。
7. 本仓库 `.venv` 已安装 `modelscope_hub`，本机已有对应 ModelScope Hub 缓存凭据。

首次配置 Apple 公证凭据时只运行下列交互命令，由 `notarytool` 安全读取 app-specific
password；不得把密码拼进命令行：

```bash
xcrun notarytool store-credentials ai2apps-notary \
  --apple-id avdpro@me.com \
  --team-id 84XL5V265N
```

正式发布要求源码已经提交，并且发布 commit 已推送到 `origin`。记录而不是猜测二进制
来源：

```bash
git status --short
git diff --check
git branch --show-current
git rev-parse HEAD
git push origin HEAD
```

`git status --short` 对正式发布必须为空。内部升级测试若确实需要从 dirty tree 构建，
必须获得明确批准，并在发布回执中保存 commit、diff 摘要和“binary 不完全由 tag 重现”
说明；不得把这种候选描述为可重现的正式版本。

根据改动范围运行测试，最低门禁为：

```bash
swift test --package-path apps/ai2apps-acefox
git diff --check
```

涉及 Local、Python 或 WebUI 的改动还必须运行对应 focused/full pytest；测试失败不得靠
提高 Build Number 或重打包绕过。

### 2.1 下一版台账门禁

正式定义候选范围前必须：

1. 匿名读取生产 `stable.json`，核对台账记录的版本、Build 和基线回执；
2. 逐项检查所有 `in_progress`、`blocked`、`ready`、`deferred` 项；
3. `blocked` 项只有在阻塞证据清零并改为 `ready` 后才能纳入；
4. 为拟纳入项记录源码文件、测试、配置/迁移、Release notes、回退方式和 NXR ID；
5. 对上一版最终 DMG 的实际内嵌内容与候选 staging App 做差异核对，确认没有未登记的
   用户可见、安全或打包变化；
6. 确认拟纳入的未跟踪文件已经加入版本控制，且正式候选满足 clean-tree 门禁。

若候选内容与台账不一致，先更新台账并补测试，不得边公证边临时整理 Release 范围。

## 3. 定义一次性发布变量

下面以 `0.1.0`、Build `2247` 为示例。每次发布只修改本节，不在后续命令中手工混用
版本号或路径：

```bash
AI2APPS_VERSION=0.1.0
AI2APPS_BUILD=2247
AI2APPS_TAG="v${AI2APPS_VERSION}-build${AI2APPS_BUILD}"
AI2APPS_RELEASE_DIR="/Users/avdpropang/sdk/omlx-moe-cache/apps/ai2apps-acefox/.build/releases/AI2Apps-${AI2APPS_VERSION}-build${AI2APPS_BUILD}"
AI2APPS_ACEFOX_APP="/Users/avdpropang/sdk/moz/acefox-firefox-153/obj-aarch64-apple-darwin/dist/firefox/Acefox.app"
AI2APPS_SIGN_IDENTITY='Developer ID Application: Avdpro Pang (84XL5V265N)'
AI2APPS_SOURCE_COMMIT="$(git rev-parse HEAD)"
AI2APPS_APP="${AI2APPS_RELEASE_DIR}/AI2Apps.app"
AI2APPS_DMG_NAME="AI2Apps-${AI2APPS_VERSION}-build${AI2APPS_BUILD}-macos-arm64.dmg"
AI2APPS_METADATA_NAME="AI2Apps-${AI2APPS_VERSION}-build${AI2APPS_BUILD}-macos-arm64.release.json"
AI2APPS_INTERNAL_DMG="${AI2APPS_RELEASE_DIR}/AI2Apps-${AI2APPS_VERSION}-build${AI2APPS_BUILD}-macos-arm64-internal.dmg"
AI2APPS_INTERNAL_METADATA="${AI2APPS_RELEASE_DIR}/AI2Apps-${AI2APPS_VERSION}-build${AI2APPS_BUILD}-macos-arm64-internal.release.json"
AI2APPS_DMG="${AI2APPS_RELEASE_DIR}/${AI2APPS_DMG_NAME}"
AI2APPS_METADATA="${AI2APPS_RELEASE_DIR}/${AI2APPS_METADATA_NAME}"
mkdir -p "${AI2APPS_RELEASE_DIR}"
```

发布脚本拒绝覆盖已有输出。这是保护机制：不要删除旧工件后在同一 tag 下重新发布；若
候选内容发生变化，应增加 Build Number 并使用新目录和新 tag。

## 4. 构建并签名 App

```bash
ACEFOX_APP="${AI2APPS_ACEFOX_APP}" \
RUNTIME_LAYERS="/Users/avdpropang/sdk/omlx-moe-cache/packaging/_export" \
RUNTIME_PROFILE=cloud \
OUTPUT_APP="${AI2APPS_APP}" \
INSTANCE_ID=default \
BUILD_NUMBER="${AI2APPS_BUILD}" \
SIGN_IDENTITY="${AI2APPS_SIGN_IDENTITY}" \
TEAM_IDENTIFIER=84XL5V265N \
SANDBOX_MODE=0 \
UPDATE_MANIFEST_URL=https://coder.ai2apps.com/updates/stable.json \
apps/ai2apps-acefox/scripts/build-release-app.sh
```

脚本会构建 Swift 组件、复制 AceFox 和精简 Runtime、生成 Runtime manifest、递归签名，
并运行 `verify-release-app.sh`。构建必须在正常 macOS 环境执行；受限沙箱中的
`codesign`/`spctl` 结果可能是假阴性，不能据此发布或否决候选。

核对身份和版本：

```bash
/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "${AI2APPS_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "${AI2APPS_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Print :AI2AppsRuntimeProfile' "${AI2APPS_APP}/Contents/Info.plist"
codesign -dvvv "${AI2APPS_APP}"
codesign --verify --deep --strict --verbose=2 "${AI2APPS_APP}"
```

预期 Runtime profile 为 `cloud`，架构为 `arm64`，Build 与本次变量一致。App 体积明显
变化时，先检查 Runtime profile 和内容差异，不要先删 Runtime。

## 5. 制作已签名的内部 DMG 和 metadata

```bash
APP="${AI2APPS_APP}" \
OUTPUT_DMG="${AI2APPS_INTERNAL_DMG}" \
SIGN_IDENTITY="${AI2APPS_SIGN_IDENTITY}" \
apps/ai2apps-acefox/scripts/build-release-dmg.sh

apps/ai2apps-acefox/scripts/generate-release-metadata.py \
  --app "${AI2APPS_APP}" \
  --dmg "${AI2APPS_INTERNAL_DMG}" \
  --output "${AI2APPS_INTERNAL_METADATA}"

APP="${AI2APPS_APP}" \
DMG="${AI2APPS_INTERNAL_DMG}" \
METADATA="${AI2APPS_INTERNAL_METADATA}" \
apps/ai2apps-acefox/scripts/preflight-notarization.sh
```

内部 metadata 必须显示 `notarization.status=not_stapled`。该三件套可以用
`verify-update-candidate.py --internal-candidate` 做开发验收，但不能上传为 stable 候选。

## 6. Apple 公证、staple 和最终验证

```bash
ARTIFACT="${AI2APPS_INTERNAL_DMG}" \
APP="${AI2APPS_APP}" \
SOURCE_METADATA="${AI2APPS_INTERNAL_METADATA}" \
OUTPUT_DMG="${AI2APPS_DMG}" \
OUTPUT_METADATA="${AI2APPS_METADATA}" \
KEYCHAIN_PROFILE=ai2apps-notary \
apps/ai2apps-acefox/scripts/notarize-release.sh
```

该脚本不会修改内部源 DMG。它会提交临时副本、等待 Apple 结果、staple、运行
Stapler/Gatekeeper/签名/DMG/Runtime 检查，再生成最终 metadata。单独复验：

```bash
APP="${AI2APPS_APP}" \
DMG="${AI2APPS_DMG}" \
METADATA="${AI2APPS_METADATA}" \
apps/ai2apps-acefox/scripts/verify-notarized-release.sh

shasum -a 256 "${AI2APPS_DMG}" "${AI2APPS_METADATA}"
stat -f '%N %z bytes' "${AI2APPS_DMG}" "${AI2APPS_METADATA}"
```

保存 `notarytool` Submission ID。若公证失败，先用同一 Submission ID 获取 Apple log 并
修复原因，不盲目重复提交。最终 metadata 必须为 `stapled`，其文件名、大小和 SHA-256
必须与最终 DMG 一致。

如果有上一版 App，可在上传前执行真正的升级候选门禁：

```bash
apps/ai2apps-acefox/scripts/verify-update-candidate.py \
  --installed-app /Applications/AI2Apps.app \
  --candidate-app "${AI2APPS_APP}" \
  --candidate-dmg "${AI2APPS_DMG}" \
  --candidate-metadata "${AI2APPS_METADATA}"
```

它只判断资格，不修改 `/Applications/AI2Apps.app`；必须看到 Build 严格递增且完整配对
验证通过。

## 7. 发布 GitHub Release

先核对登录、仓库、tag 和远端源码 commit：

```bash
gh auth status
gh api "repos/Avdpro/ai2apps/commits/${AI2APPS_SOURCE_COMMIT}" --jq .sha
gh release view "${AI2APPS_TAG}" --repo Avdpro/ai2apps
```

最后一条在新发布时应返回“不存在”。准备 release notes，至少记录版本、Build、源码
commit、`arm64`、`cloud` Runtime profile、DMG/metadata SHA-256、公证 Submission ID、
主要变更和已通过测试。随后创建 Release：

```bash
gh release create "${AI2APPS_TAG}" \
  "${AI2APPS_DMG}" \
  "${AI2APPS_METADATA}" \
  --repo Avdpro/ai2apps \
  --target "${AI2APPS_SOURCE_COMMIT}" \
  --title "AI2Apps ${AI2APPS_VERSION} Build ${AI2APPS_BUILD}" \
  --notes-file /absolute/path/to/release-notes.md \
  --prerelease
```

升级测试使用 `--prerelease`；面向客户的正式稳定版按批准去掉该参数。更新器使用固定
tag 的 asset URL，与 GitHub 的 prerelease 标记无关。

上传后验证资产存在、大小正确，并对下载文件重新算摘要：

```bash
gh release view "${AI2APPS_TAG}" \
  --repo Avdpro/ai2apps \
  --json url,tagName,targetCommitish,isPrerelease,assets
```

若上传中断，先查询 Release 和 asset；只补传缺失文件。仅在确认远端文件损坏且获批准
后使用 `gh release upload --clobber`。已进入任何清单的 tag/asset 不得覆盖。

## 8. 发布 ModelScope 双源副本

ModelScope 标准路径是仓库 `.venv` 中的 `modelscope_hub.HubApi` 和本机缓存凭据。不要
改用网页上传，不安装/配置 git-lfs，不读取或打印 token。先上传较小的 metadata，再
上传 DMG：

```bash
.venv/bin/python -c "from modelscope_hub.api import HubApi; print(HubApi().upload_file(path_or_fileobj='${AI2APPS_METADATA}', path_in_repo='${AI2APPS_METADATA_NAME}', repo_id='ai2apps/desktop-releases', repo_type='model', revision='master', commit_message='Publish AI2Apps ${AI2APPS_VERSION} Build ${AI2APPS_BUILD} release metadata'))"

.venv/bin/python -c "from modelscope_hub.api import HubApi; print(HubApi().upload_file(path_or_fileobj='${AI2APPS_DMG}', path_in_repo='${AI2APPS_DMG_NAME}', repo_id='ai2apps/desktop-releases', repo_type='model', revision='master', commit_message='Publish AI2Apps ${AI2APPS_VERSION} Build ${AI2APPS_BUILD} DMG'))"
```

每次调用都会产生 commit。必须把第二次（DMG 上传）返回的最终 commit 记为
`AI2APPS_MS_REVISION`，因为该 revision 才同时包含 metadata 和 DMG：

```bash
AI2APPS_MS_REVISION=<第二次上传返回的40位commit>
```

用不可变 revision 查询两项的 `path`、`size`、`sha256`，并与本地结果比对：

```bash
.venv/bin/python -c "from modelscope_hub.api import HubApi; import json; files=HubApi().list_repo_files('ai2apps/desktop-releases','model',revision='${AI2APPS_MS_REVISION}',recursive=True); wanted={'${AI2APPS_DMG_NAME}','${AI2APPS_METADATA_NAME}'}; print(json.dumps([{'path': x.path, 'size': x.size, 'sha256': x.sha256} for x in files if x.path in wanted], indent=2))"
```

上传超时或连接中断时，先查询 revision/文件列表再决定是否重试，不盲目重复上传。
清单只保存稳定的 `resolve/<immutable-revision>/...` URL；ModelScope 重定向产生的临时
`auth_key` URL 不得保存、打印到回执或提交到仓库。

## 9. 生成 0% 和目标灰度清单

固定镜像顺序为 ModelScope 第一、GitHub 第二，确保境内优先；客户端会在失败时断点
切换镜像。新 Build 先生成 0 basis points 清单：

```bash
apps/ai2apps-acefox/scripts/generate-update-manifest.py \
  --release-metadata "${AI2APPS_METADATA}" \
  --base-url "https://modelscope.cn/models/ai2apps/desktop-releases/resolve/${AI2APPS_MS_REVISION}" \
  --base-url "https://github.com/Avdpro/ai2apps/releases/download/${AI2APPS_TAG}" \
  --runtime-profile cloud \
  --rollout-id "build${AI2APPS_BUILD}-test" \
  --percentage-basis-points 0 \
  --output "${AI2APPS_RELEASE_DIR}/stable-zero.json"
```

同一 Build 扩灰时 `rollout.id` 必须保持不变。测试 Mac 需要立即命中时，生成 10000
basis points（100%）版本；正式有客户后按批准使用 `100 -> 500 -> 2000 -> 5000 ->
10000`：

```bash
apps/ai2apps-acefox/scripts/generate-update-manifest.py \
  --release-metadata "${AI2APPS_METADATA}" \
  --base-url "https://modelscope.cn/models/ai2apps/desktop-releases/resolve/${AI2APPS_MS_REVISION}" \
  --base-url "https://github.com/Avdpro/ai2apps/releases/download/${AI2APPS_TAG}" \
  --runtime-profile cloud \
  --rollout-id "build${AI2APPS_BUILD}-test" \
  --percentage-basis-points 10000 \
  --output "${AI2APPS_RELEASE_DIR}/stable.json"
```

不要通过改 `rollout.id` 来让同一批机器重新抽签。`0` 表示候选已登记但无人命中；
`10000` 表示所有符合 Bundle/实例/架构/macOS/Runtime/Build 条件的客户端命中。

## 10. 双源发布前验证

Cloud 预检是最终权威门禁。本地仍应先检查：

- 两个源都可匿名访问 metadata 和 DMG；
- DMG 支持 Range，并返回正确的总大小；
- 两边完整文件与本地的 size/SHA-256 相同；
- metadata 的 size/SHA-256 相同且声明 `stapled`；
- GitHub URL 是 `/releases/download/<immutable-tag>/...`；
- ModelScope URL 是 `resolve/<immutable-commit>/...`；
- 清单中没有 Cookie、token、`auth_key` 或其他临时查询参数。

探测时不要把 `curl -D -` 或 `-v` 输出直接写入发布回执，因为跟随重定向时可能暴露
短期签名查询参数。完整摘要校验应下载到临时目录，验证后安全清理；Cloud 发布工具已
实现这套受控检查。

## 11. 交给 Cloud 原子更新 AI2Apps

Desktop 仓库不直接改 Cloud 代码或生产存储。把以下内容交给 AI2Apps Cloud 的发布
负责人/生产任务：

- `stable-zero.json` 和后续目标灰度；
- 最终 DMG 与 `.release.json` 的本地绝对路径；
- Build、版本、rollout ID；
- GitHub tag、ModelScope immutable revision；
- 本地 size/SHA-256、公证 Submission ID、源码 commit、测试结果；
- 真实 operator、真实 approver 和 bounded reason。

Cloud 项目必须遵循其
`docs/desktop-update-production-runbook.md`，典型的 0% 注册命令为：

```bash
npm run desktop-update -- publish \
  --manifest /release/stable-zero.json \
  --store-dir /srv/ai2apps-cloud/desktop-updates \
  --local-artifact AI2Apps-0.1.0-build2247-macos-arm64.dmg=/release/AI2Apps-0.1.0-build2247-macos-arm64.dmg \
  --local-artifact AI2Apps-0.1.0-build2247-macos-arm64.release.json=/release/AI2Apps-0.1.0-build2247-macos-arm64.release.json \
  --operator release-operator@example.com \
  --approver release-approver@example.com \
  --reason "Publish Build 2247 at zero percent"
```

operator 与 approver 必须是不同、真实、可审计的身份。内部单人测试如果只能记录自动化
操作者和用户明确批准，必须如实标注，不能伪造两个独立审批人；面向客户的生产扩灰应
恢复真正的职责分离。

Cloud 流程必须先校验 schema，再对两个源执行 metadata/DMG 完整下载、Range、大小、
SHA-256 和 notarization 预检，然后原子发布 0%。验收 0% 后，使用同一 rollout ID 扩到
批准比例：

```bash
npm run desktop-update -- rollout \
  --store-dir /srv/ai2apps-cloud/desktop-updates \
  --build 2247 \
  --basis-points 10000 \
  --operator release-operator@example.com \
  --approver release-approver@example.com \
  --reason "Approved Build 2247 end-to-end test rollout"
```

不得拿预先生成的 `stable.json` 绕过 Cloud 的 rollout 操作和审计。

## 12. 生产验收与测试 Mac

Cloud 发布完成后至少验证：

```bash
curl -fsS https://coder.ai2apps.com/updates/stable.json
curl -fsSI https://coder.ai2apps.com/updates/stable.json
```

Cloud 还必须记录：GET/HEAD `200`、正确 Content-Type/Content-Length/Cache-Control、无
Set-Cookie、ETag 条件请求 `304`、生产清单 digest、Build/rollout/比例、双源预检、健康
检查和近期错误日志。境内外探针应在两分钟内看到相同目标摘要。

测试 Mac 上：

1. 确认已安装同 Bundle ID、同实例、同 Team ID、同 Runtime profile 且 Build 更低的
   `/Applications/AI2Apps.app`。
2. 托盘点击“检查更新”；否则 Helper 在启动后约 30 秒检查一次，之后每 24 小时检查。
3. 观察提示、下载进度、镜像切换、安装确认和重启。
4. 安装后核对新 Build；确认新 Helper 已启动并接管仍在运行的 Local。
5. 检查更新状态/日志中没有凭据、下载 URL 或本地敏感路径泄漏。

生产访问日志只能证明清单被读取，不能证明下载或安装成功。端到端验收必须以测试 Mac
实际升级和新 Build 启动成功为准。

## 13. 暂停、回退与失败恢复

- 新 Build 的 0% 发布或预检失败：保持上一份生产清单，不扩灰。
- 已扩灰后发现问题：Cloud 立即把该 Build pause 到 0%，并在两分钟内探测收敛。
- 需要恢复旧清单：按 Cloud `history/` 中已审计 digest 执行 rollback；绝不手工编辑
  `stable.json`。
- 不通过清单推送更低 Build，不做远程自动降级。修复应发布更高 Build。
- GitHub 上传失败：查询 Release/asset 后只补缺项；不覆盖已引用资产。
- ModelScope 上传失败：查询最终 revision 和文件元数据后只补缺项；最终清单必须引用
  同时包含两个文件的 commit。
- Apple 公证失败：保留 Submission ID，读取该提交的 log；修复并增加 Build 后重新走
  全链路，不把失败候选变成 stable。
- 双源任一来源失败时不扩灰。对已发布 Build 的单源应急继续服务需要单独事件批准，不
  在故障诊断期间临时改写清单去掉镜像。

## 14. 每次发布必须保存的回执

发布完成后在 `docs/` 或受控发布记录中保存：

- 产品版本、Build、日期、源码 commit、源码是否 clean；
- App/DMG/metadata 文件名、字节数和 SHA-256；
- Runtime profile、架构、Bundle ID、instance ID、Team ID；
- Apple Submission ID、Accepted/stapled/Gatekeeper 结果；
- GitHub Release URL/tag/资产验证；
- ModelScope repo/final immutable revision/资产验证；
- 0% 和最终清单 digest、rollout ID、basis points；
- Cloud operator、approver、reason、before/after digest；
- GET/HEAD/ETag、双源 Range/完整摘要和多地域探针结果；
- 测试 Mac 的旧 Build、新 Build、下载源、安装和启动结果；
- 运行过的测试及结果；任何例外、审批、暂停或回退。
- 本次纳入、延期和遗留的 NXR ID，以及每项最终状态。

只有“双源不可变工件已验证 + Cloud 原子发布验收完成 + 至少一台目标 Mac 完成升级”后，
才可以把发布标记为完整成功。

完成上述条件后还必须更新 `docs/ai2apps-desktop-next-release.md`：把实际纳入项复制到本次
Build 回执并标记 `included`，保留 `deferred` 项，随后把滚动台账的生产基线推进到新
Build。未完成台账归档与重置的发布流程不算收尾完成。

## 15. Build 2246 已验证基线

Build 2246 是本流程已完整跑通的参考基线：

- GitHub：`https://github.com/Avdpro/ai2apps/releases/tag/v0.1.0-build2246`
- ModelScope immutable revision：`3406a22c47e112920a816725e4dc220d7e4b61e9`
- DMG size：`258870315` bytes
- DMG SHA-256：`403187ea060cc345d67cd8cd1c864c825818e21e6c5a1e376258565c1f5e8d6e`
- metadata SHA-256：`fee43a281f390826d30903dfedc6ceb820ff87acffe87b211f697f1c709e3056`
- Apple Submission ID：`e81e4ac4-bf94-47d5-9b7a-565b13b3a085`
- Cloud 最终 rollout：`build2246-test`，`10000` basis points
- Cloud 最终清单 digest：`31234bfc…6e29a`

后续发布不得复制这些版本、Build、revision、摘要或 Submission ID；它们只用于核对流程
形态和诊断回归。
