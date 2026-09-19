"""Discover catalog classification for current and future Packages.

The signed Package manifest is authoritative when it contains ``discovery``.
The legacy table is intentionally version-bounded: already-published model
Packages gain useful catalog metadata without being rebuilt, while their next
release must declare the metadata in ``ai2apps.json``.
"""

from __future__ import annotations

import re
from typing import Any

from packaging.version import InvalidVersion, Version

MODEL_CATEGORIES = frozenset(
    {"text", "speech", "multimodal", "image", "video", "embedding"}
)
_TASK = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_SERVICE_KEY = re.compile(r"^[a-z][A-Za-z0-9._-]{2,199}$")
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")


def matches_model_category(discovery: dict[str, Any], category: str) -> bool:
    """Match a catalog facet while preserving capability overlap.

    A multimodal conversational model is also usable for text conversation, so
    it belongs in the Text facet without losing its primary Multimodal facet.
    """

    categories = discovery.get("categories", [])
    if category in categories:
        return True
    return category == "text" and "multimodal-conversation" in discovery.get(
        "tasks", []
    )


def _model(
    through_version: str, category: str, *tasks: str
) -> dict[str, object]:
    return {
        "throughVersion": through_version,
        "kind": "model",
        "categories": [category],
        "tasks": list(tasks),
    }


# Keep this table explicit and reviewable. Do not infer catalog identity from a
# display name, description, or Package ID prefix at runtime.
LEGACY_MODEL_DISCOVERY: dict[str, dict[str, object]] = {
    "ai2apps/mock-audio-stt": _model("0.1.0", "speech", "speech-recognition"),
    "ai2apps/mock-audio-tts": _model("0.1.0", "speech", "speech-synthesis"),
    "ai2apps/model-cosyvoice3-05b": _model("0.1.1", "speech", "speech-synthesis", "voice-cloning"),
    "ai2apps/model-deepseek-v4-flash": _model("0.3.4", "text", "text-generation"),
    "ai2apps/model-deepseek-v4-flash-2bit": _model("0.3.5", "text", "text-generation"),
    "ai2apps/model-deepseek-v41-flash": _model("0.1.1", "multimodal", "multimodal-conversation", "image-understanding"),
    "ai2apps/model-demucs-mlx": _model("0.1.0", "speech", "source-separation"),
    "ai2apps/model-detailed-transcription-mlx": _model(
        "0.1.2",
        "speech",
        "detailed-transcription",
        "speaker-diarization",
        "subtitle-generation",
    ),
    "ai2apps/model-echomimic-v3-mlx": _model("0.1.1", "video", "video-generation", "avatar-video"),
    "ai2apps/model-fish-s2-pro": _model("0.1.1", "speech", "speech-synthesis", "voice-cloning"),
    "ai2apps/model-face-swap-mlx": _model("0.1.0", "video", "face-swap"),
    "ai2apps/model-flux2-klein-mlx": _model("0.1.3", "image", "image-generation", "image-edit"),
    "ai2apps/model-glm5-3-flash-4bit-mtp": _model("0.1.5", "multimodal", "multimodal-conversation", "image-understanding"),
    "ai2apps/model-ideogram4-mlx": _model("0.1.1", "image", "image-generation", "image-edit"),
    "ai2apps/model-liveportrait-mlx": _model("0.1.0", "video", "portrait-animation"),
    "ai2apps/model-multilingual-e5-small": _model("0.1.3", "embedding", "text-embedding"),
    "ai2apps/model-minimax-h3": _model(
        "0.9.0",
        "video",
        "video-generation",
        "text-to-video",
        "image-to-video",
        "reference-to-video",
        "audio-generation",
    ),
    "ai2apps/model-ornith15-35b-a3b-4bit-vision": _model("0.1.4", "multimodal", "multimodal-conversation", "image-understanding"),
    "ai2apps/model-qwen-image-mlx": _model("0.1.1", "image", "image-generation", "image-edit"),
    "ai2apps/model-qwen25-0-5b-cuda": _model("0.1.1", "text", "text-generation"),
    "ai2apps/model-qwen3-asr-0-6b-cuda": _model("0.1.3", "speech", "speech-recognition"),
    "ai2apps/model-qwen3-asr-06b": _model("0.1.1", "speech", "speech-recognition"),
    "ai2apps/model-qwen3-tts-06b": _model("0.2.1", "speech", "speech-synthesis"),
    "ai2apps/model-qwen3-tts-17b": _model("0.1.1", "speech", "speech-synthesis", "voice-cloning", "voice-design"),
    "ai2apps/model-qwen3-vl-2b-cuda": _model("0.1.1", "multimodal", "multimodal-conversation", "image-understanding", "video-understanding"),
    "ai2apps/model-qwen35": _model("0.1.2", "multimodal", "multimodal-conversation", "image-understanding"),
    "ai2apps/model-qwen36-35b": _model("0.3.4", "text", "text-generation"),
    "ai2apps/model-qwen38": _model("0.3.3", "multimodal", "multimodal-conversation", "image-understanding"),
    "ai2apps/model-qwen38-flash-next-4bit": _model("0.1.4", "multimodal", "multimodal-conversation", "image-understanding"),
    "ai2apps/model-rvc-mlx": _model(
        "0.1.0", "speech", "voice-conversion", "voice-training"
    ),
    "ai2apps/model-seed-vc-v2-mlx": _model(
        "0.1.0", "speech", "voice-conversion", "voice-cloning"
    ),
    "ai2apps/model-sensevoice-small": _model("0.2.2", "speech", "speech-recognition"),
    "ai2apps/model-vibevoice-05b": _model("0.1.1", "speech", "speech-synthesis"),
    "ai2apps/model-z-image-mlx": _model("0.1.2", "image", "image-generation", "image-edit"),
    "ai2apps/model-z-image-base-mlx": _model("0.1.0", "image", "image-generation"),
    "ai2apps/punctuation-restorer": _model("0.1.1", "text", "punctuation-restoration"),
}


