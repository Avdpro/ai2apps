# Search All / Web Reader AaAT 验收（2026-10-19）

## 实现

系统 web.search/web.fetch 通过现有 CapabilityRouter 调用 Search All / Web Reader Mini-App。前台与 AaAT 共用安装声明、WebAgent Broker、Browser Task 队列、Profile 隔离、执行器和页面清理。结果保留实际 App/Mini-App、Package、来源 URL 与源任务 ID。旧 HTTP 实现为单独 Provider，不能在已提交的 Mini-App 执行失败后静默替换。

Web Reader 正文从示例站点范围扩展为公开网页，AaAT 执行前验证公开 URL 并将声明范围收窄到请求 origin。正文长度有上限；识别 Not Found/拒绝访问等错误页面，不冒充正常文章。

## 真实验收

- 实例：App-Dev；由聊天界面 @research 启动，模型 DeepSeek V4.1 Flash。
- 题目：SQLite WAL 是否适合本地 AI 应用，比较并发、checkpoint、备份、网络文件系统限制，引用官方正文。
- 成功 Run：run_77663878325642adba31d998c01e6dfe，状态 completed。
- web.search 两次均实际使用 ai2apps.search-all.search，每次返回 8 个去重来源。共四个 Google/Bing Browser Tasks。
- web.fetch 四次均实际使用 ai2apps.web-reader.fetch：wal.html 31003 字符、backup.html 15827 字符、useovernet.html 9266 字符；另一次 c3ref/wal.html 为 79 字符 Not Found 页面，未被最终报告引用。最后一项暴露了错误页仍被判为成功的问题，现已补充识别与回归测试，未重新执行该错误 URL 的真实调用。
- 最终答复在 Chat 中展示，包含 WAL、Backup API、SQLite Over a Network 三篇官方正文引用。核心建议为：适合单机读写并发，但仍是单写者；需要管理 checkpoint；备份不能只复制主数据库文件；不适合网络文件系统共享 WAL。
- 八个 Browser Tasks 均为 completed，页面 cleanup.state 均为 verified。
- 此次真实验收没有 HTTP 回退。

## 真实验收发现并修复的问题

1. 后台 browser_bidi_action 也使用 waiting_input；只在 requires_user 为真时报告需要人工协助，普通浏览器动作继续等待。
2. external_read + network 被通用 Harness 当作可能有写入/计费的操作，普通失败污染后续只读调用。现按明确的只读组合识别；裸 network、billing、写入、未知副作用仍保持保守规则。
3. 缺失页面返回短文本 Not Found，现由适配器作为失败报告，不计入成功正文。

首次失败研究 Run 为 run_51dbdb284cf341be99ee1058b8fe81e1，源搜索任务实际成功，但上述 waiting_input 误判使父任务过早失败。修复后新 Run 完整通过，不篡改原始记录。

## 回归

57 项定向 Python 测试通过：AaAT 参数/来源绑定与合并、部分来源失败、Web Reader origin 收窄/正文截断/错误页识别、浏览器等待状态、只读副作用分类、现有 WebAgent Mini-App、Research 和 Tool recovery。

范围：本轮接入搜索与单页正文阅读；未新增验证码自动处理、付费 API 配置、前台 App 内继续表单或独立的深度研究产品。Package 其它能力仍按各自声明单独接入。

## AaAT 元数据与路由边界补充检查

Search All / Web Reader 已补中英文 display_name 与 summary，并通过共享表单及发现目录返回。
新增四种路由组合验证：Mini-App 未安装且自动选择时允许旧 HTTP Provider 回退；显式指定
Mini-App 时不回退；提交后失败在自动和显式两种选择下均不切换 HTTP。

当前 AaAT 搜索门面默认 Google/Bing；可选来源来自安装声明中的 extract_list/search.api 能力。
Package 的 plan、review、summarize，以及用户保存的自定义网站来源，尚未由此门面串接。
不应把前台 Mini-App 的完整搜索、筛选和总结工作流等同于当前 web.search Tool。
现有真实验收只证明 Google/Bing 与 Web Reader 链路，不覆盖全部搜索来源。

扩大回归发现旧搜索提取测试的 call_json 模拟被共享访问检查提前消费；这些专项测试现显式
模拟可访问页面，访问检查本身仍由 test_browser_access.py 独立执行。未削弱生产访问检查。
本次使用隔离 Runtime 和模拟外部执行，未重新进行真实联网搜索或重启 App-Dev。
