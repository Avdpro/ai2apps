# Desktop 0.1.1 发布准备（未发布）

状态：范围核对与源码回归进行中。用户选择先整理全部当前产品改动、验证并提交后再发布。
候选版本暂定 0.1.1 / Build 2253，尚未保留 tag 或创建制品；最终分配前须重新查询生产版本与远端 tag。

## 已确认事实

- 生产基线是 0.1.0 / Build 2252，不是滚动台账历史段落中残留的 2249。
- 当前工作分支 experiment/moe-cache；主分支已包含之前提交的测试系统功能，但不包含当前未提交产品修改。
- 工作树约 196 项修改/未跟踪入口，已跟踪 diff 约 12,041 行新增、979 行删除。此统计是检查时快照，不是最终候选清单。
- 个人参考音频 `ai2apps-test-system/assets/voice-1.wav` 明确排除。
- 本轮未构建、公证或上传任何正式制品，未修改 Cloud 或生产更新清单。

## 已执行门禁

- `swift test --package-path apps/ai2apps-acefox`：77 项 Swift Testing 加 2 项 NativeUILanguage XCTest 全部通过。日志 `/private/tmp/ai2apps-2253-swift.log`。
- `node --test tests/*.cjs`：16 个测试文件通过；日志 `/private/tmp/ai2apps-2253-node-final.log`。
- 首次定向 Python：365 passed / 1 failed。共享 Studio 客户端静态断言落后于已有接口（可选 installMore）及资源版本；本轮只更新测试合同，未修改产品行为。
- 新增 Node 行为断言验证普通 setup 向 ACPF 传 false，显式 installMore 传 true；执行通过。静态客户端测试复验 3 passed。
- 首次完整 Python 回归（默认排除 slow/integration）：10227 passed、4 failed、67 skipped、74 deselected。日志 `/private/tmp/ai2apps-2253-full.log`，JUnit `/private/tmp/ai2apps-2253-full.xml`。失败分别为 ACPF 缺少 34 条翻译、Runtime 测试固定旧 1.7.9 版本、重置菜单测试未适配双语 L()、Studio 客户端旧接口断言。
- 已补齐 ACPF 中英文翻译，更新三处过期测试合同；124 项定向复验通过。全量复验完成：10231 passed、67 skipped、74 deselected，727.61 秒，无失败。日志 `/private/tmp/ai2apps-2253-full-final.log`、JUnit `/private/tmp/ai2apps-2253-full-final.xml`。该轮在产品版本源升为 0.1.1 之前运行；版本调整另行定向验证。
- Developer ID Application: Avdpro Pang (84XL5V265N) 可用；ai2apps-notary 只读历史查询成功；GitHub 当前身份 Avdpro。没有输出或导出凭据，也未提交公证。
- 修复后定向回归 366 passed；日志 `/private/tmp/ai2apps-2253-focused-final.log`，JUnit `/private/tmp/ai2apps-2253-focused-final.xml`。
- `git diff --check` 通过。

## 尚未关闭的发布门禁

2026-09-26 用户确认：“修改密码和 Imagine 新功能我都验证过了，不用你再验证了。”
下列第 2、3 项按用户人工验收关闭，纳入候选范围，不重复执行真实改密或付费生成。
这是用户确认的验收，不是本轮 Agent 执行的 UI 测试；其余源码、打包与发布门禁保持不变。

