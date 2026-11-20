"""Offline one-person InfiniteTalk CLI using prepared local checkpoints."""

import argparse
from pathlib import Path

import mlx.core as mx
import numpy as np
import soundfile as sf

from .checkpoint import load_model
from .conditioners import AudioEncoder, ImageEncoder, TextEncoder
from .pipeline import InfiniteTalkPipeline
from .wan_vae import WanVAE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoints", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", default="A person speaking.")
    parser.add_argument("--size", type=int, default=480)
    parser.add_argument("--steps", type=int, default=40)
    parser.add_argument("--window-frames", type=int, default=81)
    parser.add_argument("--motion-frames", type=int, default=25)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    root = args.checkpoints
    if args.output.resolve() in {args.audio.resolve(), args.image.resolve()}:
        parser.error("Output must differ from inputs")
    wave, rate = sf.read(args.audio, dtype="float32", always_2d=True)
    wave = wave.mean(axis=1)
    frames = int(wave.size * 25 / rate)
    if rate != 16000 or frames < 1 or not np.isfinite(wave).all():
        parser.error("Expected finite 16 kHz audio of at least one frame")
    audio = AudioEncoder(root / "chinese-wav2vec2").hidden_states(
        mx.array(wave), frames
    )
    text = TextEncoder(root / "wan13b/t5.safetensors", root / "wan13b/google/umt5-xxl")
    clip = ImageEncoder(root / "wan14b/clip.safetensors")
    vae = WanVAE(root / "flashhead/VAE_Wan/Wan2.1_VAE.safetensors")
    model = load_model(
        root / "wan14b", root / "infinitetalk/single/infinitetalk.safetensors"
    )
    print(
        InfiniteTalkPipeline(model, vae, text, clip).generate(
            args.image,
            audio,
            args.audio,
            args.output,
            prompt=args.prompt,
            size=args.size,
            steps=args.steps,
            window_frames=args.window_frames,
            motion_frames=args.motion_frames,
            seed=args.seed,
        )
    )


if __name__ == "__main__":
    main()
