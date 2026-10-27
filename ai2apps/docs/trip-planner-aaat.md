# Trip Planner AaAT owner contract

The trusted adapter is `browser/travel_aaat.py`, registered by the first-party
composition in `services/builtin_apps.py`. App: `ai2apps.ai-browser`; Mini-App:
`ai2apps.trip-planner`. Merely adding JSON to a Package is not the export mechanism.

| Capability | Inputs and scope | Existing Mini-App execution |
| --- | --- | --- |
| `travel.flights` | Origin, destination, departure, optional return date, adults, cabin, stops, airline preference, sites; outbound only by default; return date required for both/return directions | `query`, one Task per site/direction |
| `travel.hotels` | Destination, check-in/out, adults, area/landmark, bed, breakfast, transit, sites; no flight origin required | `query`, one Task per site |
| `travel.guide` | Destination, dates, purpose, preferences; does not require a flight origin | `query` for sightseeing, then `summarize` with actual observed Task references |
| `travel.refine` | Request and existing source Task references; optional previous refinement | `refine`, never auto-submits a proposed requery |

All use the existing shared Browser Task queue, model/privacy routing, durable
human assistance, progress, cancellation, idempotency and cleanup. Website/model
code is not duplicated. Chinese/English form labels and options are owner metadata;
the same declarations/forms serve Desktop and Mobile callers. This does not claim
native Mobile Agent transport rollout beyond the host's existing support.

## Workflow and authority

The Agent discovers independent capabilities through the normal catalog and loads
the selected trusted AaAT declaration. Flight/hotel/guide forms review missing
criteria before research. A cached refinement can run directly when the user's
request and source references are already present. Clarification returns ambiguous;
a requery proposal returns resolved with `requires_review`, not live availability.
The Agent reviews changed criteria with the user, then invokes only the affected
flight/hotel capability through its normal parameter review.

Flight legs are independent research. An outbound card can quote a round-trip
reference; a reverse one-way fare cannot be added to it as a paired total. Prices,
currencies, dates, verification status, native quotes, original links and source
Task IDs remain in results. Empty/unverified/failed sources remain partial; a failed
leg does not discard a completed leg. Sightseeing snippets remain unverified leads.
No capability reserves rooms, chooses fares, books or pays. A returned proposal or
next step cannot authorize effects.

## Access and recovery

Execution requires an owned Session/Installation and a durable Tool invocation.
The existing installed declaration is resolved and Browser Task ownership checks
are retained. Refinement references additionally require the same Session and
Profile and a completed query; prior proposal references require a completed refine
Task. The owner service performs existing trip/evidence checks again. Arbitrary
client observations/programs/URLs are not input parameters.

Discovery only reads existing authorized instances and bounded current-Session
Task metadata. It neither launches the App nor reads another conversation's results.
No result IDs need to be copied manually by the user: the Agent can use the declared
recent-task context. Existing UI Tasks in another Session are not silently imported.
Request IDs derive from the durable invocation and source/direction: restoration
reuses Tasks; a genuinely new reviewed search uses a new invocation.

Normal Browser Task `waiting_input` with `requires_user=false` remains normal work.
Human help uses the same Task and interaction. No replacement query resumes an
uncertain Task. Cancellation cancels sibling observers through a TaskGroup and the
existing Task cancellation path, without introducing another execution loop.

## Review evidence

Owner tests distinguish fixture website/model outputs from live availability.
They cover registration, bilingual forms, schema separation, both legs, privacy
parameters, idempotency, partial failures, progressive source completion, hotel
preferences, guide provenance, Session/Profile checks and review-only refinement.
Run the mandatory `python ai2apps/tests/run_aaat_boundaries.py` from the Git root.
General Agent, discovery/routing and result policies contain no travel-specific
branches. Activation and actual validation results belong in the release ledger.

A departure-only flight request does not invent a return date or lodging dates. Google Flights uses One way and a single selected date; Expedia uses trip=oneway without leg2. Explicit both/return requests still require a reviewed return date.
