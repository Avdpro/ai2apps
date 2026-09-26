# oMLX MoE Cache Experiment

This repository is the oMLX-based branch of the DMoE research project.

## Scope

- Preserve oMLX's existing model, attention, router, and fused MoE kernels.
- Add cache-aware routed-expert storage behind `DeepseekV4MoE`/`SwitchGLU`.
- Keep router indices on device on the all-hit path.
- Reuse DMoE trace/profile/offset artifacts by explicit file path; do not copy
  DMoE runtime modules into this repository.

## First performance gate

Implement a static oracle slot bank for DeepSeek V4 and compare it with the
unchanged full-resident oMLX path using identical prompts and generated tokens.
The prototype must demonstrate exact Top-10 parity, zero runtime misses, lower
resident memory, and retain at least 85% of the full-resident steady-state TPS
before dynamic cache replacement work begins.

## Branch discipline

- Experimental branch: `experiment/moe-cache`.
- Keep upstream-compatible changes isolated and small.
- Record benchmark commands, source commit, memory, cold TPS, and steady TPS.
- Never modify a sibling DMoE checkout from this repository.

## Notice:
- The current AI2Apps desktop client has bundle ID `com.ai2apps.desktop`.
- The desktop implementation lives under `apps/ai2apps-acefox`.
- The current development App must always use the stable path
  `apps/ai2apps-acefox/.build/AI2Apps-dev.app`. Do not create a new current App
  name for each feature or iteration. `scripts/build-dev-app.sh` archives the
  previous development App under `.build/archive/` before replacing this path.
  Release builds remain named `AI2Apps.app`.
- When using Computer Use, identify AI2Apps by its exact bundle ID or executable path, not only by display name.

## AI2Apps App-Shell development environment

- App-Shell Apps such as Chat, Terminal, Coder, Knowledge, and other Local
  HTML/Python Apps must use the permanent isolated development App at
  `apps/ai2apps-acefox/.build/AI2Apps-app-dev.app`. Its fixed display name is
  `AI2Apps-App-Dev`, bundle ID is `com.ai2apps.desktop.appdev`, and instance ID
  is `app-dev`. Do not rename, clone, or replace these identities per feature.
- Build or refresh this environment only through
  `apps/ai2apps-acefox/scripts/build-app-dev-environment.sh`. The script stages
  and verifies a complete replacement, archives the previous App under
  `apps/ai2apps-acefox/.build/archive/`, and preserves the long-lived
  `app-dev` instance data. Do not use `build-dev-app.sh` for this environment.
- Keep `AI2Apps-app-dev.app` independent from the general lower-level
  `AI2Apps-dev.app`/`dev` environment. Never copy or merge their Application
  Support, Cache, browser Profile, Cookie, database, log, Package, or model
  state. Both environments are expected to run concurrently.
- The App Dev bundle embeds a `cloud` Runtime, `omlx`, Python dependencies,
  Swift Helper/Launcher/Updater, and AceFox snapshot. It hot-mounts only the
  current repository's `ai2apps/` source through the explicit trusted
  Development Bundle contract; it must not inherit arbitrary source paths or
  use the repository `.venv` as its runtime.
- The App Dev builder must overlay the current matching AceFox
  `browser/components/ai2apps/content/shell.mjs` into the packaged browser
  `omni.ja`. This keeps the App Dev Shell aligned with the general Dev App's
  Local-aware native window title while using `AI2Apps-App-Dev` as its prefix.
  This source overlay is Development-only and must never be enabled for a
  production build. After rebuilding, verify the live native title has the
  form `AI2Apps-App-Dev: <device name> 127.0.0.1:<port>`; plist-only name checks
  are insufficient because an outdated packaged `shell.mjs` falls back to the
  embedded page title.
