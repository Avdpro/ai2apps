# Package App / Mini-App 的 Event Hook 用户授权 v1

2026-11-02。实现承接 [统一 Event/Hook 设计](platform-events-and-bot-hooks-v1.md)。安装 Package 不创建 Hook，也不授予事件、详情或后台执行权限。

## 用户流程与授权边界

1. 已验证安装的 Package 在签名 `app.yaml` 中声明可申请的权限上限。
2. App 通过 Shell bridge，Mini-App 通过 Studio MessageChannel 提出订阅申请。宿主从真实 App 实例或 mount 解析调用者身份；不接受 Package 自报另一个 App、Bot、Mini-App 或 Installation。
3. 宿主展示 Package 名称、发布者、版本、事件、资源范围、筛选条件、详情读取、后台运行、固定动作参数及有效期。点击“同意并启用”才在同一事务创建授权和 Hook。关闭窗口保留待处理申请；拒绝不创建规则。
4. 后续相同范围的事件复用授权，无须逐次确认。可以在 Settings → Event/Hook（设置 → 事件/响应）统一管理待处理申请、查看范围、暂停、恢复或撤销。System Control 保留快速授权管理入口。

每个 grant 绑定 actor、Installation、已安装 Package、App 实例，以及可选的 Studio/Mini-App 身份。App 与 Mini-App 分别授权。订阅范围、详情接口、动作参数、处理器及有效期均冻结并计算摘要。修改通用 Hook 规则不能借用原授权扩大权限。

四项权限分别申请：

| 权限 | 效果 |
| --- | --- |
| 接收事件 | 只接收授权范围内、启用之后发生的标准事实摘要 |
| 读取详情 | 对已经投递的 event_id 使用目录中冻结的 AaAT Provider/version；不授予任意查询或其他 Tool |
| 后台运行 | Local 运行时，即使 Package 页面关闭也由固定宿主处理器处理；Local 退出后暂不运行 |
| 固定动作 | 仅执行用户审阅的已注册动作、版本和参数；不接受 Package 脚本、命令、URL 或任意 Tool 工作流 |

有效期默认一天，最长七天，最低一分钟；申请预览最多保留十分钟，到期必须重新申请。恢复暂停规则会跳过暂停期间积压，不会补执行旧事件。撤销立即阻止后续读取、受理与动作，已完成的动作保留回执。

Package 首版后台处理器只有宿主拥有的 `event-inbox/v1`。它可以读取批准的详情、保存报告，并执行明确批准的已有固定动作；当前动作目录为 Todo 创建和本机站内通知。Package 可使用其声明的子集。Package JavaScript 仅在页面打开时消费 inbox，不作为后台执行入口。

## 签名声明

App 顶层以及每个 Mini-App 可分别声明：

```yaml
event_hooks:
  schema: ai2apps.package-event-hooks/v1
  handler: event-inbox/v1
  event_types:
    - intelligence.channel.refresh_finished
  scopes: [subjects]
  background: true
  details: true
  actions: [notification.local]
```

`event_types` 必须明确列举，拒绝通配符。`owned_collection` 还需要事件 owner 本身支持并授权该范围，覆盖当前及未来属于用户的同类资源。Mini-App 还必须在已有 `requirements.capabilities` 声明 `events.subscribe`，申请后台时声明 `events.background`。这些字段不产生任何用户授权。

签名归档安装和 Registry `app.yaml` 检查都校验声明。现有 Package 未声明时不能申请；源挂载且没有可验证安装来源的开发 Package 不以“开发模式”绕过验证。Legacy `studio.mini-app.event-inbox` 对已安装 Package 关闭，旧规则不能绕过新授权。内置开发消费者保留原来的受控入口。

## SDK 与宿主接口

Sandbox App 将平台提供的 `web/static/js/package_events.js` 随 Package 一起签名打包，例如保存为 `ui/package_events.js` 并使用 `<script src="package_events.js"></script>` 相对引用。生产 sandbox 不从宿主绝对 URL 动态加载 SDK；继续使用既有的签名资源验证与内联机制。SDK 使用当前 Shell URL 中已有的实例/mount 绑定：

