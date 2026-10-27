# WebAgent visual control recovery

Owner: shared Local WebAgent SDK; business constraints remain with the calling
App/Mini-App. No General Agent business routes or separate browser protocol.

For a missing/ambiguous control, prefer the current step's selected/pinned task model with an affirmative image-input declaration. Otherwise visual work may use ONLY the explicitly configured image_recognition purpose in the same effective normal/privacy profile. Never select an arbitrary enabled model, another work complexity tier, or a normal route after a system privacy upgrade. Revalidate enabled status and declared image input before capture. With no valid configured route, ask for assistance. Never infer image support from a model name or rewrite global defaults. Durable visual evidence records actual model IDs.

1. Capture the bound context's current visible screenshot through native BiDi and
   gather actual visible DOM refs. Owners may restrict allowed refs further.
2. Vision selects only an observed allowed ref, not a selector, script, coordinate
   or new action. Page text and images remain untrusted data.
3. Draw a red rectangle on a copy of the screenshot using CSS-to-pixel scaling.
   A second model pass must affirm the exact control/entity/action. This image
   annotation does not modify the page.
4. Revalidate document token, URL, context, viewport/scroll, target identity/href
   and geometry, visibility and hit-testing before native input. Input uses the
   reviewed center point, under the original Profile input lock.
5. Dispatch once. Read DOM/state and a fresh screenshot and review the result.
   Owner business predicates remain mandatory. A model saying yes cannot override
   an incorrect quantity or missing business receipt. Uncertain effects never
   trigger an automatic second click.

Model calls and screenshot sizes are bounded; raw screenshots stay in memory.
Durable action evidence records selected refs, model IDs, review decisions and
image digests, not screenshot bytes. Existing action journal, actor/Profile scope,
confirmation, cancellation, persistent assistance and task progress remain in use.

Shopping integration only recovers increments on a uniquely observed cart row in
the confirmed store. Shopping supplies permitted refs, product identity and target
quantity; it rereads exactly previous+1 after each click, before another increment.
It never uses this mechanism to retry an uncertain initial add, change stores,
remove unrelated products, subscribe, checkout or pay. Conflicting/unreadable
quantities remain unverified and cannot authorize an increment.

Coverage includes arbitrary provider goals, no vision metadata, rejected red-box
review, fabricated refs, stale geometry, covered controls, scope/sensitive-input
rejection, failed post-action verification, and owner quantity disagreement.
Fixture tests and live Dev evidence are recorded separately in the acceptance log.

The owner also rereads its exact precondition immediately after model review and
before dispatch: if the quantity changed during model latency, no increment is
sent. A newly satisfied target can finish from that real read; otherwise pause.
The model's first output is the DOM ref; all rectangle coordinates come from the
host's actual DOM snapshot. Use the current step model or the explicit same-profile image-recognition route;
never switch work complexity tiers. A bounded expanded snapshot includes pointer-handled controls, and an
explicit allowed offscreen ref may be moved into view by native scroll before
capture, with fresh geometry and document checks afterward.

## Agent/Task execution policy (2026-10-21)

Trusted Agent Source accepts `execution_policy` and `minimum_execution_policy`.
The trusted WebAgent submission API also accepts an execution_policy override.
Mini-App web_agent/capability declarations can set minimum_execution_policy;
these floors are merged with Source floors before compilation. Task policy is
persisted in the compiled program, passed to each background action, and inherited
by nested capability calls. Page text and result Context cannot set this metadata.

Fields: visual_locating (boolean, default true), visual_review (off /
on_recovery / always; default on_recovery), allow_visual_state_confirmation
(boolean, default false), readback (must be true). A request cannot lower an owner
or parent floor. Unknown fields, non-booleans and readback=false are rejected.
A missing vision-capable current model and missing valid same-profile configured
image-recognition route causes assistance when review is mandatory; there is no
arbitrary model selection, profile switch or waiver. Review off skips screenshot/model review,
while fresh DOM/state readback and existing policies remain mandatory.

