# oMLX MoE Cache Experiment

This repository is the oMLX-based branch of the DMoE research project.

## Scope

- Preserve oMLX's existing model, attention, router, and fused MoE kernels.
- Add cache-aware routed-expert storage behind `DeepseekV4MoE`/`SwitchGLU`.
- Keep router indices on device on the all-hit path.
- Reuse DMoE trace/profile/offset artifacts by explicit file path; do not copy
  DMoE runtime modules into this repository.

## First performance gate

Implement a static oracle slot bank for DeepSeek V4 and compare it with the
unchanged full-resident oMLX path using identical prompts and generated tokens.
The prototype must demonstrate exact Top-10 parity, zero runtime misses, lower
resident memory, and retain at least 85% of the full-resident steady-state TPS
before dynamic cache replacement work begins.

## Branch discipline

- Experimental branch: `experiment/moe-cache`.
- Keep upstream-compatible changes isolated and small.
- Record benchmark commands, source commit, memory, cold TPS, and steady TPS.
- Never modify a sibling DMoE checkout from this repository.

## Notice:
- The current AI2Apps desktop client has bundle ID `com.ai2apps.desktop`.
- Never launch or control the retired `com.electron.ai2apps` client or its build output.
- When using Computer Use, identify AI2Apps by its exact bundle ID or executable path, not only by display name.
