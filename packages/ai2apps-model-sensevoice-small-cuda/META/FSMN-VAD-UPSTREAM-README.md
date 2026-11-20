---
license: apache-2.0
language:
- zh
- en
pipeline_tag: voice-activity-detection
tags:
- VAD
- FunASR
- voice-activity-detection
- speech-segmentation
library_name: funasr
---

<div align="center">

### ⭐ Powered by [FunASR](https://github.com/modelscope/FunASR) — please give us a GitHub Star!

This model is part of the **FunASR** ecosystem — one industrial-grade open-source toolkit for **ASR · VAD · punctuation · speaker diarization · emotion / event · LLM-ASR**. A Star really helps the project (and keeps you updated):

[**🌟 FunASR**](https://github.com/modelscope/FunASR)  ·  [**🌟 SenseVoice**](https://github.com/FunAudioLLM/SenseVoice)  ·  [**🌟 Fun-ASR**](https://github.com/FunAudioLLM/Fun-ASR)  ·  [**🌟 FunClip**](https://github.com/modelscope/FunClip)

</div>


# FSMN-VAD

**Voice Activity Detection** — accurately detect speech segments in audio, essential for long-audio processing pipelines.

FSMN-VAD uses a Feedforward Sequential Memory Network to detect speech/non-speech boundaries with high precision and low latency. It supports both streaming and offline modes.

## Quick Start

```python
from funasr import AutoModel

# Standalone VAD
model = AutoModel(model="funasr/fsmn-vad", hub="hf", device="cuda")
result = model.generate(input="long_audio.wav")
# Returns speech segments: [[start_ms, end_ms], [start_ms, end_ms], ...]
print(result[0]["value"])
```

## Use as Part of ASR Pipeline

```python
from funasr import AutoModel

# VAD automatically segments long audio before ASR
model = AutoModel(
    model="funasr/paraformer-zh",
    hub="hf",
    vad_model="funasr/fsmn-vad",
    device="cuda",
)
result = model.generate(input="meeting_2hours.wav")
print(result[0]["text"])
```

## Features

- Streaming and offline voice activity detection
- Configurable segment length (`max_single_segment_time`)
- Low latency for real-time applications
- Works with all FunASR ASR models as a preprocessing step

## Model Details

| Property | Value |
|----------|-------|
| Architecture | FSMN (Feedforward Sequential Memory Network) |
| Sample Rate | 16kHz |
| Modes | Streaming + Offline |

## Links

- **GitHub**: [FunASR](https://github.com/modelscope/FunASR)
- **Docs**: [modelscope.github.io/FunASR](https://modelscope.github.io/FunASR/)
