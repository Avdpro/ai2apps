# AI2Apps 业务事件与订阅 Hook 设计 v1

Bot 之间的请求/回复、任务协作和直接结果回接见 [Bot 通信与任务协作设计 v1](bot-communication-and-collaboration-v1.md)（C1/C2 已编码，Event/Hook 联动仍属后续范围）。通信命令与事件事实分开；协作派生事件沿用本设计的授权、可信因果链和根预算，送达/已读/进度默认不触发模型，直接回接与 Hook 不得重复创建任务。

2026-11-02 · 设计与实施契约；E1 已有源码实现，覆盖及验证边界见[实施记录](business-events-e1-implementation.md)。E2 的只读订阅实现见[实施记录](event-hooks-e2-implementation.md)；执行消费阶段仍属设计。首期部署在 Local 的 Dev/App-Dev。本文定义平台契约；Bot、App 和 Mini-App 都是一级订阅者；Messager 是其中一个产品入口。

**决策：App 发布已经发生的业务事实；订阅者在用户授权下保存规则，决定哪些事实触发哪个已注册入口；有副作用的动作由取得相应授权的业务服务执行。** “腕表频道更新了”无需知道谁在监听；没有 Bot、没有订阅者或模型不可用，也不能妨碍频道本身完成更新。

## 1. 从现有实现出发

| 当前代码 | 已有能力 | 设计增量 |
| --- | --- | --- |
| [EventStore](../events/store.py)、[提交唤醒](../events/bus.py)、[SSE 重放](../events/stream.py) | SQLite 全局 sequence；可与业务写入同一事务追加事件；提交后唤醒，读取方按游标补读 | 增加**允许自动化订阅的业务事件目录**、可信发布身份、业务事实去重和可索引的资源范围。不把所有诊断或进度事件自动开放。 |
| [System Tasks](../system_tasks/service.py)、[Todo 自动流程](../system_tasks/agent_flows.py) | 持久任务、计划时间、处理器与运行记录；Todo 已有计划预览/确认/撤销先例 | Hook 投递对接现有任务执行。复用调度，不借用 Todo 的身份或授权。SSE 只展示状态，浏览器页面不推进任务。 |
| [持久 App Chat](app-chat-durable-v2.md)、[Messager Bot owner](../messager/bots.py) | 每个用户有自己的 Bot，App Chat 关联 Session、Run、Task | 新增可信唤醒来源、订阅及后台委托。今天 Bot 的只读工具集不因存在来信事件而扩大。 |

首期不做互联网 Webhook、任意代码回调、跨设备全局排序或 Cloud 事件总线。若以后需要 Cloud 离线入站推送，另行交接 Cloud 需求，不把它隐含在 Local 的交付承诺里。

## 2. 三份契约：声明、事实、委托

**事件声明（Event Type）**由业务 owner 提供。内置 App 在组合入口注册；Package 从签名清单引用经校验的声明资源。类型具有 owner 独占的命名空间。声明包括：稳定类型名、主版本、定义修订、显示名称/说明、发生条件及明确排除项、subject 类型、载荷 JSON Schema、可筛选字段和操作符、事实去重键、覆盖范围、所需订阅权限、资源解析/读取能力。目录只列出活跃且当前 actor 有权发现的声明。显示名称可翻译，规则不靠翻译或模型猜测字段含义。旧内部事件须逐项审查、显式映射；名字相同也不能默认可订阅。

**事件实例（Event）**不可变，不含“请发送”“请批准”等指令。下面是新类型的示意值；平台负责填入身份和提交位置，生产者只提交经 owner 验证的业务输入。

```json
{
  "id": "evt_123",
  "type": "intelligence.channel.refresh_finished",
  "schema_version": 1,
  "sequence": 8102,
  "producer": {"app_id": "ai2apps.intelligence", "declaration_revision": "1"},
  "scope": {"installation_id": "local_1", "owner_id": "user_a"},
  "subject": {"kind": "channel", "id": "channel_7"},
  "occurrence_key": "run_42:terminal",
  "occurred_at": "2026-11-02T07:01:00Z",
  "recorded_at": "2026-11-02T07:01:02Z",
  "data": {"run_id": "run_42", "status": "completed", "added_count": 3},
  "origin": "live",
  "causation_id": null
}
```

sequence 是**本次安装内的入库顺序**；不是业务发生时间，也不是用户的读取凭据。相同事实重新投递沿用原事件。生产者的业务重试若生成独立的新刷新 run，可产生独立事实。后台操作引发后续事件时传播 root/causation 引用；跨系统无法证明来源的，记录 unknown，不假造因果链。

