"""Render bounded, silent Studio visuals from ordered PNG or JPEG frames."""

import base64
import binascii
import io
import json
import zipfile

from PIL import Image

CAPABILITY = "media.visual_sequence.export"
HOST_STUDIOS = frozenset({"ai2apps.imagine-studio", "ai2apps.doc-studio"})
MAX_BYTES = 8 * 1024 * 1024
FPS = 12


def render_visual_sequence(data, output):
    try:
        spec = json.loads(data)
        if not isinstance(spec, dict):
            raise ValueError()
        mode, frames, seconds = (spec.get(key) for key in ("format", "frames", "seconds"))
        encoding = spec.get("encoding", "png")
        if (encoding not in ("png", "jpeg") or (mode in ("png", "zip") and encoding != "png")
                or mode not in ("png", "mp4", "zip") or not isinstance(frames, list)
                or not 1 <= len(frames) <= (1 if mode == "png" else 30)
                or type(seconds) not in (int, float) or seconds not in (0.5, 1, 1.5, 2, 2.5, 3)):
            raise ValueError()
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("Invalid visual sequence") from error

    image_format = "PNG" if encoding == "png" else "JPEG"

    def decode(encoded):
        try:
            if not isinstance(encoded, str):
                raise ValueError()
            raw = base64.b64decode(encoded, validate=True)
            with Image.open(io.BytesIO(raw), formats=(image_format,)) as image:
                w, h = image.size
                if (not 2 <= w <= 1280 or not 2 <= h <= 1280 or w % 2 or h % 2
                        or getattr(image, "n_frames", 1) != 1):
                    raise ValueError()
                return image.convert("RGB")
        except (ValueError, OSError, binascii.Error, Image.DecompressionBombError) as error:
            raise ValueError(f"Frames must be single {image_format} images with even dimensions up to 1280 pixels") from error

    first = decode(frames[0])
    if mode == "zip":
        with zipfile.ZipFile(output, "w") as archive:
            for index, encoded in enumerate(frames):
                image = first if index == 0 else decode(encoded)
                if image.size != first.size:
                    raise ValueError("All frames must have the same dimensions")
                with archive.open(f"page-{index + 1:02d}.png", "w") as entry:
                    image.save(entry, format="PNG")
        return {"kind": "file", "media_type": "application/zip", "format": "zip"}

    if mode == "png":
        first.save(output, format="PNG")
        return {"kind": "image", "media_type": "image/png", "format": "png"}

    import av

    with av.open(str(output), mode="w", format="mp4", options={"movflags": "+faststart"}) as movie:
        stream = movie.add_stream("libx264", rate=FPS)
        stream.width, stream.height = first.size
        stream.pix_fmt = "yuv420p"
        stream.options = {"preset": "ultrafast", "crf": "20", "threads": "2"}
        pts = 0
        for index, encoded in enumerate(frames):
            image = first if index == 0 else decode(encoded)
            if image.size != first.size:
                raise ValueError("All frames must have the same dimensions")
            for _ in range(int(seconds * FPS)):
                frame = av.VideoFrame.from_image(image)
                frame.pts = pts
                pts += 1
                for packet in stream.encode(frame):
                    movie.mux(packet)
        for packet in stream.encode():
            movie.mux(packet)
    return {"kind": "video", "media_type": "video/mp4", "format": "mp4"}
