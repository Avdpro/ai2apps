# AI2Apps oMLX Runtime 1.5.7 Qwen3.8 packaging-fix release receipt

Date: 2026-09-01 (Asia/Shanghai)

## Release identity

- Package: `ai2apps/runtime-omlx`
- Version: `1.5.7`
- Package type: `service`
- Source commit: `66736ccaed462e6f366b03d15c10aec5b43213ff`
- Build source: the current working tree, including the Runtime 1.5.7 metadata,
  Qwen3.8 checkpoint-view fix, and native-kernel ABI build gates described below
- Platform: `darwin-arm64`
- Minimum macOS version: `26.2`
- AI2Apps compatibility: `>=0.1.0 <2.0.0`

This is a new immutable Runtime release. The already published 1.5.6 artifact
was not overwritten.

## Incident fixes

Runtime 1.5.6 had two independent packaging failures:

1. Qwen3.8 checkpoint classification resolved safetensors symlinks before
   comparing them with the lexical checkpoint view. That prevented MLX-format
   metadata from being stripped and left 672 parameters unrecognized.
2. The Runtime bundled CPython 3.11 while stale custom-kernel extensions for
   CPython 3.9 and 3.13 could be copied into the bundle. Direct-L1 therefore
   could not load its native extension from the installed Runtime.

Runtime 1.5.7 fixes these failures by:

- matching checkpoint safetensors by lexical absolute path without resolving
  the model-view symlink;
- building every custom kernel, including Bonsai, with the bundled CPython
  3.11 executable and an explicit CMake Python root;
- removing stale source/build custom-kernel binaries before compilation and
  staging;
- rejecting a release unless every custom-kernel extension has the exact
  `_ext.cpython-311-darwin.so` ABI and no other CPython ABI extension exists;
- running the bundled-Python ABI probe against the exact staged cp311 file.

The custom-kernel deployment target was built as macOS 26.2 to match the
Package compatibility contract and bundled MLX layer.

## Apple-signed Runtime DMG

- Final DMG: `packages/ai2apps-runtime-omlx/dist/AI2AppsOmlxRuntime-1.5.7.dmg`
- SHA-256: `fdfb19640d9a2cf31f05e28ebc9cc37560786f3d0ec9fe1130aa20eedac15224`
- Size: `459918004` bytes
- Developer ID identity: `Developer ID Application: Avdpro Pang (84XL5V265N)`
- Developer ID certificate SHA-1: `FDEA0CD31819362ACEC3E0CFC71A1BB0B752602A`
- Notary submission: `0d11dc57-a157-441f-9bac-defe7678428b`
- Notary result: `Accepted`
- Staple validation: passed
- Gatekeeper result: `accepted`, source `Notarized Developer ID`

The mounted final DMG passed deep/strict code-signature validation and its
designated requirement. Its bundled CPython is 3.11.10. It contains four
native extensions (Bonsai, GLM/Direct-L1, MiniMax M3, and Qwen prefill), all
named `_ext.cpython-311-darwin.so`; no cp39 or cp313 extension is present.

Using only the mounted/installed Runtime's Python, MLX, and oMLX paths loaded
the GLM/Direct-L1 native extension successfully and confirmed that
`preadv_fused_experts` is available.

## Signed AI2Apps Package

- Artifact: `packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.5.7-production.ai2service`
- Envelope: `packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.5.7-production.ai2service.envelope.json`
- SHA-256: `b7f5e0bddcf285908ddd75465c02bdd35a9f6aa90690c739054a75295ea4bd49`
- Size: `457410846` bytes
- Media type: `application/vnd.ai2apps.service+zip`
- Publisher ID: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher public-key fingerprint:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

The formal Publisher key was used only after both the local derived public
fingerprint and the active Cloud key fingerprint matched the value above. No
private key was printed, copied, or stored in this receipt.

The Package has eight archive members. Its only large payload is the notarized
Runtime DMG; it contains no checkpoint, safetensors, GGUF, CKPT, or expert-store
payload.

## Verification

- Focused Runtime/package/Qwen regression suite: `21 passed`.
- Targeted checkpoint-symlink and custom-kernel subset: `4 passed`.
- Shell syntax and targeted `git diff --check`: passed.
- Runtime metadata version in all four release files: 1.5.7.
- Clean signed-Package installation: passed.
- Installed Runtime resolution: `ai2apps.runtime.omlx` 1.5.7 with digest
  `sha256:b7f5e0bddcf285908ddd75465c02bdd35a9f6aa90690c739054a75295ea4bd49`.
- Qwen model dependency lock: resolved exactly to Runtime 1.5.7.
- Qwen Worker: `ai2apps.model.qwen38-flash-next-4bit` 0.1.0 reached `running`.
- Installed Runtime Python: CPython 3.11.10.
- Installed native extension:
  `omlx/custom_kernels/glm_moe_dsa/_ext.cpython-311-darwin.so`.
- Installed Direct-L1 symbol `preadv_fused_experts`: available.

A real Qwen3.8 Flash Next MLX 4-bit Cached-MoE run used the installed signed
Runtime, the existing Hugging Face checkpoint, the converted expert store,
Natural routing, Top160, Hot10, and Direct-L1 forced on. It generated eight
non-empty tokens (`To understand why a Sparse Mixture-of`) with 428 native
direct-load calls. The observed short cold-run decode rate was 10.97 TPS and
the MLX peak was 44.08 GiB. This was a functional packaging acceptance run,
not a warmed throughput benchmark.

The ModelScope mirror path was not separately downloaded and replayed in this
release turn. The defect and fix are Runtime path/ABI issues independent of
checkpoint transport; the already installed HF bytes exercised the real model
load and Direct-L1 generation path.

## Cloud publication

- Submission ID: `5d18ea90-4f01-40c1-b446-2dd92b386a6c`
- Review ID: `9f5fdd4e-8446-465f-b56a-379eae56a2e5`
- Review decision: `approved`
- Release status: `published`
- Submission created at: `2026-09-01T11:01:21.080Z`
- Review created at: `2026-09-01T11:01:21.765Z`
- Repository metadata version: `98`

The first large upload ended with an HTTP read error. A query immediately
afterward confirmed that Cloud had created no 1.5.7 submission, so retrying
could not duplicate a release. The identical signed artifact was uploaded
again and the standard script completed submit, review request, approval, and
publication.

Publication used only `scripts/publish_signed_registry_artifact.py` and the
exact authorized current AI2Apps dev `app-shell` profile. The scoped Cookie
authorization applied only to `ai2apps/runtime-omlx 1.5.7` and expired as soon
as publication completed. No Cookie value was copied, exported, printed, or
stored.

## Anonymous public read-back

A clean Registry client with an empty `MemorySecretBackend` verified the
public repository snapshot and Publisher envelope, then downloaded the public
artifact. The public result is:

- trusted metadata version: `98`;
- release status: `published`;
- SHA-256: `b7f5e0bddcf285908ddd75465c02bdd35a9f6aa90690c739054a75295ea4bd49`;
- size: `457410846` bytes;
- Publisher ID/key/fingerprint: exact expected match;
- public artifact bytes: exact local digest and size match.

The host HTTP proxy twice truncated public Registry responses during the first
anonymous attempts. A process-local retry with proxy environment variables
unset completed in about four seconds. It still used the same HTTPS Registry
endpoint, pinned repository fingerprint, standard verification code, and an
empty anonymous session.

Public artifact endpoint:
`https://coder.ai2apps.com/v1/registry/packages/ai2apps/runtime-omlx/versions/1.5.7/artifact`.
