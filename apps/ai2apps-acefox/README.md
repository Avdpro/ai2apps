# AI2Apps AceFox Client

This directory owns the AI2Apps macOS product layer built around the AceFox
browser runtime. Gecko-specific changes remain in the AceFox repository.

The current implementation slice contains the versioned instance, Local
configuration, runtime, run-descriptor, and bootstrap contracts. It also
contains a process supervisor that validates fixed-port conflicts, launches a
supervised Local runtime, rejects stale or cross-instance descriptors, verifies
the Local bootstrap identity, and stops only the child process it owns.
The browser-agent launch contract derives an opaque, stable profile ID from
both instance and authenticated actor IDs, and places Agent profiles outside
the app-shell profile tree. Each running Agent receives a random loopback
WebDriver BiDi port and a 256-bit bearer credential. AceFox rejects WebSocket
upgrades without that credential; the Shell process never enables Remote
Agent.

The app shell establishes a five-minute, instance-and-boot-bound desktop
session using the Helper's 256-bit credential before it loads Local HTML.
AceFox writes the returned HttpOnly cookie through its privileged cookie
service because system-principal bootstrap requests do not share a content
browser cookie jar. Local HTML receives a CSP and browser-security header
baseline, while the shell navigation guard remains locked to the exact dynamic
loopback origin.

## Validate the contracts

```bash
swift test
swift run ai2apps-contract validate-instance contracts/examples/instance-manifest.json
swift run ai2apps-contract validate-config contracts/examples/local-config.json
```

For development, launch the menu-bar Helper with an explicit Local executable:

```bash
swift run ai2apps-helper --instance default --runtime /absolute/path/to/omlx
```

The Helper shows both configured and currently bound ports. Quitting the Helper
does not stop Local. A relaunched Helper validates the instance ID, boot ID,
process ID, and bootstrap endpoint before adopting that process. **彻底退出
Local** revalidates the process immediately before stopping it.
Packaged launchers also give the persistent Helper their absolute App bundle
path. The tray's **打开 AI2Apps** action can therefore restore a closed Shell
while retaining the same Helper, Local process, boot identity, and port.
On macOS 13 and later, an installed writable App registers an instance-specific
`SMAppService` LaunchAgent for the nested Helper. The Helper can bootstrap
itself without command-line paths by deriving the signed main App, instance ID,
embedded Runtime, and AceFox executable from its own bundle location. Packaged
path overrides are rejected. The exact login-item state is published as an
owner-only `run/login-item.json` and shown read-only in the tray. A launch from
a read-only DMG deliberately records `skipped_read_only` and never registers a
service from the transient mounted path.
If a configured fixed port is already occupied, startup fails closed with the
stable `port_conflict` status and identifies the configured port; the Helper
does not terminate or replace the listener. Different instances can run in
parallel on distinct fixed ports.
Model checkpoints, Hugging Face downloads, tokens, databases, settings,
browser state, and inference/KV caches are all private to the instance
directory tree. The Helper removes inherited HF token/cache variables and forces
`HF_HOME`, `HF_TOKEN_PATH`, `HF_HUB_CACHE`, and the AI2Apps model root into the
instance container before Local starts. Sibling installations obtain model
capability through Local's authenticated Sharing/Upstream API; they never gain
filesystem access to the model host's checkpoint directory. An installation
that requires a private model downloads and prepares its own copy.