def _gib(value: float) -> int:
    return round(value * 1024**3)


def _profile(
    through_version: str,
    size_gib: float,
    memory_gib: float,
    speed: int,
    capability: int,
    *,
    basis: str = "AI2Apps legacy estimate",
) -> dict[str, object]:
    return {
        "throughVersion": through_version,
        "sizeBytes": _gib(size_gib),
        "minimumMemoryBytes": _gib(memory_gib),
        "scores": {"speed": speed, "capability": capability},
        "benchmark": {
            "label": basis,
            "device": "Reference hardware",
        },
    }


# Approximate, modality-relative card data for already-published releases. The
# version cap prevents these curated estimates from leaking into a later model
# revision with different weights or performance characteristics.
LEGACY_MODEL_PROFILES: dict[str, dict[str, object]] = {
    "ai2apps/mock-audio-stt": _profile("0.1.0", 0.01, 1, 5, 1),
    "ai2apps/mock-audio-tts": _profile("0.1.0", 0.01, 1, 5, 1),
    "ai2apps/model-cosyvoice3-05b": _profile("0.1.1", 2, 8, 4, 4),
    # Checkpoint payload bytes and Cached-MoE gates, not parameter-count estimates.
    # See docs/discover-chat-model-profile-evidence-2026-09-10.md.
    "ai2apps/model-deepseek-v4-flash": _profile(
        "0.3.3", 159635168163 / 1024**3, 64, 2, 5,
        basis="Cached-MoE: 54.17 GiB peak; 64 GiB system estimate; scores estimated",
    ),
    "ai2apps/model-deepseek-v4-flash-2bit": _profile(
        "0.3.4", 96531568280 / 1024**3, 48, 3, 5,
        basis="Cached-MoE stream/patch: 31.46 GiB peak; 48 GiB system estimate; scores estimated",
    ),
    "ai2apps/model-deepseek-v41-flash": _profile(
        "0.1.0", 510320301313 / 1024**3, 96, 2, 5,
        basis="Lossless SSD Cached-MoE Main40/Hot8; <=65 GiB validated target",
    ),
    "ai2apps/model-demucs-mlx": _profile("0.1.0", 0.4, 4, 4, 4),
    "ai2apps/model-detailed-transcription-mlx": _profile(
        "0.1.2", 3832992557 / 1024**3, 8, 3, 5
    ),
    "ai2apps/model-echomimic-v3-mlx": _profile("0.1.1", 16, 32, 2, 4),
    "ai2apps/model-fish-s2-pro": _profile("0.1.1", 8, 16, 3, 5),
    "ai2apps/model-face-swap-mlx": _profile("0.1.0", 1, 8, 4, 4),
    "ai2apps/model-flux2-klein-mlx": _profile("0.1.3", 12, 16, 4, 4),
    "ai2apps/model-glm5-3-flash-4bit-mtp": _profile(
        "0.1.3", 181750094029 / 1024**3, 72, 3, 5,
        basis="Cached-MoE Lean Top80/Hot16: 55 GiB estimate; 72 GiB system floor; scores estimated",
    ),
    "ai2apps/model-ideogram4-mlx": _profile("0.1.1", 28, 24, 2, 5),
    "ai2apps/model-liveportrait-mlx": _profile("0.1.0", 1, 8, 4, 4),
    "ai2apps/model-multilingual-e5-small": _profile("0.1.3", 0.5, 2, 5, 3),
    "ai2apps/model-minimax-h3": _profile(
        "0.9.0", 41108034229 / 1024**3, 64, 2, 5
    ),
    "ai2apps/model-ornith15-35b-a3b-4bit-vision": _profile(
        "0.1.3", 20422831594 / 1024**3, 24, 3, 5,
        basis="Cached-MoE Top160/Hot32 VLM: 19.720 GiB peak; 24 GiB system estimate; scores estimated",
    ),
    "ai2apps/model-qwen-image-mlx": _profile("0.1.1", 40, 32, 2, 5),
    "ai2apps/model-qwen25-0-5b-cuda": _profile("0.1.1", 1.2, 4, 5, 2),
    "ai2apps/model-qwen3-asr-0-6b-cuda": _profile("0.1.3", 1.5, 4, 5, 4),
    "ai2apps/model-qwen3-asr-06b": _profile("0.1.1", 0.8, 4, 5, 4),
    "ai2apps/model-qwen3-tts-06b": _profile("0.2.1", 1.5, 8, 4, 4),
    "ai2apps/model-qwen3-tts-17b": _profile("0.1.1", 7, 12, 3, 5),
    "ai2apps/model-qwen3-vl-2b-cuda": _profile("0.1.1", 5, 8, 4, 4),
    "ai2apps/model-qwen35": _profile("0.1.2", 2, 8, 5, 3),
    "ai2apps/model-qwen36-35b": _profile(
        "0.3.3", 20429602477 / 1024**3, 16, 3, 5,
        basis="Cached-MoE Top120: 11.489 GiB peak; 16 GiB system estimate; size/scores estimated",
    ),
    "ai2apps/model-qwen38": _profile(
        "0.3.2", 23444503536 / 1024**3, 32, 3, 5,
        basis="Full NVFP4 VLM: 25.672 GiB peak; 32 GiB system estimate; scores estimated",
    ),
    "ai2apps/model-qwen38-flash-next-4bit": _profile(
        "0.1.3", 111602367013 / 1024**3, 64, 3, 5,
        basis="Cached-MoE Lean Top128/Hot10 + PLE mmap: 41 GiB estimate; 64 GiB system floor; scores estimated",
    ),
    "ai2apps/model-rvc-mlx": _profile(
        "0.1.0", 1410906582 / 1024**3, 16, 5, 4
    ),
    "ai2apps/model-seed-vc-v2-mlx": _profile(
        "0.1.0", 2236581603 / 1024**3, 16, 5, 5
    ),
    "ai2apps/model-sensevoice-small": _profile("0.2.2", 1, 4, 5, 4),
    "ai2apps/model-vibevoice-05b": _profile("0.1.1", 1, 6, 4, 4),
    "ai2apps/model-z-image-mlx": _profile("0.1.2", 12, 16, 4, 4),
    "ai2apps/model-z-image-base-mlx": _profile("0.1.0", 20538488386 / 1024**3, 32, 2, 4, basis="Q8 1024-square 30 steps: 166s on M5 Max 128 GiB; RAM floor estimated"),
    "ai2apps/punctuation-restorer": _profile("0.1.1", 0.2, 1, 5, 3),
}


