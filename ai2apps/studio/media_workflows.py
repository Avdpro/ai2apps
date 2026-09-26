"""Trusted, model-free media assembly helpers for Studio capability workflows."""

from __future__ import annotations

import io
import re
import unicodedata
import wave
from collections.abc import Callable
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


_TEXT_ATOM = re.compile(
    r"[\u3400-\u9fff]|[^\W\d_]+(?:['’][^\W\d_]+)*|\d+(?:[.,]\d+)*|[^\s]",
    re.UNICODE,
)
_NO_LEADING_SPACE = frozenset(",.!?;:，。！？；：、)]}）】》」』")
_NO_TRAILING_SPACE = frozenset("([{（【《「『")
_STRONG_CUE_END = frozenset(".!?。！？")
_SOFT_CUE_END = frozenset(",;:，；：、")
_CAPTION_SIZE_RATIOS = {
    "small": 0.040,
    "medium": 0.048,
    "large": 0.058,
    "extra_large": 0.070,
}
_CAPTION_BACKGROUND_STYLES = frozenset({"outline", "box"})


def _display_units(value: str) -> int:
    return sum(
        2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
        for character in value
        if not character.isspace()
    )


def _join_atoms(values: list[str]) -> str:
    result = ""
    for raw in values:
        value = str(raw or "").strip()
        if not value:
            continue
        if (
            result
            and value[0] not in _NO_LEADING_SPACE
            and result[-1] not in _NO_TRAILING_SPACE
            and result[-1].isascii()
            and value[0].isascii()
            and (result[-1].isalnum() or result[-1] in "'’")
            and (value[0].isalnum() or value[0] in "'’")
        ):
            result += " "
        result += value
    return result.strip()


def split_subtitle_segments(
    segments: list[dict[str, Any]],
    *,
    max_duration: float = 4.0,
    max_units: int = 42,
) -> list[dict[str, Any]]:
    """Turn ASR-sized segments into short, readable subtitle cues."""

    if max_duration <= 0 or max_units <= 0:
        raise ValueError("Subtitle cue limits must be positive")
    result: list[dict[str, Any]] = []
    for segment in segments:
        start = max(0.0, float(segment.get("start") or 0))
        end = max(start, float(segment.get("end") or start))
        text = str(segment.get("text") or "").strip()
        words = [
            word
            for word in (segment.get("words") or [])
            if isinstance(word, dict)
            and word.get("start") is not None
            and word.get("end") is not None
            and float(word["end"]) > float(word["start"])
            and str(word.get("word", word.get("text", ""))).strip()
        ]
        atoms = _TEXT_ATOM.findall(text)
        total_units = max(1, sum(max(1, _display_units(atom)) for atom in atoms))
        duration = end - start
        hard_duration = max_duration * 1.4
        hard_units = round(max_units * 1.25)
        text_chunks: list[tuple[str, int]] = []
        current: list[str] = []
        current_units = 0
        last_soft_index = -1
        for atom in atoms:
            current.append(atom)
            current_units += max(1, _display_units(atom))
            if atom in _SOFT_CUE_END:
                last_soft_index = len(current) - 1
            estimated_duration = duration * current_units / total_units
            natural_end = atom in _STRONG_CUE_END
            clause_end = atom in _SOFT_CUE_END and (
                estimated_duration >= max_duration or current_units >= max_units
            )
            hard_end = (
                estimated_duration >= hard_duration or current_units >= hard_units
            )
            if natural_end or clause_end:
                text_chunks.append((_join_atoms(current), current_units))
                current = []
                current_units = 0
                last_soft_index = -1
            elif hard_end:
                split_at = last_soft_index + 1 if last_soft_index >= 0 else len(current)
                head = current[:split_at]
                tail = current[split_at:]
                head_units = sum(max(1, _display_units(item)) for item in head)
                text_chunks.append((_join_atoms(head), head_units))
                current = tail
                current_units = sum(max(1, _display_units(item)) for item in tail)
                last_soft_index = max(
                    (index for index, item in enumerate(tail) if item in _SOFT_CUE_END),
                    default=-1,
                )
        if current:
            text_chunks.append((_join_atoms(current), current_units))

        chunks: list[tuple[float, float, str, list[dict[str, Any]]]] = []
        consumed_units = 0
        word_cursor = 0
        for index, (chunk_text, chunk_units) in enumerate(text_chunks):
            consumed_units += chunk_units
            if words:
                next_word = (
                    len(words)
                    if index == len(text_chunks) - 1
                    else max(
                        word_cursor + 1,
                        min(
                            len(words), round(len(words) * consumed_units / total_units)
                        ),
                    )
                )
                cue_words = words[word_cursor:next_word]
                if cue_words:
                    cue_start = float(cue_words[0]["start"])
                    cue_end = float(cue_words[-1]["end"])
                else:
                    cue_start = (
                        start + duration * (consumed_units - chunk_units) / total_units
                    )
                    cue_end = start + duration * consumed_units / total_units
                word_cursor = next_word
            else:
                cue_words = []
                cue_start = (
                    start + duration * (consumed_units - chunk_units) / total_units
                )
                cue_end = start + duration * consumed_units / total_units
            chunks.append((cue_start, cue_end, chunk_text, cue_words))
        for cue_start, cue_end, cue_text, cue_words in chunks:
            if not cue_text:
                continue
            cue = {
                **segment,
                "start": max(start, cue_start),
                "end": min(end, max(cue_start, cue_end)),
                "text": cue_text,
            }
            if "words" in segment:
                cue["words"] = cue_words
            result.append(cue)
    return result


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
        if float(segment.get("start") or 0) <= seconds < float(segment.get("end") or 0):
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


