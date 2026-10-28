# Desktop Build 2265 Cloud 发布交接

## 当前状态

2026-10-28，AI2Apps 0.1.8 / Build 2265 已签名、公证并上传 GitHub 和 ModelScope。Cloud 清单尚未由本任务发布，请按既有审批流程先登记 0%，预检与回读通过后扩到 100%。本任务不读取 Dev Cookie，也不替换 Dev、App-Dev、Test 实例。

基线为生产 Build 2264，已观察到的清单摘要为 `1311e3da1851d30be987c75a4624092265a6d1dc46065c01bf91c1348316aa46`；发布前必须重新读取实际生产状态。若已出现其他更新或摘要变化，停止并协调，不覆盖未知版本。

## 发布材料

目录：`/Users/avdpropang/sdk/omlx-moe-cache/apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.8-build2265`。

- 0% 清单：`stable-zero.json`，文件 SHA-256 `478bdb7fcec8bcbb41024d84104b63f68b9043e76cc41078e09eac9259326cba`。
- 100% 清单：`stable.json`，文件 SHA-256 `6f186ddc4cf99744f9efaf33acd3373a4289acd30212407d40d77197659f7852`。
- DMG：`AI2Apps-0.1.8-build2265-macos-arm64.dmg`，267962905 bytes，SHA-256 `70cbab06d23c93c51c6a4674deb50adc6c0701e2b4666c8a13ac44168caf3a04`。
- 元数据：`AI2Apps-0.1.8-build2265-macos-arm64.release.json`，1011 bytes，SHA-256 `f1f014c9bf1d2957a273f116aaa54de47473489868c3cfc747a376b20834e79d`。
- Apple 公证：`aa7249e0-acf2-4b71-bc48-555e7be2b467`，Accepted；staple 和 Gatekeeper 验证通过。
- 源码提交：`aff206a09f21110f3ab1fba12a146b48331dc352`，已推送 `codex/release-2265`；GitHub 标签固定到该提交，不等同于已合并 main。

GitHub Release：[v0.1.8-build2265](https://github.com/Avdpro/ai2apps/releases/tag/v0.1.8-build2265)。沿用升级验证用 prerelease 标记，客户端清单发布不受此标记影响。

ModelScope 不可变根地址：`https://modelscope.cn/models/ai2apps/desktop-releases/resolve/9f39089c94b4febb862574d9130c35dc9237fc31`。
GitHub 不可变根地址：`https://github.com/Avdpro/ai2apps/releases/download/v0.1.8-build2265`。
分别拼接上述两个文件名；准确完整 URL 已写入两份清单。禁止使用 master、临时签名跳转 URL 或覆盖现有资产。

## Cloud 执行要求

本地匿名双源验收均通过：两源 DMG 和元数据完整下载、SHA-256、大小一致，Range 1024–2047 返回 206，Content-Range 为 `bytes 1024-2047/267962905` 且内容匹配。结果在制品目录的 `github-verification.json` 和 `modelscope-verification.json`；Cloud 仍须独立重做预检。

1. 使用现有发布 CLI 和操作人、审批人分离流程，校验 JSON Schema 与两源元数据。
2. 两源都执行匿名完整 DMG 下载、完整 SHA-256、字节数、Range 206 和 notarization 预检，不跳过任何门禁。
3. 原子发布 0% 清单，回读 GET、HEAD、ETag 条件请求和缓存头，保存规范化清单摘要与审计回执。本地 JSON 文件摘要不冒充 Cloud 规范化摘要。
4. 使用同一个 `build2265-test` 灰度 ID 扩至 10000 basis points。保留 `arm64`、`default` 实例、`cloud` Runtime profile、最低 macOS 13.0 和 `com.ai2apps.desktop` 匹配条件。
5. 返回最终生产清单、摘要、灰度比例、时间、双源预检及回滚摘要。若任何预检失败，保留 2264，不强制发布。
6. 发布后在测试 Mac 验收发现更新、下载、安装、启动和旧备份清理。临时升级验证不代替这一步。

## 本版内容和验证

Chat 默认模型、能力提示、布局、悬浮提示、麦克风样式与文件选择修复；会话级 App 审批规则（默认手动，schema 96）；内部情报候选去重、默认 Dock 顺序和无效开发 Package 隔离。独立 Package、模型 Runtime、iOS 和未验收实验不在本任务发布范围。

- Host：2665 passed，2 skipped；AaAT 权限边界：462 passed。
- 冻结快照专项：32 passed；Swift Testing 79 和 XCTest 2 passed；发布工作流隔离 17 passed。
- 前端主快照运行 1020 项通过；两个依赖外部 native/iOS 源码路径的测试文件初次路径失败，正确路径补跑 4 项通过。未把初次非零退出写成整套成功。
- 签名成品隔离 Local 冷启动 3.418 秒，schema 96、服务静态资源摘要与冻结源码一致。
- 临时副本实际 updater 完成 2264→2265 替换、签名校验和 pending marker 清理；最终公证候选资格验证 eligible。没有启动完整 Helper/UI 或宣称目标 Mac 升级已验收。
- App 716461146 bytes，比 2264 增加 43965 bytes，无模型 Runtime、权重或 pyc。
- GitHub 实际发布工作流：PyPI `40630246877` 和 Homebrew `40630246788` 均 completed/skipped，没有发布 Python 包或改动 Formula。既有 main/PR CI 红灯不是本次工作流通过的证明。