The first runnable release deliberately does not enable the macOS App Sandbox.
It keeps Firefox's own content-process sandbox and adds Developer ID signing,
Hardened Runtime, strict nested-code Team ID verification, an immutable Runtime
manifest, package-content inspection, owner-only instance directories, and
authenticated loopback control planes. This avoids imposing App Sandbox limits
on Local Python/MLX, model preparation, tools, and external project access.
macOS App Sandbox remains a later hardening option; until then, sibling Apps
under the same macOS login are logically and cryptographically isolated, not
filesystem-isolated from a malicious same-user process.
While Local is ready, the Helper checks its authenticated bootstrap identity
every five seconds. Three consecutive failures trigger an automatic restart
when `auto_restart` is enabled. An adopted process is never terminated unless
its identity can be revalidated immediately before the signal is sent.
Local stdout/stderr is appended to each instance's `logs/local.log` with
owner-only permissions. The Helper can open that log folder and copy the
currently verified loopback address.
The Helper can also export a `0600` diagnostic JSON into the instance's private
`diagnostics` directory. Its fixed schema contains operational metadata only;
it deliberately excludes log contents, prompts, credentials, cookies,
authorization headers, actor identifiers, and user files.

The launcher is the future `AI2Apps.app` main executable. In a packaged build
it resolves all components inside the app bundle. A development run can point
at loose artifacts:

```bash
AI2APPS_HELPER_EXECUTABLE="$PWD/.build/debug/ai2apps-helper" \
AI2APPS_LOCAL_EXECUTABLE=/absolute/path/to/omlx \
AI2APPS_ACEFOX_EXECUTABLE=/absolute/path/to/Acefox.app/Contents/MacOS/firefox \
swift run ai2apps-launcher --instance default
```

The launcher starts a per-instance, single-copy Helper and then replaces itself
with AceFox using that instance's dedicated app-shell profile. Immediately
before `exec`, it atomically publishes the owner-only `run/shell.json`. Update
installation accepts that PID only when the descriptor's instance, App path,
expected AceFox executable, and live process executable path all match.

During startup the Helper atomically publishes a versioned, owner-only
`run/helper.json` with its current phase, user-safe message, actual port, and a
stable error code when applicable. The AceFox Loading view consumes this state.
On failure it exposes retry and an instance-scoped “Open Logs Folder” action;
raw exception text and credentials are never placed in the status contract.

## Build a development app bundle

The development packager reuses a built AceFox bundle and copies an existing
Local entrypoint. It dereferences objdir links before signing and refuses to
overwrite an existing output:

```bash
ACEFOX_APP=/absolute/path/to/Acefox.app \
LOCAL_EXECUTABLE=/absolute/path/to/omlx \
INSTANCE_ID=my-dev-instance \
scripts/build-dev-app.sh
```

The default output is `.build/AI2Apps.app`. The copied development entrypoint
still references its source Python environment through its shebang. Production
packaging will replace it with a signed, manifest-verified embedded runtime.
Every packaged App must carry a globally distinct `AI2AppsInstanceID`; this is
the default identity used for data, Helper Socket, Local, and browser Profiles.

The Helper control response contains an internal `automation` contract for the
Local Browser Service. It is validated as an authenticated
`ws://127.0.0.1:<port>/session` endpoint and is intentionally omitted from the
public browser-launch API response. A repeated request for the same actor
focuses the existing process and returns the same protected BiDi session.
The Helper removes an Agent from its live process table as soon as that process
exits, so a later request can safely launch a replacement with the same stable
profile identity. A normal Helper exit terminates all Agent processes that it
manages, while deliberately leaving Local running. Agent launch, focus, exit,
and Helper-driven termination events are appended to the instance-scoped
`logs/browser-agent-audit.jsonl` file with mode `0600`; audit records contain
only the opaque profile hash, process ID, action, outcome, and timestamp—not
the actor ID, bearer credential, or authorization header.
Local closes an Agent through the authenticated, idempotent `browser.release`
operation. The release response never returns the BiDi endpoint or bearer
credential. A successful request removes the Agent from the Helper's live table
before requesting termination; a repeated release returns `not_running`.

The supported multi-instance deployment is a model-host topology. One chosen
instance owns model files and exports only selected model IDs through scoped,
revocable bearer grants. Other instances register it as an Upstream, project
its models into their own model list, and proxy inference over loopback or the
explicitly enabled LAN data plane. Prompts cross into the trusted model host,
but accounts, databases, Agents, browser Profiles, credentials, and all other
instance state remain isolated. A future version may add a read-only external
checkpoint provider with pinned-revision integrity checks; mutable shared HF
caches and writable checkpoint links are outside the current product boundary.

