# AI2Apps oMLX Runtime 1.7.4 DeepSeek V4 auto-tier release

Date: 2026-09-19 (Asia/Shanghai)

## Problem and result

The installed DeepSeek V4 Flash SSD checkpoint uses the current
`ai2apps-ssd-checkpoint` layout. Runtime 1.7.3 only rebuilt the full-model
memory estimate for the older `ai2apps-backbone-expert-store` layout. It
therefore compared the 32.7 GiB Lean resident bank with the 12.2 GiB backbone
instead of the 156 GiB logical full model and rejected every automatic tier.

Runtime 1.7.4 recognizes both immutable SSD layout identifiers. On the current
128 GiB App-Dev device, the installed 149 GiB checkpoint now resolves all three
tiers as valid and recommends Optimal Top60:

- Lean Top20: 32.7 GiB estimated resident memory;
- Compact Top40: 43.1 GiB;
- Optimal Top60: 53.6 GiB;
- logical full model: 156 GiB;
- system/KV reserve: 26 GiB.

The Full direct-engine path also injects all 256 experts for the new SSD layout.
Physical-memory detection adds a POSIX page-count fallback so a restricted App
process that cannot spawn `sysctl`, and does not carry MLX in its control-plane
environment, does not silently fall back to 8 GiB.

No model Package or checkpoint byte changes are required.

## Frozen release source

The candidate source at `artifacts/runtime-1.7.4/source/` is copied from the
published Runtime 1.7.3 frozen source. Only these files differ:

- `omlx/model_discovery.py`;
- `omlx/engine_pool.py`;
- `omlx/utils/hardware.py`.

Developer ID internal DMG:

- path: `artifacts/runtime-1.7.4/AI2Apps-oMLX-Runtime-1.7.4-internal.dmg`;
- bytes: 376,767,222;
- SHA-256: `581ad359a7c107decc7f3ba6deb20d922c086ec3e02cf1118f8bcef5e579a7ed`;
- Team ID: `84XL5V265N`;
- DMG integrity: passed.

## Validation

- 23 memory-profile and hardware tests passed;
- 7 DeepSeek Worker/installer tests passed;
- 2 SSD Full external-expert engine-pool cases passed;
- 24 Runtime Package contract and builder tests passed;
- 10 GLM-5.3, Qwen3.8 Flash Next, and Ornith Package policy tests passed;
- frozen-source offline probe against the installed checkpoint detected
  128 GiB and recommended Optimal Top60.

Before the published Runtime is available, App-Dev was pinned to the same
`optimal` tier result and Local was restarted. A real Chat request against the
installed `Avdpro/DeepSeek-V4-Flash-SSD` checkpoint completed successfully and
returned `40` for `20+20`; the prior `No Cache-MoE memory tier fits this device`
failure did not recur. The cold request reported 51.7 seconds total, about
3.0 tok/s Prefill and 5.1 tok/s Decode. This validates the selected tier and
checkpoint execution path; the pin must return to `auto` after Runtime 1.7.4 is
installed so the repaired automatic policy remains under test.

## Other SSD Cached-MoE models

The same-layout failure is limited to DeepSeek V4-family models that call
`deepseek_cache_moe_memory_profile`; this includes the 4-bit and 2-bit V4
Packages, and the 1.7.4 layout fix covers both. DeepSeek V4.1 uses its dedicated
fixed Standard engine and does not call this profile.

GLM-5.3 and Qwen3.8 Flash Next also do not call the DeepSeek size estimator, so
their SSD backbone cannot trigger this exact failure. Their 0.1.2 Worker
adapters nevertheless mapped `auto` to fixed Balanced tiers. The accompanying
0.1.3 Package releases replace that behavior with physical-memory-aware
Balanced-to-Lean selection and correct the published minimum-memory profiles.

