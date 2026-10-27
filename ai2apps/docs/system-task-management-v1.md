# 系统级 Task 服务与 App / Mini-App 接入合同 v1

## 后台执行 Session 与前端隔离（2026-10-15 修正）

业务 Task 不能保存手机 owner-home、remote_session 或前端选中 Chat Session 作为后台执行授权。AppInstance 可能实际存在，却因 client_scope 隔离对后台 desktop principal 返回 app_instance_not_found；不能通过删除 scope 检查修复。

可信 host 的内置单例用户 App 可调用 `system_tasks.sessions.execution_session(runtime, owner, app_id)`：从当前有效成员解析 Local principal，校验启用的业务 App 定义与能力，在该 owner 的业务 AppInstance 下创建/复用 durable、unlisted、app 类型 Session。它不创建 Chat 线程，不修改手机对话选中项，不接受调用者指定 AppInstance/client_scope。业务仍须先校验频道等资源归属；该解析器不向 Mini-App 暴露，也不接受第三方 App 自注册执行身份。

页面 focus/suspend/close 不决定后台任务是否运行；App 定义禁用、成员失效或权限撤销必须阻止解析。Session 归档后按正常仓库路径创建替代项，不修改旧手机 Session 的 owner 或作用域。情报中心在提交及每次实际执行（含重启恢复）重新解析，并持久更新 collection_jobs 与旧 collection_schedules 的执行引用。原有缓存、来源范围和 Task ID 保留。已失败历史不自动改成成功或擅自重放；用户重新刷新或从 Todo 重试即可走修复后的路径。

状态：首版实现；Local 持久化服务，Todo 为统一管理入口。情报中心首批接入。

## 职责与边界

系统服务管理任务提交、根任务准入、定时触发、检查点、执行尝试和控制。服务随 Local 启动，关闭 Todo 或业务 App 页面不停止任务；关闭 Local/设备后不继续执行，重启按恢复策略处理。

Browser Task/TaskTree 继续管理浏览器子任务、Profile 名额、页面归属和清理，模型调度器继续管理算力。系统名额只按根 Task 计算；子 WebAgent 不重复占用系统名额。不要在等待浏览器/模型资源时通过心跳伪造有效进展。系统等待状态不等于浏览器响应等待，后者仍有命令超时。

不要向 Mini-App 暴露任意 Python、shell、HTTP 代理或 handler 注册能力。Handler 只由可信 Local 代码注册。Mini-App 调用所属 App 已声明的业务 API，后端校验当前身份、App 权限和资源归属，再提交任务。跨 App 管理入口在 Todo；默认只可见和控制当前用户自己的系统任务。

## 三个持久对象

- Task：冻结的 JSON 输入、owner、App、kind、手动/定时 trigger、去重键、优先级、状态、检查点、摘要进度与结果。输入上限 1 MiB；大正文/附件保存业务存储，任务携带引用。
- Attempt：每次实际获得执行名额生成一个编号，记录开始、结束、错误。重启恢复会建立新 Attempt，旧尝试标记 interrupted。人工重试创建新 Task，保留旧记录；可用 retry_payload 转换为业务恢复请求，情报中心会根据频道保存的证据恢复未完成整理，而不重放旧的已结束采集。
- Schedule：独立计划，保存 UTC Unix 秒、单次/固定间隔、启用状态。间隔至少 60 秒。首版不支持任意 cron/日历规则；不要把本地时区显示误认为执行时区。错过多次只合并触发一次，不形成补跑风暴。

Task 状态：queued → running / waiting_resource / waiting_user → completed / partial / failed；取消先进入 cancelling，资源确认清理后才 cancelled；无法安全恢复的执行 interrupted，不自动重放。

输入与检查点必须是数据，不能包含凭据。结果和私有检查点不出现在 Todo 列表；列表仅返回摘要进度。业务 App 保持正文、实体、图片等数据所有权。

## 提交与执行

