# Stable Audio 3 Small CUDA — development source

Music and sound-effect variants use original fixed optimized NPZ weights with
CUDA execution. Duration 1–120 seconds, WAV output, no lyrics. Runtime-owned
text encoder, DiT, decoder and lifecycle modules supply the implementation;
this Package owns the Worker adapter and Host generation contracts.

Stability AI Community and Gemma terms are delivered in META/licenses and
NOTICE. Installing users must explicitly confirm applicable terms/authorization;
this source does not accept terms on their behalf. Checkpoint bytes stay external.
The two CUDA-specific Registry distributions are pending, so distribution_id is
intentionally absent. A released Runtime >=0.6.0, signed Package installation
and actual installed Host generation remain required.
