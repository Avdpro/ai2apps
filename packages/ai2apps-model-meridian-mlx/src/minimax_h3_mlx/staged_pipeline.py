"""Memory-bounded MiniMax-H3 inference with one heavyweight component resident at a time.

The released pipeline is convenient but keeps the conditioner, DiT and both VAEs alive together.
This implementation treats the checkpoint as a set of stages.  Every boundary materializes the
small tensors that cross it, drops all references to the completed module, collects Python objects,
and clears MLX's reusable allocation cache before loading the next module.
"""

from __future__ import annotations

import gc
import json
import time
from pathlib import Path
from types import SimpleNamespace

import mlx.core as mx
import numpy as np

from .adaln import ModulationCache, drop_adaln_weights, final_layer_modulation
from .config import DiTConfig, PipelineConfig
from .packing import (
    AUDIO_CHANNELS, FPS, KEYFRAME_NOISE_AUG, PIXEL_MEAN, PIXEL_STD,
    align_num_frames, audio_latent_num_frames, build_packed_sequence,
    patchify_video_latents, resolve_canvas_size, unpack_audio_tokens,
    unpatchify_video_tokens, video_latent_num_frames, RefAudio, RefImage, RefVideo,
)
from .pipeline import (
    GenerationResult,
    MiniMaxH3Pipeline,
    mlx_memory_snapshot,
)
from .scheduler import MiniMaxH3Scheduler
from .speed import attention_broadcast_refresh, step_cache_warmup


