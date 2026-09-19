# Full current-source release acceptance — 2026-09-11

Status: in progress; not a production publication receipt.

The user explicitly selected acceptance of all existing changes, rather than a
clean image-only subset. This does not waive tests, immutable source provenance,
notarization, Cloud release review, or actual upgrade acceptance.

## Candidates and publication order

- Production baseline remains Desktop 0.1.0 Build 2249.
- Build 2250 is an immutable internal-only candidate, not eligible for promotion.
- Fixed isolated Test App Build 2251 was rebuilt using the standard Test builder.
  Its signing/identity verifier passed. The existing Test instance data is preserved.
- Five ACPF translation keys were corrected after Test 2251 was built. A final
  candidate must be rebuilt from the accepted, committed clean source.
- First release a compatible Desktop. Then publish the four signed image Packages:
  Z-Image Turbo 0.1.3, Ideogram 4 0.1.2, Qwen Image 0.1.2, FLUX.2 Klein 0.1.4.
  Their exact version-specific installation metadata requires the new Desktop.
- No production Package submission or Desktop upload has been performed in this
  acceptance run. Independent model Packages are not silently bundled into Desktop.

## Packaging corrections

- Refreshed the packaged AceFox snapshot with `mach build faster` and `mach package`;
  the native dialog branding patch is now present in packaged PromptParent.
- Added LICENSE, LICENSE-POLICY.md, NOTICE, TRADEMARKS.md and the Cloud connector
  BSL notice under App `Contents/Resources/Licenses`; the release verifier checks
  all five files. No license terms were changed.
- Transient `:memory:.ses`, ignored caches and test-run artifacts must not enter
  the source commit or Desktop payload. User files are preserved.

## Tests

- Test Harness self-tests: 81 passed.
- Initial client suite: 1466 passed, 1 failed, 4 deselected. The failure identified
  missing ACPF locale entries; targeted locale and license verification then passed
  all 3 tests.
- Extended Runtime suite initially found 25 stale contract assertions. Updated
  tests verify the current account-based authentication boundary: retired web-key
  endpoints return 410 and cannot create sessions or mutate settings; statistics
  never expose the inference key. Also aligned model display names, Shell version
  context and Chat settings localization assertions. No product authentication
  behavior was changed to satisfy tests.
- Extended suite after corrections: 681 passed, 6 deselected in 19.01 seconds.
- Image Package and Demucs contract checks: 31 passed. An additional unchanged
  EchoMimic test module could not collect in the host venv because its independent
  `echomimic_mlx` dependency is absent; this is not reported as passed.
- A combined client/Runtime regression is running with JUnit output at
  `/private/tmp/ai2apps-full-release-regression.xml`.
- That combined run completed with 2103 passed, 1 failed, 6 deselected. The single
  failure was a three-step Agent durability test's 3-second terminal wait. An
  isolated diagnostic retaining all original assertions completed in 3.379 seconds.
  Only this test now uses a bounded 10-second wait; targeted recheck passed. Product
  scheduling and authentication were not modified. A full rerun writes a separate
  `/private/tmp/ai2apps-full-release-regression-final.xml`.
- Final combined rerun: **2104 passed, 6 deselected in 476.44 seconds**.
  Original and final JUnit evidence is archived under
  `apps/ai2apps-acefox/.build/releases/acceptance-20260911T0816/`.

## Actual UI evidence

- Run `20260911T071647Z-57326`: 46 passed, 30 blocked. Mac lock screen prevented
  native test login. These results are retained, not rewritten as successful.
- After the user unlocked the Mac, CUA selected exactly
  `com.ai2apps.desktop.test.shell` and confirmed a usable login form.
- Run `20260911T081651Z-64291`: standard Harness account login recovered; P0 UI
  queue is executing. Results and screenshots belong to this Run only.
- Development-only disabled entries and absent independently installed Packages
  must be distinguished from broken enabled Desktop functionality in final review;
  neither is automatically marked passed.
- At 68 recorded cases, 60 passed and 8 were blocked: Agents, Bench and Messager
  main Apps are explicitly in development; five Media Voice Studio Suite Mini-Apps
  are absent because the independent suite is not installed. Additional exact
  authorization to sign/rebuild suite 0.1.0 for Test-only acceptance was requested;
  this does not authorize its production publication or Cookie access.
- Final P0 result: 76 selected, 66 passed, 0 failed, 10 blocked, 0 pending.
  The five intentionally disabled main Apps are Agents, Bench, Messager,
  Environment and Sharing. The other five blockers are the uninstalled suite's
  Mini-Apps. The standard Harness released its test account lease. Report:
  `ai2apps-test-system/artifacts/runs/20260911T081651Z-64291/report.html`.

