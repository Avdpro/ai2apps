# 访客空间本地 MVP 验收记录

## 已实现
- 内置 ai2apps.visitor-space（系统分类）；Account → 远程访问 → 管理访客空间。
- 本机 Core/Owner 管理接口；远程 Owner 会话、普通成员不能管理。
- 安装绑定的默认关闭设置、草稿、发布快照、乐观版本锁、撤销代次（schema 86）。
- 名称、简介、主题、文字/HTTPS 链接/App 卡片、排序、隐藏、移除、保存与发布。
- 手机/桌面同渲染器预览，预览不执行 App/链接；固定账户 URL 和二维码。
- 访客 bootstrap 只返回发布内容；关闭撤销、重开不恢复旧凭证；到期/关闭后清空页面和游戏 frame。
- Open-Entry 清单验证，发布锁定 App 摘要；资源请求验证访客会话、设备、发布版本、启用状态、目录、文件索引及摘要；零权限 sandbox。

## 验证
- 55 项 Python：访客数据/管理 API/清单/资源路由/CSP/会话、现有 Owner Gateway 与 Mobile policy 回归通过。
- 2 项 Node：共享预览、文本安全、隐藏、禁用 App 执行及 URL 过滤通过。
- 固定 App-Dev 通过标准脚本重建，旧 App 归档；release verifier 与 codesign --verify --deep --strict 通过。身份 app-dev、Development、cloud Runtime、可信源码根及无生产更新 URL 保持。
- 活跃窗口验证：AI2Apps-App-Dev: App-Dev 127.0.0.1:55388。
- App-Dev 实机打开管理 App，编辑简介/文字卡片，保存草稿，预览联动成功。保留标明“功能验收草稿”的测试内容；空间关闭、发布版本 0。未在公网发布该草稿。

## 未完成的外部依赖/实机验收
- Cloud 新资源路径与访客长会话尚未部署；客户端资源通道默认未开启。现有访问断言仍最多 120 秒。
- 贪吃蛇 1.0.1 仅声明 Mobile Entry，不能自动作为访客 App。已在原始工程准备 1.0.2 Open-Entry 候选并通过清单校验与 3 项握手测试，尚未签名发布；本次未复用已结束的 1.0.1 Cookie 授权。
- 非 Owner 账号、真实签名 Open-Entry、iPhone Safari 的公网端到端验收待 Cloud 部署后完成。
- 本次只刷新独立 App-Dev；公网 Dev 尚未为新内置 App 重启，未发布 Desktop。

详见开发计划、Cloud 交接和 Open-Entry v1 合同。
