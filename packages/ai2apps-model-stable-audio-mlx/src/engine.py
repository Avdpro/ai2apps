"""Offline native MLX Stable Audio inference using Host-granted weight files."""

import gc
import os
import runpy
import sys
from pathlib import Path


def _generate(checkpoint, config, params, output, check, report):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["USE_TORCH"] = "0"
    os.environ["USE_TF"] = "0"
    vendor = Path(__file__).parent / "vendor"
    scripts = str(vendor / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import mlx.core as mx
    import numpy as np
    import soundfile as sf

    previous_argv = sys.argv
    state = namespace = None
    try:
        check()
        sys.argv = [
            "sa3_mlx.py",
            "--dit",
            config["variant"],
            "--decoder",
            "same-s",
            "--prompt",
            params["prompt"],
            "--seconds",
            str(params["duration"]),
            "--steps",
            str(params["steps"]),
            "--seed",
            str(params["seed"]),
            "--out",
            str(output),
        ]
        state = runpy.run_path(str(vendor / "scripts/sa3_mlx.py"))
        namespace = state["main"].__globals__
        namespace["print"] = lambda *args, **kwargs: None

        def local_weight(name):
            check()
            path = checkpoint / "MLX" / Path(name).name
            if not path.is_file():
                raise RuntimeError("Declared checkpoint file is missing: " + path.name)
            return path

        namespace["ensure_local"] = local_weight
        namespace["is_present"] = lambda name: (
            checkpoint / "MLX" / Path(name).name
        ).is_file()
        original_sample = namespace["sample_flow_pingpong"]

        def sample(*args, **kwargs):
            before = kwargs.get("before_step")

            def before_step(*a, **kw):
                check()
                if before:
                    before(*a, **kw)

            kwargs["before_step"] = before_step
            kwargs["on_step"] = lambda i, n: report("sampling", i, n)
            return original_sample(*args, **kwargs)

        namespace["sample_flow_pingpong"] = sample

        def save_audio(path, audio, sample_rate=44100):
            check()
            report("writing")
            if not np.isfinite(audio).all() or np.max(np.abs(audio)) < 1e-5:
                raise RuntimeError("Invalid or silent generated waveform")
            data = audio.T
            if abs(len(data) / sample_rate - params["duration"]) > 0.25:
                raise RuntimeError("Generated duration differs from request")
            gain = min(1.0, 0.95 / max(float(np.abs(data).max()), 1e-12))
            sf.write(output, data * gain, sample_rate, subtype="PCM_16")

        namespace["save_wav"] = save_audio
        state["main"]()
        check()
        if not output.is_file():
            raise RuntimeError("Model produced no audio")
        if "torch" in sys.modules:
            raise RuntimeError("Pure MLX inference unexpectedly imported torch")
    finally:
        sys.argv = previous_argv
        if namespace is not None:
            namespace.clear()
        state = namespace = None
        gc.collect()
        mx.clear_cache()


def generate(checkpoint, config, params, output, check, report):
    import mlx.core as mx

    try:
        return _generate(checkpoint, config, params, output, check, report)
    except BaseException as error:
        if getattr(error, "code", None) == "generation_cancelled":
            # A cancellation traceback retains upstream sampling frames and
            # their large arrays. Keep the public error, drop those frames.
            error.__traceback__ = None
            raise error from None
        raise
    finally:
        # The inference frame and its bound methods must be gone before GC.
        gc.collect()
        mx.clear_cache()
