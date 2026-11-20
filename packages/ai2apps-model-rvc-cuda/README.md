# RVC CUDA

Development model Package for DGX Spark, requiring CUDA Runtime >=0.6.0.
Provides fixed Serena e70 synthetic-voice conversion (pitch/retrieval/protect)
and WAV-ZIP training with a voice-bundle result. Uses the fixed composite
Avdpro/MLX-RVC-Serena-E70@738acad9f58c074d9f817eeac8c7dac9e2eafa1f
checkpoint; its name describes provenance, not an MLX execution dependency.

Trained-voice requests are advertised in this development source after real
CUDA Worker and Host upload/scheduler/proxy acceptance: uploaded voice output
matches the direct normalized baseline, default voice state restores exactly,
and invalid voice ZIPs return 422 without corrupting the next request. The
optimized Runtime candidate contains the updated protocol and passes production
materialization/import acceptance. This does not claim signed installation,
production availability, or closure of existing training quality findings.

Prior CUDA conversion/training evidence is retained in spark/MEDIA-INVENTORY.json.
This Package has not passed signed installation or publication. Its CUDA-bound
checkpoint distribution must be published before building a release. The old
Mac model-bound distribution is not reused under a different model identity.
