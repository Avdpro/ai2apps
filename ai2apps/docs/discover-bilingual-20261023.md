# Discover AaAT 双语关键词检索

Discover owner 在当前对话模型中生成中英文短关键词，不在 General Agent/AS 添加业务分支。
原始词始终保留，模型最多给出中文2项、英文2项；NFKC/大小写/空白规范化去重后，最多5路。
每路独立调用原能力目录，不把中英文拼成 AND 查询。每种语言至少一个备选为不带输入/输出/技术等限定的核心能力名词，第二个词为独立同义表达，避免把功能清单拼成 AND 查询。模型只收到本次检索目标，不读取目录
描述或完整对话；模型输出仅成为有界 query 字符串，不能选择 URL、执行脚本、安装或授权。

每路按目录游标自动读取后续页，每页最多64张卡片、每路最多8页，保留来源的 outcome/counts/pages_read/truncated；15秒单页超时，所有目录读取共90秒上限，
模型40秒超时。对来源未读完、失败或关键词扩展不可用显式返回 partial/原因，不声称完全
无候选。关键词扩展失败时保留原词检索，不用静态业务词典伪造翻译。

按 Package/version/kind/component identity 合并；相同身份的双摘要冲突直接拒绝。
不同版本和组件保留。matched_queries 只记录正向匹配词；source_matches 保留所有来源的
match/reasons/unknown/exclusions。一次查询未匹配，但另一个词正向匹配时选用真实正向
目录记录；不提升 declared/unverified/UI-only，不将关键词相近视为可执行接口核验。
counts_scope=observed_unique_cards 表示有界已观察去重计数，不冒充 Cloud 全目录计数。
每路 Cloud 计数仍在 sources 中保留。

结果在 owner SQLite 表 discover_keyword_snapshots 保存15分钟，最大2MiB；游标绑定
actor/Installation/Session/Run、原始query、全部精确过滤和limit。继续读取不重新调用模型，
不重新请求已读取的来源，进程重启后可读同一快照。超时或改参要求重新搜索，不静默替换查询。
原始 source cursor 不作为此聚合 AaAT 游标使用；来源达到页数/时间上限、后续页失败或游标重复时，记录具体原因并返回 partial。search_complete=false 与 absence_established=false 明确禁止据此断言没有能力或安装包；next_cursor=null 只表示当前聚合快照已读完，不能掩盖上游未完成。需要缩小短词/过滤条件或重新查询，不要求用户放弃原目标。

旧无 Run 的库调用保留原只读关键词入口。


## 验证

- 27 项定向 Python 回归通过：4项新增双语测试，加既有 Discover、签名能力目录、Package
  生命周期用例。覆盖分别检索、精确组件/版本去重、来源合并、未核验状态保留、双摘要冲突、
  改参/跨Session/过期游标拒绝、SQLite快照重读零模型/目录重放、部分失败和当前模型规划。
- AaAT 架构/行为统一门禁272项通过；未修改共享 AS 的业务逻辑或增加业务豁免。
- 固定 App-Dev 实测 Run `run_e779f9c5f7264e298daf146017a45871`，当前模型
  cloud/deepseek/deepseek-v4-flash。只执行一次实际 discover.packages 查询
  （声明加载前的准备复核未执行）。输入 query=数字人、limit=5，内部生成
  数字人、虚拟人、digital human、avatar，分别检索生产目录。
- 原中文及 digital human 无命中；avatar 命中 ai2apps/avatar-studio-suite 的
  Talking Portrait 0.1.1、0.1.2、0.1.3。合并结果为同一Package三个精确版本，来源信息
  保留每个词的 match/excluded/unknown。三项仍为 unverified、runtime_verified=false。
- 四路来源均无后续目录分页；37个排除项仅回传16项明细，coverage.truncated=true
  明确区分排除明细裁剪与候选完整性。没有安装、接受许可、执行业务或发布Package。

## Compact discovery and exact candidate detail (2026-10-29)

Agent search now accepts existing Cloud `mini_app_category`, `studio`, `package_id`,
`publisher`, exact capability and MIME filters. Known structured filters may be used
without keywords or a translation-model call. TAG support is not fabricated; the
Cloud handoff requests a negotiated taxonomy/TAG contract and server projections.

Run-scoped search returns candidate summaries with snapshot/candidate IDs, at most
200 description characters, verification state, matching query names and hidden
history count. Default projection selects the latest matching compatible release
per Package/component; it prefers a known match over a newer unverified release.
Historical versions remain opt-in (`include_history`). Exclusions are counts by
reason, not repeated card details. Original full cards and provenance remain in
the15-minute owner snapshot. Aggregated counts still describe all observed unique
cards, not the number of default visible latest candidates.

`discover.package_detail(snapshot_id,candidate_id)` reads one observed exact card
under the same actor/Installation/Session/Run and expiry. Only this detail contains
the exact installation target and full source evidence. The installation handoff
accepts the observed detail target, preserves existing signed release review and
rechecks lifecycle/Provider state after install. Summary selection never grants
permission or makes an excluded card installable.

No rolling rewrite of historical tool messages or earlier default compaction was
introduced. Compact summaries are emitted on first admission. The generic result
reader references an already-read identical-source range, with explicit reread
available after compaction; original records are unchanged.