Qwen3.6 uses a separate expert-record calculation that already treats a small
SSD backbone as the backbone and reconstructs the full expert size. It is not
affected by the layout-name bug. Runtime 1.7.4's POSIX memory fallback also
strengthens its real automatic tier selection when `sysctl` is unavailable.
Ornith resolves the untouched `cached/auto` pair to its validated full mode on
machines with at least 32 GiB and likewise does not use the DeepSeek profile.

## Release receipt

Apple accepted notarization submission
`19430ca1-eaed-494c-87e9-8f0ada32c06c`. The stapled DMG passed Stapler and
Gatekeeper verification:

- path: `artifacts/runtime-1.7.4/AI2Apps-oMLX-Runtime-1.7.4.dmg`;
- bytes: 376,778,908;
- SHA-256: `2f745719fa9c58808c6f1a1e496802f35c6255fb749bf52ca5a5ba42525dd0e5`.

The original Publisher signed the production Runtime Package:

- path: `packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.7.4-production.ai2service`;
- bytes: 374,581,509;
- SHA-256: `20efe8fb3c97c6bef997918028940da253090a76029b8cbc2b78ffc7ddb4bd4c`;
- Cloud submission: `3aca5beb-2c5e-4c33-9345-ec27173c212d`;
- review: `b97043f1-1aa2-4971-860b-1e12dd831f0c`;
- published Repository metadata version: 163.

The identical Package was anonymously downloaded in full from both immutable
external origins. Size and SHA-256 matched the signed local artifact. GitHub
returned standard HTTP 206 for the sampled range. ModelScope returned the
strictly accepted HTTP 200 plus an exact `Content-Range`; its sampled bytes
matched GitHub byte for byte. The GitHub source passed Cloud full-file,
48-piece, and Range validation and was activated as
`src_e89f926a-f465-41ea-82ac-ada4743c5cf9`, producing Repository metadata 166
and Snapshot
`fee0a791efbec7b47831538620debd9b32b31f7962e9b516d13aa593c1d59988`.
The ModelScope source passed the same full-file and 48-piece checks under the
restricted `http-200-content-range` compatibility and was activated as
`src_5a8dc563-7939-4fd2-865c-897254024c31`. The final three-source Repository
metadata version is 167 and its Snapshot digest is
`a02cd12584a4f02fe2b8fa5d507584c8034359df9a0dd00c31501d07eaed586a`.

The immutable external URLs are:

- GitHub tag `package-runtime-omlx-v1.7.4`;
- ModelScope revision `dc48b9b4c2e44135ad887986a5e60a827ae31fe6`.

The earlier nested ModelScope object is byte-identical but Cloud source
registration does not accept that path form. A root-level object was therefore
created by ModelScope blob reuse, matching the already proven Runtime source
shape. The final anonymous Registry verification matched the local artifact
and Publisher envelope exactly with Cloud, GitHub, and ModelScope all active.

## Related model Package correction

GLM-5.3 Flash and Qwen3.8 Flash Next now resolve `auto` from physical memory
instead of treating it as an unconditional Balanced request. Both preserve the
established Balanced default on the 128 GiB reference Mac, downgrade only to
their validated Lean tier when needed, retain explicit Qwen Performance, and
reject devices below the Lean floor after reserving the larger of 8 GiB or 20%
for the system and KV cache. Their minimum published memory profiles are now
72 GiB for GLM and 64 GiB for Qwen Next.

The unchanged immutable SSD checkpoint distributions are reused. GLM 0.1.3
and Qwen Next 0.1.3 require Runtime 1.7.4 and were published from their signed,
external-weight-free archives. Their Cloud submissions are respectively
`44e3091a-638c-459b-851e-10ef9f2b3764` and
`ac46844c-34dc-4598-84f1-22bb37c6eab3`; Repository metadata advanced to 165.
The focused package, contract, discovery, publication, and Runtime-builder
suites passed 112 tests in total. A real-host resolver probe selected Balanced
for both models on 128 GiB.
