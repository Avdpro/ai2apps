# CT-Transformer punctuation — Linux Runtime development source

Fixed INT8 ONNX punctuation restoration for Chinese and English, using CPU
sherpa-onnx in the CUDA Runtime punctuation profile. This is an internal text
processing dependency, not an expansion of dialogue model scope. The existing
cross-platform Service/model identity and published checkpoint distribution
are preserved; the Linux Service Package has its own platform-specific ID.

No GPU access is requested. The adapter preserves words and numeric expressions,
normalizes English punctuation, and falls back to terminal punctuation when the
model changes words. Weights stay external. Apache license and attribution are
retained. Requires a released CUDA Runtime >=0.6.0; development source and basic
inference evidence do not establish signed installation or publication.
