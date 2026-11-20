# DeepSeek V4.1 Flash 1017

Version 0.1.2 pins the 1017 original FP4/FP8 SSD checkpoint through a signed dual-source distribution and requires Runtime 1.8.12. The Runtime fixes tool EOS parsing, image/tool encoding, cross-request expert mappings and scratch buffer lifetime. D-Spark remains disabled.

The standard Main40/Hot8 profile activates the SSD expert store in place. Existing verified AI2Apps shared checkpoint blobs are reused without downloading the weights again. Optional reasoning remains enabled by default.
