"""Whole-clip refinement, bounded overlapping VAE decode, and one audio remux."""

from __future__ import annotations

import gc
import hashlib
import heapq
import os
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

import av
import numpy as np

WINDOW = 41
OVERLAP = 17
STEP = WINDOW - OVERLAP
CUT = STEP + OVERLAP // 2
MAX_FRAMES = 1500
MAX_SECONDS = 60
AUDIO_CODECS = {"aac", "mp3", "alac", "ac3", "eac3"}


class UpscaleCancelled(Exception):
    pass


def noise_seed(seed, latent_frame):
    digest = hashlib.sha256(
        f"sol-noise-v1:{seed}:{latent_frame}".encode("ascii")
    ).digest()
    return int.from_bytes(digest[:4], "little")


def window_plan(width, height):
    """Bound spatial/temporal work while retaining 8-frame latent alignment."""
    pixels = ((width + 31) // 32 * 32) * ((height + 31) // 32 * 32)
    # Keep small-video behavior; larger frames trade temporal context for memory.
    window = next((n for n in (41, 33, 25, 17, 9) if pixels * n <= 41 * 768**2), 9)
    overlap = 17 if window == 41 else (9 if window >= 17 else 1)
    return window, overlap


def estimated_memory_bytes(width, height, frames):
    """Conservative admission estimate; whole-clip stages grow with duration."""
    pixels = ((width + 31) // 32 * 32) * ((height + 31) // 32 * 32)
    temporal = 1 + ((frames - 1 + 7) // 8) * 8
    window, _ = window_plan(width, height)
    return max(
        12 * 1024**3,
        2 * 1024**3 + pixels * max(min(window, temporal) * 1000, temporal * 300),
    )


def check_memory(width, height, frames):
    import psutil

    required = estimated_memory_bytes(width, height, frames)
    available = psutil.virtual_memory().available
    if required > max(0, available - 2 * 1024**3):
        raise MemoryError(
            f"Whole-clip upscaling needs an estimated {required / 1024**3:.1f} GiB "
            f"plus 2 GiB system headroom; {available / 1024**3:.1f} GiB available. "
            "Close other models or use a shorter/lower-resolution source. "
            "Independent segment refinement is disabled to preserve temporal consistency."
        )
    return required


def join_window(previous, current, valid, final, window=WINDOW, overlap=OVERLAP):
    """Return committed frames and a bounded tail, with no timeline shortening."""
    step = window - overlap
    cut = step + overlap // 2
    blend = min(2, overlap)
    pieces = []
    if previous is None:
        start = 0
    else:
        center = cut - step
        for i, alpha in enumerate(i / (blend + 1) for i in range(1, blend + 1)):
            frame = np.rint(
                previous[i].astype(np.float32) * (1 - alpha)
                + current[center + i].astype(np.float32) * alpha
            ).astype(np.uint8)
            pieces.append(frame[None])
        start = center + blend
    end = valid if final else cut
    pieces.append(current[start:end])
    emitted = np.concatenate(pieces)
    tail = None if final else current[cut:valid].copy()
    return emitted, tail


def remux_audio(video, source, output, origin, duration, check):
    """Copy compatible compressed audio; align original audio to video frame zero."""
    with (
        av.open(str(video)) as vin,
        av.open(str(source)) as ain,
        av.open(str(output), "w") as out,
    ):
        vs = vin.streams.video[0]
        vo = out.add_stream_from_template(vs)
        audio = list(ain.streams.audio)
        mapping = {s.index: out.add_stream_from_template(s) for s in audio}

        def video_packets():
            for p in vin.demux(vs):
                if p.dts is not None:
                    p.stream = vo
                    yield p

        def audio_packets():
            for p in ain.demux(audio):
                if p.dts is None:
                    continue
                offset = round(origin / p.time_base)
                if p.pts is not None:
                    p.pts -= offset
                p.dts -= offset
                if p.pts is not None and p.pts * p.time_base >= duration:
                    continue
                p.stream = mapping[p.stream.index]
                yield p

        for packet in heapq.merge(
            video_packets(), audio_packets(), key=lambda p: p.dts * p.time_base
        ):
            check()
            out.mux(packet)


def upscale(
    source,
    output,
    model_root,
    prompt,
    seed,
    data_root,
    check,
    progress,
    infer_factory=None,
):
    # All MLX/model imports stay behind the Worker invocation boundary.
    os.environ.setdefault("MLX_ENABLE_TF32", "0")
    import mlx.core as mx
    from sol_refiner_mlx.pipeline import Refiner

    mx.set_cache_limit(512 * 1024**2)
    from prompt_context import fixed_context

    default_context = fixed_context(model_root, prompt)
    with TemporaryDirectory(prefix="upscale-", dir=data_root) as temporary:
        temporary = Path(temporary)
        context = temporary / "context.safetensors"
        noise_file = temporary / "noise.safetensors"
        silent = temporary / "silent.mp4"
        with av.open(str(source)) as src:
            if not src.streams.video:
                raise ValueError("Input has no video stream")
            stream = src.streams.video[0]
            fps = stream.average_rate
            if fps is None or not 1 <= float(fps) <= 60:
                raise ValueError(
                    "Video requires a constant frame rate between 1 and 60 fps"
                )
            width, height = stream.codec_context.width, stream.codec_context.height
            if min(width, height) < 32:
                raise ValueError(
                    "Source dimensions must be at least 32 pixels per side"
                )
            if any(s.codec_context.name not in AUDIO_CODECS for s in src.streams.audio):
                raise ValueError(
                    "Audio must be AAC, MP3, ALAC, AC3 or EAC3 for MP4 passthrough"
                )
            window, overlap = window_plan(width, height)
            step = window - overlap
            has_audio = bool(src.streams.audio)
            total = 0
            origin = None
            iterator = iter(src.decode(stream))

            def take(count):
                nonlocal total, origin
                values = []
                for _ in range(count):
                    check()
                    frame = next(iterator, None)
                    if frame is None:
                        break
                    if frame.width != width or frame.height != height:
                        raise ValueError("Changing video dimensions are unsupported")
                    if frame.pts is None:
                        raise ValueError("Input video is missing timestamps")
                    timestamp = Fraction(frame.pts) * frame.time_base
                    if origin is None:
                        origin = timestamp
                    expected = origin + Fraction(total, 1) / fps
                    if abs(timestamp - expected) > max(
                        Fraction(1, 1000), Fraction(1, 1) / fps / 10
                    ):
                        raise ValueError(
                            "Variable frame rate input must be converted "
                            "to constant frame rate first"
                        )
                    total += 1
                    if total > MAX_FRAMES or Fraction(total, 1) / fps > MAX_SECONDS:
                        raise ValueError("Video exceeds 1500 frames or 60 seconds")
                    values.append(frame.to_ndarray(format="rgb24"))
                return values

            # Scan real decoded frames before allocating the clip or loading weights.
            # Container frame counts are not reliable enough for memory admission.
            while take(1):
                pass
            if not total:
                raise ValueError("Input has no decodable video frames")
            estimated = check_memory(width, height, total)
            temporal = 1 + ((total - 1 + 7) // 8) * 8
            ph, pw = (-height) % 32, (-width) % 32
            # Disk-backed staging avoids retaining a Python list of RGB frames.
            frames = np.memmap(
                temporary / "frames.rgb",
                dtype=np.uint8,
                mode="w+",
                shape=(temporal, height + ph, width + pw, 3),
            )
            with av.open(str(source)) as second:
                count = 0
                for frame in second.decode(video=0):
                    check()
                    if count >= total or frame.width != width or frame.height != height:
                        raise ValueError("Input video changed during preparation")
                    frames[count] = np.pad(
                        frame.to_ndarray(format="rgb24"),
                        ((0, ph), (0, pw), (0, 0)),
                        mode="edge",
                    )
                    count += 1
                if count != total:
                    raise ValueError("Input video changed during preparation")
            frames[total:] = frames[total - 1]
            pixels = (
                mx.array(frames).transpose(3, 0, 1, 2)[None].astype(mx.float32) / 127.5
                - 1
            )
            mx.eval(pixels)
            del frames
            shape = (1, 128, 1, (height + ph) // 16, (width + pw) // 16)
            noise = mx.concatenate(
                [
                    mx.random.normal(
                        shape, dtype=mx.bfloat16, key=mx.random.key(noise_seed(seed, i))
                    )
                    for i in range((temporal - 1) // 8 + 1)
                ],
                axis=2,
            )
            mx.save_safetensors(str(noise_file), {"noise": noise})
            del noise
            runner = (infer_factory or Refiner)(model_root)
            progress({"phase": "refining", "current": 0, "total": total})
            raw = runner.refine_latents(
                pixels,
                prompt,
                float(fps),
                seed,
                context_path=default_context,
                noise_path=noise_file,
                save_context=context,
                check_cancel=check,
            )
            del pixels
            gc.collect()
            mx.clear_cache()
            previous = None
            start = 0
            written = 0
            with av.open(str(silent), "w") as dest:
                encoder = dest.add_stream("libx264", rate=fps)
                encoder.width, encoder.height = width * 2, height * 2
                encoder.pix_fmt = "yuv420p"
                encoder.options = {"crf": "18"}

                def emit(frames):
                    nonlocal written
                    for image in frames:
                        check()
                        for packet in encoder.encode(
                            av.VideoFrame.from_ndarray(image, format="rgb24")
                        ):
                            dest.mux(packet)
                        written += 1

                while True:
                    check()
                    valid = min(window, total - start)
                    final = start + valid >= total
                    latent_count = (valid - 1 + 7) // 8 + 1
                    decoded = runner.decode_latents(
                        raw[:, :, start // 8 : start // 8 + latent_count],
                        check_cancel=check,
                    )
                    if not bool(mx.all(mx.isfinite(decoded)).item()):
                        raise RuntimeError("Refiner produced nonfinite pixels")
                    decoded = mx.clip(
                        (decoded[0].transpose(1, 2, 3, 0).astype(mx.float32) + 1) / 2,
                        0,
                        1,
                    )
                    rgb = np.rint(
                        np.array(decoded[:valid, : height * 2, : width * 2]) * 255
                    ).astype(np.uint8)
                    emit_frames, previous = join_window(
                        previous, rgb, valid, final, window, overlap
                    )
                    emit(emit_frames)
                    del decoded, rgb, emit_frames
                    gc.collect()
                    mx.clear_cache()
                    progress(
                        {
                            "phase": "upscaling",
                            "current": written,
                            "total": max(int(stream.frames or 0), total),
                        }
                    )
                    if final:
                        break
                    start += step
                for packet in encoder.encode():
                    dest.mux(packet)
        assert written == total
        check()
        if has_audio:
            remux_audio(silent, source, output, origin, Fraction(total, 1) / fps, check)
        else:
            silent.replace(output)
        return {
            "kind": "video_upscaling",
            "frames": written,
            "fps": str(fps),
            "width": width * 2,
            "height": height * 2,
            "scale": 2,
            "audio_preserved": has_audio,
            "temporal_policy": "whole_clip",
            "inference_frames": total,
            "decode_window_frames": window,
            "estimated_memory_bytes": estimated,
            "overlap_frames": overlap,
            "blend_frames": min(2, overlap),
        }
