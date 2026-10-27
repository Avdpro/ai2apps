# 行程安排 Mini-App

首版是 AI Browser 的独立源 Package `ai2apps/trip-planner`（Mini-App `ai2apps.trip-planner`），Desktop/Mobile 使用同一表单、草稿与后台 Browser Task。通用 Agent 不包含行程特例。

## 用户流程

1. 自然语言说明去哪、何时、多久、出行目的；可直接手填。`prepare` 只通过公共 Task 模型整理需求，缺项提出问题，不访问旅行网站。相对日期参考当前设备日历，推断值必须在表单确认。
2. 可选“使用当前位置”：已签名声明中的 `device.location` 可选能力只允许请求宿主确认。宿主显示权限说明并通过当前设备的原生 Web Geolocation 读取位置，手机不使用 Desktop 定位。用户同意前不读位置；拒绝、超时、不安全环境、定位不支持均退回手填。返回经纬度保留两位、精度至少 1500 米；坐标不写草稿，但用户继续整理时会进入所选模型的持久 Task 输入。坐标并非已确认城市/机场。原生浏览器是否提供定位仍需对应系统许可及真机验证。
3. 确认出发地、目的地、往返日期、行程晚数、人数、商务/旅游/混合及偏好。酒店入住/退房日期独立，避免跨时区导致入住日误判。首版单目的地、往返、1–90晚、1–6成人、一间房；不支持儿童房型、单程/多城市。
4. 自选 Google Flights / Expedia 机票、Booking / Expedia 酒店、观光建议。Expedia 机票须填写确认的机场代码（如 SFO 或 Tokyo (NRT)），不猜机场。每源独立提交既有公用 Browser Task；结果随来源完成陆续显示，登录/验证码复用原任务人工暂停/恢复。各任务状态仍来自 Browser Task，不创建第二个执行/调度循环。
5. 点击“帮我安排行程”，仅引用当前 Profile、同一行程、同 Mini-App 已完成的查询结果。未完成来源不阻塞其他来源；建议明确只基于已完成部分。商务保留工作时间、通勤及缓冲，旅游按兴趣、地理位置和节奏建议。所有预订和付款留给用户。

## 所有权与证据

- `browser/travel.py` 属于该 Mini-App，拥有日期/范围/来源校验、固定站点查询 URL 构建和证据投影。公开 capability 为 prepare/query/summarize；当前通过源 Package WebAgent 声明供宿主调用，未额外注册新的 General Agent AaAT 工具。
- 模型复用 `resolve_task_model` 与共享 Task LLM 路由；默认 normal，可显式 privacy；系统隐私模式单调升级，模型未配置在提交前拒绝，不读取旅行页后再报缺模型。
- 页面只经原生 BiDi 公共 `read_page` 访问，使用清洗后的可见网页文本。没有新增 DOM Actor、语义浏览器协议、反爬绕过、Cookie/API 探测、自动登录或预订。
- 网页提取最多六个候选。候选必须包含原文连续引用；owner 验证 quote 确实存在于已读取文本。价格必须为 quote 的原文子串，否则移除。URL 来自实际读取页，且须属于所选来源 HTTPS 主机，绝不使用模型生成的链接。
- “来源页面链接”通过 owner 投影的 links 与现有 open-result 通道打开；这是已观测页面入口，不等于有可预订候选。Desktop 在所选分身打开；Mobile 在手机新标签页打开，不离开 AI2Apps。
- URL 预填参数不证明网站实际应用了筛选。结果会展示 criteria_note 和原文，所有候选均为待用户核对的网页线索，不声称已经确认日期、余票或最终含税报价。网页只显示加载、访问限制或无结果时，返回空/partial；不由模型编造。
- Google Flights 通过实际城市/日期/人数/搜索步骤配置表单，酒店使用审核后的住宿区域查询；读取可见结果卡片。站点可能出现登录/验证或控件变化，必须如实展示，不能宣称所有来源已通过实时验收。
- 观光来源首版为 Google 可见搜索页的线索，不代表已全文验证开放时间/门票；建议必须保留该边界。
- 持久草稿保存行程与原 Task 引用。刷新只读/观察现有 Task，不重新查询。已确认失败后的用户重试用新请求键，未知提交重用原键；无自动预订或效果未知重试。

