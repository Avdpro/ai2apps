# 行程安排：携程接入（2026-10-26）

## 范围与默认值

新增 `ctrip_flights`、`ctrip_hotels`，与 Desktop/Mobile 的行程安排、`travel.flights`、`travel.hotels` 共用 owner 查询、校验、结果投影、公共后台 Browser Task、Mini-App LLM 与隐私机制。General Agent 不新增站点分支。

未指定网站时，境内航线优先携程，北京等中国目的地的酒店优先携程（出发地可以在海外）；其它航线保留 Google Flights，其它酒店保留 Booking。用户显式选择网站始终优先。AaAT 使用默认 `sources: ["auto"]`，也可明确选择实际来源；不允许 auto 与显式网站混合。界面提供自动来源选项；旧草稿的明确来源保持不变。

自动默认判断采用保守的常见城市中英文/IATA 别名和明确中国标识，不以中文输入语言推断地域；不认识的地点仍使用原来源，用户或需求整理模型可以明确选择携程。别名只影响默认网站，绝不用于推断机场代码、站点城市 ID 或真实地理位置。需求整理模型在未指定网站且确定中国境内时建议携程；需用户核对后才查询。

## 查询与证据

携程机票入口 https://flights.ctrip.com/online/channel/domestic ：观察并选择真实城市候选，保持城市所有机场范围；配置单程/往返、日期、人数、舱位后点击搜索。返程沿现有独立单程机制反向查询，不把它与去程往返参考价相加。

携程酒店入口 https://hotels.ctrip.com/ ：分别配置城市、地标关键词、入住退房日期、一间房及成人数。只读可见卡片；位置距离、床型、早餐、地铁等缺少原文证据时不能声称满足。未登录只显示会员价入口时，不编造价格。

所有阶段通过既有 BiDi SDK/公共可见性机制执行。查询仅允许明确的 flights.ctrip.com 或 hotels.ctrip.com 范围；不使用逆向私有 API，不选票、不预订、不付款、不自动登录。登录/验证码沿公共 Task 人工协助。单个网站失败不会自动切换到其它来源重复提交。

## 验证

- 66 项 Python 行程/优化/AaAT owner 测试通过，包括境内默认、跨境不同来源、显式来源覆盖、返程方向、地标保留、公共声明编译与隐私路由。
- 14 项真实 Chrome 隔离页面测试通过，包括390/1100px默认来源及显式覆盖、草稿恢复、隐形卡片剔除、可见航班价格口径和酒店无价格卡片。
- 391 项 AaAT 架构门禁通过，exit 0；现有无头 Metal atexit 警告不影响测试终态。
- 真实公开网站研究：北京—上海，2026-10-27 至 2026-10-30，城市级 BJS/SHA、成人1，实际返回航班卡片并显示往返总价；未点击“选为去程”。酒店公开表单选择北京后出现真实酒店卡片、地理位置、床型与“登录以查看会员价”。随后酒店页跳转 passport.ctrip.com；自动审批拒绝继续读取认证域，没有绕过或访问登录凭据。因此真实登录态酒店价格、完整模型驱动查询和实体 iPhone 尚未验收。
- App-Dev 空闲后经标准 Helper 重启，原生标题端口60082；真实行程安排 UI 显示自动选择、携程机票/酒店，旧行程结果正常恢复。未发起新的付费模型或 Cloud 搜索。未修改 Cloud，也未发布生产 Package/Desktop。

最终激活核对：Dev PID55613/port61441，App-Dev PID55619/port61589，health 均为200。两套实际 Local 日志均报告 `ai2apps/browser/travel_aaat.py` 从当前 `/Users/avdpropang/sdk/omlx-moe-cache` checkout 导入；App/Helper 源根由标准重启脚本核对。原生来源列表验证完成于最终诊断重启前的 App-Dev port60082；最终改动只增加源码路径日志。重新打开行程安排可加载新 Package。未更改旧草稿中用户已选择的网站。

## 三元桥真实失败复盘与修正

真实 Dev Browser Task `btask_234cfb9760f63421c3be045e8920f0ba1357f677c115df1151dbc6fcfdfd2aa3` / Run `run_76463ff9d71f464a9178ea5968178776` 在 location 阶段失败：共8个动作，前3个已完成北京输入和城市候选选择，第4个已填写“三元桥”；后续反复点击同一关键词输入或外层容器、重输相同文本，最终 `ai_step_action_limit`。页面不是认证失败，也没有开始正式酒店查询。

