# Shopping Pro AaAT 验收（2026-10-21）

本轮业务变更在 Shopping Pro owner adapter/service 与源 Package。通用 AS 仅通过现有声明、表单、结果策略和任务进度接口工作，无 Shopping 专用分支。

## 自动化

- 后端/owner：81项通过（15.32秒），含日期边界、不同购买日、未知周期、历史价格分币种整数合计、精确确认/取消/跨Run/凭证复用、真实注册器夹具、空白页面有限重读，以及可见 Fresh 按钮包装层必须有 submit 控件和局部渠道标识。
- 统一 AaAT 架构门禁：152项通过（81.29秒）；最终按钮改动后再次152项通过（81.37秒）。既有 headless Metal atexit warning 不影响退出码。
- 前端：日期与价格/购物车恢复定向用例通过；完整购物UI套件有3个预先存在失败（刷新动作期待与当前实现不符、相关清理期待、mock textContent差异），移除本轮两处JS更改的基线同样失败，未宣称全套通过。

## 真实 Dev

固定 Dev App/Helper 的 source root 均为 `/Users/avdpropang/sdk/omlx-moe-cache`；标准空闲检查和 Helper 重启，运行 Local 日志显示 checkout 内 builtin_apps.py、system_tasks/service.py。无 App 重建、Cloud更改、发布、结账或付款。

第一次尝试 `run_00d0d8705ab9475cb6b39c26cc49bd0b` 暴露冷页面空白与新增 owner policy 返回字符串的错误，已修复；失败只读任务正常取消。

修复后 `run_0a21219f3fc74f8aa0f695391e9a18de` 使用明确选择的 GPT6.1Sol，通过刷新确认调用 shopping.refresh_list。任务 `btask_9c2d5847be4ad22aad0b6f7011c899004a91819023272b08ecc9295e42b34024` / child `run_61e60ef722a14013b14496bb28c9bbff` 完成一页、20种商品；对话实时观察订单详情1/10、2/10、8/10及整理记录状态。

真实推荐20行，默认选3项，历史价合计USD10.71；日期分档：逾期1、今日2、未来3天2、3天以后1、未知14。10月24日归未来3天，10月25日（剩4天）归3天以后。Chat最终显示后端确定性表格。首次模型过早打开购物车表单，取消后先展示清单；owner声明已强化先出清单再等后续加购请求。

随后明确只选香蕉1份，表单显示实际商品名与数量，确认后购物任务 `btask_22c8cbaa26a644933176e5507a6040b4e53d60117dc967f79ae1f105b3a745fe` 在点击前被渠道守卫暂停，未谎报成功。原生Inspector证明 Fresh按钮透明input与aria-hidden文字双层结构导致现有可见性过滤漏检；增加可见包装层解析，保持局部渠道证据/submit/原生输入/回读验证。此阻塞任务正常取消后标准重启 Dev 激活，后续加购验收见下。

## 最终购物车验收通过

最终 Dev port53050。新主Run `run_35a3a90634cc4af79ed3cf4d994c6423` 使用原补货来源、重新显示香蕉1份确认表单，提交后调用购物车任务 `btask_4be2020c328f4ab6b3904b55d606b7d3f391c21d59da6bda5b760d6849f8a55d` / child `run_f301af76441f4cadbdac6f11909a702f`。原生UI显示“正在准备购物车 · 0/1”；单商品动作返回success、quantity1、verified=true，最后cart_report返回recognized=true、商品B07ZLFPXHC/channel fresh/quantity1。两个Run/任务均完成。

实际保留的 Amazon Fresh Shopping Cart 标签页显示香蕉1份、Fresh小计1item/$0.99，未点击结账。对话最终明确“Amazon Fresh购物车已核实数量：1”“未下单、未付款”。没有删除或改动原有其它购物车商品。失败尝试未自动重试；新一轮必须重新确认。

最终统一门禁152项通过（81.37秒，退出0）；Shopping后端/owner81项通过，前端定向3项通过。当前源已包含先清单后续再加购的声明及Markdown表格后的空行修复，最终Local重启已激活；该声明新增措辞未单独再跑一次新的刷新模型决策，不将其表述为确定性的模型行为保证。

## 前端失败清理与完整购物回归（同日后续）

原3个失败均已查明并修正测试，无生产JS/校验放宽：

