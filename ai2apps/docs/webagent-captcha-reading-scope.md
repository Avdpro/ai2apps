# WebAgent CAPTCHA blocking scope — 2026-10-27

CAPTCHA presence is not evidence that it blocks the current read. Native Local
and frontend BiDi SDKs share the identical DOM inspector. Its default remains
strict for interactive access checks. Trusted article/list read paths explicitly
select read-only inspection; this does not change task authority, navigation,
input validation, user-assistance policy or ownership.

For read-only inspection, a CAPTCHA in a blocking dialog, large positioned
viewport overlay or dedicated verification page remains needs_user/captcha.
An unrelated inline/footnote/form challenge does not stop an article whose
rendered paragraphs outside forms/navigation/aside/dialogs establish readable
content (at least160characters). Hidden content does not qualify. Dedicated
verification headings still block even when their instructions are long. Sparse
or uncertain content remains conservatively blocked. No gate is removed, no
hidden article/script/network payload is retrieved, and no CAPTCHA is clicked
or solved. Existing authentication, paywall and consent guards remain in force.

Article overlay fallback no longer reclassifies the entire page on a bare
CAPTCHA word after the scoped inspector has run. Interactive/default inspection
still requires help for the same CAPTCHA form; action workflows have not been
opted into the read-only exception.

## Evidence

- Two unrelated fixture origins cover inline/offscreen registration CAPTCHA,
  articles discussing verification, real dialogs, large overlays, long full-page
  verification instructions, hidden article paragraphs and strict-mode controls.
- Offline replay of the actual stored failed DOM: strict mode needs_user/captcha;
  read mode none;15article paragraphs loaded. All network requests blocked in the
  replay; no original website visit/registration/submission/model call.
-101Python access/background/pool tests and35Node/realChrome tests passed.
- Mandatory AaAT boundary gate394passed(exit0; existing headless Metal atexit
  warning retained). No domain/App-name branch was added to shared execution.

Local Python needs an idle Helper restart; frontend assets carry a new version
and activate on refresh. No native browser/App rebuild is needed. Previously
failed collection results are not rewritten or automatically replayed.

Activation:App-Dev new import/served SDK verified. Dev activation is pending an
idle Local restart because existing user-assistance/Agent interactions remain
active; those tasks were not interrupted or cancelled.
