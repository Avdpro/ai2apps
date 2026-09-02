"""Benchmark-only exact Q/K/V projection fusion for quantized Qwen Image."""

import mlx.core as mx
from mlx.core.fast import scaled_dot_product_attention
from mlx.nn import QuantizedLinear


def _pack(projections):
    first = projections[0]
    if not all(
        isinstance(layer, QuantizedLinear)
        and layer.group_size == first.group_size
        and layer.bits == first.bits
        and layer.mode == first.mode
        for layer in projections
    ):
        raise TypeError("fused QKV requires matching QuantizedLinear projections")
    packed = {
        "weight": mx.concatenate([layer.weight for layer in projections], axis=0),
        "scales": mx.concatenate([layer.scales for layer in projections], axis=0),
        "biases": mx.concatenate([layer.biases for layer in projections], axis=0),
        "bias": mx.concatenate([layer.bias for layer in projections], axis=0),
        "group_size": first.group_size,
        "bits": first.bits,
        "mode": first.mode,
    }
    return packed


def _project(x, packed):
    return mx.quantized_matmul(
        x,
        packed["weight"],
        scales=packed["scales"],
        biases=packed["biases"],
        transpose=True,
        group_size=packed["group_size"],
        bits=packed["bits"],
        mode=packed["mode"],
    ) + packed["bias"]


def install_fused_qkv() -> None:
    from mflux.models.qwen.model.qwen_transformer.qwen_attention import QwenAttention

    def fused_call(
        self,
        img_modulated,
        txt_modulated,
        encoder_hidden_states_mask,
        image_rotary_emb,
        block_idx=None,
    ):
        img_query, img_key, img_value = mx.split(
            _project(img_modulated, self._ai2apps_img_qkv), 3, axis=-1
        )
        txt_query, txt_key, txt_value = mx.split(
            _project(txt_modulated, self._ai2apps_txt_qkv), 3, axis=-1
        )

        shape = (img_query.shape[0], img_query.shape[1], self.num_heads, self.head_dim)
        img_query = mx.reshape(img_query, shape)
        img_key = mx.reshape(img_key, shape)
        img_value = mx.reshape(img_value, shape)
        shape = (txt_query.shape[0], txt_query.shape[1], self.num_heads, self.head_dim)
        txt_query = mx.reshape(txt_query, shape)
        txt_key = mx.reshape(txt_key, shape)
        txt_value = mx.reshape(txt_value, shape)

        img_query = self.norm_q(img_query)
        img_key = self.norm_k(img_key)
        txt_query = self.norm_added_q(txt_query)
        txt_key = self.norm_added_k(txt_key)
        if image_rotary_emb is not None:
            (img_cos, img_sin), (txt_cos, txt_sin) = image_rotary_emb
            img_query = self._apply_rope_qwen(img_query, img_cos, img_sin)
            img_key = self._apply_rope_qwen(img_key, img_cos, img_sin)
            txt_query = self._apply_rope_qwen(txt_query, txt_cos, txt_sin)
            txt_key = self._apply_rope_qwen(txt_key, txt_cos, txt_sin)

        joint_query = mx.concatenate([txt_query, img_query], axis=1)
        joint_key = mx.concatenate([txt_key, img_key], axis=1)
        joint_value = mx.concatenate([txt_value, img_value], axis=1)
        seq_txt = txt_modulated.shape[1]
        mask = self._convert_mask_for_qwen(
            encoder_hidden_states_mask, joint_query.shape[1], seq_txt
        )
        query = mx.transpose(joint_query, (0, 2, 1, 3))
        key = mx.transpose(joint_key, (0, 2, 1, 3))
        value = mx.transpose(joint_value, (0, 2, 1, 3))
        hidden = scaled_dot_product_attention(
            query,
            key,
            value,
            scale=1.0 / (self.head_dim**0.5),
            mask=mask,
        )
        hidden = mx.transpose(hidden, (0, 2, 1, 3))
        hidden = mx.reshape(hidden, (hidden.shape[0], hidden.shape[1], self.dim))
        hidden = hidden.astype(joint_query.dtype)
        txt_output = self.to_add_out(hidden[:, :seq_txt, :])
        img_output = self.attn_to_out[0](hidden[:, seq_txt:, :])
        return img_output, txt_output

    QwenAttention.__call__ = fused_call

def prepare_fused_qkv(pipeline) -> None:
    arrays = []
    for block in pipeline.transformer.transformer_blocks:
        attention = block.attn
        img = _pack([attention.to_q, attention.to_k, attention.to_v])
        txt = _pack(
            [attention.add_q_proj, attention.add_k_proj, attention.add_v_proj]
        )
        object.__setattr__(attention, "_ai2apps_img_qkv", img)
        object.__setattr__(attention, "_ai2apps_txt_qkv", txt)
        arrays.extend(
            value
            for packed in (img, txt)
            for value in packed.values()
            if isinstance(value, mx.array)
        )
        # The packed tensors contain the same rows as the six source layers.
        # Drop the now-unused modules so the experiment does not retain a
        # second copy of every Q/K/V weight.
        attention.to_q = None
        attention.to_k = None
        attention.to_v = None
        attention.add_q_proj = None
        attention.add_k_proj = None
        attention.add_v_proj = None
    mx.eval(*arrays)
