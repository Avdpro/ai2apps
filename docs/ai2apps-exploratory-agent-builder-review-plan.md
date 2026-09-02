# AI2Apps 探索式 Agent Builder、编译 Review 与反馈修订开发计划

状态：Phase 1 完成；Phase 2 首个可运行切片完成  
日期：2026-08-31  
适用范围：Browser Agent Builder、Agent Runtime、Agent Mini-Entry / Sidebar

## 1. 背景与决策

当前 Agent Builder 会让模型一次生成完整 Agent Source，再整体编译、整体试运行。对于结构稳定、目标简单的页面，这条路径成本低；但面对动态页面、延迟加载、登录提示、条件分支或不确定交互时，模型必须预先猜中后续页面状态，失败率会随步骤数快速上升。

本次改造采用两阶段架构：

1. **探索阶段**：只规划下一步，执行后读取证据并评价效果；必要时局部重试、重新规划或回退到安全检查点。
2. **产品化阶段**：探索成功后，不直接保存探索日志，而是将成功路径沉淀为 Agent Source，编译为受限 IR，并交给用户 Review。用户可提出整体修改意见，系统重新生成 Source、编译并展示变化；只有 Review 通过的版本才能加入网站智能体并激活。

浏览器访问继续严格遵循 `docs/ai2apps-browser-control-architecture.md`：Sidebar 只通过当前 mount 绑定的 WebDriver BiDi context 操作页面，不新增语义浏览器 REST API，不使用 JSWindowActor 提取页面数据。

## 2. 产品原则

- 用户的目标、成功条件、输出字段、站点范围和副作用限制是权威输入。
- 探索器一次只生成一个可验证动作，不提前虚构尚未出现的页面状态。
- 能确定性完成的步骤不调用 AI；只有语义判断、歧义消解或非结构化转换才允许显式 `ai.*` 步骤，并声明 `simple`、`standard` 或 `complex` 等级。
- 每一步必须有前置条件、预期效果、实际证据和评价结果。
- 失败优先局部修复；连续无进展或页面状态失配时，回退到最近安全检查点重新规划。
- 删除、发布、发送、提交、购买、授权等改变帐号或远端状态的动作，必须在“最后可负责时刻”向用户确认，展示准确目标、数量、帐号和可逆性。
- 登录、CAPTCHA、法律条款同意、敏感信息输入继续由用户接管，不能由模型猜测或绕过。
- Review 展示 Source 与编译 IR 的逐步映射，不能只给“编译成功”结论。
- 修改意见作用于整个流程版本；重新编译后必须显示差异，并使受影响的旧证据失效。

## 3. 生命周期

```text
intent_captured
  -> exploring
  -> exploration_succeeded
  -> source_distilled
  -> compiled
  -> awaiting_review
  -> revision_requested -> source_distilled -> compiled -> awaiting_review
  -> approved
  -> committed
  -> active
```

终止状态包括 `failed`、`cancelled`、`needs_user` 和 `restricted`。`approved` 只代表用户接受当前 Source/IR；真正写入网站智能体仍是单独的 commit 操作。

## 4. 核心数据契约

### 4.1 AgentIntent

- `goal`：用户自然语言目标。
- `success_criteria`：可观察的完成条件。
- `constraints`：站点范围、禁止操作、最大步骤、最大重试和时间预算。
- `output_schema`：结果的结构和必填字段。
- `side_effect_policy`：需要确认的 effect 与确认粒度。

### 4.2 ExplorationRun

- `id`、`recipe_id`、`status`、`budget`。
- `observation_digest`：当前页面状态摘要，不持久化不必要的敏感正文。
- `checkpoints`：可安全回退的页面与流程检查点。
- `attempts`：每次候选动作、验证、执行和评价。
- `goal_progress`：已经满足和尚未满足的成功条件。

### 4.3 NextActionProposal

- `operation`、`target`、`arguments`。
- `reason`：为何这是当前最小必要动作。
- `preconditions`：执行前必须成立的事实。
- `expected_effect`：执行后应观察到的页面或数据变化。
- `effect`：read / interact / transfer / commit / restricted。
- `ai`：仅在需要时包含等级、指令和输出 Schema。
- `on_failure`：retry / replan / rollback / needs_user。

### 4.4 ActionEvaluation

