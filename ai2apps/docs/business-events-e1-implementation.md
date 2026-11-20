# 标准业务事件 E1 实施记录

2026-11-02，Local 源码实现。对应[平台事件设计](platform-events-and-bot-hooks-v1.md) E1；业务 Hook 执行尚未开放。

## 已实现契约

- EventStore 仍是唯一事件流；Schema 101 的 business_event_facts 保存获准业务投影、事实唯一键、声明哈希、入库时间和 owner 索引。回滚不留事实，同一 occurrence 内容相同返回原 ID，内容不同拒绝。
- 内置 owner 在受信任组合入口登记 EventType 并持有 Publisher 对象，HTTP 不提供 publish 或任意处理器注册。声明包括严格载荷 schema、可筛选字段、对象类型、生产范围和详情绑定状态。
- GET /v1/platform/business-events/catalog 返回三个类型；GET /v1/platform/business-events 支持 after、limit、event_type；GET /v1/platform/business-events/{event_id} 返回当前用户仍有权查看的业务投影。原 /events SSE 保持原协议。此阶段 API 面向认证 Local 用户；App/Mini-App 受限投递入口须随 Hook 另行接入，不能当作后台委托凭据。
- 事件当前标记 causality=unknown。cause_root_id 只是单事实根标识，**尚未证明跨 AaAT/Task/outbox 的因果继承**，不得据此启用自动副作用或声称循环已被完全阻止。

## 三个业务事件的覆盖

| 类型 | 实际发布与限制 |
| --- | --- |
| intelligence.channel.refresh_finished | IntelligenceStore 新的 finish、complete_pending、fail_finalization、progress 终态事务写本库 outbox。Runtime relay 分批追加平台事实，最后确认源 outbox。崩溃重送保持 event_id，不回填已有 runs。added_count 基于该轮 new_article_ids；不等于处理/更新量。 |
| studio.video_output.published | VideoTaskManager 生成任务产物已导入 artifact，succeeded 写入与事件在同一个平台事务提交。generation 路径以 artifact_id 去重；导入、编辑导出、其他 Package/Studio 发布路径暂未覆盖，目录已说明。 |
| readaloud.voice_profile.created | ReadAloudRepository 原有事务事件直接建立业务索引，保留原 event_id；投影不带 owner_user_id 或私有素材。创建可能仍为 unverified，不代表 ready。 |

详情绑定当前为 null；本阶段没有按批次冻结文章快照，不能靠该事件承诺自动摘要的是“当时的正文”。事件授权和详情读取将分别检查。现有资源删除后不再返回该事实给资源读取调用方，持久审计不被当作继续读取内容的权限。

## 验证边界

实际 SQLite/迁移、仓库方法、视频 artifact 落盘和 HTTP 路由测试使用临时独立 Runtime。视频生成器输出使用合成视频夹具，频道以构造终态批次验证跨库故障恢复；未调用真实模型、账号或外部网站。另运行情报后台、朗读和视频工坊的相关现有回归以及 AaAT 边界门禁。运行结果与开发激活状态记录到 Desktop 发布台账。

## 下一阶段门槛

先补订阅预览、资源范围、持久游标/投递以及 front invalidation 与 background delivery 两种消费轨道，再接 Bot/App/Mini-App。自动执行前必须完成：受限调用身份、不可变规则版本、后台授权、跨步骤 cause_root 传播、重入/预算原子 guard、owner 效果限制与恢复测试；不能因 E1 有目录就直接把事件正文注入 Bot 并让它自由执行。

验证结果：新增专项 6 项通过；情报后台/朗读/视频相关回归批次 90 项通过；AaAT 边界门禁 758 项通过。Dev 与 App-Dev 经空闲检查后由各自 Helper 加载，App/Helper source root、运行模块路径、Schema 101 和匿名目录拒绝已核对。真实模型生成与后续 Hook 尚未验收。
