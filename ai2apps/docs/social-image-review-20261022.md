# 社交账号 AaAT 图片读取

社交内容语义归 AI Browser `social.account` owner；General Agent/AS 无平台分支。X 实际帖子照片、小红书账号核验后的详情轮播图通过原生 BiDi 截图，交给当前发起对话的模型读取。不是控件定位的视觉复检，也不代表视频已分析。

- 每帖默认读取前两张，先完成各帖默认部分，再按当前模型结合用户问题提出的 `request_more` 分批追加两张。
- 每个 Browser Task 最多 50 次图片模型输入、总计 10 MB JPEG；单图最长边 1280。当前模型无声明的图像输入能力时保持未看并给出原因，不改用另一个模型。
- 原始帖子文字、图片、OCR/描述均为不可信数据。模型只能返回已提供图片键的观察，不能提供新 URL、操作或授权。
- `media_review.images` 保存图片来源、顺序、状态、观察内容及局限；`media_coverage` 汇总预算、已看/未看、部分读取。超长图仅有界截取，标记 `partial_image`，不冒充完整读取。头像不计入帖子媒体。X 静态视频封面作为 video_cover 独立标记并可读图，不能据此声称审阅过视频正文；不主动播放视频。X 以已观察到的同帖图片链接打开大图；小红书排除轮播副本，使用稳定图片标识去除带时效路径和缩放参数的重复。过期置顶帖不消耗当前时间窗读图预算。
- 任务尝试先持久化预留，不自动重复未知结果的模型调用；空白、遮挡或不可读截图不记为成功；成功观察按用户/Session/Profile/平台/账号隔离缓存。相同任务恢复不会重花预算；用户要求继续时，新确认的 Task 有新 50 张预算，优先复用成功观察，只将未看图片传给模型。缓存不跨用户、会话或分身。
- 图片由刚读取 DOM 赋予临时引用，截图前核对同一源、尺寸和可见命中；不可见轮播图片可通过观察到的分页控件切换并回读。失败保留未看，不能对未检查完配图的帖子下“不含某主题”的结论。

验证状态：图片读取、预算、持久化去重已实现；真实 Dev 两个指定 case 与跨重启去重已核验。图片覆盖不完整时如实返回 partial，具体证据如下。

## 最终验证记录

- Python owner/图片预算/隔离/跨 Task 去重/当前模型/格式修复回归：46 passed；独立 Chrome DOM：8 passed；最终 AaAT 边界 gate：252 passed，exit 0。JSON 格式修复只重发文本，最多沿用公共两次修复预算；修复后的视觉证据必须能在原始响应文本中找到，否则保持未看。该修复路径为夹具验收，不宣称每次模型响应都可修复。
- 真实 Dev 当前模型 `cloud/deepseek/deepseek-flash`，三个验收 Run 均绑定 Default 的同一个原生 userContext `3fff454d-4118-4ea1-8bbe-f2afb5e5ec27`，未启动独立浏览器。
- F1：`run_cb389eeb80f1431d88fa659051ec2357` / `btask_18a887dd7de1e8904797a6ae57c4704782b514ecfd5469f036e9f2e40329ea1e`，配图源为实际观察到的 `pbs.twimg.com/media/HVJKx1bW8AAgfPu`，当前模型读到 **KIMI ANTONELLI ... WINS + RUSSELL FINISHES P9 OR BELOW + HAMILTON FINISHES P5 OR BELOW**，usable=true。另张图未核验、视频未分析，整体覆盖仍为 partial。用户后提供截图对应的是这张 Kimi 条件图，不能与更新的 “The hunt is on” 图混淆。
- 小红书：`run_239bce83f96e4513ba7bf3aa512f5a28` / `btask_f4643e8df688dfbd97d0a3bcf36327aa5226ce09f04e857d89593b9306ddb52c`，同帖两图实际识别《THE ADVENTURES OF TINTIN / EXPLORERS ON THE MOON》及月相腕表、海鸥与海岸；另一帖一图响应 JSON 失败保留未看。
- 重启后继续：`run_9408ee4cbcb140bf9b1f372dce92e900` / `btask_cb7c3ac58a556fc50e2d16a6caadc6aaf4ea8d3f9332d9be59a5e9640b375525`。先前成功的两张图与新增模型输入键交集为 **0**；本次只新增传入3张（约378 KB），成功补读上一帖未看腕表图，结果累计已看3、未看10。新扩展多图帖的格式错误诚实保留，未宣称全图读取成功；随后加入并夹具验证上面的文本修复机制。
- 最终空闲 Helper 重启激活：Dev PID91694 / port56768。App/Helper 源根、实际 Local 日志 `social_media.py`/`builtin_apps.py` 均来自 live checkout。无静态资源变更，不需重建 App。未改 App-Dev、Test、生产；无社交写操作。

最终 Dev Chat 已打开 F1 会话；原生界面可见最新结论“确认存在 —— 该配图明确写着 RUSSELL FINISHES P9 OR BELOW”，并列出已看/未看与原始 OCR。验证结束时无活动 Browser Task 或 running/queued Agent Run。

## Chat 执行进度（2026-10-23）

社交 owner 经既有 Browser Task 持久 progress_snapshot 上报解析、提取、详情阅读、
图片阅读、整理阶段。计数为去重后的已提取帖子、成功阅读详情、成功查看图片；图片
包含同 Session/Profile/账号成功缓存，未看/失败不计入。X 一跳原帖的详情和成功图片
也计入阅读量。数字表示实际观测工作量，不代表整个账号的总量或完整覆盖率。
AaAT 等待器读取同一快照，保留累计计数、真实人工等待与终态，并去重未变化的投影。
不新增 Chat 业务分支、任务调度或授权；未提交独立百分比估算。
定向社交/图片回归 55 passed，新增唯一证据计数及持久快照到 Chat 的等待/终态去重测试。
当前是自动化夹具验证，运行中开发实例激活和原生 Chat 实测另行记录。

进度改动最终验证：定向 Python 55 passed（包括真实 owner 执行夹具的逐条详情更新和
图片批次回调）；既有隔离 Chrome 通用计数更新/重新挂载恢复测试 1 passed。
完整 AaAT 门禁 254 passed / 1 failed：test_provider_parameters.py 的
`test_configure_form_returns_arguments_without_generation` 要求图片编辑表单不带 install，
当前图片 owner 描述返回该字段，单独重跑同样失败；本轮未修改该图片表单路径或放宽测试。
门禁不是全通过。
空闲检查确认 app-dev 的 Agent Run/BrowserTask/SystemTask 无活动项后，经该实例标准
Helper.restart_local 激活。Local PID58400 / port56259；App/Helper bundle ID、instance、
Development 和 live-checkout source root 已核对；新启动日志实际加载本 checkout 的
social_media.py 和 services/builtin_apps.py。原生窗口标题为
AI2Apps-App-Dev: App-Dev 127.0.0.1:56259。无静态资源变更，无需重建 App。
本次没有新建真实社交读取任务，未冒充新平台读取的 live Chat 进度验收。
Dev/Test/生产未重启，无 Cloud 或社交写操作。
