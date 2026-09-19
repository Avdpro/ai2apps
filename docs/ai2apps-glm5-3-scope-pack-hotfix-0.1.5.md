# GLM-5.3 Flash 4-bit MTP 0.1.5 scope-pack hotfix

Date: 2026-09-19 (Asia/Shanghai)

Status: published and anonymously verified

## Incident

App-Dev ACPF installation of published GLM 0.1.4 stopped at 45% before checkpoint
download with:

```text
Preparation engine.scope_pack must be Package-relative
```

The 0.1.4 `service.yaml` declared the Package-relative `engine.scope_asset` but
omitted the mandatory paired `engine.scope_pack`. Host validation therefore rejected
the Cache-MoE recipe before it could resolve either path into the installed Package.
Runtime 1.7.5 and the immutable GLM checkpoint distribution were not at fault.

## Fix

- Bumped the immutable Package version to `0.1.5`; 0.1.4 is not overwritten.
- Added signed `assets/scope-pack.json`, binding the existing profile SHA-256,
  public model identity, pinned source revision, memory tiers, Hot16 and vision reserve.
- Added `engine.scope_pack` as a Package-relative service declaration.
- Extended the bounded client discovery/install compatibility map through 0.1.5.
- Raised the Chat ACPF profile minimum to `>=0.1.5,<1.0.0`, so Retry upgrades an
  already-installed broken 0.1.4 instead of treating it as satisfied.
- Added a Host-level regression that runs `installed_model_preparation_recipes()`
  against the GLM Package record and verifies both resolved files exist.
- Strengthened the Package development manual so every Cache-MoE release must test
  the unpacked Host recipe, not only its YAML shape.

## Candidate verification

- Focused Package/Host/contract/discovery/runtime tests: 91 passed.
- Exact signed candidate:
  `artifacts/runtime-1.7.5/hotfix/ai2apps-model-glm5-3-flash-4bit-mtp-0.1.5.ai2service`
- SHA-256:
  `dfc5761347bd1e7fc8a41a57a723460656c63694696821326a24ce64f9b1fdbd`
- Size: 130941 bytes.
- Isolated install with exact published Runtime 1.7.5 succeeded; the GLM 0.1.5
  managed Worker reached `running`, and its dependency lock matched Runtime 1.7.5
  digest `b7d5b2a7a877814b125e5f12dd0fa007db2edda2fea01c30d051bea61f5bbdf7`.

## Production publication

- Published Package: `ai2apps/model-glm5-3-flash-4bit-mtp 0.1.5`.
- Submission: `bee627d6-0aa4-423c-881c-33dbf8689fa7` (`published`).
- Registry metadata version: `177`.
- Anonymous public readback matched the signed local artifact byte-for-byte and
  matched its signed envelope exactly (`artifactExactBytes: true`,
  `envelopeExactJson: true`).
- Publication used the user's exact-version Cookie authorization through the
  authenticated live Dev Shell BiDi path. No Cookie SQLite database was read or
  copied, and the authorization expired when this publication completed.

## App-Dev rollout check

- Restarted only the fixed `app-dev` Local process; new boot ID:
  `7a5c76eb-a870-4d31-ae55-2bacd7a01e18`.
- The live Shell resumed at `127.0.0.1:55320` and loaded the current Chat source.
- The Chat local-model wizard lists GLM-5.3 Flash 4-bit MTP, while its profile now
  requires `>=0.1.5,<1.0.0`. The verification stopped before confirmation so it did
  not start the approximately 181 GB checkpoint download.
