"""Benchmark-only Qwen block integration for the audited Metal norm fusions."""

import mlx.core as mx

from flux2_fused_ops import layer_norm_adaln, metal_fusions_available, residual_layer_norm_adaln


def install_fused_blocks() -> bool:
    if not metal_fusions_available():
        return False
    from mflux.models.qwen.model.qwen_transformer.qwen_transformer_block import (
        QwenTransformerBlock,
    )

    def fused_call(
        self,
        hidden_states,
        encoder_hidden_states,
        encoder_hidden_states_mask,
        text_embeddings,
        image_rotary_emb,
        block_idx=None,
    ):
        img_mod_params = self.img_mod_linear(self.img_mod_silu(text_embeddings))
        txt_mod_params = self.txt_mod_linear(self.txt_mod_silu(text_embeddings))
        img_mod1, img_mod2 = mx.split(img_mod_params, 2, axis=-1)
        txt_mod1, txt_mod2 = mx.split(txt_mod_params, 2, axis=-1)
        img_shift1, img_scale1, img_gate1 = mx.split(img_mod1, 3, axis=-1)
        txt_shift1, txt_scale1, txt_gate1 = mx.split(txt_mod1, 3, axis=-1)
        img_shift2, img_scale2, img_gate2 = mx.split(img_mod2, 3, axis=-1)
        txt_shift2, txt_scale2, txt_gate2 = mx.split(txt_mod2, 3, axis=-1)

        img_modulated = layer_norm_adaln(hidden_states, img_shift1, img_scale1)
        txt_modulated = layer_norm_adaln(
            encoder_hidden_states, txt_shift1, txt_scale1
        )
        img_attention, txt_attention = self.attn(
            img_modulated=img_modulated,
            txt_modulated=txt_modulated,
            encoder_hidden_states_mask=encoder_hidden_states_mask,
            image_rotary_emb=image_rotary_emb,
            block_idx=block_idx,
        )
        hidden_states, img_modulated2 = residual_layer_norm_adaln(
            hidden_states, img_attention, img_gate1, img_shift2, img_scale2
        )
        encoder_hidden_states, txt_modulated2 = residual_layer_norm_adaln(
            encoder_hidden_states,
            txt_attention,
            txt_gate1,
            txt_shift2,
            txt_scale2,
        )
        hidden_states = hidden_states + img_gate2[:, None, :] * self.img_ff(
            img_modulated2
        )
        encoder_hidden_states = (
            encoder_hidden_states
            + txt_gate2[:, None, :] * self.txt_ff(txt_modulated2)
        )
        return encoder_hidden_states, hidden_states

    QwenTransformerBlock.__call__ = fused_call
    return True
