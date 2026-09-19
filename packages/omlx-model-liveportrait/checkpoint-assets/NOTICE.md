# MLX LivePortrait checkpoint notices

The seven `weights/*.npz` files are deterministic MLX conversions of the
official human LivePortrait checkpoint at `KlingTeam/LivePortrait` revision
`82a4fa6735ca58432b6ce39301b4b9ee066dea47`. Conversion changes tensor layout
for MLX execution and folds inference spectral normalization; it does not train
or alter the learned model.

The detector bundle contains `face_detection_yunet_2023mar.onnx` converted to
the oMLX graph format. YuNet is licensed under the MIT License included as
`YUNET_LICENSE`.

No InsightFace checkpoint is included.