根因是 owner 指令错误：把携程的自由文本“位置/品牌/酒店 (选填)”框当作必须选择地理候选的自动补全字段；同时把城市、区域放进同一个有限动作阶段。原有8次上限是合理的防失控保护，不应靠提高上限修复。

公开携程再次复现：选择北京后输入“三元桥”，失焦后文本保留；直接搜索产生 `searchWord=三元桥`，结果页主表单保留北京、三元桥，返回附近酒店卡片，原文包括“距三元桥地铁站步行220米”。研究使用页面当前默认日期2026-10-26至27、成人2，不是用户11月5至10、成人1任务的完成证明，未获取登录后会员价。

修正：拆分 city/location → dates → party → keyword → Search。城市只核对真实城市候选，日期只处理日历，party只处理入住人数。明确区域使用编译后的原生 input 一次填写，目标是关键词 placeholder，绝不按重复的 destinationInput ID 定位，也不等待候选/自动回车。区域在城市处理之后填写，防止被城市变更清空。未指定区域则检查关键词是否为空；有残留时只用可见清除控件，无法清除时请求协助，不沿用旧关键词。保留结果中地点证据校验，关键词并不自动证明酒店距离满足要求。

68项 owner/AaAT测试通过，新增公用编译执行器夹具验证：三元桥输入只focus一次、replace一次、不submit，不调用planner；另覆盖空区域和旧关键词处理、阶段顺序。架构门禁结果与激活状态见发布台账。旧失败任务不篡改、不自动重放；Dev 中其它人工协助任务保持不变。

本次修复最终验收：391项AaAT门禁全部通过；App-Dev PID56843/port63923、Dev PID57101/port64940，health均200，App/Helper源根与真实运行owner导入路径一致。用户明确授权立即重启Dev后通过标准Helper激活；原携程任务仍为failed，未篡改为成功、未自动重跑。完整用户日期/人数下的新查询仍需重新提交。


## 航线控件定位与视觉恢复（2026-10-26）

本次真实失败为 Dev Task `btask_0b6182d33b89f2dacb539ce95fc692b65ef3bb122fe3b3ecda36c5ceddfe6895`。携程两个城市输入具有相同 placeholder，原 route 阶段同时处理两者；DOM repair 返回非唯一目标后暂停，尚未执行不确定动作。Owner 声明还明确关闭 visual_locating / visual_review，因此已有视觉恢复链路从未被调用。页面仍是默认 SFO→BJS，不能视为用户北京→上海查询结果。

修正：旅行查询启用现有有界 DOM→视觉定位→标记截图复核机制；携程航线拆分 trip_type、origin、destination。未新增浏览器协议或 General Agent 业务分支，不扩大模型权限，不绕过验证码、登录或付款限制。通用执行器使用可信 owner 步骤标签生成可理解提示，保留底层诊断但不把原始 DOM repair 错误当作用户操作指令。

另补齐 origin_airport / destination_airport / excluded_airports，贯穿 Desktop/Mobile 表单、AaAT 声明、优化、每步参数、逐候选证据检查和总结复核；返程交换指定出发/到达机场，保留排除列表。“不要浦东”不能被偷换成未明确指定的替代机场。缺少机场证据或命中排除机场的候选不推荐。总结复核不会修改保存的历史结果。

验证：172 项后台/owner/通用视觉恢复测试通过；14 项实际 Chrome 夹具测试通过（390/1100px）；394 项 AaAT 边界门禁通过，exit 0（现有无头 Metal 退出警告）。视觉恢复验证是隔离模型夹具，包含任意网站/任意标签身份、DOM 无目标后视觉选定及复核；不是本次携程线上完整查询成功证据。

App-Dev 确认无活动任务后经标准 Helper 重启：PID59068、port50760、health200；App/Helper 源根及实际 travel owner / visual recovery 导入路径为当前 checkout。原生行程界面实际显示新增三个机场字段，既有草稿及结果正常恢复。Dev 有3个浏览器任务与4个Agent活动记录，保留用户现场；当前旧 Task 不篡改、不自动重放，仍绑定旧声明。重启 Dev 及重新查询等待用户确认。未新增付费 Cloud 搜索、未发布生产版本。


### 用户授权后的 Dev 实测追踪

用户授权取消旧只读航班查询、重启 Dev 并验证。旧 Task 已因 Run deadline 自动取消，未篡改记录。标准 Helper 首次重启 Dev PID60422/port53307，health200、实际 owner/visual imports 为当前 checkout。Chat 旧会话出现独立 missing_agent_input，另开验证会话避免沿用失效输入。

