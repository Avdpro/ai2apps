# Seed-VC v2 CUDA

Development Service Package for DGX Spark. Requires CUDA Runtime >=0.6.0.
Uses fixed Avdpro/MLX-Seed-VC-v2@2122cee1aff2b0e17a843dfa7cdc0464271c43b4
checkpoint bytes, interpreted by the existing CUDA engine. The checkpoint name
is provenance, not an MLX execution dependency.

Exposes timbre_fast, timbre_quality and voice_quality with source/reference
uploads and WAV output. The engine and native dependencies belong to Runtime;
the Package owns its adapter, Host capabilities, notices and installation contract.

Prior CUDA development Worker/Host evidence is in spark/MEDIA-INVENTORY.json.
Minute timbre conversion has retained evidence; voice-quality issues remain
open. This new Package has not passed signed installation, final quality or
publication gates. No Registry distribution is bound until a CUDA model-bound
distribution has actually been published. Do not treat source availability or
an entrypoint check as real inference acceptance.