## Build a release bundle

First export the venvstacks Runtime layers with `packaging/build.py`. Then build
the App with those layers and a current AceFox bundle:

```bash
ACEFOX_APP=/absolute/path/to/Acefox.app \
RUNTIME_LAYERS=/absolute/path/to/packaging/_export \
INSTANCE_ID=my-release-instance \
BUILD_NUMBER=2193 \
scripts/build-release-app.sh
```

The default `RUNTIME_PROFILE=full` preserves the legacy self-contained MLX
bundle. Build the independent Cloud Base App with:

```bash
ACEFOX_APP=/absolute/path/to/Acefox.app \
RUNTIME_LAYERS=/absolute/path/to/packaging/_export \
RUNTIME_PROFILE=cloud \
INSTANCE_ID=my-cloud-base-instance \
BUILD_NUMBER=2228 \
scripts/build-release-app.sh
```

The cloud profile embeds `framework-control-plane`, sets the signed App and
Runtime manifest profile to `cloud`, and excludes MLX, inference engines,
custom kernels, calibration data, and model evaluation assets. It remains a
complete AI2Apps control plane, but local model execution requires a separately
installed, verified Runtime Package. `verify-release-app.sh` rejects a cloud
bundle if the MLX framework layer or top-level MLX packages are present.

`ACEFOX_APP` must be a Gecko packaging output (for example the `Acefox.app`
inside the `mach package` DMG), not the objdir development bundle; both Gecko
`omni.ja` archives are mandatory. The release packager embeds CPython, the
framework layer selected by the runtime profile, and the current
`ai2apps`/`omlx` product sources. It creates and validates a hashed Runtime
manifest, removes unusable exported symlinks and wrong-CPython-ABI extensions,
signs the complete bundle, and runs strict deep verification. It refuses to
overwrite an existing output. Set `SIGN_IDENTITY` for Developer ID builds; the
default ad-hoc identity is intended only for local smoke testing. The checked-in
entitlement set signs JIT permissions onto `acefox-bin` rather than the Swift
launcher, matching Firefox's main-process requirement.
`BUILD_NUMBER` may be set to a positive integer for candidates built from an
uncommitted tree; otherwise it defaults to the Git revision count. Production
build numbers must be monotonically increasing.

`verify-release-app.sh` is also run by both release packagers. Besides strict
signature and broken-link checks, it rejects Gecko's mutable `.purgecaches`,
objdir `moz.build`, packaged Python bytecode, and extensions for a CPython ABI
other than 3.11. For Developer ID builds it also verifies the browser JIT and
library-validation entitlements, probes the embedded Runtime, and verifies that
the probe did not alter the signed bundle.

Create a verified compressed DMG from the finished App:

```bash
APP=/absolute/path/to/AI2Apps.app \
OUTPUT_DMG=/absolute/path/to/AI2Apps.dmg \
scripts/build-release-dmg.sh
```

For distribution, pass the same Developer ID identity as `SIGN_IDENTITY` when
building the App and DMG. After storing notarization credentials with Apple's
`notarytool store-credentials`, first run the offline preflight against the
immutable internal candidate:

```bash
APP=/absolute/path/to/AI2Apps.app \
DMG=/absolute/path/to/AI2Apps-internal.dmg \
METADATA=/absolute/path/to/AI2Apps-internal.release.json \
scripts/preflight-notarization.sh
```

Then submit a temporary copy, staple it, publish it under a new filename, and
generate/verify its final release record without placing secrets on the command
line:

```bash
ARTIFACT=/absolute/path/to/AI2Apps-internal.dmg \
APP=/absolute/path/to/AI2Apps.app \
SOURCE_METADATA=/absolute/path/to/AI2Apps-internal.release.json \
OUTPUT_DMG=/absolute/path/to/AI2Apps-final.dmg \
OUTPUT_METADATA=/absolute/path/to/AI2Apps-final.release.json \
KEYCHAIN_PROFILE=ai2apps-notary \
scripts/notarize-release.sh
```

