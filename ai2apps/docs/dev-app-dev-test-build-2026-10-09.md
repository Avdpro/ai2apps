# Dev / App-Dev / Test 构建回执（2026-10-09）

源码基线：`fa377dcb`，包含当前工作区未提交变更；不是生产发布。

| 环境 | 固定产物（仓库根相对路径） | 实例 | 启动端口 |
| --- | --- | --- | --- |
| Dev | apps/ai2apps-acefox/.build/AI2Apps-dev.app | dev | 61672 |
| App-Dev | apps/ai2apps-acefox/.build/AI2Apps-app-dev.app | app-dev | 62335 |
| Test | apps/ai2apps-acefox/.build/AI2Apps-test.app | test | 62800 |

依次运行原有 build-dev-app.sh、build-app-dev-environment.sh、build-test-app.sh。三者构建成功，严格 codesign 验证通过；App-Dev/Test 的标准构建同时通过 verify-release-app.sh 和固定图标/实例检查。

Dev/App-Dev 保留 Development 与可信源码路径；App-Dev 嵌入 cloud Runtime，无生产更新地址。Test 为 cloud Runtime、非 Development、无源码热挂载。三个实例均实际启动到首页。App-Dev 原生标题为 `AI2Apps-App-Dev: App-Dev 127.0.0.1:62335`；Test 保留原有脱机状态，没有代用户登录。

Test 首次构建因旧 AceFox 打包快照缺少 bind 分支而中止。兼容补丁修改被自动审批拒绝，未执行。改用 AceFox 现有 `./mach build faster` 与 `./mach package` 正常刷新完整快照，再运行未修改的 Test 构建脚本，成功通过。没有跳过或削弱安全检查。

旧固定 App 分别归档为 AI2Apps-dev-20261009-034821.app、AI2Apps-app-dev-20261009-034941.app、AI2Apps-test-20261009-035530.app。实例数据、Cookie、Package 和缓存未复制、合并或重置。

构建日志：/tmp/visitor-rebuild-dev.log、/tmp/visitor-rebuild-app-dev.log、/tmp/visitor-rebuild-test.log；浏览器快照日志：/tmp/visitor-acefox-refresh.log、/tmp/visitor-acefox-package.log。

本次仅本机构建与启动验证。访客空间 Cloud 通道、真实跨端验收及 Package 发布仍按各自交接文档推进，不因构建完成视为上线。