- “重新生成建议”已采用已观察source_tasks调用recommend；原测试把它当成history按钮的refresh_list。拆成两个入口分别断言：history只提交一次refresh_list、保留previous_task与pages；recommend只调用recommend、传source_tasks与locale，不重新读订单。
- 原成功用例向recommend返回refresh_list的assigned.shopping_report结构，且onclick返回void导致await并未等待异步完成。刷新测试改用history入口与匹配结果；推荐独立覆盖真实结果结构，显式等待任务推进，并用deferred结果证明完成前旧对话/输入保持、控件忙碌、仅提交一次，完成后清理。失败推荐/刷新均保留原对话，并验证失败提示与持久草稿。
- DOM模拟器未初始化空元素textContent（undefined），实际浏览器是空字符串。修正DOM夹具默认值，仍验证DELETE精确确认、成功前不可清理、无恢复副本、删除后刷新previous_task为空。真实永久删除未执行。

完整购物前端4个文件31项通过，含独立浏览器390px移动端布局/操作与Desktop检查、礼物UI、任务进度及Shopping UI；后端/owner/删除85项通过（14.88秒）；统一AaAT门禁152项通过（74.71秒，退出0，既有headless Metal退出警告）。默认node缺playwright及沙箱启动阻塞属于测试环境，改用已有bundled Node/Playwright和获准的独立临时浏览器后完整执行，无跳过、过滤或校验放宽。不涉及用户浏览器、账户、真实删除或购物车重放。

## 2026-10-21 报告 items 与购物车 selected 错位

用户请求“前三种，每种2个”，实际待确认草稿记录了B0CJJZ22BB、B07ZLFPXHC、B08X283B8L，
quantity均为2，但字段名是items；prepare_cart的声明要求selected，导致additionalProperties
拒绝且缺少selected的JSON输入渲染为null。尚未执行真实购物车写入。

Shopping Pro声明补齐canonical参数及示例，并由owner prepare_values在确认前迁移无冲突
旧alias，保留ID/数量；未知额外字段不删除、冲突拒绝。owner根据已观察记录声明商品
表格和ID枚举。共享表单只增加通用、只读、幂等的确认前草稿准备hook与records编辑器；
校验、Run/Provider/revision绑定、明确确认、取消及单次购物车回执仍严格。

测试：owner/参数HTTP22通过，前端48通过（含真实浏览器三行编辑、数量草稿快照、刷新
恢复且确认前无POST提交），AaAT195通过87.18秒，退出有既有headless Metal诊断。
隔离HTTP测试确认三项各2的回执，且没有产生Browser Task写入；不是已加购的实机证据。
当前Dev无运行中Browser/System/Studio任务，只有这一项waiting_input；持久草稿完好。
激活需要标准Dev Local重启，会使既有Mobile Agent进程实例绑定失效，已明确询问用户
是否现在重启；未获得答复前没有重启、没有改动线上购物车、没有声称真实订单或购物车已生成。


## Approved Dev activation and live verification

User approved restarting Dev. Restarted through the owning Helper after checking that no Browser, System or Studio tasks were executing. Local changed from PID 70083 / port 50217 to PID 97255 / port 58733. App and Helper development source roots, actual Local imported module paths, and the served shared form widget all match the live checkout.

The native Dev Chat restored the original pending interaction int_793c10d015754e928598375b69e0455a for run_78eb4024467b48f286cb2ccf538c95ea. The live confirmation form shows Chobani Low-Fat Greek Yogurt Honey Vanilla 32oz, Banana Bunch (4-5 Count), and Amazon Grocery Pitted Prunes 8 Oz, each with quantity 2. The null field and unexpected-items validation error are gone. The source task and default browser profile remain preserved.

The Confirm cart button was not clicked. The Run remains waiting_input and the Interaction pending; Browser Task counts are unchanged. This verifies draft recovery and rendering, not cart creation, checkout or payment. Mobile Agent re-pairing and explicit Desktop approval remain a human step after the process-instance change.


## Live cart confirmation attempt after activation

User explicitly authorized confirming the three observed products at target quantity 2, without checkout/payment. Clicked the original Confirm cart UI once. Chat displayed Shopping Pro progress (0 / 3), then waiting for assistance. Browser task btask_ffecf3c7aff3d30059e571fec6ce19f8305a40f1cccc2036d1dc6e610e8351d5 and child run run_164d24499ea841cca61801d168d1d376 remain waiting_input with amazon_cart_add_unverified; the parent run also remains waiting_input. The AI Browser task detail shows the same blocked state. No successful quantity verification or completed result is claimed.

