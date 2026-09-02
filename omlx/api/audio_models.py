# SPDX-License-Identifier: Apache-2.0
"""
Pydantic models for OpenAI-compatible audio API.

These models define the request and response schemas for:
- Audio transcription (speech-to-text)
- Audio speech synthesis (text-to-speech)
"""

from typing import Any, List, Optional

from pydantic import BaseModel


class AudioTranscriptionRequest(BaseModel):
    """OpenAI-compatible audio transcription request."""

    model: str
    language: Optional[str] = None
    prompt: Optional[str] = None
    response_format: Optional[str] = "json"
    temperature: Optional[float] = 0.0


class AudioTranscriptionResponse(BaseModel):
    text: str
    language: Optional[str] = None
    duration: Optional[float] = None
    segments: Optional[List[dict]] = None


class AudioSpeechRequest(BaseModel):
    model: str
    input: Optional[str] = None
    dialogue: Optional[List[dict[str, Any]]] = None
    voice: Optional[str] = None
    language: Optional[str] = None
    instructions: Optional[str] = None
    style: Optional[dict[str, Any]] = None
    speed: Optional[float] = 1.0
    response_format: Optional[str] = "wav"
    ref_audio: Optional[str] = None
    ref_audio_format: Optional[str] = "wav"
    ref_text: Optional[str] = None
    temperature: Optional[float] = None
    top_k: Optional[int] = None
    top_p: Optional[float] = None
    repetition_penalty: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    streaming_interval: Optional[float] = None


class AudioProcessRequest(BaseModel):
    """Request model for audio processing (speech enhancement / STS).

    Used by POST /v1/audio/process — the audio file is submitted as a
    multipart upload alongside this model field.
    """

    model: str
