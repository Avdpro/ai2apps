# AI2Apps Media Voice Studio Suite 0.2.1 release receipt

Date: 2026-10-05 (Asia/Shanghai)

## Release identity

- Package: `ai2apps/media-voice-studio-suite`
- Version: `0.2.1`
- Type: App Package with six source-declared Mini-Apps
- Source commit at build time: `fa377dcb62875d5c82fc8177afd4277cd2357db9`
- Publisher: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher public-key fingerprint:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

The signing record was recovered from the prior successful release context as key reference
`sec_7d62c890f9cb46c0a223c02ec6d7ee9e` in namespace
`local_cd8e3c23002c87b528cc5f4790fa1269`. The public key derived from that exact record matched the
registered fingerprint before signing. No Publisher, Publisher key, Package ID, instance data, or
Runtime was created, replaced, copied, or migrated.

## User-visible change

0.2.1 adds complete English and Simplified Chinese localization for the Package and all six
Mini-Apps. The signed Package metadata now carries localized Package and Mini-App names and
descriptions, while each Package-hosted page localizes its dynamic workflow text, controls,
validation messages, result states, and accessible labels. English remains the fallback. User
subtitle text, speaker names, filenames, and model names are treated as user or provider data and
are not translated.

The Package has no new Runtime, model, permission, or dependency requirement. Shared Host locale
propagation and localization selection are Desktop inputs tracked separately in the next-release
ledger; publishing this Package does not publish a new Desktop client.

## Signed artifact

- Artifact:
  `packages/ai2apps-media-voice-studio-suite/dist/ai2apps-media-voice-studio-suite-0.2.1-production.ai2app`
- Artifact SHA-256:
  `c502c05dac2b1c7ef454a202e0f6937186b21c6c229a792599adc9dbda77771b`
- Artifact size: `49980` bytes
- Detached envelope:
  `packages/ai2apps-media-voice-studio-suite/dist/ai2apps-media-voice-studio-suite-0.2.1-production.ai2app.envelope.json`
- Build compatibility: `scripts/build_signed_registry_release.py --omit-mini-app-catalog`

The optional top-level Mini-App search projection remains omitted for the current production Cloud
schema. The authoritative six-component `app.yaml`, localized metadata, resources, help content,
SBOM, and license remain indexed and Publisher-signed. Because this Package is small, Cloud is its
sole artifact source; no ModelScope or GitHub mirror is required.

## Publication

- Submission: `af5ec328-6bab-4d5a-a07f-9a38efb3d381`
- Submission created at: `2026-10-05T04:14:33.020Z`
- Review: `ea7892c9-cb0a-4220-98cb-4979b242071f`
- Review created at: `2026-10-05T04:14:33.236Z`
- Status: `published`
- Repository metadata version: `247`

The standard publication script used the explicitly authorized live **Dev** instance session only
for this exact Package/version. It did not read another instance's cookies. Cookie values were not
printed, copied, or persisted, and the authorization expired when this publication completed.

## Verification

- JavaScript syntax checks passed for the Package localization/workflow code and the shared Studio
  Mini-App client.
- Package localization and transcript-edit Node tests passed.
- Ruff completed with `--no-cache`; `git diff --check` passed.
- 148 focused Package, Studio client, sandbox document, capability broker, media workflow, and
  provisioning Python tests passed. The sandboxed Metal atexit warning occurred only after the
  completed pytest result and does not represent GPU validation.
- Two unsigned Contract builds were byte-identical with SHA-256
  `eb314b1175f09a49a30e221c8b9a1b24d7962c21175df7684e01bb0ad3f78ee0`.
- The exact signed artifact was verified and installed into an isolated instance; it reached
  `active` and all six Package Mini-Apps were discovered.
- The publication progressed through candidate, review pending, approved, and published using the
  standard signed-artifact publication script. A preflight list found no existing 0.2.1
  submission, so no duplicate submission was created.
- A Cookie-free public verification against Repository metadata version 247 returned
  `artifactExactBytes: true` and `envelopeExactJson: true`, with the exact SHA-256, size,
  Publisher, and Publisher key above.

App-Dev may continue to source-mount the Package for development. Installed Dev and production
instances can upgrade to 0.2.1 through Discover. Correct Host-locale propagation in production
still depends on the separately tracked Desktop Host release.
