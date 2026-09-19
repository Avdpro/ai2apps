# AI2Apps Media Voice Studio Suite 0.1.0 signed build receipt

Date: 2026-09-07 (Asia/Shanghai)

## Release identity

- Package: `ai2apps/media-voice-studio-suite`
- Version: `0.1.0`
- Package type: `app`
- Media type: `application/vnd.ai2apps.app+zip`
- Mini-App count: `5`
- Platform: `darwin-arm64`

The signed App Package contains the following installed-package Mini-Apps:

1. detailed recording transcription with anonymous speaker detection, role naming,
   and JSON/Markdown/SRT export;
2. voice/background and multi-stem source separation;
3. one-speaker audio voice replacement using an authorized reference voice;
4. SRT/WebVTT/ASS video subtitle generation, optional Standard-model translation,
   bilingual output, and optional MP4 burn-in;
5. one-speaker video voice replacement with original-picture remux.

The Package has no eager top-level model dependency. Each operation resolves its
installed provider at execution time through the mount-bound Host Capability Broker.
The initial provider set is MLX WhisperX Detailed Transcription 0.1.2, MLX Demucs
0.1.0, and MLX Seed-VC v2 0.1.0. Translation uses the existing configured Standard
model route. Host media composition uses bundled PyAV and never exposes a Worker
endpoint, checkpoint location, or arbitrary local path to Mini-App code.

## Signed artifacts

- Artifact:
  `packages/ai2apps-media-voice-studio-suite/dist/ai2apps-media-voice-studio-suite-0.1.0-production.ai2app`
- Artifact SHA-256:
  `7e3ffa9cfaed8912c2b27b46c4f6f0a638f35a982102e18c5a0450a4b5972355`
- Artifact size: `28196` bytes
- Manifest SHA-256:
  `96c281515ffe0ced1865958cbc80d9ff38d9457921c60bac2e0733d98fb2b6ec`
- Envelope:
  `packages/ai2apps-media-voice-studio-suite/dist/ai2apps-media-voice-studio-suite-0.1.0-production.ai2app.envelope.json`
- Envelope SHA-256:
  `97c672ae1a1a084c1a3d86232637e44587b8ba22094e2e7df83f48512d6cba6b`
- Envelope size: `800` bytes
- Publisher ID: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher public-key fingerprint:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

The artifact was built and signed with
`scripts/build_signed_registry_release.py --omit-mini-app-catalog`. This release-
compatibility option omits only the optional top-level Cloud search projection; the
complete five-component `app.yaml` remains indexed and covered by the same Publisher
signature, so current clients discover all components after installation. The private key remained in the macOS
Keychain. Its DER/SPKI public fingerprint was derived in memory and matched the
registered production fingerprint before the final artifact and detached envelope
passed offline Ed25519 verification. No private-key value was printed, copied, or
written to this receipt.

## Verification

- Package Contract, Registry, installed Mini-App discovery/mount, broker security,
  model-provider selection, multipart API, subtitle/media, and extension regression:
  `85 passed`.
- Ruff on the changed Python implementation and tests: passed.
- JavaScript syntax validation for both Package scripts: passed.
- Targeted `git diff --check`: passed.
- Repeat Package builds after a populated `dist/` directory: byte-identical. The
  Contract builder now excludes `dist/` for every Package type, with a regression
  test preventing recursive output inclusion.
- Final Package Contract inspection: 19 indexed payload files; the legacy-Cloud outer
  manifest has no optional `miniApps` projection, while its indexed and signed
  `app.yaml` contains exactly five Mini-App declarations.
- Final detached Publisher envelope: offline verification passed against the exact
  artifact bytes and the registered production public-key fingerprint.
- Fixed App development environment: `AI2Apps-App-Dev`, instance `app-dev`, boot ID
  `189582a3-08ff-46a1-b796-8fb109ec56dc`, Local port `49791`; bootstrap reported
  ready and its live OpenAPI exposed list, mount, capability-probe, and capability-
  invoke Studio Mini-App routes.

The test environment is headless and emitted the expected MLX atexit notice that no
Metal device was available; no test failed because of it. Real checkpoint execution
remains a post-install acceptance step because the isolated App-Dev instance does not
currently contain the Detailed Transcription, Demucs, or Seed-VC Packages.

## Publication state

No Registry submission, review, publication, Cloud mutation, browser Cookie access,
or external artifact upload was performed. The artifact/envelope pair is a signed,
offline-verified release candidate ready for the standard Registry publication tool
and the pre-`miniApps` Cloud manifest schema.

The future Cloud component-level Discover upgrade remains specified in
`docs/ai2apps-cloud-mini-app-discovery-requirements.md`. Once deployed, the next
Package release should use the default builder so Cloud can index the signed top-level
projection. This repository does not modify Cloud code.