## Credential preflight

Read-only GitHub identity check returned Avdpro. The existing `ai2apps-notary`
profile successfully queried Apple notarization history. No secrets were exported;
no artifacts were uploaded or submitted for notarization during these checks.

## Remaining gates

Finish current UI review, real image inference and upgrade evidence; reconcile
every included release-ledger item; freeze and push clean source; rebuild, sign,
notarize and verify immutable Desktop artifacts; upload identical GitHub and
ModelScope origins; hand the verified manifest to the protected Cloud publication
workflow; validate an eligible Mac upgrade; then publish and verify the dependent
image Packages through the standard publisher. Production Cloud code and database
mutations are outside this repository's authority.

At turn end, the P0 queue and combined regression have both finished. The pending
user choice is Test-only signing/rebuilding of Media Voice Studio Suite 0.1.0 to
resolve its five missing-package UI cases (or explicitly narrow acceptance back
to Desktop and the four image Packages). No new signing-key usage, Package
submission, source commit/push, or production Desktop upload was performed.

## Suite Test-only authorization follow-up

The user approved signing/rebuilding suite 0.1.0 and installing it only in Test,
without Cookie access or production publication. The original suite receipt binds
Publisher key `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`, public fingerprint
`216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`.
It must not be replaced by the newer image-package key to work around a lookup issue.

A read-only exact-fingerprint query of App-Dev public signing metadata found no
matching record. Reading the standard dev publication context's record ID and
public fingerprint was rejected by the permission reviewer as outside Test-only
authority; that rejected read was not executed or bypassed. Additional explicit
read-only dev metadata authorization is required to locate the original key's
SecretBackend record and namespace. No Cookie, Token or private-key value was read.

Unaffected suite/Host/broker/workflow contract verification: 33 passed in 0.86 s.
The host sandbox emitted the known MLX no-Metal atexit notice; this test run did not
perform real inference. No new suite artifact was signed, installed or published.

The user subsequently authorized read-only dev metadata lookup. The exact-fingerprint
query returned no match, and a count-only check confirmed dev has zero records with
purpose `AI2Apps package signing`. No secret value or session data was accessed.
Read-only comparison found nine current payload files differ from the old signed
suite archive (README, app.yaml and seven web assets), so that archive cannot stand
in for current-source acceptance. Locating the same original key now requires
explicitly broader read-only signing-metadata scope, or its known record ID and
namespace supplied by the user; no alternative Publisher key has been selected.

After the user signed in and completed administrator verification in AI2Apps-dev,
CUA confirmed account avdpro@me.com and verification valid until 2026-09-11 20:35.
The live bootstrap at port 50944 reports instance dev, Installation
`local_a43644810f7b48bdcce578ca1db05416`; the authorized read-only dev database's
`local_security_identity` matches exactly. Its signing-record count remains zero
and the original suite key fingerprint has no match. This rules out an incorrect
Dev database selection: administrator step-up succeeded but does not restore the
separately stored Publisher signing-key reference. No Cookie or token was read,
and no signing or publication was attempted.

## Authorized signing recovery and current-session preflight

The user then authorized read-only signing-metadata lookup across local instances
and current Cookie use for this Package publication task. The exact suite public
fingerprint was found in `binding-fix-v2`; the original key was retained. The
standard builder produced a separate current-source Test candidate, without
overwriting the historical archive:

- Artifact: `packages/ai2apps-media-voice-studio-suite/dist/ai2apps-media-voice-studio-suite-0.1.0-test-acceptance-20260911.ai2app`
- SHA-256: `96d361461b6edc8002364026b4a1474dacc0888e91ac816e2f0f96fa74a4b7c6`
- Size: 29,742 bytes. Independent `verify_signed_package` verification passed
  with the exact original public fingerprint, including signature, archive digest,
  manifest digest and Package ID/version.

The Installation session returned `an active user session is required`. The
running Dev Shell process identifies exactly `dev/browser-profiles/app-shell`.
Passing only that profile's Cookie database to the standard publisher succeeded;
Cloud reports both original AI2Apps Publisher keys active with matching public
fingerprints. No Cookie or private-key value was printed or exported. Read-only
submission listing succeeded; no new submission or publication was attempted.

Test doctor and account doctor passed. A terminal-driver attempt produced no UI
acceptance and is preserved as blocked (`20260911T100325Z-72196`). The proper Codex
driver Run `20260911T100417Z-72245` selects exactly the five Suite Mini-App cases.
The Suite is still absent in Test and must not be reported installed or passed.

