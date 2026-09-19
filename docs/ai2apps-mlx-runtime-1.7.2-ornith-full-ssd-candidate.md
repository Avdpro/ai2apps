# AI2Apps oMLX Runtime 1.7.2 / Ornith 0.1.3 release receipt

Date: 2026-09-18 (Asia/Shanghai)

## Result

Runtime 1.7.2 and Ornith 0.1.3 are published. Ornith SSD Full execution now
loads all 40 MoE layers from the external expert store instead of rejecting the
SSD backbone for its intentionally omitted 120 stacked expert parameters.

Ornith keeps the external Qwen3.6 policy enabled in Full mode. Runtime 1.7.2
injects all 256 experts in canonical global expert-ID order and no longer
requires a cache-tier Scope profile to contain a Top-256 ranking. The same
Runtime removes the invalid zero tail-capacity argument from the text Qwen3.6
Full path. Cached and tiered execution behavior is unchanged.

The Ornith checkpoint and immutable Checkpoint Distribution did not change.

## Published artifacts

### Runtime 1.7.2

- Registry submission: `eb7521f1-8550-4dc8-8f1c-19d33145db13`
- Review: `50aafd39-0092-4a85-89dd-347847b6cc62`
- Registry publication metadata version: 158
- Apple notarization submission: `745fe730-0568-4a9d-ab34-043ddb577833`
- Apple status: Accepted; staple, stapler validation, Gatekeeper and
  deep/strict codesign passed
- Final DMG: `artifacts/runtime-1.7.2/AI2Apps-oMLX-Runtime-1.7.2.dmg`
- DMG bytes: 377,730,894
- DMG SHA-256:
  `b69e05d352399ba588815759b4082ba77e43419f548756110ec596ef76450a62`
- Signed Package:
  `packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.7.2-production.ai2service`
- Package bytes: 375,527,678
- Package SHA-256:
  `2ec01b8d5bd37b362d7b95fa98a7253d3f2251b0495d0c0599ac0be88240f501`
- Publisher envelope SHA-256:
  `506be78872438161c726081dbd83f5decbeccb6c78c0c364f0b5e37c45eb8cc1`
- Publisher key ID: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher key fingerprint:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

### Ornith 0.1.3

- Registry submission: `488bdda4-dcbd-4207-9463-48ec2e8dd134`
- Review: `1079543b-f1b3-42b1-89cb-2c8a4c5a2e84`
- Registry publication metadata version: 159
- Signed Package:
  `packages/omlx-model-ornith15-35b-a3b-4bit-vision/dist/omlx-model-ornith15-35b-a3b-4bit-vision-0.1.3-production.ai2service`
- Package bytes: 184,248
- Package SHA-256:
  `c5e23d56f64f598c51490371a3887db9ded5bfda55c491ae9d3851fe3f423011`
- Publisher envelope SHA-256:
  `dce31d50e624dc05044c192a0877a3fe2744a4a3a08b28612ace2a852a8c5142`
- Archive audit: 12 entries and no checkpoint, expert-store or safetensors
  payloads

## Runtime distribution

The final Repository Snapshot is metadata version 161 with digest
`2189e264a8753742898def788511fc9c925d94995ee6f63f7d889a8d85bb99ee`.
Cloud, ModelScope and GitHub are all active.

### ModelScope

- Immutable revision: `12156b50ecf5fff1ef4236867edbd37577807b60`
- Source ID: `src_63cdcd38-363d-43a1-87b5-7b4ef5cb9629`
- Validation ID: `val_903272cd-bf78-4cac-911a-18af2f035df5`
- Validation digest:
  `686b56f3eb6f5f178def2ad432a9dc65e5b0a51ce3348326e35f0873308ea868`
- Range mode: strict `HTTP 200 + Content-Range`
- Cloud verified full SHA-256, size, piece manifest and 48 Range responses
- Public URL:
  `https://modelscope.cn/models/ai2apps/desktop-releases/resolve/12156b50ecf5fff1ef4236867edbd37577807b60/ai2apps-runtime-omlx-1.7.2-production.ai2service`

### GitHub

- Immutable tag: `package-runtime-omlx-v1.7.2`
- Release ID: 391231924
- Asset ID: 571875569
- Source ID: `src_89ba789e-edc3-4c1a-a42b-35794bfa755c`
- Validation ID: `val_50ad2d05-00af-4f2e-aa79-5fb48075b524`
- Validation digest:
  `76ee9e262bab0afa00932f5f7f8183705d53d108090af5347a18a31006e78435`
- Range mode: standard HTTP 206
- GitHub metadata digest, anonymous full download SHA-256, four sampled ranges,
  Cloud full SHA-256, size, piece manifest and 48 Range responses all passed
- Public URL:
  `https://github.com/Avdpro/ai2apps/releases/download/package-runtime-omlx-v1.7.2/ai2apps-runtime-omlx-1.7.2-production.ai2service`

Both external sources matched the published Package SHA-256 and the same Cloud
piece-manifest digest
`60c68c6499f10ce1fdcc2f30575b4da53bae81f28a7df5d49a70e8bbf14a1314`.

## Validation

- 46 focused Runtime, Qwen3.6, Ornith, Package Contract and adapter tests passed.
- 35 focused Package/discovery/legacy bounded-mapping tests passed after the
  exact Ornith 0.1.3 fallback boundary was advanced.
- A pre-publication isolated Worker used the published SSD checkpoint and
  completed a 30-token real Metal Full response ending in `40`.
- App-Dev installed the exact published Runtime 1.7.2 and Ornith 0.1.3
  artifacts. Discover showed matching local/cloud versions.
- The model installer reused the existing Ornith checkpoint and marked its
  checkpoint step complete without downloading it again.
- Installed Worker metadata records `default_execution_mode: full`, package
  digest `c5e23d56...`, Runtime 1.7.2, and the existing immutable checkpoint
  distribution.
- A fresh App-Dev Chat request `20+20` completed in about 29 seconds and
  returned `40`; the former 120-parameter load failure did not recur.

## Scope boundary

This release changes Runtime and the Ornith model Package. It does not require
a new Desktop release or a new Ornith checkpoint. The existing shared
checkpoint remains the authoritative immutable payload.
