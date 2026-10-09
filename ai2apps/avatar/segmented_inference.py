"""Host-owned execution of signed portrait continuation contracts."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from .segment_jobs import h3_segments, run_segments
from .segments import SCHEMA, file_digest, job_digest


def supports_segments(model):
    spec = (getattr(model, "video_capabilities", None) or {}).get("avatar_segments")
    return "avatar_video" in getattr(model, "capabilities", ()) and spec == {
        "schema": SCHEMA,
        "planner": "h3-v1",
        "window_frames": 192,
    }


def model_identity(runtime, model):
    package = runtime.package_manager.packages.active(model.service_key)
    if package is None:
        raise ValueError("Avatar Package is not installed")
    return {
        "model": model.id,
        "package": package.package_digest,
        "weights": dict(model.weights or {}),
        "metadata": dict(model.metadata),
        "contract": dict(model.video_capabilities or {}),
    }


def validate_video(path, expected, *, width, height, fps=24):
    """Decode every retained frame before accepting a resumable segment."""
    from fractions import Fraction

    import av

    with av.open(str(path)) as media:
        if len(media.streams.video) != 1 or media.streams.audio:
            raise ValueError("Portrait segment must contain one silent video")
        stream = media.streams.video[0]
        if (stream.width, stream.height) != (
            width,
            height,
        ) or stream.codec_context.name != "h264":
            raise ValueError("Unexpected portrait segment codec or geometry")
        count = 0
        for frame in media.decode(stream):
            if frame.pts is None or frame.pts * frame.time_base != Fraction(count, fps):
                raise ValueError("Portrait segment timestamps are not contiguous")
            count += 1
            if count > expected:
                raise ValueError("Portrait segment contains extra frames")
        if count != expected:
            raise ValueError("Portrait segment frame count does not match its receipt")


async def invoke_segmented(
    runtime,
    model,
    body,
    files,
    output,
    *,
    root,
    task_id,
    frozen_model,
    cancelled,
    progress,
    admitted,
    context=None,
):
    import wave

    from .segment_media import join_segments

    if not supports_segments(model) or model_identity(runtime, model) != frozen_model:
        raise ValueError("Avatar model changed after this task was created")
    with wave.open(str(files["audio"][1]), "rb") as source_audio:
        segments = h3_segments(source_audio.getnframes(), source_audio.getframerate())
    identity = job_digest(
        {
            "model": frozen_model,
            "parameters": {
                k: v for k, v in body.items() if k not in {"metadata", "_avatar_model"}
            },
            "files": {
                k: await asyncio.to_thread(file_digest, Path(v[1]))
                for k, v in files.items()
            },
        }
    )

    async def invoke(segment, state, prior, packet):
        if model_identity(runtime, model) != frozen_model:
            raise ValueError("Avatar Package changed during segmented generation")
        payload = {k: v for k, v in body.items() if k != "_avatar_model"}
        payload["duration"] = segment.generate_frames / 24
        payload["avatar_segment"] = dict(
            schema=SCHEMA, identity=identity, index=segment.index, previous_state=prior
        )
        parts = dict(files)
        if state is not None:
            parts["avatar_context"] = ("state.npy", state, "application/octet-stream")

        def report(value):
            progress(
                dict(
                    phase="avatar_segment",
                    current=segment.index,
                    total=len(segments),
                    detail=value,
                )
            )

        await runtime.model_invocations.invoke_background_to_file(
            model.id,
            "video_generation",
            payload,
            packet,
            files=parts,
            request_id=task_id,
            cancel_requested=cancelled,
            progress=report,
            on_admitted=admitted,
            **({"context": context} if context is not None else {}),
        )
        if model_identity(runtime, model) != frozen_model:
            packet.unlink(missing_ok=True)
            raise ValueError("Avatar Package changed during segmented generation")

    clips = await run_segments(
        root,
        identity,
        segments,
        invoke=invoke,
        cancelled=cancelled,
        progress=lambda c, t: progress(
            dict(phase="avatar_segments", current=c, total=t)
        ),
        validate=lambda path, segment: validate_video(
            path,
            segment.end_frame - segment.start_frame,
            width=int(body["width"]),
            height=int(body["height"]),
        ),
    )
    stopped = threading.Event()
    work = asyncio.create_task(
        asyncio.to_thread(
            join_segments,
            clips,
            files["audio"][1],
            output,
            cancelled=lambda: stopped.is_set() or cancelled(),
        )
    )
    try:
        await asyncio.shield(work)
    except asyncio.CancelledError:
        stopped.set()
        while not work.done():
            try:
                await asyncio.shield(work)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not work.cancelled():
            work.exception()
        raise


def copy_verified_cache(source, target):
    """Copy only regular packet files; validation happens before any reuse."""
    import re
    import shutil

    staging = target.with_name(target.name + ".copying")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    try:
        for path in source.iterdir():
            if (
                (path.name == "job.json" or re.fullmatch(r"[0-9]{6}\.zip", path.name))
                and path.is_file()
                and not path.is_symlink()
            ):
                shutil.copyfile(path, staging / path.name)
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