The task-page control did not change the Dev window. Computer Use access to Firefox was not approved, preventing direct inspection of the actual Amazon page. No blind retry, assistance-complete click, checkout, or payment was performed. Live acceptance is blocked on browser-page inspection/assistance; progress and blocked-state propagation to Chat are observed, final-success propagation is not yet verified.

## Actionable assistance repair

The paused task response was inspected read-only: reason amazon_cart_add_unverified,
expected_quantity 2, observed_quantity 1. Its cart layout includes a visible
"2. Click to change quantity" control and another product's "1. Click to change
quantity". This is evidence of potentially inconsistent quantity extraction, not
proof of login/CAPTCHA or of all three final quantities. The current item is the
observed Chobani Honey Vanilla yogurt. No assistance-complete action was submitted.

Shopping now supplies assistance_message with product/target/read quantity and
specific inspection instructions, keeping reason as diagnostics. Shared durable
browser interactions transport that bounded message, with a generic inspect/report
fallback when missing; no owner-code routing or authentication guess in shared AS.
Visible quantity labels precede stale hidden values, and conflicting visible labels
produce unknown quantity. Regression covers the exact production reader block,
no-click uncertain handling, and arbitrary-provider durable message propagation.
151 owner/browser/presentation tests passed (17.66s). New backend behavior has not
been activated in the current Local process; existing pending prompts remain
historical durable records, not silently rewritten. Live cart success remains
unverified and no further add/checkout/payment was performed.

## Restarted Dev and real cart completion

User restarted Dev to port62456/PID99128, with Local imports from the live checkout.
Continued the original task as explicitly authorized. Yogurt was recognized at2.
Banana remained1; the new owner assistance message appeared in the actual workspace,
including product, target2/read1, same-profile/store inspection, and no-repeat-add/
no-checkout instructions. The actual Amazon Fresh task window was found through
the exact Dev Shell Window menu (not the unrelated org.mozilla.firefox app).

Read the real cart and clicked Banana Add once, observing1->2; continued original
task. It added prunes1 and paused with the correct new product-specific message.
Clicked Prunes Add once after verifying1, observing2, and continued for final read.
The original browser task and child Run completed. Recorded result has all three
observed IDs at quantity2 in Fresh. Native cart shows all three quantities2,
subtotal6 items/$22.26. No checkout/payment or changes to unrelated products.
This is assisted live completion, not proof that automatic increments work.

The old parent Chat had previously consumed the assistance as a Tool error and
completed; its old text does not automatically update when the detached child
finishes. Removed the shared observer's conversion of human waiting into Tool
failure; it now follows the same task without approving/resuming it. Cross-owner
waiting->completed regressions37 passed6.50s. This new observer change is not yet
loaded in the already-running Local process; historical records are not rewritten.

Final live conversation verification: a fresh explicit same-target check used
shopping.prepare_cart with original source_tasks/default profile and the same three
IDs at2. Task btask_53185e9c2c2898ccf49e3d66cd6dc4205a263c83163b98361ea05ca0eb842514
and child run run_a39c181deedf43f080dd158267faddfa completed. Each item action
returned already_present=true, quantity2, fresh; no additional add was needed.
Native Chat displayed progress1/3 then3/3, Completed, and the owner thumbnail table
with each quantity2/verified. A first malformed native typeText test lost CJK input
and attempted browser.open; it was cancelled before permission/operation, then the
complete request was pasted and confirmed correctly.

The model prose incorrectly inferred other products from cart6 items; actual native
cart contained exactly3 product rows at2 each. Treat its6-item interpretation as an
unverified model inference, not evidence; the owner table and actual cart are the
acceptance basis. Historical unit-price total21.42 differs from current cart22.26
because observed prunes current price4.17 differs from historical3.75. No claim that
historical prices are current. Mandatory AaAT197 passed99.50s (existing headless
Metal diagnostic). Assistance propagation is live; the later wait-observer fix
remains pending next Local activation, without rewriting old completed tool calls.

## WebAgent visual DOM recovery acceptance (2026-10-21)

