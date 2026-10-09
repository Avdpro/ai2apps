"""Offline native MLX ACE-Step inference using a Host-granted checkpoint."""

import gc
import json
import os
import sys
from pathlib import Path


def _generate(checkpoint, config, params, output, check, report):
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        os.environ[key] = "1"
    os.environ["USE_TORCH"] = "0"
    os.environ["USE_TF"] = "0"
    vendor = str(Path(__file__).parent / "vendor")
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
    import mlx.core as mx
    import numpy as np
    import soundfile as sf
    from mlx_audio.tts.models.ace_step.ace_step import Model
    from mlx_audio.tts.models.ace_step.config import ModelConfig

    model = None
    try:
        check()
        model = Model(
            ModelConfig.from_dict(json.loads((checkpoint / "config.json").read_text()))
        )
        model.load_weights(
            list(mx.load(str(checkpoint / "model.safetensors")).items()), strict=True
        )
        model._model_path = str(checkpoint)
        model = Model.post_load_hook(model, checkpoint)
        if (
            model.text_encoder is None
            or model.vae is None
            or model.silence_latent is None
        ):
            raise RuntimeError("Incomplete native ACE-Step components")
        model._cancel_check = check
        model._progress = lambda i, n: report("sampling", i, n)
        original_lm = model._get_or_load_lm

        def load_lm(*args, **kwargs):
            check()
            result = original_lm(*args, **kwargs)
            result._cancel_check = check
            report("planning")
            return result

        model._get_or_load_lm = load_lm
        original_hints = model._generate_lm_hints

        def hints(*args, **kwargs):
            result = original_hints(*args, **kwargs)
            check()
            if result is None:
                raise RuntimeError("Planner produced no audio codes")
            return result

        model._generate_lm_hints = hints
        original_decode = model.vae.decode

        def decode(*args, **kwargs):
            check()
            report("decoding")
            waveform = original_decode(*args, **kwargs)
            peak = float(mx.max(mx.abs(waveform)).item())
            if not np.isfinite(peak):
                raise RuntimeError("Non-finite generated waveform")
            return waveform * min(1.0, 0.95 / max(peak, 1e-12))

        model.vae.decode = decode
        mx.eval(model.parameters())
        check()
        for result in model.generate(
            text=params["prompt"],
            lyrics=params["lyrics"],
            duration=params["duration"],
            seed=params["seed"],
            num_steps=params["steps"],
            vocal_language=params["language"],
            lm_model_size=str(checkpoint / "lm"),
            use_lm=True,
            verbose=False,
        ):
            check()
            data = np.array(result.audio.astype(mx.float32))
            if not np.isfinite(data).all() or np.max(np.abs(data)) < 1e-5:
                raise RuntimeError("Invalid or silent generated waveform")
            if abs(len(data) / result.sample_rate - params["duration"]) > 0.25:
                raise RuntimeError("Generated duration differs from request")
            sf.write(output, data, result.sample_rate, subtype="PCM_16")
        if not output.is_file():
            raise RuntimeError("Model produced no audio")
        if "torch" in sys.modules:
            raise RuntimeError("Pure MLX inference unexpectedly imported torch")
    finally:
        if model is not None:
            # Drop closures that retain bound methods before releasing Metal arrays.
            for name in ("_get_or_load_lm", "_generate_lm_hints"):
                model.__dict__.pop(name, None)
            if model.vae is not None:
                model.vae.__dict__.pop("decode", None)
        model = None
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
