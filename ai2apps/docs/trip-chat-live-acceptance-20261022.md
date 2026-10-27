# Native Chat Trip Planner acceptance — 2026-10-22

Environment: isolated App-Dev, existing configured Cloud DeepSeek V4.1 Flash.
Native Chat in Agent mode; prompts and form submission used the normal UI.
Session `ses_30727b0974d74330bd6cc8c6af3c666e`.
No booking/payment or account changes. Dev was not restarted.

## Initial query

Requested 2026-11-01 San Francisco → Beijing, return 2026-11-06, one adult,
economy; Booking near Summer Palace, one room, Nov 1–6, initially any bed/stops.
Agent discovered `travel.flights`, reviewed its declaration, displayed the correctly
prefilled bilingual form, and created the two existing public Browser Tasks.

| Task | Native result |
| --- | --- |
| `btask_fcf37f4829146f6b14223ac1b78cd6714313defbad6a95a7d6d6aec0f6967dd3` | Five verified outbound candidates; round-trip reference prices |
| `btask_0d961dc410d57264baa9008f14fc19f5430a194499b754bf599e1a97a2eb2d44` | Six verified return candidates; independent one-way prices |
| `btask_9b4db6dc9a71fa68bb4376f8f89890a16bf70bf90ccd74b535606ad885bf9e3c` | Booking failed at location correction with action limit; no fabricated recommendations |

Chat displayed both fare scopes and explicitly did not sum incompatible fares.
The hotel form retained Summer Palace and exact dates/adult count.
Browser response waits were correctly presented as normal execution.

## Fixes exposed by this run

Booking reused an autocomplete option DOM node: a previously observed landmark
option became an individual property while retaining its old ref. The recorded
action intention and actual clicked option differed. Shared snapshot refs now
rotate when observed semantic identity changes; input value edits retain identity.
The existing no-fallback rule for stale explicit refs then forces re-observation.
Owner location instructions distinguish geographic areas/landmarks from properties
and allow the verified English name of the same landmark on English sites.

Review also covered combining independently queried flight and hotel observations:
the refinement owner preserves flight dates/origin and hotel-specific dates/area
instead of discarding hotel scope by copying the first flight trip. Conflicting
trips remain rejected. The new unit case reproduces distinct check-in/flight dates.

Validation before activation: 103 Python owner/SDK checks, 11 Chrome checks,
including arbitrary option names, same-node text changes and stable edited inputs.
Mandatory AaAT gate and native retry/filter acceptance are recorded below when done.

The first native retry (`btask_28f1dd1d0218d6275c3f6922fca58aba630e7470e5a92a5307b693a90c14df6a`) exposed a separate owner workflow issue: an interpreted preparation step tried to trigger Search and was rejected as `foundation_submission_disallowed`. Hotel location preparation and compiled owner Search are now separate, preserving the shared guard. 53 owner regressions passed after this change; native retry continues in the same Chat Session.

A transient Chat Cloud 502 occurred before any new hotel Task and recovered on the next native retry. The next hotel Task (`btask_c60005b4df46825954e998c84b78f5d477b13623aaef0d8200b4c6ab58a6bc0d`) demonstrated stale-ref rejection and correct selection of the Beijing Summer Palace suggestion, but the interpreted preparation stage kept re-opening that already-correct field while viewing old result cards. Preparation completion is now explicitly based on the main form only; the following compiled Search owns result refresh. No shared guard or action budget was weakened. 53 owner checks passed again.

## Final native acceptance

The corrected native retry completed as
`btask_3dcf4a0b4e9c76366b674c88eaef43642d66e6c36bfa58d3f66b142034ab3765`.
The public `travel.hotels` Tool returned six source-backed recommendations, with
Summer Palace / Beijing, Nov 1–6, one adult and one room verified. Chat rendered
hotel names, source links, distance, room evidence and five-night USD price basis.
Previously completed flight Tasks were retained and were not resubmitted.

The follow-up asked both flight directions to be nonstop, hotels to have a large
bed rather than twins, and all dates/occupancy/area to remain unchanged. Agent
selected `travel.refine`; Task
`btask_3b47b917c6ea320aa3bfe6aa2021c12cc144686fc5a13d649a24b15249be472f`
used exactly the two original completed flight Tasks plus the successful hotel
Task. Result action was `filter`, nonstop_only=true, hotel_bed=large_double; the
owner preserved original dates and Summer Palace scope while combining the
independently queried flight/hotel inputs. It selected one outbound nonstop,
one return nonstop and six hotels whose native room text contained Queen/King
or double-bed evidence. No additional website query was submitted for refinement.
The observed hotel sample had no twin-room candidate; Chat correctly explained
that absence was not proof of full website coverage or a guaranteed bed width.
Native Chat displayed the completed answer and source links, with no booking or
payment and no combined price formed by adding incompatible fare scopes.

Final Session records: three completed query Tasks, three definitively failed
query Tasks from the earlier attempts, one completed refine Task, no active Run.
Tests after the final owner prompt: 53 owner regressions passed; earlier shared
SDK coverage: 51 Python tests and 11 Chrome tests passed. Mandatory AaAT gate:
245 passed, exit 0 (existing headless Metal atexit warning). These automated site
responses are fixtures; the native flight/hotel/refinement observations above
are actual website/LLM execution, not fixture availability claims.

Final App-Dev: PID 68716, port 56369, health 200. App/Helper source-root metadata
and actual imported `services/builtin_apps.py` path match this checkout; actual
served `browser_snapshot.js` and `browser_bidi_client.js` bytes match source.
Dev was not restarted. The tested conversation remains in Chat for review.
