"""Offline image + audio Teacher CLI; all checkpoints must already be local."""

import argparse
from math import gcd
from pathlib import Path

import mlx.core as mx
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from .checkpoint import load_teacher
from .codec import SpeechCodec
from .conditioners import TextEncoder
from .pipeline import TeacherPipeline
from .wan_vae import WanVAE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoints",
        type=Path,
        required=True,
        help="Prepared local checkpoint root; see Package README",
    )
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", default="A person speaking.")
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--window-frames", type=int, default=125)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    root = args.checkpoints
    if args.output.resolve() in {args.audio.resolve(), args.image.resolve()}:
        parser.error("Output must differ from inputs")
    waveform, rate = sf.read(args.audio, dtype="float32", always_2d=True)
    waveform = waveform.mean(axis=1)
    if not waveform.size or not np.isfinite(waveform).all():
        parser.error("Audio must be nonempty and finite")
    codec = SpeechCodec(root / "qwen-codec")
    divisor = gcd(rate, codec.input_sample_rate)
    codes = codec.encode(
        mx.array(
            resample_poly(waveform, codec.input_sample_rate // divisor, rate // divisor)
        )
    )
    text = TextEncoder(root / "wan13b/t5.safetensors", root / "wan13b/google/umt5-xxl")
    model = load_teacher(
        root / "wan13b",
        root / "omniavatar/model.safetensors",
        root / "exomni/video_generator/teacher.safetensors",
    )
    vae = WanVAE(root / "flashhead/VAE_Wan/Wan2.1_VAE.safetensors")
    print(
        TeacherPipeline(model, vae, codec, text).generate(
            args.image,
            codes,
            args.audio,
            args.output,
            prompt=args.prompt,
            size=args.size,
            steps=args.steps,
            window_frames=args.window_frames,
            seed=args.seed,
        )
    )


if __name__ == "__main__":
    main()