```javascript
const events = AI2AppsPackageEvents.client();
const decision = await events.request({
  request_id: crypto.randomUUID(), // 同一次申请的重试保留原 ID
  event_type: 'intelligence.channel.refresh_finished',
  scope: 'subjects',
  subjects: [channelId],
  filters: [{field: 'status', op: 'eq', value: 'completed'}],
  background: true,
  read_details: true,
  actions: [{registration: 'notification.local', arguments: {
    title: '频道更新', include_review: true
  }}],
  expires_in: 86400
});
// pending 表示等待用户处理，不代表失败，也不代表已经获权。
const stop = events.watch(async delivery => {
  // 按 delivery_id 幂等处理，消费成功后 SDK 才 ack。
  render(delivery.event, delivery.result);
});
// 页面销毁时：stop(); events.close();
```

App 的 `request/list/details/ack/watch` 只通过父 Shell 交互，不拿 Cookie 或预览 token。异步回复绑定发起时的 frame、instance 和 mount；切换 App 后不会把结果发给新的 frame。

Mini-App 的已有 RPC 增加/沿用 `events.subscribe/list/details/ack/watch`。`events.subscribe` 的 proposal 与上面相同。`events.details` 需要 `{deliveryId}`，由实际 mount 绑定调用。`AI2AppsMiniAppEvents.watch(port, rpc, consume, {signal})` 在消费成功后确认。每次挂载重新校验当前 Package 来源。升级后的新 mount 可以读取同一兼容身份下未确认的投递。

宿主 API 前缀为 `/v1/platform/package-hooks`：

| 接口 | 用途 |
| --- | --- |
| `POST apps/{instance}/requests` | 当前 App 的申请 |
| `POST mini-apps/{studio}/{mount}/requests` | 实际挂载 Mini-App 的申请 |
| `GET .../inbox` | 当前身份的未确认投递 |
| `POST .../deliveries/{delivery}/{details,ack}` | 有授权的详情读取、消费确认 |
| `GET requests`, `GET requests/{id}` | 宿主审阅申请 |
| `POST requests/{id}/{approve,deny}` | 同源桌面宿主作出决定，绑定 review_hash 和幂等请求 ID |
| `GET grants` | 当前用户授权、范围、状态和版本 |
| `POST grants/{id}/control/{pause,resume}` | 版本校验的暂停/恢复 |
| `POST grants/{id}/revoke` | 撤销 |

公开管理接口不能传入宿主 admission 回调。Package 只得到申请状态和标识，不得到可在通用保存接口兑换的 preview_ref。源权限、详情 Provider、Tool 启用状态及 grant 每次读取均重新校验；缓存也不绕过检查。每个 delivery 最多尝试三次前台详情读取，结果最多 48 KB，成功后缓存并复用同一消费 Session。

## 升级、停用与循环防护

- 同发布者、同信任来源、同声明、同 patch 集合、相同 handler 的同主版本向前升级可以沿用授权；Mini-App 接口版本也须同主版本且不倒退。只更新已接受的发布来源，不扩大批准范围。
- 主版本变化、权限声明变化、发布者变化、patch 变化、降级或重装需要重新确认。开发源码变化不自动继承授权。已失效的 grant 不因回滚而重新生效。
- 停用或卸载 Package 撤销其 grant；重新启用不能恢复旧授权。来源失去验证或访问权限时，扫描、读取与执行都拒绝并要求处理。事件声明/详情接口版本变化也停止旧规则。
- 后台复用既有 System Task、持久受理凭据、动作回执和因果传播。同一因果链每条规则最多激活一次，最大深度 8、根激活数 20；未知因果不能自动执行。暂停、过期或撤权阻止后续动作，未知外发结果不自动重试。
- 前台 SDK 的消费不授予新的写权限。需要扩展为任意 Package 工作流或让 Package 自定义后台代码执行时，须另行设计执行身份、效果授权和跨调用因果传播；本版不提供该入口。

Schema 105 保存 requests、grants、audit 和有界详情读取结果。申请与预览同事务持久化；每个 Package 最多十个待处理申请，每个用户最多一百个，拒绝申请会释放预览配额。既有 Hook 配额（每用户 100 条、每规则 1000 次匹配）、历史回执和 gap 监控继续有效；本版未引入自动清理历史审计。未改 Cloud 代码、未发布 Package 或 Desktop。

## 验证记录

验证结果和固定 Dev/App-Dev 激活证据见 [实现验收](package-event-hooks-implementation.md)。签名安装测试使用独立临时目录，事件与 AaAT 业务返回为明确的测试夹具；不等同于第三方线上 Package 或微信外发验收。
