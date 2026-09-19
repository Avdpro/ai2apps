# Build 2250 internal candidate — 2026-09-11

Status: signed internal App and DMG built; NOT published, NOT a production-ready release.

The user explicitly authorized a dirty-tree INTERNAL candidate after being informed of the 280 changed/untracked entries. This permission does not authorize stable rollout, publishing the four model candidates, broad committing of unrelated work, or declaring incomplete ledger items ready.

## Scope and source evidence

- Production remains 0.1.0 Build 2249, confirmed anonymously against stable.json; Build 2250 had no GitHub release at preflight.
- Use standard `build-release-app.sh`, arm64, cloud Runtime, `com.ai2apps.desktop`, `default`, standard icon, no Development source overlay. Build into the new releases directory only; do not replace or launch an existing production/App-Dev/Test App.
- Baseline commit is 11b5b9ac537e42b1029d1f0148bbbe6a33307f8e plus the authorized mixed worktree. The binary is NOT reproducible from the commit/tag alone.
- `apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.0-build2250/source-evidence-prebuild.json` records 1239 source file entries, tracked diff hash/stat, untracked status, and a disposition for each of the 65 ledger headings. Evidence SHA-256: 066dc2661eedbd830fdd7750ec9967867e32975bec49265bba5d19742e411058.
- Comparing actual local Build 2249 embedded source identified 239 differing ai2apps paths and 123 omlx paths. This is an internal mixed snapshot, not a claim that all differences are newly approved production features.
- All ledger sections are retained as INTERNAL TEST SCOPE only; all in_progress/blocked items stay blocked for production. Development-only features remain disabled in this candidate. Separately distributed model/Runtime/App Packages are not bundled or published by this Desktop build.
- Main validation target: NXR-IMAGE-CAPABILITY-SPLIT plus its existing Discover/ACPF/Studio dependencies (NXR-010/014/023/027/028/029/031/048/050 and NXR-ZIMAGE-BASE). No ready/included status promotion from this internal build.

## Verification and limitations

Swift 76/76 passed. The broad selected Local/Web/Package run collected 1343 cases: 1337 passed and 6 stale static UI assertions failed (418.35s). After aligning those assertions to existing product contracts, all affected modules passed: audio 14/14, extensions 25/25, media/voice Studio 7/7, Shell/shared Mini-App client 116/116. This is a full initial run plus targeted reruns, not a claim of a second full run. The assertions cover explicit ACPF selection handlers, Agents/Bench development status, compact Studio headers, and readiness-dependent setup controls; no corresponding feature implementation changed in this turn.

The packaged AceFox snapshot has both omni.ja files and AI2Apps Shell resources. Production-only native resource adoption remains subject to candidate verification; no Development overlay is enabled as a shortcut. The existing Developer ID identity was checked without exporting private material.

## Delivery boundary

Create a signed internal App/DMG and matching `not_stapled` metadata only after tests. No Apple notarization submission, GitHub/ModelScope upload, Cloud stable modification or model Package publication in this internal-candidate phase. Do not install into /Applications or migrate the default user data without a separate controlled acceptance step.

## Built artifacts and checks

Directory: `apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.0-build2250/`.

- App: `AI2Apps.app`, 707623113 bytes; Build 2250, arm64, `com.ai2apps.desktop`, `default`, cloud Runtime, hardened runtime, Developer ID team 84XL5V265N. No Development Bundle flag/source overlay.
- DMG: `AI2Apps-0.1.0-build2250-macos-arm64-internal.dmg`, 265023067 bytes; SHA-256 `fa312b389073dc30033f6fa0cb280c3fcdda73a573f377045c8ecdf16132b426`.
- Metadata: `AI2Apps-0.1.0-build2250-macos-arm64-internal.release.json`; `notarization.status=not_stapled`.
- App CDHash: `380a4d2cc6feb2113c37e2b77c931c6b46888e80`.
- Standard App verifier, deep strict signature verification, DMG signature/checksum and matching embedded App verification passed.
- Standard `verify-update-candidate.py --internal-candidate` reports eligible from 2249 to 2250. This is read-only eligibility, NOT a completed installed upgrade.
- Candidate-owned Python 3.11 accepted editing-only capability and the four signed compatibility manifests (Z-Image 0.1.3, Ideogram 0.1.2, Qwen Image 0.1.2, FLUX.2 Klein 0.1.4). It rejected unknown future version 99.0.0 in each case. No account/session or model inference was used.
- Six embedded files matched repository SHA-256 exactly: `model_worker/image_capabilities.py`, `model_providers.py`, `packages/discovery.py`, `packages/contract_v1.py`, `api/imagine_studio.py`, `web/static/js/imagine_studio.js`.
- Postbuild evidence: `source-evidence-postbuild.json`, SHA-256 `30522f21fcfa3009a809d9795f5efdbe9660c8d8727453ecb86adfefe9cf5d3e`; all 1239 tracked source entries matched prebuild. The ledger gained this internal candidate heading (65 to 66), and test/receipt edits are represented in the postbuild git evidence.

Remaining: controlled UI/installed-upgrade acceptance and actual image generation/edit validation with compatible Packages; production source/ledger reconciliation, notarization, immutable dual-origin publication and Cloud rollout. Four model releases remain unpublished behind the compatible Desktop gate. This candidate is not automatically installed, launched, or offered through stable.