**Hook（订阅委托）**归用户所有，持久绑定安装、actor、消费方实例、处理入口、事件类型及兼容版本、资源 ID、筛选式、不可变动作计划、授权引用、预算、有效期和恢复策略。事件和定时是两种 trigger，共用委托、执行和回执，但“每天 06:00”不必伪装成某个业务 App 的事件。

资源范围可以是显式对象，也可以是 owner 明确授权的当前用户对象集合；集合不从当前可见对象列表推断，也不接受自由通配符。例如用户说“腕表频道有新文章时给我三条摘要”，保存的是：选择已解析的 channel_7，匹配 refresh_finished v1 且 status=completed、added_count>0；按 run_id 读取**该次新增**文章，最多选三条，写回指定 Bot 会话。频道改名不会失效，删掉再新建的同名频道也不会被自动接管。若 owner 只能提供当前文章列表，目录必须说明覆盖限制，不能宣称支持“本次新增”。

### 消费方注册：同一个事件可以有多个独立订阅者

订阅目标为宿主生成的 consumer_ref，关联 actor、installation、app_instance、可选 mini_app_id 或 bot_id、handler_id、已审核的处理器版本与授权引用。创建、列举、暂停、删除及查询投递记录均按此身份鉴权；一个 App 不能修改另一 App 的规则。同一事件扇出到多条规则，各自确认、失败和重试，慢消费者不会阻塞发布或消耗其他消费者的事件。处理器只确认自己的 delivery_id。

| 消费方 | 谁登记；怎样消费 | 离开界面后 |
| --- | --- | --- |
| Bot | Messager owner 绑定指定 Bot 和持久会话；用户通过对话或设置启用委托 | 通过 Local 后台运行，结果回到原会话 |
| App | 内置 App 或已安装 Package 声明命名处理器、可订阅的类型/版本、所需读取能力与用途。宿主验证声明；用户在 App 中启用具体规则 | 有后台授权才进入该 App 的持久任务；纯界面刷新只发失效提示，重开读取快照 |
| Mini-App | 通过宿主 broker 以当前已验证 mount、Package digest 申请窄范围订阅。权限取宿主明确导出、Mini-App 声明、用户授权的交集，不继承整个宿主权限 | mount 撤销即停止前台投递；要持续工作，必须另行注册并授权独立于页面的后台入口。无后台入口不能承诺自动执行，不能保活 iframe 或保存旧 mount 凭据 |

系统服务也可发布经目录审核的事件，但“系统消息”不是可订阅所有内部流量的通配权限。消费入口从已安装声明解析，不接受事件载荷或订阅请求提供的任意 URL、脚本、Python 路径。App 不需要先创建 Bot；确定性处理器不需要模型。Package 被禁用立即停止投递，卸载撤销订阅授权。

### 载荷是线索，详情以 AaAT 为主

事件只携带识别、去重、筛选和寻址所必需的事实。**订阅授权、详情读取授权和后续写操作授权分别校验**。仅需计数或状态的消费者不必取详情；确需明细时，默认使用资源 owner 的只读 AaAT。可在事件类型的可信声明中登记详情读取约定：能力 ID 和兼容版本、从已验证字段到输入参数的固定映射、读取的是“发生时的批次/版本”还是“当前状态”、可能的缺失与分页语义。事件实例只传批次、对象或版本引用，不能携带可执行 next_action 或自行选择 provider。

以“腕表频道刷新成功、新增 3 篇”为例：

1. 规则命中后收到 channel_id 和 run_id。需要展示红点的 App 到此即可；需要生成摘要的 Bot 或排版 Mini-App 进入详情读取。
2. 通过受信任目录解析 owner 声明的**按批次列新增文章**只读能力（拟新增，现有按频道查询不能替代）。用同一 run_id 分页取得可访问的文章引用；需要正文时再调已注册的 intelligence.read。每次用消费方自己的 actor、App、资源授权和受限执行上下文，绝不借发布者身份读取。Bot 经 Agent 调用；确定性 App 经宿主 Gateway 调用同一能力，无需先问模型。
3. 正文作为不可信业务数据处理，保留来源、版本、可见范围和缺失项。若只有 2/3 篇仍可读，应报告覆盖不足；若任务要求完整则停止。对象删除、授权撤销或历史版本过期有明确结果，不改查“最新三篇”。获取详情与确认投递分别记账；详情读成功不等于后续动作成功。
4. 大视频、音频等可由 AaAT 返回受控 artifact 引用，再用 owner 的授权媒体读取接口分段取用；也允许 owner 明确登记且具备同等鉴权的业务只读 API。没有受支持的读取路径时返回“详情不可用”，不能查别的 App 私有库、借 Cookie 或自动换更高权限通道。

