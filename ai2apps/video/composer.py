"""Private media references and deterministic rendering for Video Composer."""

from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import os
import uuid
from collections.abc import Callable
from fractions import Fraction
from io import BufferedIOBase
from pathlib import Path
from typing import Any, Literal

import av
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps
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
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    frame: int = Field(ge=0, le=216_000)
    endpoint: Literal["start", "end"] | None = None
    transition: Literal["hold", "linear", "ease"] = "linear"
    x: int | None = Field(default=None, ge=-16384, le=16384)
    y: int | None = Field(default=None, ge=-16384, le=16384)
    width: int | None = Field(default=None, ge=16, le=16384)
    height: int | None = Field(default=None, ge=16, le=16384)
    opacity: float | None = Field(default=None, ge=0, le=1)
    scale: float | None = Field(default=None, ge=0.05, le=20)
    crop_left: float | None = Field(default=None, alias="cropLeft", ge=0, le=95)
    crop_top: float | None = Field(default=None, alias="cropTop", ge=0, le=95)
    crop_right: float | None = Field(default=None, alias="cropRight", ge=0, le=95)
    crop_bottom: float | None = Field(default=None, alias="cropBottom", ge=0, le=95)
    crop_shape: Literal["rectangle", "ellipse", "rounded"] | None = Field(
        default=None, alias="cropShape"
    )
    crop_corner_radius: int | None = Field(
        default=None, alias="cropCornerRadius", ge=0, le=4096
    )
    crop_feather: int | None = Field(default=None, alias="cropFeather", ge=0, le=512)
    crop_scale: float | None = Field(default=None, alias="cropScale", ge=0.01, le=20)


