#!/usr/bin/env python3
"""Run a native MLX RVC reconstruction update on one fixed upstream sample."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import numpy as np
import soundfile as sf

from .training import (
    RVCMultiPeriodDiscriminator,
    RVCTrainingGenerator,
    discriminator_training_loss,
    generator_adversarial_training_loss,
    generator_reconstruction_loss,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("--sample", default="0_2")
    parser.add_argument("--frames", type=int, default=36)
    parser.add_argument("--offset", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--steps", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--discriminator", type=Path)
    parser.add_argument(
        "--precision", choices=("float32", "bfloat16"), default="float32"
    )
    args = parser.parse_args()

    root = args.experiment
    name = args.sample
    phone = np.repeat(np.load(root / "3_feature768" / f"{name}.npy"), 2, axis=0)
    pitch = np.load(root / "2a_f0" / f"{name}.wav.npy")
    pitchf = np.load(root / "2b-f0nsf" / f"{name}.wav.npy")
    try:
        import torch
    except ImportError as error:
        raise SystemExit("the oracle cache converter requires Torch") from error
    spec = torch.load(root / "0_gt_wavs" / f"{name}.spec.pt", weights_only=True).numpy()
    wave, sample_rate = sf.read(root / "0_gt_wavs" / f"{name}.wav", dtype="float32")
    if sample_rate != 48_000:
        raise SystemExit("expected a 48 kHz training fixture")

    start, end = args.offset, args.offset + args.frames
    available = min(len(phone), len(pitch), len(pitchf), spec.shape[-1])
    if not 0 <= start < end <= available:
        raise SystemExit(f"segment [{start}, {end}) exceeds {available} frames")
    state = mx.load(str(args.checkpoint), format="safetensors")
    compute_dtype = mx.bfloat16 if args.precision == "bfloat16" else mx.float32
    state = {name: value.astype(compute_dtype) for name, value in state.items()}
    model = RVCTrainingGenerator(state)
    model.freeze_content_path()
    optimizer = optim.AdamW(
        learning_rate=args.learning_rate, betas=[0.8, 0.99], eps=1e-9
    )
    discriminator = None
    discriminator_optimizer = None
    if args.discriminator:
        discriminator = RVCMultiPeriodDiscriminator(
            {
                name: value.astype(compute_dtype)
                for name, value in mx.load(
                    str(args.discriminator), format="safetensors"
                ).items()
            }
        )
        discriminator_optimizer = optim.AdamW(
            learning_rate=args.learning_rate, betas=[0.8, 0.99], eps=1e-9
        )

        def generator_objective(trainable_model, *values):
            return generator_adversarial_training_loss(
                trainable_model, discriminator, *values
            )

        loss_and_grad = nn.value_and_grad(model, generator_objective)
        discriminator_loss_and_grad = nn.value_and_grad(
            discriminator, discriminator_training_loss
        )
    else:
        loss_and_grad = nn.value_and_grad(model, generator_reconstruction_loss)
    inputs = (
        mx.array(phone[start:end][None].astype(np.float32)),
        mx.array(pitch[start:end][None].astype(np.int32)),
        mx.array(pitchf[start:end][None].astype(np.float32)),
        mx.array(spec[:, start:end][None].astype(np.float32)),
        mx.random.normal((1, 192, args.frames)),
        mx.array(wave[start * 480 : end * 480][None, None].astype(np.float32)),
    )
    if args.batch_size > 1:
        inputs = tuple(mx.repeat(value, args.batch_size, axis=0) for value in inputs)
    inputs = tuple(
        value if value.dtype in {mx.int32, mx.uint32} else value.astype(compute_dtype)
        for value in inputs
    )
    mx.clear_cache()
    mx.reset_peak_memory()
    elapsed_steps = []
    for _ in range(args.steps):
        started = time.perf_counter()
        if discriminator is not None:
            generated, _ = model(*inputs[:-1])
            disc_loss, discriminator_gradients = discriminator_loss_and_grad(
                discriminator, inputs[-1], generated
            )
            discriminator_optimizer.update(discriminator, discriminator_gradients)
        (loss, metrics), gradients = loss_and_grad(model, *inputs)
        optimizer.update(model, gradients)
        evaluation = [loss, metrics, model.parameters(), optimizer.state]
        if discriminator is not None:
            evaluation.extend(
                [
                    disc_loss,
                    discriminator.parameters(),
                    discriminator_optimizer.state,
                ]
            )
        mx.eval(*evaluation)
        elapsed_steps.append(time.perf_counter() - started)
    payload = {
        "loss": float(loss.item()),
        "mel_loss": float(metrics["mel"].item()),
        "kl_loss": float(metrics["kl"].item()),
        "elapsed_seconds": elapsed_steps,
        "warm_step_seconds": min(elapsed_steps),
        "frames": args.frames,
        "batch_size": args.batch_size,
        "precision": args.precision,
        "audio_seconds": args.frames * 0.01,
        "peak_memory_bytes": mx.get_peak_memory(),
        "parameter_count": sum(int(value.size) for value in state.values()),
        "finite": bool(mx.isfinite(loss).item()),
    }
    if discriminator is not None:
        payload["discriminator_loss"] = float(disc_loss.item())
    print(json.dumps(payload, indent=2))
    if not payload["finite"]:
        raise SystemExit("MLX RVC training step produced a non-finite loss")


if __name__ == "__main__":
    main()
