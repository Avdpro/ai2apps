"""Private media references and deterministic rendering for Video Composer."""

from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import os
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal

import av
import numpy as np
from PIL import Image, ImageChops, ImageOps
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ComposerError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int = 422) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class ComposerSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    width: int = Field(default=1280, ge=64, le=3840)
    height: int = Field(default=720, ge=64, le=2160)
    fps: int = Field(default=30, ge=1, le=60)
    background: str = Field(default="#000000", pattern=r"^#[0-9a-fA-F]{6}$")
    snapping: bool = True


class ComposerTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    kind: Literal["video", "audio"]
    name: str = Field(min_length=1, max_length=120)
    order: int = Field(ge=0, le=99)
    muted: bool = False
    locked: bool = False


class ComposerKeyframe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    frame: int = Field(ge=0, le=216_000)
    endpoint: Literal["start", "end"] | None = None
    transition: Literal["hold", "linear", "ease"] = "linear"
    x: int | None = Field(default=None, ge=-16384, le=16384)
    y: int | None = Field(default=None, ge=-16384, le=16384)
    width: int | None = Field(default=None, ge=16, le=16384)
    height: int | None = Field(default=None, ge=16, le=16384)
    opacity: float | None = Field(default=None, ge=0, le=1)


class ComposerClip(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    source_id: str = Field(alias="sourceId", min_length=1, max_length=100)
    track_id: str = Field(alias="trackId", min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    start: float = Field(ge=0, le=3600)
    source_start: float = Field(default=0, alias="sourceStart", ge=0, le=86400)
    duration: float = Field(gt=0, le=3600)
    speed: float = Field(default=1, ge=0.25, le=4)
    volume: float = Field(default=1, ge=0, le=4)
    fade_in: float = Field(default=0, alias="fadeIn", ge=0, le=30)
    fade_out: float = Field(default=0, alias="fadeOut", ge=0, le=30)
    x: int = Field(default=0, ge=-16384, le=16384)
    y: int = Field(default=0, ge=-16384, le=16384)
    width: int | None = Field(default=None, ge=16, le=16384)
    height: int | None = Field(default=None, ge=16, le=16384)
    opacity: float = Field(default=1, ge=0, le=1)
    audio_enabled: bool = Field(default=True, alias="audioEnabled")
    mask_source_id: str | None = Field(default=None, alias="maskSourceId", max_length=100)
    group_id: str | None = Field(default=None, alias="groupId", max_length=80)
    color: str = Field(default="#3b82f6", pattern=r"^#[0-9a-fA-F]{6}$")
    keyframes: list[ComposerKeyframe] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def validate_fades(self):
        if self.fade_in + self.fade_out > self.duration:
            raise ValueError("clip fades cannot exceed its timeline duration")
        return self


class ComposerProject(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    schema_name: Literal["ai2apps.video-composition/v1"] = Field(
        default="ai2apps.video-composition/v1", alias="schema"
    )
    title: str = Field(default="Untitled composition", min_length=1, max_length=160)
    settings: ComposerSettings = Field(default_factory=ComposerSettings)
    tracks: list[ComposerTrack] = Field(default_factory=list, max_length=20)
    clips: list[ComposerClip] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def validate_graph(self):
        fps = self.settings.fps
        track_kinds = {track.id: track.kind for track in self.tracks}
        for clip in self.clips:
            clip.start = round(round(clip.start * fps) / fps, 9)
            clip.duration = round(max(1, round(clip.duration * fps)) / fps, 9)
            clip.fade_in = min(clip.fade_in, clip.duration)
            clip.fade_out = min(clip.fade_out, max(0, clip.duration - clip.fade_in))
            duration_frames = max(1, round(clip.duration * fps))
            if track_kinds.get(clip.track_id) == "video":
                duration_frames = max(2, duration_frames)
                clip.duration = round(duration_frames / fps, 9)
                start = next((item for item in clip.keyframes if item.endpoint == "start"), None)
                if start is None:
                    start = next((item for item in clip.keyframes if item.frame == 0), None)
                if start is None:
                    start = ComposerKeyframe(
                        id=f"start-{clip.id}"[:80], frame=0, endpoint="start",
                        transition="hold", x=clip.x, y=clip.y,
                        width=clip.width or self.settings.width,
                        height=clip.height or self.settings.height, opacity=clip.opacity,
                    )
                    clip.keyframes.append(start)
                start.frame = 0
                start.endpoint = "start"
                start.transition = "hold"
                end_frame = duration_frames - 1
                end = next((item for item in clip.keyframes if item.endpoint == "end"), None)
                if end is None:
                    end = next((item for item in clip.keyframes if item.frame == end_frame and item is not start), None)
                if end is None:
                    source = max(clip.keyframes, key=lambda item: item.frame, default=start)
                    end = ComposerKeyframe(
                        id=f"end-{clip.id}"[:80], frame=end_frame, endpoint="end",
                        transition="linear", x=source.x, y=source.y,
                        width=source.width, height=source.height, opacity=source.opacity,
                    )
                    clip.keyframes.append(end)
                end.frame = end_frame
                end.endpoint = "end"
            frames = [keyframe.frame for keyframe in clip.keyframes]
            if len(frames) != len(set(frames)):
                raise ValueError("clip keyframes must use unique frame positions")
            if any(frame >= duration_frames for frame in frames):
                raise ValueError("clip keyframes must be inside the clip duration")
            clip.keyframes.sort(key=lambda keyframe: (keyframe.frame, keyframe.id))
        track_ids = {track.id for track in self.tracks}
        if len(track_ids) != len(self.tracks):
            raise ValueError("track IDs must be unique")
        clip_ids = {clip.id for clip in self.clips}
        if len(clip_ids) != len(self.clips):
            raise ValueError("clip IDs must be unique")
        if any(clip.track_id not in track_ids for clip in self.clips):
            raise ValueError("every clip must belong to a project track")
        clips_by_track = {
            track_id: sorted(
                (clip for clip in self.clips if clip.track_id == track_id),
                key=lambda clip: (clip.start, clip.id),
            )
            for track_id in track_ids
        }
        for clips in clips_by_track.values():
            for previous, current in zip(clips, clips[1:], strict=False):
                if current.start < previous.start + previous.duration - 1e-6:
                    raise ValueError("clips on the same track cannot overlap")
        groups: dict[str, list[ComposerClip]] = {}
        for clip in self.clips:
            if clip.group_id:
                groups.setdefault(clip.group_id, []).append(clip)
        for members in groups.values():
            if len(members) < 2 or len({clip.track_id for clip in members}) != 1:
                raise ValueError("a clip group must contain at least two clips on one track")
            ordered = clips_by_track[members[0].track_id]
            positions = sorted(ordered.index(clip) for clip in members)
            if positions != list(range(positions[0], positions[-1] + 1)):
                raise ValueError("clip group members must be adjacent on their track")
        if max((clip.start + clip.duration for clip in self.clips), default=0) > 600:
            raise ValueError("composition duration is limited to 10 minutes")
        return self

    @property
    def duration(self) -> float:
        return max((clip.start + clip.duration for clip in self.clips), default=0)


def _clip_visual_state(clip: ComposerClip, local_frame: int) -> dict[str, float]:
    state = {
        "x": float(clip.x),
        "y": float(clip.y),
        "width": float(clip.width or 0),
        "height": float(clip.height or 0),
        "opacity": float(clip.opacity),
    }
    previous_frame = 0
    previous = state
    for keyframe in clip.keyframes:
        target = {
            "x": previous["x"] if keyframe.x is None else float(keyframe.x),
            "y": previous["y"] if keyframe.y is None else float(keyframe.y),
            "width": previous["width"] if keyframe.width is None else float(keyframe.width),
            "height": previous["height"] if keyframe.height is None else float(keyframe.height),
            "opacity": previous["opacity"] if keyframe.opacity is None else float(keyframe.opacity),
        }
        if local_frame >= keyframe.frame:
            previous_frame, previous = keyframe.frame, target
            continue
        if keyframe.transition == "hold" or keyframe.frame <= previous_frame:
            return previous
        progress = (local_frame - previous_frame) / (keyframe.frame - previous_frame)
        progress = max(0.0, min(1.0, progress))
        if keyframe.transition == "ease":
            progress = progress * progress * (3 - 2 * progress)
        return {name: previous[name] + (target[name] - previous[name]) * progress for name in previous}
    return previous


class ComposerSourceStore:
    """Persist native paths privately while exposing only scoped opaque IDs."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    @staticmethod
    def _scope(actor_id: str, installation_id: str, app_instance_id: str) -> str:
        raw = "\0".join((actor_id, installation_id, app_instance_id)).encode()
        return hashlib.sha256(raw).hexdigest()

    def _directory(self, actor_id: str, installation_id: str, app_instance_id: str) -> Path:
        directory = self.root / self._scope(actor_id, installation_id, app_instance_id)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        return directory

    def register(
        self,
        path: Path,
        *,
        actor_id: str,
        installation_id: str,
        app_instance_id: str,
        display_name: str | None = None,
        media_type: str | None = None,
    ) -> dict[str, Any]:
        if not path.is_absolute():
            raise ComposerError("invalid_source_path", "Selected media path must be absolute")
        try:
            source = path.expanduser().resolve(strict=True)
            stat = source.stat()
        except (OSError, RuntimeError) as error:
            raise ComposerError("source_unavailable", "Selected media is unavailable") from error
        if not source.is_file() or stat.st_size <= 0:
            raise ComposerError("source_unavailable", "Selected media is unavailable")
        resolved_media_type = media_type or mimetypes.guess_type(source.name)[0] or ""
        is_image = resolved_media_type.startswith("image/")
        try:
            if is_image:
                with Image.open(source) as image:
                    width, height = image.size
                    has_alpha = "A" in image.getbands() or "transparency" in image.info
                    image.verify()
                duration, video, audio = 1.0, None, None
                detected_kind = "image"
            else:
                with av.open(str(source)) as container:
                    duration = float(container.duration or 0) / av.time_base
                    video = container.streams.video[0] if container.streams.video else None
                    audio = container.streams.audio[0] if container.streams.audio else None
                    if video is None and audio is None:
                        raise ComposerError("unsupported_media", "The selected file has no media streams")
                    detected_kind = "video" if video is not None else "audio"
                    width = int(video.width) if video is not None else None
                    height = int(video.height) if video is not None else None
                has_alpha = False
        except ComposerError:
            raise
        except (av.error.FFmpegError, OSError) as error:
            raise ComposerError("unsupported_media", "The selected file could not be opened") from error
        source_id = f"cmsrc_{uuid.uuid4().hex}"
        record = {
            "id": source_id,
            "path": str(source),
            "name": Path(display_name or source.name).name,
            "kind": detected_kind,
            "mediaType": resolved_media_type or ("video/mp4" if detected_kind == "video" else "audio/mpeg"),
            "duration": round(duration, 6),
            "width": width,
            "height": height,
            "hasVideo": video is not None,
            "hasAudio": audio is not None,
            "hasImage": is_image,
            "hasAlpha": has_alpha,
            "size": stat.st_size,
            "mtimeNs": stat.st_mtime_ns,
        }
        destination = self._directory(actor_id, installation_id, app_instance_id) / f"{source_id}.json"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(destination)
        return self.public(record)

    def get(
        self, source_id: str, *, actor_id: str, installation_id: str, app_instance_id: str
    ) -> tuple[dict[str, Any], Path]:
        if not source_id.startswith("cmsrc_") or not source_id[6:].isalnum():
            raise ComposerError("source_not_found", "Composer source was not found", status_code=404)
        record_path = self._directory(actor_id, installation_id, app_instance_id) / f"{source_id}.json"
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
            source = Path(record["path"])
            stat = source.stat()
        except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
            raise ComposerError("source_not_found", "Composer source was not found", status_code=404) from error
        if not source.is_file() or stat.st_size != record.get("size") or stat.st_mtime_ns != record.get("mtimeNs"):
            raise ComposerError("source_changed", "Composer source changed or moved; relink it", status_code=409)
        return record, source

    @staticmethod
    def public(record: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in record.items() if key not in {"path", "size", "mtimeNs"}}


async def render_composition(
    project: ComposerProject,
    sources: dict[str, tuple[dict[str, Any], Path]],
    destination: Path,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    await asyncio.to_thread(_render_with_pyav, project, sources, destination)


class _VideoReader:
    def __init__(self, path: Path, source_start: float) -> None:
        self.container = av.open(str(path))
        self.stream = self.container.streams.video[0]
        self.container.seek(int(source_start * av.time_base), backward=True)
        self.frames = iter(self.container.decode(self.stream))
        self.frame: av.VideoFrame | None = None
        self.frame_time = -1.0

    def at(self, target: float) -> av.VideoFrame | None:
        while self.frame_time < target:
            try:
                candidate = next(self.frames)
            except StopIteration:
                break
            candidate_time = float(candidate.time or 0)
            self.frame = candidate
            self.frame_time = candidate_time
        return self.frame

    def close(self) -> None:
        self.container.close()


def _decoded_audio(path: Path, start: float, duration: float, rate: int = 48_000) -> np.ndarray:
    chunks: list[np.ndarray] = []
    with av.open(str(path)) as container:
        if not container.streams.audio:
            return np.zeros((2, 0), dtype=np.float32)
        stream = container.streams.audio[0]
        container.seek(int(start * av.time_base), backward=True)
        resampler = av.AudioResampler(format="fltp", layout="stereo", rate=rate)
        wanted_end = start + duration
        for frame in container.decode(stream):
            frame_start = float(frame.time or 0)
            frame_end = frame_start + frame.samples / float(frame.sample_rate)
            if frame_end <= start:
                continue
            if frame_start >= wanted_end:
                break
            for output in resampler.resample(frame):
                samples = output.to_ndarray().astype(np.float32, copy=False)
                output_start = float(output.time if output.time is not None else frame_start)
                left = max(0, round((start - output_start) * rate))
                right = min(samples.shape[1], round((wanted_end - output_start) * rate))
                if right > left:
                    chunks.append(samples[:, left:right])
        for output in resampler.resample(None):
            chunks.append(output.to_ndarray().astype(np.float32, copy=False))
    if not chunks:
        return np.zeros((2, 0), dtype=np.float32)
    return np.concatenate(chunks, axis=1)[:, : max(1, round(duration * rate))]


def _mix_audio(
    project: ComposerProject,
    sources: dict[str, tuple[dict[str, Any], Path]],
    rate: int = 48_000,
) -> np.ndarray:
    total = max(1, round(project.duration * rate))
    mixed = np.zeros((2, total), dtype=np.float32)
    tracks = {track.id: track for track in project.tracks}
    for clip in project.clips:
        track = tracks[clip.track_id]
        record, path = sources[clip.source_id]
        if (
            (track.kind == "audio" and track.muted)
            or not clip.audio_enabled
            or not record["hasAudio"]
            or clip.volume <= 0
        ):
            continue
        source_count = max(1, round(clip.duration * clip.speed * rate))
        segment = _decoded_audio(path, clip.source_start, clip.duration * clip.speed, rate)
        segment = segment[:, :source_count]
        target_count = max(1, round(clip.duration * rate))
        if not segment.shape[1]:
            continue
        if segment.shape[1] != target_count:
            positions = np.linspace(0, segment.shape[1] - 1, target_count)
            source_positions = np.arange(segment.shape[1])
            segment = np.vstack(
                [np.interp(positions, source_positions, channel) for channel in segment]
            ).astype(np.float32)
        envelope = np.full(target_count, clip.volume, dtype=np.float32)
        fade_in = min(target_count, round(clip.fade_in * rate))
        fade_out = min(target_count - fade_in, round(clip.fade_out * rate))
        if fade_in:
            envelope[:fade_in] *= np.linspace(0, 1, fade_in, dtype=np.float32)
        if fade_out:
            envelope[-fade_out:] *= np.linspace(1, 0, fade_out, dtype=np.float32)
        target_start = round(clip.start * rate)
        available = min(target_count, total - target_start)
        if available > 0:
            mixed[:, target_start : target_start + available] += segment[:, :available] * envelope[:available]
    return np.clip(mixed, -1, 1)


def _render_with_pyav(
    project: ComposerProject,
    sources: dict[str, tuple[dict[str, Any], Path]],
    destination: Path,
) -> None:
    if project.duration <= 0:
        raise ComposerError("empty_composition", "Add at least one clip before exporting")
    settings = project.settings
    tracks = {track.id: track for track in project.tracks}
    visual_clips = [
        clip for clip in project.clips
        if tracks[clip.track_id].kind == "video"
        and not tracks[clip.track_id].muted
        and (sources[clip.source_id][0]["hasVideo"] or sources[clip.source_id][0].get("hasImage"))
    ]
    visual_clips.sort(key=lambda clip: (tracks[clip.track_id].order, clip.start, clip.id))
    readers = {
        clip.id: _VideoReader(sources[clip.source_id][1], clip.source_start)
        for clip in visual_clips if sources[clip.source_id][0]["hasVideo"]
    }
    still_images = {
        source_id: Image.open(path).convert("RGBA")
        for source_id, (record, path) in sources.items() if record.get("hasImage")
    }
    mask_images = {}
    for source_id, (record, path) in sources.items():
        if not record.get("hasImage"):
            continue
        with Image.open(path) as mask:
            has_alpha = "A" in mask.getbands() or "transparency" in mask.info
            mask_images[source_id] = (
                mask.convert("RGBA").getchannel("A")
                if has_alpha
                else ImageOps.grayscale(mask.convert("RGB"))
            )
    audio_samples = _mix_audio(project, sources)
    try:
        with av.open(str(destination), "w", format="mp4") as container:
            video = container.add_stream("libx264", rate=settings.fps)
            video.width, video.height, video.pix_fmt = settings.width, settings.height, "yuv420p"
            audio = container.add_stream("aac", rate=48_000)
            audio.layout = "stereo"
            frame_count = max(1, round(project.duration * settings.fps))
            background = tuple(int(settings.background[index : index + 2], 16) for index in (1, 3, 5))
            for frame_index in range(frame_count):
                timeline_time = frame_index / settings.fps
                canvas = Image.new("RGBA", (settings.width, settings.height), (*background, 255))
                for clip in visual_clips:
                    if not clip.start <= timeline_time < clip.start + clip.duration:
                        continue
                    local_frame = max(0, frame_index - round(clip.start * settings.fps))
                    visual_state = _clip_visual_state(clip, local_frame)
                    if sources[clip.source_id][0].get("hasImage"):
                        image = still_images[clip.source_id].copy()
                    else:
                        source_time = clip.source_start + (timeline_time - clip.start) * clip.speed
                        frame = readers[clip.id].at(source_time)
                        if frame is None:
                            continue
                        image = Image.fromarray(frame.to_ndarray(format="rgba"), "RGBA")
                    box_width = visual_state["width"] or image.width
                    box_height = visual_state["height"] or image.height
                    ratio = min(box_width / image.width, box_height / image.height)
                    image = image.resize(
                        (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
                        Image.Resampling.BILINEAR,
                    )
                    layer_alpha = image.getchannel("A")
                    if clip.mask_source_id:
                        mask_alpha = mask_images[clip.mask_source_id].resize(
                            image.size, Image.Resampling.BILINEAR
                        )
                        layer_alpha = ImageChops.multiply(layer_alpha, mask_alpha)
                    alpha = visual_state["opacity"]
                    if alpha < 1:
                        layer_alpha = layer_alpha.point(
                            lambda value, opacity=alpha: round(value * opacity)
                        )
                    image.putalpha(layer_alpha)
                    canvas.alpha_composite(
                        image,
                        (round(visual_state["x"]), round(visual_state["y"])),
                    )
                output = av.VideoFrame.from_ndarray(np.asarray(canvas.convert("RGB")), format="rgb24")
                output.pts = frame_index
                output.time_base = Fraction(1, settings.fps)
                for packet in video.encode(output):
                    container.mux(packet)
            for packet in video.encode():
                container.mux(packet)
            for offset in range(0, audio_samples.shape[1], 1024):
                block = audio_samples[:, offset : offset + 1024]
                frame = av.AudioFrame.from_ndarray(block, format="fltp", layout="stereo")
                frame.sample_rate = 48_000
                frame.pts = offset
                frame.time_base = Fraction(1, 48_000)
                for packet in audio.encode(frame):
                    container.mux(packet)
            for packet in audio.encode():
                container.mux(packet)
    except (av.error.FFmpegError, OSError, ValueError) as error:
        raise ComposerError("render_failed", f"Composition rendering failed: {error}") from error
    finally:
        for reader in readers.values():
            reader.close()
        for image in still_images.values():
            image.close()
    if not destination.is_file() or destination.stat().st_size <= 0:
        raise ComposerError("render_failed", "Composition rendering produced no output")