真实 AaAT 参数确认保留 excluded_airports=[PVG]、2026-11-05、business；执行进入携程 trip_type/origin。Task `btask_7c2a43ad33d4e4a20803005221ff04da624ac2ef0ae7a3d71f67459808f95d22` 未得到报价：公用匹配将长意图中的“出发地”短标签按50分子串匹配直接点击，随后页面到 fuzzysearch/search；origin 重新观察、DOM repair 后真实进入视觉 select，仍无可选控制而安全暂停。新提示正确说明“选择出发城市或机场”，不再暴露原始 DOM 错误。已通过标准取消按钮终止本轮任务，没有预订/付款。

进一步修复公用 Python/JS 目标匹配：不再将“节点短标签出现在长意图中”作为直接可操作证据；搜索加分仅用于明确 search/搜索目标，不能让包含 search 的叙述匹配任意搜索控件。明确 ref、精确标签、目标包含在实际标签中的窄匹配保留；弱匹配交给已有 AI/视觉恢复。新测试使用非旅行 Workspace/搜索标签及中文表单，证明机制无业务身份分支。104项后台/恢复测试、7项JS测试通过。

第二次标准重启激活：Dev PID61197/port54480，App-Dev PID61309/port54913，两者health200、实际travel owner导入为当前checkout，App/Helper源根核对。Dev实际提供的 browser_bidi_client.js SHA256 与checkout完全相同。新的实测正在独立会话运行，尚不能声明完整查询成功。


最终真实验收限制：第二轮 Task `btask_276729dba10da8065af9831a060705c9394765dbd1a5c683bd9b95ae48813923` 发现主表单 li/span 控件被公共观察遗漏（旧候选 items 没有单程/往返，但可见 HTML 明确有两个 li）。共享 snapshot 增补 pointer li 并与相同文本子 span 去重，不暴露隐藏或普通列表内容。新增真实Chrome夹具通过，完整15项Chrome、7项JS通过；最后394项AaAT门禁通过。快照按调用从当前源码读取，无需再次重启；SDK快照请求版本已更新，实际served snapshot SHA256核对一致。

继续同一个新任务后，回读出现真实 li 节点：e724“单程”、e725“往返”，证明遗漏修复已在真实页面生效。但原生输入抛 RuntimeError；执行器记录 action_outcome_unknown、automatic_replay_allowed=false，未擅自重放。独立酒店 Task `btask_c7f7896c2bf6b6130c2caef31addd8b8e8c15310894e44810170300fc6442704` 在 location 也记录同类原生输入不确定异常。当前记录只保留异常类别，不能据此断言具体是窗口可见性、激活还是输入派发；未将此前其它Task的visibility日志冒充本次原因。

两条本轮验证Task及父Run均通过标准UI停止，DB确认 cancelled；没有留下本轮收费模型循环，没有预订或付款。结果：Dev/App-Dev激活完成，AaAT结构化机场约束和真实视觉恢复调用、真实列表节点覆盖已验证；完整航班/酒店报价未通过，后续仍需定位原生输入失败并补齐现场验收。不要把fixture通过等同于完整真实流程通过。


## 携程整体流程继续完善（2026-10-26）

用户要求继续跑通，并以携程适配整体优化而非该行程特判。先验证现有原生输入链路：固定Dev原生BiDi一次性隔离容器验收通过（点击、中文长输入、上传、durable后台执行）；另以新窗口/后台标签两种布局及原失败Task同一已绑定Profile的一次性本地测试标签验证，点击均有实际readback。独立真实携程查询标签的单程li原生点击也成功，页面仍为正式查询入口。这些隔离探针不等于完整后台行程通过。

为进一步捕获仅在后台执行出现的异常，增加Local原生输入失败位置异常日志，不输出页面、输入参数或凭据；维持不确定动作禁止自动重放规则。Dev仅保留此前已告知并获重启授权的两条Booking/Expedia等待记录，标准Helper重启PID63310/port57364，health200；App-Dev空闲后标准重启以继续诊断。当前完整流程仍在调查中。


### 通用宿主可见性根因与修复

本轮 Dev 真实任务 btask_c43e95844be95bec748586f9870a6fcddce86781f6305e8a396afe021543ebe3 的新异常日志显示：pointer_to 在 activate_for_input 阶段失败，尚未调用 input.performActions。Task window 处于 active/normal 且有焦点，但 document.visibilityState 为 hidden；native unhide/activate 未消除 occlusion。正常 Launcher 路径未携带 Helper 冷启动宿主已有的 BACKGROUND_HOST 标记，而现有 Gecko 原生补丁仅对 agent/background host 保留渲染。

