# AI2Apps oMLX Runtime 1.7.5 reasoning contract release

Date: 2026-09-19 (Asia/Shanghai)

Status: published and anonymously verified

## Scope

Runtime 1.7.5 makes the signed `ai2apps.reasoning/v1` declaration authoritative for
oMLX chat models. Required-reasoning models cannot be disabled by a stale client
setting; optional models receive their declared default; streaming, non-streaming,
Chat Completions and Responses all separate think-tag reasoning from visible output.
DeepSeek V4.1 now maps `enable_thinking` and `reasoning_effort` to its native engine
mode instead of hard-coding chat mode.

No checkpoint bytes, revisions, distribution IDs or weight layouts changed in this
release.

## Apple and Publisher verification

- Developer ID: `Developer ID Application: Avdpro Pang (84XL5V265N)`
- Apple notarization submission: `5efb941a-0d49-47b7-ae1d-741338f01914`
- Apple result: `Accepted`
- Stapler validation: passed
- Gatekeeper: `accepted`, source `Notarized Developer ID`
- Notarized inner DMG SHA-256:
  `ef90092944baef2660c10d8292d9b15c9c65d51273e6abd59871c614203a00f1`
- Publisher: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Public-key fingerprint:
  `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

The existing SecretBackend record and namespace were selected by exact public
fingerprint. The private key was loaded only in the standard builders and was not
printed or exported. The authorized Dev Cookie was read through the authenticated
live Shell BiDi path; no browser SQLite Cookie database was read or copied.

## Published artifacts

| Package | Version | SHA-256 | Bytes | Submission |
| --- | --- | --- | ---: | --- |
| `ai2apps/runtime-omlx` | 1.7.5 | `b7d5b2a7a877814b125e5f12dd0fa007db2edda2fea01c30d051bea61f5bbdf7` | 373254507 | `135762af-0a99-423d-9521-db9f235f2506` |
| `ai2apps/model-deepseek-v4-flash` | 0.3.4 | `138bc1d3a9c9c73140b998d4a077ea231c13468d4990a760b5896b0ae65d5699` | 53367 | `1306e450-d88f-4df8-b517-854f70025400` |
| `ai2apps/model-ornith15-35b-a3b-4bit-vision` | 0.1.4 | `c3c904cb4e328572910fc7d2116307e121c317b13a4a8197c632509d462d160d` | 184334 | `84482223-2b71-4579-930d-1626e6435c7f` |
| `ai2apps/model-deepseek-v4-flash-2bit` | 0.3.5 | `d9593b73da8e10a3d41fe9de9b1ba9bcdac2d1a205eed821e906de1298767534` | 52326 | `2e76b6fd-e281-47b8-ad54-f2751843f920` |
| `ai2apps/model-deepseek-v41-flash` | 0.1.1 | `689129714673c8a666cb35f0b22947df66d21801ad0a4ea9841ee1d169b04720` | 10793 | `d296ac6f-5757-43e8-bef4-2e682d1707cc` |
| `ai2apps/model-glm5-3-flash-4bit-mtp` | 0.1.4 | `40fe982108dfdc1aa99f5ad710818d5020e9f66124782ee8fbc856768dacea8e` | 129836 | `478a36ae-e36b-4d03-aa2e-c6a811401e03` |
| `ai2apps/model-qwen36-35b` | 0.3.4 | `ba2a9752c8167cc6605469b09035903da736be75db385282319008eaad79c6ac` | 179817 | `e0197e03-c785-4079-a6a5-ef41d6eee1c7` |
| `ai2apps/model-qwen38` | 0.3.3 | `c6dfbf3381b4e7ca864fe225070bc3f45cee29c0af2e5dde36f30d365da49a8e` | 14812 | `1bad9625-965d-4e68-a0d7-aee4bdb01e69` |
| `ai2apps/model-qwen38-flash-next-4bit` | 0.1.4 | `2f4803f067ba357325c05953fa8e4ef16974084efe1732cccb0008fc53f1159f` | 479060 | `69b6550f-a1b0-4e7b-a2aa-d16d6824e97f` |

Runtime was published and anonymously verified before any dependent model Package
was submitted. Final Registry metadata version is `176`. Anonymous public readback
reported `artifactExactBytes: true` and `envelopeExactJson: true` for all nine
artifacts.

The first model submission attempt was rejected during schema validation before a
submission was created because production Cloud still rejects the optional outer
`modelInstall` projection. Final model artifacts use the standard
`--omit-model-install-catalog` compatibility form. The authoritative Package source
and signed `service.yaml` remain unchanged; the client legacy projection is bounded
through exactly the versions in this release.

## Verification

- Runtime/reasoning focused suite: 112 passed.
- Cloud-compatibility and Package contract suite: 47 passed.
- Package-specific DeepSeek V4, Ornith, DeepSeek V4.1, GLM and Qwen Flash Next
  suites passed; all nine final artifacts independently verified against the
  registered public key.
- Archive audit confirmed that model Packages contain no `.safetensors` or `.gguf`
  weights; DeepSeek V4 2-bit contains its package-owned `chat_template.jinja`.
- An isolated managed install of the exact final Runtime 1.7.5 and DeepSeek V4
  0.3.4 artifacts succeeded. The Worker reached `running`, and its dependency lock
  resolved Runtime version 1.7.5 with the exact published digest.

App-Dev/Test bundle rebuilding and interactive multi-model UI inference are separate
client rollout checks; they were not required to alter or republish these immutable
Registry artifacts.

## Post-release GLM scope-pack hotfix

App-Dev subsequently exposed a packaging defect in GLM 0.1.4: its Cache-MoE recipe
declared `engine.scope_asset` without the mandatory Package-relative
`engine.scope_pack`. This did not require a Runtime or checkpoint change. Immutable
GLM Package 0.1.5 adds the signed scope pack and was published as submission
`bee627d6-0aa4-423c-881c-33dbf8689fa7`; Registry metadata advanced to `177`.
Anonymous public readback matched both artifact bytes and signed envelope exactly.
Chat ACPF now requires `>=0.1.5,<1.0.0`, so a retry upgrades the defective 0.1.4
instead of accepting it as satisfied. See
`docs/ai2apps-glm5-3-scope-pack-hotfix-0.1.5.md` for the complete receipt.

## Post-release DeepSeek V4.1 streaming defect

App-Dev later reproduced a DeepSeek V4.1-only stream decoder defect that could
duplicate already separated reasoning into visible content and emit U+FFFD. The
source correction preserves special think-boundary tokens and makes tokenizer
deltas append-only. This correction is intentionally **not** attributed to the
immutable Runtime 1.7.5 artifact; it requires a subsequent Runtime release. The
App-Dev proof and release boundary are recorded in
`docs/ai2apps-deepseek-v41-thinking-stream-fix-2026-09-19.md`.
