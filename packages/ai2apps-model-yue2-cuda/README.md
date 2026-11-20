# YuE2 CUDA candidate

Unreleased model service candidate. Requires a signed, installed CUDA Runtime
with the `yue2` capability and isolated profile; published Runtime 0.5.0 does
not supply this capability. The version floor does not waive capability checks.

Reuses the verified default and VAE checkpoint bytes, but requires new signed
distributions bound to the CUDA model IDs. Existing MLX distributions cannot
be used by this package. weights.distribution_id is intentionally omitted until
the new envelopes are published and anonymously verified; release policy must
reject this unfinished candidate. No checkpoint or
upstream Python downloaded from the model repository is executed. Official
CUDA source, engine, lifecycle owner and dependencies belong to the Runtime.

Pending gates: all-mode Host acceptance, perceptual/lyrics/melody quality,
signed Runtime and package installation, authenticated product invocation,
Registry download and lifecycle acceptance. Do not publish this candidate
until those gates and the standard publication runbook are satisfied.
