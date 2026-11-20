"""End-to-end mouth refinement for a generated motion video."""

import gc
import os
from pathlib import Path

import av
import mlx.core as mx
import soundfile as sf

from .pipeline_mlx import MuseTalkPipeline
from .prepare import prepare_regions
from .template import render_template


def refine_video(
    source,
    audio,
    output,
    assets,
    *,
    fps=24,
    frame_interval=None,
    source_start=0,
    cancelled=lambda: False,
    progress=lambda phase, current, total: None,
):
    source, audio, output, assets = map(Path, (source, audio, output, assets))

    def check():
        if cancelled():
            raise InterruptedError("Mouth refinement cancelled")

    check()
    info = sf.info(str(audio))
    expected = (info.frames * fps + info.samplerate - 1) // info.samplerate
    with av.open(str(source)) as media:
        stream = media.streams.video[0]
        if frame_interval is not None:
            start, end = frame_interval
            if (type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= expected
                    or type(source_start) is not int or source_start < 0
                    or source_start + end - start > stream.frames):
                raise ValueError("Invalid mouth-refinement segment interval")
            expected = end - start
        if ((frame_interval is None and stream.frames != expected)
                or abs(float(stream.average_rate) - fps) > 1e-6):
            raise ValueError(
                "Motion video must exactly cover the driving audio at the selected FPS"
            )
    regions = prepare_regions(
        source,
        assets,
        cancel_check=check,
        progress=lambda c, t: progress("prepare_mouth", c, t),
    )
    check()
    gc.collect()
    mx.clear_cache()
    pipe = MuseTalkPipeline.from_pretrained_mlx(assets / "musetalk")
    temporary = output.with_name(output.stem + ".refining.mp4")
    try:
        render_template(
            pipe,
            source,
            audio,
            temporary,
            regions,
            fps=fps,
            frame_interval=frame_interval,
            source_start=source_start,
            batch_size=4,
            cancel_check=check,
            progress=lambda c, t: progress("refine_mouth", c, t),
        )
        check()
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
        del pipe, regions
        gc.collect()
        mx.clear_cache()
    return {"frames": expected, "fps": fps, "mouth_refiner": "musetalk-1.5-q4"}
