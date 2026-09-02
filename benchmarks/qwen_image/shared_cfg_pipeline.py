"""Benchmark-only Qwen pipeline that shares invariant true-CFG work."""

from pathlib import Path

import mlx.core as mx

from mflux.models.common.config.config import Config
from mflux.models.common.latent_creator.latent_creator import Img2Img, LatentCreator
from mflux.models.common.vae.vae_util import VAEUtil
from mflux.models.qwen.latent_creator.qwen_latent_creator import QwenLatentCreator
from mflux.models.qwen.model.qwen_text_encoder.qwen_prompt_encoder import QwenPromptEncoder
from mflux.models.qwen.model.qwen_transformer.qwen_attention import QwenAttention
from mflux.models.qwen.model.qwen_transformer.qwen_transformer import QwenTransformer
from mflux.models.qwen.variants.txt2img.qwen_image import QwenImage
from mflux.utils.exceptions import StopImageGenerationException
from mflux.utils.image_util import ImageUtil


class SharedCFGQwenImage(QwenImage):
    """Reuse prompt-, geometry- and branch-invariant MLX expressions."""

    @staticmethod
    def _prepare_mask(mask: mx.array, image_sequence_length: int) -> mx.array | None:
        image = mx.ones((mask.shape[0], image_sequence_length), dtype=mx.float32)
        joint = mx.concatenate([mask.astype(mx.float32), image], axis=1)
        if bool(mx.all(joint >= 0.999).item()):
            return None
        additive = (1.0 - joint) * (-1e9)
        return additive.reshape((additive.shape[0], 1, 1, additive.shape[1]))

    @staticmethod
    def _branch(
        transformer,
        *,
        hidden_states: mx.array,
        encoder_hidden_states: mx.array,
        attention_mask: mx.array | None,
        text_embeddings: mx.array,
        rotary_embeddings: tuple[mx.array, mx.array],
    ) -> mx.array:
        for index, block in enumerate(transformer.transformer_blocks):
            encoder_hidden_states, hidden_states = block(
                hidden_states=hidden_states,
                encoder_hidden_states=encoder_hidden_states,
                encoder_hidden_states_mask=attention_mask,
                text_embeddings=text_embeddings,
                image_rotary_emb=rotary_embeddings,
                block_idx=index,
            )
        hidden_states = transformer.norm_out(hidden_states, text_embeddings)
        return transformer.proj_out(hidden_states)

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

        transformer = self.transformer
        positive = transformer.txt_in(transformer.txt_norm(positive))
        negative = transformer.txt_in(transformer.txt_norm(negative))
        positive_rope = QwenTransformer._compute_rotary_embeddings(
            encoder_hidden_states_mask=positive_mask,
            pos_embed=transformer.pos_embed,
            config=config,
        )
        negative_rope = QwenTransformer._compute_rotary_embeddings(
            encoder_hidden_states_mask=negative_mask,
            pos_embed=transformer.pos_embed,
            config=config,
        )
        image_sequence_length = (config.height // 16) * (config.width // 16)
        positive_attention_mask = self._prepare_mask(positive_mask, image_sequence_length)
        negative_attention_mask = self._prepare_mask(negative_mask, image_sequence_length)
        constants = [positive, negative, *positive_rope, *negative_rope]
        constants.extend(
            mask for mask in (positive_attention_mask, negative_attention_mask) if mask is not None
        )
        mx.eval(*constants)

        original_mask_converter = QwenAttention._convert_mask_for_qwen

        def accept_prepared_mask(_self, mask, joint_seq_len, txt_seq_len):
            if mask is None or mask.ndim == 4:
                return mask
            return original_mask_converter(mask, joint_seq_len, txt_seq_len)

        QwenAttention._convert_mask_for_qwen = accept_prepared_mask
        ctx = self.callbacks.start(seed=seed, prompt=prompt, config=config)
        ctx.before_loop(latents)
        try:
            for t in config.time_steps:
                try:
                    latents = config.scheduler.scale_model_input(latents, t)
                    hidden_states = transformer.img_in(latents)
                    batch_size = hidden_states.shape[0]
                    timestep = QwenTransformer._compute_timestep(t, config)
                    timestep = mx.broadcast_to(timestep, (batch_size,)).astype(hidden_states.dtype)
                    text_embeddings = transformer.time_text_embed(timestep, hidden_states)
                    noise = self._branch(
                        transformer,
                        hidden_states=hidden_states,
                        encoder_hidden_states=positive,
                        attention_mask=positive_attention_mask,
                        text_embeddings=text_embeddings,
                        rotary_embeddings=positive_rope,
                    )
                    noise_negative = self._branch(
                        transformer,
                        hidden_states=hidden_states,
                        encoder_hidden_states=negative,
                        attention_mask=negative_attention_mask,
                        text_embeddings=text_embeddings,
                        rotary_embeddings=negative_rope,
                    )
                    guided = QwenImage.compute_guided_noise(
                        noise, noise_negative, config.guidance
                    )
                    latents = config.scheduler.step(noise=guided, timestep=t, latents=latents)
                    ctx.in_loop(t, latents)
                    mx.eval(latents)
                except KeyboardInterrupt:
                    ctx.interruption(t, latents)
                    raise StopImageGenerationException(
                        f"Stopping image generation at step {t + 1}/{config.num_inference_steps}"
                    )
        finally:
            QwenAttention._convert_mask_for_qwen = original_mask_converter

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


class CompiledSharedCFGQwenImage(SharedCFGQwenImage):
    """Compile the stable 60-block branch graph once per loaded pipeline."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        transformer = self.transformer

        def branch(
            hidden_states,
            encoder_hidden_states,
            attention_mask,
            text_embeddings,
            image_cos,
            image_sin,
            text_cos,
            text_sin,
        ):
            return SharedCFGQwenImage._branch(
                transformer,
                hidden_states=hidden_states,
                encoder_hidden_states=encoder_hidden_states,
                attention_mask=attention_mask,
                text_embeddings=text_embeddings,
                rotary_embeddings=((image_cos, image_sin), (text_cos, text_sin)),
            )

        self._ai2apps_compiled_branch = mx.compile(branch)

    @staticmethod
    def _mask_array(mask, *, batch_size: int, joint_length: int):
        if mask is not None:
            return mask
        return mx.zeros((batch_size, 1, 1, joint_length), dtype=mx.float32)

    def _branch(self, transformer, **kwargs):
        rotary = kwargs["rotary_embeddings"]
        encoder = kwargs["encoder_hidden_states"]
        hidden = kwargs["hidden_states"]
        mask = self._mask_array(
            kwargs["attention_mask"],
            batch_size=encoder.shape[0],
            joint_length=encoder.shape[1] + hidden.shape[1],
        )
        return self._ai2apps_compiled_branch(
            hidden,
            encoder,
            mask,
            kwargs["text_embeddings"],
            rotary[0][0],
            rotary[0][1],
            rotary[1][0],
            rotary[1][1],
        )
