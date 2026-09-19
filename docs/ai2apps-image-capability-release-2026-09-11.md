# Image capability Package candidates — 2026-09-11

Status: all four Packages published on 2026-09-12 via the standard publication script.

## Publication receipt — 2026-09-12

The user clarified that there are no production users yet and explicitly removed
production Desktop rollout as a prerequisite. These releases target the current
development client with the new operation validator and bounded installation maps;
the older-client limitations below remain documented, not fixed by publication.
No Desktop or audio/video release was performed.

| Family | Version | Submission | Repository metadata version |
| --- | --- | --- | --- |
| z-image | 0.1.3 | ae980758-0a6b-424b-8bb3-6d6386a79192 | 131 |
| ideogram4 | 0.1.2 | 082132b6-c6fd-4501-ba2e-63fcdfb4733d | 132 |
| qwen-image | 0.1.2 | a9e1bea0-280e-46f7-a6d7-5a94034ff53f | 133 |
| flux2-klein | 0.1.4 | 6e719f34-77e4-48bb-bde1-efc4bbe75dee | 134 |

All four standard-script publish responses and a subsequent `--list-only`
query confirm `published` with the exact SHA-256 values below. Publication used
only the authorized current Dev Profile Cookie after user administrator step-up;
no credentials were exported. Small archives use Cloud distribution; checkpoint
weights and their existing distributions are unchanged. Previous installation
and readiness evidence below remains applicable to the identical signed bytes.
No fresh real-image inference is claimed by this release receipt.

Anonymous public Registry catalog and full-artifact download checks passed for
all four releases: each downloaded archive is byte-for-byte identical to its
tested local signed artifact, with matching SHA-256 and length. Published times
(UTC): Z-Image 08:08:51.664, Ideogram 08:09:22.064, Qwen 08:09:24.826,
FLUX 08:10:04.901 on 2026-09-12. Live Discover installation and fresh inference
were not rerun in this publication-only scope.

The production gates and preflight notes below are historical context, superseded
as release blockers by the user's explicit development-stage scope decision.
Source baseline: `11b5b9ac537e42b1029d1f0148bbbe6a33307f8e` plus scoped uncommitted changes in the shared worktree.

## Signed artifacts

Each archive is in `packages/ai2apps-model-<family>-mlx/dist/ai2apps-model-<family>-mlx-<version>-cloud-compatible.ai2service`, with adjacent `.envelope.json`.

| Family | Version | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| z-image | 0.1.3 | 17383 | 4c25e6f036513a4ff0f5090a5ebb73b8bf4c88eb82845fb1aef4a4cb9bde47f3 |
| ideogram4 | 0.1.2 | 3803615 | ef22b76dbf29b66bdbe64ab3deaf6ddbae8d881fff00ba8e3806e68c408be4fc |
| qwen-image | 0.1.2 | 19589 | 8f03c0d3c56ac09153c9ebe6b9624ab4465b03b08d08ec80054fc2f6ce487e4e |
| flux2-klein | 0.1.4 | 19493 | fbccb9780a5ac5d33c425364fed6d4c52c1184a3618f9772d9db4f65804050f7 |

Publisher: `229d6350-cd0e-408a-9905-41367385ae5c`.
Key: `f54e5b3f-375b-4fb0-a253-3e230f567327`, active in Cloud.
Public fingerprint: `4d0414816987a3c418897c8a8b7d7e2bad85acebb2534016298f76ba9a8d5102`, matched against the exact existing Secret record metadata before signing.
The user explicitly authorized this key's use through the standard builder. No private key was exported, printed, or stored in an artifact. Cloud Publisher verification used the authorized current App-Dev Cookie, not Keychain login credentials.

## Contract changes

- Turbo and Ideogram expose generation only and reject editing before model loading.
- Qwen 2512 exposes generation only; Edit 2511 exposes editing only with 1–3 reference images.
- Flux exposes generation and editing with 1–4 reference images.
- Host and Imagine Studio enforce operation/reference limits; ACPF separates generation/editing.
- Checkpoint revisions and distribution IDs remain unchanged; no new weights were published.
- Compatibility builder now checks the explicit version-bounded installation map, independently of the old discovery metadata map. It validates the fallback plan against actual weighted Service models. Unknown versions still fail closed.

## Verification

Final regression: 343 passed in 10.67 seconds (image contracts, Package Contract, Discover, model discovery/providers, ACPF, Imagine Studio, and all four Package tests). All four exact signed archives passed isolated managed installation smoke with Runtime 1.6.2 and reached Worker `running`; each smoke shut down its test runtime normally. No live user instance was changed.

Final signed artifacts are tested using `scripts/smoke_inference_runtime_install.py`, isolated paths under `/private/tmp/image-capability-*-smoke`, the published Runtime 1.6.2 archive and both existing public keys. Runtime digest: `040bdf2e5bc32fed203bbc695d5bd34ebd5e514a70a7b38dd8a97f0cdc28943a`.
This smoke proves archive signature validation, installation, dependency lock and Managed Worker readiness. It does NOT claim new real-image inference, complete checkpoint download/resume or live Discover acceptance.

## Production gates

Scope clarification after Suite 0.1.1 mount acceptance: the user explicitly deferred
real audio/video processing and other Suite follow-up verification. Do not extend
this image-model publication into that work. Existing Suite mount evidence remains
valid; deferred media tests are not represented as passes. The image-specific
Desktop compatibility gates below remain necessary and are not waived.

1. Older Host validators require `image_generation` first and reject Qwen editing-only declarations. Release a compatible Desktop before distributing Qwen, or establish a reliable signed minimum-client-version gate. Do not restore a false generation claim.
2. Candidates use the runbook's `--omit-model-install-catalog` for the existing Cloud schema. Their exact new-version installation maps must ship in the Desktop first. The current common `>=0.1.0` constraint cannot distinguish old/new Host builds.
3. Alternatively Cloud can accept signed `modelInstall` (requirements below), but that alone does not fix the Qwen Host validator gate.
4. After compatible client availability: refresh Publisher/submission state with the same standard script, publish exact verified artifacts, and finish public Registry/Discover and real inference acceptance. Do not blindly resubmit after partial failure.

## Cloud handoff (requirements only; no Cloud code changed)

### Publication preflight recheck

The standard publication script successfully queried the current authorized Dev
browser session. The original Publisher and Image signing key remain active, and
the public-key fingerprint still matches the signed candidate context. The latest
20 submissions contain no submission for these four candidate versions; no new
submission was created during this recheck. Installation-session-only querying
returned `an active user session is required`; no alternative credentials were
probed.

An anonymous read of the production stable manifest still reports Desktop
`0.1.0`, Build `2249`. Thus the directly required client compatibility rollout
has not been established. Current Host compatibility checks use the fixed
contract version `0.1.0`, not Desktop build numbers, so changing a minimum-build
label cannot safely gate these candidates. Publication remains blocked on the
client prerequisite above, not on Cookie access or deferred media testing.

Accept and preserve the optional signed `modelInstall` projection in Package Contract v1, including serviceKey and weighted model IDs, in submission, review, immutable manifest and signed Registry responses. Validate the documented structure, retain existing older releases, and do not rewrite Publisher-signed bytes. Add acceptance tests for these image packages and unknown/invalid model entries. Return production schema/version evidence before clients stop using the compatibility omission. Desktop editing-only support is a separate dependency.
