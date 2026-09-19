"""Dataset preparation and end-to-end native MLX RVC voice training."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import numpy as np
import soundfile as sf
from mlx.utils import tree_flatten, tree_map
from scipy.signal import butter, lfilter, resample_poly

from .contentvec import ContentVec
from .pitch import coarse_f0
from .rmvpe import RMVPE
from .training import (
    RVCMultiPeriodDiscriminator,
    RVCTrainingGenerator,
    discriminator_training_loss,
    generator_adversarial_training_loss,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _prefixed_arrays(prefix: str, tree) -> dict[str, mx.array]:
    arrays = {}

    def visit(path: tuple[str, ...], value) -> None:
        if isinstance(value, dict):
            for name, child in value.items():
                visit((*path, str(name)), child)
        elif isinstance(value, mx.array):
            arrays["/".join((prefix, *path))] = value

    visit((), tree)
    return arrays


def _extract_tree(arrays: dict[str, mx.array], prefix: str):
    marker = f"{prefix}/"
    result = {}
    found = False
    for name, value in arrays.items():
        if not name.startswith(marker):
            continue
        found = True
        path = name[len(marker) :].split("/")
        target = result
        for component in path[:-1]:
            target = target.setdefault(component, {})
        target[path[-1]] = value
    return result if found else None


def write_voice_manifests(
    output: Path,
    model_state: dict[str, mx.array],
    vectors: mx.array,
    *,
    segment_frames: int = 36,
) -> None:
    model_path = output / "model.safetensors"
    index_path = output / "index.safetensors"
    model_manifest = {
        "schema": "ai2apps.mlx-rvc-checkpoint/v1",
        "source": {"name": "native-mlx-training", "synthetic": False},
        "weights": {
            "name": model_path.name,
            "sha256": _sha256(model_path),
            "tensor_count": len(model_state),
            "parameter_count": sum(int(value.size) for value in model_state.values()),
            "dtype": "float32",
        },
        "model": {
            "spec_channels": 1025,
            "segment_size": segment_frames,
            "inter_channels": 192,
            "hidden_channels": 192,
            "filter_channels": 768,
            "heads": 2,
            "layers": 6,
            "kernel_size": 3,
            "dropout": 0.0,
            "resblock": "1",
            "resblock_kernel_sizes": [3, 7, 11],
            "resblock_dilation_sizes": [[1, 3, 5]] * 3,
            "upsample_rates": [12, 10, 2, 2],
            "upsample_initial_channels": 512,
            "upsample_kernel_sizes": [24, 20, 4, 4],
            "speaker_count": int(model_state["emb_g.weight"].shape[0]),
            "speaker_embedding_channels": 256,
            "sample_rate": 48000,
            "feature_version": "v2",
            "uses_f0": True,
        },
    }
    (output / "model.json").write_text(json.dumps(model_manifest, indent=2) + "\n")
    index_manifest = {
        "schema": "ai2apps.mlx-rvc-retrieval/v1",
        "source": {"name": "native-mlx-training-cache"},
        "vectors": {
            "name": index_path.name,
            "sha256": _sha256(index_path),
            "count": int(vectors.shape[0]),
            "dimensions": int(vectors.shape[1]),
            "dtype": "float32",
        },
        "search": {"implementation": "mlx-exact-top-k", "neighbors": 8},
    }
    (output / "index.json").write_text(json.dumps(index_manifest, indent=2) + "\n")


@dataclass(frozen=True)
class VoiceTrainingConfig:
    epochs: int = 30
    batch_size: int = 4
    segment_frames: int = 36
    learning_rate: float = 1e-4
    seed: int = 1234
    precision: str = "float16"
    save_every_epochs: int = 10
    adaptation: str = "safe"
    max_retrieval_vectors: int = 50_000

    def validate(self) -> None:
        if self.epochs < 1 or self.batch_size < 1 or self.segment_frames < 8:
            raise ValueError("invalid RVC training dimensions")
        if (
            self.learning_rate <= 0
            or self.precision not in {"float32", "float16", "bfloat16"}
            or self.adaptation not in {"safe", "full"}
            or self.max_retrieval_vectors < 8
        ):
            raise ValueError("invalid RVC training optimizer configuration")


def _spectrogram(audio: mx.array, n_fft: int = 2048, hop: int = 480) -> mx.array:
    padding = (n_fft - hop) // 2
    left = audio[1 : padding + 1][::-1]
    right = audio[-padding - 1 : -1][::-1]
    padded = mx.concatenate((left, audio, right))
    window = mx.array(np.hanning(n_fft + 1)[:-1].astype(np.float32))
    frames = mx.stack(
        [
            padded[start : start + n_fft] * window
            for start in range(0, padded.size - n_fft + 1, hop)
        ]
    )
    return mx.sqrt(mx.square(mx.abs(mx.fft.rfft(frames, axis=-1))) + 2e-7).T


class VoiceDatasetPreprocessor:
    def __init__(self, contentvec: ContentVec, rmvpe: RMVPE) -> None:
        self.contentvec = contentvec
        self.rmvpe = rmvpe

    def prepare(
        self,
        audio_files: list[Path],
        output: Path,
        *,
        progress: Callable[[dict], None] | None = None,
    ) -> dict:
        if output.exists():
            raise FileExistsError(f"training cache already exists: {output}")
        output.mkdir(parents=True)
        records = []
        highpass_b, highpass_a = butter(N=5, Wn=48, btype="highpass", fs=48_000)
        for index, path in enumerate(audio_files):
            audio, rate = sf.read(path, dtype="float32", always_2d=False)
            if audio.ndim == 2:
                audio = audio.mean(axis=1)
            if rate != 48_000:
                divisor = np.gcd(rate, 48_000)
                audio48 = resample_poly(
                    audio, 48_000 // divisor, rate // divisor
                ).astype(np.float32)
            else:
                audio48 = audio.astype(np.float32)
            filtered = lfilter(highpass_b, highpass_a, audio48).astype(np.float32)
            chunk_samples = int(3.7 * 48_000)
            stride_samples = int(3.4 * 48_000)
            chunks = []
            start = 0
            while filtered.size - start > int(4.0 * 48_000):
                chunks.append(filtered[start : start + chunk_samples])
                start += stride_samples
            chunks.append(filtered[start:])
            for chunk_index, chunk in enumerate(chunks):
                peak = float(np.max(np.abs(chunk))) if chunk.size else 0.0
                if not np.isfinite(peak) or peak <= 0.0 or peak > 2.5:
                    continue
                # Match the pinned RVC preprocessor: 75% peak-normalized signal
                # blended with 25% of the original waveform.
                audio48 = (
                    chunk / peak * np.float32(0.9 * 0.75)
                    + np.float32(0.25) * chunk
                ).astype(np.float32)
                audio16 = resample_poly(audio48, 1, 3).astype(np.float32)
                phone = mx.repeat(
                    self.contentvec(mx.array(audio16), version="v2"), 2, axis=1
                )[0]
                raw_f0 = np.asarray(self.rmvpe(mx.array(audio16)))
                pitch, pitchf = coarse_f0(raw_f0)
                spec = _spectrogram(mx.array(audio48))
                frames = min(
                    phone.shape[0],
                    pitch.size,
                    pitchf.size,
                    spec.shape[-1],
                    audio48.size // 480,
                )
                if frames < 36:
                    continue
                target = output / f"{index:05d}-{chunk_index:02d}.safetensors"
                mx.save_safetensors(
                    str(target),
                    {
                        "phone": phone[:frames].astype(mx.float32),
                        "pitch": mx.array(pitch[:frames], dtype=mx.int32),
                        "pitchf": mx.array(pitchf[:frames], dtype=mx.float32),
                        "spectrogram": spec[:, :frames].astype(mx.float32),
                        "waveform": mx.array(
                            audio48[: frames * 480], dtype=mx.float32
                        ),
                    },
                    metadata={"format": "ai2apps.mlx-rvc-training-example/v2"},
                )
                records.append(
                    {
                        "file": target.name,
                        "frames": int(frames),
                        "source": path.name,
                        "chunk": chunk_index,
                    }
                )
            if progress:
                progress(
                    {
                        "phase": "preprocess",
                        "current": index + 1,
                        "total": len(audio_files),
                    }
                )
            mx.clear_cache()
        if not records:
            raise ValueError("no training audio produced a usable RVC segment")
        manifest = {
            "schema": "ai2apps.mlx-rvc-training-cache/v2",
            "preprocessing": {
                "highpass_hz": 48,
                "chunk_seconds": 3.7,
                "overlap_seconds": 0.3,
                "peak_target": 0.9,
                "normalization_blend": 0.75,
            },
            "records": records,
        }
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return manifest


class MLXRVCVoiceTrainer:
    def __init__(self, generator_state: dict, discriminator_state: dict) -> None:
        self.generator_state = generator_state
        self.discriminator_state = discriminator_state

    def fit(
        self,
        cache: Path,
        output: Path,
        config: VoiceTrainingConfig,
        *,
        resume: Path | None = None,
        progress: Callable[[dict], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> dict:
        config.validate()
        if output.exists() and resume is None:
            raise FileExistsError(f"voice output already exists: {output}")
        output.mkdir(parents=True, exist_ok=resume is not None)
        manifest = json.loads((cache / "manifest.json").read_text())
        if manifest.get("schema") != "ai2apps.mlx-rvc-training-cache/v2":
            raise ValueError(
                "RVC training cache predates loudness-normalized preprocessing; "
                "remove it and preprocess the source audio again"
            )
        records = manifest.get("records", [])
        if not records:
            raise ValueError("RVC training cache is empty")
        dtype = {
            "float32": mx.float32,
            "float16": mx.float16,
            "bfloat16": mx.bfloat16,
        }[config.precision]
        resume_arrays = None
        resume_metadata = None
        start_epoch = 0
        step = 0
        if resume is not None:
            resume = resume.resolve()
            metadata_path = resume.with_suffix(".json")
            if not resume.is_file() or not metadata_path.is_file():
                raise FileNotFoundError("RVC resume checkpoint or metadata is missing")
            resume_arrays = mx.load(str(resume), format="safetensors")
            resume_metadata = json.loads(metadata_path.read_text())
            if resume_metadata.get("schema") != "ai2apps.mlx-rvc-training-state/v1":
                raise ValueError("unsupported RVC resume checkpoint schema")
            previous = resume_metadata.get("config", {})
            for field in (
                "batch_size",
                "segment_frames",
                "learning_rate",
                "seed",
                "precision",
                "adaptation",
            ):
                if previous.get(field) != getattr(config, field):
                    raise ValueError(f"RVC resume configuration mismatch: {field}")
            start_epoch = int(resume_metadata["epoch"])
            step = int(resume_metadata["step"])
            if config.epochs <= start_epoch:
                raise ValueError("target epochs must exceed the resume checkpoint epoch")
            generator_state = _extract_tree(resume_arrays, "generator")
            discriminator_state = _extract_tree(resume_arrays, "discriminator")
            if not isinstance(generator_state, dict) or not isinstance(
                discriminator_state, dict
            ):
                raise ValueError("RVC resume checkpoint lacks model weights")
        else:
            generator_state = self.generator_state
            discriminator_state = self.discriminator_state
        generator = RVCTrainingGenerator(
            {name: value.astype(dtype) for name, value in generator_state.items()}
        )
        if config.adaptation == "safe":
            generator.freeze_content_path()
        discriminator = RVCMultiPeriodDiscriminator(
            {
                name: value.astype(dtype)
                for name, value in discriminator_state.items()
            }
        )
        optimizer_g = optim.AdamW(config.learning_rate, betas=[0.8, 0.99], eps=1e-9)
        optimizer_d = optim.AdamW(config.learning_rate, betas=[0.8, 0.99], eps=1e-9)
        # FP16 parameters need FP32 Adam moments. Static loss scaling is not
        # used here: RVC's adversarial branches can overflow FP16 gradients
        # even at modest scales, while master weights prevent the optimizer
        # underflow that otherwise produces NaNs after the first updates.
        loss_scale = 1.0
        master_g = (
            tree_map(lambda value: value.astype(mx.float32), generator.trainable_parameters())
            if config.precision == "float16"
            else None
        )
        master_d = (
            tree_map(
                lambda value: value.astype(mx.float32),
                discriminator.trainable_parameters(),
            )
            if config.precision == "float16"
            else None
        )
        if resume_arrays is not None:
            saved_master_g = _extract_tree(resume_arrays, "master_g")
            saved_master_d = _extract_tree(resume_arrays, "master_d")
            if config.precision == "float16":
                if saved_master_g is None or saved_master_d is None:
                    raise ValueError("FP16 resume checkpoint lacks optimizer master weights")
                master_g, master_d = saved_master_g, saved_master_d
                generator.update(tree_map(lambda value: value.astype(dtype), master_g))
                discriminator.update(
                    tree_map(lambda value: value.astype(dtype), master_d)
                )
            optimizer_g.state = _extract_tree(resume_arrays, "optimizer_g")
            optimizer_d.state = _extract_tree(resume_arrays, "optimizer_d")

        def g_objective(model, *values):
            loss, metrics = generator_adversarial_training_loss(
                model, discriminator, *values
            )
            return loss * loss_scale, metrics

        def d_objective(model, *values):
            return discriminator_training_loss(model, *values) * loss_scale

        def finite_tree(values) -> bool:
            return all(
                bool(np.isfinite(np.asarray(value)).all())
                for _, value in tree_flatten(values)
            )

        def apply_update(model, optimizer, gradients, master):
            if master is None:
                optimizer.update(model, gradients)
                return None
            gradients = tree_map(
                lambda value: value.astype(mx.float32) / loss_scale, gradients
            )
            master = optimizer.apply_gradients(gradients, master)
            model.update(tree_map(lambda value: value.astype(dtype), master))
            return master

        grad_g = nn.value_and_grad(generator, g_objective)
        grad_d = nn.value_and_grad(discriminator, d_objective)
        started = time.perf_counter()
        last_metrics = {}
        for epoch in range(start_epoch + 1, config.epochs + 1):
            rng = np.random.default_rng(config.seed + epoch)
            order = rng.permutation(len(records))
            for batch_start in range(0, len(order), config.batch_size):
                if cancelled and cancelled():
                    raise InterruptedError("RVC voice training was cancelled")
                indices = order[batch_start : batch_start + config.batch_size]
                if len(indices) < config.batch_size:
                    indices = np.resize(indices, config.batch_size)
                samples = [
                    mx.load(str(cache / records[int(i)]["file"]), format="safetensors")
                    for i in indices
                ]
                offsets = [
                    int(
                        rng.integers(
                            0,
                            int(records[int(i)]["frames"]) - config.segment_frames + 1,
                        )
                    )
                    for i in indices
                ]

                def batch(
                    name,
                    transform=lambda value, _offset: value,
                    current_samples=samples,
                    current_offsets=offsets,
                ):
                    return mx.stack(
                        [
                            transform(sample[name], offset)
                            for sample, offset in zip(current_samples, current_offsets)
                        ]
                    )

                frames = config.segment_frames
                phone = batch(
                    "phone",
                    lambda value, offset, count=frames: value[offset : offset + count],
                ).astype(dtype)
                pitch = batch(
                    "pitch",
                    lambda value, offset, count=frames: value[offset : offset + count],
                )
                pitchf = batch(
                    "pitchf",
                    lambda value, offset, count=frames: value[offset : offset + count],
                ).astype(dtype)
                spec = batch(
                    "spectrogram",
                    lambda value, offset, count=frames: value[
                        :, offset : offset + count
                    ],
                ).astype(dtype)
                wave = batch(
                    "waveform",
                    lambda value, offset, count=frames: value[
                        offset * 480 : (offset + count) * 480
                    ],
                )[:, None].astype(dtype)
                mx.random.seed(config.seed + step + 1)
                noise = mx.random.normal((config.batch_size, 192, frames)).astype(dtype)
                values = (phone, pitch, pitchf, spec, noise, wave)
                generated, _ = generator(*values[:-1])
                loss_d, gradients_d = grad_d(discriminator, wave, generated)
                mx.eval(loss_d, gradients_d)
                if not np.isfinite(float(loss_d.item())) or not finite_tree(
                    gradients_d
                ):
                    raise FloatingPointError(
                        f"non-finite discriminator state at step {step + 1}"
                    )
                master_d = apply_update(
                    discriminator, optimizer_d, gradients_d, master_d
                )
                (loss_g, metrics), gradients_g = grad_g(generator, *values)
                mx.eval(loss_g, metrics, gradients_g)
                if not np.isfinite(float(loss_g.item())) or not finite_tree(
                    gradients_g
                ):
                    raise FloatingPointError(
                        f"non-finite generator state at step {step + 1}"
                    )
                master_g = apply_update(generator, optimizer_g, gradients_g, master_g)
                mx.eval(
                    loss_g,
                    loss_d,
                    metrics,
                    generator.parameters(),
                    discriminator.parameters(),
                )
                step += 1
                last_metrics = {
                    name: float(value.item()) for name, value in metrics.items()
                }
            event = {
                "phase": "training",
                "current": epoch,
                "total": config.epochs,
                "epoch": epoch,
                "epochs": config.epochs,
                "step": step,
                "loss_g": float(loss_g.item()) / loss_scale,
                "loss_d": float(loss_d.item()) / loss_scale,
                **last_metrics,
            }
            if progress:
                progress(event)
            if epoch % config.save_every_epochs == 0 or epoch == config.epochs:
                mx.save_safetensors(
                    str(output / f"generator-e{epoch}.safetensors"),
                    {
                        name: value.astype(mx.float32)
                        for name, value in generator.weights.items()
                    },
                )
                state_arrays = {
                    **_prefixed_arrays("generator", generator.weights),
                    **_prefixed_arrays("discriminator", discriminator.weights),
                    **_prefixed_arrays("optimizer_g", optimizer_g.state),
                    **_prefixed_arrays("optimizer_d", optimizer_d.state),
                }
                if master_g is not None and master_d is not None:
                    state_arrays.update(_prefixed_arrays("master_g", master_g))
                    state_arrays.update(_prefixed_arrays("master_d", master_d))
                state_path = output / "training-state.safetensors"
                temporary_state = output / "training-state.tmp.safetensors"
                mx.save_safetensors(
                    str(temporary_state),
                    state_arrays,
                    metadata={"format": "ai2apps.mlx-rvc-training-state/v1"},
                )
                temporary_state.replace(state_path)
                state_metadata = {
                    "schema": "ai2apps.mlx-rvc-training-state/v1",
                    "epoch": epoch,
                    "step": step,
                    "config": asdict(config),
                    "cache_schema": manifest["schema"],
                }
                temporary_metadata = output / "training-state.tmp.json"
                temporary_metadata.write_text(
                    json.dumps(state_metadata, indent=2) + "\n"
                )
                temporary_metadata.replace(output / "training-state.json")
        final = {
            name: value.astype(mx.float32)
            for name, value in generator.weights.items()
            if not name.startswith("enc_q.")
        }
        model_path = output / "model.safetensors"
        mx.save_safetensors(
            str(model_path), final, metadata={"format": "ai2apps.mlx-rvc.weights/v1"}
        )
        vectors = mx.concatenate(
            [
                mx.load(str(cache / row["file"]), format="safetensors")["phone"]
                for row in records
            ],
            axis=0,
        )
        if vectors.shape[0] > config.max_retrieval_vectors:
            selected = np.linspace(
                0,
                vectors.shape[0] - 1,
                config.max_retrieval_vectors,
                dtype=np.int32,
            )
            vectors = vectors[mx.array(selected)]
        index_path = output / "index.safetensors"
        mx.save_safetensors(
            str(index_path),
            {"vectors": vectors.astype(mx.float32)},
            metadata={"format": "ai2apps.mlx-rvc.retrieval/v1", "metric": "squared_l2"},
        )
        write_voice_manifests(
            output, final, vectors, segment_frames=config.segment_frames
        )
        report = {
            "schema": "ai2apps.mlx-rvc-training-report/v1",
            "config": asdict(config),
            "records": len(records),
            "steps": step,
            "elapsed_seconds": time.perf_counter() - started,
            "metrics": last_metrics,
        }
        (output / "training-report.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        return report
