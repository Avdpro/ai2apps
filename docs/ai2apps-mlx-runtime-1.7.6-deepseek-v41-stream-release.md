# AI2Apps oMLX Runtime 1.7.6 DeepSeek V4.1 stream release

Date: 2026-09-19 (Asia/Shanghai)

Status: published and anonymously verified

## Scope

Runtime 1.7.6 fixes the dedicated DeepSeek V4.1 streaming decoder. Special
`<think>` boundaries remain visible to the Worker reasoning parser, EOS is excluded
explicitly, an incomplete UTF-8 suffix is withheld, and decoded deltas are
append-only. Reasoning is therefore persisted in `reasoning_content` without being
replayed into visible `content`, and the transient U+FFFD no longer leaks.

No checkpoint, model Package, model identity, revision, distribution, native
kernel, or Host Worker source changed in this release.

## Frozen source and verification

The release source was copied from the mounted, published Runtime 1.7.5 DMG. Only
`omlx/patches/deepseek_v41/engine.py` differs by content. The current worktree's
unrelated rebuilt native libraries were deliberately excluded. The `ai2apps`
Model Worker tree is byte-identical to Runtime 1.7.5.

- Runtime/Worker/Package focused suite: 28 passed.
- App-Dev real request `请只回答：你好`: visible content exactly `你好`;
  reasoning stored separately; no U+FFFD or replay.
- Isolated exact-artifact install with DeepSeek V4.1 0.1.1: Worker `running`;
  dependency lock resolved Runtime 1.7.6 with the published digest.

## Apple and Publisher receipt

- Developer ID: `Developer ID Application: Avdpro Pang (84XL5V265N)`
- Apple notarization submission: `06b63e09-2d23-47c5-91b2-f6fbf7ea79a4`
- Apple result: `Accepted`
- Stapler validation: passed
- Gatekeeper: `accepted`, source `Notarized Developer ID`
- Stapled DMG SHA-256:
  `a4f47eb3bf1aaa3ed79711d1b586807b54f0b2c0623bc8e10900974d77751096`
- Stapled DMG bytes: 375,238,531
- Publisher: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Public-key fingerprint:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

The first Cloud submit attempt was rejected before creating a submission because
an older local Secret Store record signed for a different active Publisher key.
The two existing candidates were compared only by derived public fingerprint; no
private key was printed or exported. The Package was re-signed with the existing
record that exactly matches the registered key above. Package bytes did not change.

## Production publication

- Package: `ai2apps/runtime-omlx` 1.7.6
- Artifact SHA-256:
  `cd383af9b9dc8bd11105b4a7b83217d6d5e5f568237de7c458e391a67869e324`
- Artifact bytes: 373,043,941
- Submission: `8a9f69d0-4512-4e3b-bdbb-ad9c0cce2f98`
- Review: `090c2fc3-1a24-4579-aaeb-d291c5033336`
- Repository metadata version: 178
- Anonymous readback: `artifactExactBytes: true`, `envelopeExactJson: true`

The authorized current Dev Cookie was accessed only through the live authenticated
Shell BiDi path. No Cookie SQLite database was read or copied. The authorization
expired immediately after publication; anonymous verification did not use it.

This large Runtime is currently Cloud-single-source, matching Runtime 1.7.5. The
Package runbook permits this temporary exception; the identical immutable artifact
must later be mirrored to fixed GitHub and ModelScope revisions, fully hash/Range
validated, and activated through a separately authorized protected source update.
