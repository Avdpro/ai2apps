# 频道通知客户端合同 1.2.0

Cloud 对接依据：`/Users/avdpropang/sdk/ai2apps-cloud/docs/intelligence-notifications-client-handoff-v1.md`。

Local 在当前 Owner 身份下获取 producer-policy，核对身份/epoch、enabled 和精确 event_capabilities；首次入队前将频道名、真实已保存新增文章数、最新两条标题、终态与运行/系统任务引用冻结在业务 run。只查询本轮新增文章，不扫描整个频道。无能力时冻结旧 Task 格式，不试发未知字段。已有 outbox 原样重试，崩溃窗口按 event_id 对账，不改写为新模板；无新增、取消、其它 Owner 和已通知历史不补发。不得上传正文或 URL。

iOS Build 3 支持新 kind、冻结多语言通知箱文案与预览选择：通用提示、频道与数量、文章标题。修改设置前重新 GET preferences，使用服务器 ETag + If-Match，只改变指定字段，保留 enabled/kinds/devices 及已有预览模式。冲突重新加载并提示重新选择，不自动覆盖。

点击频道先重新鉴权读取当前通知 detail，仅接受 intelligence.updated / intelligence_channel / ai2apps.intelligence，再核对当前 HTTPS Desktop host 与 source_device_id。通过现有 Mobile 会话查询可见频道；未连接、未授权、频道删除均报错，不自动跨设备/账户回退。固定 Mobile App 路由承载 opaque channel id，App 在已授权快照中选择该频道；目标不存在时留在频道列表。页面请求有 10 秒有限超时。当前不自动连接另一台 Desktop。

## 验证与未完成验收

- Python：32 项情报桥接与生产者测试通过，包含冻结快照后编辑标题/频道名、重试、旧 outbox 对账、能力精确匹配/过期、Owner 隔离和旧格式兼容。
- Swift 通知协议和 API 测试通过：新 kind/展示解析、静音及设备偏好保留、现有 OAuth/PKCE/令牌轮转/退出处理。
- iOS Simulator 与 iPhoneOS Debug 构建通过；签名校验通过。开发版 com.ai2apps.ios.dev Build 3 覆盖安装到既有 iPhone 15 Pro，未卸载或清理数据。
- Dev/App-Dev 经各自 Helper 在队列空闲时重载，健康 200；实际 NotificationProducer 导入路径指向当前 checkout，路由静态资源逐字节匹配当前源码。
- 用户选择“频道与数量”；本次没有自动修改账户隐私偏好，需要在手机通知设置选中。真实 received/opened/read、锁屏显示与频道成功跳转仍待真机验收，构建/模拟测试/Cloud 202 均不能替代这些证据。本次未发送人工测试推送。
