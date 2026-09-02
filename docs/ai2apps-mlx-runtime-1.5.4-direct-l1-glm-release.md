# AI2Apps oMLX Runtime 1.5.4 Direct-L1 and GLM release receipt

Release date: 2026-08-28

## Release identity

- Source commit: `66736ccaed462e6f366b03d15c10aec5b43213ff`
- Branch: `experiment/moe-cache`
- Package ID: `ai2apps/runtime-omlx`
- Version: `1.5.4`
- Runtime Python: CPython 3.11.10
- MLX: 0.32.0
- Native wheel: `ai2apps-0.1.0-cp311-cp311-macosx_15_0_arm64.whl`
- Native wheel SHA-256: `65bc160d2a8bab3eaf886caac608fa0893295a6001eb88237ff6018494cc69f5`
- Package artifact: `packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.5.4-production.ai2service`
- Package SHA-256: `849305a7b4b370cc7e72fc689f76aed36df292832f9893f9fbaf55342fc809fb`
- Package size: `447960989` bytes
- Publisher ID: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher key fingerprint SHA-256: `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

The source tree contained the reviewed Direct-L1 and GLM development changes.
The immutable artifact and native wheel digests above identify the release
inputs independently of the working-tree state.

## Native and correctness gates

- The CPython 3.11 staging Runtime imported the MLX 0.32.0 native extension and
  exposed `preadv_fused_experts`, `glm_moe_weighted_sum`, and the Direct-L1 ABI.
- Selected Direct-L1, GLM loader, dynamic L1/runtime, and session tests:
  `29 passed`.
- GLM Boost, expert-store, Scope, VLM engine, and vision-feature-cache tests:
  `155 passed`.
- Real DSV4F expert-major store: two nonmatching experts loaded into two slots,
  all six segments and all 12 comparisons byte-exact; `26,738,688` bytes.
- Real GLM fused-v2 store: the same nonmatching-slot test was byte-exact for all
  six segments and all 12 comparisons; `28,311,552` bytes.
- The old loader remains available for A/B and rollback.

## DeepSeek V4F performance gates

All A/B runs used identical prompts, generated-token budgets, and strict cache
trajectories.

| Gate | Legacy | Direct | Result |
|---|---:|---:|---|
| Decode, 25 prompt / 64 generated | 8.6 TPS | 9.7 TPS | +12.8%; loader 5.702 s to 3.501 s |
| 128-token Prefill | 11 TPS | 18 TPS | +63.6%; TTFT 11.731 s to 7.077 s |
| 4K Prefill | 187 TPS | 228 TPS | +21.9%; TTFT 21.851 s to 17.935 s |
| 10K Prefill | 226 TPS | 278 TPS | +23.0%; TTFT 44.157 s to 35.956 s |

The final isolated 4K run was used after explicitly identifying thermal/load
drift in earlier repetitions. Direct and legacy cache event counts remained
identical. The 10K Direct result also exceeded the previously accepted 266 TPS
checkpoint.

## GLM 5.3 Flash Q4 gates

The 12K-character text run produced 3,025 prompt tokens with Top80 + Hot16 and
one L1 promotion per layer/token. Peak memory was `62.645 GiB` in all modes.

| Mode | Routing | Prefill | Decode | Misses avoided |
|---|---|---:|---:|---:|
| Natural | exact/default | 95.112 TPS | 5.087 TPS | 0 |
| Turbo | Top5 | 101.221 TPS | 6.140 TPS | 77,471 |
| Blast | Top3 | 106.213 TPS | 7.216 TPS | 129,807 |

Natural remains the default. Turbo and Blast are request/session-selectable and
apply to both Prefill and Decode.

The real three-turn vision session used `IMG_4305.PNG` followed by
`IMG_4306.PNG` with Top64 + Hot16 (`16` main slots reserved for vision):

| Turn | Prompt tokens | Vision cache | Peak | Reclaimed active |
|---|---:|---|---:|---:|
| Read payment image | 814 | saved | 52.173 GiB | 51.970 GiB |
| Text-only historical follow-up | 898 | old image hit | 60.147 GiB | 51.970 GiB |
| Append comics image | 1,753 | old hit, new saved | 61.939 GiB | 51.976 GiB |

Semantic checks passed: the model read both transactions, recalled HSBC/card
tail `8657` and the green status label without a re-upload, then identified the
comics application and search term `狗咬狗`. The VLM batch generator was released
after every turn. Machine-readable results are in
`artifacts/runtime-1.5.4-gates/glm5-vision-multiturn.json`.

## Apple release validation

- Developer ID: `Developer ID Application: Avdpro Pang (84XL5V265N)`
- Team ID: `84XL5V265N`
- Notary submission ID: `2a800225-cf60-4d00-8313-18dde6cd3937`
- Notary status: `Accepted`
- Stapler: staple and validate passed
- Gatekeeper: `accepted`, source `Notarized Developer ID`
- Stapled DMG SHA-256: `85a134f5cc428539a68f9546300aa7e2284fd6cf33a3c7a2950a7a06924e68a1`

## Cloud publication and public read-back

- Submission ID: `7811e664-2c30-4b20-b817-8a2bf796bf64`
- Review ID: `9bca64dc-791d-4488-b4c7-e7bcfedd77e4`
- Review decision: `approved`
- Release status: `published`
- Published at: `2026-08-28T07:56:25.434Z`
- Repository metadata version returned by publication: `87`

Anonymous public Registry read-back, without a browser Cookie, confirmed:

- catalog latest version: `1.5.4`;
- release status: `published`;
- public artifact SHA-256: `849305a7b4b370cc7e72fc689f76aed36df292832f9893f9fbaf55342fc809fb`;
- public artifact size: `447960989` bytes;
- compatibility: AI2Apps `>=0.1.0 <2.0.0`, darwin/arm64, minimum macOS `26.2`.

The one-release browser Cookie authorization expired immediately after Cloud
publication and was not used for public Registry verification.