Code inspection identifies a local candidate-installation gap: the existing
`/interactive-packages/install` route invokes `InteractiveArchive.inspect`, which
requires legacy `signatures/publisher.sig` and `attestations/publisher.json` inside
the archive. The new standard candidate is Contract v1 with a detached envelope.
The Registry path adapts this format only after published-repository verification.
Do not manufacture a published Registry entry, substitute a different signed
format, or bypass audit to install the candidate. A supported Test-only signed
candidate import path is needed before these five current-source UI cases can
complete. This is distinct from the now-resolved signing/Cookie authorization.

The five-case Run completed: 0 passed, 0 failed, 5 blocked, 0 pending; the Harness
released the test account. The blocked result confirms missing installation, not
a demonstrated Mini-App runtime failure. Report:
`ai2apps-test-system/artifacts/runs/20260911T100417Z-72245/report.html`.

## Authorized Test candidate import implementation

The user explicitly approved adding a Test-only import path. It is implemented
in `ai2apps/packages/test_candidates.py`, exposed through the existing
system-manage-authorized Package router, and shown by Discover only when the
server confirms the fixed Test instance. It requires both Helper/test environment
identity and the exact, non-redirected Test data path. App-only candidates with
required Package dependencies are rejected rather than silently skipping them.

The Publisher key and namespace must be present in a currently trusted Registry
snapshot; revoked keys and non-published source releases are excluded. Bytes are
staged before verification and audit. Inspect never installs; installation binds
approval to the exact SHA-256 and reruns local audit. Records identify
`test-only-publisher-signed-candidate`, not a published Registry release. No
Registry installation or release row is fabricated.

Focused isolation/signature/audit tests plus Registry regression: **40 passed**.
Test 2252 built successfully, but a subsequent source-to-bundle hash check found
it predated the final revoked-key/symlink guards. Test 2253 is being rebuilt by the
standard builder; no signed bundle was patched in place. Real import/approval and
five Mini-App mount cases remain pending until the final bundle is running.

Test 2253 completed standard build verification and `codesign --verify --deep
--strict`; the embedded candidate-import module SHA matches source exactly.
Harness Run `20260911T101930Z-8823` logged in its Test account and remains in
manual takeover mode for explicit installation review. CUA confirmed BUILD 2253
and the new Discover panel on port 57541. Real candidate inspection succeeded
with the expected Package identity and SHA. The unconfigured local AI auditor
returned the normal static gate: `review`, `medium`, reason
`local_ai_auditor_not_configured`. The UI displays `Approve and install in Test`.
No approval click, installation, mount pass or production publication has occurred.
User action is now needed at the displayed audit approval; five cases remain
pending. Evidence is `candidate-review-evidence.txt` in this Run directory.

## Installed Test candidate: real mount failures

Following the user's installation confirmation, the signed candidate was installed
in Test 2253. All five entries were discovered in their Studio lists. Actual CUA
clicks opened their correct mount URLs, but every form remained blank in repeated
accessibility snapshots and screenshots. Run `20260911T101930Z-8823` finalized as
**0 passed, 5 failed, 0 blocked, 0 pending**; its test account is **released**.
Evidence and the final report remain in that Run directory. This supersedes the
pending-installation state above, not the historical results of earlier Runs.

Code inspection identifies a production-contract incompatibility: the suite loads
external authenticated resources, uses localStorage, and directly fetches local
capability endpoints. Installed sandbox entries have opaque origins and
`connect-src 'none'`; only Development source entries receive the same-origin
exception. The shared Studio integration currently accepts frame resize messages,
but has no corresponding execution transport for these suite operations. The
external-resource failure is a hypothesis for the initial blank screen, not a
captured browser-network finding. The direct-fetch incompatibility is independently
established by the CSP and source code; fixing rendering alone cannot establish
working production execution.

Do not add `allow-same-origin`, relax network CSP, fabricate a Registry release, or
mark discovery alone as a mount pass. Resolution requires a reviewed, mount-bound
Host transport, compatible verified-resource delivery, and draft persistence that
does not depend on opaque-frame localStorage. That is new platform implementation
beyond the approved Test-only candidate importer. No production publication,
source commit, or source push occurred during this continuation.

## Authorized production-sandbox adaptation (Test 2254)

The user approved implementing the missing Host transport. Added verified HTML
asset delivery in `ai2apps/extensions/sandbox_document.py`, invoked by the existing
authenticated resource route. It keeps production CSP unchanged, verifies every
relative script/style resource, preserves deferred script placement, and rejects
remote/traversal assets, closing-tag injection and oversized documents.

