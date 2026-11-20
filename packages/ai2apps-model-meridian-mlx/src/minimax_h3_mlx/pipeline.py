"""The MiniMax-H3 text/keyframe -> video+audio pipeline in MLX.

One packed sequence carries text, keyframe conditioning, audio and video rows at once, and a single
transformer forward per step predicts the velocity of every row — video and audio are denoised
*jointly*, on two schedules with different sigma shifts (12.0 and 3.0). The checkpoint is
CFG-distilled, so there is no unconditional pass and no guidance scale.

Conditioning rows are re-imposed by construction rather than by masking: only the generated rows are
ever written back, so keyframe anchors survive the whole loop untouched.

The AdaLN modulation cache is built once over the union of every timestep the run will present, and
the 13B of `adaln_proj` is then dropped — see :mod:`minimax_h3_mlx.adaln`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import mlx.core as mx
import numpy as np

from .adaln import ModulationCache, drop_adaln_weights, final_layer_modulation
from .config import PipelineConfig
from .packing import (
    AUDIO_CHANNELS,
    FPS,
    KEYFRAME_NOISE_AUG,
    PIXEL_MEAN,
    PIXEL_STD,
    align_num_frames,
    audio_latent_num_frames,
    build_packed_sequence,
    build_row_timesteps,
    patchify_video_latents,
    resolve_canvas_size,
    unpack_audio_tokens,
    unpatchify_video_tokens,
    video_latent_num_frames,
)
from .scheduler import MiniMaxH3Scheduler


@dataclass
class GenerationResult:
    video: np.ndarray  # (frames, height, width, 3) uint8
    audio: np.ndarray  # (2, samples) float32, in [-1, 1]
    sample_rate: int
    fps: int = FPS
    seconds_per_step: float = 0.0
    total_seconds: float = 0.0
    step_seconds: tuple[float, ...] = ()
    step_memory: tuple[dict[str, int], ...] = ()
    step_modes: tuple[str, ...] = ()
    continuation_latents: np.ndarray | None = None  # normalized VAE tail, chunk-aligned


def mlx_memory_snapshot() -> dict[str, int]:
    """Return the MLX allocator counters available in the installed runtime."""
    result: dict[str, int] = {}
    for label, name in (
        ("active_bytes", "get_active_memory"),
        ("cache_bytes", "get_cache_memory"),
        ("peak_bytes", "get_peak_memory"),
    ):
        getter = getattr(mx, name, None)
        if getter is not None:
            result[label] = int(getter())
    return result


class MiniMaxH3Pipeline:
    """Joint video + audio generation."""

    def __init__(
        self,
        dit,
        text_encoder,
        video_vae,
        audio_vae,
        config: PipelineConfig | None = None,
    ):
        self.dit = dit
        self.text_encoder = text_encoder
        self.video_vae = video_vae
        self.audio_vae = audio_vae
        self.config = config or PipelineConfig()
        self._cache: ModulationCache | None = None
        self._cache_timesteps: tuple[float, ...] | None = None

    @classmethod
    def from_pretrained(
        cls,
        checkpoint_dir: str | Path,
        transformer_dir: str | Path | None = None,
        dtype: mx.Dtype = mx.bfloat16,
        load_vision: bool = False,
        verbose: bool = True,
    ) -> "MiniMaxH3Pipeline":
        """Load a released ``FL2VA/`` (or ``Ref2VA/``) directory.

        Args:
            checkpoint_dir: the upstream release, which supplies the VAEs and the text encoder.
            transformer_dir: load the DiT from here instead of ``<checkpoint_dir>/transformer``.
                This is how a published quant is used: the quantized repository holds only the
                transformer, and everything else still comes from upstream. ``load_dit`` picks up
                the recorded recipe from its ``quant_config.json`` automatically.
        """
        from .load import load_audio_vae, load_dit, load_video_vae
        from .text_encoder import MiniMaxH3TextEncoder

        root = Path(checkpoint_dir)
        dit_path = Path(transformer_dir) if transformer_dir else root / "transformer"
        config = PipelineConfig.from_model_index(root / "model_index.json")

        def step(label, fn):
            started = time.perf_counter()
            out = fn()
            if verbose:
                print(f"  {label}: {time.perf_counter() - started:.1f}s")
            return out

        if verbose:
            print(f"loading MiniMax-H3 from {root}")
        text_encoder = step(
            "text encoder", lambda: MiniMaxH3TextEncoder(root / "text_encoder", dtype=dtype, load_vision=load_vision)
        )
        dit = step(f"transformer ({dit_path.name})", lambda: load_dit(dit_path))
        video_vae = step("video vae", lambda: load_video_vae(root / "video_vae"))
        audio_vae = step("audio vae", lambda: load_audio_vae(root / "audio_vae"))
        return cls(dit, text_encoder, video_vae, audio_vae, config)

    # -- schedule -----------------------------------------------------------------------------

    def _build_schedules(self, num_inference_steps: int):
        video = MiniMaxH3Scheduler(shift=self.config.sigma_shift_video)
        audio = MiniMaxH3Scheduler(shift=self.config.sigma_shift_audio)
        video.set_timesteps(num_inference_steps)
        audio.set_timesteps(num_inference_steps)
        return video, audio

    def _row_timestep_plan(self, layout, video_timesteps, audio_timesteps, *, fixed_audio=False, protected_video_rows=0):
        """Per-step ``(timestep_indices,)`` against one global timestep table.

        The transformer is handed the same table at every step, so a single
        :class:`ModulationCache` covers the whole run. Conditioning video rows sit at
        ``max(t, 0.999)`` and reference audio rows at ``1.0``, matching the reference.
        """
        per_step = []
        for t, at in zip(video_timesteps.tolist(), audio_timesteps.tolist()):
            distinct, inverse = build_row_timesteps(
                layout, float(t), 1.0 if fixed_audio else float(at), max(float(t), KEYFRAME_NOISE_AUG), 1.0
            )
            if protected_video_rows:
                rows = np.array(distinct)[np.array(inverse)]
                indices = np.array(layout.video_indices)[layout.num_condition_video_rows:]
                if protected_video_rows < 0 or protected_video_rows >= len(indices):
                    raise ValueError("Protected video prefix must leave generated rows")
                rows[indices[:protected_video_rows]] = max(float(t), KEYFRAME_NOISE_AUG)
                distinct, inverse = np.unique(rows, return_inverse=True)
            per_step.append((np.array(distinct), np.array(inverse)))

        table = sorted({float(v) for distinct, _ in per_step for v in distinct})
        lookup = {v: i for i, v in enumerate(table)}
        plan = []
        for distinct, inverse in per_step:
            remap = np.array([lookup[float(v)] for v in distinct], dtype=np.int32)
            plan.append(mx.array(remap[inverse].astype(np.int32)))
        return mx.array(np.array(table, dtype=np.float32)), plan

    def _ensure_cache(self, timesteps: mx.array, drop_adaln: bool, verbose: bool):
        key = tuple(round(float(v), 9) for v in timesteps.tolist())
        if self._cache is not None and self._cache_timesteps == key:
            return
        started = time.perf_counter()
        self._cache = ModulationCache.build(self.dit, timesteps, dtype=mx.bfloat16)
        self._cache_timesteps = key
        if verbose:
            print(f"  adaln cache: {len(key)} timesteps, {self._cache.nbytes() / 1e6:.0f} MB "
                  f"in {time.perf_counter() - started:.1f}s")
        if drop_adaln:
            freed = drop_adaln_weights(self.dit)
            mx.eval(self.dit.parameters())
            if verbose:
                print(f"  dropped adaln projections, freeing {freed / 1e9:.1f} GB")

    # -- keyframe conditioning ----------------------------------------------------------------

    def _encode_keyframes(self, images: list, height: int, width: int) -> mx.array:
        """Encode ``fl2va`` keyframes into packed conditioning rows.

        Keyframes are single frames, so they go through the video VAE's **spatial** encoder only —
        none of its 17-frame temporal chunking applies. Two details of the reference are load-bearing
        and easy to miss:

        * the posterior is **sampled**, not taken at its mode, under a generator seeded with 42
          independently of the request seed;
        * the sampled latent is **rounded through float16** before normalization, which is about 11
          bits of every conditioning latent — the released model's conditioning cannot be reproduced
          without it.

        MLX's RNG differs from torch's, so the seed-42 draw is not bit-identical to the reference's;
        the distribution and every other step are.
        """
        from .packing import KEYFRAME_ENCODE_SEED, prepare_keyframe_image

        cfg = self.video_vae.config
        latents_mean = mx.array(np.array(cfg.latents_mean, np.float32)).reshape(1, -1, 1, 1, 1)
        latents_std = mx.array(np.array(cfg.latents_std, np.float32)).reshape(1, -1, 1, 1, 1)
        pixel_mean = np.array(PIXEL_MEAN, np.float32).reshape(1, 3, 1, 1, 1)
        pixel_std = np.array(PIXEL_STD, np.float32).reshape(1, 3, 1, 1, 1)

        mx.random.seed(KEYFRAME_ENCODE_SEED)
        rows = []
        for index, image in enumerate(images):
            prepared = prepare_keyframe_image(image, height, width, stretch=index == 0)
            pixels = np.asarray(prepared, dtype=np.float32).transpose(2, 0, 1)[None, :, None]
            pixels = (pixels / 255.0 - pixel_mean) / pixel_std

            # (1, 3, 1, H, W) -> channels-last for the spatial encoder.
            moments = self.video_vae._encode_clip(mx.array(pixels).transpose(0, 2, 3, 4, 1))
            channels = cfg.latent_channels
            mean, logvar = moments[..., :channels], moments[..., channels:]
            logvar = mx.clip(logvar, -30.0, 20.0)
            std = mx.exp(0.5 * logvar)
            latent = mean + std * mx.random.normal(mean.shape)
            # -> (1, C, 1, H', W'), then the float16 round trip the reference relies on.
            latent = latent.transpose(0, 4, 1, 2, 3).astype(mx.float16).astype(mx.float32)
            normalized = (latent - latents_mean) / latents_std
            rows.append(patchify_video_latents(normalized, self.dit.config.patch_size))
        return mx.concatenate(rows)

    # -- generation ---------------------------------------------------------------------------

    def __call__(
        self,
        prompt: str,
        duration_seconds: float = 5.0,
        aspect: tuple[int, int] = (16, 9),
        num_inference_steps: int = 16,
        seed: int = 0,
        images: list | None = None,
        keyframe_anchors: tuple[str, ...] = (),
        height: int | None = None,
        width: int | None = None,
        drop_adaln: bool = True,
        verbose: bool = True,
    ) -> GenerationResult:
        """Generate a clip.

        Args:
            duration_seconds: 5 to 15; snapped up to the ``17n + 5`` frame grid the VAE encodes.
            num_inference_steps: the weights are CFG-distilled, so each step is one forward.
            keyframe_anchors: ``"first"`` / ``"last"`` per conditioning keyframe, in packed order.
            height, width: override the canvas ``aspect`` would resolve to. Both must be multiples
                of 32. H3 was released for a 768-pixel short edge only, so anything else is
                off-distribution — useful for exercising the pipeline, not for quality.
        """
        run_started = time.perf_counter()

        # 1. Text conditioning. Keyframe vision blocks come back tagged as *video* rows.
        prompt_embeds, text_token_tags = self.text_encoder.encode(prompt, images)

        # 2. Geometry.
        if height is None or width is None:
            height, width = resolve_canvas_size(*aspect)
        elif height % 32 or width % 32:
            raise ValueError(f"`height` and `width` must be multiples of 32, got {height}x{width}.")
        num_frames = align_num_frames(int(round(duration_seconds * FPS)))
        num_latent_frames = video_latent_num_frames(num_frames)
        ratio = self.video_vae.config.spatial_compression_ratio
        latent_height, latent_width = height // ratio, width // ratio
        num_audio_latents = audio_latent_num_frames(num_frames)
        patch_size = self.dit.config.patch_size

        layout = build_packed_sequence(
            text_token_tags,
            num_latent_frames,
            latent_height,
            latent_width,
            num_audio_latents,
            patch_size,
            keyframe_anchors,
        )
        if verbose:
            print(f"canvas {width}x{height}, {num_frames} frames ({num_latent_frames} latent), "
                  f"{num_audio_latents} audio latents")
            print(f"packed sequence: {layout.sequence_length:,} rows "
                  f"({len(text_token_tags):,} text, {layout.num_condition_video_rows:,} condition)")

        # 3. Keyframe conditioning rows, encoded before any request noise is drawn.
        condition_rows = None
        if images:
            condition_rows = self._encode_keyframes(images, height, width)

        # 4. Initial noise. Draw order matches the reference — the conditioning noise comes off the
        #    request generator first, then video, then audio — so a seed reproduces the same run.
        mx.random.seed(seed)
        if condition_rows is not None:
            condition_noise = mx.random.normal(condition_rows.shape).astype(mx.float32)
            # Anchors are not fully clean: they are noised to t = 0.999 and held there every step.
            condition_rows = MiniMaxH3Scheduler(shift=self.config.sigma_shift_video).scale_noise(
                condition_rows, KEYFRAME_NOISE_AUG, condition_noise
            )

        latents = mx.random.normal(
            (1, self.video_vae.config.latent_channels, num_latent_frames, latent_height, latent_width)
        ).astype(mx.float32)
        video_rows = patchify_video_latents(latents, patch_size)
        audio_rows = mx.random.normal(
            (num_audio_latents * AUDIO_CHANNELS, self.audio_vae.config.latent_channels)
        ).astype(mx.float32)
        if condition_rows is not None:
            video_rows = mx.concatenate([condition_rows, video_rows])

        # 5. Two schedules over one shared forward.
        video_sched, audio_sched = self._build_schedules(num_inference_steps)
        timestep_table, plan = self._row_timestep_plan(layout, video_sched.timesteps, audio_sched.timesteps)
        self._ensure_cache(timestep_table, drop_adaln, verbose)

        n_cond_v = layout.num_condition_video_rows
        n_cond_a = layout.num_condition_audio_rows
        embeds = prompt_embeds.astype(mx.bfloat16)
        refined_text = self.dit.refine_text(embeds)
        rotary = self.dit.rope(layout.position_ids)
        final_modulation = final_layer_modulation(self.dit, timestep_table, dtype=mx.bfloat16)
        mx.eval(refined_text, *rotary, *final_modulation)

        # 6. Denoise. One forward per step; only generated rows are written back, so the
        #    conditioning anchors survive without any masking.
        step_times = []
        step_memory = []
        for i, t in enumerate(video_sched.timesteps.tolist()):
            started = time.perf_counter()
            video_pred, audio_pred = self.dit(
                video_rows[None].astype(mx.bfloat16),
                audio_rows[None].astype(mx.bfloat16),
                embeds,
                timestep_table,
                plan[i],
                layout.token_tags,
                layout.position_ids,
                layout.video_indices,
                layout.audio_indices,
                layout.text_indices,
                modulation_cache=self._cache,
                refined_text=refined_text,
                rotary=rotary,
                final_modulation=final_modulation,
            )
            # Rebind rather than assign into a slice: the stepped result is a lazy graph reading the
            # very rows it would overwrite, and with conditioning rows present the two halves must
            # stay distinct. Concatenating is unambiguous and costs nothing next to the forward.
            stepped_video = video_sched.step(
                video_pred[0, n_cond_v:].astype(mx.float32), float(t), video_rows[n_cond_v:]
            )
            stepped_audio = audio_sched.step(
                audio_pred[0, n_cond_a:].astype(mx.float32),
                float(audio_sched.timesteps[i].item()),
                audio_rows[n_cond_a:],
            )
            video_rows = (
                mx.concatenate([video_rows[:n_cond_v], stepped_video]) if n_cond_v else stepped_video
            )
            audio_rows = (
                mx.concatenate([audio_rows[:n_cond_a], stepped_audio]) if n_cond_a else stepped_audio
            )
            mx.eval(video_rows, audio_rows)
            before_step = mlx_memory_snapshot()
            after_step = mlx_memory_snapshot()
            step_times.append(time.perf_counter() - started)
            step_memory.append({**before_step, **{
                f"after_step_{key}": value for key, value in after_step.items()
            }})
            if verbose:
                done = i + 1
                mean = sum(step_times) / len(step_times)
                eta = mean * (len(video_sched.timesteps) - done)
                print(f"  step {done}/{len(video_sched.timesteps)}  "
                      f"{step_times[-1]:.1f}s  eta {eta / 60:.1f} min", flush=True)

        # 7. Decode both modalities.
        video = self._decode_video(video_rows[n_cond_v:], num_latent_frames, latent_height, latent_width)
        audio = self._decode_audio(audio_rows[n_cond_a:], num_audio_latents)
        total = time.perf_counter() - run_started
        return GenerationResult(
            video=video,
            audio=audio,
            sample_rate=self.audio_vae.config.sampling_rate,
            seconds_per_step=sum(step_times) / max(len(step_times), 1),
            total_seconds=total,
            step_seconds=tuple(step_times),
            step_memory=tuple(step_memory),
        )

    # -- decoding -----------------------------------------------------------------------------

    def _decode_video(self, rows, num_latent_frames, latent_height, latent_width) -> np.ndarray:
        cfg = self.video_vae.config
        latents = unpatchify_video_tokens(
            rows, num_latent_frames, latent_height, latent_width, cfg.latent_channels, self.dit.config.patch_size
        )
        mean = mx.array(np.array(cfg.latents_mean, np.float32)).reshape(1, -1, 1, 1, 1)
        std = mx.array(np.array(cfg.latents_std, np.float32)).reshape(1, -1, 1, 1, 1)
        latents = latents * std + mean

        frames = np.array(self.video_vae.decode(latents.astype(mx.float32)))
        # The VAE decodes into ImageNet-normalized RGB over a [0, 1] base range.
        pixel_mean = np.array(PIXEL_MEAN, np.float32).reshape(1, 3, 1, 1, 1)
        pixel_std = np.array(PIXEL_STD, np.float32).reshape(1, 3, 1, 1, 1)
        frames = frames * pixel_std + pixel_mean
        frames = np.clip(frames, 0.0, 1.0)[0].transpose(1, 2, 3, 0)  # -> (F, H, W, 3)
        return (frames * 255.0 + 0.5).astype(np.uint8)

    def _decode_audio(self, rows, num_audio_latents) -> np.ndarray:
        cfg = self.audio_vae.config
        latents = unpack_audio_tokens(rows, num_audio_latents)
        mean = mx.array(np.array(cfg.latents_mean, np.float32)).reshape(1, -1, 1)
        std = mx.array(np.array(cfg.latents_std, np.float32)).reshape(1, -1, 1)
        latents = latents * std + mean
        waveform = np.array(self.audio_vae.decode(latents.astype(mx.float32)))
        return waveform[:, 0, :].astype(np.float32)  # (2, samples), one row per stereo channel