共享 Swift ShellHostEnvironment 统一两条启动路径；SHOW_SHELL 单独声明交互式 Launcher 显示主界面，避免把“保持渲染”与“隐藏启动”混为一谈。沿标准开发构建器更新固定 App，不改 Gecko、不创建新身份。新增 NativeInputNotDispatched 区分窗口准备失败与派发后不确定，通过普通/视觉执行链传播；后者仍不允许自动重放。2 项 Swift 测试、105 项 Python 回归、394 项 AaAT 门禁通过。原生探针通过不等同完整携程报价验收。

### 无角色候选浮层的真实覆盖

新 Dev Task btask_628eb35aaabf1fab6e4c181efaefcedb4b93d6cbd0b856d1606c65af8c51dcac 已越过 native click，单程与北京输入成功；随后实际城市候选为无 role、无 cursor:pointer 的 div/li，旧 Probe 仅正文看到“北京(所有机场)BJSBJ”，并未暴露可操作 ref。共享快照补充当前输入框的 sibling popup 与紧邻输入框的 absolute/fixed 浮层，只观察有尺寸且可见的叶行，优先于页脚导航；不认识城市名、站点或日期，也不修改页面事件/值。角色缺失的表格日期和无 href 指针链接也纳入既有 pointer 控件观察。

真实 readback 现有完整城市行 e1020，AI 已成功完成 origin/destination。日历另有 portal 浮层（无角色、cursor auto）；补充锚定浮层后完整日期格进入 Probe，真实 dates 阶段已成功，继续验证人数与舱位。16 项真实 Chrome 夹具（含任意 Workspace/2031日期、不相关及隐藏节点排除）和9项共享 JS 测试通过。两固定 App 标准构建/严格深度签名通过，App-Dev 原生标题 port61455、Dev port60622；两端实际 served snapshot/SDK 字节均与 checkout 相同。

最后 AaAT 全门禁一次出现并发确认测试 SQLite database is locked（393过/1失败），该单测独立复跑通过；此前全394通过，当前再次跑完整门禁验证，未修改其权限或断言以掩盖问题。现场询价验收仍在进行，不以中途阶段通过声明完整成功。

### 菜单锚定与准备动作边界

第二个干净航班 Task btask_e870a5a30afd24bf93eb31aa4b1450bef1e697e8a045aea8340846e778609b6e 在无人辅助下成功完成 open/access/trip_type/origin/destination/dates；party 仍缺少非输入框菜单的 roleless 候选。共享快照现在被动观察 isTrusted pointerdown，仅将最近真实点击节点作为可见浮层观察锚点，不记录输入文字、不合成点击、不扩大动作权限。第三方合成 pointerdown 不能建立锚点。17项 Chrome 回归通过，含任意 Category 菜单 fixture。

第一轮 party 的 foundation_submission_disallowed 还暴露公用否定表达误判：description 中 Do not submit 触发粗 substring guard。统一 requests_submission 处理明确否定表达，真实 press Enter/submit 仍被准备阶段阻断，目标效应保护保留。112项浏览器/恢复回归通过。

App-Dev 酒店 Task btask_7cb4e0bcfedc7fced5d9e65041df97ecce4b1bae8c575ca92c09ad80279b02f5 被 foundation_action_outside_contract 拦住（未派发）。规划提示列出 open，但 owner preparation_only 禁止 open。新增无业务身份的 step_policy.allowed_primitives 供 planner 与 executor 共同使用，模型越界动作在 JSON repair 预算内重新规划，绝不扩大 allowed operations。27项模型路由/边界测试通过（两任意 provider 身份验证越界 open 修复为 observed-ref click）；完整394项AaAT门禁再通过。Dev旧验证Task/父Run已停止，App-Dev已无活动任务，通过标准 Helper 分别重启以激活。最终报价验收仍在进行。


### 人数装饰图标与携程舱位语义

