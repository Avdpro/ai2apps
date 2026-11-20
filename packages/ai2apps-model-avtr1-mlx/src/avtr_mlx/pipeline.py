"""Standalone AVTR-1 MLX image + audio experiment (all neural networks on MLX)."""

import json
import os
import time
from math import gcd
from pathlib import Path

import mlx.core as mx
import numpy as np
import soundfile as sf
from PIL import Image
from scipy.signal import resample_poly
from scipy.spatial.transform import Rotation
from scipy.special import ndtr, ndtri

from .detector import MLXSCRFD
from .graph import AvatarGraph
from .image import warp_affine
from .model import MotionModel
from .rotation import _rotation_matrix
from .source_crop import crop_image


class AvatarPipeline:
    def __init__(
        self,
        root,
        *,
        renderer="optimized",
        render_batch_size=2,
        asynchronous_encoding=True,
        output_mode="source",
    ):
        if render_batch_size not in (1, 2, 5):
            raise ValueError("render_batch_size must be 1, 2 or 5")
        if output_mode not in {"source", "crop"}:
            raise ValueError("output_mode must be source or crop")
        self.output_mode = output_mode
        self.render_batch_size = render_batch_size
        self.asynchronous_encoding = asynchronous_encoding
        if renderer not in {"reference", "optimized", "fast"}:
            raise ValueError("Unknown renderer mode")
        self.renderer_mode = renderer
        self.fast_renderer = None
        self.render_fallbacks = 0
        self.root = Path(root)
        self.motion = MotionModel(root)
        self.graphs = {
            name: AvatarGraph(self._graph_path(name))
            for name in (
                "landmark106",
                "landmark203",
                "motion_extractor",
                "appearance_extractor",
                "stitch_network",
                "warp_network",
                "decoder",
            )
        }
        self.hubert = AvatarGraph(self._graph_path("hubert"))
        self.detector = MLXSCRFD(self._graph_path("insightface_det"))

    def _graph_path(self, name):
        bundle = self.root / "graphs" / name
        if bundle.is_dir():
            return bundle
        return self.root / (
            "build_artifacts/hubert-lbs-avtr1.onnx"
            if name == "hubert"
            else f"ditto_onnx/{name}.onnx"
        )

    def run_graph(self, name, **feeds):
        out = self.graphs[name](feeds)
        mx.eval(out)
        return out

    def prepare(self, image_path):
        self.render_fallbacks = 0
        from .image import load_source_rgb

        rgb = load_source_rgb(image_path)
        bgr = np.ascontiguousarray(rgb[:, :, ::-1])
        faces = self.detector.detect(bgr, input_size=(512, 512))
        if not faces:
            raise ValueError("No face detected")
        bbox = max(faces, key=lambda f: np.prod(f.bbox[2:4] - f.bbox[:2])).bbox
        center = (bbox[:2] + bbox[2:4]) / 2
        scale = 192 / (max(bbox[2:4] - bbox[:2]) * 1.5)
        mat = np.array(
            [[scale, 0, 96 - scale * center[0]], [0, scale, 96 - scale * center[1]]]
        )
        patch = warp_affine(rgb, mat, (192, 192))
        blob = patch[:, :, ::-1].astype("float32").transpose(2, 0, 1)[None]
        pts = np.array(self.run_graph("landmark106", data=blob)[0]).reshape(-1, 2)
        pts = (pts + 1) * 96
        inv = np.linalg.inv(np.vstack([mat, [0, 0, 1]]))[:2]
        pts = pts @ inv[:, :2].T + inv[:, 2]
        crop = crop_image(
            rgb,
            pts,
            dsize=224,
            scale=1.5,
            vx_ratio=0.0,
            vy_ratio=-0.1,
            flag_do_rot=True,
        )
        inp = crop.img_crop.astype("float32").transpose(2, 0, 1)[None] / 255
        pts = np.array(self.run_graph("landmark203", input=inp)[0]).reshape(-1, 2) * 224
        pts = pts @ crop.M_c2o[:2, :2].T + crop.M_c2o[:2, 2]
        crop = crop_image(
            rgb,
            pts,
            dsize=512,
            scale=2.6,
            vx_ratio=0.0,
            vy_ratio=-0.1,
            flag_do_rot=True,
        )
        image = (
            np.array(
                Image.fromarray(crop.img_crop).resize((256, 256), Image.Resampling.BOX)
            )
            .astype("float32")
            .transpose(2, 0, 1)[None]
            / 255
        )
        self.crop = crop.img_crop
        self.source_size = (rgb.shape[1], rgb.shape[0])
        self.crop_to_source = crop.M_c2o
        self.canvas = None
        if self.output_mode == "source":
            from .image import SourceCanvas

            self.canvas = SourceCanvas(rgb, crop.M_c2o, (512, 512))
        values = self.run_graph("motion_extractor", image=image)
        info = dict(
            zip(
                ("pitch", "yaw", "roll", "t", "exp", "scale", "kp"),
                [np.array(v) for v in values],
            )
        )
        angles = []
        for n in ("pitch", "yaw", "roll"):
            p = info[n]
            p = np.exp(p - p.max())
            p /= p.sum()
            angles.append((p * np.arange(66)).sum() * 3 - 97.5)
        self.rot = _rotation_matrix(*[np.array([v]) for v in angles])
        self.info = info
        self.kp = info["kp"].reshape(1, 21, 3)
        self.exp = info["exp"].reshape(1, 21, 3)
        self.feature = self.run_graph("appearance_extractor", image=image)[0]
        self.source = info["scale"][..., None] * (self.kp @ self.rot + self.exp)
        self.source[:, :, :2] += info["t"][:, None, :2]
        w = self.motion.weights

        def norm(x, typ):
            return (mx.array(x) - w["offset_" + typ]) / w["scale_" + typ]

        so3 = norm(Rotation.from_matrix(self.rot).as_rotvec().astype("float32"), "so3")
        exp = mx.clip(norm(self.exp @ self.rot.transpose(0, 2, 1), "exp"), -5, 5)
        kp = mx.clip(norm(self.kp, "kp"), -5, 5)
        self.kp_cond = mx.concatenate(
            [so3, kp.reshape(1, -1), exp.reshape(1, -1)], axis=-1
        )[:, None, :]
        self.coords = np.array(w["lipsync_coords"]).astype(int).tolist()
        self.past = mx.repeat(
            mx.concatenate([so3, exp.reshape(1, -1)[:, self.coords]], axis=-1)[
                :, None, :
            ],
            75,
            axis=1,
        )
        if self.renderer_mode != "reference":
            from .renderer import FastRenderer

            self.fast_renderer = FastRenderer(
                self.graphs,
                self.feature,
                self.source,
                mixed=self.renderer_mode == "fast",
            )
        self.history = mx.zeros((1, 75, 2048))
        self.shared = None

    def render_reference(self, drive):
        drive = self.run_graph(
            "stitch_network", kp_source=self.source, kp_driving=drive
        )[0]
        warped = self.run_graph(
            "warp_network",
            feature_3d=self.feature,
            kp_source=self.source,
            kp_driving=drive,
        )[0]
        return self.run_graph("decoder", feature=warped)[0]

    def render_pixels(self, drives):
        """One in-flight batch overlaps GPU work with CPU transfer/encoding."""
        pending = None
        for offset in range(0, len(drives), self.render_batch_size):
            drive = drives[offset : offset + self.render_batch_size]
            if self.fast_renderer is not None:
                rendered = self.fast_renderer.render_batch(mx.array(drive))
            else:
                rendered = mx.concatenate(
                    [
                        self.render_reference(drive[i : i + 1])
                        for i in range(len(drive))
                    ],
                    axis=0,
                )
            finite = mx.all(mx.isfinite(rendered), axis=(1, 2, 3))
            pixels = (
                (mx.clip(rendered, 0, 1) * 255).astype(mx.uint8).transpose(0, 2, 3, 1)
            )
            mx.async_eval(pixels, finite)
            if pending is not None:
                yield self._finish_pixels(*pending)
            pending = (pixels, finite, drive)
        if pending is not None:
            yield self._finish_pixels(*pending)

    def _finish_pixels(self, pixels, finite, drive):
        values = np.array(pixels)
        valid = np.array(finite)
        for index in np.flatnonzero(~valid):
            if self.renderer_mode != "fast":
                raise ValueError("Nonfinite rendered frame")
            reference = np.array(self.render_reference(drive[index : index + 1]))[
                0
            ].transpose(1, 2, 0)
            if not np.isfinite(reference).all():
                raise ValueError("Nonfinite fallback frame")
            values[index] = (np.clip(reference, 0, 1) * 255).astype("uint8")
            self.render_fallbacks += 1
        return values

    def noise(self, rng):
        coef = 2 / np.sqrt(5)
        std = 1 / np.sqrt(5)
        prev = self.shared
        items = []
        for _ in range(5):
            lo, hi = (
                (-1.2, 1.2)
                if prev is None
                else ((-1.2 - coef * prev) / std, (1.2 - coef * prev) / std)
            )
            eps = ndtri(
                np.clip(
                    ndtr(lo) + rng.random((1, 42)) * (ndtr(hi) - ndtr(lo)),
                    1e-6,
                    1 - 1e-6,
                )
            )
            prev = eps if prev is None else coef * prev + std * eps
            items.append(prev)
        self.shared = prev
        return mx.array(np.stack(items, axis=1).astype("float32"))

    def generate(
        self,
        image,
        audio,
        output,
        seconds=2.0,
        steps=5,
        seed=42,
        *,
        cancel_check=lambda: None,
        progress=None,
        writer_factory=None,
    ):
        if steps < 2:
            raise ValueError("steps must be at least two schedule points")
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        total_start = time.perf_counter()
        start = time.perf_counter()
        self.prepare(image)
        prep = time.perf_counter() - start
        Image.fromarray(self.crop).save(output.with_suffix(".source.png"))
        sound, rate = sf.read(str(audio), dtype="float32", always_2d=True)
        sound = sound.mean(axis=1)
        if rate != 16000:
            factor = gcd(rate, 16000)
            sound = resample_poly(sound, 16000 // factor, rate // factor)
        frames = min(int(seconds * 25), len(sound) // 640)
        frames = (frames // 5) * 5
        if frames < 5:
            raise ValueError("Need at least 0.2 seconds of audio")
        sound = np.pad(sound, (1920, 6400))
        rng = np.random.default_rng(seed)
        from .video_writer import VideoWriter

        cancel_check()
        writer = (writer_factory or VideoWriter)(
            output,
            audio,
            frames / 25,
            asynchronous=self.asynchronous_encoding,
            size=self.source_size if self.canvas is not None else (512, 512),
        )
        times = {"hubert": 0.0, "motion": 0.0, "render": 0.0, "composition": 0.0}
        start = time.perf_counter()
        silence = None
        try:
            for frame in range(0, frames, 5):
                cancel_check()
                tic = time.perf_counter()
                window = sound[frame * 640 : frame * 640 + 8400]
                features = []
                for track_index, track in enumerate((window, np.zeros_like(window))):
                    if track_index == 1 and silence is not None:
                        features.append(silence)
                        continue
                    feat = (
                        self.hubert({"input_values": track[None]})[0][:, -20:, :]
                        .reshape(1, 10, 2, 1024)
                        .mean(axis=2)
                    )
                    mx.eval(feat)
                    features.append(feat)
                    if track_index == 1:
                        silence = feat
                new = mx.concatenate(features, axis=-1)
                times["hubert"] += time.perf_counter() - tic
                tic = time.perf_counter()
                cond = self.motion.encode(
                    self.past,
                    mx.concatenate([self.history, new], axis=1),
                    self.kp_cond,
                    mx.ones((1, 15, 1)),
                )
                pred = self.motion.sample(
                    cond,
                    self.noise(rng),
                    steps=steps,
                    self_weights=2.0,
                    other_weights=2.0,
                    kp_weights=3.0,
                )
                mx.eval(pred)
                self.past = mx.concatenate([self.past[:, 5:], pred], axis=1)
                self.history = mx.concatenate([self.history[:, 5:], new[:, :5]], axis=1)
                denorm = np.array(
                    pred * self.motion.weights["motion_scale"]
                    + self.motion.weights["motion_offset"]
                )[0]
                times["motion"] += time.perf_counter() - tic
                tic = time.perf_counter()
                drives = []
                for values in denorm:
                    rot = (
                        Rotation.from_rotvec(values[:3])
                        .as_matrix()
                        .astype("float32")[None]
                    )
                    delta = self.exp.copy().reshape(1, 63)
                    for i, index in enumerate(self.coords):
                        delta[:, index] = values[3 + i]
                    drive = (
                        self.info["scale"][..., None]
                        * ((self.kp + delta.reshape(1, 21, 3)) @ rot)
                        + self.info["t"][:, None, :]
                    )
                    drives.append(drive)
                drives = np.concatenate(drives, axis=0)
                for pixels in self.render_pixels(drives):
                    if self.canvas is None:
                        writer.submit(pixels)
                    else:
                        # Submit one full-size frame at a time to bound host memory.
                        for pixel in pixels:
                            compose_start = time.perf_counter()
                            composed = self.canvas.compose(pixel)
                            times["composition"] += time.perf_counter() - compose_start
                            writer.submit(composed[None])
                times["render"] += time.perf_counter() - tic
                if progress is not None:
                    progress(frame + 5, frames)
                print(
                    f"frames {frame + 5}/{frames}; seconds {time.perf_counter() - start:.2f}",
                    flush=True,
                )
        except BaseException:
            writer.abort()
            raise
        elapsed = time.perf_counter() - start
        finalize_start = time.perf_counter()
        try:
            cancel_check()
            writer.close()
        except BaseException:
            writer.abort()
            raise
        finalize_seconds = time.perf_counter() - finalize_start
        report = {
            "frames": frames,
            "video_seconds": frames / 25,
            "resolution": list(writer.size),
            "model_resolution": [512, 512],
            "source_resolution": list(self.source_size),
            "output_mode": self.output_mode,
            "pixel_format": writer.pixel_format,
            "crop_to_source": self.crop_to_source.tolist(),
            "composition_roi": list(self.canvas.roi) if self.canvas else None,
            "fps": 25,
            "steps": steps,
            "seed": seed,
            "prepare_seconds": prep,
            "generate_seconds": elapsed,
            "generation_fps": frames / elapsed,
            "stage_seconds": times,
            "mlx_peak_bytes": mx.get_peak_memory(),
            "all_neural_networks": "MLX",
            "renderer": self.renderer_mode,
            "render_fallbacks": self.render_fallbacks,
            "render_batch_size": self.render_batch_size,
            "asynchronous_encoding": self.asynchronous_encoding,
            "finalize_seconds": finalize_seconds,
            "total_seconds": time.perf_counter() - total_start,
            "tf32": os.environ.get("MLX_ENABLE_TF32", "1") != "0",
        }
        output.with_suffix(".json").write_text(json.dumps(report, indent=2))
        return report