Shared implementation: browser/visual_recovery.py. Uses the current step's pinned
model only, affirmative image-input metadata, bound native BiDi viewport screenshots
and real DOM refs. First model response selects a ref; host DOM geometry produces
the red rectangle; second model pass reviews it; native input occurs once, followed
by owner quantity readback and a third fresh screenshot/DOM review. No model-supplied
scripts/selectors/coordinates or new AS business routing. Owner preflight rereads
quantity immediately before dispatch; if async state already satisfies the target,
no increment is sent. Ref/document/URL/viewport/geometry/hit-test guards remain.

Live setup changed Banana2->1 once through the real cart decrement button, leaving
yogurt/prunes2. First attempt did not dispatch an increment because the bounded DOM
candidate sample omitted pointer-handled controls; it paused with the existing
product/target/read-quantity guidance. The test parent was stopped before restart;
its durable child remained paused. Expanded bounded DOM capture and row-scoped
ref candidates fix that gap; offscreen allowed controls are natively scrolled into
view and reobserved before capture.

After activation at Dev54065, resumed original task
btask_5b4d4606c41aa819728f569f0074fd02cdac1621fad57fcee85e486621bb53b6,
child run_d52a462c84c44ebbba9bd802caedae39. Banana action recorded:
select ref e171, review confirmed=true, after confirmed=true, all using the current
cloud/deepseek/deepseek-flash. Distinct screenshot hashes persisted, no raw screenshot
bytes. One automatic increment produced owner-verified quantity2. No manual plus
click occurred in this test. Original child/task completed with all three Fresh IDs
quantity2. Refreshing the retained real native cart ultimately shows3 rows each2,
6 units/$22.26; immediate reload snapshots can still contain old page state until
load finishes, so the settled native state is the acceptance basis. No checkout,
payment, subscription or unrelated item change.

The later owner preflight guard and fixed-current-model behavior are loaded through
standard Dev restart to55548/PID3160 (no active Browser jobs at restart). App/Helper
source roots remain the checkout; Local imports and visual module import log point
to live source. Current image-input model was not replaced. Final additional native
Chat text-entry attempts did not submit a new request; no claim of a fresh full Chat
turn after the final restart. The successful automatic child and its durable result
are real; negative/race behavior uses isolated model fixtures.

Final directed suite166 passed15.02s, including17 visual/shared-owner tests; mandatory
AaAT197 passed99.67s, exit0 with existing headless Metal atexit diagnostic. Earlier
optional native test remained skipped because its explicit opt-in was absent; the
real Dev acceptance above is separate, not substituted by that skipped test. Tests
cover red-box rejection, fabricated refs, missing vision metadata without model
switching, scope/sensitive-page rejection, stale geometry/occlusion, post-action
failure without replay, owner quantity disagreement, late satisfaction without
input, and shared executor fallback with arbitrary provider identity.

## Generic execution policy — 2026-10-21 Dev58079

Implemented Source/Task execution_policy, owner minimum_execution_policy, validated
compiler persistence and monotonic nested capability inheritance. Shared AS has no
business-name branches. Package capabilities can impose floors through the same
Mini-App declaration; Shopping cart requires always, Web Reader defaults off.
Fresh result readback cannot be disabled. Unknown owner predicate may be resolved
by fresh positive visual state evidence only when explicitly allowed; false owner
predicate remains false. Direct DOM controls also receive red-box review under
always; off skips vision but preserves readback. Explicit observed offscreen refs
use bounded native scroll and fresh capture, not unbounded search.

Fixtures: cross-provider alpha/beta floor protection; invalid flags/readback=false;
real shared executor direct-DOM always review/after; article off with actual mocked
read result and post snapshot, zero screenshots; tri-state owner verdict with
visual fallback allowed/denied; observed-offscreen scroll; existing visual safety
and Shopping owner tests. These fixtures are not live cart mutations.

Real Dev: standard Helper restart, PID5718 / port58079, boot
2184d8f7-d662-42ce-ad13-7159fa42ce07; live-checkout App metadata and imported
background executor/page/visual-recovery paths confirmed.

- Web Reader article capability, SJX current homepage: task
  btask_01ccd94e2fa1f83d694c31e5082058912a5220b7831201bf198837d79b0c5757,
  run_70fd81d404f747df8dfaaabe5f4ccf32, completed via Readability, actual page text
  returned and temporary tab closure verified. Persisted policy visual_locating=false,
  visual_review=off, readback=true. This live input was the homepage, not a claim
  of strict single-news-article selection.