- Use the smallest feedback loop that matches the change:
  - For `ai2apps/web/templates/`, `ai2apps/web/static/`, ordinary HTML, CSS,
    JavaScript, and directly loaded localization content, refresh the Shell
    page; force-refresh only when browser caching masks a static change.
  - For Python API, Service, App registration, or other imported `ai2apps/`
    modules, restart the `app-dev` Local process from its Helper menu; do not
    rebuild the App merely for these changes.
  - Rebuild `AI2Apps-app-dev.app` after changes to `omlx/`, Runtime layers or
    Python dependencies, Swift Helper/Launcher/Updater code, AceFox, embedded
    entrypoints or manifests, bundle metadata, signing/entitlements, or App
    development icons. Also rebuild whenever a new lower-level snapshot is
    intentionally adopted by the App-Shell environment.
- Before replacing the fixed App, quit only the exact `app-dev` Helper, Shell,
  and Local processes; do not terminate other AI2Apps instances. After a
  rebuild, launch the fixed path and verify the bundle identifier, instance ID,
  Development flag, embedded Runtime profile, disabled production update URL,
  source-root contract, `verify-release-app.sh`, and
  `codesign --verify --deep --strict`.
- The App Dev Helper uses the standard four-state menu bar icon with one orange
  circle in its upper-left corner, and its App/Shell icon uses the pale-purple
  upper sphere. Test uses two purple diamonds in the upper corners and a
  light-blue upper sphere. Production, `main`, and `AI2Apps-dev.app` icons must
  remain unchanged. These are fixed identity contracts, not optional build
  decoration: always use `build-app-dev-environment.sh` or `build-test-app.sh`
  for those identities. `build-release-app.sh` must centrally derive and verify
  the corresponding App, embedded Shell, and all four Helper-state icons; do
  not bypass, duplicate, or weaken those checks in another build path.
- `docs/ai2apps-app-dev-environment.md` is the detailed workflow reference. The
  App Dev bundle is never a releasable artifact; production Desktop work still
  follows `docs/ai2apps-desktop-release-runbook.md` and the release ledger.

## AI2Apps Cloud change boundary

- When work involves changes to AI2Apps backend Cloud APIs or any related
  Cloud-side behavior, do not modify Cloud-side code directly from this
  repository.
- Instead, write a change-requirements document describing the required Cloud
  changes and give it to the user. The user will hand it off to the Cloud
  development project for implementation, deployment, and upgrade.

## AI2Apps browser control

- `docs/ai2apps-browser-control-architecture.md` is authoritative for all
  AceFox, Chat Sidebar, Knowledge webpage import, and WebAgent browser work.
- WebDriver BiDi is the single browser-control protocol. Main App and trusted
  Mini-Entries must receive the complete protocol through an authenticated,
  protocol-transparent Gateway; do not duplicate the BiDi method catalog as a
  semantic REST, WebSocket, Python, or JavaScript browser API.
- Shared Readability, page-stability, cookie-consent, screenshot, and input
  helpers must be implemented as client SDK helpers on top of native BiDi.
- Do not add JSWindowActor messages for DOM extraction, screenshots, or browser
  interaction. Firefox UI code may only bootstrap the protected BiDi session,
  enforce trust, and bind a Sidebar mount to an explicit active BiDi browsing
  context.
- Never expose AceFox's raw debugging endpoint or bearer credential to Local
  HTML. Use actor-, Profile-, App-, and mount-bound Gateway sessions.

## Apple release credentials

- When asking the user to create the AI2Apps `notarytool` Keychain profile,
  prefill the known non-secret account fields and prompt only for the
  app-specific password:
  `xcrun notarytool store-credentials ai2apps-notary --apple-id avdpro@me.com --team-id 84XL5V265N`.
- Never put an app-specific password, App Store Connect private key contents,
  or another Apple secret directly on the command line or in chat. Let
  `notarytool` collect the password through its secure interactive prompt, or
  use an already configured Keychain profile.

## AI2Apps Package publication

- `docs/ai2apps-package-publication-runbook.md` is the authoritative release
  procedure. Read it completely before building or publishing any Package.
- Agent-driven production publication must use the existing signed-artifact
  builders and `scripts/publish_signed_registry_artifact.py`; do not improvise
  with browser automation, ad-hoc `curl`, direct Cloud database writes, or a
  second publication implementation. Discover may be used to inspect and
  verify the published result.