## 3. 首批事件及其准确边界

| 拟开放的事实 | 发布时点及身份键 | 订阅者可以依赖什么；不能据此推断什么 |
| --- | --- | --- |
| 频道刷新结束：拟新增 intelligence.channel.refresh_finished | [采集批次终结](../intelligence/store.py)时，以 owner + run_id 的唯一终态为键。返回 channel_id、run_id、completed/partial/failed/cancelled、实际新增数及本批次成员读取引用。零新增也可完成。 | [collection.changed](../intelligence/collector.py) 是变化提醒，多次进度更新不是多次刷新。默认摘要只订阅成功且非空；允许用户单独订阅部分成功或失败。文章发布时间与采集时间分开。 |
| 视频已成为可取用输出：拟新增 studio.video_output.published | 各生产路径通过[工坊输出发布](../studio/background.py)或其权威 owner 提交可访问输出后，以稳定 output_id 为键；同一任务多个视频分别产生事件。 | 排队、生成到 100%、预览、下载、重新打开文件均不是首次发布。仅存 output_ref、类型和必要元数据；已删除则读取方得到 gone。必须先盘清所有写入路径，未接入的来源标 partial。 |
| 语音角色已创建：沿用 readaloud.voice_profile.created | [角色仓库](../readaloud/repository.py)已有事务内事件，subject 为 profile_id；按字段白名单投影，不另发同义事件。 | 创建时可仍待训练。自动合成要订阅另一个经 owner 校验的 ready 状态转换，或显式检查创建时即 ready。不能依赖“过一会儿肯定好了”。不附参考音频或声纹，不改变 Voice Studio 输出归属。 |
| 好友来信：沿用 messager.message.received | [Messager 入库](../messager/repository.py)同事务记录本地入站或 Cloud 离线消息导入，subject 为消息 ID。附来源、会话/对端引用、原发生时间与导入时间（可知时）。 | 是 AI2Apps 好友来信，非微信好友来信；后者需要独立适配器声明其实际覆盖率。Cloud 消息在[导入 Local](../api/cloud.py)时才可观察，不能承诺即时。首期不将旧历史同步、自己发出的回声当作新来信自动回复。 |

## 4. 发布与存储：避免业务成功、事件丢失

同一个平台 SQLite 内，复用 append_in_transaction：业务对象、唯一事实映射和 Event 一起提交，回滚均不可见。**不同数据库不能靠先保存再 emit 假装原子。** 情报等使用独立库的 owner，在业务终态事务中写本库 outbox；Local 搬运器以稳定 occurrence_key 幂等追加到平台库，收到提交回执后才标记 outbox 完成。若崩溃发生在平台提交后、本库标记前，重送只取回原 event_id。涉及媒体文件时先完成文件持久化及可读取核验，再提交 owner 的公开输出记录；孤立临时文件不是业务事件。

建议在既有 events 上增加业务索引/关联表，而不是再复制一份事件流：

- event_types：owner、类型、major/revision、schema、活跃版本与权限声明；同名不同 owner 拒绝。
- event_facts：关联现有 event_id/sequence，索引 installation、owner、type、subject；唯一键为 installation + owner + producer + type + occurrence_key。同键不同业务内容报冲突，不静默覆盖。producer 为稳定 owner 身份，不包含 Package digest；schema 主版本也不进入事实唯一键，避免升级后把同一个事实再发一次。
- hook_rules / hook_rule_revisions：当前状态、不可变规则版本、启用游标、授权和计划引用。历史版本保留至相关投递结束。
- hook_deliveries / hook_steps：唯一 (rule_id,event_id)，固化命中时的规则版本；步骤唯一 (delivery_id,step_key)，记录 task/run/operation 引用、尝试、租约、结果或不确定状态。迁移用既有平台 migration；旧 SSE 和 App 可继续消费原格式。

Package 签名证明来源，不授予代替其他 App 发事件的权力。对 Package 采用绑定已安装 digest、实例、actor 和声明的宿主 publish 接口；拒绝 Package 自报 owner、替用户选 installation 或提交未声明字段。不能提供可认证调用通道时，不开放该 Package 的发布。完整声明按内容哈希固化修订；同一 major 下规则固定具体 revision，兼容升级也由宿主显式迁移，不让已排队消息使用新定义解释。新可选非敏感字段可兼容新增；删字段、改变语义、筛选范围或权限提升须升主版本或暂停规则重新审阅。升级/降级不能自动扩大旧订阅。

