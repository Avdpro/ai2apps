# Event Hook E2 只读订阅实施记录

2026-11-02。依据[平台 Event/Hook 设计](platform-events-and-bot-hooks-v1.md)，实现到观察与记账层。每次命中为 matched、executed=false；没有模型、工具、回复、Todo 或微信发送入口。

## 已交付

Schema 102 保存 previews、rules、不可变规则版本、投递记录、请求幂等凭据与显式保留水位。预览有效 10 分钟，使用一次；同 request_id 同请求返回原结果，不同请求拒绝。每用户最多 100 条未删除规则、100 个未消费预览；每规则最多 1000 条命中历史，到达上限暂停并保留未处理游标，不静默丢弃。

注册来自受信任 owner 的 ConsumerType，区分 bot/app/mini-app，固定版本和绑定校验器；HTTP 不能上传可执行 handler。Dev/App-Dev 的 Messager 登记 Bot 和 App 只读观察者。Bot 必须属于当前用户；App 必须是当前用户拥有的活动 Messager 实例。Mini-App 类型用独立测试 owner 验证了框架，但真实 mount/broker 接入属于 E3，当前不登记泛用 Mini-App 入口。

每条规则默认选择明确的资源 ID，最多 20 个。视频和语音角色也声明了 owned_collection 范围，允许当前用户在创建对象前订阅其未来输出；源事实仍必须属于该用户，查询投影再校验实际资源。没有该声明的事件拒绝集合范围，普通通配符始终拒绝。筛选仅允许事件声明中的字段，以 AND 组合 eq、in、gt、gte、lt、lte；验证类型、枚举与有限数字，不接受脚本。事件和消费者版本固定在规则中；变化、资源撤权或消费者失效会暂停扫描。读取历史也重新检查权限，不能通过旧事件继续读取已撤销对象。

启用时在事务里记录当前事件高水位，从启用后平台接收的事实开始。修改活动规则保存旧版本结束水位，新版本从该水位开始；积压用原版本匹配。暂停规则经新预览重新启用时明确跳过旧积压，防止新授权用于旧事件。暂停将未扫描范围明确标为 skipped；恢复从当前高水位开始，不重放暂停期间事件。删除停止匹配，原用户仍可按规则 ID 查询历史。请求凭据和历史不自动删除，保留清理由后续容量阶段设计，不假装无限存储已解决。

扫描复用 Local 生命周期的事件 Relay，提交唤醒加 2 秒后备轮询。事件命中插入和游标前移在同一事务提交；唯一 rule/event 键、当前游标重读确保并发扫描不重复。进程退出等待正在进行的事务 worker 收尾；重启可继续。显式 retention floor 超过游标时暂停为 cursor_gap，不能用普通全局序号空洞推断丢事件。

## Local 用户管理 API

以下位于 /v1/platform/hooks，沿用认证 Local 用户与 app.use。它是用户管理面；App/Mini-App SDK 的 mount/digest 委托通道尚未开放，不继承用户完整管理权限。

| 路由 | 作用 |
| --- | --- |
| GET /consumers | 已登记消费者类型，mode=observe_only |
| POST /preview | 验证 consumer、event_type、subjects、filters，返回 preview_ref 与规范化规则 |
| POST 空路径 | preview_ref + request_id 启用新规则 |
| GET 空路径 / GET /{id} | 当前用户规则与版本、水位、暂停原因；删除后仍可按 ID 查审计 |
| PUT /{id} | 新 preview_ref、expected_revision、request_id 更新规则；暂停规则经新预览明确重新启用，从当前水位开始 |
| POST /{id}/pause、resume、delete | expected_revision + request_id 操作；过期版本拒绝 |
| GET /{id}/deliveries | 授权投影、mode/状态和 executed=false，after/limit 分页 |

示例为用户已经选择并解析了 Bot 与角色 ID 后的预览请求，不表示可直接拿显示名代替 ID：

```json
{
  "consumer": {"registration": "messager.bot.observe", "binding": {"bot_id": "已拥有的 Bot ID"}},
  "event_type": "readaloud.voice_profile.created",
  "subjects": ["已拥有的角色 ID"],
  "filters": [{"field": "status", "op": "eq", "value": "ready"}]
}
```

此例只观察所选角色的创建事实，并且仅当创建时已 ready。订阅未来新角色时，改为 scope="owned_collection"、subjects=[]；这由语音 owner 的集合授权提供，不从当前可见列表推断未来权限。要处理已存在角色后续变 ready，需另一个真实状态转换事件。

## 验证与下一步

专项测试覆盖 from_now、筛选、幂等、重启、规则版本边界、暂停恢复、删除审计、HTTP/跨用户拒绝、实际 Bot/App 绑定、资源和声明撤销、缺口/上限、并发扫描、插入后游标写入失败回滚，以及无页面/模型的后台扫描。源事件使用临时 Runtime 和业务事实夹具，没有发送外部消息。

E3 再接 Bot 会话唤醒、App 后台 handler、Mini-App 前台失效提示与明确后台入口，以及 AaAT 详情读取。必须先补后台委托、固定能力/provider、可信因果继承和重入/效果预算。E2 不把“matched”当作已投递到消费者或业务完成，也不会产生递归工具调用。

验证结果：32 项专项及相关测试通过；AaAT 门禁重跑 758 项通过（首次一项旧表单交接出现 SQLite 锁冲突，单项复跑也通过）。Dev/App-Dev 通过标准 Helper 在空闲后加载，源码绑定、模块路径、Schema 102 和匿名管理拒绝核对通过。尚未提供订阅管理 UI，也未执行实际用户 Bot 或外部消息。
