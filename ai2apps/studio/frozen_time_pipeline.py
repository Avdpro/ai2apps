"""Host-owned Frozen Time orchestration using installed model capabilities."""
from __future__ import annotations

import asyncio
from fractions import Fraction
import os
from pathlib import Path

from .frozen_time import CameraKey, interactive_html, live_photo_frame_order

DEPTH_MODELS = {
    "da": "ai2apps.model.depth-anything-v2-large-mlx/large",
    "vggt": "ai2apps.model.vggt-omega-mlx/1b-512",
}
MERIDIAN = "ai2apps.model.meridian-mlx/h3-8bit"


def reference_size(size, long_edge):
    """Choose the aligned model canvas without floating-point rounding drift."""
    w, h = size
    edge = long_edge // 2
    longest = max(w, h)
    return tuple(max(128, ((v * edge + longest * 32 - 1) // (longest * 32)) * 32)
                 for v in (w, h))


def crop_model_input(source, destination, long_edge):
    """Center crop once, before depth estimation; leave the upload untouched."""
    from math import gcd
    from PIL import Image, ImageOps
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert("RGB")
        rw, rh = reference_size(image.size, long_edge)
        divisor = gcd(rw, rh)
        uw, uh = rw // divisor, rh // divisor
        scale = min(image.width // uw, image.height // uh)
        if scale < 1:
            raise ValueError("Input image is too small for the model aspect ratio")
        w, h = uw * scale, uh * scale
        x, y = (image.width-w)//2, (image.height-h)//2
        image.crop((x, y, x+w, y+h)).save(destination, format="PNG")
    return rw, rh


def encode_frames(path, frames, width, height):
    import av
    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=24)
        stream.width, stream.height = width, height
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": "18", "preset": "fast"}
        for array in frames:
            for packet in stream.encode(av.VideoFrame.from_ndarray(array, format="rgb24")):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def save_original_still(source, poster):
    """Live Photo still preserves the full upload, independently of video crop."""
    from PIL import Image, ImageOps
    with Image.open(source) as image:
        ImageOps.exif_transpose(image).convert("RGB").save(poster, format="JPEG", quality=95)


def prepare_reference(source, depth_path, reference, *, output, long_edge, cancelled, trajectory=None, reference_speedup=True):
    import numpy as np
    from PIL import Image
    from .frozen_time_geometry import orbit_pose, point_cloud, render

    with Image.open(source) as image:
        image = image.convert("RGB")
        original_w, original_h = image.size
        # Keep dense geometry while bounding CPU memory. Reference/output use the
        # same cropped aspect ratio; never stretch a portrait into a square.
        scale = min(1, 1036 / max(image.size))
        w, h = round(original_w * scale), round(original_h * scale)
        colors = np.asarray(image.resize((w, h), Image.Resampling.LANCZOS))
    with np.load(depth_path, allow_pickle=False) as arrays:
        depth = np.asarray(arrays["depth"], dtype=np.float32).squeeze()
        if depth.shape != (original_h, original_w) or not np.isfinite(depth).all():
            raise ValueError("Invalid depth output")
        depth = np.asarray(Image.fromarray(depth).resize((w, h), Image.Resampling.BILINEAR))
        kind = str(arrays["depth_kind"].item())
        if kind == "relative_inverse_depth":
            low, high = np.percentile(depth, [2, 98])
            depth = 1 / (0.35 + 0.65 * np.clip((depth-low)/max(high-low, 1e-6), 0, 1))
            intrinsic = np.array([[w, 0, w/2], [0, w, h/2], [0, 0, 1]], dtype=np.float32)
        elif kind == "camera_depth":
            intrinsic = np.asarray(arrays["intrinsics"], dtype=np.float32).copy()
            intrinsic[0] *= w/original_w
            intrinsic[1] *= h/original_h
        else:
            raise ValueError("Unsupported depth semantics")
    if np.any(depth <= 0) or not np.isfinite(intrinsic).all():
        raise ValueError("Invalid camera geometry")
    # Keep the canonical output canvas unchanged; optionally halve references.
    rw, rh = reference_size((original_w, original_h), long_edge)
    output_w, output_h = rw*2, rh*2
    if not reference_speedup:
        rw, rh = output_w, output_h
    projection = intrinsic.copy()
    projection[0] *= rw/w
    projection[1] *= rh/h
    points = point_cloud(depth, intrinsic)
    pivot = np.array([0, 0, np.median(depth[h//3:2*h//3, w//3:2*w//3])])
    if trajectory is None:
        raise ValueError('Package-computed camera frames are required')
    plan = tuple(CameraKey(**key) for key in trajectory['frames'])
    def frames():
        for key in plan:
            if cancelled():
                raise RuntimeError("Cancelled")
            rgb, _ = render(points, colors, projection, orbit_pose(pivot, key.yaw, key.pitch, key.radius, key.roll), (rh, rw))
            yield rgb
    encode_frames(reference, frames(), rw, rh)
    return output_w, output_h, plan


def export_video(raw, output, poster, plan, kind, cancelled, return_origin=None, playback=None, poster_index=None):
    import av
    from PIL import Image
    with av.open(str(raw)) as container:
        frames = [frame.to_ndarray(format="rgb24") for frame in container.decode(video=0)]
    if len(frames) != len(plan):
        raise ValueError("Source frames do not match camera plan")
    if cancelled():
        raise RuntimeError("Cancelled")
    center = poster_index if poster_index is not None else min(range(len(plan)), key=lambda i: plan[i].yaw**2 + plan[i].pitch**2 + (plan[i].radius-1)**2)
    Image.fromarray(frames[center]).save(poster)
    order = range(len(plan)) if kind == "html" else playback if playback is not None else live_photo_frame_order(plan)
    from .frozen_time_editor import frame_order,apply_filters
    if kind!='html' and return_origin is not None:
        order=frame_order(plan,return_origin)
    h, w = frames[0].shape[:2]
    encode_frames(output, (apply_filters(frames[i],plan[i]) for i in order), w, h)
    return center / 24


def mux_soundtrack(video: Path, soundtrack: Path, cancelled):
    """Copy video packets and add a bounded AAC track without changing video timing."""
    import av
    temporary = video.with_name('output-with-audio.mp4')
    try:
        with av.open(str(video)) as source, av.open(str(soundtrack)) as music, av.open(str(temporary), 'w') as target:
            if not source.streams.video or not music.streams.audio:
                raise ValueError('Video or soundtrack has no decodable media track')
            input_video = source.streams.video[0]
            video_seconds = float(input_video.duration * input_video.time_base) if input_video.duration else float(source.duration or 0) / 1_000_000
            if video_seconds <= 0:
                raise ValueError('Video duration is unavailable')
            max_samples = round(video_seconds * 48_000)
            output_video = target.add_stream_from_template(input_video)
            output_audio = target.add_stream('aac', rate=48_000)
            output_audio.layout = 'stereo'
            for packet in source.demux(input_video):
                if cancelled():
                    raise RuntimeError('Cancelled')
                if packet.dts is not None:
                    packet.stream = output_video
                    target.mux(packet)
            resampler = av.AudioResampler(format='fltp', layout='stereo', rate=48_000)
            offset = 0
            def encode(frame):
                nonlocal offset
                remaining = max_samples - offset
                if remaining <= 0:
                    return
                if frame.samples > remaining:
                    frame = av.AudioFrame.from_ndarray(frame.to_ndarray()[:, :remaining].copy(), format='fltp', layout='stereo')
                    frame.sample_rate = 48_000
                frame.pts = offset
                frame.time_base = Fraction(1, 48_000)
                offset += frame.samples
                for packet in output_audio.encode(frame):
                    target.mux(packet)
            for frame in music.decode(audio=0):
                if cancelled():
                    raise RuntimeError('Cancelled')
                for converted in resampler.resample(frame):
                    encode(converted)
                if offset >= max_samples:
                    break
            if offset < max_samples:
                for converted in resampler.resample(None):
                    encode(converted)
            if not offset:
                raise ValueError('Soundtrack contains no decodable audio samples')
            for packet in output_audio.encode(None):
                target.mux(packet)
        os.replace(temporary, video)
    finally:
        temporary.unlink(missing_ok=True)


async def prepare_preview(runtime, source: Path, directory: Path, *, depth, output,
                          long_edge, context, request_id, cancelled, progress, trajectory=None, reference_speedup=True):
    depth_path, reference = directory / "depth.npz", directory / "reference.mp4"
    cropped = directory / "model-input.png"
    await asyncio.to_thread(crop_model_input, source, cropped, long_edge)
    source = cropped
    if cancelled():
        return
    progress(5, "Estimating depth")
    await runtime.model_invocations.invoke_background_to_file(
        DEPTH_MODELS[depth], "depth_estimation",
        {"schema": "ai2apps.depth-estimation/v1", "image": {"part": "image"}, "input_size": 1036 if depth == "da" else 512, "output_format": "npz"},
        depth_path, files={"image": ("input.png", source, "image/png")},
        request_id=request_id+"-depth", cancel_requested=cancelled, context=context)
    if cancelled():
        return
    progress(20, "Rendering camera path")
    width, height, plan = await asyncio.to_thread(prepare_reference, source, depth_path, reference,
        output=output, long_edge=long_edge, cancelled=cancelled, trajectory=trajectory, reference_speedup=reference_speedup)
    # A separate playback copy uses precisely the final export ordering. The
    # untouched 73-frame reference remains the input to Meridian.
    await asyncio.to_thread(export_video, reference, directory/'preview.mp4',
        directory/'preview-poster.jpg', plan, output, cancelled, None, trajectory['playback'], trajectory['poster'])
    return width, height, plan


async def generate(runtime, source: Path, directory: Path, *, depth, output, long_edge,
                   seed, context, request_id, cancelled, progress, prepared=None, trajectory=None, reference_speedup=True, soundtrack=None):
    original_source = source
    if prepared is None:
        prepared = await prepare_preview(runtime, source, directory, depth=depth,
            output=output, long_edge=long_edge, context=context, request_id=request_id,
            cancelled=cancelled, progress=progress, trajectory=trajectory, reference_speedup=reference_speedup)
    if prepared is None or cancelled():
        return
    width, height, plan = prepared
    import json
    from dataclasses import asdict
    return_origin=None
    (directory/'conversion.json').write_text(json.dumps({'schema':2,'plan':[asdict(key) for key in plan],'playback':trajectory['playback'],'poster':trajectory['poster']}),encoding='utf-8')
    source, reference = directory/'model-input.png', directory/'reference.mp4'
    progress(35, "Meridian refinement")
    raw = directory / "raw.mp4"
    await runtime.model_invocations.invoke_background_to_file(
        MERIDIAN, "video_generation", {"width": width, "height": height, "num_frames": len(plan), "fps": 24, "steps": 3, "seed": seed},
        raw, files={"image": ("input.png", source, "image/png"), "camera_video": ("reference.mp4", reference, "video/mp4")},
        request_id=request_id+"-meridian", cancel_requested=cancelled, context=context)
    if cancelled():
        return
    progress(90, "Exporting")
    video, poster = directory / "output.mp4", directory / "poster.jpg"
    still_time = await asyncio.to_thread(export_video, raw, video, poster, plan, output, cancelled, None, trajectory['playback'], trajectory['poster'])
    if output == 'mp4' and soundtrack is not None:
        await asyncio.to_thread(mux_soundtrack, video, soundtrack, cancelled)
    artifacts = [("output.mp4", "video", "video/mp4")]
    if output == "html":
        (directory / "output.html").write_text(interactive_html(video.read_bytes()), encoding="utf-8")
        artifacts.insert(0, ("output.html", "document", "text/html"))
    elif output == "live-photo":
        from .live_photo import export_live_photo
        await asyncio.to_thread(save_original_still, original_source, poster)
        await export_live_photo(video, directory, still_time, cancelled)
        from .frozen_time_conversion import live_photo_artifacts
        artifacts[:0] = live_photo_artifacts()
    return artifacts