## 5. Hook 投递与恢复

1. **启用**：授权校验、创建规则和读取平台当前高水位在同一事务完成。默认 from_now；导入、回填和显式 replay 有独立 origin。首期外发规则不接受历史回放；查看历史可用只读预览。对于延迟搬运的旧事实，按来源和发生时间的新鲜度策略判断；时间不明则阻止有时效的自动外发。
2. **匹配**：Local worker 接收提交唤醒，按 sequence 批读。仅匹配 owner/授权资源和声明允许的字段。v1 支持类型安全的等于、集合、数值范围及 AND；拒绝任意 SQL、脚本或模型生成的过滤器。“是否紧急”属于受预算和隐私配置约束的分类步骤，不在发布事务里运行模型。
3. **领取**：在同一平台事务内插入命中投递并推进持久扫描游标；之后才调度。任务提交使用 delivery_id 作为持久接受凭据，重启先查原任务，再决定是否创建。仅对活跃任务去重不足以覆盖“任务已完成、回写前崩溃”的窗口。失效 worker 不能凭旧租约继续提交。
4. **执行**：分发到固定的受信任消费入口：App/后台 Mini-App 处理器进入其 owner 的任务队列，前台订阅进入有效 mount；Bot 按会话串行进入 Harness，手动聊天时排队。每步复验主体、owner 资源、provider 版本和后台授权。状态分 queued、running、needs_user、succeeded、failed、outcome_unknown、cancelled、expired。只在明确未提交或下游具备持久幂等时自动重试；未知外发只能核对原回执。结果归消费方所有：Bot 回原会话并标记自动触发，App/Mini-App 更新自己的任务或业务记录。
5. **暂停、编辑与缺口**：修改规则使用 expected_revision；新版本以平台事务内确定的生效 sequence 为边界；扫描积压按事件 sequence 对应的旧/新规则版本判断，不能用扫描时最新版本重新解释旧事实。暂停立即阻止新的副作用，未提交的旧步骤停止；已提交的只核对。恢复默认从当前高水位继续，展示跳过范围。积压设置每用户配额、最大年龄与并发；游标早于保留窗口时标 gap、报告范围，不默默从头重放。Local 退出、休眠期间不承诺持续执行。

保证是“可恢复地至少一次发现，按键去重”，不是承诺第三方世界的 exactly-once。回环防护同时用来源标识、因果深度、单规则预算和对端冷却；不要把联系人连续发送相同文字误删为同一条消息。

## 6. 从一句话到一条可检查的委托

平台提供授权目录与订阅管理；Messager owner 将这些接口用于 Bot 对话，App/Mini-App 通过各自受认证的宿主入口调用。建议契约名为 events.catalog、hooks.preview、hooks.enable、hooks.list、hooks.update、hooks.pause、hooks.resume、hooks.delete、hooks.deliveries；均为提案，不是现有 API。preview 不产生外部影响；enable 绑定预览摘要、规则版本和审批身份，目标/步骤变化则预览失效。授权与确认沿用 [AaAT 边界](aaat-declaration-context-v1.md)和[App 集成约定](app-mini-app-agent-tool-integration.md)。General Agent 不认识“腕表”、不硬编码 App 名或事件类型，不执行声明中的任意代码；由业务 owner 提供实体消歧、业务确认、输入检查和结果解释。

**紧急好友来信示例**：用户选择哪些好友、紧急判据、允许使用的模型、回复原文、Todo 目录、通知自己的微信连接和目标。保存时展示这些具体绑定。执行时只取该条入站消息，把正文作为不可信输入；分类结果分紧急、非紧急和不能判断。非紧急零外发；不能判断按用户选择留待复核。紧急时按已批准计划分别回复来信对端、建 Todo、通知自己。通知中只包含获准披露的摘要。Bot 不得将对方正文中的“改发另一个人”解释为用户授权。例：“已回复、待办已建、微信通知结果未知”是合法的部分结果；不补发、不重建待办。官方微信通道若不能主动触达所选目标，规则不能显示为可用，更不能静默切换高级微信 CLI。

