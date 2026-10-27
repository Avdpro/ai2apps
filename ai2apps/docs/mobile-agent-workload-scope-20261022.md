# Mobile Agent workload scope repair

The reported mobile Run `run_3dee59e4fd9148688c3a987bdf678b5d` first failed
with `app_instance_not_found` while resolving an account. Its originating Chat
instance existed, but the trusted browser executor reconstructed a Desktop
principal and lost the Session's `owner-home` client scope. A later attempt to
open an unregistered handoff capability produced `invalid_app_interaction` and
ended the Run. Mobile rendered the same terminal status and error twice.

Internal WebAgent submission now derives the originating client scope from the
owned active Session's canonical persisted AppInstance key, then runs the normal
access guard. Caller parameters cannot supply that scope. External HTTP guards,
owner checks and current membership checks remain in place. An invalid interaction
which opened nothing is eligible for the existing bounded preparation correction;
effectful unknown results are still ineligible for automatic retry. Identical
mobile terminal status/error text is rendered once; distinct details remain.

Validation on October 22:

- 44 related Python tests passed, including arbitrary provider identities, mobile
  scopes, foreign owners, archived Sessions and real invocation preparation.
- 11 Node/Chrome mobile UI tests passed, including repeated status snapshots and
  distinct error details.
- Mandatory AaAT boundary regression: 252 passed. The existing headless Metal
  atexit warning did not affect successful exit.
- Idle Dev Local restarted through its Helper: PID 94234, port 58454, boot
  `dc4539ee-51ef-4170-a402-3703f35aeccf`. App and Helper source-root metadata point
  to the live Git checkout; new Local logs show live `builtin_apps.py` and
  `social_media.py` module paths. Served `/mobile/static/js/mobile_agent_chat.js`
  exactly matches the changed source bytes.
- Read-only verification against the actual failed mobile Session
  `ses_eeb768e5a9824cc4aaedba50561abf8e` restores `owner-home` for the trusted
  workload, while the original Desktop HTTP principal still receives 404.

The model correction and phone UI behavior above are regression fixtures; the
actual Session verification uses Dev data without submitting a new browser task.
A complete phone-signed rerun remains to be performed from the phone after a page
refresh. No Cloud code or business-specific shared Agent branch was added.

## October 23: outer adapter coverage correction

Phone Run `run_aa10a2d781ea4a58af72e34e7c776536` exposed an incomplete repair:
the built-in AaAT handler's initial Session guard ran before WebAgent submission,
and its `principal_for` still reconstructed a Desktop principal. No browser task
could be submitted. The original validation tested the inner invocation guard,
not this outer adapter, so it did not demonstrate the full provider path.

The identity module now owns `workload_session_principal`, which restores only
the scope of an owned active Session. Both internal API authorization and the
common AaAT principal factory use it. The adapter retains its ordinary App access
guard. This avoids a shared AS dependency on HTTP API ownership code; the first
implementation of that dependency was rejected by the boundary gate and removed,
without changing or weakening the gate policy.

New tests exercise the public capability router's preparation and outer built-in
handler through real social WebAgent enqueue in a mobile Session, with only the
website-result observer stubbed. A separate Gallery provider verifies the same
identity recovery, while installation mismatch, missing/foreign Sessions and
direct Desktop HTTP access remain denied. No live website completion is claimed
by these tests. The two screenshot cards are separate historical Runs, rather
than duplicate rendering of one error.

Follow-up verification: 50 relevant Python tests and all 252 mandatory AaAT
boundary tests passed (exit 0). Final Dev activation
is PID 8696 / port 52765 / boot `38eabd74-ab98-43e1-a284-e2bfaeb8db93`.
App/Helper live source roots, live Local adapter import path and served mobile
asset bytes were checked again. Read-only execution of the outer principal
factory plus its subsequent access guard against the real failed Session passes;
direct Desktop access remains 404. The phone-signed full rerun is still pending.
