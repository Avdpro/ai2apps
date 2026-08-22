# CT-Transformer Punctuation Restorer

Internal CPU-only punctuation dependency for AI2Apps ASR Packages. It restores
Chinese and English punctuation with a pinned INT8 ONNX checkpoint and rejects
any result that changes the source words. It is hidden from normal Chat model
selection and is installed automatically with SenseVoice Small.
