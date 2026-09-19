# AI2Apps oMLX Runtime 1.7.8 Qwen3.6 Tiered pre-split release

Date: 2026-09-20 (Asia/Shanghai)

Status: published, three-source active, and anonymously verified

## Scope

Runtime 1.7.8 fixes Qwen3.6 Tiered SSD loading when the scoped reader has
already separated the checkpoint into a Top120 protected bank and a Tail24
replaceable bank. The text-model sanitizer now accepts that exact pre-split
representation while preserving the complete 256-row and legacy compact
144-row compatibility paths.

The existing `ai2apps/model-qwen36-35b` 0.3.4 Package, scope pack, and immutable
checkpoint were not changed or republished.

## Verification

- 55 focused Qwen3.6, Cache-MoE Worker, Inference Runtime Package, and Runtime
  builder tests passed in the real macOS/Metal environment.
- The App-Dev Package Manager installed the 1.7.8 development candidate and,
  on Local restart, atomically activated it and relocked every compatible
  active model from 1.7.7 to 1.7.8.
- The live Qwen3.6 Worker was confirmed to execute from the materialized 1.7.8
  Runtime. A real Chat request returned `40`, the former 120-versus-256/144
  error did not recur, and Prefill/Token Gen metrics were non-zero.
- Targeted release-file whitespace checks passed. The repository-wide check
  still reports one unrelated pre-existing trailing-space finding in
  `experiments/dsv41_reference/prepare_full_expert_store.py`.
- The production Package passed local Contract inspection, Publisher Ed25519
  verification, Publisher fingerprint matching, and exact embedded-DMG digest
  verification before Cloud submission.
- The exact production artifact was installed into a clean temporary instance
  with the published Qwen3.6 0.3.4 Package. Runtime 1.7.8 resolved from digest
  `sha256:0e2f7098f35ac5786ba01920fc066f4600c9e585dcd53307e5b54cd4522711d6`,
  the model dependency lock pointed to that exact digest, and the managed
  Worker reached `running`.

## Apple and Publisher receipt

- Source commit: `8ff6faf966d56ae92d21bf2d36d9512da5745784`
- Developer ID: `Developer ID Application: Avdpro Pang (84XL5V265N)`
- Apple notarization submission: `54b2c19c-45d8-4648-a550-270a1b815feb`
- Apple result: `Accepted`
- Stapler validation: passed
- Gatekeeper: `accepted`, source `Notarized Developer ID`
- Stapled DMG SHA-256:
  `c46b858d01dfe3acaaab7f7b9ebc23af163f09ce8e880fbbfa4ff302d7c8ed7c`
- Stapled DMG bytes: 376,912,775
- Publisher: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Public-key fingerprint:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

The existing production Publisher key was used only after its public metadata
fingerprint exactly matched the active Cloud key. No private key was printed,
exported, or written to this receipt.

## Production publication

- Package: `ai2apps/runtime-omlx` 1.7.8
- Artifact SHA-256:
  `0e2f7098f35ac5786ba01920fc066f4600c9e585dcd53307e5b54cd4522711d6`
- Artifact bytes: 374,705,308
- Manifest SHA-256:
  `9943b220e258372f67b9bdbbff3452f1a7d4a3e0ff71f24d44de71d5df478507`
- Submission: `319cad86-d84d-4992-a16a-8a0bb53dee77`
- Review: `142b69bf-e443-4f44-b986-fbd267e0d588`
- Repository metadata version: 180
- Anonymous readback: `artifactExactBytes: true`, `envelopeExactJson: true`

The user-authorized current Dev Cookie was accessed only through the live
authenticated Shell BiDi path and remained process-local. No Cookie SQLite
database was read or copied. That authorization expired immediately after
publication; anonymous verification did not use it.

## External distribution mirrors

The identical production artifact has been mirrored without repacking or
resigning. Both public origins report 374,705,308 bytes and SHA-256
`0e2f7098f35ac5786ba01920fc066f4600c9e585dcd53307e5b54cd4522711d6`.
Anonymous full downloads matched the local artifact exactly. Four sampled
ranges covered the first 4 KiB, a 16 KiB middle span, the final 4 KiB, and the
last byte.

### GitHub

- Immutable tag: `package-runtime-omlx-v1.7.8`
- Release ID: `392208455`
- Asset ID: `575453344`
- Source ID: `src_7d273abf-119c-44df-afe9-5af509c82e69`
- Validation ID: `val_a3b7fb7e-7bd7-4dda-ba6e-ecdc6d46d81c`
- Validation digest:
  `109a2e08b68b7e85ebafea1b1033613fd9833ac2f4b93909aed2a1276d1327b0`
- Range mode: standard HTTP 206
- Public URL:
  `https://github.com/Avdpro/ai2apps/releases/download/package-runtime-omlx-v1.7.8/ai2apps-runtime-omlx-1.7.8-production.ai2service`

### ModelScope

- Immutable revision: `9a6411755593810876673cd594e085c169048f26`
- Source ID: `src_9a0c8006-02a1-4072-89b7-ac7dd2ba130b`
- Validation ID: `val_e786c302-ce52-4fca-a9cf-3d6a56147db3`
- Validation digest:
  `60e6528cba69ce990a20aef3e26e39e1ba4320aa488613ef385c320c26de1010`
- Range mode: accepted HTTP 200 with exact `Content-Range`
- Public URL:
  `https://modelscope.cn/models/ai2apps/desktop-releases/resolve/9a6411755593810876673cd594e085c169048f26/ai2apps-runtime-omlx-1.7.8-production.ai2service`

Cloud validated the full artifact digest and size, all 45 8-MiB pieces, and 48
Range responses per external source. Both sources are active alongside the
permanent Cloud source. The final Repository metadata version is 182 and the
signed Snapshot digest is
`ab0756465380540977ee446ad9cdb7aae7fb3ecdb1e7b2030572d0cacffe78d8`.
The common piece-manifest digest is
`b45aca5cdaf18da2110fc253115a7c868a30160dbcd6793539590db29a92b0b0`.

An anonymous Registry readback verified metadata version 182, the exact local
artifact bytes, and the exact Publisher envelope JSON. The newly authorized
Dev Cookie was accessed only through the live authenticated Shell BiDi path
for these source-management operations; no Cookie database was read or copied,
and that authorization expired immediately after the final readback.