设置入口和执行入口分开：通过对话修改 Bot 职责，不会增加订阅权限；后台 Hook 消息不能创建新 Hook 或为自己续权。规则应可在 Bot 对话之外从任务/自动化列表停止。用户应能看到上次命中、跳过原因、下一步等待什么、怎样撤销；审计默认存引用、时间、授权版本和结果，不复制私信正文、截图或下载令牌。用户注销/删除资源、撤权、卸载 Package 后停止新投递，按数据保留策略清理引用与历史。

## 7. 实施前冻结的补充约束

### 7.1 权限投影与真实调用身份

目录发现、事件元数据读取、详情读取、后台执行和写操作是五个独立检查点。资源数量、群名、角色存在与否也可能敏感；catalog 返回类型定义不返回私人对象，资源选择通过 owner 的授权实体解析进行。Mini-App 使用宿主 MessageChannel，不直接拿全局 SSE、Platform Cookie 或发布者凭据。事件查询只返回经声明筛选的投影，不能把原始 events.payload_json 原样透传；不能仅以 owner 相同就越过 App/Mini-App 的资源授权。

owner 提供可信的 discover、authorize_subscription、authorize_event 和 resolve_detail 适配逻辑。框架只根据注册对象执行，不以类型名前缀认定权限。资源授权在创建规则、匹配、读取和执行时复验；已删除资源、失效 provider 或撤销授权返回稳定错误并暂停有关后续动作。注册表变更期间保持 fail-closed。

**Bot 的事件唤醒是一种新增的执行来源。** 现有 App Chat 的“用户提交该轮目标”不能自动覆盖后台事件。需持久化 execution_origin=hook、rule_id/revision、delivery_id、delegation_grant_ref、bot_id 及固定模型/能力/provider 版本。宿主据委托构造上下文，不从模型参数或事件字段接受授权。无后台委托则进入 needs_user，不能借 General Agent 的常规权限执行。

Bot scope 先改为仅以 bot_id 为稳定身份，名字和职责独立版本化；存量会话迁移保留 session_id。唤醒固定本轮档案版本。Bot 改职责不修改既有 Hook 计划；需要另行更新规则。App/Mini-App 确定性消费者使用同样受限的 Gateway 上下文，owner 处理器不得借 Host 权限绕过访问检查。

### 7.2 三个试点的发布范围与详情接口

- **频道终态。** 建立 owner/run/article/version 的批次成员清单。added_count 是本次新建的独立文章数，updated_count 是本次修改已有文章数；与 article_count（处理量）分开。零新增、增量分批保存和缓存命中都要验证；不能只从“当前文章.run_id”查询，因为之后刷新会覆盖它。首次提供按批次引用清单；若不能读取历史正文，则明示 detail_mode=current、返回实际读取 revision 和与事件 revision 的差异，不伪装快照。依赖“当时内容”的任务必须有保留快照才可启用。完成状态需等权威终态；同 run 的 completed/partial/failed/cancelled 只产生一次终态事实，之后的修正以引用原事件的新 correction 表达。
- **视频输出。** 先列出生成、导入、编辑导出和 Package 输出等生产路径，v1 必须在目录声明包含的 production_kinds 和未覆盖路径。用户要求的“视频生成”默认筛选 generation；导入、重新索引旧文件不应命中。媒体文件、可访问输出记录、owner/outbox 提交构成可恢复发布过程，重复 publish 沿用 output_id。不能简单在一个生成器的 succeeded 分支发事件就宣称整个视频工坊覆盖完毕。
- **语音角色。** created 的状态是创建时事实，不随后续训练修改事件；created 与 ready 两种规则不可同时对同一次自动试听重复触发。既有 created 映射到业务索引时保留原 event_id，存量旧事件不批量激活。reference_asset、训练私有素材和声纹始终不进入事件投影；由角色 owner 的详情能力校验实际可读字段。

详情读取约定需机器可验证：provider_id、capability、provider_version、输入 JSON Schema、字段引用映射、返回 coverage/version、最大分页量和上下文上限。业务 owner 负责 snapshot/current 语义，框架不能自动推断。owner 暂无 AaAT 时，E1 可以发布无 details_binding 的事实，但相关规则不能承诺已支持详情自动化。高频事件不允许触发无限查询、媒体下载或模型上下文增长。

### 7.3 首期 API 和状态契约

平台路由建议置于 /v1/platform/business-events 与 /v1/platform/hooks，实际挂载遵循现有 API 约定。原 /events SSE 保持兼容；新 SDK 和业务目录不依赖原 SSE 全量访问。