# Runtime card values are separate from minimum system capacity. Cached-MoE
# entries use the lowest supported tier, not full-resident or optimal-tier peaks.
# Tuple: runtime GiB, system minimum GiB, measurement/configuration description.
LEGACY_CHAT_RUNTIME_MEMORY = {
    "ai2apps/model-deepseek-v4-flash": (33, 48, "Cached-MoE Lean Top20; runtime estimate"),
    "ai2apps/model-deepseek-v4-flash-2bit": (17, 32, "Cached-MoE Lean Top20; runtime estimate"),
    "ai2apps/model-deepseek-v41-flash": (65, 96, "Lossless SSD Cached-MoE Main40/Hot8; validated target"),
    "ai2apps/model-glm5-3-flash-4bit-mtp": (55, 72, "Cached-MoE Lean Top80/Hot16; runtime estimate"),
    "ai2apps/model-ornith15-35b-a3b-4bit-vision": (20, 32, "Cached-MoE Compact Top160; runtime estimate"),
    "ai2apps/model-qwen36-35b": (9, 16, "Cached-MoE Lean Top80; runtime estimate"),
    "ai2apps/model-qwen38-flash-next-4bit": (41, 64, "Cached-MoE Lean Top128 + PLE mmap; runtime estimate"),
    "ai2apps/model-qwen38": (22.3, 24, "NVFP4 text peak 22.3 GiB; vision peak 25.7 GiB; context dependent"),
}
for _package_id, (_runtime_gib, _system_gib, _basis) in LEGACY_CHAT_RUNTIME_MEMORY.items():
    LEGACY_MODEL_PROFILES[_package_id].update(
        runtimeMemoryBytes=_gib(_runtime_gib),
        minimumMemoryBytes=_gib(_system_gib),
        benchmark={"label": _basis, "device": "AI2Apps runtime tier / reference-host measurement"},
    )