The shared Studio client now supplies a private MessageChannel only to the exact
frame registered by an authenticated mount response. It derives endpoints and draft
namespace from Host state, not Package messages. Each operation revalidates the
actor/mount; invocation retains server-side signed capability validation and accepts
only the five existing media operations. Navigation revokes the channel. The suite
now uses this transport for capability probing, multipart invocation and bounded
draft storage, without direct fetch or opaque-frame localStorage. Reset clears live
state without navigating away from the authenticated mount.

Related regression: **150 passed in 4.11 seconds**, including dynamic JavaScript
tests for foreign source/origin, undeclared capability, arbitrary fields, draft
identity, signed-out storage access, Blob transport and navigation revocation.
Test 2254 passed the standard builder and strict deep signature verification;
embedded resource-delivery and Host client SHA-256 match source.

Original Publisher/key signed a distinct Test-only Suite 0.1.0 r2 candidate:
`packages/ai2apps-media-voice-studio-suite/dist/ai2apps-media-voice-studio-suite-0.1.0-test-sandbox-r2-20260911.ai2app`
SHA-256 `fe8f14e7acfac66ac9a150a4e35ff166dc7b78f9c05b5e29e9aa3cd6ec8811c1`,
30,874 bytes. Earlier candidate bytes remain unchanged. No Cookie was read.

Run `20260911T105258Z-27711` is awaiting manual Test installation approval.
Actual CUA on Test 2254 / port 62061 confirmed candidate verification and normal
`review / medium / local_ai_auditor_not_configured` audit. The user must approve the
new candidate in the displayed product UI. Five UI cases remain pending; neither
real mounted-form success nor real model inference is claimed. The Harness lease
remains active for this handoff. No production publication, commit or push occurred.

### Installation confirmation outcome

The user confirmed approval, but actual Discover UI reports **Same version already
has another digest**. The r2 candidate did not install. The normal ExtensionManager
correctly rejects different bytes for installed Suite 0.1.0; the Test-only importer
does not expose that candidate through Registry's ordinary uninstall list. No
digest check was weakened, installation record deleted, or instance reset.
Run `20260911T105258Z-27711` records all five cases blocked on this shared installation
prerequisite; updated UI and inference results remain unverified. A proper 0.1.1
upgrade with the original Publisher/key requires extending the explicit 0.1.0
Test-only authorization. Finalization/lease cleanup was requested.

### Authorized Suite 0.1.1 upgrade candidate

The prior Run finalized BLOCKED and its test account was released. The user then
explicitly authorized Suite 0.1.1 with the original Publisher/key for continued
Test acceptance. Package, App, five component declarations, SBOM and suite-ready
metadata now consistently use 0.1.1. Related tests: **18 passed**. Old artifacts
remain unchanged; an intermediate 0.1.1 candidate was never installed or published.

Final candidate:
`packages/ai2apps-media-voice-studio-suite/dist/ai2apps-media-voice-studio-suite-0.1.1-test-final-20260911.ai2app`
SHA-256 `be5790b9d42191113a8a316fea2356d8dd58d34b85e37d7d68ebb4d8941439b0`,
30,877 bytes. Standard builder and original key were used; no Cookie was read.
Actual Discover inspection in Test 2254 / port 64004 confirmed version and digest,
with normal `review / medium / local_ai_auditor_not_configured` audit. Run
`20260911T110555Z-28490` is pending user approval at `Approve and install in Test`.
Its Harness lease remains active for the handoff. Installation, UI mounts and real
provider execution are not yet verified; no production publication occurred.

### Suite 0.1.1 actual installed-form acceptance completed

After user approval, actual Test 2254 / port 64004 Studio navigation loaded all
five candidate forms successfully. CUA verified file selectors, workflow options,
rights controls where applicable, and save/run controls. Each iframe completed its
Host capability probe: transcription/separation/voice replacement reported missing
installed model dependencies; subtitles reported its Host workflow available and
individual dependencies checked at invocation. No blank iframe or bridge error
recurred. A screenshot also confirmed the styled subtitle form visually.

Run `20260911T110555Z-28490` finalized **SCOPED_PASS: 5 passed, 0 failed,
0 blocked, 0 pending**, with its test account **released**. Evidence is in the five
Run-local text files and `report.html`. This closes the discovery/mount regression
only: actual media inference, draft save/refresh restoration, upgrade rollback and
full Desktop release acceptance are not claimed. No production publication occurred.
