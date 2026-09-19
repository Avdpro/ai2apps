# LivePortrait checkpoint provenance

Date: 2026-09-05

The release candidate should use the official `KlingTeam/LivePortrait` model
repository at immutable revision
`82a4fa6735ca58432b6ce39301b4b9ee066dea47`. The five selected source files,
their sizes, and SHA-256 values are locked in `assets.lock.json`. The
InsightFace and official landmark assets are intentionally excluded; the
pipeline uses MIT-licensed YuNet for detection and five-point landmarks.

`convert_official_liveportrait.py` converts the official PyTorch state dicts
into MLX NHWC/NDHWC layouts, folds inference spectral normalization, splits the
combined stitching/eye/lip checkpoint, and writes a conversion receipt. Torch
is used only in this trusted build step and is not an inference dependency.

The reproduced output was compared with the audited community MLX conversion
at revision `2cc2ac92c9fe65ca4fb68cb1a1556ead285e7391`. All 562 tensors across
the seven human LivePortrait files were byte-identical, including the complete
NPZ container SHA-256 values:

| Output | Tensors | SHA-256 |
| --- | ---: | --- |
| appearance_feature_extractor.npz | 92 | `4eec38855dce659872aa33b684dcb513289d905941a19531e7ff32bf464b4fbd` |
| motion_extractor.npz | 212 | `f761c3441b3833af57603069bb5163b8355e28c0d5a9c64363f5e6d08def2178` |
| spade_generator.npz | 146 | `a9de6c00bff60ced8985429280a63c561cdf7d3cf8165edbdc0258643613f1b3` |
| warping_module.npz | 84 | `1e42984161e17391d41eec9b7444318890ff816cd23316e272707153bdf0d27d` |
| stitching.npz | 8 | `c947d7dba4905d560bf144fb2ef9aa7dfb6fdab795736909073c8cc49a78501d` |
| stitching_eye.npz | 12 | `72b5f6b00b43e4963f0ba24e9e58cdcb20a9332ac676480fdef4cf584124a750` |
| stitching_lip.npz | 8 | `af27dce745f662f4d7f48185e24bfc4caf33ebceb7e66f14c088f3844e8a53dd` |

The audited native FP32 MLX implementation was also compared with the
independent parser-free graph baseline on identical inputs. Motion tensors were
close, rendering was visually equivalent, and the native path improved the
largest warping/render stage. BF16 remains an opt-in speed profile because its
stress-input image difference is material; FP16 motion is rejected because it
produced non-finite values.

This evidence clears the technical source trace for a LivePortrait checkpoint.
It does not authorize publication by itself: the converted checkpoint must
still be mirrored byte-for-byte to fixed Hugging Face and ModelScope revisions,
receive a signed Registry distribution ID, and pass the Package release audit.