The source DMG is never modified. The script refuses an in-place output, an
existing destination, an already-stapled source, stale source metadata, and any
post-notary result that fails Stapler, Gatekeeper, signature, checksum, Runtime,
or final metadata verification. `verify-notarized-release.sh` can rerun the same
post-notary gate independently.

Generate the public, machine-readable release record after the final signing
and notarization/staple step (or before notarization when recording an internal
candidate):

```bash
scripts/generate-release-metadata.py \
  --app /absolute/path/to/AI2Apps.app \
  --dmg /absolute/path/to/AI2Apps.dmg \
  --output /absolute/path/to/AI2Apps.release.json
```

The generator first performs strict App and DMG signature verification, checks
that the bundle identity agrees with the signing identity and embedded Runtime
manifest, and mounts the DMG read-only to prove its single `AI2Apps.app` has the
same CDHash, signing team, bundle/version/instance identity, minimum macOS
version, and Runtime manifest as the supplied source App. It then records
versions, architecture, minimum macOS version,
CDHash, signing team, Hardened Runtime, notarization status, artifact sizes, and
SHA-256 digests. The output intentionally contains no credentials or user data,
is written atomically as a public `0644` artifact, and is never overwritten.

Independently verify the record and both published artifacts:

```bash
scripts/verify-release-metadata.py \
  --metadata /absolute/path/to/AI2Apps.release.json \
  --app /absolute/path/to/AI2Apps.app \
  --dmg /absolute/path/to/AI2Apps.dmg
```

The verifier reruns signature, identity, Runtime manifest, size, digest, and
notarization inspection—including the DMG/App pairing—and requires an exact schema match except for the record
creation timestamp. A one-character forged DMG digest is rejected at the exact
mismatched field.

Before an updater is allowed to stage a replacement, verify the complete
candidate against the currently installed App:

```bash
scripts/verify-update-candidate.py \
  --installed-app /Applications/AI2Apps.app \
  --candidate-app /absolute/path/to/AI2Apps.app \
  --candidate-dmg /absolute/path/to/AI2Apps.dmg \
  --candidate-metadata /absolute/path/to/AI2Apps.release.json
```

The production gate requires an exact bundle identifier, instance ID,
Developer ID team and signature identifier match, a strictly increasing
positive `CFBundleVersion`, Hardened Runtime, a supported architecture, a
compatible minimum macOS version, and a valid `stapled` release record. It also
reruns the full App/DMG/metadata pairing verifier before making the update
decision. `--internal-candidate` is an explicit developer-only escape hatch
that accepts a correctly recorded `not_stapled` candidate; it does not relax
identity, version, signature, Runtime, architecture, or OS checks. This command
only decides eligibility and does not modify the installed App.

Update-capable bundles declare `AI2AppsUpdaterProtocol=1` and contain a
separately signed `Contents/Helpers/AI2AppsUpdater`. The updater must first be
copied outside the App it will replace. It waits for the exact Shell PID to
exit, copies the candidate to a unique sibling staging path, revalidates both
the installed and staged App, and then performs same-volume renames. A
per-directory exclusive lock prevents concurrent transactions. The previous
verified App remains at the explicit sibling backup path after success. The new
Launcher supports `--post-update-health-only`, which validates its nested
Helper identity and complete embedded Runtime without registering a login item,
starting Helper/Local, or opening UI. Failed signature, copy, replacement, or
health checks restore the previous App before returning failure. Existing
bundles that predate protocol 1 remain verifiable but cannot claim this update
capability. The exact installed-App sibling pending marker is passed to the
external Updater, which removes it on every terminal path. A Helper crash
therefore cannot leave the Launcher permanently blocked.

