# Web-Agent Mini-App Package contract v1

Web-Agent Mini-Apps are ordinary App Packages hosted by `ai2apps.ai-browser`. They use the same
Package discovery, installation, AppInstance, sandbox mount and private MessageChannel contract as
Imagine Studio Mini-Apps. They add fixed UI and multiple independent capabilities to AI Browser's
**Apps / 应用** tab; they do not introduce another Package type or browser execution engine.

## Package declaration

Web-Agent Mini-Apps also follow the [Discover development/publication gate](ai2apps-studio-mini-app-package-contract-v1.md#development-and-publication-gate-2026-10-13).
Explicitly declare catalog categories and the `ai2apps.ai-browser` host placement; retain the generated
signed `miniApps` projection. A host-only provider uses `navigation.launcher: false`. Source discovery in
AI Browser is not proof of public Discover visibility; verify a clean, uninstalled client's catalog too.

Develop under the trusted repository `packages/<package>/` tree, with `ai2apps.json`, `app.yaml`
and indexed UI resources. Follow `ai2apps-studio-mini-app-package-contract-v1.md` for source mounts,
signing, immutable file indexes, installation, upgrades and removal. The App entrypoint remains
`kind: sandbox`; `navigation.launcher: false` is appropriate for a host-only Mini-App.

```yaml
mini_apps:
  - schema: ai2apps.mini-app/v1
    id: example.web-reader
    name: Web Reader
    version: 1.0.0
    kind: project
    icon: globe
    entry:
      kind: sandbox
      resource: web/index.html
      placements: [inline, sidebar]
    placements:
      - {studio: ai2apps.ai-browser, category: web, order: 100}
    web_agent:
      schema: ai2apps.web-agent-mini-app/v1
      capabilities:
        - id: article
          title: Read article
          description: Read an article on the declared website.
          source:
            agent_type: web
            site_scope: ['https://example.com/**']
            inputs:
              type: object
              properties:
                url: {type: string, minLength: 1}
              required: [url]
              additionalProperties: false
            steps:
              - name: read
                operation: read_page
                execution: {mode: compiled}
                arguments: {url: '${input.url}', new_tab: true, close_tab: true}
                on: {success: done, failed: failed}
```

The signed `web_agent` declaration contains 1–32 unique capability IDs and at most 1 MiB of JSON.
Each capability is a standalone WebAgent Source with its own goal/guidance, JSON Schema inputs,
local variables and steps. Sources require an explicit website scope and must pass the existing
compiler. A source cannot itself contain another `capabilities` array. Installation and trusted
development source loading run the same validator. Invocation validates again against the currently
mounted Package, and validates user parameters before creating a task. Scope enforcement remains in
the shared background executor; UI input cannot grant additional websites.

Choose explicit domains for packages intended for specific websites. Package capabilities are
programs declared by their publisher, not names selected from arbitrary frontend-supplied Source.
Compiled steps run first; the host adds bounded read-only list recovery as described below.
Interpreted or AI steps retain the existing WebAgent semantics.

## Client SDK

Copy `ai2apps/web/static/js/web_agent_mini_app_sdk.js` into the Package's indexed resources and load
it from the sandbox UI. This portable SDK uses the existing `ai2apps:studio-connect` handshake,
verifies the parent window, and communicates over the host-provided private MessageChannel.
It connects after iframe loading so navigation can revoke the old channel safely.

```js
const unsubscribe = AI2AppsWebAgent.onTask(task => {
  renderStatus(task.status, task.message);
  if (task.result) renderResult(task.result);
});
const task = await AI2AppsWebAgent.submit('article', {url}, {profile: 'default'});
// Submit returns the queued task immediately; completion arrives through onTask.
const current = await AI2AppsWebAgent.task(task.id);
await AI2AppsWebAgent.watch(savedTaskId); // resume updates for a task from this Mini-App
```

- `probe()` returns declared capability IDs, titles, descriptions and input schemas.
- `submit(capability, parameters, {profile, requestId})` submits one capability. A generated UUID is
  the default request ID; retain it to retry the same submission after an uncertain HTTP outcome.
- `task(id)` reads the durable status and available run result.
- `watch(id)` reads status and subscribes to further updates for that task.
- `onTask(listener)` returns an unsubscribe function. Delivery is a status view, not a unique command;
  render by task ID and tolerate reconnect snapshots.

The profile key selects an existing Profile owned by the current actor. The SDK does not expose
cookies, debugging endpoints, bearer credentials, browser connections or arbitrary HTTP calls.
The host authenticates every operation and checks the live mount/provider digest. Reading another
Mini-App's task is rejected even when it belongs to the same account.

## Shared execution and status ownership

All submissions go through `WebAgentInvocation` → `BrowserTaskRepository` → the existing Local
background worker and native BiDi execution. This is the common AI2Apps WebAgent invocation contract,
also used by AI Browser and Intelligence Center. The signed Source is compiled and its IR pinned in
the queued task, so later Package edits cannot change an already queued program. Global/Profile
concurrency, execution modes, browser page ownership, assistance, cancellation and cleanup use the
existing Task system. The Mini-App must not run steps or poll browser state in its iframe.

The host opens the existing authenticated Browser Workspace SSE stream and fetches only watched
scoped tasks on state-change events or reconnect. Concurrent notifications coalesce while retaining
an update arriving during a status read. There is no interval polling. The host and SDK use HTTP for
commands and SSE for changes; the Package never receives the workspace event stream itself.

Tasks appear in AI Browser's shared task column. Users open that task for assistance or cancellation.
Switching tabs hides and preserves the fixed UI. Closing/navigating/uninstalling the UI revokes its
channel and event subscription but does not cancel the durable background task. On Package refresh,
removed or digest-changed providers lose stale frames; the new mount must match the current digest.
Reopen and `watch` to resume status for tasks belonging to the same provider AppInstance/Mini-App.

## Example and validation

`packages/ai2apps-web-reader/` is a development source Package with a single fixed UI and two
capabilities: extract SJX links and read an SJX article. Both declare only
`https://watchesbysjx.com/**`. It uses compiled read/extract steps and the common queue.
The example is source-mounted in the fixed App-Dev environment; it is not a published signed release.
Installable releases use the existing signed App Package builders and Discover installation workflow,
following the Package publication runbook. No Cloud API or registry schema change is required.

Tests cover invalid declarations, independent input schemas, queue idempotency, task isolation,
SDK parent validation, SSE update coalescing and iframe preservation/removal. Existing Studio mount
and Browser Workspace tests remain acceptance gates. Signed installation and real browser execution
are separate release/runtime acceptance checks and must not be inferred from source tests.

Request IDs are idempotent within the mounted provider and Package digest. Reusing an ID with a different capability, Profile or input is rejected instead of silently returning the earlier task.

Development runtime acceptance: the Web Reader list capability completed against SJX in App-Dev through the shared queue, returned article titles and links, delivered completion through SSE, and verified task-page cleanup. The article capability is source/API-tested but has not yet had a separate live runtime acceptance.

## Model routing profiles

`web_agent.model_profile` selects `normal` (legacy default) or `privacy`; each capability may declare its own `model_profile`. Shopping and email Mini-Apps must declare `privacy`. The server retains selection in the shared Task and resolves routes into the AgentRun; the frame cannot override it. Privacy does not inherit Normal/Cloud-default routes and fails explicitly when an AI tier is missing. Users may configure trusted local, private-service or cloud models. See `ai2apps/docs/model-routing-profiles.md` for the common configuration and compatibility contract.

## Multi-source search example

`packages/ai2apps-search-all` hosts 一搜到底: each selected source submits an independent compiled shared Task through the existing SDK. Merging and provenance are presentation logic, not another browser engine. See `ai2apps/docs/search-all-mini-app.md` for scopes, deduplication, partial results and verification limits.

Profile selection: the portable SDK exposes `AI2AppsWebAgent.profiles()`. The authenticated host revalidates the live mount and returns only the current actor’s Profile key/name/default flag through MessageChannel. Mini-Apps should show a select menu and pass the selected key when submitting Tasks; no browser credentials are exposed.


## Required resilience to webpage changes

Every Web Mini-App must tolerate ordinary DOM/presentation changes: use semantic anchors and
observable content rather than only brittle CSS selectors; use bounded loading waits and native
Readability fallbacks. For extraction, validate actual observed URLs and required fields. A source
must never return fabricated URLs, article text, engagement counts or a false success when its
reader no longer matches the page. Display partial metadata and actionable source failures.

The shared Mini-App Broker adds `mini_app_list_recovery` to `extract_list` steps in a copied,
Task-pinned Source; signed Package declarations are not rewritten. All current and newly submitted
Mini-App list capabilities receive this policy, including Search All's independent sources. Existing
queued tasks keep their original pinned program. Normally compiled extraction runs without AI.
Only `site_rule_drift`, `search_markup_unavailable` and `search_page_not_loaded` failures enter the
fallback: the native BiDi SDK reads at most 100 visible link candidates; one model invocation with a
45-second deadline selects candidate IDs. The executor accepts only unique observed IDs, keeps
observed order, caps results to the requested limit (maximum 50), and copies original title, text,
URL and image fields. Social/video sources additionally enforce canonical content-link shapes.
Recovery does not generate scripts/selectors or navigate, click, input, upload or submit. It uses the
Task actor and normal/privacy model routing and records `observed_links_ai` recovery evidence.
Fallback metadata is marked `layout_recovery_partial`; absent metrics stay absent.

Authentication, CAPTCHA, payment/access restrictions, unavailable providers, wrong search pages,
and unverifiable requested sorting are not layout recovery opportunities. Do not silently relax
sorting or swap providers. Ask for existing user assistance or show a source failure. No configured
recovery model, invalid/empty selection or timeout remains a failure; it must not strand the queue.
Site scope and actor/Profile boundaries remain enforced. Native commands whose outcome is unknown
must never be replayed automatically, especially publishing, deletion, payment and uploads.

For UI steps that genuinely require adaptable interaction, publishers should declare existing
`execution: {mode: adaptive}` with explicit goal, scope and result evidence; review consequential
operations carefully. The shared adaptive engine has an eight-action ceiling and existing access/
confirmation checks. Read-page capabilities already use the shared Readability/rendered-DOM
fallback. No mechanism guarantees arbitrary site redesigns; regression-test modified markup,
unknown candidate IDs, login/CAPTCHA, provider failures, sort mismatch and ambiguous native errors.
Do not persist AI recovery as newly trusted compiled rules without a separate review.


## Search All owner-added sources

Search All's source list ends with an Add (+) dialog accepting a public HTTPS website URL. The
host validates the URL and builds a fixed `discover_source` Source scoped to that exact origin;
no frontend IR, selectors or scripts are accepted. Its shared background Task opens/inspects the
site using the selected browser Profile, then a standard-tier AI supplies name, description,
category and an observed search control reference. Saving validates the completed Task's actor,
Mini-App provenance, origin and actual control reference, rejecting invented/password controls.

Source configuration is stored in the local platform SQLite `custom_search_sources` table with
owner isolation, URL uniqueness and a 30-source limit. No browser localStorage or IndexedDB is
used. Listing/saving/deleting requires an authenticated Search All mount; client saving sends only
the analysis Task ID. New source queries use host-generated programs: compiled open, bounded
read-only adaptive search, then observed-link AI extraction. Exact user query is enforced on native
input and completion requires successful actual input; scope, sensitive input, CAPTCHA, login and
consequential-target restrictions still apply. The source's kind affects result cards; unavailable
metrics are never invented. Sources become candidates for Preferred mode and can be checked in
Custom mode. Fast API mode remains independent. Initial analysis identifies a visible entry,
not proof that every future query will work; failures must remain actionable to users.


Search All also accepts a website name or a fuzzy description (for example 豆瓣 or GitHub).
A standard-tier `resolve_source` Task contains only `ai.transform`, proposing up to three official
HTTPS sites with short reasons and an ambiguity/clarification question. It never navigates or
claims a search entry has been verified. The UI shows the actual proposed URLs; the user chooses
and confirms one, then the existing exact-origin discovery Task inspects its real controls before
SQLite persistence. An empty identification asks for more detail, not a fabricated source. Explicit
URLs retain the direct discovery path. Candidate lists are transient dialog state only; saved source
configuration remains exclusively in the owner-scoped local database.


## Startup readiness and retry

Mini-App HTML must initially expose a compact loading state and keep its interactive content hidden
and inert. Apply locale, mode-dependent visibility and event handlers, then await required host
connection/data (for example Profiles and owner-added sources) before revealing content. The iframe
load event alone does not imply application readiness. Never flash untranslated/default controls or
an empty Profile selector while initializing. On script failure, required-data error or bounded
startup timeout, retain the loading panel as an error with an explicit Retry action; do not reveal
partially initialized content. Ignore normal post-startup task errors in the startup gate.

Search All implements this in `web/startup.js` with a 45-second deadline and explicit completion
after custom sources and Profiles initialize. Its host startup operation shares one authenticated
mount/capability probe and fetches these independent read-only resources concurrently; endpoint
authorization remains in force. Historical retained-page verification runs after Ready and must not
block first paint. Starting a new search still awaits this verification before offering to close or
keep old pages; concurrent verification requests are coalesced. Retry posts
`{type:'ai2apps:mini-app-retry', version:1}` to the host. AI Browser accepts this only from the current
Mini-App frame's exact contentWindow and an allowed origin, then remounts that same catalog entry
with a fresh mount/channel. Do not replace this with iframe reload that bypasses or weakens existing
load-time channel revocation. Retrying UI initialization must not resubmit or cancel background
WebAgent Tasks. Loading animation respects reduced-motion preferences.

## Shopping Pro first-party Package

`packages/ai2apps-shopping-pro` supplies a fixed UI and six independent capabilities: history,
recommend, revise, search_products, prepare_cart and refresh_list. All run through the common durable background
Task/AgentRun mechanism; closing the frame does not stop browser actions. The signed declaration
selects Privacy for every capability, with no Normal fallback. Amazon.com actions always use natural
input timing, regardless of a domain's Fast preference. Read at most six order pages and pause on
login, verification, restrictions or unsupported structure. Do not solve verification automatically.

Order extraction retains product/date fields only, not shipping addresses or payment details.
Purchase intervals use observed, parseable purchase dates and do not imply consumption or inventory.
Sparse/unknown dates must remain uncertain. Recommendations and conversational edits reference
observed product IDs. A new product request can yield a search query; users select observed search
candidates before adding them to the list.

Cart preparation is a separately confirmed action. The broker resolves selected IDs exclusively from
completed history/search Tasks belonging to the same actor, Mini-App and browser Profile; the frame
cannot supply arbitrary URLs or action programs. One journaled step per product first checks current
cart quantity, only tops up a deficit, and verifies after a native add-to-cart click. Unknown cart
structure, subscription purchase mode, unavailable quantity or an uncertain result must pause rather
than replay the click. Never remove existing items, checkout, order, pay or subscribe. Retain the cart
Task page so the user can review and order.

The UI saves drafts (catalog, selection, conversation and pending Task reference) through host
`draft.get`/`draft.set` into the platform database with actor/installation/App/Mini-App scope. Web Mini-App
drafts never migrate from or write to browser localStorage. Restoring UI watches the existing Task,
without resubmitting cart actions.

### Shopping product thumbnails

Shopping uses `productImages(taskIds)` on the authenticated host channel to load thumbnails
from completed history/search Tasks belonging to this actor and Mini-App. Frames never supply
arbitrary image URLs. The host only accepts fixed Amazon image CDN HTTPS paths, refuses
redirects, bounds parallelism (4), source bytes (2 MB), image pixels (16 million), batch size (50)
and batch timeout (20 seconds), and produces JPEG DataURLs up to 160×200. The UI loads these
after Ready and persists them in the local scoped draft. Package CSP remains unchanged; neither
order-page navigation nor an AI call is needed to repair existing lists.

### Replenishment history synchronization

Generating a new list uses a single durable `refresh_list` program: inspect current orders, merge
with the previous completed history/refresh Task snapshot, recompute frequency, run Privacy AI, and
bundle history plus plan. The broker authorizes the prior Task's actor, Mini-App, capability and
Profile; frames cannot inject historical products. Same-day distinct orders use opaque SHA-256
order/product keys when observed, never store raw order IDs; legacy date-only samples are merged
without double counting. Intervals remain median gaps between distinct dates. Unknown keys/dates
retain uncertainty. An empty latest page never deletes the saved history.

Stop after an entirely known dated page; continue up to the configured page bound otherwise. Reaching
the bound is reported as incomplete, never silently presented as a full sync. The result retains
`synced_at`, pages read, stop reason and all merged observed products. Local drafts persist the latest
snapshot reference, sync time, thumbnails and selection; old Tasks remain in the database.
Cart preparation, thumbnails and product opening accept grounded products in refresh snapshots.
Closing the UI never interrupts synchronization or AI generation, and reopening watches the same
Task without resubmission. Conversational edits do not need a separate history refresh.

## Shopping Pro gift recommendation reference

`gift_recommend` and `gift_revise` are standard-tier background Tasks, using Normal by default with optional Privacy. Their Sources plan up to three generic Amazon queries, read bounded observed cards, rank three to five suitable IDs, and verify IDs/prices/budget before returning `assigned.gift_report`. Do not place private recipient names or contact information into website queries; never read purchase history for this flow. Model-generated URLs, images and prices cannot establish product provenance. Budget changes require an explicit amount in the user revision. Known over-budget products are removed; unavailable prices remain unverified. Use locale for all generated reasons, interface labels and task titles.

Gift and replenishment state remain separate fields in the host-owned local database draft, never browser storage. Persist pending Task IDs and conversation so remounting resumes instead of resubmitting. `gift_prepare_cart` accepts only products observed by completed gift Tasks belonging to the same actor, Mini-App and browser profile. It runs only after a local confirmation that shows image, observed unit price, quantity, subtotal and estimated total. Checkout remains user-owned. Permanent Shopping Pro data deletion includes gift drafts, input fields, conversation and Task content; stale drafts referencing deleted gift Tasks cannot restore those records.

Gift recommendations default to the Normal model profile. Users may opt into Privacy models for recommendation, revision, and cart preparation. Replenishment remains Privacy-only. The selected profile is passed through the shared background Task system; Privacy never falls back to Normal.

Search sort readers must exclude hidden/inert/aria-hidden or effectively transparent nodes through their ancestor chain before selecting controls or interpreting selected state. Duplicate hidden markup may retain stale classes. Validate only the actual visible sort control; a matching label or a successful click alone does not establish sorting.

Mini-App WebAgents must use the shared `ai2appsDOMVisible` BiDi SDK helper for result links, login/sort controls and observed input targets. Do not duplicate a site-specific bounding-box/CSS visibility predicate. All built-in search readers (Google, Bing, DuckDuckGo, Brave, Wikipedia, X, Weibo, Xiaohongshu, Bilibili and YouTube) exclude hidden duplicate results before URL deduplication, so hidden stale markup cannot displace the real result.

Web Mini-Apps consumed by Mobile AI Browser must fit a phone viewport, wrap forms/cards and keep dialog actions reachable. Their execution remains on the computer through shared background Tasks. Browser profile login or verification is completed on the computer; Mobile task detail exposes progress and continuation/confirmation. Host navigation must preserve mounted frames and drafts when returning to the library or task list. No self-built WebAgent editor or raw browser-control session is exposed in Mobile.

### Xiaohongshu / Rednote account-aware search

Search All inspects both public site home feeds using temporary BiDi tabs in the selected Profile. It never reads or copies cookies. Visible own-profile navigation proves login; visible login gates prove logged-out; missing evidence stays unknown. A confirmed preference is stored in `browser_search_site_preferences`, scoped by actor and Profile, and rechecked on each search. Both hosts must appear in the signed capability site_scope. Extractors preserve the actual observed host and token-bearing original links. Sorting remains optional and cannot discard otherwise readable results.

### Parallel Search All source Tasks

Search All gives each search a random batch_id and declared batch_size. The broker validates the signed Search All mount, derives an actor/provider-bound task root, and submits source Tasks via WebAgentInvocation with parallel_limit=3. BrowserTaskRepository remains the admission authority; shared Profile native input locks remain in force. Frontends cannot assign arbitrary parents or concurrency limits. Completion waits for source terminal states and the existing cleanup checks; root cancellation uses the common Task tree. Search sort/detail reads within one source remain sequential.

### Progressive search result delivery

Observed lists and per-item enrichment are stored in the Local database (`browser_search_progress`) with actor/Task ownership. They are exposed only after the usual signed mount/caller Task scope checks, never in public status event payloads. The normal authenticated task reader returns `result.partial=true` while processing; terminal run output takes precedence. Keep existing result card DOM when data is unchanged, show pending notes as reading rather than unavailable, and defer ranking-based folding until AI review ends. Partial results are evidence for display/opening only; summary source provenance still requires completed Tasks.
