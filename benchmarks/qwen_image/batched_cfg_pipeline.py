"""Benchmark-only Qwen Image pipeline with positive/negative CFG batching."""

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


class BatchedCFGQwenImage(QwenImage):
    """Evaluate both true-CFG branches in one transformer call per step."""

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
        max_length = max(positive.shape[1], negative.shape[1])
        if positive.shape[1] < max_length:
            padding = max_length - positive.shape[1]
            positive = mx.pad(positive, ((0, 0), (0, padding), (0, 0)))
            positive_mask = mx.pad(positive_mask, ((0, 0), (0, padding)))
        if negative.shape[1] < max_length:
            padding = max_length - negative.shape[1]
            negative = mx.pad(negative, ((0, 0), (0, padding), (0, 0)))
            negative_mask = mx.pad(negative_mask, ((0, 0), (0, padding)))
        single_pass = guidance == 1.0
        embeddings = (
            positive if single_pass else mx.concatenate([positive, negative], axis=0)
        )
        masks = (
            positive_mask
            if single_pass
            else mx.concatenate([positive_mask, negative_mask], axis=0)
        )
        ctx = self.callbacks.start(seed=seed, prompt=prompt, config=config)
        ctx.before_loop(latents)
        for t in config.time_steps:
            try:
                latents = config.scheduler.scale_model_input(latents, t)
                model_latents = (
                    latents if single_pass else mx.concatenate([latents, latents], axis=0)
                )
                predicted = self.transformer(
                    t=t,
                    config=config,
                    hidden_states=model_latents,
                    encoder_hidden_states=embeddings,
                    encoder_hidden_states_mask=masks,
                )
                if single_pass:
                    guided_noise = predicted
                else:
                    noise, noise_negative = mx.split(predicted, 2, axis=0)
                    guided_noise = QwenImage.compute_guided_noise(
                        noise, noise_negative, config.guidance
                    )
                latents = config.scheduler.step(noise=guided_noise, timestep=t, latents=latents)
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
