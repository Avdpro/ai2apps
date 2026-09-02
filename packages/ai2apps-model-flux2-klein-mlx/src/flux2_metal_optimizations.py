"""Guarded block-level integration of FLUX.2 Metal fusions."""

from __future__ import annotations

from flux2_fused_ops import (
    layer_norm_adaln,
    metal_fusions_available,
    residual_layer_norm_adaln,
)


_INSTALLED = False


def install_flux2_metal_fusions() -> bool:
    """Install fusions once on Apple Metal; leave CUDA/CPU classes untouched."""
    global _INSTALLED
    if _INSTALLED:
        return True
    if not metal_fusions_available():
        return False

    from mflux.models.flux2.model.flux2_transformer.single_transformer_block import (
        Flux2SingleTransformerBlock,
    )
    from mflux.models.flux2.model.flux2_transformer.transformer_block import (
        Flux2TransformerBlock,
    )

    def double_block_call(
        self,
        hidden_states,
        encoder_hidden_states,
        temb_mod_params_img,
        temb_mod_params_txt,
        image_rotary_emb,
        kv_cache=None,
        kv_cache_layer_idx=None,
    ):
        (shift_msa, scale_msa, gate_msa), (shift_mlp, scale_mlp, gate_mlp) = temb_mod_params_img
        (c_shift_msa, c_scale_msa, c_gate_msa), (c_shift_mlp, c_scale_mlp, c_gate_mlp) = temb_mod_params_txt

        norm_hidden_states = layer_norm_adaln(hidden_states, shift_msa, scale_msa)
        norm_encoder_hidden_states = layer_norm_adaln(
            encoder_hidden_states, c_shift_msa, c_scale_msa
        )
        attn_output, encoder_attn_output = self.attn(
            hidden_states=norm_hidden_states,
            encoder_hidden_states=norm_encoder_hidden_states,
            image_rotary_emb=image_rotary_emb,
            kv_cache=kv_cache,
            kv_cache_layer_idx=kv_cache_layer_idx,
        )

        hidden_states, norm_hidden_states = residual_layer_norm_adaln(
            hidden_states, attn_output, gate_msa, shift_mlp, scale_mlp
        )
        encoder_hidden_states, norm_encoder_hidden_states = residual_layer_norm_adaln(
            encoder_hidden_states,
            encoder_attn_output,
            c_gate_msa,
            c_shift_mlp,
            c_scale_mlp,
        )
        hidden_states = hidden_states + gate_mlp * self.ff(norm_hidden_states)
        encoder_hidden_states = (
            encoder_hidden_states
            + c_gate_mlp * self.ff_context(norm_encoder_hidden_states)
        )
        return encoder_hidden_states, hidden_states

    def single_block_call(
        self,
        hidden_states,
        temb_mod_params,
        image_rotary_emb,
        kv_cache=None,
        kv_cache_layer_idx=None,
    ):
        mod_shift, mod_scale, mod_gate = temb_mod_params
        norm_hidden_states = layer_norm_adaln(hidden_states, mod_shift, mod_scale)
        attn_output = self.attn(
            norm_hidden_states,
            image_rotary_emb,
            kv_cache=kv_cache,
            kv_cache_layer_idx=kv_cache_layer_idx,
        )
        return hidden_states + mod_gate * attn_output

    Flux2TransformerBlock.__call__ = double_block_call
    Flux2SingleTransformerBlock.__call__ = single_block_call
    _INSTALLED = True
    return True