- First Chat attempt run_2444ffb58e454c2dbd879c06dd14b1c2 was rejected before
  task submission due duplicate profile in common/provider parameters, then
  conservatively blocked by uncertain-execution handling. No cart Task or change
  occurred; no successful visual verification is claimed for that run. A separately
  approved canonical-input Run followed, without relaxing validation.
- Successful parent run_c8ec9709c2264007a76af938f1634a48; browser task
  btask_a0fac60e378f034b9a1391a2fa1f5665bef1d856275caf910453d54a61066ffa;
  child run_1f9da35098cb4c44b97d69a443c57f5d. Effective policy always, owner minimum
  always/readback=true persisted. Each existing Fresh product was freshly reread
  as quantity2/verified/already_present, then separately visually confirmed by
  current cloud/deepseek/deepseek-flash. Three after-phase image digests recorded:
  fa5d5bb0a8a15a93946d0ac5ea7f721c75ed673d73603cce5a960ad48592e689,
  56d1a27a57368a5a4a484f0ca7eff75a8e6eb0af08bb1aeb1a07e4f6c4006fd6,
  5ed6362644b626bf2ed90299bb41c96dc7453e96979428019607a5b4d1129096.
  Chat showed 1/3 progress then completed text and thumbnail result table. No
  increment was needed or sent, no checkout/payment/subscription. Direct control
  red-box policy is fixture-tested; no new live quantity-changing action claimed.

Mandatory AaAT gate:197 passed88.86s, existing headless Metal atexit warning, exit0.
Directed combined suite:190 passed21.23s before one added offscreen-ref case;
policy suite including that case17 passed0.34s. Final combined rerun recorded below.

Final combined policy/visual/Shopping/background/capability-call/Mini-App suite:
191 passed20.56s (`/tmp/execution-policy-final.log`). Helper and App both declare
live source root `/Users/avdpropang/sdk/omlx-moe-cache`.

## Pre-submit argument correction — 2026-10-21

Generic CapabilityRouter now rejects duplicate common/provider fields (even equal
values), non-object parameters and unknown explicit Provider with
invalid_tool_arguments/phase=prepare, before invoking any Provider. JSON Schema
ValidationError from Provider prepare has the same no-submission classification.
Existing bounded model recovery receives the error and requests a new model
choice; it never silently merges conflicting values or automatically replays.
AgentRuntime accepts only the existing trusted prepare-stage codes plus this
parameter code as non-uncertain. Handler-side validation, timeout and ordinary
execution errors remain uncertain for effectful tools and block repeat/replacement.

The common first-party adapter now fills defaults and validates effective_schema
in prepare, shared read-only with parameter forms. Session/authorization checks
remain at the business handler boundary; installation identity is still checked
for the declaration. The initial extraction of preparation accidentally required
a Session during form submission; full regression caught this, and the final
implementation restores form-only validation without weakening execution guards.

Cross-provider alpha/beta real scheduler fixtures prove an invalid duplicate-field
call never executes the handler, AI sees no-submission correction instructions,
and corrected parameters execute exactly once. Routing fixtures cover malformed
objects, reserved fields, prepare-vs-handler schema errors and health isolation.
Common adapter tests cover Todo/Knowledge schema rejection before handler; existing
military research form/restart/grounded-report acceptance remains passing.
Final directed tests68 passed29.54s; AaAT gate207 passed103.38s, existing headless
Metal exit warning. Models/external effects in these tests are fixtures.

Dev read/recommendation attempt run_47c313b3bfae4a9e8dba356a4248e9f0 reused the
original request (one dozen cola plus 2–3 usual products, USD25–30). History task
btask_9dfc84efad1d27e05ac5d5962200f867ed1f87008aace1ca2ac97e551211a51b
completed; repeated result paging and recommendation exhausted the existing
24-step budget before cart submission. No cart mutation is claimed for that Run;
subsequent acceptance directly reuses its observed source and the original four
confirmed product quantities, without raising the step/recovery budget.

Live canonical cart continuation: run_884c2c1b08e34affb54d606327ed4174 actually
reproduced duplicate profile. The first shopping.prepare_cart returned
invalid_tool_arguments/phase=prepare/conflicting_fields=[profile], no uncertain
latch. Current DeepSeek removed only the duplicate top-level field. The existing
confirmation claim guard requested a second form for the corrected call; same
products/quantities were confirmed. One browser task was submitted:
btask_4d6da19ce19fec3648d638764cc49dbc8ac534bb9e37de14e1fe00970a6e0f8d,
child run_d2b53a93a6f047e78e6659944f455622. No AS business rule or confirmation
bypass was added.

