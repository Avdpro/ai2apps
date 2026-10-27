# X social account AaAT acceptance — 2026-10-22

AI Browser owns `social.resolve_account` and `social.read_account`. It resolves
observed X identities, shows an account confirmation form with name, handle, bio,
avatar and original link, then reads bounded recent posts in the existing Profile.
The owner declarations prefer this route for account activity over broad research.
General Agent has no X/site/provider branches. Other social platforms are not yet
implemented.

Browser work uses existing WebAgentInvocation and BrowserTask dispatch through
Shell Default, with native BiDi. The generic registered read hook requires the
stored Task owner, run and caller binding. It does not execute model code. Login
assistance stays in the same Profile; it never launches legacy Browser Agent.
Completed Task tabs use existing verified cleanup.

Authorization labels and scopes are localized, including old pending records;
remembering one tool does not authorize all tools in the same capability. Nested
Search All failures have short summaries and retain structured diagnostics.
No historical error records or persistent grants were rewritten.

## Tests

- Mandatory AaAT boundary gate: 224 passed before retry-reference regression.
- Social owner regression: 9 passed including persisted read-to-resolution retry,
  foreign Session rejection, observed identity, exact confirmation, login pause,
  timezone/pinned/repost filtering and cross-provider dispatch isolation.
- JavaScript parameter/approval checks: 19 passed.
- Isolated Chrome form and real DOM extraction fixtures: 3 passed. Fixtures cover
  exclusion of sidebar account recommendations and safe option-preview links.
- A mixed-name initial live search exposed sidebar recommendations; extraction was
  corrected to primaryColumn search results and explicit Profile headers.

## First live Dev acceptance

Prompt: 今天马斯克在 X 上发了什么帖子？
Root Run: `run_66baca39ec6f4e30a29e9dad6d1ae18d` (completed).
Resolution: `btask_80d88f985fd53409b6317cda690961f527e54b1c6532fd75ca125823d7c229a7`.
Read: `btask_c982d23c794e8f3da06d3832c86a762e688cc7710a3a8698dd7609e089a847eb`.

Actual tool sequence selected the social capabilities, resolved candidates,
opened one explicit account confirmation and read @elonmusk. No Search All,
Intelligence research or legacy browser.open fallback; no capability approvals.
The read used Default userContext `3fff454d-4118-4ea1-8bbe-f2afb5e5ec27`, shared
with the resolution and earlier Default Tasks, retaining authenticated login.
Cleanup reported verified with no remaining owned tabs.

The result observed 11 posts and returned 10 within Asia/Shanghai
2026-10-22 00:00–04:10, with timestamps and original links. Chat visibly displayed
the final answer and partial-coverage qualification. This is bounded observed
coverage, not an exhaustive today/archive claim. No follow/like/repost/reply or
other social writes were performed.

A final repeat exposed a model passing the previous read Task as resolution_task.
The owner now follows that Task's stored resolution evidence with Session/Profile
checks; the failed draft was cancelled before restart. Final activation and repeat
acceptance are recorded below.

## Final current-code repeat

Dev Local restarted through the standard Helper to port 61138. App and Helper
source-root metadata point to the live checkout; imported owner module logs show
this checkout and the served parameter-form JS matches its bytes.
Final boundary gate: **225 passed** (111.44s); social tests: **9 passed**.

Repeat parent `run_3d0da7c4748846a09a7c7d050052616e` attempted a direct read,
which the exact confirmation guard rejected, then opened the proper form. The
model omitted resolution_task on that form; acceptance supplied the already
observed previous read reference through the UI and confirmed the known account.
Thus this repeat validates owner reference recovery, not autonomous completion
of a missing-reference retry. First natural-language acceptance above was
unassisted apart from clicking the explicit account confirmation.

Current-code read `btask_8befaf3806ef5f9b7971f4ce053a069f1767c7f3a848e62565802e9590a28d82`
completed through the stored Task/run/caller guard in the same Default userContext.
It returned two actually observed in-window posts, partial coverage, with window
ending 04:24:53 Asia/Shanghai; results can differ as X renders/scrolls dynamically.
Terminal cleanup is verified, remaining owned contexts empty. No expanded grants
or social writes. No Cloud, Package or production Desktop publication.

Final owner form refinement automatically fills a missing resolution reference
from the newest completed same-Session, same-Profile resolution containing the
requested observed handle. Foreign or invalid references yield a controlled 422,
not a server traceback. This restores evidence only; exact user confirmation and
execution authorization remain mandatory. An additional fixture covers missing
reference recovery and foreign-Session exclusion.

Dev 63617 loaded this final owner module from the checkout and served byte-equal
form JS. Live follow-up requested the same account confirmation without supplying
an ID; the form automatically showed the stored resolution, Elon Musk (@elonmusk),
bio, avatar and original link. This form-only acceptance was cancelled without
another browser read. The earlier successful read path is unchanged.

Final delivery regression: **226 passed** (full mandatory boundary gate), including
10 social owner checks. The earlier 225 count predates the missing-reference form
regression. Final Dev is 63617, with no active social BrowserTasks remaining.
