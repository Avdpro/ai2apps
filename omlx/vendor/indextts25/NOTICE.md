# WIndexTTS MLX notice

The files in this directory are derived from WIndexTTS commit
`eafb98c1b2ba46f6a608f29d8831208b89047681`, Copyright (c) 2026
baicai-1145 contributors, under Apache License 2.0.

Source: https://github.com/baicai-1145/WIndexTTS

AI2Apps modifications:

- moved the pure-MLX runtime into the `omlx.vendor.indextts25` namespace;
- removed runtime imports of the Torch implementation;
- added a Torch-free BigVGAN configuration reader;
- resolve all assets only from Host-selected, pinned checkpoint directories.

IndexTTS model weights remain governed by the separate Bilibili Model Use
License Agreement supplied with the model Package.
