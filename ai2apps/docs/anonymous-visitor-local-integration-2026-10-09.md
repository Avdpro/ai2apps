# 匿名访客 Local 接入记录

状态：代码与自动化验证完成；未启用就绪标志、未重启实例，未完成真实匿名/iPhone 验收。

依据 Cloud 生产合同 personal-space-anonymous-v1，实现：
- 匿名完成页读取并清除 fragment，经现有 Local POST space/exchange 携带明确 protocol 兑换到 Cloud visitor/exchange。浏览器不接触 Device credential。
- 独立 Ed25519 JWT 校验，精确 issuer/audience/protocol/scope/mode、UUID 匿名身份、设备/Owner/安装身份、access/mapping/capability/space/published 代次、固定 120 秒 TTL；拒绝账户 session epoch 及额外字段。
- 单次断言关联 opaque Secure HttpOnly SameSite=Strict space Cookie，绝不生成 Local principal。资源与 bootstrap 保持访问边界。
- 发布/关闭先推进本地持久状态和撤销会话，再同步 capability；逐次拒绝旧发布版本、关闭状态及安装变更。
- 声明就绪仍由 AI2APPS_VISITOR_APP_GATEWAY_READY 控制，持久代次映射为本地值 + 1，不改存量数据。Cloud mapping revision 来自公开 resolver，capability revision 来自 Device 声明响应。
- 开启前明确告知“任何持有链接的人都可免登录访问已发布内容”。

验证：68 项 Python（含既有 v1、Owner Gateway、匿名签名/绑定/重放/发布/关闭）和 6 项 Node 通过；scoped diff 检查通过。测试使用隔离数据，不发布用户内容。

阻塞：Cloud 的 publishedAppCount=0 => unpublished 判定阻止纯文字/链接空间；详见 cloud-anonymous-text-space-fix-2026-10-09.md。不能通过伪造 App 数量规避。

后续：Cloud 修正并冻结发布状态字段后补齐声明，按标准 App-Dev Helper 重启、启用指定实例的就绪标志，再完成真实公开内容访问、跨设备/Owner 拒绝、过期/撤销及 opaque sandbox Cookie 的 Chrome/iPhone Safari 实测。自动化通过不代表 Safari Cookie 通过。旧 Dev/App-Dev/Test 构建不等于本轮 Python 已加载。

## 纯文字生产协议接入与真实验证（2026-10-09）

上述文字空间阻塞已被 Cloud 1.64.1 修复。本地声明增加 published = (published snapshot is not None)，App 数量仍只统计真实且未隐藏的 App 卡片。新测试覆盖零 App 发布和未发布状态。

Dev 单实例 config/visitor-space-gateway.json 已设为 enabled=true / personal-space-anonymous-v1，环境变量仍有最高优先级且可显式关闭。未改变用户访客开关或发布内容。通过原有 HelperControlClient.restart_local 重启 Dev Local，PID 73190、端口 55625；App-Dev/Test 未重启或改配置。

真实内置浏览器从固定 /u/ 入口无需登录进入 /mobile/space/home，展示“Avdpro 的数字城堡”和现有文字卡片。独立 httpx 客户端从空 Cookie 状态验证：handoff 201；无 Cookie bootstrap 401；匿名 exchange 200；bootstrap mode=anonymous/revision=2；同码重放 401；mobile apps 与 Owner status 403；平台管理和 /admin 404。未打印/保存交接秘密、JWT、Cookie。

验证：69 项 Python 协议/空间/Owner 回归通过；新增就绪配置测试后 visitor-space 16 项通过；diff 检查通过。此前 6 项 Node 通过，本轮未修改前端脚本。

未完成：iPhone Safari、Chrome opaque sandbox App Cookie、真实关闭/重开和过期完整矩阵。当前只证明公开文字空间匿名链路正常，访客会话仍为合同约定的最长 120 秒，无自动续租。Test 现有 Bundle 不含本轮 Python 变更。

## 续租协议已接入
后续已接入 personal-space-anonymous-session-v1，Dev 真实浏览器持续10分27秒、同会话10次续租通过。新入口会话最长8小时、闲置30分钟；旧v1 Cookie不升级。详见 anonymous-visitor-session-local-2026-10-09.md。
