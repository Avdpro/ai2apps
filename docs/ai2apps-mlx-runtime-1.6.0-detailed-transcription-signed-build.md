# AI2Apps oMLX Runtime 1.6.0 signed build receipt

Date: 2026-09-04 (Asia/Shanghai)

## Build identity

- Package: `ai2apps/runtime-omlx`
- Version: `1.6.0`
- Package type: `service`
- Source commit: `11b5b9ac537e42b1029d1f0148bbbe6a33307f8e`
- Build source: the current working tree, including the Detailed Transcription
  capability, dedicated Worker route, Qwen3-ASR token-limit fix, and Runtime
  payload pruning recorded in NXR-015
- Platform: `darwin-arm64`
- Minimum macOS version: `26.2`

The source worktree was not clean when this candidate was built. The artifacts
below are therefore signed, notarized, and locally verified release candidates,
but they were not submitted to the AI2Apps Registry in this turn. Registry
publication requires reconciling and committing the intended release source.

## Apple-signed Runtime DMG

- Final DMG: `packages/ai2apps-runtime-omlx/dist/AI2AppsOmlxRuntime-1.6.0.dmg`
- SHA-256: `1ae8c38aab38c98f68c6d7eb9c2167bebcb6ecaedce94a812a48808547bc5505`
- Size: `384756624` bytes
- Developer ID identity: `Developer ID Application: Avdpro Pang (84XL5V265N)`
- Developer ID certificate SHA-1: `FDEA0CD31819362ACEC3E0CFC71A1BB0B752602A`
- Notary submission: `938e8163-7319-4bd9-b5ce-abfdeba34216`
- Notary result: `Accepted`
- Staple validation: passed
- Gatekeeper result: `accepted`, source `Notarized Developer ID`

The mounted final DMG passed deep/strict Bundle signature validation in the
full macOS signing environment. Its bundled interpreter reports Python
3.11.10. A complete path scan found no `cp313`, `cpython-313`, or `python3.13`
residue. The four oMLX custom-kernel extensions are all
`_ext.cpython-311-darwin.so`; their MLX-array ABI probes passed, and the
GLM/Direct-L1 `preadv_fused_experts` symbol is available. Host-only ModelScope,
Selenium, and MCP client packages are absent from the Runtime framework.

The pre-staple internal and final DMG copies were byte-identical at SHA-256
`5739eca6429e70c6b5408ba5212c54c1603509ede5561c8fb4a4d9cd8e43e12c`.
Stapling correctly changed the final artifact hash to the value recorded above.

## Publisher-signed AI2Apps Package

- Artifact: `packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.6.0-production.ai2service`
- Envelope: `packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.6.0-production.ai2service.envelope.json`
- Artifact SHA-256: `ce4f946b4f3a9f90f5e68e07d1d8a965e4ba1634a89fe895dfd6ca2a9c03a9a5`
- Artifact size: `382501589` bytes
- Envelope SHA-256: `ffbdd486e6695a90fced91b154359be7b7d4774d87662fdb43362741ff07c2b1`
- Envelope size: `800` bytes
- Media type: `application/vnd.ai2apps.service+zip`
- Publisher ID: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher public-key fingerprint:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

The formal Publisher key was selected only after deriving its public key in
memory and matching the registered fingerprint above. A second local key with
a different fingerprint was explicitly rejected. No private-key value was
printed, copied, exported, or written to this receipt.

The Publisher envelope passed offline Ed25519 verification against the exact
artifact bytes. Package identity, version, manifest digest, artifact digest,
and size all matched. The archive has eight deterministic members. Its embedded
DMG SHA-256 is
`1ae8c38aab38c98f68c6d7eb9c2167bebcb6ecaedce94a812a48808547bc5505`,
exactly matching the notarized standalone DMG. The embedded Runtime descriptor
records `developer-id` signing, Team ID `84XL5V265N`, Python 3.11 paths, and the
`audio-detailed-transcription-v1` capability.

## Verification summary

- Runtime/Package/Model Worker and Detailed Transcription regression suite:
  `138 passed, 5 skipped`; one test invoked a cp311 extension from the repository
  with the development `.venv` Python 3.13 and failed at the expected ABI
  boundary rather than in Runtime code.
- The authoritative bundled-CPython 3.11 native gate passed all four ABI probes,
  custom-kernel deployment-target checks, and the Direct-L1 symbol check.
- Earlier focused Runtime/Package/Model Worker verification: `109 passed`.
- Targeted `git diff --check`: passed.
- Developer ID Bundle verification, notarization, staple validation, Gatekeeper
  assessment, Publisher envelope verification, and embedded-DMG equality: passed.

## Publication state

No Registry submission, review, publication, Cloud metadata mutation, or Cookie
access was performed. This receipt covers only the signed/notarized Runtime DMG
and Publisher-signed outer Package produced at the paths above.
