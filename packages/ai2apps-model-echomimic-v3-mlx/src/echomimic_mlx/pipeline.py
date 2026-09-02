"""Staged native-MLX EchoMimicV3 avatar generation pipeline."""

from __future__ import annotations

import gc
import hashlib
import json
import math
import threading
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, cast

import mlx.core as mx
import numpy as np
import numpy.typing as npt

from .audio_condition import project_audio_condition
from .audio_encoder import (
    split_wav2vec2_windows,
    wav2vec2_encode,
    wav2vec2_parameters_from_tensors,
    wav2vec2_tensor_names,
    wav2vec2_window_hidden_states,
)
from .checkpoints import DenoiseCheckpointStore
from .config import FlashTransformerConfiguration, GenerationRequest
from .image_encoder import (
    wan_clip_preprocess,
    wan_clip_vision_encode,
    wan_clip_vision_parameters_from_tensors,
    wan_clip_vision_tensor_names,
)
from .media import (
    load_reference_audio,
    prepare_reference_image,
    temporary_audio_segments,
    write_mp4_chunks_with_audio,
    write_mp4_with_audio,
)
from .rope import build_rope_table
from .safetensors_io import SelectiveSafeTensorReader
from .schedulers import FlowUniPCScheduler
from .teacache import TeaCacheState
from .text_encoder import (
    load_wan_t5_tokenizer,
    wan_t5_encode_trimmed,
    wan_t5_parameters_from_tensors,
    wan_t5_tensor_names,
    wan_t5_tokenize,
)
from .transformer import (
    WanBlockParameters,
    WanTransformerInputs,
    wan_attention_block,
    wan_output_head,
    wan_transformer_context,
    wan_transformer_inputs,
)
from .vae import (
    vae_decoder_tensor_names,
    vae_encoder_tensor_names,
    wan_vae_decode,
    wan_vae_decode_chunks,
    wan_vae_decoder_parameters_from_tensors,
    wan_vae_encode_mode,
    wan_vae_encoder_parameters_from_tensors,
)
from .weight_mapping import (
    full_transformer_tensor_names,
    wan_transformer_parameters_from_tensors,
)

ProgressCallback = Callable[[str, int, int], None]


class GenerationCancelled(RuntimeError):
    """Raised cooperatively when an in-flight generation is cancelled."""