| 操作 | 冻结的行为 |
| --- | --- |
| catalog / event get | 可分页的类型目录、单个业务事件授权投影；全局 sequence 不授予读取权；subject、type 过滤必须带获准范围 |
| hooks.preview | 解析 consumer_ref、目标、筛选和详情/动作能力；返回规范化规则、缺失权限和短期 preview_ref，不保存活跃订阅 |
| hooks.enable / update | 使用 preview_ref、expected_revision、request_id；同 ID 不同请求冲突，原子记录授权引用和生效游标；预览过期或 owner 版本变化拒绝 |
| hooks.list / pause / resume / delete | 仅管理调用方所属规则；用户级管理面可查看其所有规则；取消已提交副作用只能尽力，回执独立呈现 |
| deliveries / get | 显示匹配、略过、读取与处理结果及任务引用；正文按需另读，不能借投递历史旁路详情权限 |
| consumer lease / ack | 仅供认证后台 SDK，绑定 delivery、attempt、worker generation 和租约；客户端不得凭 delivery_id 自报业务发送成功 |

错误统一为 structured code、phase、retryable、所需用户动作和相关 ID。至少覆盖 event_type_unavailable、unsupported_version、subscription_denied、resource_gone、details_unavailable、cursor_gap、declaration_changed、preview_expired、request_conflict、lease_expired、budget_exceeded、effect_outcome_unknown；“缺权限”不假装“没事件”。App 普通事件操作不应整体要求 app.system.manage，资源检查必须在 owner 上实现。

投递分三条轨道：matched → queued → leased → processing → succeeded，或者明确 failed/needs_user/expired/outcome_unknown。dead_letter 是明确可重试错误耗尽后的停放状态；不确定副作用保持 outcome_unknown，不能点“重试”重发。每次 ack 校验 attempt 和租约，旧 worker 的迟到 ack 不覆盖新结果；attempt 变化不改变业务步骤幂等键。

前台刷新采用 invalidation 模式：合并状态变更通知，重挂载读取授权快照，无持久业务处理承诺。后台自动化采用 delivery 模式，必须持久确认。Mini-App 若需要逐事件处理就声明后台 handler；不能把前台 SSE 收到或 UI 已重绘当作后台任务成功。

### 7.4 队列、排序、保留与故障边界

v1 按 consumer + rule 的处理顺序串行；无关规则允许并发，同一 Bot 会话仍串行。未知结果阻塞有顺序依赖的后续步骤。合并和防抖只对声明允许的状态通知使用；视频产物、好友来信等独立事实不丢弃。每规则/用户有待处理数量、年龄、读取次数、执行时间和模型费用预算；超限进入可见 backlog/paused，不能为推进游标静默丢弃。

启动顺序为注册声明和 owner → 恢复 outbox → 校验 consumer/授权/版本 → 恢复扫描与投递，最后开启领取。提交唤醒之外保留有界轮询，防唤醒丢失；停止时先停止领取再释放租约，未确认的 OS/网络动作不重置为 queued。执行、续租和检查点复用现有 Task/Harness 生命周期，不另建模型循环。

首期不主动裁剪未处理事实；积压有容量告警且有上限。引入清理前必须确定并公开每类保留窗口、最早可恢复游标和删除水位。事件正文可先裁剪，但去重 tombstone 与步骤请求凭据至少保留到生产者最大重送窗口、投递恢复窗口和下游幂等窗口的最大值；不能清空 Event 后让旧 outbox 重送变成新消息。永久保留不是容量方案，未确定清理策略前不开放无限后台订阅。

from_now 以 recorded sequence 为界，语义是“启用后平台接收的事实”，跨库延迟可能带来启用前发生的事实。提供 occurred_at 新鲜度限制且展示这个区别；发生时间 unknown 的事件不进入依赖时间正确性的外发规则。恢复时暂停区间明确记 skip，不重放历史动作。整体至少一次的保证仅适用于声明覆盖、尚在保留窗口且权限持续有效的事实。

### 7.5 因果链与循环触发防护

事件去重只防止同一个事实重复投递。Bot 收到频道刷新完成事件后再发起刷新，会产生新的 run_id 和合法新事实，不能靠 event_id 去重或冷却阻止无限循环。v1 采用以下分层控制。

