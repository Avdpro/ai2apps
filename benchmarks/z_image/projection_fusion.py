"""Benchmark-only projection packing for quantized Z-Image transformer blocks."""

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
        raise TypeError("projection packing requires matching QuantizedLinear layers")
    return {
        "weight": mx.concatenate([layer.weight for layer in projections], axis=0),
        "scales": mx.concatenate([layer.scales for layer in projections], axis=0),
        "biases": mx.concatenate([layer.biases for layer in projections], axis=0),
        "group_size": first.group_size,
        "bits": first.bits,
        "mode": first.mode,
    }


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
    )


def install_projection_fusion(*, fuse_ffn: bool = False) -> None:
    from mflux.models.z_image.model.z_image_transformer.attention import ZImageAttention

    def fused_attention_call(
        self,
        hidden_states,
        attention_mask=None,
        freqs_cis=None,
    ):
        batch_size, seq_len, _ = hidden_states.shape
        query, key, value = mx.split(
            _project(hidden_states, self._ai2apps_qkv), 3, axis=-1
        )
        shape = (batch_size, seq_len, self.n_heads, self.head_dim)
        query = query.reshape(shape)
        key = key.reshape(shape)
        value = value.reshape(shape)
        if self.norm_q is not None:
            query = self.norm_q(query)
        if self.norm_k is not None:
            key = self.norm_k(key)
        if freqs_cis is not None:
            query = ZImageAttention._apply_rotary_emb(query, freqs_cis)
            key = ZImageAttention._apply_rotary_emb(key, freqs_cis)
        query = mx.transpose(query, axes=(0, 2, 1, 3))
        key = mx.transpose(key, axes=(0, 2, 1, 3))
        value = mx.transpose(value, axes=(0, 2, 1, 3))
        mask = None
        if attention_mask is not None:
            mask = mx.where(
                attention_mask[:, None, None, :],
                mx.array(0.0),
                mx.array(float("-inf")),
            )
        hidden_states = scaled_dot_product_attention(
            query, key, value, scale=self.scale, mask=mask
        )
        hidden_states = mx.transpose(hidden_states, axes=(0, 2, 1, 3))
        hidden_states = hidden_states.reshape(batch_size, seq_len, self.dim)
        return self.to_out[0](hidden_states)

    ZImageAttention.__call__ = fused_attention_call

    if fuse_ffn:
        from mflux.models.z_image.model.z_image_transformer.feed_forward import FeedForward
        from mlx import nn

        def fused_ffn_call(self, x):
            gate, up = mx.split(_project(x, self._ai2apps_gate_up), 2, axis=-1)
            return self.w2(nn.silu(gate) * up)

        FeedForward.__call__ = fused_ffn_call


def prepare_projection_fusion(pipeline, *, fuse_ffn: bool = False) -> None:
    transformer = pipeline.transformer
    blocks = transformer.noise_refiner + transformer.context_refiner + transformer.layers
    arrays = []
    for block in blocks:
        attention = block.attention
        qkv = _pack([attention.to_q, attention.to_k, attention.to_v])
        object.__setattr__(attention, "_ai2apps_qkv", qkv)
        arrays.extend(value for value in qkv.values() if isinstance(value, mx.array))
        attention.to_q = None
        attention.to_k = None
        attention.to_v = None

        if fuse_ffn:
            feed_forward = block.feed_forward
            gate_up = _pack([feed_forward.w1, feed_forward.w3])
            object.__setattr__(feed_forward, "_ai2apps_gate_up", gate_up)
            arrays.extend(
                value for value in gate_up.values() if isinstance(value, mx.array)
            )
            feed_forward.w1 = None
            feed_forward.w3 = None
    mx.eval(*arrays)
