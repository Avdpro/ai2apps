# Social author resolution recovery — 2026-10-22

The failing Dev run resolved a name twice in native Default, but returned sidebar
self navigation as the only candidate. The General Agent then called legacy
browser.open, whose standalone AceFox session lacked native Default login state.

The social owner now excludes navigation/self links on search pages, extracts
Profile links from observed note authors independently of title matches, and
verifies each bounded candidate against its actual same-origin Profile header.
Signed query parameters from the observed link are preserved for navigation.
Search, bounded scroll recovery and Profile verification use the same page and
Profile. Missing/incorrect author headers never establish identity. Exact observed
names rank first; ambiguity still requires the existing user account confirmation.

Desktop composition marks its legacy standalone AceFox backend as requiring
Profile binding. It fails before Helper access/process creation, with a generic
instruction to use Profile-bound BrowserTask/App capabilities and existing
assistance controls. Standalone non-Desktop backend behavior remains available
where explicitly composed. AS/General Agent has no social/site-name branches.
This does not replace BiDi with a semantic API or expose raw browser credentials.

Regression/live Dev evidence to follow. No Cloud changes or publication.

The confirmed read window can extend to 365 days (default remains today), so a
user asking about an infrequently updated account can review older content
without misrepresenting an empty short window. Existing scrolling/time/post
limits still apply, and the exact days/limit remain in the confirmation receipt.

Live resolution acceptance on fixed Dev 61335:
`btask_4bb1a26d4e9807e161fda714d2a8ef0ed2ab927dfaaaeeee3973ad42c02ff703`
returned exactly the observed account 晃悠的程序员 / 5ea41d5f0000000001004026,
identity_source=post_author and identity_verified=true. Its signed observed URL
was verified against the real Profile header; native Default userContext stayed
3fff454d-4118-4ea1-8bbe-f2afb5e5ec27. Owned-tab cleanup verified with remaining empty.

The first read then exposed a separate coverage defect: profile note links now
use /user/profile/<author>/<note>, which the old extractor did not recognize.
A 0-row loading_stalled result was not accepted as timeline verification. The
extractor now accepts these actual nested links only for the confirmed author,
plus existing explore/discovery/search-result forms. It preserves observed query
parameters, scopes links to the same origin, and recognizes leading pinned tags.
Confirmed reads preserve the persisted observed account entry URL as an internal
owner-derived input, rejecting origin/path/identity overrides. This is not a
model-controlled URL field. Xiaohongshu collection stops at the confirmed post
limit to retain time for bounded detail/date hydration; coverage stays partial
when no date frontier has been established.

Final targeted suite: 39 passed; isolated Chrome DOM: 6 passed. Mandatory final
gate and corrected live read evidence are recorded after completion below.

Second live read found 21 stable IDs but returned only list titles/unknown dates;
that was also not accepted as complete content/date acceptance. Some Profile
hrefs were bare client routes. Detail hydration now reuses the existing owner
search helper to locate the observed note control, performs one native BiDi click,
then reads only a visible note container with matching current note ID and
confirmed author Profile. It reads the body even when the date remains unknown,
and returns via native history without replaying an uncertain click. If no DOM
target is present it may use the already-observed read-only URL and restore the
original confirmed Profile URL. No synthetic detail endpoint or hidden data/API
is used. The same time/page budget applies.

Native detail regression: 40 targeted Python checks passed, including one click
per note, full-body/date readback and same-context history; Chrome DOM 6 passed.

## Final accepted Dev evidence

Fixed Dev 63290 read Task:
`btask_644bb1a9ade8e7072c818f7a7109b2ba7c85b009b28c4f8aa886b52d96fd003f`;
child Run `run_675f6bc8b04147fc8b24dda6fb94bbed`;
invoking Chat Run `run_279cf913e144439086fb47bb7b6a3fa4` completed.
The new confirmation showed the persisted verified account, Default, 365 days,
20 posts. It observed 21 stable IDs, returned 19 dated entries (one body only
contains tags), one old pinned entry dated 2021-07-25 local, and one unhydrated
list-only/unknown-date entry. Dated returned IDs are unique and every author ID
is the confirmed 5ea41d5f0000000001004026. Full-body examples contain actual watch
selection/purchase discussion; native click/readback now reaches note content.
Stop reason post_limit and coverage partial are intentional; no exhaustive-year
claim is made. Chat visibly includes the dated content summary, old pin,
unknown/list-only item and partial-coverage limitation.

The final Chat Run used app.collect_parameters, social.account and read-only
agent.read_tool_result only: no browser.open, separate business Agent or isolated
browser fallback. BrowserTask userContext remained the original Default
3fff454d-4118-4ea1-8bbe-f2afb5e5ec27. Task cleanup state verified, remaining []; active
social BrowserTasks zero. Temporary manual investigation tabs were closed, while
the user's original Default home tab was preserved.

Final regression: 40 targeted Python tests; 6 isolated Chrome DOM tests (including
wrong author/note ID and hidden stale container); mandatory AaAT gate 252 passed
(114.80s). Suites overlap and must not be summed as unique cases. App/Helper
retain fixed Dev identities and live-checkout source-root metadata; Local logs
identify current checkout imports and new owner behavior was exercised live.
Python-only activation used standard Helper Local restart while no tasks were
executing. No Cloud change, Package/production publication, credential access or
social write occurred.
