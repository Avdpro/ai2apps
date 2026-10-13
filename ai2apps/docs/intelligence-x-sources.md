# X channel sources

In Intelligence → channel → Sources → Add source, select X. Choose Accounts, Search queries or Lists. Enter one target per line (1–20 targets): accounts
accept @handles or X/Twitter account URLs; search lines are independent queries,
including X search operators. Lists accept multiple URLs in the form
https://x.com/i/lists/<ID>. X/Twitter host variants and share query parameters
normalize to the same canonical URL. Private lists require the list owner's
logged-in Profile. Searches use the Latest result view. Choose the
actor's existing AI Browser Profile; Default is initially selected. Login state
is retained in that Profile, never copied between instances.

X sources use the Local background WebAgent task tree and authenticated BiDi
Gateway. The shared BackgroundPage SDK performs natural-mode wheel input and
pauses; this source path defaults to natural mode even when a domain's generic
WebAgent setting is fast. There is no X API, private endpoint, cookie export,
or additional browser-control protocol. Login/challenge handling and task-owned
page cleanup remain with the shared runner.

Each target scans up to 20 visible DOM snapshots, stopping after three consecutive
snapshots add no posts, or after 200 unique posts. Targets are merged by post ID;
previously collected posts are skipped before detail reads. Every discovered new
candidate is read, with natural-mode spacing; there is no five-detail batch cap.
This remains bounded discovery, not exhaustive history or guaranteed coverage.
An individual known detail failure is recorded and skipped; remaining candidates
continue. Failed URLs are not marked collected and may be retried in a later update.
Login/challenge and uncertain native actions retain shared interruption handling.

Detail extraction matches the requested status ID and reads that post's visible
text, author, timestamp and photos. Replies, video transcription, hidden long-form
content, image-only posts and inaccessible content are not synthesized. Generic
webpage lead-image extraction must not replace a post's own photos. Collected
posts use the channel's existing post filtering, language, evidence and digest
pipeline. Source refresh intervals and social cooldowns continue to apply.

Configuration is stored in the source JSON as x_mode (accounts/search/lists) and
normalized x_values. URL is the first target for existing source display and
scheduling. X uses owner-scoped learned list/body Agents on top of its bounded reader; explicit
generic website list/body overrides are cleared. Python changes require a Local restart, and UI
changes require page refresh. No native rebuild is required.

Validation includes normalization and rejection, independent search URLs,
scrolled-feed merging, exact post matching, image preservation, multi-query
collection/Profile reuse and deduplication. Live X login/challenge acceptance
has not yet been performed.

Missing detail bodies and empty feeds are explicit failed read outcomes, not
uncertain native-action exceptions. Detail retries stay at the post's position;
feed discovery alone scrolls. Transport/native command failures retain the
shared uncertain-action contract and pause for inspection, without replaying.
Schema 90 permits pausing a waiting_input AgentRun while retaining its pending
interaction and accounting for the elapsed waiting time in its deadline.


## Adaptive compiled X extraction (2026-10-11)

The initial reader observes visible post containers and relative body/permalink/
author/photo selector candidates. If the old tweet attributes change, it falls
back to semantic article containers, timestamp permalinks and language-marked
body elements. AI chooses only supplied selector indices; it cannot generate
JavaScript or arbitrary selectors. Page samples are untrusted data.

List and detail rules are persisted as ordinary owner-owned WebAgent drafts and
immutable compiled generations. They appear in AI Browser. A new generation is
activated only after a separate browser read matches observed post identities,
URLs, body evidence and photo URLs. Repair versions the same draft. Normal reads
reuse the active generation and do not call AI per post. Missing selectors or
insufficient post coverage invalidate the cached rule and trigger relearning;
failed validation retains observed evidence without activating the candidate.

Learning is limited to one attempt per source/template per collection, persisted
in the collection job across restart. A failed attempt may retry on a subsequent
update. Profile ownership, natural mode, Task tree admission, journal uncertainty,
login/challenge assistance and cleanup remain owned by the shared browser runner.
All DOM work uses existing script.callFunction over authenticated native BiDi.
No new browser-control API or X private API is added.

This repairs common DOM/attribute changes locally after this framework is
installed. It does not promise to adapt to new authentication, status URL formats,
non-DOM rendering, unavailable content or arbitrary interaction flows. Those
cases fail visibly or request existing assistance rather than inventing evidence.
Synthetic regression covers changed body attributes, compiled reuse, drift,
owner/version isolation and failed validation. Live X repair still needs a real
source update and is not claimed as completed acceptance.

## Manual refresh interval

Manual channel and single-source refreshes use a 60-second minimum interval
from the previous social collection's completion. Automatic refreshes keep the
source's configured hour interval. Both respect the shared platform lease and verification pause. Ordinary read
failures also allow manual retry after 60 seconds; explicit rate-limit or
verification outcomes retain their longer backoff. A partial collection with
successful posts does not trigger platform failure backoff. Legacy ordinary
failure limits are interpreted using their original completion time.
The manual timestamp is persisted and survives Local restart. Existing automatic
schedule timestamps do not impose the hour interval on manual refresh.

## Page reuse within a source refresh

Ordinary X list/detail reads reuse one Task-owned page within the same source
refresh and Profile. Sequential children transfer ownership of the recorded
context; user tabs, other owners/Profiles and other source Task scopes cannot
be adopted. A live same-URL X read does not navigate again. Learning validation
still uses an independent temporary page. Failed or cancelled children close
their pages; completion of the source waits for retained page cleanup. Cleanup
reconciliation after restart uses recorded IDs and never creates a replacement.

## Manual update progress

Manual channel or source updates open Update history. Running records persist
source identity, stage, active requested page URLs, completed read-task count,
extracted evidence article count and finished source count. Validation reads
are shown as a distinct stage and excluded from the ordinary read count. Elapsed
time is computed from the persisted run start, updated locally each second;
collection SSE (Mobile polling) refreshes actual backend progress. Counters
survive restart and duplicate completed Task reads are not counted twice.

### 搜索排序（2026-10-12）

X 关键词信息源支持 `x_sort=latest|top`，默认 latest。多个关键词使用相同的保存排序；帐号与列表不显示排序设置。Latest 使用页面实测的 `f=live` 搜索地址，Top 不带 `f`。后台在采集前核验搜索词和对应 Tab 的 `aria-selected`；必要时用 native BiDi 拟人点击切换，无法确认则明确失败。校验也覆盖已编译的 X feed 规则，旧信息源缺字段仍默认最新。Desktop/Mobile 使用同一配置。

已在 Default 分身实测 F1：Latest 被选中，点击 Top 后 URL 去掉 f；切回 Latest 恢复 f=live，显示秒级发布的搜索结果。测试新建的 X 标签页已关闭。此验证确认站点控件和 URL 行为；不等同整轮频道采集验收。
