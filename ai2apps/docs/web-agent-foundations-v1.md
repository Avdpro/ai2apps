# 全局 Web Agent 基础能力

当前版本：`web-foundations/2`。这些是内置、版本固定的子 Agent，复用现有 `agent.call`、变量、条件分支和用户接管机制。所有浏览器操作使用受认证 Gateway 上的原生 WebDriver BiDi，DOM/正文读取在客户端 SDK 完成，无新的语义浏览器后端 API。

生成/探索提示中的能力目录包含名称、用途、输入及输出 JSON Schema、版本和作用范围。空白页也能发现全部基础能力。优先选择匹配网站的专用能力；公共阅读不自动要求登录；观察到实际遮挡再清理 Blocker。

| 能力 | 输入 | 行为与输出 |
| --- | --- | --- |
| `web.ensure-login` | 无 | 观察当前网站及关联窗口；AI 判断登录状态、打开真实登录入口。仅在扫码、凭据、验证码等处接管，继续后重新验证。成功输出 `outcome: success`。 |
| `web.read-page` | `url`；`new_tab=true`、`close_tab=true`、`delay_ms=1500`、`max_chars=20000` | 等待稳定，Readability 优先；异常、空结果或不足 100 字符回退清洗 DOM。返回 `outcome`、URL、正文、提取方式和上下文。临时 Tab 默认关闭并恢复原 Tab；验证码保留 Tab 等待协助。 |
| `web.extract-list` | `limit=50`，最多 100 | SDK 从清洗 DOM 提取搜索/文章链接，返回 `items` 数组。不自动翻页；复杂商品列表应使用网站能力或 AI 探索。 |
| `web.fill-form` | `fields: [{target, value}]`，最多 20 | AI 填写普通字段并核验，限制为准备动作，不提交、不发布、不修改凭据。成功返回 `outcome`、context 和 URL。 |
| `web.upload-files` | `target`、`files: [{asset_id,...}]` | 上传已授权图库附件数组至观察到的文件输入，包含隐藏 file input。复用原生 BiDi 文件设置与受保护附件传输。返回 `file_count`，不提交表单。 |
| `web.wait-state` | `target`、`present=true`、`timeout_ms=10000`（最多 30000） | SDK 每 500ms 观察目标出现/消失，不点击或导航。成功返回 `ready: true`，超时走失败分支。 |
| `web.clear-blockers` | `max_dismissals=6`，最多 12 | AI 识别当前遮挡并选观察到的关闭/取消/拒绝控件，执行一次后重新观察，直到全部移除。无阻挡输出 `outcome: false`；达到上限或无安全关闭入口走失败分支。 |
| `web.light-explore` | `goal` | AI 在当前页及相关页面查找，可点击、滚动和导航，每次使用新观察，最多 8 个探索动作。禁止购买、发布、提交、删除及账号修改。输出 `answer`、`facts`、来源 URL、context。 |

## 调用与后续判断

```json
{
  "name": "read-article",
  "operation": "agent.call",
  "arguments": {
    "agent_id": "builtin:web:read-page",
    "capability": "web.read-page",
    "generation_id": "web-foundations/2",
    "parameters": {"url": "${vars.items[vars.index].url}"}
  },
  "on": {"success": "check-read-status", "failed": "failed"}
}
```

`steps.read-article.output` 是结构化输出。`web.read-page` 的调用成功表示完成观察并返回了状态，不代表一定读取成功；消费正文前须检查 `output.outcome`：`success` 才有正文，`needs_user` 保留窗口用于协助，`restricted` 不可通过重试绕过，技术读取失败走失败分支。打开多个页面时使用返回的 context ID，不猜测当前 Tab。

## 边界

- Cookie 优先拒绝非必要项；广告、推广、活动及付费邀请只关闭/取消，绝不付款。付费墙、登录、验证码不能当普通广告清除。
- `clear-blockers` 每轮重新观察；遇到需要用户的状态复用持久化接管，继续后重新观察。运行时总计 100 步上限继续生效。
- AI 能力使用配置的 Standard 模型；模型错误、无证据或无法操作必须返回失败或具体协助原因，不虚构答案。目标值、页面文字和能力元数据均视为数据。
- 文件数组第一版使用已有图库 asset_id；不是任意文件系统路径或外部 URL 上传器。
- 读取只接受公共 HTTP(S) 地址，检查导航后实际地址。此校验不是 DNS 解析或网络隔离替代品。
- 可保留页面通过 SDK 当前会话记录与原上下文的关联；跨 SDK 重载的临时 Tab 关联不是本版本保证。
- 自动测试覆盖目录/调用、运行时输出、重新观察、清理次数上限、失败分支、Readability 回退、Tab 清理、等待超时及重定向地址校验。尚未完成全部能力逐网站实测。

## 加载更新

Python/API 更新后从 app-dev Helper 重启 Local；静态 Sidebar/SDK 刷新后生效。无需重建 Desktop。

## v2 能力组合

`web.read-page` 现在由打开保留页面、`agent.call web.clear-blockers`、读取关闭三个阶段组成。清理调用绑定打开阶段返回的 context，清理失败走关闭临时 Tab 后失败的路径。需要扫码/验证码时，子能力持久化暂停，继续后重新观察。读取能力不再只依赖 SDK 内部的一次关闭启发式。

`web.light-explore` 开始前直接调用清理能力；解释执行的 AI 在跳转后观察到新遮挡时，可以再次调用同一能力。只允许这个子能力通过只读探索的调用边界；其他任意子 Agent 不放行。嵌套调用记录与外层运行隔离。

已固定 `web-foundations/1` 的旧 Agent 保持旧 IR；重新编译/生成并选择目录中的 v2，才使用上述组合。这些语义能力需要 Standard 模型，公共页面也会多一次有界的阻挡判断。跨 Sidebar 重载后的临时窗口关联仍受 SDK 会话限制；取消任务的通用资源清理不属于本次变更。

## 站内搜索实测与边界

轻探索允许为明确搜索目标向观察到的搜索字段输入关键词，并通过搜索控件/回车查询；不允许向发布框、凭据字段或任意普通表单输入。站内搜索沿用当前登录状态，只有观察到实际登录门槛才接管。全局 HTTP(S) 范围使用 URL glob，兼容 Firefox 不接受星号主机名的 URL 解析；精确域名、端口及协议边界保持不变。

Google v2 真实运行记录：`agent-google-foundations-v2-test-20261007.json`。三次读取都经过 clear-blockers，并关闭临时 Tab。本次无实际 Blocker，因此没有验证关闭遮挡的现场路径。

轻探索逐步执行时使用 `verify_goal_with_ai=true`，避免把任意列表提取成功误当成整个搜索目标完成。模型输出无效 JSON 时最多修复一次；不升档、不无限重试。答案提取优先保留最新的清洗 DOM 观察，去除重复 before/after 快照并保留文本、控件引用及链接，以有效 JSON 控制证据长度；上下文必须使用真实观察到的 ID。

实测驱动保存在 `tests/fixtures/`，不由正式侧栏加载。微博驱动依赖仅测试时注入的执行器绑定，运行后移除测试导出与加载器。
