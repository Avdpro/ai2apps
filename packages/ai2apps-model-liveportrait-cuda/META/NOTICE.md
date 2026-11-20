# LivePortrait CUDA notices

LivePortrait is Copyright (c) 2024 Kuaishou Visual Generation and Interaction Center, MIT licensed. This Package supplies the CUDA Worker adapter; its required CUDA Runtime supplies pinned official Torch modules, crop geometry and mask. Exact source revision is recorded in service.yaml and the Runtime source inventory.

Shared media decoding, motion workflow and output handling derive from the existing AI2Apps MLX LivePortrait integration and fasterliveportrait-mlx (Copyright (c) 2026 Ivan Fioravanti, MIT). This CUDA path uses official Torch kernels rather than the MLX model port.

The separately distributed checkpoint contains losslessly converted safetensors, official 203-point landmark weights and OpenCV YuNet (Copyright (c) 2020 Shiqi Yu, MIT). Its fixed manifest includes LICENSE, YUNET_LICENSE and provenance notices. No InsightFace weights are included. Download and installation must use the Host checkpoint distribution and applicable user license declaration flow.

Development source only: shared Runtime GPU acceptance and signed installation remain required before Package publication. No Mac throughput result is claimed for Spark.
