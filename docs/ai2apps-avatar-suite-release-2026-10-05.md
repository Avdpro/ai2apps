# 数字人 Mini-App 0.1.3 发布回执

- 发布状态：published，2026-10-05T04:15:06Z；Repository Snapshot 248。
- Package：`ai2apps/avatar-studio-suite`，版本 `0.1.3`。
- Submission：`226303d1-fa6e-4e64-a9f7-414d32d26824`。
- Publisher：`229d6350-cd0e-408a-9905-41367385ae5c`；key：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`。
- SHA-256：`8b8bb7ba7abb699e1df93f8c916be830b35f55c3412a0702b4b8a1ba6f014d83`；大小：26423 bytes。
- 源码：`fa377dcb62875d5c82fc8177afd4277cd2357db9` 加当前未提交修改；精确制品摘要为发布字节身份。
- 制品：`packages/ai2apps-avatar-studio-suite/dist/0.1.3/ai2apps-avatar-studio-suite-0.1.3.ai2app`。

## 内容

九语言名称、描述与界面；音频槽文件名、时长与试听；Host 管理的录音入口；提交错误和时长校验。App 和 Mini-App 名称声明都包含九语言，中文名称为“照片说话”。没有新模型或 Runtime 载荷，仍通过通用数字人能力选择已安装模型。

## 验证

- 4 组 Node 前端验证、31 项 Python 回归通过。
- 最终精确签名包在独立临时实例安装并激活，保留九语言 Mini-App 声明。
- 发布后再次通过无 Cookie 的 Local Registry 信任链下载，验证 Snapshot 248、公钥信任、Publisher 签名、完整摘要与 envelope 一致；下载字节在另一个干净实例成功安装。
- 标准发布脚本 list-only 确认 published。使用本次授权的 Dev 在线 Cookie，未输出或导出秘密；本次授权现已结束。
- Cloud 拒绝可选顶层 miniApps 搜索投影，确认无 submission 后按手册使用 `--omit-mini-app-catalog` 重建。签名 app.yaml 声明完整；原未发布候选保存在 schema-rejected/。没有覆盖既有已发布版本。
- 小型 App Package 使用 Cloud 制品源；既有模型权重分发不变。

## 交付边界

Desktop 的录音桥接、Blob 音频 CSP 和工作室名称解析是独立 Host 更新，需要配套客户端支持；本次没有发布 Desktop。未在用户实例执行 Discover 升级验收，未实录麦克风，也未重复运行模型推理。临时实例安装使用静态审阅批准，没有修改用户实例审计策略。
