# AI2Apps Desktop 0.1.3 Build 2257 Release Preparation

Date: 2026-10-02

## Candidate identity

- Product version: `0.1.3`
- Build: `2257`
- Bundle ID: `com.ai2apps.desktop`
- Instance: `default`
- Architecture: `arm64`
- Runtime profile: `cloud`
- Sandbox mode: `0`
- Update channel: `stable`
- Rollout ID: `build2257-test`

## Included scope

- Discover shows an upgrade action for installed Packages when the catalog has a newer version and keeps model upgrades on the Package operation path.
- Imagine Studio includes the built-in 2× image upscaling workflow backed by the published Runtime 1.8.8 and SoL-Refiner Package.
- Video Studio includes the built-in 2× video upscaling workflow, bounded long-video segmentation, overlap blending, cancellation/retry, and audio preservation.
- The Host understands image upscaling, video upscaling, and video segmentation Model Worker capabilities and reserves resources from the actual source geometry.
- Video Composer can create dynamic person masks through the built-in Apple Vision helper or an installed SAM 2.1 Model Worker.
- The App bundle includes the signed `ai2apps-person-mask` native helper.
- Release assembly excludes repository `.build`, `.pytest_cache`, and `.ruff_cache` directories and verifies embedded Python with `PYTHONSAFEPATH=1`.
- The embedded source records the published Runtime 1.8.8, SAM 2.1, and SoL-Refiner Package contracts and release receipts.

## Explicitly deferred

- Encore MLX remains quality-failed and is not shipped or selected by production code.
- AVTR-1, MuseTalk, InfiniteTalk, and Ex-Omni ports and their parity fixtures are not included in this Release commit or Desktop artifact.
- Personal test media, including `ai2apps-test-system/assets/voice-1.wav`, is excluded.

## Source and verification gates

- The candidate is assembled in an independent worktree based on the latest `origin/main`; the Release build must use the final committed and pushed source with a clean worktree.
- A Package test import collision between two top-level `worker_adapter` modules was fixed by loading the SAM adapter under a unique test module name.
- Runtime 1.8.8 service and descriptor capability order, ACPF bilingual copy, and Discover upgrade contract assertions were synchronized before the final full regression.
- Final source regression: Python `10437 passed, 68 skipped, 74 deselected`; all 16 Node test files; Swift `77` Swift Testing plus `2` XCTest; focused Ruff and `git diff --check` passed.
- Final test counts, source commit, artifact hashes, Apple submission, immutable origins, Cloud digests, and target-Mac upgrade evidence are recorded in the final Build receipt.

## Rollback

- Before rollout, a failure leaves Build 2256 active.
- After rollout, Cloud can pause Build 2257 to 0% or restore the audited Build 2256 manifest digest.
- Clients are never instructed to install a lower Build; a corrective client must use a higher Build number.
