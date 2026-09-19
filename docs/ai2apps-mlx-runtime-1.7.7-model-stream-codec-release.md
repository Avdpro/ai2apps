# AI2Apps oMLX Runtime 1.7.7 model stream codec release

Date: 2026-09-20 (Asia/Shanghai)

Status: published and anonymously verified

## Scope

Runtime 1.7.7 introduces the versioned pure-Python
`ai2apps.model-stream-codec/v1` extension point. Future Model Packages can
provide model-specific token-to-text, special-token preservation, and
append-only streaming normalization without bundling native code or requiring a
Runtime release for each formatting policy change.

Existing Model Packages remain compatible and were not upgraded. They continue
through the Runtime's existing adapters when `create_stream_codec()` returns
`None`. MLX/oMLX, tokenizer native implementations, Metal kernels, Worker Host,
protocol routing, and metering remain Runtime-owned.

Contract v1 build/inspection and the legacy Service Archive inspector now reject
native payloads in `ai2apps-model-worker/v1` Packages, including native-artifact
declarations. This preserves the pure-Python Model Package boundary.

## Verification

- 69 focused tests passed across the stream codec, DeepSeek V4.1 decoder, Chat
  adapter, Cache-MoE Worker, Package Contract, legacy Service Archive, Runtime
  Package, and Runtime builder.
- Ruff and diff whitespace checks passed for the changed implementation.
- The unchanged `ai2apps/model-deepseek-v41-flash 0.1.1` Package built through
  the standard builder, confirming that existing Packages do not need an
  upgrade for the new extension point.
- The fixed App-Dev environment was rebuilt and passed strict deep signing,
  identity, embedded-codec, native-title, and Local health checks.
- The production archive passed local Package inspection, publisher signature
  verification, and artifact/manifest digest verification before submission.

## Apple and Publisher receipt

- Developer ID: `Developer ID Application: Avdpro Pang (84XL5V265N)`
- Apple notarization submission: `b15b7da5-0eec-4afb-aad6-6279e131220d`
- Apple result: `Accepted`
- Stapler validation: passed
- Gatekeeper: `accepted`, source `Notarized Developer ID`
- Stapled DMG SHA-256:
  `4ca9eaa2ca9e772f89715df6ecc88f4549ae9412090eb2e116d7bc3bfb25a8b0`
- Stapled DMG bytes: 379,237,144
- Publisher: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Public-key fingerprint:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

The current Dev namespace contained an older active Publisher key. Under the
user's explicit authorization, one existing candidate in another local
namespace was read only in memory and selected only after its derived public
fingerprint exactly matched the recent production key above. The private key
was not printed or exported.

## Production publication

- Package: `ai2apps/runtime-omlx` 1.7.7
- Artifact SHA-256:
  `f1b8d19e6befcb9c604bf975fd6dbdd3bb055db8a78fa83c17ef3e498dfc9408`
- Artifact bytes: 377,042,056
- Manifest SHA-256:
  `9f5b9bc549d1db1ba63c8fd97d4ec7cef1bede347133f92b0619dc6aef53f568`
- Submission: `9b85c590-199c-4ec4-80e7-f87d10fc4392`
- Review: `17511876-fb14-4923-8719-91ae4cf3a57f`
- Repository metadata version: 179
- Anonymous readback: `artifactExactBytes: true`, `envelopeExactJson: true`

The authorized current Dev Cookie was accessed only through the live
authenticated Shell BiDi path. No Cookie SQLite database was read or copied.
The Cookie authorization expired immediately after publication; anonymous
verification did not use it.

This large Runtime remains Cloud-single-source, matching Runtime 1.7.5 and
1.7.6. The Package publication runbook permits this temporary exception. The
identical immutable artifact should later be mirrored to fixed GitHub and
ModelScope revisions, fully hash/Range validated, and activated through a
separately authorized protected source update.
