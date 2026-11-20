# FlashHead CUDA release preparation

Not installable or published. This directory contains the validated CUDA adapter, shared request/lifecycle and checkpoint helpers, pinned distribution specs and license. Draft ai2apps.json and service.yaml now bind the fixed CUDA identities and signed distribution candidates. These contracts do not authorize installation/publication before the Runtime, checkpoint publication and signed installation gates pass.

The adapter matches fixed official Lite/Pro 2-second outputs and passes Lite 60-second/Pro 10-second fixture lifecycle tests. Broader perceptual lipsync quality, memory-pressure prevention and real signed installation remain open.

Before constructing a release, reconcile source hashes with spark/cuda_flashhead_adapter.py and the current shared FlashHead sources. Follow docs/ai2apps-package-publication-runbook.md.

Cancellation cleanup now releases native traceback references while retaining diagnostic text. See spark/evidence/media/flashhead-real-cancel-recovery-20261008.json for exact real-device coverage; Task cancellation is tracked separately in spark/evidence/media/flashhead-task-cancel-recovery-20261008.json; socket disconnect and broader stress remain separate gates.
