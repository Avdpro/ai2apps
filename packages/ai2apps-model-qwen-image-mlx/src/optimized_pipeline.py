"""AI2Apps optimizations layered on the audited mflux Qwen Image graph."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable

import mlx.core as mx
from mflux.models.qwen.variants.edit.qwen_image_edit import QwenImageEdit
from mflux.models.qwen.variants.txt2img.qwen_image import QwenImage


class _EvaluatedLRU(OrderedDict):
    """Bound prompt tensors and materialize them before retaining the graph."""

    def __init__(self, limit: int, evaluator: Callable[..., Any] = mx.eval) -> None:
        super().__init__()
        self.limit = limit
        self.evaluator = evaluator
        self.requests = 0
        self.hits = 0

    def __contains__(self, key: object) -> bool:
        self.requests += 1
        present = super().__contains__(key)
        if present:
            self.hits += 1
        return present

    def __getitem__(self, key: object):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key: object, value: Any) -> None:
        tensors = tuple(item for item in value if item is not None)
        if tensors:
            self.evaluator(*tensors)
        super().__setitem__(key, value)
        self.move_to_end(key)
        while len(self) > self.limit:
            self.popitem(last=False)


class OptimizedQwenImage(QwenImage):
    """Use a bounded evaluated cache instead of mflux's unbounded graph cache."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.prompt_cache = _EvaluatedLRU(limit=8)

    def generate_image(self, *args, guidance: float = 4.0, **kwargs):
        if guidance != 1.0:
            return super().generate_image(*args, guidance=guidance, **kwargs)
        return self._generate_single_pass(*args, guidance=guidance, **kwargs)

    def _generate_single_pass(
        self,
        seed: int,
        prompt: str,
        num_inference_steps: int = 4,
        height: int = 1024,
        width: int = 1024,
        guidance: float = 1.0,
        image_path: Path | str | None = None,
        image_strength: float | None = None,
        scheduler: str = "linear",
        negative_prompt: str | None = None,
        **_unsupported,
    ):
        # At guidance=1, mflux's normalized CFG expression is exactly the
        # positive prediction. Avoiding the unused negative transformer pass
        # preserves the math while nearly halving denoiser work.
        from mflux.models.common.config.config import Config
        from mflux.models.common.latent_creator.latent_creator import Img2Img, LatentCreator
        from mflux.models.common.vae.vae_util import VAEUtil
        from mflux.models.qwen.latent_creator.qwen_latent_creator import QwenLatentCreator
        from mflux.models.qwen.model.qwen_text_encoder.qwen_prompt_encoder import QwenPromptEncoder
        from mflux.utils.exceptions import StopImageGenerationException
        from mflux.utils.image_util import ImageUtil

        config = Config(
            width=width,
            height=height,
            guidance=guidance,
            scheduler=scheduler,
            image_path=image_path,
            image_strength=image_strength,
            model_config=self.model_config,
            num_inference_steps=num_inference_steps,
        )
        latents = LatentCreator.create_for_txt2img_or_img2img(
            seed=seed,
            width=config.width,
            height=config.height,
            img2img=Img2Img(
                vae=self.vae,
                latent_creator=QwenLatentCreator,
                sigmas=config.scheduler.sigmas,
                init_time_step=config.init_time_step,
                image_path=config.image_path,
                tiling_config=self.tiling_config,
            ),
        )
        positive, positive_mask, _negative, _negative_mask = QwenPromptEncoder.encode_prompt(
            prompt=prompt,
            negative_prompt=negative_prompt,
            prompt_cache=self.prompt_cache,
            qwen_tokenizer=self.tokenizers["qwen"],
            qwen_text_encoder=self.text_encoder,
        )
        ctx = self.callbacks.start(seed=seed, prompt=prompt, config=config)
        ctx.before_loop(latents)
        for t in config.time_steps:
            try:
                latents = config.scheduler.scale_model_input(latents, t)
                noise = self.transformer(
                    t=t,
                    config=config,
                    hidden_states=latents,
                    encoder_hidden_states=positive,
                    encoder_hidden_states_mask=positive_mask,
                )
                latents = config.scheduler.step(noise=noise, timestep=t, latents=latents)
                ctx.in_loop(t, latents)
                mx.eval(latents)
            except KeyboardInterrupt:
                ctx.interruption(t, latents)
                raise StopImageGenerationException(
                    f"Stopping image generation at step {t + 1}/{config.num_inference_steps}"
                )
        ctx.after_loop(latents)
        latents = QwenLatentCreator.unpack_latents(
            latents=latents, height=config.height, width=config.width
        )
        decoded = VAEUtil.decode(vae=self.vae, latent=latents, tiling_config=self.tiling_config)
        return ImageUtil.to_image(
            decoded_latents=decoded,
            config=config,
            seed=seed,
            prompt=prompt,
            quantization=self.bits,
            lora_paths=self.lora_paths,
            lora_scales=self.lora_scales,
            image_path=config.image_path,
            image_strength=config.image_strength,
            generation_time=config.time_steps.format_dict["elapsed"],
            negative_prompt=negative_prompt,
        )

    def ai2apps_optimization_stats(self) -> dict[str, int | float]:
        requests = self.prompt_cache.requests
        return {
            "prompt_cache_requests": requests,
            "prompt_cache_hits": self.prompt_cache.hits,
            "prompt_cache_hit_rate": self.prompt_cache.hits / requests if requests else 0.0,
            "prompt_cache_entries": len(self.prompt_cache),
        }


class OptimizedQwenImageEdit(QwenImageEdit):
    """Cache repeated reference/prompt encodings for regenerate workflows."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._ai2apps_edit_prompt_cache = _EvaluatedLRU(limit=2)

    @staticmethod
    def _reference_identity(image_paths: list[str]) -> tuple[str, ...]:
        identities = []
        for value in image_paths:
            digest = hashlib.sha256()
            with Path(value).open("rb") as source:
                for chunk in iter(lambda: source.read(1 << 20), b""):
                    digest.update(chunk)
            identities.append(digest.hexdigest())
        return tuple(identities)

    def _encode_prompts_with_images(
        self,
        prompt: str,
        negative_prompt: str,
        image_paths: list[str],
        config,
        vl_width: int | None = None,
        vl_height: int | None = None,
    ):
        key = (
            prompt,
            negative_prompt,
            self._reference_identity(image_paths),
            vl_width,
            vl_height,
        )
        cache = self._ai2apps_edit_prompt_cache
        if key in cache:
            return cache[key]
        value = super()._encode_prompts_with_images(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image_paths=image_paths,
            config=config,
            vl_width=vl_width,
            vl_height=vl_height,
        )
        cache[key] = value
        return value

    def ai2apps_optimization_stats(self) -> dict[str, int | float]:
        cache = self._ai2apps_edit_prompt_cache
        requests = cache.requests
        return {
            "edit_prompt_cache_requests": requests,
            "edit_prompt_cache_hits": cache.hits,
            "edit_prompt_cache_hit_rate": cache.hits / requests if requests else 0.0,
            "edit_prompt_cache_entries": len(cache),
        }