The Helper-side staging tool accepts only an immutable DMG and release record,
mounts the image read-only, requires one real top-level `AI2Apps.app`, and
copies it into a random owner-only directory using the exact artifact filename
bound by the release record. After unmounting, it reruns the complete update
eligibility verifier. The copy must retain the embedded App's CDHash and pass
strict deep verification before it is atomically published as the instance's
staged `AI2Apps.app`. Production staging rejects an explicit `not_stapled`
record before copying; `--internal-candidate` exists only for developer
acceptance. These resources are declared separately by
`AI2AppsUpdateStagingProtocol=1`, so earlier updater-capable bundles remain
verifiable.

Helper publishes only the bounded owner-only `run/update.json` contract. It
contains instance identity, phase, current/candidate Build Numbers, a safe
single-line message, a stable error code, and timestamp. Artifact paths,
signature output, credentials, and raw exceptions are never included.
The tray exposes **检查已下载更新** and **安装更新并退出 AI2Apps…** for
writable protocol-1 packages. Inputs live at fixed instance-private paths.
Staging runs embedded Python and every recursive verifier in isolated,
no-bytecode mode. Installation requires confirmation, closes only the verified
current Shell, and leaves Helper and Local running.

See `docs/ai2apps-acefox-client-definition-development-plan.md` for the product
definition and phased implementation plan.

### Latest verified Developer ID artifact

The first fully exercised local baseline was
`.build/artifacts/developer-id-v9/AI2Apps-developer-id-v9.app`, with its signed
compressed image and release record in the same directory. The versioned artifact contains a
stable `AI2Apps.app` product name. The DMG has passed CRC validation,
strict deep signing verification before and after first launch, a read-only
mounted launch to a ready Local backend, isolated-cache permission checks, and
Shell close/reopen reuse of the same Helper/Local process. v9 contains the
Helper's bounded safe-diagnostic export, no-argument packaged self-bootstrap,
and an instance-specific LaunchAgent, and uses unique build number `2198`;
its 37 Swift tests pass. It is built from packaged AceFox with both `omni.ja`
archives; a real process audit confirms content processes use
`-greomni/-appomni` and contain no development `-sbTestingReadPath` allowance.
An installed APFS-cloned copy was verified both registering and unregistering
the Helper through `SMAppService`; launchd reported the expected parent bundle,
nested Helper program, and `RunAtLoad` policy. v9 adds a checked tray toggle
backed by a signed `--update-login-item-only` Launcher path. Its real
`enabled` to `not_registered` transition left the existing Shell and Local PID,
boot ID, and port `53681` unchanged. A separate v9 read-only DMG launch recorded
`skipped_read_only`, reached Local Ready on dynamic port `54776`, and left no
LaunchAgent registered. The preceding v2 candidate also passed an Agent
launch/release lifecycle smoke test. v9 is
intentionally not described as generally distributable yet: Gatekeeper reports
`Unnotarized Developer ID` until Apple notarization and staple are completed.
Its release record pins DMG SHA-256
`637ad61bd1119231600008399bdbae338c4ca3b1d95d7b8125154b5a8090319d`
and reports `not_stapled`, so a subsequently notarized artifact must receive a
new release record rather than silently reusing this one.

An earlier same-identity update fixture lives under
`.build/artifacts/developer-id-v9-update1/` with build number `2199`. The real
update gate accepts it over v9 build `2198` only with the explicit internal
flag. It rejects the same build, a downgrade, a differently identified
instance, and the unstapled fixture on the production path. v9 build `2198`
remains a historical baseline; update1 exists to exercise update
and future rollback transactions.