## 共享小机制

`device.location` 是有签名声明、每次宿主确认、原生权限和 live mount 约束的通用设备数据请求，不识别 Mini-App 名称。任意不同身份声明都按同样规则处理；不声明则拒绝。确认不放宽其他能力。`links` 是 owner 显式返回的已观测来源入口列表，open-result 仅匹配 items/articles/links 中的 URL，不扫描任意嵌套文本。

当前 UI 为中英文，其他应用语言回退英文；入口名称/简介提供既有九语言。后续可补全其他语言正文，不以模型实时翻译替代固定界面文案。

## 验证记录

2026-10-22：owner/公用 WebAgent 后端 45 项通过（行程 22 项 + 原 Mini-App 23 项）；AaAT 必需门禁 224 项通过。Node/Chrome 17 项通过，其中新行程测试覆盖 390px/1100px 逐源展示、来源勾选、手动总结和刷新恢复不重复提交，定位测试覆盖确认前零调用、拒绝零调用、坐标降精度；其余为公共桥接/错误展示回归。

扩展跑到既有 `test_mini_app_llm.py` 时，12 个模型调用 fixture 因未提供当前实现需要的 `mounted.mount` 报错；失败位于此前已有的 `_task_completion` 路径，不是此次改动的定位 probe 分支。没有修改共享 LLM 路由或为通过测试弱化权限；此次 Task 模型/系统隐私前置检查另由 owner 三种 Profile 测试覆盖。故不宣称全仓测试通过。

固定 App-Dev 已由自身 Helper 重启到 PID 41380、端口 60609；App/Helper 的 DevelopmentSourceRoot 均指向 `/Users/avdpropang/sdk/omlx-moe-cache`。实际运行日志证明 `browser/mini_apps.py` 来自该 checkout，实际 HTTP 返回的 `studio_mini_apps.js` 与源文件逐字节相同。原生 App-Dev UI 已发现“行程安排”并打开完整表单，分身就绪、无启动错误。首次激活时行程 owner 模块尚未在该实例提交真实旅行任务，原生 Geolocation 未请求用户许可，没有执行真实预订。

Dev 有两个等待输入的 Agent 会话；用户明确选择“保留会话，稍后重启”，因此未重启 Dev，新后端在该实例仍待重启。不复制旧快照、不改固定 App 标识；Test/生产未改。浏览器夹具用于确定性验证 Desktop/Mobile 展示、逐源更新、手动总结、状态恢复与定位确认；夹具不代表真实旅游网站价格、手机原生定位或预订验收。


## 2026-10-22 实测问题修正与激活

- 原 Google Flights q 参数被实际网页忽略，任务只读到首页。改为原生 BiDi 公用解释步骤分阶段设置出发城市、目的城市、日期、人数并点击搜索；保留 preparation_only 守卫，最后由 owner 可见卡片读取器读取候选。尚待完整后台任务实测。
- 新增 hotel_area 审核字段，旧草稿明确“住宿在…附近”短语迁移；Booking/Expedia 酒店地点实际包含地标。独立临时页真实检索已经返回 Summer Palace 与12酒店卡片，位置说明含距地标距离；未预订。
- 酒店改用可见卡片读取，保留原始 ID/标题/quote/实际详情链接，模型只对这些候选评分、说明推荐理由。日期/地点条件未核验、位置未知或只有距市中心距离时不能标成推荐。空结果与 partial 不再显示业务成功，可手动重查单一来源。
- 公共访问检查先安全关闭带明确关闭按钮的可选登录优惠提示；真实登录墙/验证码/条款仍等待用户。公共快照补齐标准 ARIA option/menuitem/treeitem/gridcell，并优先开放对话框/listbox，避免选项被背景列表截断。没有站点名分支或 General Agent 业务特例。
- 复用可信 owner_reader 精确 caller/action 机制；重启时从本 owner 的 App实例恢复注册，新提交按可信声明注册；共享执行器继续验证 Run/Task/caller/context。原公用 Task 为唯一执行源。