class CancellationToken:
    """Thread-safe cancellation signal suitable for service and UI adapters."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise GenerationCancelled("generation was cancelled")


@dataclass(frozen=True, slots=True)
class PipelineModelPaths:
    transformer: Path
    vae: Path
    t5: Path
    tokenizer: Path
    clip: Path
    wav2vec2: Path

    @classmethod
    def from_directory(cls, directory: str | Path) -> PipelineModelPaths:
        root = Path(directory).expanduser().resolve()
        return cls(
            transformer=root / "echomimicv3-flash-pro" / "diffusion_pytorch_model.safetensors",
            vae=root / "Wan2.1_VAE.safetensors",
            t5=root / "models_t5_umt5-xxl-enc-bf16-local.safetensors",
            tokenizer=root / "umt5-xxl",
            clip=root / "models_clip_open-clip-xlm-roberta-large-vit-huge-14.safetensors",
            wav2vec2=root / "chinese-wav2vec2-base" / "model.safetensors",
        )

    def validate(self) -> None:
        paths = (
            self.transformer,
            self.vae,
            self.t5,
            self.tokenizer,
            self.clip,
            self.wav2vec2,
        )
        missing = [str(path) for path in paths if not path.exists()]
        if missing:
            raise FileNotFoundError(f"pipeline model assets are missing: {missing}")


@dataclass(frozen=True, slots=True)
class GenerationResult:
    frames: npt.NDArray[np.float32]
    audio_path: Path
    fps: int

    def save(self, path: str | Path) -> Path:
        return write_mp4_with_audio(self.frames, self.audio_path, path, fps=self.fps)


@dataclass(frozen=True, slots=True)
class EncodedConditions:
    text: mx.array
    image: mx.array
    first_audio: mx.array
    later_audio: mx.array
    inpaint: mx.array


def _release() -> None:
    gc.collect()
    mx.clear_cache()


def _read_cast(
    reader: SelectiveSafeTensorReader,
    names: tuple[str, ...],
    dtype: mx.Dtype | None = None,
) -> dict[str, mx.array]:
    tensors: dict[str, mx.array] = {}
    for name in names:
        value = reader.read(name)
        if dtype is not None and value.dtype != dtype:
            value = value.astype(dtype)
            mx.eval(value)
        tensors[name] = value
    return tensors


class AvatarPipeline:
    """Load one model family at a time and run the fixed 512x512 Flash path."""

    def __init__(self, paths: PipelineModelPaths, *, cache_conditions: bool = True) -> None:
        paths.validate()
        self.paths = paths
        self.configuration = FlashTransformerConfiguration()
        self.cache_conditions = cache_conditions
        self._condition_cache_lock = threading.Lock()
        self._condition_cache_key: tuple[object, ...] | None = None
        self._condition_cache_value: EncodedConditions | None = None

    @classmethod
    def from_pretrained(
        cls, model_dir: str | Path, *, cache_conditions: bool = True
    ) -> AvatarPipeline:
        return cls(PipelineModelPaths.from_directory(model_dir), cache_conditions=cache_conditions)

    @staticmethod
    def _file_signature(path: str | Path) -> tuple[str, int, int]:
        resolved = Path(path).expanduser().resolve()
        stat = resolved.stat()
        return str(resolved), stat.st_size, stat.st_mtime_ns

    def _checkpoint_store(
        self, request: GenerationRequest, path: str | Path | None
    ) -> DenoiseCheckpointStore | None:
        if path is None:
            return None
        if request.teacache_threshold > 0:
            raise ValueError("denoise checkpoints currently require exact mode without TeaCache")
        payload = {
            "request": asdict(request),
            "image": self._file_signature(request.image_path),
            "audio": self._file_signature(request.audio_path),
            "transformer": self._file_signature(self.paths.transformer),
        }
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return DenoiseCheckpointStore(path, fingerprint)

    def clear_condition_cache(self) -> None:
        """Release the bounded exact-request condition cache used by resident workers."""

        with self._condition_cache_lock:
            self._condition_cache_key = None
            self._condition_cache_value = None
        _release()

    @staticmethod
    def _progress(callback: ProgressCallback | None, phase: str, current: int, total: int) -> None:
        if callback is not None:
            callback(phase, current, total)

    def _encode_text(self, prompt: str) -> mx.array:
        tokenizer = load_wan_t5_tokenizer(self.paths.tokenizer)
        input_ids, attention_mask = wan_t5_tokenize([prompt], tokenizer)
        reader = SelectiveSafeTensorReader(self.paths.t5)
        parameters = wan_t5_parameters_from_tensors(_read_cast(reader, wan_t5_tensor_names()))
        output, lengths = wan_t5_encode_trimmed(
            input_ids,
            attention_mask,
            parameters,
            fast_attention=False,
            minimum_length=64,
        )
        mx.eval(output, lengths)
        length = int(cast(int, lengths[0].item()))
        context = output[:, :length].astype(mx.bfloat16)
        mx.eval(context)
        del parameters, output
        _release()
        return context

    def _encode_image(self, rgb: npt.NDArray[np.uint8]) -> mx.array:
        source = rgb.astype(np.float32) / np.float32(127.5) - np.float32(1.0)
        pixels = wan_clip_preprocess(mx.array(cast(Any, source[None])).astype(mx.bfloat16))
        reader = SelectiveSafeTensorReader(self.paths.clip)
        parameters = wan_clip_vision_parameters_from_tensors(
            _read_cast(reader, wan_clip_vision_tensor_names(), mx.bfloat16)
        )
        context = wan_clip_vision_encode(pixels, parameters, fast_attention=True)
        mx.eval(context)
        del parameters, pixels
        _release()
        return context

    def _encode_audio(self, waveform: npt.NDArray[np.float32]) -> tuple[mx.array, mx.array]:
        reader = SelectiveSafeTensorReader(self.paths.wav2vec2)
        parameters = wav2vec2_parameters_from_tensors(_read_cast(reader, wav2vec2_tensor_names()))
        hidden_states = wav2vec2_encode(
            mx.array(cast(Any, waveform[None])),
            parameters,
            output_length=81,
            fast_attention=True,
        )
        windowed = wav2vec2_window_hidden_states(hidden_states).astype(mx.bfloat16)
        first, later = split_wav2vec2_windows(windowed)
        mx.eval(first, later)
        del parameters, hidden_states, windowed
        _release()
        return first, later

    def _encode_inpaint(
        self,
        masked_video: npt.NDArray[np.float32],
        cancellation: CancellationToken | None = None,
    ) -> mx.array:
        reader = SelectiveSafeTensorReader(self.paths.vae)
        parameters = wan_vae_encoder_parameters_from_tensors(
            _read_cast(reader, vae_encoder_tensor_names(), mx.bfloat16)
        )
        latent = wan_vae_encode_mode(
            mx.array(cast(Any, masked_video)).astype(mx.bfloat16),
            parameters,
            fast_attention=True,
            evaluation_interval=1,
            cancel_check=None if cancellation is None else cancellation.raise_if_cancelled,
        )
        batch, _, latent_frames, latent_height, latent_width = latent.shape
        mask = mx.concatenate(
            [
                mx.ones((batch, 4, 1, latent_height, latent_width), dtype=mx.bfloat16),
                mx.zeros(
                    (batch, 4, latent_frames - 1, latent_height, latent_width),
                    dtype=mx.bfloat16,
                ),
            ],
            axis=2,
        )
        condition = mx.concatenate([mask, latent], axis=1)
        mx.eval(condition)
        del parameters, latent, mask
        _release()
        return condition

    def _denoise(
        self,
        text_context: mx.array,
        image_context: mx.array,
        first_audio: mx.array,
        later_audio: mx.array,
        inpaint_condition: mx.array,
        request: GenerationRequest,
        callback: ProgressCallback | None,
        cancellation: CancellationToken | None,
        checkpoint: DenoiseCheckpointStore | None = None,
    ) -> mx.array:
        configuration = self.configuration
        batch, _, latent_frames, latent_height, latent_width = inpaint_condition.shape
        grid_sizes = [
            (
                latent_frames,
                latent_height // configuration.patch_size[1],
                latent_width // configuration.patch_size[2],
            )
        ]
        sequence_tokens = math.prod(grid_sizes[0])
        reader = SelectiveSafeTensorReader(self.paths.transformer)
        parameters = wan_transformer_parameters_from_tensors(
            _read_cast(reader, full_transformer_tensor_names(configuration.num_layers)),
            configuration,
        )
        audio_context = project_audio_condition(
            first_audio,
            later_audio,
            parameters.audio_projection,
            context_tokens=32,
        )
        zero_audio = mx.zeros_like(audio_context)
        mx.eval(audio_context, zero_audio)
        mx.random.seed(request.seed)
        sample = mx.random.normal((batch, 16, latent_frames, latent_height, latent_width)).astype(
            mx.bfloat16
        )
        mx.eval(sample)
        scheduler = FlowUniPCScheduler()
        scheduler.set_timesteps(request.steps, shift=5.0)
        first_step = 0
        if checkpoint is not None:
            restored = checkpoint.restore(scheduler)
            if restored is not None:
                sample = restored.sample
                first_step = restored.next_step
                self._progress(callback, "denoise-resume", first_step, request.steps)
        rope_table = build_rope_table(1024, configuration.dim // configuration.num_heads)
        projected_context = wan_transformer_context(
            text_context,
            image_context,
            parameters.global_parameters,
            text_len=configuration.text_len,
        )
        mx.eval(projected_context)
        tea_cache = (
            TeaCacheState(
                request.steps,
                request.teacache_threshold,
                request.teacache_skip_start_steps,
            )
            if request.teacache_threshold > 0
            else None
        )

        def compile_block(
            block: WanBlockParameters,
        ) -> Callable[[mx.array, mx.array, mx.array, mx.array], mx.array]:
            def run_block(
                hidden: mx.array,
                modulation: mx.array,
                context: mx.array,
                audio: mx.array,
            ) -> mx.array:
                return wan_attention_block(
                    hidden,
                    modulation,
                    context,
                    audio,
                    block,
                    latent_frames=latent_frames,
                    num_heads=configuration.num_heads,
                    grid_sizes=grid_sizes,
                    rope_table=rope_table,
                    fast_attention=True,
                    eps=configuration.eps,
                )

            return mx.compile(run_block)

        compiled_blocks = (
            tuple(compile_block(block) for block in parameters.blocks)
            if tea_cache is None
            else None
        )

        def predict(
            prepared: WanTransformerInputs,
            audio: mx.array,
            branch: str,
            compute_blocks: bool,
        ) -> mx.array:
            if compute_blocks:
                hidden = prepared.hidden
                if compiled_blocks is None:
                    for block in parameters.blocks:
                        if cancellation is not None:
                            cancellation.raise_if_cancelled()
                        hidden = wan_attention_block(
                            hidden,
                            prepared.timestep_modulation,
                            prepared.context,
                            audio,
                            block,
                            latent_frames=latent_frames,
                            num_heads=configuration.num_heads,
                            grid_sizes=prepared.grid_sizes,
                            rope_table=rope_table,
                            fast_attention=True,
                            fast_norms=request.use_fused_norms,
                            eps=configuration.eps,
                        )
                        mx.eval(hidden)
                else:
                    for run_block in compiled_blocks:
                        if cancellation is not None:
                            cancellation.raise_if_cancelled()
                        hidden = run_block(
                            hidden,
                            prepared.timestep_modulation,
                            prepared.context,
                            audio,
                        )
                        mx.eval(hidden)
                if tea_cache is not None:
                    residual = hidden - prepared.hidden
                    mx.eval(residual)
                    tea_cache.store_residual(branch, residual)
            else:
                if tea_cache is None:
                    raise RuntimeError("TeaCache skip requested while the cache is disabled")
                hidden = prepared.hidden + tea_cache.residual(branch)
            output = wan_output_head(
                hidden,
                prepared.timestep_embedding,
                parameters.global_parameters.output_head,
                grid_sizes=prepared.grid_sizes,
                patch_size=configuration.patch_size,
                out_dim=configuration.out_dim,
                eps=configuration.eps,
            )
            mx.eval(output)
            return output

        for index in range(first_step, len(scheduler.timesteps)):
            timestep_value = scheduler.timesteps[index]
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            timestep = int(timestep_value)
            prepared = wan_transformer_inputs(
                sample,
                inpaint_condition,
                mx.array(timestep),
                text_context,
                image_context,
                parameters.global_parameters,
                text_len=configuration.text_len,
                seq_len=sequence_tokens,
                projected_context=projected_context,
            )
            mx.eval(
                prepared.hidden,
                prepared.timestep_embedding,
                prepared.timestep_modulation,
                prepared.context,
            )
            compute_blocks = tea_cache is None or tea_cache.should_compute(
                index, prepared.timestep_modulation
            )
            if not compute_blocks:
                self._progress(callback, "teacache-skip", index + 1, request.steps)
            conditional = predict(prepared, audio_context, "conditional", compute_blocks)
            unconditional = predict(prepared, zero_audio, "unconditional", compute_blocks)
            guided = unconditional + 3.0 * (conditional - unconditional)
            sample = scheduler.step(guided, timestep, sample)
            mx.eval(sample)
            if checkpoint is not None:
                checkpoint.save(sample, scheduler)
            self._progress(callback, "denoise", index + 1, request.steps)
        return sample

    def _decode(
        self, latent: mx.array, cancellation: CancellationToken | None = None
    ) -> npt.NDArray[np.float32]:
        reader = SelectiveSafeTensorReader(self.paths.vae)
        parameters = wan_vae_decoder_parameters_from_tensors(
            _read_cast(reader, vae_decoder_tensor_names(), mx.bfloat16)
        )
        decoded = wan_vae_decode(
            latent,
            parameters,
            fast_attention=True,
            evaluation_interval=1,
            cancel_check=None if cancellation is None else cancellation.raise_if_cancelled,
        )
        mx.eval(decoded)
        frames = np.asarray(
            mx.transpose(decoded[0], (1, 2, 3, 0)).astype(mx.float32), dtype=np.float32
        )
        del parameters, decoded
        _release()
        return frames

    def _decode_chunks(
        self,
        latent: mx.array,
        callback: ProgressCallback | None,
        cancellation: CancellationToken | None = None,
    ) -> Iterator[npt.NDArray[np.float32]]:
        reader = SelectiveSafeTensorReader(self.paths.vae)
        parameters = wan_vae_decoder_parameters_from_tensors(
            _read_cast(reader, vae_decoder_tensor_names(), mx.bfloat16)
        )

        def chunks() -> Iterator[npt.NDArray[np.float32]]:
            try:
                decoded_chunks = wan_vae_decode_chunks(
                    latent,
                    parameters,
                    fast_attention=True,
                    evaluation_interval=1,
                    cancel_check=(
                        None if cancellation is None else cancellation.raise_if_cancelled
                    ),
                )
                for index, decoded in enumerate(decoded_chunks):
                    mx.eval(decoded)
                    frames = np.asarray(
                        mx.transpose(decoded[0], (1, 2, 3, 0)).astype(mx.float32),
                        dtype=np.float32,
                    )
                    self._progress(callback, "decode", index + 1, latent.shape[2])
                    yield frames
            finally:
                _release()

        return chunks()

    @staticmethod
    def _validate_request(request: GenerationRequest) -> None:
        if (request.width, request.height) not in {(512, 512), (768, 768)} or (
            request.num_frames,
            request.fps,
            request.steps,
        ) != (81, 25, 8):
            raise ValueError(
                "production inference requires 512x512 or 768x768, 81 frames, 25 FPS, 8 steps"
            )

    def _generate_latent(
        self,
        request: GenerationRequest,
        progress: ProgressCallback | None,
        cancellation: CancellationToken | None,
        checkpoint: DenoiseCheckpointStore | None = None,
    ) -> mx.array:
        self._validate_request(request)
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        conditions = self.prepare_conditions(request, progress=progress, cancellation=cancellation)
        latent = self._denoise(
            conditions.text,
            conditions.image,
            conditions.first_audio,
            conditions.later_audio,
            conditions.inpaint,
            request,
            progress,
            cancellation,
            checkpoint,
        )
        _release()
        return latent

    def generate(
        self,
        request: GenerationRequest,
        *,
        progress: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
        checkpoint_path: str | Path | None = None,
    ) -> GenerationResult:
        """Generate the fixed 81-frame Flash result with staged model residency."""

        try:
            checkpoint = self._checkpoint_store(request, checkpoint_path)
            latent = self._generate_latent(request, progress, cancellation, checkpoint)
            frames = self._decode(latent, cancellation)
            self._progress(progress, "decode", 1, 1)
            if checkpoint is not None:
                checkpoint.clear()
            return GenerationResult(
                frames, Path(request.audio_path).expanduser().resolve(), request.fps
            )
        except GenerationCancelled:
            _release()
            raise

    def generate_to_file(
        self,
        request: GenerationRequest,
        output_path: str | Path,
        *,
        progress: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
        checkpoint_path: str | Path | None = None,
    ) -> Path:
        """Generate and stream decoded frame chunks directly into an atomic MP4."""

        try:
            checkpoint = self._checkpoint_store(request, checkpoint_path)
            latent = self._generate_latent(request, progress, cancellation, checkpoint)
            chunks = self._decode_chunks(latent, progress, cancellation)
            destination = write_mp4_chunks_with_audio(
                chunks,
                request.audio_path,
                output_path,
                fps=request.fps,
            )
            if checkpoint is not None:
                checkpoint.clear()
            return destination
        except GenerationCancelled:
            _release()
            raise

    def generate_long_to_file(
        self,
        request: GenerationRequest,
        output_path: str | Path,
        *,
        progress: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
    ) -> Path:
        """Generate an arbitrary-duration audio track as bounded overlapping 81-frame segments."""

        self._validate_request(request)
        with temporary_audio_segments(request.audio_path, fps=request.fps) as segmentation:
            segment_total = len(segmentation.paths)

            def chunks() -> Iterator[npt.NDArray[np.float32]]:
                static_conditions: EncodedConditions | None = None
                emitted = 0
                pending_tail: npt.NDArray[np.float32] | None = None
                try:
                    for segment_index, audio_path in enumerate(segmentation.paths):
                        if cancellation is not None:
                            cancellation.raise_if_cancelled()
                        self._progress(progress, "segment", segment_index, segment_total)
                        segment_request = replace(request, audio_path=str(audio_path))
                        if static_conditions is None:
                            conditions = self.prepare_conditions(
                                segment_request,
                                progress=progress,
                                cancellation=cancellation,
                            )
                            static_conditions = conditions
                        else:
                            waveform = load_reference_audio(
                                audio_path,
                                num_frames=request.num_frames,
                                fps=request.fps,
                            )
                            first_audio, later_audio = self._encode_audio(waveform)
                            conditions = EncodedConditions(
                                static_conditions.text,
                                static_conditions.image,
                                first_audio,
                                later_audio,
                                static_conditions.inpaint,
                            )
                        latent = self._denoise(
                            conditions.text,
                            conditions.image,
                            conditions.first_audio,
                            conditions.later_audio,
                            conditions.inpaint,
                            segment_request,
                            progress,
                            cancellation,
                        )
                        _release()
                        candidate: npt.NDArray[np.float32] | None = None
                        for decoded in self._decode_chunks(latent, progress, cancellation):
                            for frame_index in range(decoded.shape[0]):
                                frame = decoded[frame_index : frame_index + 1]
                                if pending_tail is not None:
                                    blended = (pending_tail + frame) * np.float32(0.5)
                                    pending_tail = None
                                    if emitted < segmentation.total_frames:
                                        emitted += 1
                                        yield blended
                                    continue
                                if candidate is not None and emitted < segmentation.total_frames:
                                    emitted += 1
                                    yield candidate
                                candidate = frame
                        pending_tail = candidate
                        self._progress(progress, "segment", segment_index + 1, segment_total)
                    if pending_tail is not None and emitted < segmentation.total_frames:
                        yield pending_tail[: segmentation.total_frames - emitted]
                finally:
                    self.clear_condition_cache()

            return write_mp4_chunks_with_audio(
                chunks(),
                request.audio_path,
                output_path,
                fps=request.fps,
            )

    def prepare_conditions(
        self,
        request: GenerationRequest,
        *,
        progress: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
    ) -> EncodedConditions:
        """Run each condition encoder while retaining only its evaluated output."""

        if cancellation is not None:
            cancellation.raise_if_cancelled()
        cache_key = (
            self._file_signature(request.image_path),
            self._file_signature(request.audio_path),
            request.prompt,
            request.width,
            request.height,
            request.num_frames,
            request.fps,
        )
        if self.cache_conditions:
            with self._condition_cache_lock:
                if cache_key == self._condition_cache_key:
                    cached = self._condition_cache_value
                else:
                    cached = None
            if cached is not None:
                self._progress(progress, "conditions-cache", 1, 1)
                return cached
        prepared = prepare_reference_image(
            request.image_path,
            num_frames=request.num_frames,
            size=(request.height, request.width),
        )
        waveform = load_reference_audio(
            request.audio_path, num_frames=request.num_frames, fps=request.fps
        )
        self._progress(progress, "text", 0, 1)
        text = self._encode_text(request.prompt)
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        self._progress(progress, "text", 1, 1)
        image = self._encode_image(prepared.rgb)
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        self._progress(progress, "image", 1, 1)
        first_audio, later_audio = self._encode_audio(waveform)
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        self._progress(progress, "audio", 1, 1)
        inpaint = self._encode_inpaint(prepared.masked_video, cancellation)
        self._progress(progress, "inpaint", 1, 1)
        conditions = EncodedConditions(text, image, first_audio, later_audio, inpaint)
        if self.cache_conditions:
            with self._condition_cache_lock:
                self._condition_cache_key = cache_key
                self._condition_cache_value = conditions
        return conditions
