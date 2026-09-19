"""Trusted, model-free media assembly helpers for Studio capability workflows."""

from __future__ import annotations

import io
import math
import textwrap
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any

import av
import numpy as np
from PIL import ImageDraw, ImageFont


class StudioMediaError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def validate_video_media(video: bytes) -> None:
    """Reject non-video containers before a composite media workflow starts."""

    try:
        with av.open(io.BytesIO(video), mode="r") as container:
            if not container.streams.video:
                raise StudioMediaError(
                    "video_track_not_found", "Input has no video track"
                )
            if not container.streams.audio:
                raise StudioMediaError(
                    "audio_track_not_found", "Input video has no audio track"
                )
    except StudioMediaError:
        raise
    except (av.error.FFmpegError, OSError, ValueError) as error:
        raise StudioMediaError(
            "video_decode_failed", "Input is not a supported video container"
        ) from error


def _timestamp(seconds: float, *, separator: str) -> str:
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def _cue_text(segment: dict[str, Any], translated: str | None, bilingual: bool) -> str:
    original = str(segment.get("text") or "").strip()
    translated = (translated or "").strip()
    if translated and bilingual and translated != original:
        return f"{original}\n{translated}"
    return translated or original


def render_subtitles(
    segments: list[dict[str, Any]],
    *,
    output_format: str,
    translations: list[str] | None = None,
    bilingual: bool = False,
    speaker_names: dict[str, str] | None = None,
) -> bytes:
    """Serialize trusted transcript segments as SRT, WebVTT, or ASS."""

    normalized = output_format.lower()
    if normalized not in {"srt", "vtt", "ass"}:
        raise StudioMediaError("subtitle_format_invalid", "Unsupported subtitle format")
    if translations is not None and len(translations) != len(segments):
        raise StudioMediaError(
            "translation_count_mismatch", "Translation count does not match transcript"
        )
    names = speaker_names or {}

    def text(index: int, segment: dict[str, Any]) -> str:
        value = _cue_text(
            segment,
            None if translations is None else translations[index],
            bilingual,
        )
        speaker = str(segment.get("speaker") or "")
        return f"{names[speaker]}: {value}" if speaker in names else value

    if normalized == "vtt":
        lines = ["WEBVTT", ""]
        for index, segment in enumerate(segments):
            lines.extend(
                (
                    str(index + 1),
                    f"{_timestamp(segment.get('start', 0), separator='.')} --> "
                    f"{_timestamp(segment.get('end', 0), separator='.')}",
                    text(index, segment),
                    "",
                )
            )
        return "\n".join(lines).encode("utf-8")
    if normalized == "ass":
        lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Alignment, MarginL, MarginR, MarginV, "
            "BorderStyle, Outline, Shadow",
            "Style: Default,Arial,48,&H00FFFFFF,&H00000000,&H80000000,0,0,2,60,60,50,1,2,0",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Text",
        ]
        for index, segment in enumerate(segments):
            value = text(index, segment).replace("\n", r"\N").replace(",", r"\,")
            start = _timestamp(segment.get("start", 0), separator=".")[:-1]
            end = _timestamp(segment.get("end", 0), separator=".")[:-1]
            lines.append(f"Dialogue: 0,{start},{end},Default,{value}")
        return "\n".join(lines).encode("utf-8-sig")

    lines = []
    for index, segment in enumerate(segments):
        lines.extend(
            (
                str(index + 1),
                f"{_timestamp(segment.get('start', 0), separator=',')} --> "
                f"{_timestamp(segment.get('end', 0), separator=',')}",
                text(index, segment),
                "",
            )
        )
    return "\n".join(lines).encode("utf-8")


_FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _font(size: int):
    for candidate in _FONT_CANDIDATES:
        if not Path(candidate).is_file():
            continue
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default(size=max(10, size))


def _active_text(
    seconds: float,
    segments: list[dict[str, Any]],
    translations: list[str] | None,
    bilingual: bool,
    speaker_names: dict[str, str] | None,
) -> str:
    for index, segment in enumerate(segments):
        if float(segment.get("start") or 0) <= seconds < float(
            segment.get("end") or 0
        ):
            value = _cue_text(
                segment,
                None if translations is None else translations[index],
                bilingual,
            )
            speaker = str(segment.get("speaker") or "")
            return (
                f"{speaker_names[speaker]}: {value}"
                if speaker_names and speaker in speaker_names
                else value
            )
    return ""


