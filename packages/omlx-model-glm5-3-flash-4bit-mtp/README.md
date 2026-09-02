# GLM-5.3 Flash 4-bit MTP Cached-MoE model package

Adds the immutable Vontra MLX affine 4-bit checkpoint recipe and multimodal,
session-aware dynamic Cached-MoE Worker adapter required by AI2Apps oMLX
Runtime 1.5.5 or later.

Natural/exact inference is the default. Turbo (Top-5 protected) and Blast
(Top-3 protected) remain explicit per-request or per-session choices and apply
to both Prefill and Decode. The multimodal memory profile uses Main64 + Hot16
inside a 96-slot bank; the native MTP drafter remains opt-in.

The checkpoint and SSD-ready fused-v2 expert store are acquired and prepared
at install time. They are not embedded in this Package.
