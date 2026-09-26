# AI2Apps Media Voice Studio Suite 0.2.0 release receipt

Date: 2026-09-24 (Asia/Shanghai)

## Release identity

- Package: `ai2apps/media-voice-studio-suite`
- Version: `0.2.0`
- Type: App Package with six source-declared Mini-Apps
- Publisher: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher public-key fingerprint:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

The signing record was recovered from the prior successful release context as key reference
`sec_7d62c890f9cb46c0a223c02ec6d7ee9e` in namespace
`local_cd8e3c23002c87b528cc5f4790fa1269`. Before signing, the public key derived from that exact
record was checked against the registered fingerprint above. No Publisher, Publisher key, Package
ID, version, or instance data was created, replaced, copied, or migrated.

## User-visible change

0.2.0 adds the sixth Mini-App, **Video Audio Translation**, for single-narrator and explainer
videos. It translates sentence-sized narration cues, generates replacement speech from a selected
Voice Studio Character, preserves the background stem, aligns each sentence to its original time
window, and publishes the remuxed MP4 through Video Studio's host-owned Generation result.

The workflow includes per-stage progress, concise-translation retry for overflowing cues,
model-native speed adjustment where supported, final pitch-preserving time compression, optional
ASR back-listening with bounded regeneration, and `Original voice · temporary clone`. Original-voice
mode selects a clear roughly ten-second reference window with matching transcript text, offers only
installed single-reference cloning models, can launch ACPF through `Install more models…`, and keeps
the temporary reference outside Characters and retained output storage.

## Signed artifact

- Artifact:
  `packages/ai2apps-media-voice-studio-suite/dist/ai2apps-media-voice-studio-suite-0.2.0-production.ai2app`
- Artifact SHA-256:
  `78bb7f0e76bdead49ad9b873e161b820886efb2ba895a2151f93c4775f2efc02`
- Artifact size: `37292` bytes
- Detached envelope:
  `packages/ai2apps-media-voice-studio-suite/dist/ai2apps-media-voice-studio-suite-0.2.0-production.ai2app.envelope.json`
- Build compatibility: `scripts/build_signed_registry_release.py --omit-mini-app-catalog`

The optional top-level Mini-App search projection remains omitted for the current production Cloud
schema. The authoritative six-component `app.yaml`, resources, help content, SBOM, and license are
still indexed and Publisher-signed. Because this Package is small, Cloud remains its sole required
artifact source; no Runtime or checkpoint distribution changed.

## Publication

- Submission: `a8f0664e-7729-4158-ae08-89518e4fd94f`
- Submission created at: `2026-09-23T20:33:16.744Z`
- Review: `617ed92b-157d-4cab-9e63-84bf0c6c8c05`
- Status: `published`
- Repository metadata version: `196`

The standard publication script used the explicitly authorized live **Dev** instance session for
this exact Package/version. It did not read App-Dev cookies. Cookie values were neither printed nor
persisted, and that authorization expired when publication completed.

## Verification

- 116 focused Package, provisioning, Host bridge, capability-broker and media-workflow tests passed.
- Ruff, both relevant JavaScript syntax checks, Contract construction and diff-whitespace checks
  passed. The harmless sandboxed Metal atexit warning occurred after the completed pytest run and
  did not change its 116/116 result.
- The publication progressed through candidate, review pending, approved, and published using the
  standard signed-artifact publication script; there was no pre-existing 0.2.0 submission.
- Anonymous public verification against Repository metadata version 196 returned
  `artifactExactBytes: true` and `envelopeExactJson: true`, with the exact SHA-256 and size above.

App-Dev continues to source-mount this Package from the trusted development repository; it does not
need to install 0.2.0 for development-mode testing. Installed Dev and production instances must
upgrade the Package to receive the sixth Mini-App and its resources. The Host-side workflow changes
remain Desktop release inputs tracked separately in the next-release ledger.