修正回归：2026-10-22，相关 Python 62 项（含 owner 卡片 reader、区域迁移、真实表单阶段、推荐证据与公共访问检查）通过；AaAT 边界 232 项通过；Node/Chrome 公共可见性、共享快照、可选登录提示和双端行程流程15项通过（最终空候选标签版本又通过其中9项）。原生 BiDi 独立临时页验证 Booking“颐和园, 北京”返回 Summer Palace 和12条酒店卡片，其中卡片有“0.7 miles from Summer Palace”等实际位置证据；没有预订或支付。Google 原生页面已证实提供城市自动补全，并已修复其标准 ARIA 选项观测。完整修正后后台旅行任务仍待 App-Dev 重启后验证，不能当作已完成全链路验收。

用户已批准“取消旧查询并重启验证”。通过正常 Task 取消入口取消旧 Booking，App-Dev 空闲后由自身 Helper 重启至 PID51819/port59816，App/Helper 源码根、Local 导入 mini_apps.py/builtin_apps.py 和三份服务JS均核对。真实后台 Booking Run `run_4fd9ffd821884deba07191a9b53afd7d` 完成，核验 Summer Palace、11月1–6日、1成人，UI显示6家候选及距离/五晚USD合计价格和推荐理由。Google城市选择后的值未在公共观测中传递，模型重复填写；新增非敏感表单当前value及规划上下文，密码/OTP值遮蔽，并在空闲后再次重启App-Dev验证。Dev继续保持原会话，不重启。

最终航班实测进一步发现模型携带“名称（ref eN）”时未按明确引用定位。公用 Python/JS 定位器现支持完整 ref 及末尾明确引用注释，已失效引用直接不命中，不能模糊回退到其他控件。任意站点同规则，无旅行身份分支。63项共享执行器/规划上下文Python和2项SDK回归通过。表单值及明确引用版本各AaAT245项通过（退出码0；仅既有无Metal设备atexit警告）。新Agent会话自行结束后再次确认空闲，标准Helper重启至PID52693/port65293；App/Helper根与当前服务snapshot/client字节核对。最终真实航班验证继续进行，未中断其他会话。

长日历进一步暴露屏幕外日期节点挤掉可见完成按钮：公共快照在开放弹层优先后，再按当前视口排序，仍保留屏幕外候选作为后续观察，不绕过可见性/输入检查。真实Chrome长日历夹具及双端UI共8项通过；SDK缓存版本已更新。

Google最终Search阶段由owner固定为compiled click Search，避免模型尝试键盘提交而触发preparation_only守卫；守卫未放宽。结果卡片读取补充旅客/成人/往返舱位控件并在页面稳定后有限等待，防止只读到加载过渡页。62项owner/公共Mini-App/访问检查回归通过。

最后一轮暴露Google日期文本未提交：移除“优先ISO输入”指令，改为实际日期格选择，独立dates_commit阶段确认Done关闭且主表单值正确。owner26项通过；空闲后标准重启App-Dev，继续真实验证。

控件引用统一为目标描述中的唯一eN标记，存在多个不同ref或过期ref则不命中，不做模糊回退。共享Python48项、SDK2项通过，最终AaAT245项通过。连续重启中一次旧Local尚未退出引发租约冲突；确认无活动任务/无租约持有者后，仅退出确切App-Dev Helper并重开固定App，Local恢复PID53859/port60908、health200，运行导入三模块与服务脚本字节核对。Dev未动，实例数据未改。


最终验收：Google Run `run_63abef7266d447b59ca139dfc7fcc276` 实际核验旧金山→北京、2026-11-01/11-06、1位成人并读取9张原生航班卡片。模型选6张；NBSP/普通空格差异仅做空白规范比对，返回仍为原生quote，内容改写继续拒绝。27项owner回归通过，既有已完成结果直接恢复5个推荐航班，另1个改写内容候选剔除，无需重搜。Booking Run `run_4fd9ffd821884deba07191a9b53afd7d` 保留6家颐和园附近酒店及位置/价格/推荐依据。最后空闲标准重启至PID54059/port63299，health200、App/Helper根、实际导入三模块与服务脚本字节核对。Dev/Test/生产未改，未预订或付款。Mobile共用owner/Package展示，已通过390px夹具，未在手机真机复测。

UI acceptance: the exact App-Dev Shell at port 63299 restored the saved trip without resubmission and visibly showed 5 recommended Google Flights candidates and 6 Booking hotels near Summer Palace. Both source sections display completion and their observed evidence. No reservation or payment; Dev remains untouched.