- Use only the runbook's fixed entry points:
  `scripts/build_signed_registry_release.py`,
  `scripts/build_omlx_runtime_dmg.py`,
  `scripts/build_omlx_runtime_package.py`, and
  `scripts/publish_signed_registry_artifact.py`.
- Use the existing Publisher and registered Publisher key from the confirmed
  release context. Never create or switch to another Publisher, key, Package
  ID, or version merely to work around a publication failure.
- When the Publish page requests administrator verification, open
  **Account → Security → Administrator verification**, then hand control to the
  user so they can enter the administrator password and select
  **Verify administrator**. Never ask for, read, type, or store that password.
- Prefer the Installation Cloud session. If publication requires the current
  administrator browser session, do not read browser cookies, browser profiles,
  session databases, or Cloud tokens until the user explicitly authorizes
  Cookie access for the exact Package and version being published. That grant
  expires when the named publication finishes and does not carry to another
  task. Pass only the exact current profile's `cookies.sqlite` path to the
  standard script; never copy, export, print, probe, or try multiple Cookie
  databases.
- If a submission was created before a later step failed, query it and resume
  with `--submission-id`; never blindly submit the same release again.
- For dependent releases, publish the Runtime first and verify its published
  status before publishing model Packages that require that Runtime.

## AI2Apps Desktop publication

- `docs/ai2apps-desktop-release-runbook.md` is the authoritative end-to-end
  procedure for building, Developer ID signing, notarizing, publishing, and
  rolling out the macOS Desktop App. Read it completely before every Desktop
  release; it is distinct from the Package publication runbook above.
- `docs/ai2apps-desktop-next-release.md` is the authoritative rolling ledger for
  work completed after the current production Build. Update it in the same turn
  as every change that must be evaluated for a future Desktop Release. Before
  building, reconcile every open ledger item with the candidate scope; after
  end-to-end publication, archive included items into the immutable Build
  receipt and advance the ledger baseline. Never infer the next Release scope
  only from a dirty worktree or commit diff.
- Ledger maintenance is automatic and does not require a user reminder. Whenever
  an agent creates, modifies, fixes, removes, or materially reconfigures content
  that can change the shipped AI2Apps Desktop App, its embedded components, or
  its release/installation/update behavior, the agent must create or update the
  corresponding ledger item before ending that turn. Pure investigation with
  no releasable change need not create an item; once implementation begins, the
  item is mandatory even if the work remains `in_progress` or `blocked`.
- Use the checked-in App/DMG/metadata/manifest scripts. Publish GitHub assets to
  `Avdpro/ai2apps` with an immutable Release tag and publish the identical
  artifacts to `ai2apps/desktop-releases` through `modelscope_hub.HubApi` with
  cached credentials. Do not substitute browser upload, git-lfs, mutable
  revisions, or token-bearing URLs.
- Preserve the fixed `com.ai2apps.desktop`, `default`, `arm64`, Developer ID,
  `RUNTIME_PROFILE=cloud`, and `SANDBOX_MODE=0` contracts unless the user has
  explicitly approved a product-level migration. Never remove the compact
  Cloud Runtime merely to reduce the DMG size.
- Do not edit production `stable.json` or Cloud storage directly. Hand the
  dual-source manifest and verified local artifacts to the protected Cloud
  release workflow for schema/full-download/Range/SHA-256/notarization
  preflight, audited zero-percent publication, rollout, and production probes.
- A Desktop publication is incomplete until both immutable origins are
  verified, the Cloud endpoint passes production acceptance, and an eligible
  Mac completes an end-to-end upgrade. Record a release receipt, and never
  expose Apple, GitHub, ModelScope, Cookie, or redirect-signature secrets.


## Voice Studio shared output contract

All Voice Studio Mini-Apps, including Package-hosted frames, MUST use the one host-owned
Preview & Output based on Quick Read. Never introduce per-Mini-App output history, playback,
download or drag logic, or condition the right panel on the active Mini-App. See the mandatory
"Voice Studio output ownership" section in `docs/ai2apps-studio-mini-app-package-contract-v1.md`.
Run the shared output contract and cross-Mini-App selection tests when adding an output producer.
Keep private Line audio caches and reference materials outside output retention/deletion.
