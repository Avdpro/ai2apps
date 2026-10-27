# 列表统计与预算续额

社交 owner 新增 read_mode（content/metrics）、selection（date_window/recent）、metrics（likes/comments/reposts）声明与确认参数。仅统计时直接使用列表的已观测计数，跳过详情和媒体审阅；只对缺失的计数补读原 Profile 中的对应详情。recent 保留主页列表顺序、排除置顶，不因列表未显示日期而额外读详情。日期窗口读取仍保留日期核验。未观测到、约数与零继续区分。

共享 Runtime 在下一次模型/工具调用前检查步骤与 Token 预算。耗尽时复用持久菜单交互；继续从当前累计步骤与 Token 用量起开启新额度，不修改历史步骤、不抹除用量、不重放完成动作。用户停止后保留原步骤与结果并结束。历史 Token 续额仍兼容。明确的超时、取消和权限限制继续生效，续额不授予业务权限。API 返回续额后的有效累计上限。

回归覆盖任意 executor 在步骤/Token 耗尽时等待、重启恢复、继续与停止；社交列表模式跨 X/小红书/微博验证无详情点击、无读图。针对性 Python 测试 20 通过；浏览器 DOM 测试 13 通过；AaAT 边界门禁 371 通过（新增 recent 内容媒体回归另在针对性测试中通过）。


## Dev 现场验收

- 社交统计 Run：`run_7f4e11b4d4b94d02bcf16258fec26d9d`，completed，11 步。当前 DeepSeek 模型选择 metrics/recent/limit=3，原 Default Profile 中完成账号确认及读取。第 2、3 帖直接复用列表计数（1、5），仅第 1 帖缺失数字而查看详情，仍明确记录 `like_count_not_numeric`，不当作 0。媒体审阅为 `requested=false/reason=metrics_only`。
- Token 续额 Run：`run_78b6fad87f4147df8f4fa6fa5347ca1d`。通过 Chat 输入 1000 Token 额度，真实模型首次返回后累计 19,561，任务进入 waiting_input；点击继续后有效上限变为 20,561。下一次累计 40,662 再次等待，继续后完成（6 步）。两个 app.describe 调用参数分别为 `{}` 与 `{capability: social.account}`，均只执行一次；续额未重放已完成调用。单次模型调用按返回用量结算，故可越过小额测试额度。
- 步数续额、选择结束、等待中 Runtime 重启，以及任意 Provider 的嵌套任务预算菜单，由持久数据库/真实调度器回归覆盖；没有声称这些是线上模型现场执行。
- 测试后恢复 Chat Token 额度 500000。最终 Python 修改经标准 Dev Helper 重启（无活动任务）；Dev App/Helper 的 DevelopmentSourceRoot 均为当前 Git checkout。Local 日志的已导入模块路径指向当前 checkout；新端口 50820 的 Chat 已显示新的“每轮额度”文案，历史验收任务仍为 Completed。未修改 App-Dev 或生产。

列表中无数值的计数仍标未知；本次验收第 1 帖的点赞数不可用，这是页面观测限制，不是读取成零。预算续额不会扩展任务超时或授予新权限。


## 列表发帖时间补充（2026-10-26）

时间同样遵循列表优先：列表已有发布时间时标记 `published_at_source=list`，即使为其他缺失字段或图片进入详情，也不让详情的空值/不同时间覆盖它。列表缺失且详情实际读到时间时标记 detail；摘要保留来源。按日期窗口统计时，列表时间及计数齐全即可跳过详情。最近 N 帖仍按观察到的列表顺序，不为不需要的缺失时间强制开详情。

针对性回归 52 通过；DOM 12 通过，包含 rednote/xiaohongshu 两个域名的列表 datetime 提取。补充覆盖日期窗口从列表返回、详情缺失/不同时间时保留列表时间。标准 Dev Helper 在活动任务为零时重启加载；本次未额外执行真实社交抓取，现场社交读取证据沿用上节，新增行为由回归验证。

本次时间优先补充的完整 AaAT 边界回归：375 通过；无业务例外。
