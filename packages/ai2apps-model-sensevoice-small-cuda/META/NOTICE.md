# SenseVoice Small CUDA attribution

SenseVoiceSmall is an unmodified upstream model by FunAudioLLM / FunASR.
Original checkpoint: https://huggingface.co/FunAudioLLM/SenseVoiceSmall
Official mirror: https://modelscope.cn/models/iic/SenseVoiceSmall
Official inference source: https://github.com/FunAudioLLM/SenseVoice

Model weights remain subject to FunASR Model Open Source License Agreement 1.1,
Copyright (C) 2023–2028 Alibaba Group. The exact retrieved license is preserved
in `licenses/FunASR-MODEL-LICENSE-1.1.txt`. Checkpoint files remain externally
hosted; they are not included in this source directory. Keep model name, source
and attribution when distributing the model or this notice.

CUDA integration source lives in `spark/cuda_sensevoice_adapter.py`. This draft
metadata does not assert that a Registry distribution or Package is published.

FSMN-VAD helper: FunASR authors / Alibaba Group. The pinned HF model card
declares Apache-2.0 and is retained as FSMN-VAD-UPSTREAM-README.md. Exact
HF checkpoint df20e6b30c653645fa4ff125cacfcabd1020a669 is mirrored unchanged
at ai2apps/fsmn-vad commit dce94570fbc263aa692d8867b0f47bc03f6330b3.
Full Apache-2.0 text is retained in licenses/Apache-2.0.txt.
