# SoL-Refiner CUDA development Package

Adapter-only Package using the CUDA Runtime SoL profile. Standard and custom prompt variants retain image/video 2x upscaling contracts. Fixed converted BF16 assets are reused; no claim of Mac numerical identity or throughput.

Variant distribution specifications are drafts, not signed or published; service weights deliberately have no distribution_id until publication verification. Installation must present the exact LTX-2/Gemma terms and require the installing user declaration. No consent is inherited.

META/source-lock.json and notices retain original conversion provenance, including Mac development dependencies; these are not CUDA runtime locks. Executable dependencies and engines belong to the separately validated CUDA Runtime.

Existing engine/Host evidence does not establish signed installation of this new Package.

## Checkpoint compatibility blocker

Do not sign or publish the current draft distribution specs. Header audit of the Mac snapshot against the accepted official CUDA input found 2,729 missing transformer keys (1,457 versus 4,186), and no Diffusers shard index in the Mac snapshot. The current CUDA engine loads the official full transformer using Diffusers. Equal retained tensor shapes/dtypes and configs do not establish compatibility or equal values. The Package source/empty lifecycle checks do not load weights.

Before publication, bind a verified official-layout distribution (including the shard index and separately verified fixed prompt context) and run this actual Package with it. Preserve the original LTX-2/Gemma installation declaration. Audit: spark/artifacts/sol-checkpoint-layout-comparison-r1.json.
