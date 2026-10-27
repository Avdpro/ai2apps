# 自定义通知客户端接入 1.3.0

日期：2026-10-16。依据 Cloud `custom-notifications-client-handoff-v1.md` 与通知合同 1.3.0。本次只改 Local/iOS，不修改 Cloud。旧 intelligence.updated 等事件不改为 custom，不自动补发历史通知，也不更改预览偏好。

## 发送入口与权限

受信任 Python App 服务先获取 `runtime.remote.notifications` 的 producer-policy（`await refresh_policy(force=True)`），再在工作线程调用：

```python
from ai2apps.remote.notification_host import NotificationHost

NotificationHost(runtime).send_for_instance(principal, app_instance_id, {
    "event_id": "stable-business-event-id",
    "content": {"title": "任务完成", "body": "这是业务自由编写的正文。", "locale": "zh-CN"},
    "target": {"type": "https_url", "app_id": "example.app", "url": "https://example.com/news"},
    "group_key": "updates"
})
```

App manifest 需要 `notifications: {"send": true}`。真实调用 App 从宿主数据库中的 App instance 解析，不从 JSON 接受 caller/source App ID。App 必须注册、启用且当前主体可访问；仅当前 Installation Owner 可发送。成员不能借 Owner 的设备发送私有通知。

Studio / AI Browser 的 Package Mini-App 需在当前已安装声明的 requirements.capabilities 中显式声明 `notifications.send`。使用现有宿主 MessageChannel，不获得 Cookie / Device credential：

```javascript
await AI2AppsNotifications.send({
  event_id: 'stable-business-event-id',
  content: {title: '任务完成', body: '自由正文，可含段落与 emoji。'},
  target: {type: 'https_url', app_id: 'example.app', url: 'https://example.com/news'}
});
```

`AI2AppsNotifications` 与现有 `web_agent_mini_app_sdk.js` 共用一个宿主连接及串行请求队列，不要再建立第二个竞争的 MessageChannel。宿主使用自身 binding 中的 studioId/mountId 转发到 `POST /v1/platform/studios/{studio}/mini-app-mounts/{mount}/notifications`；服务端重新校验实际 mount、当前 Package digest 和声明能力。Mini-App 不能自行指定调用者身份。已有媒体 Mini-App 也可通过其同一 hostRequest 通道使用 `notifications.send`，payload 为 notification。

默认只能指向真实调用 App。合法跨 App 目标必须在来源 manifest / Mini-App 声明的 `notifications.targets` 中列出，且目标 App 注册、可访问、路由已注册、资源 ACL 校验通过。宿主原子写入 outbox 和 `notification.custom.enqueued` 本地审计事件，记录真实来源 App/Mini-App、目标 App 和 Owner，不记录正文/URL；重用其它调用者的 event_id 被拒绝。低层 `NotificationProducer.enqueue_custom` 只供受信任宿主内部使用，不能直接暴露给未校验的 App 请求。

## 内容、能力和幂等

本地按 1.3.0 约束规范化纯文本、段落、emoji、引用和 HTTPS 地址，保留字面尖括号；限制标题 160、正文 4000 code points、实际 UTF-8 请求 32768 字节。Locale 先做 BCP47 语法校验，最终规范化由 Cloud 完成。HTTPS 不包含凭据/敏感参数，不指向 Device origin 或受保护 Cloud API。不抓取或预览 URL。

新事件首次入队要求当前有效身份、enabled、精确 kind/版本/隐私策略/可信宿主能力、所需 target 类型及足够的 limits。内容/目标/元数据冻结进现有 outbox，已有事件不受后续能力发现变化影响，不同内容重用同 ID 报冲突，超时重试原字节载荷。Cloud 统一处理预览、静音、投递分组和实际 push_snapshots；custom 在 channel_only 下仍是系统通用锁屏提示。

## App 路由注册与点击

`runtime.notification_routes` 是宿主只读资源路由注册表，通过 `routes(runtime)` 取得。已内置情报频道 `channel` 和文章 `article`；其它 App 必须注册自身资源 ACL 处理器，不能把任意 route 当 URL 或命令执行：

```python
from ai2apps.remote.notification_host import routes

def authorize_detail(principal, resource_id):
    repository.require_visible(principal, resource_id)  # App 自己实现真实 ACL
    return {"notification-route": "detail", "notification-resource": resource_id}

routes(runtime).register("example.app", "detail", authorize_detail)
```

处理器只能返回该 App 的参数，不能覆盖 app / notification-id。App 的页面通过已授权宿主入口加载，渲染并确认目标资源后再完成 SDK 回调：

```javascript
AI2AppsNotifications.onRoute(async ({route, id}) => {
  if (route !== 'detail') throw new Error('Unsupported route');
  await loadAndDisplayAuthorizedDetail(id);
});
```

成功回调表示资源已实际展示，不得在仅收到参数时就成功返回。未注册路由、资源删除或无权限均拒绝，不能回退到其它资源。

iOS 先重新鉴权读取当前账户的 Cloud detail。App 内目标通过当前 Mobile 会话调用 `POST /v1/platform/notifications/resolve-target`；Local 再次校验 Owner、App 和资源，并返回自身绑定的 source_device_id。Native 与通知来源匹配后才导航。公开域名的 slug 不能用 Device ID 拼接推导；本次同时修复了 1.2.0 频道入口的此问题。

Mobile 仅接受当前活动 iframe、对应 mount token 和 notification-id 的 opened/failed 确认。Native 最多等待 20 秒业务页面确认；失败或超时不标记已读。内置频道/文章执行相同流程。自定义 HTTPS 目标在重新获取 Cloud detail 且再次校验 URL 后交系统浏览器，不转交 Native token/Local Cookie。未知目标提示不可用，不跨账户或 Desktop 回退。

## iOS 展示与验收边界

开发 Build 4 解析 app.custom、URL-only target 和完整纯文本内容，不解析 HTML/Markdown。通知详情只按当前 binding_id 选择实际推送快照，不取数组末项；Apple 200 仅显示“已接受”，不冒充 received。前台横幅沿用系统 APS，不用完整 content 改写 generic/channel_only 文案。自定义通知与频道通知只有在业务页确认打开后才进入 opened/read；查看通知详情不直接确认这些目标已打开。

验证：112 项 Python 通知/Owner 手机网关/宿主回归通过；22 项 JavaScript SDK、路由确认及卡片/分页回归通过；Swift 通知协议与账户 API 测试通过；iPhoneOS / Simulator Debug 构建和签名校验通过，Build 4 已覆盖安装到既有 iPhone 15 Pro。

手机网关仅显式导出 resolve-target 与 mount-bound notifications 两个 POST 入口，保留原有 Owner lease、Origin、App Mobile 开关与资源权限；没有导出不带真实 App 上下文的通用发送 HTTP 入口。

验证结果在发布台账中记录。模拟器/真机构建、协议测试、Local API 测试与 Cloud 202 不替代真实 iPhone 的锁屏 received/opened/read 验收。本次不自动修改用户隐私模式，不发送人工测试推送。其它 App 注册业务路由与发送权限后才能使用自定义通知。
