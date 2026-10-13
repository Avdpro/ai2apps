# H3 avatar 0.11.0 release

Status: published and anonymously verified, 2026-10-06 (Asia/Shanghai). Repository Snapshot 261.

Submission: `8e81b99c-ba8e-46c8-841b-6f383e871559`.
Host source baseline: `fa377dcb62875d5c82fc8177afd4277cd2357db9` plus the documented working-tree changes.

## Scope

Eight portrait variants: FL2VA Q4/Q8, Ref2VA Q4/Q8, LightX2V 4/8-step Q4,
and OpenVDN DMD8/Stage-B50 Q4. Each model declares its motion weights and shared
mouth-refiner Distribution. Long audio is a durable Host task: bounded generation
windows, checked continuation state, global-time mouth refinement, and one final
audio mux. The current 100 MiB input quota allows 3276 seconds after 16 kHz mono
PCM16 normalization. The longest actual visual/sync acceptance remains 69 seconds.

Requires Host feature `avatar.segmented-jobs.v1` and oMLX Runtime >=1.8.8,<2.0.0.
Older Hosts must reject this Package. Desktop delivery of the Host changes is
tracked separately under NXR-H3-AVATAR-LONG-JOBS-20261006.

## Immutable candidate

- Package: `ai2apps/model-minimax-h3 0.11.0`
- SHA-256: `6c79415f087a5a334ac8bbcb458a1759dce2fdf2abffcde45a46163c9b02a0f1`
- Size: 229683 bytes

- Publisher: 229d6350-cd0e-408a-9905-41367385ae5c
- Publisher key: 8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc
- Six new refiner Distributions: published and anonymously signature/digest verified.
  Receipts: `artifacts/h3-avatar-20261006/release/distributions/`.

## Acceptance

- All eight variants passed one-second real adapter checks and nine-second,
  two-window generation. Source/video hashes verified for 15 harness runs;
  Turbo4 continuation evidence is retained separately.
- Turbo4 69-second source run: 11 windows, 1656 frames, exact duration/PTS;
  SyncNet samples at 30/60-second boundaries and tail show -40 ms offsets.
- Exact signed 0.11.0 Package installed into independent sandbox with signed 1.8.8
  Runtime; owned checkpoint fixtures verified against public manifests.
- Actual installed Worker: queue shutdown/reconstruction, explicit user cancel,
  and retry passed. First window invoked exactly once; its SHA-256 remained
  unchanged through all attempts. Retry output: 216 frames, H.264/AAC, 9 seconds,
  zero timestamp error; cross-boundary SyncNet -40 ms, confidence 5.211.
- Full Local process restart passed: original PID 56744 exited with a queued task;
  new PID 62581 invoked only segment 1 and reused the unchanged segment 0 hash.
  Final video has 216 frames and exact video/audio timing.
- Installed model catalog contains eight portrait aliases and eight ordinary video
  models. Uninstalled weight sets remain unavailable for generation.
- Stop/restart/stop/restart/uninstall passed in the independent sandbox.
- Final public artifact and envelope exactly match the installed candidate;
  Repository Snapshot and Publisher signature verification passed.
- Eight ACPF installation choices updated to >=0.11.0; 17 Avatar Studio tests and
  Mini-App input/model-selection JavaScript checks passed.
- Sampled frames and seam frames show no abrupt placement/exposure change.
  Mouth softening persists; this is not a claim of identical quality across variants.
- No Desktop binary or runtime update has been released by this Package publication.

## Desktop activation

The model Package release is complete. The Host queue, segmented transport and
ACPF profile changes are implemented in this checkout and recorded in the Desktop
release ledger. They are not part of the model Package; an older installed Desktop
will correctly reject 0.11.0 until it gains `avatar.segmented-jobs.v1`. No Desktop
rebuild or rollout is claimed here.

Package public verification: `artifacts/h3-avatar-20261006/release/package-public-verification.json`.
Installed acceptance: `artifacts/h3-avatar-20261006/release/installed/`.
