# AI2Apps CUDA Torch Runtime

This package is built on a Linux ARM64 CUDA host. It contains a private CPython
standard library, the PyTorch/Transformers framework layer, and the trusted
AI2Apps Model Worker launcher. NVIDIA userspace libraries are supplied by the
compatible host CUDA installation. cuDNN, cuSPARSELt, NCCL and NVSHMEM
distributions are bundled when required; the remaining CUDA toolkit libraries
are supplied by the host. The dependency inventory is included in META.

Build it with the Python environment whose Torch installation should be
exported:

```bash
python scripts/build_cuda_torch_runtime_package.py --stage-only --keep-work /absolute/path/to/new-candidate \
  --nvfp4-aot-cache ~/.cache/flashinfer/0.7.0.post1/121a/cached_ops \
  --audio-python /absolute/path/to/media-audio-venv/bin/python \
  --h3-python /absolute/path/to/h3-venv/bin/python \
  --h3-sources /absolute/path/to/pinned-h3-archives \
  --h3-python-headers-deb /absolute/path/to/libpython3.12-dev_3.12.3-1ubuntu0.17_arm64.deb \
  --h3-toolchain-sources /absolute/path/to/h3-toolchain-sources
```

Transfer the reported unsigned `package` source to the signing Mac, then use
`scripts/build_signed_registry_release.py --source ...` with the existing
registered Publisher key. Do not transfer that key to the build host or use
the legacy development archive's ephemeral signing identity for publication.
Follow `docs/ai2apps-package-publication-runbook.md` for publication and recovery.
The archive contains Linux ELF binaries and uses the Linux tar Runtime installer;
Apple Developer ID/notarization applies to macOS DMG Runtime payloads.

Version 0.5.0 (unpublished H3 candidate) targets Ubuntu 24.04 ARM64 with a compatible CUDA 13 toolkit,
NVIDIA driver and Docker GPU runtime. The base Worker image must be installed
before starting an offline Worker. Inspect and test the generated Runtime in
the managed Docker sandbox before publishing; source-venv success is insufficient.

The GB10 native NVFP4 capability bundles FlashInfer 0.7.0.post1 and the two
validated AArch64 AOT modules. It never relies on a development JIT cache.

The default layer retains Transformers 5.18 and includes Diffusers 0.41.0.
Qwen3-TTS uses a separately resolved audio layer (Transformers 4.57.3), selected
by a service allowlist in signed Runtime metadata before importing the Worker.
No development `.pth` or external venv path is exported. Dependency versions
are checked for each export closure; profile-specific versions appear in the SBOM.
Runtime 0.4.0 is the previously published media baseline. H3 source archives and
compatibility patch are pinned by digest; the H3 layer reuses the exported Torch
core and matching TorchAudio. The builder records the compiler/header package
versions, copyright files and file hashes. Complete matching Ubuntu source
packages (original source, distribution patches and descriptors) are bundled in
`h3/toolchain/sources`, alongside the export script. The checked-in
`scripts/h3-toolchain-sources.json` pins their sizes and SHA-256 digests; a
binary/source version mismatch or changed archive fails the build.

Candidate evidence is tracked in `spark/MEDIA-PROGRESS.md`; publication and
full installed Host acceptance are still pending.
