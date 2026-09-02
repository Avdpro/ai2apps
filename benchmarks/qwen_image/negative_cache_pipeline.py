"""Benchmark-only Qwen pipeline that refreshes negative CFG at a cadence."""

from pathlib import Path

import mlx.core as mx

from mflux.models.common.config.config import Config
from mflux.models.common.latent_creator.latent_creator import Img2Img, LatentCreator
from mflux.models.common.vae.vae_util import VAEUtil
from mflux.models.qwen.latent_creator.qwen_latent_creator import QwenLatentCreator
from mflux.models.qwen.model.qwen_text_encoder.qwen_prompt_encoder import QwenPromptEncoder
from mflux.models.qwen.variants.txt2img.qwen_image import QwenImage
from mflux.utils.exceptions import StopImageGenerationException
from mflux.utils.image_util import ImageUtil


class NegativeCacheQwenImage(QwenImage):
    negative_cadence = 2

    def generate_image(
        self,
        seed: int,
        prompt: str,
        num_inference_steps: int = 4,
        height: int = 1024,
        width: int = 1024,
        guidance: float = 4.0,
        image_path: Path | str | None = None,
        image_strength: float | None = None,
        scheduler: str = "linear",
        negative_prompt: str | None = None,
        **_unsupported,
    ):
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
        positive, positive_mask, negative, negative_mask = QwenPromptEncoder.encode_prompt(
            prompt=prompt,
            negative_prompt=negative_prompt,
            prompt_cache=self.prompt_cache,
            qwen_tokenizer=self.tokenizers["qwen"],
            qwen_text_encoder=self.text_encoder,
        )
        ctx = self.callbacks.start(seed=seed, prompt=prompt, config=config)
        ctx.before_loop(latents)
        cached_negative = None
        for index, t in enumerate(config.time_steps):
            try:
                latents = config.scheduler.scale_model_input(latents, t)
                noise = self.transformer(
                    t=t,
                    config=config,
                    hidden_states=latents,
                    encoder_hidden_states=positive,
                    encoder_hidden_states_mask=positive_mask,
                )
                refresh_negative = cached_negative is None or index % self.negative_cadence == 0
                if refresh_negative:
                    cached_negative = self.transformer(
                        t=t,
                        config=config,
                        hidden_states=latents,
                        encoder_hidden_states=negative,
                        encoder_hidden_states_mask=negative_mask,
                    )
                guided = QwenImage.compute_guided_noise(
                    noise, cached_negative, config.guidance
                )
                latents = config.scheduler.step(noise=guided, timestep=t, latents=latents)
                ctx.in_loop(t, latents)
                # The refreshed negative prediction is already a dependency of
                # latents. Keeping the array referenced is sufficient to reuse
                # its evaluated buffer; requesting it as a second sync output
                # makes the refresh steps materially slower on Metal.
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
