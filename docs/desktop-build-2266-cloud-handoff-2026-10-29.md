# Desktop Build 2266 Cloud 发布交接

## 状态

已完成签名、公证、双源上传及匿名完整校验，材料可交Cloud按以下流程发布。Cloud清单尚未发布，目标Mac升级尚待验收。

版本为 AI2Apps 0.1.8 / Build 2266，源码提交 `55f85f062697779c787f70dca8e460962a848f30`，分支 `codex/release-2266`。生产基线为2265；发布前重新读取生产清单，如已存在更新版本则停止协调，不能覆盖未知状态。

制品目录：`/Users/avdpropang/sdk/omlx-moe-cache/apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.8-build2266`。

本任务不读取 Dev Cookie，不替换固定 Dev/App-Dev/Test，不发布独立 Package、Runtime 或 iOS，也不直接修改 Cloud 清单。

本次发布前匿名回读2265/10000bp，响应原始文件SHA-256为`601df28a6421b169d0698083ea9812c24dcac1ee5a3e2c3e63368fb54ea69ec4`。这是原始文件摘要，不冒充Cloud规范化发布摘要；Cloud需重新获取当前规范化摘要并核对。

## 发布材料

- `stable-zero.json`：SHA-256 `6a4c38179d6669e4f4f6112c154bc8328b962d3a551bcf6b85037efc02569e54`。
- `stable.json`：SHA-256 `233df17ca8a4b271d9a9134619a9ce837d3ea5cfab5b6e58331ef02bea4dc11f`。
- `AI2Apps-0.1.8-build2266-macos-arm64.dmg`：268270717 bytes，SHA-256 `769b2c5d1f97b49fcd98de25474ac0ae494f91bcd5565f51385032913d18bfed`。
- `AI2Apps-0.1.8-build2266-macos-arm64.release.json`：1011 bytes，SHA-256 `d135805535df551c06e3b80727a1e711391ce5a42e925a0bd17fc92040621e3d`。
- Apple公证：`572222b7-99d3-423a-8885-7dbab6b1483c`，Accepted；staple及Gatekeeper验证通过。
- GitHub：[v0.1.8-build2266](https://github.com/Avdpro/ai2apps/releases/tag/v0.1.8-build2266)，沿用prerelease标记，不影响Cloud清单升级资格。
- GitHub不可变根地址：`https://github.com/Avdpro/ai2apps/releases/download/v0.1.8-build2266`。
- ModelScope不可变根地址：`https://modelscope.cn/models/ai2apps/desktop-releases/resolve/bd5c828cd77ec74231e80436faf4e326c44e5c9b`。

两根地址分别拼接上述DMG/元数据文件名；完整准确URL已写入清单，禁止使用master或临时跳转签名URL。

## Cloud 执行要求

1. 材料全部就绪后，使用现有发布 CLI、操作人/审批人分离及审计流程，校验 Schema。
2. 匿名验证两源完整 DMG/元数据下载、SHA-256、大小、Range 206 和公证信息；不得跳过门禁。
3. 先原子登记 `stable-zero.json` 的0%，回读 GET/HEAD/ETag/缓存头并记录规范化摘要。
4. 验收后用同一灰度 ID `build2266-test` 扩到10000 basis points。保持 com.ai2apps.desktop/default/arm64/cloud、最低macOS13.0和Build递增约束。
5. 返回最终清单、规范化摘要、灰度比例、审计回执及回滚摘要。失败则保留旧版本，不强制发布。
6. 测试Mac实际完成发现、下载、安装、启动、旧备份清理；本地临时副本验证不代替目标Mac验收。

## 本版范围

- Agent工具目录按需加载、多轮上下文恢复、当前请求路由、精确参数合同与配置面板定位。
- Package AaAT归属和生命周期隔离；Discover投影、过滤、分页及安装接续展示。
- Chat持久音频/视频/文档卡片和Mobile访问支持；修正Mobile资源白名单遗漏。
- Todo目录创建、精确模型路由视觉能力声明。
- SearchAll/WebReader改为内置AI Browser Mini-App，默认快速搜索，保持确认与权限守卫。

Cloud对应旧SearchAll/WebReader Package的下架另按 `ai2apps/docs/builtin-browser-package-retirement-20261029.md` 独立处理；本次Desktop不代替该操作，也不得远程卸载用户现有Package。

## 已知边界

钥匙串重复授权没有在本版修改或宣称修复；仍需正式身份的全新安装、登录、重启、升级实机验收。模型/网站捕获及自然短指令路由的剩余限制保留原台账，不宣称全面解决或普适效率提升。

## 验证回执

- Host完整重跑：2776 passed/2 skipped；此前8项失败已经修复，未把初次失败写成成功。
- AaAT权限边界：657 passed；前端1031 passed；Swift Testing79与XCTest2 passed。
- 冻结候选手机、身份与工作流专项：46 passed。
- 成品隔离Local冷启动3.167秒，schema96和服务资源校验通过；源码匹配冻结候选。
- 临时副本2265→2266 updater替换、签名和pending marker清理通过；最终公证候选eligible。未宣称目标Mac或完整Helper/UI验收。
- App717311728 bytes，比2265增加850582 bytes；无模型Runtime、权重或pyc。
- GitHub实际工作流：PyPI `40860305176`、Homebrew `40860305175` 均completed/skipped，未发布PyPI或改动Formula。
- GitHub匿名完整DMG/元数据SHA和大小校验通过，Range1024–2047返回206及精确Content-Range/内容。
- ModelScope不可变提交同样通过匿名完整DMG/元数据SHA和大小校验，Range1024–2047返回206，Content-Range为`bytes 1024-2047/268270717`且内容相符。两源回执保存在制品目录的`github-verification.json`、`modelscope-verification.json`。Cloud仍须独立预检。
