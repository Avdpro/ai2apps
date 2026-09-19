# Preliminary checkpoint license review

Date: 2026-09-05

This is an engineering release gate, not legal advice. The current ONNX files
were obtained from the locked VisoMaster asset release for reproducible local
testing. A third-party conversion or mirror does not by itself grant permission
to redistribute the underlying weights.

## Current finding

| Component | Upstream statement | Package consequence |
| --- | --- | --- |
| InsightFace SCRFD and ArcFace weights | Public pretrained models are limited to non-commercial research unless separately licensed. | Do not mirror these weights in a generally available AI2Apps Package. Use a separately licensed replacement or a user-initiated external install with the applicable terms. |
| InSwapper 128 | Distributed through the InsightFace ecosystem; no permissive redistribution grant has been established for the locked converted file. | Experiment-only until explicit model authorization or a replacement checkpoint is selected. |
| SimSwap | Official project is CC BY-NC 4.0 and states academic/non-commercial use only. | May be offered only in a clearly non-commercial channel whose distribution is confirmed compliant; exclude from the default public/commercial Package. |
| LivePortrait core | Official project license is MIT. Its own license warns that the default InsightFace detector must be removed/replaced for commercial use. | Technical provenance is now reproduced from the pinned official weights and the detector is replaced by MIT YuNet. It is the first public Package candidate, subject to dual-source distribution and release review. |
| GFPGAN | Official project declares Apache 2.0, with third-party notices in its license. | Candidate for an optional restoration Package after exact ONNX checkpoint provenance and required notices are verified. |

## Release-safe direction

1. Keep the current 13 locked files as local numerical-reference assets only.
2. Separate detector/landmarker from identity and generation capabilities so a
   permissive replacement can be installed without changing LivePortrait.
3. Build the first public Package candidate from the pinned official
   LivePortrait weights and `convert_official_liveportrait.py` receipt, not the
   VisoMaster mirror. Evaluate GFPGAN separately after its exact checkpoint
   provenance is established.
4. Treat InSwapper/InsightFace and SimSwap as bring-your-own-model or explicitly
   licensed Package variants until written redistribution terms are available.
5. Store license ID, source revision, original hash, conversion command, output
   hash, and required notices alongside every published bundle.

## Primary upstream references

- InsightFace model policy: <https://github.com/deepinsight/insightface/tree/master/model_zoo>
- SimSwap repository and license notice: <https://github.com/neuralchen/SimSwap>
- LivePortrait license: <https://github.com/KlingAIResearch/LivePortrait/blob/main/LICENSE>
- GFPGAN repository and license: <https://github.com/TencentARC/GFPGAN>