def _install(
    through_version: str,
    service_key: str,
    *models: tuple[str, str],
) -> dict[str, object]:
    return {
        "throughVersion": through_version,
        "serviceKey": service_key,
        "models": [
            {"id": model_id, "label": label, "recommended": index == 0}
            for index, (model_id, label) in enumerate(models)
        ],
    }


# Catalog-safe checkpoint identities for already-published model releases. The
# table contains no repository URL or mutable revision: ACPF obtains those only
# from the installed, verified Service manifest and the signed distribution
# envelope. Later releases must carry the equivalent signed ``modelInstall``
# declaration in ai2apps.json.
LEGACY_MODEL_INSTALLS: dict[str, dict[str, object]] = {
    "ai2apps/mock-audio-stt": _install("0.1.0", "ai2apps.model.mock-audio-stt", ("ai2apps.model.mock-audio-stt/default", "Mock Audio STT")),
    "ai2apps/mock-audio-tts": _install("0.1.0", "ai2apps.model.mock-audio-tts", ("ai2apps.model.mock-audio-tts/default", "Mock Audio TTS")),
    "ai2apps/model-cosyvoice3-05b": _install("0.1.1", "ai2apps.model.cosyvoice3-0.5b", ("ai2apps.model.cosyvoice3-0.5b/4bit", "CosyVoice 3 0.5B 4-bit"), ("ai2apps.model.cosyvoice3-0.5b/8bit", "CosyVoice 3 0.5B 8-bit")),
    "ai2apps/model-deepseek-v4-flash": _install("0.3.4", "ai2apps.model.deepseek-v4-flash", ("ai2apps.model.deepseek-v4-flash/deepseek-v4-flash", "DeepSeek V4 Flash")),
    "ai2apps/model-deepseek-v4-flash-2bit": _install("0.3.5", "ai2apps.model.deepseek-v4-flash-2bit", ("ai2apps.model.deepseek-v4-flash-2bit/deepseek-v4-flash-2bit", "DeepSeek V4 Flash 2-bit DQ")),
    "ai2apps/model-deepseek-v41-flash": _install("0.1.1", "ai2apps.model.deepseek-v41-flash", ("ai2apps.model.deepseek-v41-flash/deepseek-v41-flash", "DeepSeek V4.1 Flash")),
    "ai2apps/model-demucs-mlx": _install("0.1.0", "ai2apps.model.demucs-mlx", ("ai2apps.model.demucs-mlx/default", "MLX Demucs HTDemucs")),
    "ai2apps/model-detailed-transcription-mlx": _install("0.1.2", "ai2apps.model.detailed-transcription-mlx", ("ai2apps.model.detailed-transcription-mlx/quality", "Detailed Transcription Quality"), ("ai2apps.model.detailed-transcription-mlx/compact", "Detailed Transcription Compact")),
    "ai2apps/model-echomimic-v3-mlx": _install("0.1.1", "ai2apps.model.echomimic-v3-mlx", ("ai2apps.model.echomimic-v3-mlx/default", "EchoMimic V3 MLX")),
    "ai2apps/model-fish-s2-pro": _install("0.1.1", "ai2apps.model.fish-s2-pro", ("ai2apps.model.fish-s2-pro/bf16", "Fish Audio S2 Pro BF16")),
    "ai2apps/model-face-swap-mlx": _install("0.1.0", "ai2apps.model.face-swap-mlx", ("ai2apps.model.face-swap-mlx/default", "MLX Actor Replacement")),
    "ai2apps/model-flux2-klein-mlx": _install("0.1.4", "ai2apps.model.flux2-klein-mlx", ("ai2apps.model.flux2-klein-mlx/4b", "FLUX.2 Klein 4B MLX")),
    "ai2apps/model-flux2-klein-9b-mlx": _install("0.1.0", "ai2apps.model.flux2-klein-9b-mlx", ("ai2apps.model.flux2-klein-9b-mlx/9b", "FLUX.2 Klein 9B MLX")),
    "ai2apps/model-glm5-3-flash-4bit-mtp": _install("0.1.5", "ai2apps.model.glm5-3-flash-4bit-mtp", ("ai2apps.model.glm5-3-flash-4bit-mtp/glm5-3-flash-mlx-4bit-mtp", "GLM-5.3 Flash 4-bit MTP")),
    "ai2apps/model-ideogram4-mlx": _install("0.1.2", "ai2apps.model.ideogram4-mlx", ("ai2apps.model.ideogram4-mlx/fp8-q4", "Ideogram 4 MLX Q4")),
    "ai2apps/model-liveportrait-mlx": _install("0.1.0", "ai2apps.model.liveportrait-mlx", ("ai2apps.model.liveportrait-mlx/default", "MLX LivePortrait")),
    "ai2apps/model-multilingual-e5-small": _install("0.1.3", "ai2apps.model.multilingual-e5-small", ("ai2apps.model.multilingual-e5-small/default", "Multilingual E5 Small")),
    "ai2apps/model-minimax-h3": _install(
        "0.9.0",
        "ai2apps.model.minimax-h3",
        ("ai2apps.model.minimax-h3/fl2va-4bit", "MiniMax H3 Q4"),
        ("ai2apps.model.minimax-h3/fl2va-8bit", "MiniMax H3 Q8"),
        ("ai2apps.model.minimax-h3/ref2va-4bit", "MiniMax H3 Ref2VA Q4"),
        ("ai2apps.model.minimax-h3/ref2va-8bit", "MiniMax H3 Ref2VA Q8"),
        (
            "ai2apps.model.minimax-h3/lightx2v-4step-4bit",
            "LightX2V Turbo 4-step Q4",
        ),
        (
            "ai2apps.model.minimax-h3/lightx2v-8step-4bit",
            "LightX2V Turbo 8-step Q4",
        ),
        (
            "ai2apps.model.minimax-h3/openvdn-dmd8-4bit",
            "OpenVDN DMD 8-step Q4",
        ),
        (
            "ai2apps.model.minimax-h3/openvdn-stageb50-4bit",
            "OpenVDN Stage-B 50-step Q4",
        ),
    ),
    "ai2apps/model-ornith15-35b-a3b-4bit-vision": _install("0.1.4", "ai2apps.model.ornith15-35b-a3b-4bit-vision", ("ai2apps.model.ornith15-35b-a3b-4bit-vision/ornith-1.5-35b-a3b-mlx-4bit-vision", "Ornith 1.5 35B A3B 4-bit Vision")),
    "ai2apps/model-qwen-image-mlx": _install("0.1.2", "ai2apps.model.qwen-image-mlx", ("ai2apps.model.qwen-image-mlx/2512", "Qwen Image 2512 MLX"), ("ai2apps.model.qwen-image-mlx/edit-2511", "Qwen Image Edit 2511 MLX")),
    "ai2apps/model-qwen25-0-5b-cuda": _install("0.1.1", "ai2apps.model.qwen25-0.5b-cuda", ("ai2apps.model.qwen25-0.5b-cuda/qwen2.5-0.5b-instruct", "Qwen2.5 0.5B Instruct CUDA")),
    "ai2apps/model-qwen3-asr-0-6b-cuda": _install("0.1.3", "ai2apps.model.qwen3-asr-0.6b-cuda", ("ai2apps.model.qwen3-asr-0.6b-cuda/qwen3-asr-0.6b", "Qwen3 ASR 0.6B CUDA")),
    "ai2apps/model-qwen3-asr-06b": _install("0.1.1", "ai2apps.model.qwen3-asr-0.6b", ("ai2apps.model.qwen3-asr-0.6b/4bit", "Qwen3 ASR 0.6B 4-bit")),
    "ai2apps/model-qwen3-tts-06b": _install("0.2.1", "ai2apps.model.qwen3-tts-0.6b", ("ai2apps.model.qwen3-tts-0.6b/custom-voice-6bit", "Qwen3 TTS 0.6B CustomVoice 6-bit")),
    "ai2apps/model-qwen3-tts-17b": _install("0.1.1", "ai2apps.model.qwen3-tts-1.7b", ("ai2apps.model.qwen3-tts-1.7b/custom-voice-8bit", "Qwen3 TTS 1.7B CustomVoice 8-bit"), ("ai2apps.model.qwen3-tts-1.7b/base-5bit", "Qwen3 TTS 1.7B Base 5-bit"), ("ai2apps.model.qwen3-tts-1.7b/voice-design-5bit", "Qwen3 TTS 1.7B VoiceDesign 5-bit")),
    "ai2apps/model-qwen3-vl-2b-cuda": _install("0.1.1", "ai2apps.model.qwen3-vl-2b-cuda", ("ai2apps.model.qwen3-vl-2b-cuda/qwen3-vl-2b-instruct", "Qwen3 VL 2B Instruct CUDA")),
    "ai2apps/model-qwen35": _install("0.1.2", "ai2apps.qwen35", ("ai2apps.qwen35/qwen3.5-2b-4bit", "Qwen3.5 2B 4-bit"), ("ai2apps.qwen35/qwen3.5-0.8b-4bit", "Qwen3.5 0.8B 4-bit")),
    "ai2apps/model-qwen36-35b": _install("0.3.4", "ai2apps.model.qwen36-35b", ("ai2apps.model.qwen36-35b/qwen3.6-35b-a3b-4bit", "Qwen3.6 35B A3B 4-bit")),
    "ai2apps/model-qwen38": _install("0.3.3", "ai2apps.model.qwen38", ("ai2apps.model.qwen38/qwen3.8-27b-nvfp4", "Qwen3.8 27B NVFP4")),
    "ai2apps/model-qwen38-flash-next-4bit": _install("0.1.4", "ai2apps.model.qwen38-flash-next-4bit", ("ai2apps.model.qwen38-flash-next-4bit/qwen3.8-flash-next-mlx-4bit", "Qwen3.8 Flash Next 4-bit")),
    "ai2apps/model-rvc-mlx": _install("0.1.0", "ai2apps.model.rvc-mlx", ("ai2apps.model.rvc-mlx/serena-e70", "MLX-RVC Serena e70")),
    "ai2apps/model-seed-vc-v2-mlx": _install("0.1.0", "ai2apps.model.seed-vc-v2-mlx", ("ai2apps.model.seed-vc-v2-mlx/default", "MLX Seed-VC v2")),
    "ai2apps/model-sensevoice-small": _install("0.2.2", "ai2apps.model.sensevoice-small", ("ai2apps.model.sensevoice-small/default", "SenseVoice Small")),
    "ai2apps/model-vibevoice-05b": _install("0.1.1", "ai2apps.model.vibevoice-0.5b", ("ai2apps.model.vibevoice-0.5b/realtime-4bit", "VibeVoice Realtime 0.5B 4-bit")),
    "ai2apps/model-z-image-mlx": _install("0.1.3", "ai2apps.model.z-image-mlx", ("ai2apps.model.z-image-mlx/turbo", "Z-Image Turbo MLX")),
    # Cloud currently rejects the optional modelInstall projection; source and
    # signed service.yaml retain the real model declaration. Bound to 0.1.0.
    "ai2apps/model-z-image-base-mlx": _install("0.1.0", "ai2apps.model.z-image-base-mlx", ("ai2apps.model.z-image-base-mlx/base", "Z-Image Base MLX")),
    "ai2apps/punctuation-restorer": _install("0.1.1", "ai2apps.model.punctuation-restorer", ("ai2apps.model.punctuation-restorer/default", "CT-Transformer Punctuation Restorer")),
}