酒店本轮已成功完成 location/dates，party 因8次重复点击数字容器而失败。隔离公开首页探针证实，人数加减按钮实际为有尺寸的 i[aria-hidden=true]，在 tabindex=0 计数器内部；aria-hidden 是装饰语义，不代表 CSS 隐藏。共享可见性增加仅供控制观察/命中复核使用的 controlIcons 窄选项：仅可见 pointer i/svg 且有焦点控制祖先，CSS隐藏/惰性/透明或aria-hidden祖先仍排除；普通内容读取默认不变。无文字图标即使精确 ref 也必须视觉复核，单击后readback与不确定禁止重放保持。18项Chrome、9项JS、28项视觉恢复测试通过。Ctrip owner 明确区分数字显示与两侧加减图标。

干净航班 Task btask_84763396d6362f3019e8e04dcc15adf3e6ecede5e425799953ae47086dd04258 已无辅助完成准备全部阶段和 search，进入真实结果页；preferences 因重复打开舱位筛选而暂停，继续回读中。owner补充携程组合“公务/头等舱”仅为搜索入口，实际商务舱/公务舱仍逐卡验证，不把头等或无舱位证据当商务推荐；主查询页只有儿童/婴儿附加选项时使用成人单人参考票价，不编造成人数量控件或多人总价。机场UI筛选不可用时不阻塞提取，owner仍严格排除命中/不明机场的候选。具体城市/日期不进入通用基础设施。

### 真实航班结果已取回

Task btask_84763396d6362f3019e8e04dcc15adf3e6ecede5e425799953ae47086dd04258 / run_9f480583c4e04637acfda765d1ed14be 已完成。原生读取7张卡，页面显示北京(BJS)→上海(SHA)、2026-11-05；卡片实际为大兴→虹桥T2，公务舱。最低观察到上海航空FM9102 ¥1187起，其次中国联合航空KN5955 ¥1220起；均是当时页面参考起价，未核对税费/退改/行李，不作当前票价保证。未点订票或选票。

结果 owner 原先只认商务舱/business，漏认携程用词公务舱。现补充等义词，仍拒绝单纯“公务/头等舱”组合筛选或头等舱卡冒充商务。对保存的同一真实 Task.result 重新运行正式 project_result 得到 complete、criteria_verified=true、6条候选且6条recommended；保持逐卡quote、价格substring、机场证据校验。没有重抓网页或改写旧Task证据。原生流程在preferences曾经暂停一次，调查者通过标准继续重读后完成；不冒称此轮全程无人工续接。未来owner规则已说明组合舱位和不可用UI筛选不应重复设置。Dev父会话结束后按标准Helper重启，完成结果可由既有task读取路径以新owner重新投影。

### 配置的图片识别路由复用与隔离

App-Dev 文本任务模型缺少图片声明，导致 location 自动恢复暂停。共享视觉机制现在先用当前已声明可视的任务模型；否则只尝试同一 effective profile 显式配置的 image_recognition 路由，且仍检查已启用与肯定图片能力声明。无任意候选/复杂度跳转、不改全局配置、不从普通配置继承到隐私模式。更新了视觉恢复合同并记录开发评审理由；两个任意 provider、normal/privacy、系统隐私升级、缺失模型元数据测试均覆盖。App-Dev 配置的识别路由是 cloud/openai/gpt-6-luna，但本机目录没有其图片能力声明，因此保持不发送截图；相关验证Task/父Run已通过标准UI停止。使用Dev既有已肯定声明支持图片的任务模型继续完整酒店验证，并未伪造元数据或切换用户全局模型。

最终当前源码217项相关Python回归、18项Chrome、9项JS及394项AaAT门禁通过。两固定App的原生身份、深度严格签名、源码根合同保持；最新Dev PID9111/port54391、App-Dev PID9106/port54393，实际提供snapshot/visibility/SDK三份资产全部与checkout一致。真实酒店Task btask_c538e4014cd8b4c9b1ef65388ed4c0dccd3abaf50742d4bddfa034f1ee8070d5 正在执行，城市选择已通过。

### 模型输出错误不再冒充浏览器派发错误

Dev 酒店 Task btask_c538e4014cd8b4c9b1ef65388ed4c0dccd3abaf50742d4bddfa034f1ee8070d5 在 dates 的模型下一步规划中出现 JSONDecodeError，已做两次模型修复后耗尽；并非 input.performActions 报错。旧模型修复代码把完整 OpenAI envelope 字符串当成 assistant JSON 内容，已改为传真实 message.content。仅遇 finish_reason=length 时，把下一次同模型、同观察、有限修复请求的max_tokens从2400增到4800、最多8192，不重放浏览器输入，不按站点或模型名分支。新增跨任意模型的截断修复测试；修复耗尽返回明确 browser_planner_invalid_decision、action_outcome_unknown=false，而非“浏览器命令可能已经生效”。调用次数/步骤/原Task预算继续保留。146项相关回归通过，最终门禁与现场重跑继续中；本轮失败父Run已停止，精确Helper重启两固定实例。