The first complete protocol-1 candidate is
`.build/artifacts/developer-id-v10/AI2Apps-developer-id-v10.app`, build `2200`,
with matching DMG and release record in the same directory. Its embedded
Updater and no-UI Launcher health mode are Developer ID signed with Hardened
Runtime. The full 1.6 GB transaction was exercised against an isolated APFS
clone of v9: build `2198` became `2200`, health validation passed, the verified
`2198` backup remained available, and both resulting bundles passed strict deep
verification. A separate deliberately failing health fixture restored the old
App automatically. The v10 DMG pairing CDHash is
`ab0edc669de483bea92333dabaad3f08b311b4d8`; its DMG SHA-256 is
`570bc3fadb66616b7380c1ca349845032bb455068b70870a54be758c4780f8a5`.
It remains an internal `not_stapled` candidate and is not a public update.
The v10 DMG also passed the staging tool: build `2200` was published only after
read-only extraction, metadata filename preservation, full eligibility
verification, copy CDHash verification, and owner-only `0700` staging. All 43
Swift contract, supervisor, and update tests pass.

The historical pre-Sandbox local release candidate was
`.build/artifacts/developer-id-v17/AI2Apps-developer-id-v17.app`, build `2207`,
with its signed DMG and release record in the same directory. It contains the
complete Helper update menu, instance-scoped Shell process descriptor,
external Updater pending-marker recovery, immutable recursive Python staging,
and the then-experimental shared model-cache lifecycle, which has since been
retired in favor of private model storage plus authenticated model hosting.
Its 49 Swift tests pass, including a two-instance launch-plan matrix, the
versioned cache report contract, and exact Shell process identity checks across
instance, App path, executable path, and live PID. The focused
shared-cache/model-provider/delete Python suite has 39 passing tests, including
a real cross-process cache-gate case. The embedded cache CLI was also exercised
from the signed App with a minimal environment and returned a path-free
versioned report. A black-box v17 run then started two signed embedded Local
processes concurrently with isolated data/HF Home/token/run roots and one
shared model cache. Both became healthy on distinct automatic ports `56219`
and `56220`, and both terminated cleanly without reconciliation errors.
A second signed-runtime matrix had both instances concurrently reference the
same pinned snapshot. Collection protected it with both references and again
after only instance A released it; only after instance B also released did the
collector remove exactly one snapshot and its one now-orphaned blob.

A black-box staging run mounted the v17 DMG, copied and recursively verified
the candidate, then proved the source App still passed strict deep signing and
contained no `.pyc`. A full transaction upgraded v16 build `2206` to `2207`,
retained the verified `2206` backup, passed Launcher health validation, and
cleared the pending marker. The App CDHash is
`f27d8167d1237a687c65048019456237610f51fc`; the DMG SHA-256 is
`e2e672318380c902310ac0856818a386ebbf8d23e004ddff247bb946dcc666eb`.
The triplet passed offline notarization preflight but remains an internal
`not_stapled` candidate.

Development after v17 adds a Helper-enforced browser Agent lease. Automation
activity renews a 30-minute idle window, manual user control pauses expiry,
resuming automation starts a fresh window, and Session close still releases
the Agent immediately. Failed BiDi startup is now transactional and cannot
leave an unmanaged visible Agent behind. The freshly compiled Swift suite has
52 passing tests (including three lease state-machine tests); the focused
Python Agent/Helper/browser lifecycle suite has 29 passing tests.

`scripts/migrate-installed-model.py` is the explicit, dry-run-by-default
pre-release migration path. It accepts only an operator-supplied repo and
pinned 40-hex revision, rejects unsafe entries, materializes external file
links, prefers APFS clone-on-write, validates the copied inventory, and
publishes atomically. It does not import legacy settings or credentials. The
current DeepSeek-V4-Flash and Qwen3.8-27B-NVFP4 installations pass its real
read-only preflight; no bulk model copy has been started before the final model
host instance is selected.

During this gate, v11 and v13 were rejected after test execution revealed that
a nested embedded-Python verifier could create signed-bundle `__pycache__`
files. v14 and later propagate bytecode suppression through the complete
verifier process tree, and `smoke-immutable-staging.sh` retains this failure
mode as a release regression. v15 was a valid signed intermediate build, but a
post-build crash-safety review found that it marked a snapshot collectible
before publishing its protecting reference. v16 reverses that order and is the
first release candidate containing the corrected protocol; v15 is therefore
superseded and must not be distributed.