def validate_model_install(value: Any) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {"serviceKey", "models"}:
        raise ValueError("modelInstall must contain exactly serviceKey and models")
    service_key = value.get("serviceKey")
    models = value.get("models")
    if not isinstance(service_key, str) or not _SERVICE_KEY.fullmatch(service_key):
        raise ValueError("modelInstall.serviceKey is invalid")
    if not isinstance(models, list) or not 1 <= len(models) <= 32:
        raise ValueError("modelInstall.models must contain 1 through 32 entries")
    normalized = []
    seen: set[str] = set()
    for index, model in enumerate(models):
        if not isinstance(model, dict) or set(model) != {"id", "label", "recommended"}:
            raise ValueError(f"modelInstall.models[{index}] is invalid")
        model_id = model.get("id")
        label = model.get("label")
        recommended = model.get("recommended")
        if not isinstance(model_id, str) or not _MODEL_ID.fullmatch(model_id) or not model_id.startswith(service_key + "/") or model_id in seen:
            raise ValueError(f"modelInstall.models[{index}].id is invalid")
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 160:
            raise ValueError(f"modelInstall.models[{index}].label is invalid")
        if not isinstance(recommended, bool):
            raise ValueError(f"modelInstall.models[{index}].recommended must be boolean")
        seen.add(model_id)
        normalized.append({"id": model_id, "label": label.strip(), "recommended": recommended})
    if sum(1 for model in normalized if model["recommended"]) != 1:
        raise ValueError("modelInstall.models must declare exactly one recommended model")
    return {"serviceKey": service_key, "models": normalized}