### 初始状态检查也是实际证据

后续dates仍出现两次决策校验失败、最后一次finish_reason=length空正文，现已记录不含页面/参数的validation phase、正文/推理长度。代码检查还发现 interpreted inspect 源指令与 completion gate 的矛盾：owner明确允许条件已满足立即完成，但模型完成必须至少一次successful attempt。公用执行器现在将刚刚通过SDK实际获取、且URL仍在授权scope内的初始observation登记为inspect成功证据；不伪造点击，不给click/delete等效果步骤补凭据，不允许越域完成。两任意provider测试确认已满足检查无需新动作即可完成，效果/越域仍拒绝。精确ref无文字图标的视觉复核也保留完整原动作描述（不是仅“click eNN”）。150项相关回归通过；本轮旧测试父Run已停止，两固定实例标准Helper重启激活，继续同条件酒店真实查询。

### 观察与编译 Probe 一致性

上一轮日期阶段日志明确为 compile 阶段拒绝，不是完成判定失败。共享快照此前把超过 maxItems 的候选也标入 HTML 的 data-ai2apps-ref，规划可以选择 HTML 可见但受限 Probe 未收录的编号。现只为实际输出控件标注 ref；规划/显式 ref 定位统一为 600 个控件，普通语义定位仍 150，浮层/role=grid 优先。Python 与前端 SDK 保持一致，不放宽正向观察要求。另修正 planner 的 permitted 操作集合被 context 集合覆盖的变量混淆，并只记录静态编译错误码，避免泄露页面内容。

19项真实Chrome交互fixture、9项共享JS测试、69项背景浏览器Python、103项视觉/Probe/模型/旅行owner回归通过。通过标准Helper重启两固定Local，Dev60038实际导入当前源码且快照/SDK服务字节匹配。新真实酒店Task btask_18dc0bdf03d4c16fab03bad79ce0f98329ed22e15579d11b9a3d34ca03e11b2c已无辅助通过location/dates，进入party，最终结果仍待验收。

### 酒店表单已走通，真实携程要求登录

Dev Task btask_18dc0bdf03d4c16fab03bad79ce0f98329ed22e15579d11b9a3d34ca03e11b2c / run_47d48db6b7e04659841cad64f915c464 全部自动完成 location、dates、party、keyword。Search 实际已提交，携程将结果页重定向 passport.ctrip.com/user/login；backurl 保留上海、五角场、2026-11-05/08、1间房等已确认条件。真实酒店候选尚不可读取，不能冒称推荐已验收。没有预订、支付、绕过登录或改用其它Profile。用户已被提示在已打开的分身登录，当前任务与页面保留。

原先该实际登录要求被视觉复核失败掩盖为 visual_action_unverified。共享执行器增加只读、限定当前/owned相关窗口、现有scope内的登录/CAPTCHA确认；不重放输入、不自动点认证、不读凭据值，保留 action_outcome_unknown 和 no-replay。通用页面访问检测识别专用登录标题+密码表单/登录path，优先于登录页上的“验证码登录”选项，不把普通页头登录链接当拦截。127项背景/访问/视觉Python、20项Cookie/读取JS通过；19项既有Chrome及新增专用登录/导航/CAPTCHA真实浏览器fixture通过（新增fixture首轮编码缺失，补正确UTF-8后独立通过）。394项AaAT门禁再次运行。

通过标准Helper重启空闲App-Dev以激活最终登录修正；Dev60038保留待登录页面，最终Python登录修正待安全重启。两固定App/Helper源码根、实际模块路径、服务快照/SDK/可见性资源字节均匹配当前checkout。App-Dev PID13073/62270，Dev PID11639/60038。使用当前源码只读调用标准BiDi DOM助手对该真实owned登录页核验，结果needs_user/authentication；未读取账号密码、未截图、未输入或提交。航班真实结果已完成，酒店受携程认证阻断，最终酒店推荐和物理手机尚未验收。

最终登录修正后完整AaAT边界门禁394通过（exit0；已有headless Metal atexit警告仍在）。当前Dev保留真实待登录Task和父会话，没有为了激活后端改动中断它。App-Dev已激活最终修正；Dev最终登录提示修正等待安全Local重启。任务继续和酒店最终推荐取决于用户完成当前分身登录；没有自动假定登录完成。
