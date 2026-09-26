# AI2Apps Media Voice Studio Suite 0.1.2 release receipt

Date: 2026-09-23 (Asia/Shanghai)

## Release identity

- Package: `ai2apps/media-voice-studio-suite`
- Version: `0.1.2`
- Type: App Package with five source-declared Mini-Apps
- Publisher: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher public-key fingerprint:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

## User-visible change

Video Subtitles and Translation now offers Small, Standard, Large (default), and Extra Large
subtitle sizes. Users can choose white text with a scale-aware thick black outline or white text on
a translucent black rounded box. Host layout measures the selected typography and background
together with two-line wrapping and video safe areas before rendering.

## Signed artifact

- Artifact:
  `packages/ai2apps-media-voice-studio-suite/dist/ai2apps-media-voice-studio-suite-0.1.2-production.ai2app`
- Artifact SHA-256:
  `40d6425c1021b65c7de9c9584986ab4644ef68a661b6911c6e7a2ab198cbabe0`
- Artifact size: `32164` bytes
- Detached envelope:
  `packages/ai2apps-media-voice-studio-suite/dist/ai2apps-media-voice-studio-suite-0.1.2-production.ai2app.envelope.json`
- Build compatibility: `scripts/build_signed_registry_release.py --omit-mini-app-catalog`

The optional top-level Mini-App search projection is omitted for the current production Cloud
schema. The authoritative five-component `app.yaml`, resources, and license file remain indexed and
Publisher-signed, so current clients discover the Mini-Apps after installation.

The first submission attempt was rejected before creating a submission because production Cloud
does not yet accept the Contract v1 nested `package.localizations` and `package.license` properties.
The outer compatibility manifest omits these two optional properties; localized App metadata stays
in signed `app.yaml`, and `LICENSE` remains an indexed signed payload. The Cloud schema handoff is
updated in `docs/ai2apps-cloud-package-discovery-schema-requirements.md`.

## Publication

- Submission: `caa0b6b5-1ed4-42e8-b539-f048da3bd997`
- Review: `eae5c168-4bbd-45af-84e6-c5e19859cf33`
- Status: `published`
- Repository metadata version: `195`

The standard publication script used the explicitly authorized live **Dev** instance session for
this exact Package/version. It did not read App-Dev cookies. Cookie values were neither printed nor
persisted, and that authorization expired when publication completed.

## Verification

- 79 focused media-workflow, capability-broker, Studio API/bridge, Package UI, candidate, and
  sandbox-document tests passed before signing.
- 10 Package and Development Bundle source-mount regressions passed after the Cloud compatibility
  adjustment.
- Ruff, JavaScript syntax, Package Contract inspection, and diff-whitespace checks passed.
- Anonymous public verification against Repository metadata version 195 returned
  `artifactExactBytes: true` and `envelopeExactJson: true`, with the exact SHA-256 and size above.

App-Dev source-mounts this Package from the trusted repository with `distribution=development`; it
does not require a local Package installation. Installed Dev and production instances must upgrade
to 0.1.2 to receive the new Mini-App resources. No Runtime or checkpoint release changed.