def legacy_model_install(package_id: str | None, version: str | None) -> dict[str, object] | None:
    row = LEGACY_MODEL_INSTALLS.get(str(package_id or ""))
    if row is None:
        return None
    if version:
        try:
            if Version(version) > Version(str(row["throughVersion"])):
                return None
        except InvalidVersion:
            return None
    result = {key: value for key, value in row.items() if key != "throughVersion"}
    result["source"] = "legacy-map"
    return result


def validate_model_profile(value: Any) -> dict[str, object]:
    """Validate signed, Publisher-supplied model card facts and benchmarks."""

    if not isinstance(value, dict) or set(value) - {"runtimeMemoryBytes"} != {
        "sizeBytes",
        "minimumMemoryBytes",
        "scores",
        "benchmark",
    }:
        raise ValueError(
            "modelProfile must contain exactly sizeBytes, minimumMemoryBytes, scores, and benchmark"
        )
    for key in ("sizeBytes", "minimumMemoryBytes", *(["runtimeMemoryBytes"] if "runtimeMemoryBytes" in value else [])):
        if not isinstance(value[key], int) or isinstance(value[key], bool) or value[key] <= 0:
            raise ValueError(f"modelProfile.{key} must be a positive integer")
    scores = value["scores"]
    if not isinstance(scores, dict) or set(scores) != {"speed", "capability"}:
        raise ValueError("modelProfile.scores must contain exactly speed and capability")
    if any(
        not isinstance(scores[key], int)
        or isinstance(scores[key], bool)
        or not 1 <= scores[key] <= 5
        for key in ("speed", "capability")
    ):
        raise ValueError("modelProfile scores must be integers from 1 through 5")
    benchmark = value["benchmark"]
    if not isinstance(benchmark, dict) or set(benchmark) != {"label", "device"}:
        raise ValueError("modelProfile.benchmark must contain exactly label and device")
    if any(
        not isinstance(benchmark[key], str) or not 1 <= len(benchmark[key].strip()) <= 120
        for key in ("label", "device")
    ):
        raise ValueError("modelProfile benchmark label and device must be non-empty strings")
    return {
        "sizeBytes": value["sizeBytes"],
        **({"runtimeMemoryBytes": value["runtimeMemoryBytes"]} if "runtimeMemoryBytes" in value else {}),
        "minimumMemoryBytes": value["minimumMemoryBytes"],
        "scores": {"speed": scores["speed"], "capability": scores["capability"]},
        "benchmark": {
            "label": benchmark["label"].strip(),
            "device": benchmark["device"].strip(),
        },
    }


