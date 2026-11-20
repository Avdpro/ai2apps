# FLUX.2 Klein 4B CUDA — development source

BF16 image generation and editing through the shared CUDA Runtime adapter.
The capability contract includes 1–4 reference images and PNG/JPEG/WebP output.
Mac-specific quantization/cache implementation flags are not advertised.

The fixed CUDA checkpoint distribution candidate is
`dist_ai2apps_flux2_klein_4b_cuda_e7b7dc27_v1` (18 files, 15,980,131,745 bytes).
Its spec includes the official scheduler. `weights.distribution_id` remains
absent until publication and fresh public signature verification complete.
Do not build a production Package with an unpublished distribution.

Requires released CUDA Runtime >=0.6.0. Basic isolated Worker and lifecycle
receipts exist under spark/artifacts/flux-http-lifecycle-r1 and
spark/artifacts/flux-host-lifecycle-r2; these do not replace signed installation.
Memory figures are estimates. No checkpoint bytes are bundled here.
