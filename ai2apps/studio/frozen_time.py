"""Deterministic camera plans and offline output for Frozen Time.

No inference, filesystem paths or user HTML are accepted by these helpers.
Live Photo pairing is a separate native export step; a reversed MP4 alone is
not advertised as an Apple Live Photo.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CameraKey:
    yaw: float
    pitch: float = 0.0
    radius: float = 1.0
    roll: float = 0.0
    blur: float = 0.0
    saturation: float = 1.0
    exposure: float = 0.0
    brightness: float = 1.0


CAMERA_MODES = {
    "orbit": (CameraKey(-15), CameraKey(15)),
    "arc": (CameraKey(-15), CameraKey(0, -12), CameraKey(15), CameraKey(0)),
    "push-orbit": (CameraKey(-15, radius=1.22), CameraKey(-15), CameraKey(15)),
    "push-orbit2": (CameraKey(0), CameraKey(0, radius=.8), CameraKey(-15, radius=.8), CameraKey(15, radius=.8)),
    "vertical": (CameraKey(0, -15), CameraKey(0, 15)),
    "diagonal": (CameraKey(-15, -9, 1.18), CameraKey(0), CameraKey(15, 9)),
    "float": (CameraKey(-8, 3), CameraKey(0, -5), CameraKey(8, 3), CameraKey(0)),
}


AMPLITUDES = {"large": 1.0, "medium": 2/3, "small": 1/3}
FRAME_COUNTS = (73,90,107,124,141,158,175,243)


def camera_plan(mode: str = "push-orbit", *, output: str = "live-photo", frames: int = 73, amplitude: str = "medium"):
    """Scale angle and dolly distance together, keeping the source camera fixed."""
    if mode not in CAMERA_MODES or amplitude not in AMPLITUDES or output not in {"live-photo", "html"}:
        raise ValueError("Unknown Frozen Time camera/output mode")
    if type(frames) is not int or frames not in FRAME_COUNTS:
        raise ValueError("Unsupported Meridian frame count")
    horizontal_html = output == "html" and mode == "orbit"
    scale = AMPLITUDES[amplitude]
    keys = tuple(CameraKey(k.yaw*scale, k.pitch*scale, 1+(k.radius-1)*scale) for k in CAMERA_MODES[mode])
    result = []
    for i in range(frames):
        t = i / (frames - 1) * (len(keys) - 1)
        segment = min(int(t), len(keys) - 2)
        u = t - segment
        # Uniform yaw is important for drag-to-angle mapping. Cinematic paths
        # ease in/out at keyframes, without changing the frame budget.
        if not horizontal_html:
            u = u * u * (3 - 2 * u)
        a, b = keys[segment:segment + 2]
        result.append(CameraKey(*(getattr(a, field) * (1-u) + getattr(b, field) * u
                                  for field in ("yaw", "pitch", "radius"))))
    return tuple(result)


def live_photo_frame_order(plan):
    """Append only the final leg in reverse, stopping at its nearest center.

    No duplicate end frame. Center-start dolly paths also reverse the opening
    dolly to restore the original photo distance.
    This ordering is shared by the paired-video encoder and preview.
    """
    if len(plan) < 2:
        raise ValueError("At least two camera frames required")
    # The center-start dolly/orbit path returns along two existing legs:
    # final orbit back to its zero-angle crossing, then opening dolly reversed.
    # Detect geometry rather than a mode name so retained exports convert alike.
    if plan[0] == CameraKey(0) and plan[-1].radius < 1 and plan[-1].yaw > 0:
        dolly_end = next((i-1 for i, k in enumerate(plan) if k.yaw != 0), None)
        if dolly_end is not None:
            center = min(range(len(plan)//2, len(plan)), key=lambda i: abs(plan[i].yaw)+abs(plan[i].pitch))
            return tuple(range(len(plan))) + tuple(range(len(plan)-2, center-1, -1)) + tuple(range(dolly_end-1, -1, -1))
    # Search the latter half: initial/earlier center crossings must not rewind
    # a completed opening camera movement.
    center = min(range(len(plan)//2, len(plan)),
                 key=lambda i: plan[i].yaw**2 + plan[i].pitch**2 + (plan[i].radius-1)**2)
    return tuple(range(len(plan))) + tuple(range(len(plan)-2, center-1, -1))


def interactive_html(video: bytes) -> str:
    """Embed a bounded MP4 in a network-free, standalone HTML document."""
    if not video or len(video) > 128 * 1024 * 1024:
        raise ValueError("Video must be between 1 byte and 128 MiB")
    if len(video) < 12 or video[4:8] != b"ftyp":
        raise ValueError("Expected MP4 content")
    template = (Path(__file__).with_name("frozen_time_player.html")).read_text(encoding="utf-8")
    return template.replace("__VIDEO_BASE64__", base64.b64encode(video).decode("ascii"))