def _wrap_caption_lines(
    draw: ImageDraw.ImageDraw,
    value: str,
    font: Any,
    max_width: int,
    background_style: str = "outline",
) -> list[str]:
    stroke_width = _caption_stroke_width(font, background_style)
    lines: list[str] = []
    for paragraph in value.splitlines() or [value]:
        atoms: list[str] = []
        for atom in _TEXT_ATOM.findall(paragraph):
            box = draw.textbbox((0, 0), atom, font=font, stroke_width=stroke_width)
            atoms.extend(list(atom) if box[2] - box[0] > max_width else [atom])
        current: list[str] = []
        for atom in atoms:
            candidate = _join_atoms([*current, atom])
            box = draw.textbbox((0, 0), candidate, font=font, stroke_width=stroke_width)
            if current and box[2] - box[0] > max_width:
                lines.append(_join_atoms(current))
                current = [atom]
            else:
                current.append(atom)
        if current:
            lines.append(_join_atoms(current))
    return lines or [""]


def _caption_stroke_width(font: Any, background_style: str = "outline") -> int:
    """Use a scale-aware outline that remains readable without a backdrop."""

    size = int(getattr(font, "size", 18))
    if background_style == "box":
        return max(1, round(size * 0.04))
    return max(3, round(size * 0.14))