Real acceptance then exposed raw fractional owner rectangles versus one-decimal
DOM snapshot coordinates. The review helper now normalizes exactly to the SDK's
Math.round precision before unique-ref matching; mismatched/colliding controls
still fail. Real yogurt initial add succeeded after fix: Chobani1, review
and after both confirmed, current DeepSeek; digests
f06383d81755e684b165c353ba7bd74e323842b53a39a41bc485ce3c44df864d and
2239711861e20a823fbc5deca52d0418c0917db5f6c319b6a1b60b387abf9bf2.
Prunes1 subsequently succeeded too, no manual add click. Cola2 was already present.

A preserved-task restart also exposed startup interruption events missing their
App owner when Session was non-null. PlatformRuntime now resolves app_instance_id
from the stored Session for this existing event; no constraint or identity guard
was weakened. Bound/unbound Session restart tests pass and preserve INTERRUPTED,
never replay. Dev Helper required an exact Dev-only recovery after control timed
out; App-Dev remained untouched. Final active Local54719/PID9159, boot
22d120ca-38a3-4b9e-b41b-965801a2bd5d. Original parent run remains interrupted by
the restart safety guard and is not rewritten as completed.

The original ice cream B000PNCWXA is genuinely Out of Stock in the bound native
Amazon Fresh page. Task's channel-assistance label is imprecise; this is not a
parameter-recovery failure. Native cart showed cola2/yogurt1/prunes1, actual
USD21.18. Paused ice-cream task was cancelled without removing these products.
Per the user's delegated choice of 2–3 usual products and USD25–30 budget, final
continuation selects observed Stonyfield B00108HZFY1 (four historical purchases,
USD5.49 historical price), with live final amount still to verify. No out-of-stock
add, substitute seller, checkout, payment or subscription.

Final expanded directed suite183 passed44.64s; AaAT gate207 passed102.04s;
existing headless Metal atexit diagnostic, exit0. Includes the extra geometry and
Session-bound startup regressions; no test assertions or architecture gate weakened.

Final live continuation completed on Dev54719/PID9159:
- Parent run_ce1aadbbd6614f8f938de3850c060da1 completed with no error.
- Cart task btask_2c0404d1e18024091f113d1ebd2eb2d38742981aca27b101c22ea913494ea40c
  and child run_a0b2c839e5bb48aeaa682c78d77305ae completed.
- Fresh cart readback: B000T9WM62 cola2 (two six-packs,12 bottles), B0CJJZ22BB
  Chobani1, B08X283B8L prunes1, B00108HZFY Stonyfield1. First three returned
  verified/already_present; only the new Stonyfield was added. Its pre-input review
  and after review both confirmed on current DeepSeek, image digests
  c067a10da68114a932350e857b15626dbd5126d398202e5c02df1041427f0802 and
  cfb74ba5b7b79584ffb2bd4afc88ed6fae4fa1dec17f1c55a8a53853e0d9866f.
- Actual CART_SCRIPT layout heading: `Fresh Amazon Fresh No items selectedSubtotal
  (5 items): $26.67`; four product rows,5 sellable units. Item subtotal meets25–30;
  taxes/delivery/service fees were not confirmed because no checkout was entered.
- Chat showed1/4->3/4->Completed and thumbnail table with four products. Final
  explanation distinguishes actual26.67 from historical26.25 and out-of-stock
  ice cream. No duplicate cola, old-item deletion, checkout, payment or subscription.
- Source roots/imports remain live checkout; App/Helper metadata both bind the same
  checkout. No Cloud changes, data rewriting or historical unknown-status removal.
- Additional original Service regression14 passed10.04s, including legacy unbound
  invocation restart. All final tests exit0; Metal diagnostic is environment-only.

Remaining distinct observation: the owner currently labels this ice cream's
missing purchase control as a channel-confirmation request, while the actual page
says Out of Stock. This wording was not weakened or reclassified in shared AS;
current acceptance used a real observed usual-product replacement instead.
Native Chat refresh also restored Completed, actual26.67 explanation and all four
thumbnail rows from saved history; no new cart operation was submitted.