`always` reviews a directly located input control too; on_recovery reviews only
visually recovered controls. Shopping owner requires always for cart preparation,
including initial add and increments. Article owner defaults to no visual locating
or review. These are owner declarations, never General Agent identity branches.
Readback means reacquiring actual post-operation evidence: DOM, structured business
state or receipts. `verified=true/false/null` is the generic owner predicate:
false is a contradiction, null/missing is unknown. Only unknown may be resolved
by positive fresh visual evidence when allow_visual_state_confirmation=true.
An owner's exact quantity or required receipt cannot be waived by vision. Visual
confirmation records a separate evidence source; it never authorizes a retry.

Scrolling recovery is bounded to an already observed permitted DOM ref outside the
viewport. Scroll, recapture and revalidate before review. This is not unbounded
scroll-search for not-yet-loaded targets.

Direct owner control rectangles use the same one-decimal Math.round representation
as browser_snapshot.js before exact matching to a unique observed DOM ref. This
normalizes raw getBoundingClientRect doubles; it does not add a wider geometric
matching tolerance. Ambiguous/colliding or differently rounded rectangles fail
before input. Fresh document/ref/binding/hit-test checks and red-box review remain
mandatory under the task policy.

### Read-only state review and malformed decisions (2026-10-22)

The Shopping owner may scroll an already observed, uniquely matched cart row into
view before reviewing existing quantities, then reread DOM. Scrolling performs no
cart mutation. Shared visual decisions reuse the common bounded JSON repair policy,
with the existing six-model-call ceiling retained. Only model values over the same
frozen observation are repaired; input is never replayed. Exhausted read-only decision
repair becomes VisualRecoveryUnavailable; exhausted repair after dispatched input
remains VisualActionUncertain. Assistance retains observed quantities and concrete
visual-review reasons rather than presenting a generic unknown count.

## Fast search call policy (2026-10-24)

Visual assistance is a persisted Task execution parameter, not an inference from
a timeout or App identity. The default remains visual_locating=true and
visual_review=on_recovery. Fast search owners explicitly pass
`execution_policy={"visual_locating":false,"visual_review":"off"}` for both source
search and every candidate-page read. The immutable confirmed search mode is
carried into the durable read operation; normal reads retain the owner/default
policy. Shopping retains its declared always-review behavior and quantity readback.

Fast mode rejects a capability whose mandatory owner floor requires vision rather
than weakening that floor or silently doing visual work. Reusing a submitted Task
with an explicit different execution policy fails; it never updates the original
program or creates an effectful retry. Ten-second fast read budgets now have no
visual branch competing for the remaining time. DOM/loaded-body extraction,
access checks, strict citations and unattended skip/replacement remain in effect.


## Persisted Task execution budgets (2026-10-24)

The same execution_policy now also accepts allow_user_intervention (true),
timeout_seconds (null), recovery_timeout_seconds (null), max_recovery_attempts
(null). Null adds no new cap and does not remove legacy guards. Total deadlines
start at queue admission; recovery reservations and cumulative elapsed time are
stored in the existing Task/Run context. No assistance/approval Interaction is
created when intervention is disabled. Nested calls cannot refund budgets or
re-enable disabled intervention/vision; conflicting mandatory owner checks fail.
See [Task execution policy](task-execution-policy-20261024.md) for exact accounting,
legacy bounds, zero values, fast search overrides and restart behavior.


### Configured visual purpose and native icon observation (2026-10-26)

Review rationale: some installations deliberately configure a text-only work model
and a separate image_recognition model. Reusing that explicit shared purpose avoids
incorrectly reporting vision unavailable without changing user defaults. Text
planning/DOM repair retains its pinned work route; only visual selection/review
uses the configured image purpose when necessary. Tests cover two arbitrary
providers, normal/privacy profiles, system privacy upgrade, missing declarations
and unavailable models. This has no site/App identity branches.

