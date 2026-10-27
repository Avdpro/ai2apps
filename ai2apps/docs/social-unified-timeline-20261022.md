# Unified social account AaAT — 2026-10-22

## Implementation

AI Browser exposes one `social.account` capability/provider for X, Xiaohongshu
and Weibo. A platform parameter selects the owner adapter. Resolution returns
observed identities; the same capability's reading form confirms identity and
scope. General Agent/AS has no platform/business branches. Superseded split
Tool descriptors are disabled through generic service registration-set cleanup.

The owner normalizes display-name `handle` aliases into resolution `query`,
infers the default resolution stage, and validates stage-specific required
fields in provider preparation before submission. Mixed-language X searches
with no candidates may retry the literal ASCII portion of the supplied query;
this never invents an identity. Reading still requires actual observed candidates,
the same owner/Session/platform/Profile and an exact current durable confirmation.

X accumulates stable post IDs across overlapping virtualized views. It scrolls
until an ordered, non-pinned/non-repost account frontier crosses the requested
local date boundary. Old pins do not trigger termination; pins outside the dated
result list are separate. Limits are 120 DOM reads / 180 seconds, with delayed
load retries and eight unchanged-read stagnation detection. Output defaults to
200 posts (maximum 500). Unknown dates, truncation or any loading/budget limit
produce partial coverage and an explicit stop_reason. A boundary observation
means observed-page coverage, not an exhaustive platform archive.

Xiaohongshu and Weibo have scoped account and timeline DOM adapters. Xiaohongshu
can read up to 20 undated note detail pages within the same time budget, checking
observed author and date. Unknown dates remain separate evidence; note IDs do
not supply dates. Existing native Default login state, BiDi, BrowserTask ownership,
read-only execution and terminal owned-tab cleanup remain unchanged.

One account confirmation binds one durable read Task key, independent of model
invocation IDs. Identical confirmed calls reuse the existing Task/result; a new
user request requires its own confirmation. A cancelled child propagates standard
cancellation after persistently cancelling the exact trusted invoking Run in the
same Session. A bare cancellation exception alone is insufficient because the
durable runtime treats worker interruption as recoverable. Cross-Session parent
cancellation is refused. This is owner lifecycle handling, not an AS exception.

Login assistance uses the existing assistance_message protocol. Pending child
assistance projects into Chat task-progress requires_user/wait_reason and the
existing page/continue/cancel controls; executing browser requests do not pretend
to require user intervention.

## Regression evidence

- 22 social owner checks cover cross-date scrolling beyond eight views, old pins,
  stable-ID deduplication, stalled/unknown/unsorted data, platform scope and identity,
  exact confirmation, same-confirmation Task keys, parameter normalization,
  assistance state, cancellation and foreign-Session parent protection.
- 3 isolated Chrome DOM tests cover X identities/pins, Xiaohongshu account,
  note detail/date/body and observed links, Weibo identities/post dates and wrong
  account rejection. Fixtures are not authenticated live-platform acceptance.
- Final mandatory AaAT gate result is recorded below.

## Live Dev evidence and limitations

X resolution Task:
`btask_1c5ed411a1f6b11846d509720d1d70a29b87e8f31cdff11b54da2aff9163db8d`.
Confirmed read Task:
`btask_88d5b52d27dfd64120f4c1e57f396d053a8d2b6eb43d4b1ddab0d40864930552`.
It observed 21 rows over 24 DOM reads, returning 10 today's posts and one old pin,
then reported loading_stalled / partial because no reliable date frontier was
reached. Owned-tab cleanup was verified, remaining empty. The model's subsequent
identical reads exposed the per-confirmation idempotency fix described above;
that earlier test Run was stopped. Do not claim a complete live X timeline.

Weibo resolution Task:
`btask_f4913a9305a87ebc3f6b793eca8c2aabd8ec82b954a8bfbf8a4bf0435e3c8733`
returned actual candidates including 人民日报 / 2803301701. Xiaohongshu resolution
reached a real login requirement on xiaohongshu.com only (see the dual-home correction below). Both reused Default userContext
`3fff454d-4118-4ea1-8bbe-f2afb5e5ec27`; no login or social writes were performed.
Authenticated Xiaohongshu timeline and live Weibo timeline acceptance remain
unverified; the DOM fixtures cover their implementation paths.