def legacy_model_profile(package_id: str | None, version: str | None) -> dict[str, object] | None:
    row = LEGACY_MODEL_PROFILES.get(str(package_id or ""))
    if row is None:
        return None
    if version:
        try:
            if Version(version) > Version(str(row["throughVersion"])):
                return None
        except InvalidVersion:
            return None
    result = {key: value for key, value in row.items() if key != "throughVersion"}
    result["source"] = "legacy-map"
    return result


def _catalog_package_identity(
    value: dict[str, Any],
    *,
    manifest_package: dict[str, Any],
    latest_release: dict[str, Any],
) -> tuple[str | None, str | None, str]:
    """Read identity from both Registry row and catalog-detail shapes."""

    catalog_package = (
        value.get("package") if isinstance(value.get("package"), dict) else {}
    )
    package_id = (
        value.get("packageId")
        or value.get("package_id")
        or value.get("id")
        or catalog_package.get("packageId")
        or catalog_package.get("package_id")
        or catalog_package.get("id")
        or manifest_package.get("id")
    )
    version = (
        value.get("version")
        or value.get("latestVersion")
        or value.get("latest_version")
        or catalog_package.get("latestVersion")
        or catalog_package.get("latest_version")
        or catalog_package.get("version")
        or latest_release.get("version")
        or manifest_package.get("version")
    )
    package_type = str(
        value.get("packageType")
        or value.get("package_type")
        or value.get("type")
        or catalog_package.get("packageType")
        or catalog_package.get("package_type")
        or catalog_package.get("type")
        or latest_release.get("packageType")
        or latest_release.get("package_type")
        or manifest_package.get("type")
        or ""
    )
    return (
        package_id if isinstance(package_id, str) else None,
        version if isinstance(version, str) else None,
        package_type,
    )


def catalog_model_profile(value: dict[str, Any]) -> dict[str, object] | None:
    manifest = value.get("manifest")
    latest_release: dict[str, Any] = {}
    for release_key in ("latestRelease", "latest"):
        release = value.get(release_key)
        if isinstance(release, dict):
            latest_release = release
            if not isinstance(manifest, dict) and isinstance(release.get("manifest"), dict):
                manifest = release["manifest"]
            break
    if not isinstance(manifest, dict):
        manifest = {}
    package = manifest.get("package") if isinstance(manifest.get("package"), dict) else {}
    raw = manifest.get("modelProfile")
    if not isinstance(raw, dict) and isinstance(value.get("modelProfile"), dict):
        raw = value["modelProfile"]
    if isinstance(raw, dict):
        candidate = {key: raw.get(key) for key in ("sizeBytes", "minimumMemoryBytes", "scores", "benchmark")}
        if "runtimeMemoryBytes" in raw:
            candidate["runtimeMemoryBytes"] = raw["runtimeMemoryBytes"]
        try:
            resolved = validate_model_profile(candidate)
        except ValueError:
            resolved = None
        if resolved is not None:
            resolved["source"] = (
                raw.get("source")
                if raw.get("source") in {"manifest", "legacy-map"}
                else "manifest"
            )
            return resolved
    package_id, version, _package_type = _catalog_package_identity(
        value,
        manifest_package=package,
        latest_release=latest_release,
    )
    return legacy_model_profile(package_id, version)


