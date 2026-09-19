"""Isolated AI2Apps Model Worker adapter for native MLX-RVC."""

from __future__ import annotations

import asyncio
import json
import shutil
import threading
import zipfile
from pathlib import Path
from typing import NamedTuple

import mlx.core as mx
import numpy as np
import soundfile as sf
from mlx_rvc.contentvec import ContentVec
from mlx_rvc.pipeline import ConversionOptions, RVCInferencePipeline
from mlx_rvc.rmvpe import RMVPE
from mlx_rvc.synthesizer import RVCSynthesizer
from mlx_rvc.voice_training import (
    MLXRVCVoiceTrainer,
    VoiceDatasetPreprocessor,
    VoiceTrainingConfig,
)
from scipy.signal import resample_poly

from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError


class LoadedVoice(NamedTuple):
    pipeline: RVCInferencePipeline
    retrieval_vectors: mx.array | None


def _number(payload: dict, name: str, default, cast):
    value = payload.get(name)
    if value in {None, ""}:
        return default
    try:
        return cast(value)
    except (TypeError, ValueError) as error:
        raise ModelWorkerError(f"{name} is invalid", code="invalid_request") from error


class MLXRVCAdapter:
    def __init__(self, context) -> None:
        self.context = context
        self._voices: dict[str, LoadedVoice] = {}
        self._lock = asyncio.Lock()
        self._cancellations: dict[str, threading.Event] = {}
        self._worker_cpu_stream = mx.new_thread_local_stream(mx.cpu)
        self._worker_gpu_stream = mx.new_thread_local_stream(mx.gpu)

    async def stop(self) -> None:
        self._voices.clear()
        mx.clear_cache()

    def cancel(self, request_id: str) -> None:
        event = self._cancellations.get(request_id)
        if event is not None:
            event.set()

    @staticmethod
    def _extract_dataset(source: Path, destination: Path) -> list[Path]:
        destination.mkdir()
        files = []
        total = 0
        with zipfile.ZipFile(source) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if not 1 <= len(members) <= 500:
                raise ModelWorkerError("dataset ZIP must contain 1 to 500 WAV files")
            for index, member in enumerate(members):
                if Path(member.filename).suffix.lower() != ".wav":
                    raise ModelWorkerError("dataset ZIP may contain WAV files only")
                total += member.file_size
                if total > 2 * 1024 * 1024 * 1024:
                    raise ModelWorkerError("expanded training dataset is too large")
                target = destination / f"{index:05d}.wav"
                with archive.open(member) as reader, target.open("wb") as writer:
                    shutil.copyfileobj(reader, writer)
                files.append(target)
        return files

    async def _train_voice(self, request):
        payload = dict(request.payload)
        model_id = payload.get("model")
        if not isinstance(model_id, str) or not model_id:
            raise ModelWorkerError("model is required", code="invalid_request")
        declaration = self._declaration(model_id)
        metadata = declaration.get("metadata", {})
        required = ("contentvec", "rmvpe", "training")
        if not all(
            isinstance(metadata.get(f"{name}_subdir"), str)
            or isinstance(metadata.get(f"{name}_model_id"), str)
            for name in required
        ):
            raise ModelWorkerError("MLX-RVC training checkpoints are not declared")
        dataset_root = request.output_root / "dataset"
        cache_root = request.output_root / "cache"
        voice_root = request.output_root / "voice"
        files = self._extract_dataset(request.part("dataset").path, dataset_root)
        loop = asyncio.get_running_loop()
        cancellation = threading.Event()
        self._cancellations[request.request_id] = cancellation

        def report(event):
            if request.progress:
                asyncio.run_coroutine_threadsafe(request.progress(event), loop)

        def run():
            with mx.stream(self._worker_cpu_stream), mx.stream(self._worker_gpu_stream):
                contentvec = ContentVec.from_directory(
                    self._declared_checkpoint_root(declaration, "contentvec")
                )
                rmvpe = RMVPE.from_directory(
                    self._declared_checkpoint_root(declaration, "rmvpe")
                )
                VoiceDatasetPreprocessor(contentvec, rmvpe).prepare(
                    files, cache_root, progress=report
                )
                training_root = self._declared_checkpoint_root(declaration, "training")
                trainer = MLXRVCVoiceTrainer(
                    mx.load(
                        str(training_root / "generator.safetensors"),
                        format="safetensors",
                    ),
                    mx.load(
                        str(training_root / "discriminator.safetensors"),
                        format="safetensors",
                    ),
                )
                return trainer.fit(
                    cache_root,
                    voice_root,
                    VoiceTrainingConfig(
                        epochs=_number(payload, "epochs", 30, int),
                        batch_size=_number(payload, "batch_size", 4, int),
                        precision=str(payload.get("precision") or "float16"),
                    ),
                    progress=report,
                    cancelled=cancellation.is_set,
                )

        try:
            await asyncio.to_thread(run)
        except InterruptedError as error:
            raise ModelWorkerError(
                str(error), code="cancelled", status_code=409
            ) from error
        finally:
            self._cancellations.pop(request.request_id, None)
        bundle_base = request.output_root / "mlx-rvc-voice"
        bundle = Path(shutil.make_archive(str(bundle_base), "zip", voice_root))
        return ModelWorkerArtifact(
            bundle,
            media_type="application/zip",
            filename="mlx-rvc-voice.zip",
        )

    def _declaration(self, model_id: str) -> dict:
        declaration = next(
            (
                item
                for item in self.context.models
                if model_id in {item.get("id"), item.get("upstream_id")}
                and not item.get("metadata", {}).get("internal")
            ),
            None,
        )
        if declaration is None:
            raise ModelWorkerError("Unsupported MLX-RVC voice", code="model_not_found")
        return declaration

    def _checkpoint_path(self, model_id: str) -> Path:
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError(
                f"Required checkpoint is not installed: {model_id}",
                code="model_unavailable",
                status_code=503,
            )
        return Path(checkpoint.path)

    def _declared_checkpoint_root(self, declaration: dict, name: str) -> Path:
        """Resolve a component in either the composite or legacy split layout."""

        metadata = declaration.get("metadata", {})
        subdirectory = metadata.get(f"{name}_subdir")
        if isinstance(subdirectory, str) and subdirectory:
            if Path(subdirectory).is_absolute() or ".." in Path(subdirectory).parts:
                raise ModelWorkerError("Invalid MLX-RVC checkpoint declaration")
            return self._checkpoint_path(str(declaration["id"])) / subdirectory
        model_id = metadata.get(f"{name}_model_id")
        if not isinstance(model_id, str) or not model_id:
            raise ModelWorkerError(f"MLX-RVC {name} checkpoint is not declared")
        return self._checkpoint_path(model_id)

    def _load_voice(self, declaration: dict) -> LoadedVoice:
        model_id = str(declaration["id"])
        loaded = self._voices.get(model_id)
        if loaded is not None:
            return loaded
        checkpoint_root = self._checkpoint_path(model_id)
        manifest_path = checkpoint_root / "ai2apps-checkpoint.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ModelWorkerError(
                "Invalid MLX-RVC checkpoint manifest",
                code="model_unavailable",
                status_code=503,
            ) from error
        if manifest.get("schema") != "ai2apps.mlx-rvc-composite/v1":
            raise ModelWorkerError(
                "Unsupported MLX-RVC checkpoint layout",
                code="model_unavailable",
                status_code=503,
            )
        voice_root = self._declared_checkpoint_root(declaration, "voice")
        state = {
            name: np.asarray(value)
            for name, value in mx.load(
                str(voice_root / "model.safetensors"), format="safetensors"
            ).items()
        }
        index_path = voice_root / "index.safetensors"
        vectors = (
            mx.load(str(index_path), format="safetensors")["vectors"]
            if index_path.is_file()
            else None
        )
        loaded = LoadedVoice(
            RVCInferencePipeline(
                ContentVec.from_directory(
                    self._declared_checkpoint_root(declaration, "contentvec")
                ),
                RMVPE.from_directory(
                    self._declared_checkpoint_root(declaration, "rmvpe")
                ),
                RVCSynthesizer(state),
            ),
            vectors,
        )
        self._voices[model_id] = loaded
        return loaded

    async def invoke(self, request):
        if request.operation == "audio_voice_training":
            return await self._train_voice(request)
        if request.operation != "audio_process":
            raise ModelWorkerError(f"Unsupported operation: {request.operation}")
        payload = dict(request.payload)
        task = str(payload.get("task") or "voice_conversion")
        if task != "voice_conversion":
            raise ModelWorkerError(
                "task must be voice_conversion", code="invalid_request"
            )
        model_id = payload.get("model")
        if not isinstance(model_id, str) or not model_id:
            raise ModelWorkerError("model is required", code="invalid_request")
        declaration = self._declaration(model_id)
        retrieval_rate = _number(payload, "retrieval_rate", 0.75, float)
        options = ConversionOptions(
            speaker_id=_number(payload, "speaker_id", 0, int),
            semitones=_number(payload, "semitones", 0.0, float),
            retrieval_rate=retrieval_rate,
            protect=_number(payload, "protect", 0.33, float),
            seed=_number(payload, "seed", 0, int),
        )
        try:
            options.validate()
        except ValueError as error:
            raise ModelWorkerError(str(error), code="invalid_request") from error
        source, sample_rate = sf.read(request.part("file").path, dtype="float32")
        if source.ndim == 2:
            source = source.mean(axis=1)
        if sample_rate != 16_000:
            divisor = np.gcd(sample_rate, 16_000)
            source = resample_poly(source, 16_000 // divisor, sample_rate // divisor)
        async with self._lock:

            def convert():
                with (
                    mx.stream(self._worker_cpu_stream),
                    mx.stream(self._worker_gpu_stream),
                ):
                    loaded = self._load_voice(declaration)
                    if loaded.retrieval_vectors is None and retrieval_rate != 0:
                        raise ModelWorkerError(
                            "This voice does not include a retrieval index",
                            code="unsupported_feature",
                        )
                    return loaded.pipeline.convert_long_16khz(
                        source.astype(np.float32),
                        options=options,
                        retrieval_vectors=loaded.retrieval_vectors,
                    )

            output = await asyncio.to_thread(
                convert,
            )
        path = request.output_root / "voice-converted.wav"
        sf.write(path, output, 48_000, subtype="PCM_16")
        return ModelWorkerArtifact(path, media_type="audio/wav", filename=path.name)


def create_adapter(context):
    return MLXRVCAdapter(context)