1. **保留可信因果链。** 独立用户动作或独立定时委托启动新的 cause_root_id；Hook 派生动作保留同一个 root，记录 parent_event_id、rule_id/revision、delivery_id 和实际 operation/task 引用。经 AaAT、异步任务、跨库 outbox 发布的后续事件都携带这条宿主上下文。root 的预算和父子关系持久化，重启不重置。Package 不得自行清空或重置；无法证明来源的动作标 causality_unknown，不能绕过已有护栏进入自动有副作用链。
2. **默认禁止同根规则重入。** 规则匹配后先做原子 root/rule claim；同一 rule_id 在同一 root 内默认只接受一次可执行激活，后续命中写 suppressed:rule_reentry，不再启动 Run。修订号变化不产生新额度。A→B→A 的第三步也因此停止；不能因同一规则接到了新 event_id 就重新执行。不同用户刷新、独立定时轮次各有新 root，仍可正常触发。
3. **精确到资源的效果护栏。** owner 在可信动作声明中描述会改变哪些资源，例如 refresh(channel_id) 会产生该频道的 refresh_finished。来自频道完成事件的摘要委托，默认不允许再刷新同一 channel_id。允许摘要读取与写回 Bot 会话；确需刷新另一个频道需在规则计划里显式声明并受其资源授权限制。可推导的自环在 preview 阶段报出触发与效果链，默认拒绝启用；不让模型选择另一个 Tool 或 provider 绕开相同业务效果限制。
4. **跨规则总预算。** 根链限制最大派生深度、累计激活次数、耗时、工具效果次数和模型预算。v1 建议默认深度 8、激活 20；具体限制随规则可见，不声称是平台性能上限。共享 root 的并发投递原子扣减，超限暂停该因果链并记录 cycle_or_budget_limit。不同 root 仍受每规则/每用户时间窗口额度限制，防外部系统丢失因果信息后形成新 root 风暴。冷却仅作限流，不作为循环正确性保证。
5. **显式批处理与有限迭代。** 默认一次规则激活可能压制同一根下多个合法的兄弟产物。规则预览应说明这点；需要处理批量视频时，优先一次唤醒按批次读取多个 output。确需逐产物执行时，可单独登记宿主验证的 fan_out 计划，以稳定 item_id 去重、限制最大项数，并仍禁止祖先规则重入。v1 不提供任意自动反馈循环；有上限的“刷新直到条件满足”作为一个专用任务内部的有限迭代实现，不能通过相互 Hook 递归。
6. **观察和处置。** 被抑制的事件仍保留事实与审计，不悄悄删除。展示“频道刷新完成→Bot 摘要→请求刷新同一频道已阻止”及关联 root/rule/task。默认只停相关链，其他独立正常订阅继续运行。用户手动重试未知外发不能创建新 root 绕过核对；解除暂停也不重放已抑制的效果。

静态依赖图用于显示风险，不能代替执行期检查：动态模型选工具、条件分支、Package 升级和外部事件都会改变链路。所有入口共用执行期 effect guard，General Agent 只消费受限契约，不写“频道”或 Bot 身份的特例。

验收必须覆盖：同一频道直接自环、A→B→A、多条并发分支重入、Outbox 延迟和重启后的重入、切换 Tool/provider、独立定时新 root、批量兄弟事件、未知因果来源和外部回声。前七类应有确定的计数/抑制证据；外部因果无法完整保存时明确保证边界，用窗口预算和暂停防止失控，不宣称能识别任意外部循环。

### 7.6 实施审查与必测故障窗口

| 问题 | 必须出现的可验证结果 |
| --- | --- |
| 原始内部事件缺 owner 或敏感载荷 | 只能通过可信 owner 适配映射；非业务事件不出现在公共目录 |
| 业务提交、outbox 搬运、标记已发之间分别崩溃 | 未提交不见事实；已提交最终可见且只一个 event_id；冲突可诊断 |
| 匹配落库后、任务接受前或任务完成后回写前崩溃 | 同一 delivery 不多开一次已完成的效果任务；由持久接受凭据恢复 |
| 修改/暂停规则时扫描尚有积压 | 按已记录生效边界解释旧事实，暂停不新提交，恢复不回放 |
| 改 Bot 名字/职责、模型不可用或 provider 升级 | 历史会话不丢；不借其他模型/权限回退；显式暂停或重新授权 |
| 同一事件发给 Bot、App、Mini-App | 独立状态与权限；一个失败不影响其他消费者；旧 mount/旧 worker 无权确认 |
| 文章正文变更、视频删除、角色未 ready | 返回版本/缺失/状态事实，不替换成最新其他对象 |
| 租约失效、重复投递、事件清理、旧生产者重送 | 不覆盖新回执、不扩大授权；缺口可见，tombstone 阻止重复效果 |
| 两个任意测试 provider 各有同名资源 | 不按业务名字分支，不串 scope；发现、详情与执行三层分别拒绝越权 |

## 8. 实施顺序与验收