def catalog_model_install(value: dict[str, Any]) -> dict[str, object] | None:
    """Resolve the signed or version-bounded ACPF install declaration."""

    manifest = value.get("manifest")
    latest_release: dict[str, Any] = {}
    for release_key in ("latestRelease", "latest"):
        release = value.get(release_key)
        if isinstance(release, dict):
            latest_release = release
            if not isinstance(manifest, dict) and isinstance(release.get("manifest"), dict):
                manifest = release["manifest"]
            break
    if not isinstance(manifest, dict):
        manifest = {}
    package = manifest.get("package") if isinstance(manifest.get("package"), dict) else {}
    raw = manifest.get("modelInstall")
    if not isinstance(raw, dict) and isinstance(value.get("modelInstall"), dict):
        raw = value["modelInstall"]
    if isinstance(raw, dict):
        try:
            resolved = validate_model_install(raw)
        except ValueError:
            resolved = None
        if resolved is not None:
            resolved["source"] = (
                raw.get("source")
                if raw.get("source") in {"manifest", "legacy-map"}
                else "manifest"
            )
            return resolved
    package_id, version, _package_type = _catalog_package_identity(
        value,
        manifest_package=package,
        latest_release=latest_release,
    )
    return legacy_model_install(package_id, version)


def validate_discovery(value: Any, *, package_type: str) -> dict[str, object]:
    """Validate and normalize signed Package discovery metadata."""

    if not isinstance(value, dict) or set(value) != {"kind", "categories", "tasks"}:
        raise ValueError("discovery must contain exactly kind, categories, and tasks")
    if value.get("kind") != "model":
        raise ValueError("discovery.kind must be model")
    if package_type != "service":
        raise ValueError("model discovery metadata is only valid for Service Packages")
    categories = value.get("categories")
    if (
        not isinstance(categories, list)
        or not 1 <= len(categories) <= len(MODEL_CATEGORIES)
        or not all(isinstance(item, str) and item in MODEL_CATEGORIES for item in categories)
        or len(set(categories)) != len(categories)
    ):
        raise ValueError(
            "discovery.categories must be unique supported model categories"
        )
    tasks = value.get("tasks")
    if (
        not isinstance(tasks, list)
        or not 1 <= len(tasks) <= 32
        or not all(isinstance(item, str) and len(item) <= 64 and _TASK.fullmatch(item) for item in tasks)
        or len(set(tasks)) != len(tasks)
    ):
        raise ValueError("discovery.tasks must be unique lower-kebab-case identifiers")
    return {"kind": "model", "categories": list(categories), "tasks": list(tasks)}


def legacy_model_discovery(
    package_id: str | None, version: str | None
) -> dict[str, object] | None:
    row = LEGACY_MODEL_DISCOVERY.get(str(package_id or ""))
    if row is None:
        return None
    if version:
        try:
            if Version(version) > Version(str(row["throughVersion"])):
                return None
        except InvalidVersion:
            return None
    return {
        "kind": "model",
        "categories": list(row["categories"]),
        "tasks": list(row["tasks"]),
        "source": "legacy-map",
    }


def catalog_discovery(value: dict[str, Any]) -> dict[str, object] | None:
    """Resolve signed or legacy discovery metadata from a Registry row."""

    manifest = value.get("manifest")
    latest_release: dict[str, Any] = {}
    for release_key in ("latestRelease", "latest"):
        release = value.get(release_key)
        if isinstance(release, dict):
            latest_release = release
            if not isinstance(manifest, dict) and isinstance(
                release.get("manifest"), dict
            ):
                manifest = release["manifest"]
            break
    if not isinstance(manifest, dict):
        manifest = {}
    package = manifest.get("package") if isinstance(manifest.get("package"), dict) else {}
    raw = manifest.get("discovery")
    if not isinstance(raw, dict) and isinstance(value.get("discovery"), dict):
        raw = value["discovery"]
    package_id, version, package_type = _catalog_package_identity(
        value,
        manifest_package=package,
        latest_release=latest_release,
    )
    if isinstance(raw, dict):
        try:
            candidate = {
                key: raw.get(key) for key in ("kind", "categories", "tasks")
            }
            if not set(raw).issubset({"kind", "categories", "tasks", "source"}):
                raise ValueError("unexpected discovery metadata")
            resolved = validate_discovery(candidate, package_type=package_type)
        except ValueError:
            resolved = None
        if resolved is not None:
            resolved["source"] = (
                raw.get("source")
                if raw.get("source") in {"manifest", "legacy-map"}
                else "manifest"
            )
            return resolved
    return legacy_model_discovery(package_id, version)


def is_legacy_model_release(package_id: str, version: str) -> bool:
    return legacy_model_discovery(package_id, version) is not None
