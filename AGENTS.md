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
