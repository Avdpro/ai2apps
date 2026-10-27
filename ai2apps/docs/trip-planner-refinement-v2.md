# Trip Planner: refinement, dates and return-direction research

Owner: `browser/travel.py`, `browser/travel_refine.py`, source Package `packages/ai2apps-trip-planner`. General Agent and shared model transport are unchanged. Public Mini-App declarations expose `refine` beside prepare/query/summarize; the existing Browser Task is the only execution source, using existing normal/privacy/system-privacy routing.

## Flow and evidence

- Initial flight research creates outbound round-trip reference and independent one-way return-direction Tasks. The return query reverses cities, uses the confirmed return date and explicitly switches to One way. These are not paired fare offers; never add their prices into a round-trip total. Existing outbound results have a return-only entry that reuses an existing return Task when available.
- The prompt proposes a cached filter, affected-source requery, or clarification. Cached selection binds server-owned Task/item IDs and native quote evidence. Only whitespace is normalized; native rows and quotes render unchanged. A lowest-price request orders the loaded comparable prices by provider/leg/currency, not the whole market. Unknown price formats remain unknown.
- New cabin/dates/route/room requirements without observed evidence require a requery proposal. Website queries execute only after the user confirms the displayed field changes and sources. Clarification replies use the previous same-owner/Profile/trip refinement Task; arbitrary frontend observations are rejected by the declared schema.
- Hard direct-flight/cabin/large-bed/twin/breakfast/transit preferences require native card or search-control evidence. A subway-access label is not proof of an exact walking distance. Not requiring breakfast removes that requirement; it does not exclude every hotel offering breakfast. Ambiguous extra-night/airline-region requests ask questions rather than inventing dates or airline scope.
- Result-date controls independently edit flight and hotel dates. Relevant provider identity determines whether saved observations are still current. Previous Task references remain in a bounded query history; switching or refreshing does not silently resubmit work. No reservations, room/fare commitments, payments, account changes or Cloud changes.

## Review gate

Business semantics and source eligibility remain in the owner adapters. The broker changes are trusted Mini-App composition and projection only. Actor/mount/caller/Profile/idempotency/cancellation and public model-routing guards remain in use. No new generic Agent identity branch or browser protocol is introduced.

Google city selection can retry the same city’s standard English name after an observed “No matching locations” response; it must verify an actual city/country suggestion and cannot invent an airport code.

Native input activates only the already-bound page under the shared Profile input lock and waits for its actual document visibility. Hidden tabs can freeze CSS menu animations at time zero; waiting for stable text alone does not make their options visible. Background read-only loading remains parallel, and existing DOM visibility rules remain unchanged. This generic SDK behavior has arbitrary-context coverage and fails before input if the page stays hidden.

Tests: 113 owner/public Mini-App and shared browser SDK Python checks, including normal/privacy/system privacy and idempotency; 9 Chrome checks including 390/1100px progressive results and refinement, confirmation, selective requery, return-only entry and restoration. AaAT boundary gate: 245 passed (exit 0; existing headless Metal atexit warning). Fixtures are not claims of live travel availability. Live App-Dev activation/acceptance is recorded in the release ledger.

Live acceptance (2026-10-22, App-Dev): cached refinement ordered the observed USD 904/994/1028 offers without website requery. Return Task `btask_0b068407a8441a735017c415c0dfd04e245e8f6f3a0619fb0ebbc83a55a712b2` completed Beijing → San Francisco, 2026-11-06, one adult; seven native cards, six evidence-bound projected candidates, including nonstop. Native Mini-App displayed the completed return card. Flight prices are ephemeral observations, not fixtures or promises of availability. Selected trip-type/cabin reader coverage was added afterwards and tested with visible-vs-hidden controls. Full live combinations of every hotel/cabin/airline preference were not exhaustively exercised.