| 阶段 | 交付 | 可验证的通过条件 |
| --- | --- | --- |
| E1 事件标准 | 类型目录、声明验证、scope、事实索引、事务发布/跨库 outbox；三种首批业务事件 | 使用两个无关测试 provider 验证命名空间/主体隔离；模拟事务回滚和搬运崩溃；同事实一条、不同事实不丢。三个真实 owner 各有一次完整存储路径验证；夹具可代替模型/生成器，须记录替代边界，不能称为真实模型或设备验收。 |
| E2 只读订阅 | 规则预览、from_now 游标、持久投递、暂停和历史；先记录命中，不启动模型 | 关闭 UI、重复唤醒、重启、连续刷新、游标过期、版本升级均可解释；同名频道不串；运行权限与发现权限分别检查；恢复不重放暂停区间，编辑不改写已建立投递。 |
| E3 消费入口与详情读取 | 实现 App 后台任务、Mini-App mount 与 Bot 会话分发；优先经 AaAT 补取详情 | 同一事件扇出给三类消费者；验证一个消费失败不影响另两者、mount 失效停止前台投递、无详情权限只见获准元数据。真实触发“腕表更新→摘要”，按本批次读取而非最新列表；和手动聊天并发不串轮；重开后可恢复 Bot 历史及来源引用。 |
| E4 多步副作用 | 好友来信、固定回复、Todo 和微信的分步回执与撤权处理 | 合成事件覆盖注入、非紧急、回声、重复、部分成功及未知结果；用户指定测试目标单独验证真实发送，不以模型文字或入队代替回执。 |
| E5 Package 接入与发布评估 | 签名声明、版本兼容、依赖停用、配额、积压与保留监控 | 第三方样例不能冒充系统 App，热升级不扩权；记录提交到命中延迟、队列年龄、重复抑制、gap 和未知外发数；区分夹具与实机证据。 |

第一件可合并的工作是 **E1：同一目录里列出三种事实，用真实业务写入验证事件语义，不启动 Bot**。这样可以先验证所有 App 是否说同一种“事件语言”，再让用户用对话把它们连成自动化。实施共享 Agentic/AaAT 行为时运行仓库强制边界门禁及 owner 测试；一旦开始影响 Desktop 的实现，同轮维护发布台账。

实施前复核结论：总体分层保留；按第 7 节冻结身份/版本、消费轨道、后台授权和故障恢复。E1 先限定内置 owner 和三个声明覆盖的业务路径，完成前不把 Package 发布、全媒体覆盖或后台 Hook 列为已交付。

## E3 实施索引（2026-11-02）

[消费执行实施记录](event-hooks-e3-implementation.md) 描述 Schema 103、Bot/App/Mini-App 的实际入口、三个 owner 的 AaAT 详情绑定、后台预览委托及因果预算。E2 规则默认继续只观察；新后台规则须重新预览启用。当前只交付详情阅读、Bot 审阅和宿主事件收件箱，自定义 Package 后台代码、跨 App 写动作与对外通讯发送仍属后续范围。

## E4 与 E5 监控实施范围（2026-11-02）

[最小动作闭环与运行监控](event-hooks-e4-monitoring-implementation.md) 已实现可信冻结动作计划、Todo／本机通知、分步回执、条件判断、未知结果阻断与 Messager 管理页。好友来信加入标准事实目录，离线历史不自动执行动作。外发与第三方 Package 扩展仍待单独讨论，未因动作注册框架存在而开放。


### Package 用户授权实现（2026-11-02）

[Package Event Hook 用户授权 v1](package-event-hooks-user-consent-v1.md) 在 E3/E4 上增加独立授权记录。安装不授权，签名声明只是上限；App/Mini-App 通过宿主申请并由用户审阅，接收事件、AaAT 详情、后台处理和固定动作分别冻结。兼容升级不扩权，不兼容变更要求重新确认；System Control 和 Messager 支持暂停与撤销。Package 自定义后台代码、任意工作流和新的外发渠道仍需另行设计。此前 E3 中已安装 Package 的 legacy digest 绑定入口由此协议取代。


### 系统设置入口调整（2026-11-02）

Event/Hook 的全局规则、Package 授权、通知与运行监控从 Messager 移到 Settings，在 Capabilities & Tools 后增加 Event/Hook（事件/响应）页签。Messager 移除 Automation 全局页签；System Control 保留快速授权管理。此次仅迁移前端入口与现有内容，订阅、后台执行、确认与隔离契约不变，内部内容结构后续再完善。
