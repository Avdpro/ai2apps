# Sources

Weights: Tongyi-MAI/Z-Image, Apache-2.0, pinned in source-lock.json; not bundled.
Runtime implementation: mflux 0.19.0 (MIT), supplied by the installed oMLX Runtime, not copied into this Package.
Adapter derived from the AI2Apps Z-Image Turbo adapter with separate identities and native undistilled CFG configuration. No Turbo fused kernel is used.

Validation: Q8, 1024x1024, 30 steps, CFG 4, seed 42 on Apple M5 Max 128 GiB: 166.278s including cold setup, Metal peak 17,950,257,918 bytes. 32 GiB admission floor is conservative estimated headroom, not a measured minimum on 32 GiB hardware. Scores are Publisher relative estimates.