class StagedMiniMaxH3Pipeline:
    """Load, run and release each H3 component instead of retaining a monolithic pipeline."""

    def __init__(self, checkpoint_dir: str | Path, *, dtype=mx.bfloat16,
                 phase_observer=None, loaders: dict | None = None,
                 transformer_adapters: tuple[str | Path, ...] = (),
                 variant_config: dict | None = None,
                 openvdn_config: dict | None = None,
                 openvdn_branch_path: str | Path | None = None):
        root = Path(checkpoint_dir)
        self.root = root / "FL2VA" if (root / "FL2VA").is_dir() else root
        self.dtype = dtype
        self.phase_observer = phase_observer
        self._custom_loaders = loaders or {}
        with open(self.root / "config.json" if (self.root / "config.json").exists()
                  else self.root / "transformer" / "config.json") as fh:
            raw = json.load(fh)
        self.flat = "transformer" in raw and (self.root / "transformer.safetensors").exists()
        self.transformer_adapters = tuple(Path(item) for item in transformer_adapters)
        self.variant = variant_config if variant_config is not None else raw.get("variant") or {}
        self.vsa = raw.get("vsa") or {}
        self.openvdn = openvdn_config if openvdn_config is not None else raw.get("openvdn") or {}
        self.openvdn_branch_path = (
            None if openvdn_branch_path is None else Path(openvdn_branch_path)
        )
        self.dit_config = DiTConfig.from_dict(raw.get("transformer", raw))
        if self.flat:
            shifts = raw.get("sigma_shift_scales", {})
            self.config = PipelineConfig(
                partition=raw.get("partition", "fl2va"), tasks=list(raw.get("tasks", ["t2va", "fl2va"])),
                sigma_shift_video=float(shifts.get("video", 12.0)),
                sigma_shift_audio=float(shifts.get("audio", 3.0)),
            )
        else:
            self.config = PipelineConfig.from_model_index(self.root / "model_index.json")

    @classmethod
    def from_pretrained(cls, checkpoint_dir, **kwargs):
        # Kept API-compatible with the old factory; vision is now selected per text stage.
        kwargs.pop("load_vision", None)
        kwargs.pop("verbose", None)
        return cls(checkpoint_dir, **kwargs)

    def _notify(self, event: str, phase: str) -> None:
        if self.phase_observer is not None:
            self.phase_observer(event, phase)

    def _load(self, phase: str, *, load_vision: bool = False):
        self._notify("load", phase)
        if phase in self._custom_loaders:
            return self._custom_loaders[phase](load_vision=load_vision)
        from .load import load_audio_vae, load_dit, load_video_vae
        if phase == "text_encoder":
            from .text_encoder import MiniMaxH3TextEncoder
            path = self.root if self.flat else self.root / "text_encoder"
            return MiniMaxH3TextEncoder(path, dtype=self.dtype, load_vision=load_vision)
        if phase == "dit":
            return load_dit(
                self.root if self.flat else self.root / "transformer",
                adapters=self.transformer_adapters,
            )
        if phase == "video_vae":
            return load_video_vae(self.root if self.flat else self.root / "video_vae")
        if phase == "audio_vae":
            return load_audio_vae(self.root if self.flat else self.root / "audio_vae")
        raise ValueError(phase)

    def _release(self, phase: str, *outputs) -> None:
        # An evaluated output owns its storage independently of the lazy graph/model that produced
        # it. clear_cache only releases reusable allocations; it does not invalidate live arrays.
        if outputs:
            mx.eval(*[value for value in outputs if value is not None])
        gc.collect()
        mx.clear_cache()
        self._notify("release", phase)

    def _configs(self):
        from .load import audio_vae_config, video_vae_config
        base = self.root
        return video_vae_config(base if self.flat else base / "video_vae"), \
            audio_vae_config(base if self.flat else base / "audio_vae")

    def __call__(self, prompt: str, duration_seconds: float = 5.0,
                 aspect: tuple[int, int] = (16, 9), num_inference_steps: int = 16,
                 seed: int = 0, images: list | None = None,
                 keyframe_anchors: tuple[str, ...] = (), height: int | None = None,
                 width: int | None = None, drop_adaln: bool = True,
                 verbose: bool = True, optimize_denoise: bool = True,
                 clear_step_cache: bool = False, fast: bool = False, fast_max: bool = False,
                 fused_kernels: bool = True,
                 attention_broadcast_period: int | None = None,
                 velocity_cache_threshold: float | None = None,
                 video_vae_tile_size: int | None = None,
                 references: tuple | list = (),
                 reference_image_size: str = "match",
                 driving_audio: np.ndarray | None = None,
                 video_context: np.ndarray | None = None,
                 video_context_latents: np.ndarray | None = None,
                 context_image_anchor: bool = False,
                 return_context_frames: int | None = None,
                 cancelled=None) -> GenerationResult:
        started = time.perf_counter()
        if cancelled and cancelled():
            raise InterruptedError("Avatar generation cancelled")
        if driving_audio is not None:
            driving_audio = np.asarray(driving_audio, dtype=np.float32)
            if driving_audio.ndim != 2 or driving_audio.shape[0] != 2 or not np.isfinite(driving_audio).all():
                raise ValueError("driving_audio must be finite 32 kHz stereo PCM shaped (2, samples)")
            if fast or fast_max or (attention_broadcast_period is not None and attention_broadcast_period != 1) or velocity_cache_threshold:
                raise ValueError("Fixed-audio validation requires uncached denoising")
        if context_image_anchor and (video_context_latents is None or driving_audio is None
                or not images or len(images) != 1 or keyframe_anchors not in {('first',), ('last',)} or references):
            raise ValueError("Context image anchoring requires one original image anchor and latent continuation")
        if video_context_latents is not None:
            video_context_latents = np.asarray(video_context_latents, dtype=np.float32)
            portrait_reference = (references and len(references) == 1
                                  and references[0].kind == "image"
                                  and self.config.partition.lower() in {"ref2va", "ref"})
            if (driving_audio is None or video_context is not None
                    or (images and not context_image_anchor)
                    or (references and not portrait_reference)):
                raise ValueError("Latent continuation requires fixed audio and compatible portrait conditions")
            if video_context_latents.ndim != 5 or not np.isfinite(video_context_latents).all():
                raise ValueError("Context latents must be finite BCFHW")
        if return_context_frames is not None and (
            return_context_frames < 39 or (return_context_frames - 39) % 51
        ):
            raise ValueError("Returned context must be 39 + 51*k frames")
        if video_context is not None:
            video_context = np.asarray(video_context)
            if driving_audio is None:
                raise ValueError("Video continuation requires fixed driving_audio")
            if video_context.dtype != np.uint8 or video_context.ndim != 4 or video_context.shape[-1] != 3:
                raise ValueError("video_context must be uint8 RGB frames")
            if len(video_context) < 39 or (len(video_context) - 39) % 51:
                raise ValueError("video_context frame count must be 39 + 51*k")
            if images or references:
                raise ValueError("Context and independent image/reference conditions are not yet validated together")
        references = tuple(references or ())
        if references and images:
            raise ValueError("Ref2VA references cannot be combined with FL2VA keyframes")
        if references and self.config.partition.lower() not in {"ref2va", "ref"} \
                and "ref2va" not in {str(task).lower() for task in self.config.tasks}:
            raise ValueError("The selected checkpoint is not a Ref2VA checkpoint")
        if not references and self.config.partition.lower() in {"ref2va", "ref"}:
            raise ValueError("A Ref2VA checkpoint requires at least one reference")
        image_count = sum(getattr(item, "kind", None) == "image" for item in references)
        video_count = sum(getattr(item, "kind", None) == "video" for item in references)
        # Embedded video soundtracks are part of their video file; the independent
        # three-audio limit applies only to standalone audio references.
        audio_count = sum(getattr(item, "kind", None) == "audio" for item in references)
        if image_count > 9 or video_count > 3 or audio_count > 3 or len(references) > 12:
            raise ValueError("Ref2VA supports 9 images, 3 videos, 3 audio clips and 12 files total")
        if references and not image_count and not video_count:
            raise ValueError("Ref2VA audio requires an image or video reference")
        fast = fast or fast_max
        attention_broadcast_period = (
            3 if fast_max else 2
        ) if attention_broadcast_period is None else max(1, int(attention_broadcast_period))
        video_cfg, audio_cfg = self._configs()

        if height is None or width is None:
            height, width = resolve_canvas_size(*aspect)
        elif height % 32 or width % 32:
            raise ValueError(f"`height` and `width` must be multiples of 32, got {height}x{width}.")
        num_frames = align_num_frames(int(round(duration_seconds * FPS)))
        num_latent_frames = video_latent_num_frames(num_frames)
        latent_height = height // video_cfg.spatial_compression_ratio
        latent_width = width // video_cfg.spatial_compression_ratio
        num_audio_latents = audio_latent_num_frames(num_frames)
        if driving_audio is not None and driving_audio.shape[1] != num_audio_latents * 800:
            raise ValueError(f"driving_audio requires exactly {num_audio_latents * 800} samples on the target audio grid")
        patch_size = self.dit_config.patch_size
        if video_context is not None:
            if video_context.shape[1:3] != (height, width) or len(video_context) >= num_frames:
                raise ValueError("Context must match output dimensions and be shorter than target")

        if video_context_latents is not None:
            shape = video_context_latents.shape
            if (shape[:2] != (1, video_cfg.latent_channels)
                    or shape[3:] != (latent_height, latent_width)
                    or shape[2] < 12 or (shape[2] - 12) % 15
                    or shape[2] >= num_latent_frames):
                raise ValueError("Context latent shape/grid does not match the target")
        if return_context_frames is not None and return_context_frames > num_frames:
            raise ValueError("Returned context is longer than generated video")

        # Stage 1: conditioner. Only the compact embeddings and integer tags cross the boundary.
        encoder = self._load("text_encoder", load_vision=bool(images or references))
        if references:
            from .text_encoder import ReferencePresentation

            presentations = []
            for item in references:
                if item.kind == "video":
                    qwen_frames = tuple(item.frames[:: max(1, FPS // 2)])
                else:
                    qwen_frames = tuple(item.frames)
                presentations.append(ReferencePresentation(
                    item.kind, qwen_frames, has_audio=item.audio is not None
                ))
            prompt_embeds, text_token_tags = encoder.encode_references(
                prompt, tuple(presentations)
            )
        else:
            prompt_embeds, text_token_tags = encoder.encode(prompt, images)
        mx.eval(prompt_embeds)
        del encoder
        self._release("text_encoder", prompt_embeds)

        # Stage 2: encode FL2VA keyframes or ordered Ref2VA visual conditions.
        protected_video_rows = (None if video_context_latents is None else
                                patchify_video_latents(mx.array(video_context_latents), patch_size))
        condition_rows = None
        reference_geometry = []
        visual_conditions = [item for item in references if item.frames]
        visual_latents = []
        if images or visual_conditions or video_context is not None:
            video_vae = self._load("video_vae")
            if images:
                helper = MiniMaxH3Pipeline(SimpleNamespace(config=self.dit_config), None, video_vae, None, self.config)
                condition_rows = helper._encode_keyframes(images, height, width)
                del helper
            elif visual_conditions:
                cfg = video_vae.config
                latent_mean = mx.array(np.array(cfg.latents_mean, np.float32)).reshape(1, -1, 1, 1, 1)
                latent_std = mx.array(np.array(cfg.latents_std, np.float32)).reshape(1, -1, 1, 1, 1)
                pixel_mean = np.array(PIXEL_MEAN, np.float32).reshape(1, 3, 1, 1, 1)
                pixel_std = np.array(PIXEL_STD, np.float32).reshape(1, 3, 1, 1, 1)
                for item in visual_conditions:
                    pixels = np.stack([np.asarray(frame, np.float32) for frame in item.frames])
                    pixels = pixels.transpose(3, 0, 1, 2)[None]
                    normalized_pixels = (pixels / 255.0 - pixel_mean) / pixel_std
                    if len(item.frames) == 1:
                        moments = video_vae._encode_clip(
                            mx.array(normalized_pixels).transpose(0, 2, 3, 4, 1)
                        ).transpose(0, 4, 1, 2, 3)
                    else:
                        moments = video_vae.encode(mx.array(normalized_pixels))
                    mean = moments[:, :cfg.latent_channels].astype(mx.float32)
                    latent = (mean - latent_mean) / latent_std
                    mx.eval(latent)
                    visual_latents.append(latent)
                condition_rows = mx.concatenate([
                    patchify_video_latents(latent, patch_size) for latent in visual_latents
                ])
            if video_context is not None:
                cfg = video_vae.config
                pixels = video_context.astype(np.float32).transpose(3, 0, 1, 2)[None] / 255.0
                pixel_mean = np.array(PIXEL_MEAN, np.float32).reshape(1, 3, 1, 1, 1)
                pixel_std = np.array(PIXEL_STD, np.float32).reshape(1, 3, 1, 1, 1)
                moments = video_vae.encode(mx.array((pixels - pixel_mean) / pixel_std))
                mean = moments[:, :cfg.latent_channels].astype(mx.float32)
                latent_mean = mx.array(np.array(cfg.latents_mean, np.float32)).reshape(1, -1, 1, 1, 1)
                latent_std = mx.array(np.array(cfg.latents_std, np.float32)).reshape(1, -1, 1, 1, 1)
                latent = (mean - latent_mean) / latent_std
                protected_video_rows = patchify_video_latents(latent, patch_size)
                mx.eval(protected_video_rows)
            if condition_rows is not None:
                mx.eval(condition_rows)
            del video_vae
            self._release("video_vae", condition_rows, protected_video_rows)

        # Ref2VA audio conditions use the posterior mean and are clean/pinned for every step.
        condition_audio_rows = None
        audio_latents_by_reference = []
        audio_conditions = [item for item in references if item.audio is not None]
        target_audio_rows = None
        if audio_conditions or driving_audio is not None:
            audio_vae = self._load("audio_vae")
            cfg = audio_vae.config
            latent_mean = mx.array(np.array(cfg.latents_mean, np.float32)).reshape(1, -1, 1)
            latent_std = mx.array(np.array(cfg.latents_std, np.float32)).reshape(1, -1, 1)
            for item in audio_conditions:
                samples = mx.array(np.asarray(item.audio, np.float32))[:, None, :]
                mean, _ = audio_vae.encode(samples)
                latent = ((mean.astype(mx.float32) - latent_mean) / latent_std)
                mx.eval(latent)
                audio_latents_by_reference.append(latent)
            if audio_latents_by_reference:
                condition_audio_rows = mx.concatenate([
                    latent.transpose(0, 2, 1).reshape(-1, latent.shape[1])
                    for latent in audio_latents_by_reference
                ])
                mx.eval(condition_audio_rows)
            if driving_audio is not None:
                mean, _ = audio_vae.encode(mx.array(driving_audio)[:, None, :])
                latent = (mean.astype(mx.float32) - latent_mean) / latent_std
                if latent.shape != (2, cfg.latent_channels, num_audio_latents):
                    raise ValueError(f"Unexpected target audio latent shape: {latent.shape}")
                target_audio_rows = latent.transpose(0, 2, 1).reshape(-1, latent.shape[1])
                mx.eval(target_audio_rows)
            del audio_vae
            self._release("audio_vae", condition_audio_rows, target_audio_rows)

        if references:
            visual_iter = iter(visual_latents)
            audio_iter = iter(audio_latents_by_reference)
            for item in references:
                visual = next(visual_iter) if item.frames else None
                audio = next(audio_iter) if item.audio is not None else None
                if item.kind == "image":
                    reference_geometry.append(RefImage(visual.shape[-2], visual.shape[-1]))
                elif item.kind == "video":
                    reference_geometry.append(RefVideo(
                        visual.shape[-3], visual.shape[-2], visual.shape[-1],
                        0 if audio is None else audio.shape[-1],
                    ))
                else:
                    reference_geometry.append(RefAudio(audio.shape[-1]))

        layout = build_packed_sequence(
            text_token_tags, num_latent_frames, latent_height, latent_width,
            num_audio_latents, patch_size, keyframe_anchors, tuple(reference_geometry),
        )

        mx.random.seed(seed)
        if condition_rows is not None:
            condition_noise = mx.random.normal(condition_rows.shape).astype(mx.float32)
            condition_rows = MiniMaxH3Scheduler(shift=self.config.sigma_shift_video).scale_noise(
                condition_rows, KEYFRAME_NOISE_AUG, condition_noise)
        latents = mx.random.normal((1, video_cfg.latent_channels, num_latent_frames,
                                    latent_height, latent_width)).astype(mx.float32)
        video_rows = patchify_video_latents(latents, patch_size)
        protected_count = 0 if protected_video_rows is None else int(protected_video_rows.shape[0])
        if protected_count:
            # Match upstream inpainting strength and its per-token timestep.
            # Reuse target noise so protected rows do not shift RNG for audio.
            protected_video_rows = (KEYFRAME_NOISE_AUG * protected_video_rows
                                    + (1.0 - KEYFRAME_NOISE_AUG) * video_rows[:protected_count])
            video_rows = mx.concatenate([protected_video_rows, video_rows[protected_count:]])
        audio_rows = mx.random.normal(
            (num_audio_latents * AUDIO_CHANNELS, audio_cfg.latent_channels)).astype(mx.float32)
        if target_audio_rows is not None:
            audio_rows = target_audio_rows
        if condition_rows is not None:
            video_rows = mx.concatenate([condition_rows, video_rows])
        if condition_audio_rows is not None:
            audio_rows = mx.concatenate([condition_audio_rows, audio_rows])

        # Stage 3: DiT and its temporary AdaLN table. Both are gone before either decoder loads.
        dit = self._load("dit")
        if self.openvdn.get("enabled"):
            from .openvdn import VDNGeometry

            branch_path = self.openvdn_branch_path or (
                self.root / self.openvdn.get(
                    "branch_weights", "openvdn_linear_branch.safetensors"
                )
            )
            all_branch_weights = mx.load(str(branch_path))
            target_video_start = int(layout.video_indices[layout.num_condition_video_rows].item())
            geometry = VDNGeometry(
                video_start=target_video_start,
                video_end=layout.sequence_length,
                num_frames=num_latent_frames,
                frame_height=latent_height // patch_size[1],
                frame_width=latent_width // patch_size[2],
                text_start=0,
                text_length=int(layout.text_indices.shape[0]),
                radius=int(self.openvdn.get("radius", 1)),
                chunk=int(self.openvdn.get("chunk", 5)),
                anchors=str(self.openvdn.get("anchors", "both")),
                solver_iterations=int(self.openvdn.get("solver_iterations", 8)),
            )
            if geometry.video_end - geometry.video_start != (
                geometry.num_frames * geometry.tokens_per_frame
            ):
                raise ValueError("OpenVDN requires the generated-video rows to be one final span")
            for index, block in enumerate(dit.blocks):
                source_prefix = f"transformer_blocks.{index}.attn."
                block.attn.vdn_geometry = geometry
                block.attn.vdn_weights = {
                    key[len(source_prefix):]: value
                    for key, value in all_branch_weights.items()
                    if key.startswith(source_prefix)
                }
                if len(block.attn.vdn_weights) != 16:
                    raise KeyError(
                        f"OpenVDN block {index} has {len(block.attn.vdn_weights)} branch tensors"
                    )
        if self.vsa.get("enabled"):
            from .vsa import build_vsa_geometry

            _, patch_h, patch_w = patch_size
            generated_video_rows = (
                num_latent_frames * (latent_height // patch_h) * (latent_width // patch_w)
            )
            prefix_segments = (
                int(layout.text_indices.shape[0]), layout.num_condition_video_rows,
                int(layout.audio_indices.shape[0]),
            )
            geometry = build_vsa_geometry(
                prefix_segments,
                (num_latent_frames, latent_height // patch_h, latent_width // patch_w),
                int(self.vsa.get("tile_size", 64)),
            )
            if geometry.total_length != layout.sequence_length:
                raise ValueError(
                    f"FastH3 VSA layout mismatch: {geometry.total_length} vs "
                    f"{layout.sequence_length} rows ({generated_video_rows} generated video rows)"
                )
            for block in dit.blocks:
                block.attn.vsa_geometry = geometry
                block.attn.vsa_sparsity = float(self.vsa.get("sparsity", 0.9))
        for block in dit.blocks:
            block.use_fused_ops = fused_kernels
        helper = MiniMaxH3Pipeline(dit, None, None, None, self.config)
        video_sched, audio_sched = helper._build_schedules(num_inference_steps)
        timestep_table, plan = helper._row_timestep_plan(
            layout, video_sched.timesteps, audio_sched.timesteps, fixed_audio=driving_audio is not None, protected_video_rows=protected_count)
        cache = ModulationCache.build(dit, timestep_table, dtype=mx.bfloat16)
        if drop_adaln:
            drop_adaln_weights(dit)
            mx.eval(dit.parameters())
        n_cond_v, n_cond_a = layout.num_condition_video_rows, layout.num_condition_audio_rows
        embeds = prompt_embeds.astype(mx.bfloat16)
        # Text conditioning, rotary coordinates and final AdaLN modulation are invariant across
        # the schedule. Materialize them before the loop so every step contains only the changing
        # latent projections and transformer stack.
        refined_text = rotary = final_modulation = None
        if optimize_denoise:
            refined_text = dit.refine_text(embeds)
            rotary = dit.rope(layout.position_ids)
            final_modulation = final_layer_modulation(dit, timestep_table, dtype=mx.bfloat16)
            mx.eval(refined_text, *rotary, *final_modulation)
        step_times = []
        step_memory = []
        step_modes = []
        attention_cache = [None] * len(dit.blocks) if fast and attention_broadcast_period > 1 else None
        velocity_threshold = ((0.08 if fast_max else 0.05) if fast else 0.0) \
            if velocity_cache_threshold is None \
            else max(0.0, float(velocity_cache_threshold))
        cached_video_pred = cached_audio_pred = None
        velocity_accumulator = 0.0
        velocity_consecutive = 0
        for index, timestep in enumerate(video_sched.timesteps.tolist()):
            if cancelled and cancelled():
                raise InterruptedError("Avatar generation cancelled")
            step_started = time.perf_counter()
            if fast_max and attention_cache is not None:
                shallow = max(1, len(dit.blocks) // 3)
                attention_refresh = [
                    attention_broadcast_refresh(
                        index, len(video_sched.timesteps),
                        2 if block_index < shallow else attention_broadcast_period,
                    )
                    for block_index in range(len(dit.blocks))
                ]
            else:
                attention_refresh = attention_broadcast_refresh(
                    index, len(video_sched.timesteps), attention_broadcast_period)
            velocity_reuse = False
            if (velocity_threshold > 0 and cached_video_pred is not None
                    and index >= step_cache_warmup(len(video_sched.timesteps))
                    and index + 1 < len(video_sched.timesteps)
                    and velocity_consecutive < (3 if fast_max else 2)):
                sigma = float(video_sched.sigmas[index].item())
                sigma_next = float(video_sched.sigmas[index + 1].item())
                velocity_mag = float(mx.mean(mx.abs(cached_video_pred)).item())
                latent_mag = float(mx.mean(mx.abs(video_rows[n_cond_v:])).item())
                relative_move = abs(sigma_next - sigma) * velocity_mag / max(latent_mag, 1e-8)
                if velocity_accumulator + relative_move < velocity_threshold:
                    velocity_accumulator += relative_move
                    velocity_reuse = True

            if velocity_reuse:
                video_velocity, audio_velocity = cached_video_pred, cached_audio_pred
                velocity_consecutive += 1
                mode = "velocity-reuse"
            else:
                video_pred, audio_pred = dit(
                    video_rows[None].astype(mx.bfloat16), audio_rows[None].astype(mx.bfloat16), embeds,
                    timestep_table, plan[index], layout.token_tags, layout.position_ids,
                    layout.video_indices, layout.audio_indices, layout.text_indices,
                    modulation_cache=cache,
                    refined_text=refined_text,
                    rotary=rotary,
                    final_modulation=final_modulation,
                    attention_cache=attention_cache,
                    attention_refresh=attention_refresh,
                )
                video_velocity = video_pred[0, n_cond_v:].astype(mx.float32)
                audio_velocity = audio_pred[0, n_cond_a:].astype(mx.float32)
                cached_video_pred, cached_audio_pred = video_velocity, audio_velocity
                velocity_accumulator = 0.0
                velocity_consecutive = 0
                if attention_cache is None:
                    mode = "full"
                elif isinstance(attention_refresh, list):
                    refreshed = sum(attention_refresh)
                    mode = "full" if refreshed == len(attention_refresh) else \
                        f"layered-pab-{refreshed}/{len(attention_refresh)}"
                else:
                    mode = "pab-reuse" if not attention_refresh else "full"
            stepped_video = video_sched.step(
                video_velocity, float(timestep), video_rows[n_cond_v:])
            if protected_count:
                stepped_video = mx.concatenate([protected_video_rows, stepped_video[protected_count:]])
            stepped_audio = target_audio_rows if target_audio_rows is not None else audio_sched.step(
                audio_velocity,
                float(audio_sched.timesteps[index].item()), audio_rows[n_cond_a:])
            video_rows = mx.concatenate([video_rows[:n_cond_v], stepped_video]) if n_cond_v else stepped_video
            audio_rows = mx.concatenate([audio_rows[:n_cond_a], stepped_audio]) if n_cond_a else stepped_audio
            live_attention = [] if attention_cache is None else [
                value for value in attention_cache if value is not None
            ]
            mx.eval(video_rows, audio_rows, cached_video_pred, cached_audio_pred, *live_attention)
            # Keep allocator telemetry available for A/B runs. Full per-step cache clearing is an
            # explicit benchmark/low-memory option: on some MLX releases it bounds the pool, while
            # on others rebuilding the large attention workspace costs more than retaining it.
            before_step = mlx_memory_snapshot()
            if clear_step_cache:
                mx.clear_cache()
            after_step = mlx_memory_snapshot()
            step_times.append(time.perf_counter() - step_started)
            step_modes.append(mode)
            step_memory.append({**before_step, **{
                f"after_step_{key}": value for key, value in after_step.items()
            }})
            if verbose:
                memory = ""
                if before_step:
                    memory = (f" active={before_step.get('active_bytes', 0) / 1e9:.1f}GB"
                              f" cache={before_step.get('cache_bytes', 0) / 1e9:.1f}GB")
                print(f"  step {index + 1}/{len(video_sched.timesteps)} "
                      f"{step_times[-1]:.1f}s{memory} {mode}",
                      flush=True)
        video_rows, audio_rows = video_rows[n_cond_v:], audio_rows[n_cond_a:]
        mx.eval(video_rows, audio_rows)
        del cache, helper, dit, prompt_embeds, embeds, refined_text, rotary, final_modulation, \
            attention_cache, cached_video_pred, cached_audio_pred, condition_rows, \
            condition_audio_rows, visual_latents, audio_latents_by_reference
        self._release("dit", video_rows, audio_rows)

        # Stage 4: video decoder.
        video_vae = self._load("video_vae")
        # 320px is also the strict default.  It nearly halves decoder time on
        # 512x288/512x512 output without enabling any denoiser approximation;
        # callers targeting tighter memory budgets can still request 256.
        tile_size = 320 if video_vae_tile_size is None else int(video_vae_tile_size)
        if tile_size < 256 or tile_size % video_cfg.spatial_compression_ratio:
            raise ValueError(
                f"`video_vae_tile_size` must be >= 256 and divisible by "
                f"{video_cfg.spatial_compression_ratio}, got {tile_size}.")
        video_vae.tile_sample_min_height = tile_size
        video_vae.tile_sample_min_width = tile_size
        video_vae.batch_decoder_tiles = fast_max
        latents = unpatchify_video_tokens(
            video_rows, num_latent_frames, latent_height, latent_width,
            video_cfg.latent_channels, patch_size)
        mean = mx.array(np.array(video_cfg.latents_mean, np.float32)).reshape(1, -1, 1, 1, 1)
        std = mx.array(np.array(video_cfg.latents_std, np.float32)).reshape(1, -1, 1, 1, 1)
        # Window/context differences are multiples of 51 pixels = 15 latent frames.
        # This preserves the VAE's 17-frame chunk phase. The first decoder overlap
        # may differ, but it is discarded along with the protected context.
        continuation_latents = None
        if return_context_frames is not None:
            count = video_latent_num_frames(return_context_frames)
            continuation_latents = np.array(latents[:, :, -count:], copy=True)
        frames = np.array(video_vae.decode((latents * std + mean).astype(mx.float32)))
        pixel_mean = np.array(PIXEL_MEAN, np.float32).reshape(1, 3, 1, 1, 1)
        pixel_std = np.array(PIXEL_STD, np.float32).reshape(1, 3, 1, 1, 1)
        frames = np.clip(frames * pixel_std + pixel_mean, 0.0, 1.0)[0].transpose(1, 2, 3, 0)
        video = (frames * 255.0 + 0.5).astype(np.uint8)
        del video_vae, video_rows, latents
        self._release("video_vae")

        # Fixed-audio jobs retain their source PCM and skip lossy VAE reconstruction.
        if driving_audio is not None:
            audio = driving_audio.copy()
            del audio_rows, target_audio_rows
        else:
            # Stage 5: audio decoder.
            audio_vae = self._load("audio_vae")
            latents = unpack_audio_tokens(audio_rows, num_audio_latents)
            mean = mx.array(np.array(audio_cfg.latents_mean, np.float32)).reshape(1, -1, 1)
            std = mx.array(np.array(audio_cfg.latents_std, np.float32)).reshape(1, -1, 1)
            waveform = np.array(audio_vae.decode((latents * std + mean).astype(mx.float32)))[:, 0, :]
            audio = waveform.astype(np.float32)
            del audio_vae, audio_rows, latents
            self._release("audio_vae")

        total = time.perf_counter() - started
        return GenerationResult(video=video, audio=audio, sample_rate=audio_cfg.sampling_rate,
                                seconds_per_step=sum(step_times) / max(len(step_times), 1),
                                total_seconds=total, step_seconds=tuple(step_times),
                                step_memory=tuple(step_memory), step_modes=tuple(step_modes),
                                continuation_latents=continuation_latents)