class ComposerClip(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    layer_type: Literal["media", "spotlight", "text"] = Field(default="media", alias="layerType")
    source_id: str | None = Field(default=None, alias="sourceId", min_length=1, max_length=100)
    track_id: str = Field(alias="trackId", min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    start: float = Field(ge=0, le=3600)
    source_start: float = Field(default=0, alias="sourceStart", ge=0, le=86400)
    duration: float = Field(gt=0, le=3600)
    speed: float = Field(default=1, ge=0.25, le=20)
    volume: float = Field(default=1, ge=0, le=4)
    fade_in: float = Field(default=0, alias="fadeIn", ge=0, le=30)
    fade_out: float = Field(default=0, alias="fadeOut", ge=0, le=30)
    x: int = Field(default=0, ge=-16384, le=16384)
    y: int = Field(default=0, ge=-16384, le=16384)
    width: int | None = Field(default=None, ge=16, le=16384)
    height: int | None = Field(default=None, ge=16, le=16384)
    opacity: float = Field(default=1, ge=0, le=1)
    scale: float = Field(default=1, ge=0.05, le=20)
    spotlight_shape: Literal["rounded", "ellipse"] = Field(default="rounded", alias="spotlightShape")
    dim_opacity: float = Field(default=0.65, alias="dimOpacity", ge=0, le=1)
    feather: int = Field(default=24, ge=0, le=512)
    corner_radius: int = Field(default=32, alias="cornerRadius", ge=0, le=4096)
    text: str = Field(default="Text", max_length=4000)
    font_size: int = Field(default=64, alias="fontSize", ge=8, le=512)
    text_color: str = Field(default="#ffffff", alias="textColor", pattern=r"^#[0-9a-fA-F]{6}$")
    text_bold: bool = Field(default=False, alias="textBold")
    text_italic: bool = Field(default=False, alias="textItalic")
    text_underline: bool = Field(default=False, alias="textUnderline")
    text_strikethrough: bool = Field(default=False, alias="textStrikethrough")
    text_stroke_enabled: bool = Field(default=False, alias="textStrokeEnabled")
    text_stroke_width: int = Field(default=2, alias="textStrokeWidth", ge=0, le=128)
    text_stroke_color: str = Field(
        default="#000000", alias="textStrokeColor", pattern=r"^#[0-9a-fA-F]{6}$"
    )
    text_stroke_style: Literal["solid", "feather"] = Field(
        default="solid", alias="textStrokeStyle"
    )
    text_shadow_enabled: bool = Field(default=False, alias="textShadowEnabled")
    text_shadow_color: str = Field(
        default="#000000", alias="textShadowColor", pattern=r"^#[0-9a-fA-F]{6}$"
    )
    text_shadow_opacity: float = Field(default=0.5, alias="textShadowOpacity", ge=0, le=1)
    text_shadow_blur: int = Field(default=12, alias="textShadowBlur", ge=0, le=512)
    text_shadow_offset_x: int = Field(default=8, alias="textShadowOffsetX", ge=-4096, le=4096)
    text_shadow_offset_y: int = Field(default=8, alias="textShadowOffsetY", ge=-4096, le=4096)
    text_anchor: Literal[
        "top-left", "top", "top-right", "left", "center", "right",
        "bottom-left", "bottom", "bottom-right",
    ] = Field(default="center", alias="textAnchor")
    reveal: bool = False
    reveal_speed: float = Field(default=12, alias="revealSpeed", ge=0.1, le=200)
    audio_enabled: bool = Field(default=True, alias="audioEnabled")
    mask_source_id: str | None = Field(default=None, alias="maskSourceId", max_length=100)
    crop_left: float = Field(default=0, alias="cropLeft", ge=0, le=95)
    crop_top: float = Field(default=0, alias="cropTop", ge=0, le=95)
    crop_right: float = Field(default=0, alias="cropRight", ge=0, le=95)
    crop_bottom: float = Field(default=0, alias="cropBottom", ge=0, le=95)
    crop_shape: Literal["rectangle", "ellipse", "rounded"] = Field(
        default="rectangle", alias="cropShape"
    )
    crop_corner_radius: int = Field(default=32, alias="cropCornerRadius", ge=0, le=4096)
    crop_feather: int = Field(default=0, alias="cropFeather", ge=0, le=512)
    crop_scale: float = Field(default=1, alias="cropScale", ge=0.01, le=20)
    crop_viewport_version: int = Field(default=2, alias="cropViewportVersion", ge=1, le=2)
    group_id: str | None = Field(default=None, alias="groupId", max_length=80)
    color: str = Field(default="#3b82f6", pattern=r"^#[0-9a-fA-F]{6}$")
    keyframes: list[ComposerKeyframe] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def validate_fades(self):
        if self.layer_type == "media" and not self.source_id:
            raise ValueError("media clips require a source")
        if self.layer_type != "media" and self.mask_source_id:
            raise ValueError("special layers cannot use an image mask")
        if self.crop_left + self.crop_right >= 100:
            raise ValueError("horizontal crop must leave part of the source visible")
        if self.crop_top + self.crop_bottom >= 100:
            raise ValueError("vertical crop must leave part of the source visible")
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
                        scale=clip.scale, crop_left=clip.crop_left, crop_top=clip.crop_top,
                        crop_right=clip.crop_right, crop_bottom=clip.crop_bottom,
                        crop_shape=clip.crop_shape,
                        crop_corner_radius=clip.crop_corner_radius,
                        crop_feather=clip.crop_feather,
                        crop_scale=clip.crop_scale,
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
                    end = ComposerKeyframe(
                        id=f"end-{clip.id}"[:80], frame=end_frame, endpoint="end",
                        transition="linear",
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
            for keyframe in clip.keyframes:
                state = _clip_visual_state(clip, keyframe.frame)
                if float(state["crop_left"]) + float(state["crop_right"]) >= 100:
                    raise ValueError("horizontal keyframe crop must leave source content visible")
                if float(state["crop_top"]) + float(state["crop_bottom"]) >= 100:
                    raise ValueError("vertical keyframe crop must leave source content visible")
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


def _clip_visual_state(clip: ComposerClip, local_frame: int) -> dict[str, float | str]:
    state = {
        "x": float(clip.x),
        "y": float(clip.y),
        "width": float(clip.width or 0),
        "height": float(clip.height or 0),
        "opacity": float(clip.opacity),
        "scale": float(clip.scale),
        "crop_left": float(clip.crop_left),
        "crop_top": float(clip.crop_top),
        "crop_right": float(clip.crop_right),
        "crop_bottom": float(clip.crop_bottom),
        "crop_shape": clip.crop_shape,
        "crop_corner_radius": float(clip.crop_corner_radius),
        "crop_feather": float(clip.crop_feather),
        "crop_scale": float(clip.crop_scale),
    }
    numeric_fields = (
        "x", "y", "width", "height", "opacity", "scale", "crop_left", "crop_top",
        "crop_right", "crop_bottom", "crop_corner_radius", "crop_feather", "crop_scale",
    )
    previous_frame = 0
    previous = state
    for keyframe in clip.keyframes:
        target = dict(previous)
        for name in numeric_fields:
            value = getattr(keyframe, name)
            if value is not None:
                target[name] = float(value)
        if keyframe.crop_shape is not None:
            target["crop_shape"] = keyframe.crop_shape
        if local_frame >= keyframe.frame:
            previous_frame, previous = keyframe.frame, target
            continue
        if keyframe.transition == "hold" or keyframe.frame <= previous_frame:
            return previous
        progress = (local_frame - previous_frame) / (keyframe.frame - previous_frame)
        progress = max(0.0, min(1.0, progress))
        if keyframe.transition == "ease":
            progress = progress * progress * (3 - 2 * progress)
        result = dict(previous)
        for name in numeric_fields:
            result[name] = float(previous[name]) + (
                float(target[name]) - float(previous[name])
            ) * progress
        return result
    return previous


def _fit_image_to_visual_box(image: Image.Image, width: float, height: float) -> Image.Image:
    """Match the browser preview's object-fit: contain box semantics."""

    box_width = max(1, round(width))
    box_height = max(1, round(height))
    fitted_box = _fitted_content_box(image.size, (box_width, box_height))
    fitted = image.resize(
        (fitted_box[2] - fitted_box[0], fitted_box[3] - fitted_box[1]),
        Image.Resampling.BILINEAR,
    )
    layer = Image.new("RGBA", (box_width, box_height), (0, 0, 0, 0))
    layer.alpha_composite(fitted, fitted_box[:2])
    fitted.close()
    return layer


def _fitted_content_box(
    source_size: tuple[int, int], target_size: tuple[int, int]
) -> tuple[int, int, int, int]:
    source_width, source_height = source_size
    target_width, target_height = target_size
    ratio = min(target_width / source_width, target_height / source_height)
    width = max(1, round(source_width * ratio))
    height = max(1, round(source_height * ratio))
    left = (target_width - width) // 2
    top = (target_height - height) // 2
    return left, top, left + width, top + height


def _crop_image_to_visible_region(
    image: Image.Image,
    clip: ComposerClip,
    state: dict[str, float | str] | None = None,
) -> Image.Image:
    state = state or _clip_visual_state(clip, 0)
    crop_left = float(state["crop_left"])
    crop_top = float(state["crop_top"])
    crop_right = float(state["crop_right"])
    crop_bottom = float(state["crop_bottom"])
    left = min(image.width - 1, round(image.width * crop_left / 100))
    top = min(image.height - 1, round(image.height * crop_top / 100))
    right = max(left + 1, round(image.width * (1 - crop_right / 100)))
    bottom = max(top + 1, round(image.height * (1 - crop_bottom / 100)))
    return image.crop((left, top, min(image.width, right), min(image.height, bottom)))


def _place_cropped_image_in_visual_box(
    cropped: Image.Image,
    width: float,
    height: float,
    crop_scale: float,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Place a cropped source at the viewport origin without stretching it.

    ``crop_scale`` is an absolute source-pixel to canvas-pixel ratio.  The
    viewport may grow beyond the scaled source; those pixels intentionally
    remain transparent so lower tracks can show through.
    """

    box_width = max(1, round(width))
    box_height = max(1, round(height))
    scale = max(0.01, min(20.0, float(crop_scale)))
    scaled_width = max(1, round(cropped.width * scale))
    scaled_height = max(1, round(cropped.height * scale))
    resized = cropped.resize((scaled_width, scaled_height), Image.Resampling.BILINEAR)
    layer = Image.new("RGBA", (box_width, box_height), (0, 0, 0, 0))
    visible_width = min(box_width, scaled_width)
    visible_height = min(box_height, scaled_height)
    if visible_width and visible_height:
        visible = resized.crop((0, 0, visible_width, visible_height))
        layer.alpha_composite(visible, (0, 0))
        visible.close()
    resized.close()
    return layer, (0, 0, visible_width, visible_height)


def _crop_shape_mask(
    clip: ComposerClip,
    size: tuple[int, int],
    content_box: tuple[int, int, int, int] | None = None,
    state: dict[str, float | str] | None = None,
) -> Image.Image:
    state = state or _clip_visual_state(clip, 0)
    width, height = size
    hard = Image.new("L", size, 0)
    draw = ImageDraw.Draw(hard)
    if content_box is None:
        box = (0, 0, max(0, width - 1), max(0, height - 1))
    else:
        box = (
            content_box[0], content_box[1],
            max(content_box[0], content_box[2] - 1),
            max(content_box[1], content_box[3] - 1),
        )
    crop_shape = str(state["crop_shape"])
    corner_radius = round(float(state["crop_corner_radius"]))
    if crop_shape == "ellipse":
        draw.ellipse(box, fill=255)
    elif crop_shape == "rounded":
        draw.rounded_rectangle(box, radius=corner_radius, fill=255)
    else:
        draw.rectangle(box, fill=255)
    content_width = box[2] - box[0] + 1
    content_height = box[3] - box[1] + 1
    feather = min(
        round(float(state["crop_feather"])),
        max(0, (min(content_width, content_height) - 1) // 2),
    )
    if not feather:
        return hard
    inner = Image.new("L", size, 0)
    inner_draw = ImageDraw.Draw(inner)
    inner_box = (
        box[0] + feather,
        box[1] + feather,
        max(box[0] + feather, box[2] - feather),
        max(box[1] + feather, box[3] - feather),
    )
    if crop_shape == "ellipse":
        inner_draw.ellipse(inner_box, fill=255)
    elif crop_shape == "rounded":
        inner_draw.rounded_rectangle(
            inner_box, radius=max(0, corner_radius - feather), fill=255
        )
    else:
        inner_draw.rectangle(inner_box, fill=255)
    softened = inner.filter(ImageFilter.GaussianBlur(max(0.5, feather / 2)))
    inner.close()
    result = ImageChops.multiply(hard, softened)
    hard.close()
    softened.close()
    return result


def _composer_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _anchor_position(anchor: str, x: float, y: float, width: int, height: int) -> tuple[int, int]:
    horizontal = 0 if anchor.endswith("left") or anchor == "left" else width if anchor.endswith("right") or anchor == "right" else width / 2
    vertical = 0 if anchor.startswith("top") or anchor == "top" else height if anchor.startswith("bottom") or anchor == "bottom" else height / 2
    return round(x - horizontal), round(y - vertical)


def _apply_spotlight(canvas: Image.Image, clip: ComposerClip, state: dict[str, float]) -> None:
    hole = Image.new("L", canvas.size, 0)
    draw = ImageDraw.Draw(hole)
    box = (
        round(state["x"]), round(state["y"]),
        round(state["x"] + max(1, state["width"])),
        round(state["y"] + max(1, state["height"])),
    )
    if clip.spotlight_shape == "ellipse":
        draw.ellipse(box, fill=255)
    else:
        draw.rounded_rectangle(box, radius=clip.corner_radius, fill=255)
    feather = min(
        clip.feather,
        max(0, (min(box[2] - box[0], box[3] - box[1]) - 1) // 2),
    )
    if feather:
        inner = Image.new("L", canvas.size, 0)
        inner_draw = ImageDraw.Draw(inner)
        inner_box = (
            box[0] + feather,
            box[1] + feather,
            max(box[0] + feather, box[2] - feather),
            max(box[1] + feather, box[3] - feather),
        )
        if clip.spotlight_shape == "ellipse":
            inner_draw.ellipse(inner_box, fill=255)
        else:
            inner_draw.rounded_rectangle(
                inner_box, radius=max(0, clip.corner_radius - feather), fill=255
            )
        softened = inner.filter(ImageFilter.GaussianBlur(max(0.5, feather / 2)))
        inner.close()
        inward = ImageChops.multiply(hole, softened)
        hole.close()
        softened.close()
        hole = inward
    darkness = ImageOps.invert(hole).point(
        lambda value: round(value * clip.dim_opacity * state["opacity"])
    )
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 255))
    overlay.putalpha(darkness)
    canvas.alpha_composite(overlay)
    overlay.close()
    hole.close()


def _apply_text_layer(
    canvas: Image.Image,
    clip: ComposerClip,
    state: dict[str, float],
    local_seconds: float,
) -> None:
    text = clip.text
    if clip.reveal:
        text = text[: max(0, int(local_seconds * clip.reveal_speed))]
    if not text:
        return
    font = _composer_font(clip.font_size)
    spacing = max(2, clip.font_size // 5)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    bold_width = max(1, round(clip.font_size / 28)) if clip.text_bold else 0
    bounds = probe.multiline_textbbox(
        (0, 0), text, font=font, spacing=spacing, stroke_width=bold_width
    )
    width, height = max(1, bounds[2] - bounds[0]), max(1, bounds[3] - bounds[1])
    stroke_width = clip.text_stroke_width if clip.text_stroke_enabled else 0
    stroke_blur = max(1.0, stroke_width * 0.5) if clip.text_stroke_style == "feather" else 0
    shadow_blur = clip.text_shadow_blur if clip.text_shadow_enabled else 0
    effect_extent = max(
        stroke_width + round(stroke_blur * 3),
        abs(clip.text_shadow_offset_x) + round(shadow_blur * 3),
        abs(clip.text_shadow_offset_y) + round(shadow_blur * 3),
    )
    padding = 4 + effect_extent
    size = (width + padding * 2, height + padding * 2)
    origin = (padding - bounds[0], padding - bounds[1])
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    fill_mask = Image.new("L", size, 0)
    ImageDraw.Draw(fill_mask).multiline_text(
        origin, text, font=font, fill=255, spacing=spacing,
        stroke_width=bold_width, stroke_fill=255,
    )

    if clip.text_shadow_enabled and clip.text_shadow_opacity > 0:
        shadow_mask = Image.new("L", size, 0)
        shadow_origin = (
            origin[0] + clip.text_shadow_offset_x,
            origin[1] + clip.text_shadow_offset_y,
        )
        ImageDraw.Draw(shadow_mask).multiline_text(
            shadow_origin, text, font=font, fill=255, spacing=spacing,
            stroke_width=bold_width, stroke_fill=255,
        )
        if shadow_blur:
            shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(shadow_blur))
        shadow_mask = shadow_mask.point(
            lambda value: round(value * clip.text_shadow_opacity)
        )
        shadow_rgb = tuple(int(clip.text_shadow_color[index:index + 2], 16) for index in (1, 3, 5))
        shadow_layer = Image.new("RGBA", size, (*shadow_rgb, 0))
        shadow_layer.putalpha(shadow_mask)
        layer.alpha_composite(shadow_layer)
        shadow_layer.close()
        shadow_mask.close()

    if stroke_width:
        stroke_mask = Image.new("L", size, 0)
        ImageDraw.Draw(stroke_mask).multiline_text(
            origin, text, font=font, fill=255, spacing=spacing,
            stroke_width=stroke_width + bold_width, stroke_fill=255,
        )
        outside_mask = ImageChops.subtract(stroke_mask, fill_mask)
        stroke_mask.close()
        if clip.text_stroke_style == "feather":
            softened_mask = outside_mask.filter(ImageFilter.GaussianBlur(stroke_blur))
            outside_mask.close()
            outside_mask = softened_mask
        stroke_rgb = tuple(
            int(clip.text_stroke_color[index:index + 2], 16) for index in (1, 3, 5)
        )
        stroke_layer = Image.new("RGBA", size, (*stroke_rgb, 0))
        stroke_layer.putalpha(outside_mask)
        layer.alpha_composite(stroke_layer)
        stroke_layer.close()
        outside_mask.close()

    # Paint the glyph fill last so neither solid nor feathered outlines can
    # cover the text itself. The configured stroke width is entirely external.
    draw = ImageDraw.Draw(layer)
    draw.multiline_text(
        origin, text, font=font, fill=clip.text_color, spacing=spacing,
        stroke_width=bold_width, stroke_fill=clip.text_color,
    )
    decoration_width = max(1, round(clip.font_size / 16))
    decoration_left = padding
    decoration_right = padding + width
    if clip.text_underline:
        underline_y = padding + height - max(1, round(clip.font_size / 14))
        draw.line(
            (decoration_left, underline_y, decoration_right, underline_y),
            fill=clip.text_color, width=decoration_width,
        )
    if clip.text_strikethrough:
        strike_y = padding + round(height * 0.52)
        draw.line(
            (decoration_left, strike_y, decoration_right, strike_y),
            fill=clip.text_color, width=decoration_width,
        )
    fill_mask.close()
    if clip.text_italic:
        shear = 0.22
        extra_width = max(1, round(layer.height * shear))
        italic_layer = layer.transform(
            (layer.width + extra_width, layer.height),
            Image.Transform.AFFINE,
            (1, shear, -shear * layer.height, 0, 1, 0),
            resample=Image.Resampling.BICUBIC,
        )
        layer.close()
        layer = italic_layer
    scale = state["scale"]
    if abs(scale - 1) > 1e-6:
        layer = layer.resize(
            (max(1, round(layer.width * scale)), max(1, round(layer.height * scale))),
            Image.Resampling.LANCZOS,
        )
    if state["opacity"] < 1:
        layer.putalpha(layer.getchannel("A").point(lambda value: round(value * state["opacity"])))
    canvas.alpha_composite(layer, _anchor_position(clip.text_anchor, state["x"], state["y"], layer.width, layer.height))
    layer.close()


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

    def import_stream(
        self,
        stream: BufferedIOBase,
        *,
        actor_id: str,
        installation_id: str,
        app_instance_id: str,
        display_name: str,
        media_type: str | None = None,
        max_bytes: int,
    ) -> dict[str, Any]:
        """Stream browser-selected media into private Composer storage.

        AceFox normally provides an authorized native path, so desktop imports
        do not copy the source. This fallback deliberately bypasses Gallery's
        small general-purpose import quota while retaining a bounded, private
        copy for browsers that cannot expose a native path.
        """

        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        suffix = Path(display_name).suffix.lower()
        if len(suffix) > 16 or any(not (character.isalnum() or character == ".") for character in suffix):
            suffix = ""
        directory = self._directory(actor_id, installation_id, app_instance_id) / "imports"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination = directory / f"media_{uuid.uuid4().hex}{suffix}"
        temporary = destination.with_suffix(destination.suffix + ".part")
        size = 0
        try:
            with temporary.open("xb") as output:
                os.chmod(temporary, 0o600)
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ComposerError(
                            "source_too_large",
                            f"Composer media exceeds the {max_bytes}-byte import limit",
                            status_code=413,
                        )
                    output.write(chunk)
            if size == 0:
                raise ComposerError("source_unavailable", "Selected media is empty")
            temporary.replace(destination)
            return self.register(
                destination,
                actor_id=actor_id,
                installation_id=installation_id,
                app_instance_id=app_instance_id,
                display_name=display_name,
                media_type=media_type,
            )
        except Exception:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise

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
    progress: Callable[[float, float], None] | None = None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    await asyncio.to_thread(_render_with_pyav, project, sources, destination, progress)


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
        if clip.layer_type != "media" or not clip.source_id:
            continue
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
    progress: Callable[[float, float], None] | None = None,
) -> None:
    if project.duration <= 0:
        raise ComposerError("empty_composition", "Add at least one clip before exporting")
    settings = project.settings
    tracks = {track.id: track for track in project.tracks}
    visual_clips = [
        clip for clip in project.clips
        if tracks[clip.track_id].kind == "video"
        and not tracks[clip.track_id].muted
        and (
            clip.layer_type in {"spotlight", "text"}
            or (
                clip.source_id is not None
                and (sources[clip.source_id][0]["hasVideo"] or sources[clip.source_id][0].get("hasImage"))
            )
        )
    ]
    visual_clips.sort(key=lambda clip: (tracks[clip.track_id].order, clip.start, clip.id))
    readers = {
        clip.id: _VideoReader(sources[clip.source_id][1], clip.source_start)
        for clip in visual_clips
        if clip.layer_type == "media" and clip.source_id and sources[clip.source_id][0]["hasVideo"]
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
            clip_frame_ranges = {
                clip.id: (
                    round(clip.start * settings.fps),
                    max(1, round(clip.duration * settings.fps)),
                )
                for clip in visual_clips
            }
            frame_count = max(
                1,
                max(
                    (
                        round(clip.start * settings.fps)
                        + max(1, round(clip.duration * settings.fps))
                        for clip in project.clips
                    ),
                    default=0,
                ),
            )
            progress_interval = max(1, settings.fps)
            if progress is not None:
                progress(0, project.duration)
            background = tuple(int(settings.background[index : index + 2], 16) for index in (1, 3, 5))
            for frame_index in range(frame_count):
                canvas = Image.new("RGBA", (settings.width, settings.height), (*background, 255))
                for clip in visual_clips:
                    clip_start_frame, clip_duration_frames = clip_frame_ranges[clip.id]
                    if not clip_start_frame <= frame_index < clip_start_frame + clip_duration_frames:
                        continue
                    local_frame = frame_index - clip_start_frame
                    local_time = local_frame / settings.fps
                    visual_state = _clip_visual_state(clip, local_frame)
                    if clip.layer_type == "spotlight":
                        _apply_spotlight(canvas, clip, visual_state)
                        continue
                    if clip.layer_type == "text":
                        _apply_text_layer(canvas, clip, visual_state, local_time)
                        continue
                    if not clip.source_id:
                        continue
                    if sources[clip.source_id][0].get("hasImage"):
                        image = still_images[clip.source_id].copy()
                    else:
                        source_time = clip.source_start + local_time * clip.speed
                        frame = readers[clip.id].at(source_time)
                        if frame is None:
                            continue
                        image = Image.fromarray(frame.to_ndarray(format="rgba"), "RGBA")
                    box_width = visual_state["width"] or image.width
                    box_height = visual_state["height"] or image.height
                    source_image = image
                    cropped_image = _crop_image_to_visible_region(
                        source_image, clip, visual_state
                    )
                    image, fitted_box = _place_cropped_image_in_visual_box(
                        cropped_image,
                        box_width,
                        box_height,
                        float(visual_state["crop_scale"]),
                    )
                    cropped_image.close()
                    source_image.close()
                    layer_alpha = image.getchannel("A")
                    crop_alpha = _crop_shape_mask(
                        clip, image.size, fitted_box, visual_state
                    )
                    layer_alpha = ImageChops.multiply(layer_alpha, crop_alpha)
                    crop_alpha.close()
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
                    image.close()
                output = av.VideoFrame.from_ndarray(np.asarray(canvas.convert("RGB")), format="rgb24")
                output.pts = frame_index
                output.time_base = Fraction(1, settings.fps)
                for packet in video.encode(output):
                    container.mux(packet)
                completed_frames = frame_index + 1
                if progress is not None and (
                    completed_frames == frame_count
                    or completed_frames % progress_interval == 0
                ):
                    progress(
                        min(project.duration, completed_frames / settings.fps),
                        project.duration,
                    )
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