- `outcome`：success / no_progress / not_found / retryable_error / needs_user / restricted / failed。
- `evidence`：BiDi 操作结果、前后页面指纹和结构差异。
- `criteria_delta`：本步新增满足的成功条件。
- `decision`：continue / retry / replan / rollback / finish。

### 4.5 AgentReview

Review API 返回 `ai2apps.agent-review/v1`：

- `recipe_id`、`source_revision`、`source_digest`。
- `status`：awaiting_review / approved / revision_requested。
- `compiler`：编译器、策略版本、errors、warnings、effects。
- `steps[]`：
  - `source`：编译前的名称、自然语言描述、目标、参数、AI 等级和转移。
  - `compiled`：编译后的 operation、mode、effect、规范化目标、参数和转移。
  - `mapping`：source index 与 compiled step id。
  - `evidence`：探索或试运行产生的相关证据摘要。
- `permission_review`：远端副作用、确认点和范围变化。

### 4.6 RevisionRequest

- `expected_revision`：乐观并发控制。
- `feedback`：用户对整个流程的修改意见，例如新增 corner case。
- `locale`：用于生成 Review 文案，不改变执行语义。
- 返回完整新 Source 和新的 AgentReview；不接受局部、未经编译的 IR 覆盖。

## 5. 探索循环

每轮严格执行：

1. **Observe**：读取当前 BiDi context 的 URL、title、可访问树摘要、候选目标和必要的渲染内容。
2. **Propose**：模型只生成一个 `NextActionProposal`；优先确定性 operation。
3. **Preflight**：本地 Schema、站点范围、effect、敏感目标和前置条件校验。
4. **Confirm if needed**：仅对 transfer / commit 或策略指定动作请求用户确认。
5. **Execute**：Sidebar 使用原生 BiDi 命令执行。
6. **Evaluate**：确定性比较前后指纹、目标可见性和输出 Schema；语义成功条件才调用指定等级 AI。
7. **Decide**：继续、局部重试、重新规划、回退或完成。

防止死循环：相同 observation digest + 相同动作最多重试一次；连续三步无 progress 必须 replan；超过预算进入 `needs_user`，并说明已尝试内容。

## 6. 成功路径沉淀与编译

探索成功后执行 distillation：

- 去掉纯诊断、重复滚动和无效尝试。
- 将临时目标解析结果还原为稳定的自然语言 target hint，不保存脆弱的 DOM 节点句柄。
- 合并可安全合并的连续读取步骤。
- 保留真正需要的 `ai.*` 步骤和等级。
- 为动态分支添加来自探索证据的 fallback，而不是逐字重放探索日志。
- 为输出字段生成 validators/fixtures；请求了 `image_url` 等字段时必须进入输出 Schema 和测试夹具。
- 对每个 destructive/commit step 插入显式 approval 前驱。

沉淀后的 Source 经过现有严格编译器生成 IR。编译错误先进入自动 repair；两次仍失败则把错误和失败 Source 交给用户，不创建可提交版本。

## 7. Sidebar Review 体验

- 探索/试运行成功后自动进入 Review 区，而不是立即显示“可以加入”。
- 顶部显示版本、编译状态、effects 和警告。
- 每个步骤同时显示：
  - **编译前**：用户可读的目标、描述、AI 等级、预期分支。
  - **编译后**：operation、effect、mode、规范化参数和实际转移。
- effect 为 transfer / commit / destructive 的步骤使用醒目标记，并展示确认点。
- 提供“修改整个流程”输入框。提交后调用标准任务模型生成完整修订 Source，严格校验、编译，并显示版本差异。
- 提供“通过 Review”按钮。只有 approved 版本显示“加入当前网站智能体 / 另建网站智能体”。
- JSON Source 与 IR 始终可以展开查看，方便高级用户审查。

## 8. API 与事件

Phase 1：

- `GET /agent-recipes/{id}/review`：生成或读取当前版本 Review。
- `POST /agent-recipes/{id}/review/revisions`：根据反馈修订完整 Source 并重新编译。
- `POST /agent-recipes/{id}/review/approve`：批准准确的 `expected_revision`。
- `/commit` 只接受 approved Recipe。

Phase 2：

- `POST /agent-recipes/{id}/exploration-runs`。
- `GET /agent-exploration-runs/{id}`。
- `POST /agent-exploration-runs/{id}/actions/{action_id}/result`。
- `POST /agent-exploration-runs/{id}/confirmations/{id}`。
- `POST /agent-exploration-runs/{id}/distill`。