Unlabeled i/svg pointer controls inside focusable controls require visual review
even when directly located by ref. A narrow controlIcons visibility option can
observe a rendered icon whose own aria-hidden marks decoration; CSS-hidden,
inert/transparent or aria-hidden ancestors remain excluded. Ordinary content reads
retain the default aria-hidden policy. Popup anchors observe only trusted
native/user pointer events and never authorize an operation.

### Access gates after a single native action

A failed visual readback must not conceal a definite authentication or CAPTCHA
blocker. The executor may inspect the current and owned related windows within
the existing site scope, without dismissing a prompt, reading credential values,
or replaying input. A confirmed gate returns its specific assistance kind and
owned context, with automatic replay disabled. Generic login detection uses a
visible dedicated sign-in title/heading plus a password form or sign-in path;
a normal navigation login link is not an access gate. An OTP login tab on such
a page is authentication, not proof of CAPTCHA. Arbitrary provider fixtures
cover scope exclusion, context restoration and no-input handoff.

### Profile input critical section (2026-10-27, P1)

Visual selection and marked-target model review execute without the Profile input
lock. After admission to that lock, re-observe the bound context and validate the
reviewed document/URL/viewport/target binding, hit test and owner precondition.
Reject drift before dispatch; waiting for the lock does not authorize rebinding a
different target. Preserve single input and all existing unknown-effect rules.

The lock spans native preparation/input, owner readback and capture of fresh
post-action DOM/screenshot. Freeze that evidence and release the lock BEFORE the
after-state model call. Its verdict describes the captured state, not a promise
that a dynamic page remains unchanged until the model returns. Every subsequent
operation still needs its own current binding and owner precondition. Readback
and preflight callbacks must perform native/DOM work only, not model waits.
Cancellation/errors leave the input context manager; uncertain input is never
re-admitted for an automatic second click. Local logs contain run/context IDs,
wait/hold milliseconds and conservative dispatch state, not goals, body text,
input values, screenshots or credentials.

This changes Profile input capacity only. It adds no native rendering lease,
removes no visibility/activation checks and makes no energy or no-focus claim.
Phased plan: [on-demand resources](webagent-demand-rendering-implementation-20261027.md).

### Input dispatch and focus diagnostics (2026-10-27, P2)

BackgroundPage centralizes native pointer/key/wheel commands and the existing
bulk editor mutation path. Per-action diagnostics contain only context IDs,
command kinds, conservative dispatch/acknowledgement state, readback observation
status and protocol unhide/activate counts. Keep at most64events plus aggregate
counts. Acknowledgement or observed DOM is not proof of the owner's business
predicate. A partial composite action never becomes wholly not-dispatched merely
because its last keyboard command could not start. Evidence is saved with the
existing journal response; a crash without a saved response remains uncertain.

Transport reports command_dispatched=false only before a send starts (including
cancellation while waiting for its send lock). Send errors, lost replies and
post-send cancellation remain potentially dispatched, never auto-replayed.
Runtime preparation may retry once only before any tracked input and within the
existing recovery budget, always on the same bound context. Repeated preparations
cannot refund budgets or resume an uncertain input. A verified not-dispatched
failure is committed as its own durable response rather than misclassified as a
lost input reply; unattended policy still suppresses user intervention.

A visible bound context uses directed native BiDi input without explicit
activate, even with document.hasFocus() false. Hidden pages retain unhide,
activate and bounded real visibility checks. No CSS or visibilityState spoofing.
Pure article/list DOM reads do not call this preparation path. Real OS foreground
state is unavailable to this SDK and is explicitly null; protocol request counts
are not OS foreground counts. No universal no-focus promise or rendering-lease
claim. Native and Intelligence evidence:acceptance/webagent-dispatch-focus-20261027/.
