YuE2 CUDA model Worker adapter for AI2Apps.

This package contains the Python adapter, not model weights or native libraries.
The required Runtime provides the official YuE2 pipeline at commit
3d21f8f5d31be867f4c3b2e6beafb0f2e52f8c10 and a pinned CUDA stream reuse patch.
The model, sampler, flow solver and VAE retain official CUDA algorithms.
Adapter and upstream code are Apache-2.0. Weights retain their separate
MODEL_LICENSE, including CC BY-NC 4.0 and individual creator permission.
Users must review original terms through the checkpoint installation flow.
See included original notices and licenses in META/licenses.
