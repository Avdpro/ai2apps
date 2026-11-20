"""Shared pure-Python adapter source staged into each depth Model Package.

No user-home lookup, downloads, pickle, or developer checkpoint paths.
"""
import os
os.environ["MLX_ENABLE_TF32"] = "0"

import asyncio
import gc
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
import mlx.core as mx
from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError
from da import DepthAnythingLarge


class DepthAdapter:
    family = None
    filename = None

    def __init__(self, context):
        self.context = context
        self.model = None

    async def start(self):
        pass

    async def stop(self):
        self.model = None
        gc.collect()
        mx.clear_cache()

    def _compute(self, rgb, checkpoint, size):
        if self.family == "da":
            if self.model is None:
                self.model = DepthAnythingLarge(checkpoint / self.filename)
            depth = np.asarray(self.model.infer_rgb(rgb, size), dtype=np.float32)
            return {"depth": depth, "depth_kind": np.array("relative_inverse_depth")}
        from vggt import VGGTOmegaSingle
        from geometry import camera_from_encoding
        if self.model is None:
            self.model = VGGTOmegaSingle(checkpoint / self.filename)
        h, w = rgb.shape[:2]
        scale = 512 / max(h, w)
        sw, sh = max(1, round(w * scale)), max(1, round(h * scale))
        left, top = (512-sw)//2, (512-sh)//2
        canvas = Image.new("RGB", (512,512))
        canvas.paste(Image.fromarray(rgb).resize((sw,sh), Image.Resampling.BICUBIC), (left,top))
        result = self.model(mx.array(np.asarray(canvas)[None].astype(np.float32)/255))
        mx.eval(result)
        _, intrinsic = camera_from_encoding(np.asarray(result["pose_enc"]).reshape(-1,9)[-1])
        intrinsic = intrinsic.copy()
        intrinsic[0,2] -= left
        intrinsic[1,2] -= top
        intrinsic[0,:] *= w/sw
        intrinsic[1,:] *= h/sh
        def restore(value):
            field=np.asarray(value,dtype=np.float32).squeeze()[top:top+sh,left:left+sw]
            return np.asarray(Image.fromarray(field).resize((w,h),Image.Resampling.BILINEAR),dtype=np.float32)
        return {"depth": restore(result["depth"]), "depth_kind": np.array("camera_depth"),
                "confidence": restore(result["depth_conf"]), "intrinsics": intrinsic.astype(np.float32)}

    async def invoke(self, request):
        if request.operation != "depth_estimation":
            raise ModelWorkerError("Unsupported operation", status_code=422)
        checkpoint = self.context.checkpoint_for(request.payload["model"])
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError("Checkpoint is not installed", code="model_unavailable", status_code=503)
        size = request.payload.get("input_size", 1036 if self.family=="da" else 512)
        if type(size) is not int or (self.family=="da" and size not in (518, 756, 1036)) or (self.family=="vggt" and size != 512):
            raise ModelWorkerError("Unsupported depth input size", status_code=422)
        try:
            with Image.open(request.part("image").path) as source:
                if source.width*source.height > 16_000_000 or min(source.size)<32 or max(source.size)/min(source.size)>4:
                    raise ModelWorkerError("Image exceeds supported dimensions/aspect ratio", status_code=422)
                rgb = np.asarray(ImageOps.exif_transpose(source).convert("RGB"))
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise ModelWorkerError("Unable to decode input image", status_code=422) from error
        # Keep the event loop responsive. Cancellation waits for the native
        # invocation to exit before allowing Runtime cleanup or another job.
        task = asyncio.create_task(asyncio.to_thread(self._compute, rgb, checkpoint.path, size))
        try:
            output = await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
            if not task.cancelled():
                task.exception()
            raise
        if output["depth"].shape != rgb.shape[:2] or not np.isfinite(output["depth"]).all():
            raise ModelWorkerError("Invalid depth output", status_code=500)
        for value in output.values():
            if np.issubdtype(value.dtype, np.number) and not np.isfinite(value).all():
                raise ModelWorkerError("Non-finite geometry output", status_code=500)
        if self.family=="vggt" and np.any(output["depth"]<=0):
            raise ModelWorkerError("Non-positive camera depth", status_code=500)
        output["source_size"] = np.array(rgb.shape[:2],dtype=np.int32)
        path = request.output_root / "depth.npz"
        np.savez(path, **output)
        mx.clear_cache()
        return ModelWorkerArtifact(path,"application/octet-stream","depth.npz")