def _caption_layout(
    draw: ImageDraw.ImageDraw,
    value: str,
    *,
    width: int,
    height: int,
    font_size: str = "large",
    background_style: str = "outline",
) -> tuple[str, Any, tuple[int, int, int, int], int, int, int]:
    if font_size not in _CAPTION_SIZE_RATIOS:
        raise ValueError("Unsupported subtitle font size")
    if background_style not in _CAPTION_BACKGROUND_STYLES:
        raise ValueError("Unsupported subtitle background style")
    safe_x = max(8, round(width * 0.05))
    safe_bottom = max(8, round(height * 0.06))
    preferred_size = max(14, round(height * _CAPTION_SIZE_RATIOS[font_size]))
    minimum_size = 10
    preferred_font = _font(preferred_size)
    preferred_stroke = _caption_stroke_width(preferred_font, background_style)
    preferred_padding = (
        max(5, round(preferred_size / 3))
        if background_style == "box"
        else preferred_stroke
    )
    max_width = max(24, width - 2 * (safe_x + preferred_padding))
    selected_font = _font(preferred_size)
    selected_lines: list[str] = []
    for size in range(preferred_size, minimum_size - 1, -2):
        candidate_font = _font(size)
        candidate_lines = _wrap_caption_lines(
            draw,
            value,
            candidate_font,
            max_width,
            background_style,
        )
        selected_font = candidate_font
        selected_lines = candidate_lines
        if len(candidate_lines) <= 2:
            break
    caption = "\n".join(selected_lines[:2])
    stroke_width = _caption_stroke_width(selected_font, background_style)
    box = draw.multiline_textbbox(
        (0, 0),
        caption,
        font=selected_font,
        align="center",
        stroke_width=stroke_width,
    )
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    padding = (
        max(5, round(int(getattr(selected_font, "size", minimum_size)) / 3))
        if background_style == "box"
        else stroke_width
    )
    x = max(safe_x + padding, (width - text_width) // 2)
    x = min(x, max(safe_x + padding, width - safe_x - padding - text_width))
    y = max(padding + 2, height - safe_bottom - padding - text_height)
    return caption, selected_font, box, x, y, padding


def _draw_caption(
    image: Any,
    value: str,
    *,
    width: int,
    height: int,
    font_size: str = "large",
    background_style: str = "outline",
) -> None:
    """Draw a safely fitted caption using the selected presentation style."""

    draw = ImageDraw.Draw(image, "RGBA")
    caption, font, box, x, y, padding = _caption_layout(
        draw,
        value,
        width=width,
        height=height,
        font_size=font_size,
        background_style=background_style,
    )
    stroke_width = _caption_stroke_width(font, background_style)
    if background_style == "box":
        text_width = box[2] - box[0]
        text_height = box[3] - box[1]
        draw.rounded_rectangle(
            (
                x - padding,
                y - padding,
                x + text_width + padding,
                y + text_height + padding,
            ),
            radius=padding,
            fill=(0, 0, 0, 155),
        )
    draw.multiline_text(
        (x, y),
        caption,
        font=font,
        fill="white",
        align="center",
        stroke_width=stroke_width,
        stroke_fill="black",
    )


def burn_subtitles(
    video: bytes,
    segments: list[dict[str, Any]],
    *,
    translations: list[str] | None = None,
    bilingual: bool = False,
    speaker_names: dict[str, str] | None = None,
    font_size: str = "large",
    background_style: str = "outline",
    progress: Callable[[int], None] | None = None,
) -> bytes:
    """Burn subtitles into an MP4 while copying its first audio track."""

    if font_size not in _CAPTION_SIZE_RATIOS:
        raise StudioMediaError(
            "subtitle_style_invalid", "Unsupported subtitle font size"
        )
    if background_style not in _CAPTION_BACKGROUND_STYLES:
        raise StudioMediaError(
            "subtitle_style_invalid", "Unsupported subtitle background style"
        )

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
        total_frames = int(input_video.frames or 0)
        if total_frames <= 0 and input_video.duration is not None:
            total_frames = max(
                1,
                round(
                    float(input_video.duration * input_video.time_base) * float(rate)
                ),
            )
        last_progress = -1
        if progress is not None:
            progress(0)
        for frame_index, frame in enumerate(input_container.decode(input_video)):
            seconds = float(frame.time or (frame_index / float(rate)))
            value = _active_text(
                seconds, segments, translations, bilingual, speaker_names
            )
            image = frame.to_image().convert("RGB")
            if value:
                _draw_caption(
                    image,
                    value,
                    width=width,
                    height=height,
                    font_size=font_size,
                    background_style=background_style,
                )
            output_frame = av.VideoFrame.from_ndarray(
                np.asarray(image, dtype=np.uint8), format="rgb24"
            )
            output_frame.pts = frame_index
            output_frame.time_base = Fraction(rate.denominator, rate.numerator)
            for packet in output_video.encode(output_frame):
                output.mux(packet)
            if progress is not None and total_frames > 0:
                current_progress = min(95, round((frame_index + 1) * 95 / total_frames))
                if current_progress > last_progress:
                    last_progress = current_progress
                    progress(current_progress)
        for packet in output_video.encode(None):
            output.mux(packet)
        input_container.close()

        if input_audio is not None and output_audio is not None:
            if progress is not None:
                progress(97)
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
        if progress is not None:
            progress(100)
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
            resampler = av.AudioResampler(format="fltp", layout="stereo", rate=48_000)
            chunks = []
            for frame in container.decode(stream):
                chunks.extend(resampler.resample(frame))
            chunks.extend(resampler.resample(None))
            arrays = [frame.to_ndarray() for frame in chunks]
    except StudioMediaError:
        raise
    except (av.error.FFmpegError, OSError, TypeError, ValueError) as error:
        raise StudioMediaError(
            "audio_decode_failed", "Could not decode WAV artifact"
        ) from error
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


def audio_duration(data: bytes) -> float:
    """Return decoded audio duration in seconds using the shared 48 kHz path."""

    values, rate = _read_audio(data)
    return len(values) / rate


def _fit_audio_to_frames(
    values: np.ndarray, target_frames: int, *, rate: int
) -> np.ndarray:
    """Compress audio to an exact slot without changing its perceived pitch."""

    if target_frames <= 0:
        return np.empty((0, values.shape[1]), dtype=np.float32)
    if len(values) <= target_frames:
        return values
    speed = len(values) / target_frames
    shortest = min(len(values), target_frames)
    max_frame_size = 2 ** max(7, int(np.floor(np.log2(rate * 0.05))))
    frame_size = min(max_frame_size, 2 ** max(7, shortest.bit_length() - 1))
    hop = max(1, frame_size // 4)
    window = np.hanning(frame_size).astype(np.float32)
    padded_frames = max(
        frame_size,
        frame_size + hop * int(np.ceil(max(0, len(values) - frame_size) / hop)),
    )
    padded = np.pad(values, ((0, padded_frames - len(values)), (0, 0)))
    frames = np.stack(
        [
            padded[offset : offset + frame_size]
            for offset in range(0, padded_frames - frame_size + 1, hop)
        ],
        axis=0,
    )
    spectrum = np.fft.rfft(frames * window[None, :, None], axis=1)
    time_steps = np.arange(0, max(1, len(spectrum) - 1), speed)
    output_spectrum = np.empty(
        (len(time_steps), spectrum.shape[1], spectrum.shape[2]), dtype=np.complex64
    )
    phase_advance = (
        2 * np.pi * hop * np.arange(spectrum.shape[1], dtype=np.float32) / frame_size
    )[:, None]
    phase = np.angle(spectrum[0])
    for output_index, step in enumerate(time_steps):
        left = min(int(step), len(spectrum) - 1)
        right = min(left + 1, len(spectrum) - 1)
        fraction = step - left
        magnitude = (1 - fraction) * np.abs(spectrum[left]) + fraction * np.abs(
            spectrum[right]
        )
        output_spectrum[output_index] = magnitude * np.exp(1j * phase)
        delta = np.angle(spectrum[right]) - np.angle(spectrum[left]) - phase_advance
        delta -= 2 * np.pi * np.round(delta / (2 * np.pi))
        phase += phase_advance + delta
    output_length = frame_size + hop * max(0, len(output_spectrum) - 1)
    stretched = np.zeros((output_length, values.shape[1]), dtype=np.float32)
    weights = np.zeros(output_length, dtype=np.float32)
    for index, spectrum_frame in enumerate(output_spectrum):
        offset = index * hop
        frame = np.fft.irfft(spectrum_frame, n=frame_size, axis=0).real
        stretched[offset : offset + frame_size] += frame * window[:, None]
        weights[offset : offset + frame_size] += window**2
    nonzero = weights > 1e-8
    stretched[nonzero] /= weights[nonzero, None]
    if len(stretched) < target_frames:
        stretched = np.pad(stretched, ((0, target_frames - len(stretched)), (0, 0)))
    return stretched[:target_frames]


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
            "target_speaker_not_found",
            "The selected speaker has no transcript segments",
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


def mix_dubbed_segments(
    background_wav: bytes,
    speech_segments: list[bytes],
    segments: list[dict[str, Any]],
) -> bytes:
    """Place synthesized narration on the source timeline and preserve ambience.

    Phase 1 deliberately treats the video as single-narrator material. The
    original dialogue stem is omitted; only the separated background and the
    translated Character speech are mixed. Every clip is locked to its ASR
    start/end window. Any remaining overflow is compressed with a pitch-
    preserving time stretch instead of delaying later clips.
    """

    if len(speech_segments) != len(segments):
        raise StudioMediaError(
            "dub_segment_count_mismatch",
            "Synthesized speech does not match the translated segment count",
        )
    background, rate = _read_audio(background_wav)
    channels = background.shape[1]
    mixed = np.asarray(background, dtype=np.float32).copy()
    fade = max(1, round(rate * 0.015))
    for speech_wav, segment in zip(speech_segments, segments, strict=True):
        speech, _speech_rate = _read_audio(speech_wav)
        if speech.shape[1] == 1 and channels > 1:
            speech = np.repeat(speech, channels, axis=1)
        elif speech.shape[1] != channels:
            speech = speech[:, :channels]
        start = max(0, round(float(segment.get("start") or 0) * rate))
        segment_end = max(start, round(float(segment.get("end") or 0) * rate))
        if start >= len(mixed):
            break
        available = min(len(mixed), segment_end) - start
        if available <= 0:
            continue
        speech = _fit_audio_to_frames(speech, available, rate=rate)
        if not len(speech):
            continue
        ramp = min(fade, len(speech) // 2)
        if ramp:
            envelope = np.ones(len(speech), dtype=np.float32)
            envelope[:ramp] = np.linspace(0, 1, ramp, endpoint=False)
            envelope[-ramp:] = np.linspace(1, 0, ramp, endpoint=False)
            speech = speech * envelope[:, None]
        mixed[start : start + len(speech)] += speech
    peak = float(np.max(np.abs(mixed), initial=0))
    if peak > 1:
        mixed /= peak
    return _wav(mixed, rate)


def select_voice_clone_reference(
    audio_wav: bytes,
    segments: list[dict[str, Any]],
    *,
    target_seconds: float = 10.0,
    min_seconds: float = 1.0,
    max_seconds: float = 15.0,
) -> tuple[bytes, str, dict[str, float]]:
    """Select one dense, audible narration window for request-scoped cloning.

    The returned audio stays on the original timeline and its text is assembled
    only from ASR segments wholly represented by the selected window.  Nothing
    is persisted as a Voice Studio Character.
    """

    if min_seconds <= 0 or max_seconds < min_seconds:
        raise StudioMediaError(
            "voice_clone_reference_limits_invalid",
            "The voice-clone model declares invalid reference limits",
        )
    audio, rate = _read_audio(audio_wav)
    duration = len(audio) / rate
    usable = []
    for item in segments:
        start = max(0.0, float(item.get("start") or 0))
        end = min(duration, max(start, float(item.get("end") or start)))
        text = str(item.get("text") or "").strip()
        if text and end > start:
            usable.append((start, end, text))
    if not usable:
        raise StudioMediaError(
            "voice_clone_reference_unavailable",
            "No transcribed speech is available for temporary voice cloning",
        )

    target = min(max(float(target_seconds), min_seconds), max_seconds)
    mono = np.mean(audio, axis=1) if audio.shape[1] > 1 else audio[:, 0]
    candidates: list[tuple[float, float, float, str, float]] = []
    for first in range(len(usable)):
        speech_seconds = 0.0
        texts: list[str] = []
        for last in range(first, len(usable)):
            if last > first and usable[last][0] - usable[last - 1][1] > 2.0:
                break
            start = usable[first][0]
            end = usable[last][1]
            span = end - start
            if span > max_seconds:
                break
            speech_seconds += usable[last][1] - usable[last][0]
            texts.append(usable[last][2])
            if span < min_seconds:
                continue
            begin_frame = max(0, round(start * rate))
            end_frame = min(len(mono), round(end * rate))
            samples = mono[begin_frame:end_frame]
            if not len(samples):
                continue
            rms = float(np.sqrt(np.mean(np.square(samples), dtype=np.float64)))
            clipping = float(np.mean(np.abs(samples) >= 0.985))
            density = min(1.0, speech_seconds / max(span, 0.001))
            duration_score = 1.0 - min(1.0, abs(span - target) / max(target, 0.001))
            audible_score = min(1.0, rms / 0.08)
            score = duration_score * 2.0 + density * 1.5 + audible_score - clipping * 8.0
            candidates.append((score, start, end, " ".join(texts), rms))
    if not candidates:
        raise StudioMediaError(
            "voice_clone_reference_unavailable",
            "The narration has no continuous window that meets this model's reference duration",
        )
    _score, start, end, text, rms = max(candidates, key=lambda item: item[0])
    begin_frame = max(0, round(start * rate))
    end_frame = min(len(audio), round(end * rate))
    return (
        _wav(audio[begin_frame:end_frame], rate),
        text,
        {"start": start, "end": end, "duration": end - start, "rms": rms},
    )


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
