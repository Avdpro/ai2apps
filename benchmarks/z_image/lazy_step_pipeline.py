"""Benchmark pipeline that reduces denoising synchronization frequency."""

import mlx.core as mx

from mflux.models.common.config.config import Config
from mflux.models.common.latent_creator.latent_creator import Img2Img, LatentCreator
from mflux.models.common.vae.vae_util import VAEUtil
from mflux.models.z_image.latent_creator import ZImageLatentCreator
from mflux.models.z_image.variants.z_image import ZImage
from mflux.utils.image_util import ImageUtil


class LazyStepZImage(ZImage):
    sync_interval = 0

    def generate_image(
        self,
        seed,
        prompt,
        num_inference_steps=4,
        height=1024,
        width=1024,
        guidance=None,
        image_path=None,
        image_strength=None,
        scheduler=None,
        negative_prompt=None,
        pid_decode=False,
        pid_degrade_sigma=0.0,
    ):
        supports_guidance = bool(self.model_config.supports_guidance)
        if not supports_guidance:
            guidance = 0.0
        if scheduler is None:
            scheduler = "flow_match_euler_discrete" if supports_guidance else "linear"
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
                latent_creator=ZImageLatentCreator,
                image_path=config.image_path,
                sigmas=config.scheduler.sigmas,
                init_time_step=config.init_time_step,
                tiling_config=self.tiling_config,
            ),
        )
        text_encodings, negative_encodings = self._encode_prompts(
            prompt=prompt,
            negative_prompt=negative_prompt,
            guidance=config.guidance,
        )
        ctx = self.callbacks.start(seed=seed, prompt=prompt, config=config)
        ctx.before_loop(latents)
        predict = self._predict(self.transformer)
        for step_index, t in enumerate(config.time_steps, start=1):
            sigma_t = config.scheduler.sigmas[t].reshape((1,))
            timestep = mx.ones_like(sigma_t) - sigma_t
            noise = predict(
                latents=latents,
                timestep=timestep,
                sigmas=config.scheduler.sigmas,
                text_encodings=text_encodings,
                negative_encodings=negative_encodings,
                guidance=config.guidance,
            )
            latents = config.scheduler.step(
                noise=noise, timestep=t, latents=latents
            )
            ctx.in_loop(t, latents)
            if self.sync_interval and step_index % self.sync_interval == 0:
                mx.eval(latents)
        ctx.after_loop(latents)
        unpacked = ZImageLatentCreator.unpack_latents(
            latents, config.height, config.width
        )
        decoded = VAEUtil.decode(
            vae=self.vae, latent=unpacked, tiling_config=self.tiling_config
        )
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
            pid_decode=pid_decode,
            pid_degrade_sigma=pid_degrade_sigma,
        )
