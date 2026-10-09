"""Durable, sequential portrait continuation outside a single Worker request."""

from __future__ import annotations

import asyncio
import json
import shutil
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from .h3_timeline import plan_h3_windows
from .segments import read_packet


@dataclass(frozen=True)
class Segment:
    index: int
    start_frame: int
    end_frame: int
    window_start: int
    generate_frames: int
    context_frames: int


def h3_segments(samples: int, rate: int, *, window_frames=192) -> tuple[Segment, ...]:
    """Account for the VAE's five-frame holdback on the absolute timeline."""
    windows = plan_h3_windows(samples, rate, window_frames=window_frames)
    return tuple(
        Segment(
            w.index,
            w.output_start - (5 if w.index else 0),
            w.output_end - (5 if w.index + 1 < len(windows) else 0),
            w.start_frame,
            w.generate_frames,
            w.context_frames,
        )
        for w in windows
    )


async def run_segments(
    root: Path,
    identity: str,
    segments: tuple[Segment, ...],
    *,
    invoke,
    cancelled=lambda: False,
    progress=lambda *args: None,
    validate=None,
):
    """invoke(segment, previous_state_path, predecessor_digest, packet_path).

    The caller owns authorization, immutable model resolution, media validation
    and final mux. This loop serializes invocations and recovers only a verified
    prefix; it never publishes an intermediate clip as a finished video.
    """
    if not segments or segments[0].start_frame != 0:
        raise ValueError("A segment job must start at zero")
    for index, segment in enumerate(segments):
        if (
            segment.index != index
            or segment.end_frame <= segment.start_frame
            or (index and segments[index - 1].end_frame != segment.start_frame)
        ):
            raise ValueError("Segment job has a gap, overlap or unordered index")
    root.mkdir(parents=True, exist_ok=True)
    marker = root / "job.json"
    frozen = dict(
        schema="ai2apps.avatar-segment-job/v1",
        identity=identity,
        segments=[vars(s) for s in segments],
    )
    if marker.exists():
        if json.loads(marker.read_text()) != frozen:
            raise ValueError("Continuation job identity or timeline changed")
    else:
        temporary = marker.with_suffix(".partial")
        temporary.write_text(json.dumps(frozen, sort_keys=True))
        temporary.replace(marker)
    predecessor = None
    state = None
    outputs = []
    reusable = True
    for segment in segments:
        if cancelled():
            raise asyncio.CancelledError()
        packet = root / f"{segment.index:06d}.zip"
        accepted = root / f"{segment.index:06d}"
        expected = dict(
            identity=identity,
            index=segment.index,
            start_frame=segment.start_frame,
            end_frame=segment.end_frame,
            fps=24,
            previous_state=predecessor,
        )
        receipt = None

        def clear_accepted(accepted=accepted):
            if accepted.is_symlink():
                accepted.unlink()
            elif accepted.exists():
                shutil.rmtree(accepted)

        async def accept(
            packet=packet,
            accepted=accepted,
            expected=expected,
            segment=segment,
            clear=clear_accepted,
        ):
            clear()
            value = await asyncio.to_thread(
                read_packet, packet, destination=accepted, **expected
            )
            if validate is not None:
                await asyncio.to_thread(validate, accepted / "video.mp4", segment)
            return value

        if reusable and packet.is_file():
            with suppress(ValueError, OSError):
                receipt = await accept()
        if receipt is None:
            reusable = False
            packet.unlink(missing_ok=True)
            clear_accepted()
            await invoke(segment, state, predecessor, packet)
            if cancelled():
                raise asyncio.CancelledError()
            receipt = await accept()
        state = accepted / "state.npy"
        predecessor = receipt["state_sha256"]
        outputs.append(accepted / "video.mp4")
        progress(segment.index + 1, len(segments))
    return tuple(outputs)