```python
from ai2apps.system_tasks import TaskHandler

service.register('myapp.refresh', TaskHandler(
    app_id='publisher.myapp', execute=execute, cancel=cancel,
    authorize=authorize_owner_and_resource, resumable=True,
))

task = service.submit(owner, 'publisher.myapp', 'myapp.refresh', '更新资料',
    {'resource_id': resource_id}, dedup_key='refresh:'+resource_id)
```

`execute(context)` 接收冻结 payload；`context.report(checkpoint={...}, progress={...}, message=...)` 持久保存可恢复边界。报告 waiting_resource / waiting_user 时必须提供真实等待原因，恢复后报告 running。不要每次轮询重写全量正文。返回结果字典，可用 `_status: partial/failed` 表示业务结果。

`authorize(owner,payload)` 在提交和每次执行前校验权限，权限撤销必须阻止启动。首次系统级并发上限为 4，每 App 2、每 owner 2；优先级加等待分钟进行老化。Browser/Profile 与模型限制仍独立生效，立即启动不能绕过它们。

同 owner/App/非空去重键下最多一个非终态 Task。定时与手动入口必须使用相同业务去重键。不要给每篇文章分配一个系统根任务；文章与来源使用同一任务树的子节点。

## 定时与取消

`schedule(...)` 注册单次或固定间隔计划。定时入口与手动启动复用相同 handler；立即执行计划不修改下一次计划时间。禁用/删除业务资源时同步停用对应 Schedule。

`cancel(context,force)` 只处理本 Task 拥有的资源，必须幂等，确认清理完成返回 True；暂未完成返回 False。服务会继续检查，期间保持 cancelling 和执行名额。禁止杀掉整个 Local、共享浏览器、共享模型 Worker，禁止清除其它任务页面。

强制中断请求设置 force 标志并取消该任务执行协程，适配器可采取更强的任务范围内取消措施；无法证明资源已释放时仍保持 cancelling，不假报完成。首版情报适配器复用 WebAgent 取消与 owned-context 清理，没有共享进程级 kill。排队任务可以直接取消，因为尚未占用执行资源。

## 恢复与重试

只有 resumable=True 的 handler 可以在 Local 重启后自动恢复；必须能根据持久检查点识别已提交结果。涉及支付、发布、消息发送等不确定副作用时，先核查外部结果，再继续。不可恢复 handler 重启后 interrupted，不能通用一键重放。

根任务必须等待子任务及页面清理结束。取消后也必须等待清理确认。单篇失败可继续其它文章，根任务返回 partial；不要让失败的子任务导致全部成功结果丢失。模型/网络失败保留原始证据，业务重试可以重新选择当前默认模型。

首版不做通用自动失败重试；业务 handler 可在安全边界内有限重试，用户从 Todo 显式重试。不要隐藏无限重试或把资源排队算作执行停滞。

## Todo 与 API

Todo Desktop/Mobile 的固定“系统任务”目录提供执行中、排队中、待定时执行及历史；默认只列根任务，展开查看绑定的子任务树和近期 Attempt。

- `GET /v1/platform/todo/system-tasks`：owner 范围摘要列表，最多 200 项。
- `GET /v1/platform/todo/system-tasks/{id}`：安全摘要、Attempts 与绑定子任务树。
- `POST .../{id}/start`：排队任务提优先级或从安全检查点重试。
- `POST .../{id}/cancel`：`{"force":false/true}`。
- `POST /v1/platform/todo/system-schedules/{id}/start`：立即执行一次。

管理 API 沿用 App 身份、Cookie 同源与 Mobile Bridge 访问校验。未经 App 业务鉴权不能通过这些 API 注册任意任务或计划。

## 迁移范围

首版情报中心的频道根任务和周期刷新迁入本服务，保留 collection_jobs 原始网页缓存和编辑检查点；历史未绑定运行会由协调器补注册。原 Browser/模型资源队列不迁移，不能重复执行旧采集循环。

Todo 自身已有的项目执行器、Studio 持久生成任务、购物及其它定时器仍保留现有执行逻辑，后续按适配器逐个迁移，不能声称它们已受本服务全局并发约束。未接入 App 不会自动出现在此列表。

