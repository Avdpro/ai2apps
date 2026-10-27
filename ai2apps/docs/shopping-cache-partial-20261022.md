# Shopping Pro cache / retry / partial completion

Implementation: owner-side cached history selection; AaAT incremental/cache modes only;
owner discovery observations supply authorized prior references. General Agent adds only
identity-independent retry guidance. Budget errors retain bounded tool diagnostics.
Explicit visible product stock-out before native input is a skipped result; later products
continue and final native cart readback remains mandatory. No automatic substitution,
checkout, payment or replay of uncertain input.

Tests and live evidence will be recorded below. Fixture browser/model observations are not
live cart acceptance. Existing tasks retain original evidence and are not rewritten.

## Regression and observed Dev evidence

- 177 targeted regressions passed (`/tmp/shopping-cache-visual-final-tests.log`):
  owner cache isolation, incremental known-page/detail skipping, cache-only no DOM,
  out-of-stock continuation/all-skipped/verified partial report, concrete assistance,
  two arbitrary Provider identities resolving prior references from discovery,
  budget diagnostic preservation, generic partial progress, visual scrolling and JSON repair.
- The mandatory AaAT gate previously passed 212 tests. A later run hit a SQLite
  lock in the existing before-link restart fixture; isolated rerun passed, then
  the complete gate passed again unchanged. No checks or expectations were loosened.
- Dev cache run `run_585136216766406b8d294e59529feecf` completed in 13 steps with
  `history_mode=cache`, automatically selected owned stored history
  `btask_9dfc84efad1d27e05ac5d5962200f867ed1f87008aace1ca2ac97e551211a51b`,
  returned 20 products, and created ZERO new Browser Tasks. The user prompt included no IDs.
- Live cart retry likewise resolved and prefilled the four exact IDs/quantities without
  user-provided IDs. A first run paused because its screenshot did not include the
  offscreen cola row, despite DOM quantity 2. It was cancelled without adding products.
  Added owner-directed read-only scroll and fresh DOM reread before visual verification.
- Next run `btask_cc4c1b848edc366d7ab131668a0b631260295779811bd09092aa2de152828b13`
  failed during read-only visual-model JSON parsing, before new cart input. The shared
  visual decision path now reuses JsonRepairBudget/repair_json_request (2 repairs,
  total visual-call cap unchanged); post-click exhausted repair remains uncertain.
  This is model-output repair, never a browser-action replay.
- Runtime traceback verifies imported shopping.py, background_runner.py,
  background_executor.py and visual_recovery.py under the live checkout.
  App and Helper metadata both bind `/Users/avdpropang/sdk/omlx-moe-cache`.
- Fixture and live evidence are distinguished below; final real partial-cart acceptance passed.

## Live stock layout follow-up

The actual Fresh product uses `data-feature-name=almOutOfStockBuyBox` and a
`data-csa-c-asin` matching the requested ASIN, rather than the standard
availability node. Added this owner selector, normalized whitespace, and required
any declared ASIN to match the current product. Hidden/foreign stock nodes and
recommendation text do not establish stock status. Twenty cache/partial tests
pass, including both layouts and foreign-product rejection. The mandatory gate
passed 212 tests (`/tmp/shopping-stock-layout-gate.log`).

Dev run `btask_9f4368827f0b1cd2830fdb241d6648d2cfad3da1e92ff16e5120b39669ad72bb`
resolved the same combination from a natural retry without user-supplied IDs.
Real item results: cola 2, Chobani 1 and prunes 1 already present, all visually
confirmed; ice cream returned unavailable/out_of_stock with changed=false and
continued to the report step. Final acceptance evidence follows.

Final live acceptance completed: the task above and its compiled child
`run_551e8924f76f4f55a080a0faaeae2ade` completed normally. The owner report status
is `partial`, skipped ice cream has `out_of_stock` and changed=false, and the
three requested available rows are verified at quantities 2/1/1. The observed
Fresh cart contains four rows/five units, subtotal $26.67; existing Stonyfield
remains. The conversation visibly shows Completed, the partial-result message,
explicit ice-cream skip, and the verified thumbnail table. No order/payment or
new add input occurred in this acceptance run.

After refreshing the Shell, the conversation restored the same completed run, explicit partial/stock-out message, and verified cart table without another execution.

## Prunes 1→2 / $25 basket follow-up

The paused cart task `btask_3e83da1679e2301af3734327879e0ce9cf931b9a19150b5776b1c75e80d044ec`
had no dispatched increment: vision select returned ref=null. Owner candidates
included an Add-to-Cart-labelled quantity trigger. Top-up now excludes that menu,
reviews a DOM-located independent increment directly when available, and otherwise
uses scoped increment-only visual selection. Owner row quantity-control/row-rect
anchors scroll an offscreen row into view before fresh observation. Existing
extra quantities are reviewed as observed counts satisfying a requested minimum,
not as an exact-match demand to remove the extra units.

126 targeted tests passed (`/tmp/shopping-topup-final-tests.log`), including
observed DOM targets, scoped visual fallback, one input maximum, rejected
post-click quantity mismatches, scrolling using three anchor types, and minimum
versus actual quantity. Mandatory AaAT gate: 214 passed
(`/tmp/shopping-topup-acceptance-gate.log`). No checks were relaxed.

Live task `btask_404bc3c96ae51e9a49a8621497d50b884ce5530a5f3b37a4fee8f7e6b1801635`
actually incremented prunes to 2 and added the missing banana to 1. Both DOM and
visual evidence verified these results. Its later read-only cola review paused;
the task was cancelled before loading the minimum/visibility follow-up. This
history remains intact; no mutation was blindly replayed.

Final live task `btask_5aab09c50976ec2f00a3155d014075eadc6638b28e4137414aceed598e5ddbfe`,
child `run_33b4505b1af84d3cb5bc3b2ca35005cb`, and parent
`run_12391431d25b40ad9809e933a835e4d0` all completed. It reread existing quantities:
prunes2, Chobani1, banana1, Stonyfield1, cola2 (requested minimum1; extra retained).
The cart DOM heading reads Subtotal (7 items): $31.83. Native UI independently
showed the same subtotal and quantities. One Chobani visual review paused despite
the visible quantity1; after direct native-page inspection, the existing Chat
assistance continue button resumed read-only verification successfully. This is
assisted live acceptance, not a claim of zero-intervention visual reliability.
The final owner result is complete and Chat shows Completed plus the verified
product table. Cleanup is verified, remaining=[], without checkout or payment.
