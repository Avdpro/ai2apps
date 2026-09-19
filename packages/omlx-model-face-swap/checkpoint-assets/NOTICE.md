# MLX GhostV2 checkpoint notices

GhostV2 source and pretrained checkpoints are from
`dimitribarbot/ghostv2` commit
`bc53ed086dbe8ea38e165aec7aaac90d1749a335` under BSD-3-Clause.

Face detection uses YuNet 2023mar from OpenCV Zoo commit
`47534e27c9851bb1128ccc0102f1145e27f23f98` under MIT.

The GhostV2 generator was converted to a BatchNorm-folded native NHWC MLX
checkpoint. The CVLFace encoder and YuNet detector are parser-free oMLX graph
bundles. Conversion does not change the upstream license terms.