1. 滚动台账已完整读取，逐项纳入/延期核对仍须完成，不能以本文代替。
2. 修改密码人工验收已由用户确认完成；不重复操作，不读取或处理密码。
3. Imagine 新功能人工验收已由用户确认完成；不重复执行付费生成。该确认不扩展为其他音视频功能或正式制品升级验收。
4. 正式 packaged AceFox 两个 omni.ja 存在，但 shell.mjs 与 shell.xhtml 都不等于当前源码。必须走正式浏览器构建/打包；禁止以 Development overlay 代替。
   - 浏览器源码 HEAD：06e98acfcb1e853da0783ab3c5591e2f7dc91e62，工作树另有未提交 AI2Apps 补丁，最终来源须单独记录。
   - 当前包 shell.mjs SHA-256：f5bc972004e390bb676224b10001a0f2bac55c144f75600ada1ff059153b290f。
   - 当前包 shell.xhtml SHA-256：83d835c024815e4b6516d2b45dc2ea2f1fc4804905ce5dd2918cc96b05481fcb。
   - 后续已完成 `mach build faster` 和 `mach package`，未使用 Development overlay、未替换运行中 App。两份打包资源与源码逐字节一致：shell.mjs SHA-256 `6ae8a56bb76bb4baf28da0ee091516ad82cf96e65a854ffae3c4605ad7fb2e4f`；shell.xhtml SHA-256 `27530945a44d1b921a6b7c2587e4c7925184f00109a44271d772ae71f658b56a`。关闭这两份资源陈旧问题，不代表整份浏览器来源冻结、签名或正式 Desktop 制品验收完成。
5. 全量源码检查、回归、提交/推送及 clean 候选 checkout；上一版最终 DMG 与候选内嵌内容比较。
6. Developer ID、Apple 公证、双源完整回读、Cloud 受保护发布交接及目标 Mac 实际升级均未执行。

不得将已有开发 App 验证、独立 Runtime/Package 已发布或历史 UI Run 当作此正式候选通过证据。

## 本轮范围决策

- 2251 台账已明确纳入的历史 NXR 集合与 2252 增量 Checkpoint 修正保留为基线，不重复作为 0.1.1 新功能，也不将历史升级验收欠项改为本轮已验证。
- 2026-09-22 至 26 的 Voice/Characters/Audiobook/Quick Read、共享输出、字幕/视频翻译 Host、Composer、Discover、Checkpoint 下载及 Imagine 条目拟纳入。对应源码为 `ai2apps/api/`、`readaloud/`、`studio/`、`video/`、`web/`、provisioning profiles、checkpoint 模块及 `omlx/settings.py`；测试由本轮完整 Python、Node 回归覆盖。Release notes 只描述实现能力，不宣称所有模型已逐一完成主观音频质量或现场推理验证。
- Schema 72–77 为增量字段/索引迁移，覆盖项目归属、角色素材、软删除、合并结果、角色定位与 ASR 设置。版本调整后的产品/更新脚本/存储迁移定向回归 36 passed。不得以回滚代码代替数据库降级；出现问题先暂停新 Build，再发布修复 Build，保留用户数据。
- 修改密码及 Imagine Product/Sticker/Portrait/Extract Items/Try On 的人工验收按用户 2026-09-26 确认关闭；不重做付费生成。
- Native/登录双语条目已由用户在 2026-09-26 进一步确认现场验收通过，纳入候选；不将用户验收记作 Agent 操作。Shell 名称与 Dock Helper 冷启动采用台账中三实例实际验证记录作为既有开发证据，正式候选仍须检查包体身份。
- App-Dev Test Center、Dev/Test 构建及 Harness 为开发工具，不作为生产可见功能；正式包不得启用 Development source mount、测试入口或测试重置能力。
- Runtime 1.7.9–1.7.12、Detailed Transcription 0.1.3/0.1.4、Media Voice Suite 0.1.2/0.2.0 已独立发布。只纳入 Desktop Host 兼容代码；本轮不重发、不覆盖它们的不可变制品。旧 language-normalization 未完成的媒体推理验证不扩大为 Desktop 已验证结论。
- 保持 2251 已记录的研究/延期边界：DSV4.1 L1/L2、miss/resume、ICB 实验不启用；Ideogram JSON 后续 Package、Work complexity 完整 E2E、aria Inspector、旧 Video/Read Aloud 未完成阶段不声明新增交付。保留历史条目，不删除证据或改为 included。
- 正式候选构建后须对照 2252 最终 DMG 内容，核对以上归类；不一致时停止公证。回退发布策略保持生产 2252 清单不变，直到 2253 双源及受保护 Cloud 验收完成。