def burn_subtitles(
    video: bytes,
    segments: list[dict[str, Any]],
    *,
    translations: list[str] | None = None,
    bilingual: bool = False,
    speaker_names: dict[str, str] | None = None,
) -> bytes:
    """Burn subtitles into an MP4 while copying its first audio track."""

    source = io.BytesIO(video)
    destination = io.BytesIO()
    try:
        input_container = av.open(source, mode="r")
        if not input_container.streams.video:
            raise StudioMediaError("video_track_not_found", "Input has no video track")
        input_video = input_container.streams.video[0]
        rate = input_video.average_rate or input_video.guessed_rate or Fraction(25, 1)
        width = int(input_video.codec_context.width)
        height = int(input_video.codec_context.height)
        audio_container = av.open(io.BytesIO(video), mode="r")
        input_audio = (
            audio_container.streams.audio[0] if audio_container.streams.audio else None
        )
        output = av.open(destination, mode="w", format="mp4")
        output_video = output.add_stream("libx264", rate=rate)
        output_video.width = width
        output_video.height = height
        output_video.pix_fmt = "yuv420p"
        output_audio = None
        if input_audio is not None:
            output_audio = output.add_stream("aac", rate=48_000)
            output_audio.layout = "stereo"
        font_size = max(18, round(height * 0.045))
        font = _font(font_size)
        for frame_index, frame in enumerate(input_container.decode(input_video)):
            seconds = float(frame.time or (frame_index / float(rate)))
            value = _active_text(
                seconds, segments, translations, bilingual, speaker_names
            )
            image = frame.to_image().convert("RGB")
            if value:
                draw = ImageDraw.Draw(image)
                max_chars = max(12, math.floor(width / max(font_size * 0.58, 1)))
                lines = []
                for paragraph in value.splitlines():
                    lines.extend(textwrap.wrap(paragraph, width=max_chars) or [""])
                caption = "\n".join(lines[-4:])
                box = draw.multiline_textbbox(
                    (0, 0), caption, font=font, align="center", stroke_width=2
                )
                text_width = box[2] - box[0]
                text_height = box[3] - box[1]
                x = max(20, (width - text_width) // 2)
                y = max(20, height - text_height - round(height * 0.07))
                padding = max(8, font_size // 3)
                draw.rounded_rectangle(
                    (x - padding, y - padding, x + text_width + padding, y + text_height + padding),
                    radius=padding,
                    fill=(0, 0, 0, 155),
                )
                draw.multiline_text(
                    (x, y),
                    caption,
                    font=font,
                    fill="white",
                    align="center",
                    stroke_width=2,
                    stroke_fill="black",
                )
            output_frame = av.VideoFrame.from_ndarray(
                np.asarray(image, dtype=np.uint8), format="rgb24"
            )
            output_frame.pts = frame_index
            output_frame.time_base = Fraction(rate.denominator, rate.numerator)
            for packet in output_video.encode(output_frame):
                output.mux(packet)
        for packet in output_video.encode(None):
            output.mux(packet)
        input_container.close()

        if input_audio is not None and output_audio is not None:
            resampler = av.AudioResampler(format="fltp", layout="stereo", rate=48_000)
            offset = 0
            for frame in audio_container.decode(input_audio):
                for converted in resampler.resample(frame):
                    converted.pts = offset
                    converted.time_base = Fraction(1, 48_000)
                    offset += converted.samples
                    for packet in output_audio.encode(converted):
                        output.mux(packet)
            for converted in resampler.resample(None):
                converted.pts = offset
                converted.time_base = Fraction(1, 48_000)
                offset += converted.samples
                for packet in output_audio.encode(converted):
                    output.mux(packet)
            for packet in output_audio.encode(None):
                output.mux(packet)
        audio_container.close()
        output.close()
    except StudioMediaError:
        raise
    except (av.error.FFmpegError, OSError, ValueError) as error:
        raise StudioMediaError(
            "subtitle_burn_in_failed", f"Could not render subtitled video: {error}"
        ) from error
    result = destination.getvalue()
    if not result:
        raise StudioMediaError(
            "subtitle_burn_in_failed", "Subtitled video produced no output"
        )
    return result


def _read_audio(data: bytes) -> tuple[np.ndarray, int]:
    try:
        with av.open(io.BytesIO(data), mode="r") as container:
            stream = next(
                (item for item in container.streams if item.type == "audio"), None
            )
            if stream is None:
                raise StudioMediaError(
                    "audio_track_not_found", "WAV artifact has no audio track"
                )
            resampler = av.AudioResampler(
                format="fltp", layout="stereo", rate=48_000
            )
            chunks = []
            for frame in container.decode(stream):
                chunks.extend(resampler.resample(frame))
            chunks.extend(resampler.resample(None))
            arrays = [frame.to_ndarray() for frame in chunks]
    except StudioMediaError:
        raise
    except (av.error.FFmpegError, OSError, TypeError, ValueError) as error:
        raise StudioMediaError("audio_decode_failed", "Could not decode WAV artifact") from error
    if not arrays:
        raise StudioMediaError("audio_decode_failed", "WAV artifact is empty")
    values = np.concatenate(arrays, axis=1).T
    return np.asarray(values, dtype=np.float32), 48_000


def _wav(values: np.ndarray, rate: int) -> bytes:
    output = io.BytesIO()
    normalized = np.asarray(values, dtype=np.float32)
    if normalized.ndim == 1:
        normalized = normalized[:, None]
    pcm = np.round(np.clip(normalized, -1, 1) * 32_767).astype("<i2")
    with wave.open(output, "wb") as target:
        target.setnchannels(pcm.shape[1])
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(pcm.tobytes())
    return output.getvalue()


def speaker_conversion_source(
    dialogue_wav: bytes,
    segments: list[dict[str, Any]],
    *,
    target_speaker: str,
) -> bytes:
    """Build a timeline-preserving mono voice-conversion source for one speaker."""

    dialogue, rate = _read_audio(dialogue_wav)
    mono = dialogue.mean(axis=1, keepdims=True)
    mask = _speaker_mask(len(mono), rate, segments, target_speaker)
    if not np.any(mask > 0):
        raise StudioMediaError(
            "target_speaker_not_found", "The selected speaker has no transcript segments"
        )
    return _wav(mono * mask[:, None], rate)


def _speaker_mask(
    frames: int,
    rate: int,
    segments: list[dict[str, Any]],
    target_speaker: str,
) -> np.ndarray:
    mask = np.zeros(frames, dtype=np.float32)
    fade = max(1, round(rate * 0.02))
    for segment in segments:
        if str(segment.get("speaker") or "") != target_speaker:
            continue
        start = max(0, min(frames, round(float(segment.get("start") or 0) * rate)))
        end = max(start, min(frames, round(float(segment.get("end") or 0) * rate)))
        if end <= start:
            continue
        mask[start:end] = 1
        ramp = min(fade, (end - start) // 2)
        if ramp:
            mask[start : start + ramp] = np.linspace(0, 1, ramp, endpoint=False)
            mask[end - ramp : end] = np.linspace(1, 0, ramp, endpoint=False)
    return mask


def mix_replaced_speaker(
    dialogue_wav: bytes,
    background_wav: bytes,
    converted_wav: bytes,
    segments: list[dict[str, Any]],
    *,
    target_speaker: str,
) -> bytes:
    """Replace target dialogue windows and preserve background/non-target dialogue."""

    dialogue, rate = _read_audio(dialogue_wav)
    background, _background_rate = _read_audio(background_wav)
    converted, _converted_rate = _read_audio(converted_wav)
    channels = max(dialogue.shape[1], background.shape[1])

    def channels_of(values: np.ndarray) -> np.ndarray:
        if values.shape[1] == channels:
            return values
        if values.shape[1] == 1:
            return np.repeat(values, channels, axis=1)
        return values[:, :channels]

    dialogue = channels_of(dialogue)
    background = channels_of(background)
    converted = channels_of(converted)
    frames = max(len(dialogue), len(background))

    def length_of(values: np.ndarray) -> np.ndarray:
        if len(values) >= frames:
            return values[:frames]
        return np.pad(values, ((0, frames - len(values)), (0, 0)))

    dialogue = length_of(dialogue)
    background = length_of(background)
    converted = length_of(converted)
    mask = _speaker_mask(frames, rate, segments, target_speaker)[:, None]
    mixed = background + dialogue * (1 - mask) + converted * mask
    peak = float(np.max(np.abs(mixed), initial=0))
    if peak > 1:
        mixed /= peak
    return _wav(mixed, rate)


def replace_video_audio(video: bytes, audio_wav: bytes) -> bytes:
    """Copy the original video stream and replace its audio with a WAV artifact."""

    destination = io.BytesIO()
    try:
        video_input = av.open(io.BytesIO(video), mode="r")
        if not video_input.streams.video:
            raise StudioMediaError("video_track_not_found", "Input has no video track")
        audio_input = av.open(io.BytesIO(audio_wav), mode="r")
        if not audio_input.streams.audio:
            raise StudioMediaError(
                "audio_track_not_found", "Replacement audio has no audio track"
            )
        output = av.open(destination, mode="w", format="mp4")
        output_video = output.add_stream_from_template(video_input.streams.video[0])
        output_audio = output.add_stream("aac", rate=48_000)
        output_audio.layout = "stereo"
        for packet in video_input.demux(video_input.streams.video[0]):
            if packet.dts is not None:
                packet.stream = output_video
                output.mux(packet)
        resampler = av.AudioResampler(format="fltp", layout="stereo", rate=48_000)
        offset = 0
        for frame in audio_input.decode(audio_input.streams.audio[0]):
            for converted in resampler.resample(frame):
                converted.pts = offset
                converted.time_base = Fraction(1, 48_000)
                offset += converted.samples
                for packet in output_audio.encode(converted):
                    output.mux(packet)
        for converted in resampler.resample(None):
            converted.pts = offset
            converted.time_base = Fraction(1, 48_000)
            offset += converted.samples
            for packet in output_audio.encode(converted):
                output.mux(packet)
        for packet in output_audio.encode(None):
            output.mux(packet)
        output.close()
        video_input.close()
        audio_input.close()
    except StudioMediaError:
        raise
    except (av.error.FFmpegError, OSError, ValueError) as error:
        raise StudioMediaError(
            "video_audio_mux_failed", f"Could not replace video audio: {error}"
        ) from error
    result = destination.getvalue()
    if not result:
        raise StudioMediaError(
            "video_audio_mux_failed", "Video audio replacement produced no output"
        )
    return result