运行事件增加 `observation.created`、`action.proposed`、`action.validated`、`action.executed`、`action.evaluated`、`exploration.replanned`、`source.distilled`、`review.awaiting` 和 `review.approved`。

## 9. 分阶段交付

### Phase 1：Review 基座（本轮）

- Review v1 数据协议与逐步 Source/IR 映射。
- Recipe 修订与批准状态。
- Sidebar 编译前/后对照、反馈输入和批准门禁。
- API、仓储和 UI 回归测试。

### Phase 2：一步一探索

- ExplorationRun 存储和预算。
- 单步 proposal / preflight / execute / evaluate 循环。
- 确定性 evaluator、检查点和 replan。
- Sidebar 实时展示“观察—动作—效果”。

首个可运行切片采用以下安全限制：

- 标准任务模型只接收页面结构计数、指纹、步骤 outcome 和结果的字段/类型/数量摘要；页面标题、正文、控件文本和结果值不会进入模型请求。
- `inspect`、`extract_list`、`scroll` 可在通过本地预检后自动执行。
- `open`、`page_access`、`click`、`input`、`hover`、`delete` 在探索阶段逐动作确认。当前 effect 分类器尚不能可靠区分纯导航点击与发布/发送按钮，不能只凭模型描述自动放行。
- 探索最多 12 个动作，成功路径由本地编译器确定性沉淀为 Recipe，再进入 Phase 1 Review。
- 当前探索状态保存在 Sidebar 会话中；持久化 ExplorationRun、检查点回退和显式 `ai.*` 探索步骤仍属于 Phase 2 后续切片。

### Phase 3：自动沉淀与回放

- 成功轨迹 distillation。
- fixtures、validators 和 corner-case 回放。
- 受反馈影响的证据失效与增量复测。

### Phase 4：可靠性与发布

- 站点漂移检测、局部修复、版本回滚。
- 指标仪表盘和失败分类。
- 老 Recipe 的兼容迁移与灰度开关。

## 10. 验收标准

- 动态页面任务无需模型一次预测全部后续状态。
- 每一步都有可审计的提议、验证、执行证据和评价。
- 确定性任务的最终 Agent 不包含隐式 AI。
- 必要 AI 步骤明确等级、指令和输出 Schema。
- 所有改变帐号/远端状态的动作在执行前获得精确确认。
- 探索成功后能生成合法 Source 和 IR，并在 Sidebar 逐步对照展示。
- 未批准 Recipe 无法 commit；旧版本批准不能批准新 revision。
- 用户反馈会生成新 revision、重新编译并显示差异。
- 模型无配置、不可用、返回非法 Source 或编译失败时，Sidebar 给出可关闭且自动消失的本地化错误。
- 现有 BiDi 页面绑定、Knowledge/Agent 随页面更新和 JSON/AI 展示能力不回退。

## 11. 测试与指标

测试覆盖：

- Review 映射、effect 标记、编译错误和 revision 冲突。
- 修订模型成功、一次 repair、模型不可用和非法返回。
- 未 Review commit 拒绝、批准后 commit 成功、修改后批准失效。
- Sidebar 对照渲染、反馈提交、按钮门禁和多语言。
- Phase 2 的无进展循环、页面漂移、回退、确认和 needs_user。

首个验收 Case 使用 Fratello 文章列表页，目标为“提取所有文章的标题、链接、作者、发布时间和图片 URL”。自动化测试按两轮模型决策验证完整路径：第一轮只生成并编译一个包含 `image_url` 的 `extract_list`，执行证据成功后第二轮判定完成，再将成功路径沉淀为 Recipe 和逐步 Source/IR Review。测试还断言页面正文和提取结果值不会进入标准任务模型请求。

2026-08-31 本机桌面冒烟测试确认新版 Sidebar 已展示探索状态、动作预算和停止入口。测试环境在读取页面前被现有 AceFox BiDi WebSocket 同源门禁以 403 拒绝；没有为通过测试而放宽该安全边界。该运行时连接问题需由浏览器网关单独修复后，再补一次完整桌面回放验收。

关键指标：任务完成率、平均探索步数、replan 次数、AI 步骤占比、用户接管率、误触副作用为零、Review 后修改率、编译/回放通过率和站点漂移恢复率。
