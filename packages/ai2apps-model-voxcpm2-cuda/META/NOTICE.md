# VoxCPM2 CUDA notices

VoxCPM2 code and model weights from OpenBMB are Apache-2.0. Fixed MLX-Audio converted 4-bit and 8-bit snapshots are loaded by the CUDA engine with explicit inverse conversion; this does not imply native low-bit CUDA kernels. Original model/implementation provenance and licenses are retained in the distribution and Runtime inventories.

The CUDA Runtime owns pinned OpenBMB source, dependencies, checkpoint and inference modules. This Package supplies the AI2Apps speech adapter for Host-selected weights, structured instructions, reference cloning and serialized request lifecycle. Qualitative speed controls map to instructions and do not promise exact audio duration multipliers. No BF16 variant is advertised by this Package.

Development contract only: the two CUDA checkpoint envelopes already exist as signed candidates. Production status, shared Runtime regression, installation audit and signed installation must be verified before release. No Mac throughput benchmark is claimed for CUDA.
