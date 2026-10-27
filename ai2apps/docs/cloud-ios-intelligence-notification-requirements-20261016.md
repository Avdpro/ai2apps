# 频道更新通知：Cloud / iOS 接入需求

2026-10-16。状态：需求交接，尚未实现或部署。Cloud 代码不在此仓库修改；iOS 源码亦不在当前 checkout。

## 用户问题与预期

当前频道刷新复用 task.completed / task_completed，锁屏只显示“有一项任务已完成，打开应用查看”。Local 虽已传 result_count，现有模板没有展示频道或文章信息。

期望示例（示意数据，非本轮真实采集结果）：

> 腕表 · 新增 6 篇情报
>
> BA111OD 推出 Chapter 4 新款；Mido 新增天文台认证版本

> AI进展 · 新增 3 篇情报
>
> 本轮新文章标题一；本轮新文章标题二

一轮更新只通知一次。更新已有文章、重复帖子、无新增、取消任务继续不通知。有已保存新增但部分来源失败时，仍显示新增数量，并在展开详情中标注“部分来源未完成”，不得误称全部刷新成功。

## Cloud 协议扩展提案

以下为待 Cloud 确认的新增协议，不代表当前服务已经接受这些字段。

- 在现有 Device-auth `POST /api/v1/notifications/events` 增加 `intelligence.updated` kind、`intelligence_updated` 模板及 `intelligence_channel` 目标类型。
- target 保留结构化不透明引用：`type=intelligence_channel`、`id=channel_id`、`app_id=ai2apps.intelligence`。发送身份继续绑定现有 Installation / Device / Owner / epoch，不接受任意跳转 URL。
- 受限模板参数包含 `channel_name`（最多 80 字符）、`new_article_count`（1–1,000,000）、`headlines`（最多 2 条，每条最多 100 字符）、`refresh_status`（completed / partial / failed）。保留不透明 run_id、system_task_id 供通知详情追溯。
- headlines 仅取本轮实际新增并已保存的文章；不从已有文章更新、未保存结果或原始帖子凑数。排序与频道最新文章顺序一致，不额外调用模型生成广告式摘要。
- Cloud 统一渲染 APNs alert：title 为“{频道名} · 新增 {数量} 篇情报”，body 为最多两条标题；无可用标题时降级为“频道已更新，打开查看新情报”。最终 APNs payload 保持在平台限制内，按完整 Unicode 字符截断，不拆坏 emoji。
- 纯文本处理标题和频道名，移除控制字符；不接受 HTML、任意 APNs 字典、声音、URL 或 action 注入。不上传文章正文、证据内容、Cookie 或凭据。
- 多语言由既有通知语言策略渲染固定模板，用户的频道名和文章标题保持原文，不在推送阶段重新翻译。
- 保留当前限流、授权、TTL、退避和 event_id 幂等规则；相同 event_id 的展示参数也必须一致。

## 能力协商与兼容

在现有 producer-policy 中明确发布支持的 event kind / 模板能力（字段名称由 Cloud 项目最终确认）。Local 只有收到明确支持后才生成新格式事件；旧服务继续使用原任务通知，不能靠试发未知字段或收到 4xx 后改写同一事件来探测。

现有 outbox 内已冻结的事件原样重试，不改内容、不重新发送历史通知。同一刷新不能先发通用通知再补一条丰富通知。新格式一经入队，频道名、数量、标题和路由引用都冻结，避免重试期间文章编辑或模型变化引发幂等冲突。

Local 改造待 Cloud 协议确认后实施：在业务事务中保存新增文章 ID，生成通知时按 owner / channel 校验并读取上述短展示快照，再进入现有持久 outbox。现有 Owner 隔离保持不变，成员频道不能送给设备 Owner。

## iOS 展示与点击

- 锁屏横幅、通知中心和 App 内通知箱使用同一标题、正文和数量，不再统一覆盖为“任务完成”。遵守 iOS 系统通知预览设置；若提供 App 级隐私模式，可仅显示频道与数量。
- 同一 Device / channel 的通知可使用稳定的 APNs thread-id 分组，不按所有 AI2Apps 通知混为一个业务频道。
- 点击通知通过当前已有设备连接和会话鉴权打开对应情报频道，显示最新文章；不要仅打开任务列表。频道/设备不可访问时清晰提示，不跨用户回退。
- 从通知打开后按既有通知协议更新 opened/read；APNs accepted、手机 received、opened、read 分开记录，不用 Cloud 202 充当送达证据。

## 交付与验收顺序

1. Cloud 确认事件 schema、能力协商、模板、多语言和通知箱数据结构，并兼容旧客户端。
2. iOS 支持该 target、丰富文案、按频道分组和点击路由。
3. 本仓库接入经确认的字段，补充展示快照冻结、Owner 隔离、限长、多语言和去重测试。
4. 实机刷新一个有新增文章的频道：验证锁屏可见频道名/数量/标题、点击到正确频道；无新增不通知、重启/超时不重复发送，部分失败描述正确。当前截图证明通用推送已可达手机，但不替代新格式端到端验收。

在以上步骤完成前，当前 Local 继续发送既有通用任务通知；本需求文档不表示丰富推送已经生效。