管理入口首版提供中文/英文文案；状态存储与 API 使用稳定英文枚举。真实 iPhone Safari 的远程触发与恢复需另行验收，不能用隔离浏览器测试替代。

## 本轮验证与激活

- 主回归 170 项通过（系统服务、情报中心、Todo）；补充回归 117 项通过（与主回归有重叠，包含 Mobile/网关和数据库迁移）。最后的进度去重、适配器与界面修正另行定向验证。
- 10 项 Node/隔离浏览器界面检查通过，包含 Desktop/Mobile 控制、转义、展开状态保持与既有目录布局；最后共享任务界面再跑 2 项通过。
- 固定 App-Dev 经标准 builder 重建和归档，验证签名、App/Helper 源根、schema 94、实际服务导入路径与 Mobile 资源逐字节一致；Dev 不操作。
- 登录后的 App-Dev 原生实测：从 F1 官网单源入口提交刷新，在 Todo 显示同一个系统根任务，展开可见列表与并发文章子任务、Attempt #1；中断后进入历史，全部浏览器子任务终态且 owned 页面清理状态 verified/retained。该测试用于任务控制，未声称完成新情报生成。真实 iPhone 远程控制仍未验收。
- 取消时先通知 owned 资源再等待协程退出，防止内部等待阻塞取消通知；单源重试保留 source_id，兼容早期记录通过原 run_id 恢复范围；已结束任务的耗时停止增长。72 项系统/采集回归通过。

登录后第二轮实测：Todo 重新执行产生新任务，仍只更新原 F1 官网；普通中断后列表任务完成、3 个文章子任务取消，根任务 cancelled，owned 页面清理无 pending。历史卡片已确认显示“任务已中断，所属资源已清理”，耗时固定。此轮没有完成新情报生成，也未改变现有定时设置。

### v94 开发库兼容修复

已部署的开发库存在带/不带 `system_tasks.trigger` 的两种 v94 结构。v95 `system_task_trigger_compatibility` 通过迁移声明的 ensure_columns 仅在字段缺失时添加，已有值、任务、尝试和计划保留；禁止靠重新执行 v94 或手工改实例库修复。新库也通过 v94 → v95 获得字段。覆盖两种结构、数据保留和重复初始化的回归已通过。

“立即启动”成功后跟随该任务切换至排队、执行或历史列表；用户手动切换分类则停止跟随，避免仍停留在定时页而看似没有响应。


## 频道更新系统推送（2026-10-15）

情报中心每轮刷新把实际新建文章的 ID 与文章一起提交到业务 SQLite，增量保存、缓存恢复和最终保存不会重复计数；已有文章更新不算新增。Local 协调器每 5 秒检查已结束且有新增的刷新，向统一 NotificationProducer 入队，不依赖 Todo、频道页面或 iOS 前台运行。

复用 Cloud 已部署的 task.completed / task_completed；若刷新最终失败但已有新文章提交，使用 task.failed，避免伪报成功。partial 使用完成通知；纯失败、无新增、取消、删除频道和旧历史记录不补发。每轮只发一条，result_count 是实际新建文章数；target 为真实系统 Task ID，app_id 为 ai2apps.intelligence。当前模板是系统任务模板，尚未增加频道专用通知标题或点击直达文章能力。

业务 SQLite 与平台 SQLite 不共用事务，因此先保存业务意图，再使用稳定 intelligence.new_articles:<run_id> 入平台持久 outbox，成功后回写确认；两次提交之间崩溃由 event_id 幂等去重。业务入队失败至少间隔 60 秒重试，刷新结束超过 24 小时不再补入队；入队后的发送、网络退避和 TTL 由统一 Producer 管理。未授权时不绕过手机/Cloud 通知偏好，文章保存不受通知失败影响。

当前 Device-auth 接口发送给 Installation Owner，只通知同一 Owner 的频道；成员私有频道不发送给设备 Owner。enqueue(expected_owner_id=...) 在生产者采集身份时再次校验，防止调用前身份变化。事件仅含不透明 Task/App 引用及数量，不发送频道名、文章标题、正文、URL 或凭据。Cloud 202 仅表示接收，不证明 iOS 已收到或已读。