Dev 53369 visibly showed the Xiaohongshu login explanation and 前往问题页面 /
已处理，继续 / 取消任务 directly in Chat. Final cancellation-chain acceptance and
source activation are recorded below. No Cloud/Package/production publication.

## Final acceptance

Mandatory boundary gate: **238 passed** (112.88s). Isolated Chrome DOM: **3 passed**.
The gate includes the 22 social owner checks; counts overlap and are not summed.
Final Dev is 55154; App/Helper source-root metadata remains the live checkout and
startup logs confirm the imported built-in owner module at that checkout.

Final live cancellation parent `run_426af9b34d7c44dc931cefb9404f5027` became
cancelled after the Chat 取消任务 button. Child
`btask_023f6d01910ea742da4eb01e874fdc206de8766be6eeca1869f2123b7be227a2`
is cancelled with verified cleanup and remaining contexts empty. Chat visibly
shows Cancelled; active social BrowserTasks are zero. No automatic resubmission
occurred after the persisted parent cancellation. No credentials, persistent
permissions or external social state were changed.

## Dual-home Xiaohongshu correction

The earlier login observation applied only to `www.xiaohongshu.com`, not to the
Default Profile's separately authenticated `www.rednote.com`. Resolution now
probes both HTTPS homes in the same page/Profile and records each observed state.
Visible self-profile navigation establishes login evidence; feed author links do
not. A visible login wall requires assistance; unknown/unavailable pages never
claim the user is logged out. Prefer an observed logged-in home, then an unknown
home for further read-only inspection. Both login-required homes prompt login;
other unusable combinations prompt page verification instead.

Both brands remain one owner capability. The chosen site origin is persisted in
resolution evidence and injected internally into confirmed reads, rather than
accepted as a model-controlled parameter. Historical observed candidate URLs may
supply an exact whitelisted origin. Site scope includes only the two exact brands
(bare/www HTTPS); no new Profile or cookie access is introduced.

Live manual Dev check: the same native Default window displayed authenticated
self navigation on rednote.com and a login modal at xiaohongshu.com/explore.
Restored rednote.com afterward. Automated task acceptance is recorded separately.

Dual-home live owner Task: `btask_e0fc5664461297eb70c74bd436fe634b959d858757e849d6fae9fede5e714a9b` completed in Dev 57528. home_checks observed rednote logged_in and xiaohongshu login_required; site_origin was https://www.rednote.com. It resolved MicroDuck / 615fda44000000001f03494f and returned the result visibly to Chat. Default userContext remained 3fff454d-4118-4ea1-8bbe-f2afb5e5ec27; terminal cleanup verified with no remaining contexts. This is authenticated live identity resolution, not timeline acceptance. The run additionally exposed sidebar self-navigation appearing among candidates; current Profile resolution now filters candidates to that exact observed Profile ID, covered on both domains in Chrome fixtures.

Final filtered live acceptance: Task
`btask_796cc0987de7ce0ad18f24115395b739dab7e4a385ab6a79ca64eba02bf03141`
completed in Dev 58379, returning exactly one MicroDuck candidate, with the same
rednote logged_in / xiaohongshu login_required home_checks. Chat visibly displayed
Completed and the new single-candidate result. Cleanup again verified, remaining
empty; Default userContext unchanged. App and Helper source-root metadata match
the live checkout; restarted Local logs identify the built-in owner registration
module in that checkout. This runtime behavior exercises the changed owner code.

Final Chrome DOM regression: 4 passed. The new resolver integration fixture reads
execute's standard outcome/evidence/result envelope; its initial assertion used
the wrong envelope level and was corrected without changing execution behavior.

Dual-home final mandatory gate: **245 passed** (110.74s), including 29 social
owner cases. The separate Chrome DOM suite has **4 passed**; counts overlap and
are not summed. No Cloud changes or publication. Authenticated timeline reading
coverage remains outside this dual-home resolution acceptance.
