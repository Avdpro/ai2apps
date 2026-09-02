# AI2Apps CUDA Torch Runtime

This package is built on a Linux ARM64 CUDA host. It contains a private CPython
standard library, the PyTorch/Transformers framework layer, and the trusted
AI2Apps Model Worker launcher. NVIDIA userspace libraries are supplied by the
compatible host CUDA installation and are not duplicated in the archive.

Build it with the Python environment whose Torch installation should be
exported:

```bash
python scripts/build_cuda_torch_runtime_package.py
```
