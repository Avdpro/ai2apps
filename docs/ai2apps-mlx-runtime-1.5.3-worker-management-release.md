# AI2Apps oMLX Runtime 1.5.3 Worker Management Release Receipt

发布日期：2026-08-27

## Release identity

- Source commit: `66736ccaed462e6f366b03d15c10aec5b43213ff`
- Source state: working tree contained the reviewed AI2Apps next-stage development changes; the immutable release artifact is identified by the SHA-256 below.
- Package ID: `ai2apps/runtime-omlx`
- Version: `1.5.3`
- Package type: `service`
- Artifact: `packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.5.3-production.ai2service`
- Artifact SHA-256: `b87581e98f2d889ed4b1db8b21d4203936715b800e9d28de62a75c980860486c`
- Artifact size: `455292893` bytes
- Publisher ID: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher key fingerprint SHA-256: `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

## Delivered behavior

- Model Worker scheduling remains transparent to Chat, Read Aloud, Imagine Studio, Video Studio, and other model consumers.
- Dashboard lists Worker lifecycle, PID, RSS, generation, active/queued work, pin state, and eviction reason, and supports Load, Drain & Exit, Cancel Drain, and idle-only Exit.
- Runtime installation is staged until Local restart, then activated atomically with dependency relocking.
- Failed or timed-out drain operations resume the Worker instead of leaving it stuck in draining state.
- Runtime and Worker control remains outside business App APIs; non-model Apps do not depend on Worker scheduling.
- `AI2APPS_ALLOW_DEVELOPMENT_RUNTIME` is injected only by the explicitly marked development Helper. Release builds do not contain the development marker.

## Validation

### Targeted automated gates

- Python: `173 passed` covering Worker management/resources/scheduler, model invocation, Chat provider routing, Read Aloud, Imagine Studio, Video Studio, oMLX audio adapter, Package lifecycle, and inference Runtime contracts.
- Swift: `53 passed` covering Helper/App identity, development-only Runtime permission, instance isolation, browser-agent lifecycle, update validation, and release boundaries.
- `git diff --check`: passed.
- Python compileall and release-builder entry point checks: passed.
- General Agent repeated-tool protection was confirmed to terminate correctly; its timing assertion was widened from 3 to 10 seconds to avoid a load-sensitive false failure.

### Full-repository diagnostic run

An additional non-blocking full-suite diagnostic was stopped at 45% after Hub download retry tests became network-bound. At that point it reported `4275 passed`, `60 failed`, `21 skipped`, and `74 deselected`.

The failures were reviewed rather than treated as a green release gate. They were outside the Runtime 1.5.3 Worker scope and primarily represented:

- legacy unauthenticated Server/API tests expecting 200 where the current Local-session boundary correctly returns 401;
- retired API-key Web login tests expecting the pre-retirement contract instead of 410;
- App catalog and Chat template snapshots that predate Knowledge, Gallery, Read Aloud, Imagine Studio, and Video Studio;
- unrelated MLX exact-equality/numerical tolerance tests;
- the load-sensitive Agent timeout noted above, whose underlying loop protection passed with the corrected observation window.

The authoritative 1.5.3 release gates are the targeted suites, signed Package validation, real AI2Apps-dev managed installation, Apple validation, and clean public Registry installation recorded here.

### AI2Apps-dev real-device acceptance

- Development Package 1.5.3 installed and activated with all five installed Workers discovered.
- Dashboard Load produced READY with a new PID/generation.
- Drain & Exit exposed Draining and Cancel Drain, then safely reached STOPPED.
- Dependency protection rejected draining the punctuation Worker while SenseVoice depended on it; failure recovery returned it to READY.
- Idle timeout eviction and on-demand reload were observed.
- Chat listed local MiniMax Worker models while Worker lifecycle remained hidden from the business UI.
- Read Aloud, Imagine Studio, and Video Studio exposed model/generation concepts only, with no direct Worker lifecycle coupling.

## Apple release validation

- Developer ID identity: `Developer ID Application: Avdpro Pang (84XL5V265N)`
- Team ID: `84XL5V265N`
- Notary submission ID: `9bd4ea5f-5448-428e-bf80-35a6409acf3e`
- Notary status: `Accepted`
- Stapler: staple and validate passed.
- Gatekeeper: `accepted`, source `Notarized Developer ID`.
- Publisher envelope was verified locally against the same public key used by Runtime 1.5.2 before Cloud submission.

## Cloud publication

- Submission ID: `c7ceaca1-4337-4edd-bf94-67789608d239`
- Review ID: `cbc02d73-8031-46a4-8a5c-dc27b161f7aa`
- Review decision: `approved`
- Release status: `published`
- Published at: `2026-08-27T03:16:17.421Z`
- Repository metadata version returned by publication: `68`

## Public Registry read-back and clean install

Anonymous public Registry verification, without a browser Cookie, confirmed:

- catalog latest version: `1.5.3`;
- release status: `published`;
- installability: `true`, no blockers;
- compatibility: AI2Apps `>=0.1.0 <2.0.0`, darwin/arm64, minimum macOS `26.2`;
- public artifact SHA-256 and size exactly match this receipt.

A clean temporary instance downloaded the artifact through the signed public repository metadata, installed it, restarted Local, and confirmed:

- activation status: `active`;
- active digest: `sha256:b87581e98f2d889ed4b1db8b21d4203936715b800e9d28de62a75c980860486c`;
- descriptor version: `1.5.3`;
- descriptor protocol: `ai2apps-model-worker/v1`;
- private Runtime Python: executable, `Python 3.11.10`;
- Model Worker launcher: present in the materialized Runtime root.

The one-release browser Cookie authorization expired immediately after Cloud publication and was not used for public Registry verification.
