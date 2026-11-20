# SPDX-License-Identifier: Apache-2.0
"""Checkpoint-specific swish attention for Qwen3.8 27B on Transformers 5.18.

Forward follows Hugging Face Transformers Qwen3_5Attention (Apache-2.0),
changing only the checkpoint-declared output gate. No global class patch.
"""
import torch
import transformers
from transformers.models.qwen3_5.modeling_qwen3_5 import (
    ALL_ATTENTION_FUNCTIONS, Qwen3_5Attention,
    apply_rotary_pos_emb, eager_attention_forward,
)


class Qwen38SwishAttention(Qwen3_5Attention):
    def forward(self, hidden_states, position_embeddings, attention_mask,
                past_key_values=None, **kwargs):
        input_shape = hidden_states.shape[:-1]
        hidden_shape = (*input_shape, -1, self.head_dim)
        query, gate = torch.chunk(
            self.q_proj(hidden_states).view(*input_shape, -1, self.head_dim * 2), 2, dim=-1,
        )
        gate = gate.reshape(*input_shape, -1)
        query = self.q_norm(query.view(hidden_shape)).transpose(1, 2)
        key = self.k_norm(self.k_proj(hidden_states).view(hidden_shape)).transpose(1, 2)
        value = self.v_proj(hidden_states).view(hidden_shape).transpose(1, 2)
        cos, sin = position_embeddings
        query, key = apply_rotary_pos_emb(query, key, cos, sin)
        if past_key_values is not None:
            key, value = past_key_values.update(key, value, self.layer_idx)
        attention = ALL_ATTENTION_FUNCTIONS.get_interface(
            self.config._attn_implementation, eager_attention_forward,
        )
        output, weights = attention(
            self, query, key, value, attention_mask,
            dropout=0.0 if not self.training else self.attention_dropout,
            scaling=self.scaling, **kwargs,
        )
        output = output.reshape(*input_shape, -1).contiguous()
        output = output * torch.nn.functional.silu(gate)
        return self.o_proj(output), weights


def apply_qwen38_swish(model, checkpoint_config):
    text = checkpoint_config.get("text_config", {})
    if (checkpoint_config.get("model_type") != "qwen3_5"
            or text.get("output_gate_type") != "swish"
            or text.get("hidden_size") != 5120 or text.get("num_hidden_layers") != 64):
        raise ValueError("Not the validated Qwen3.8 27B swish checkpoint")
    if transformers.__version__ != "5.18.0":
        raise RuntimeError("Revalidate the attention ABI before using another Transformers version")
    modules = [m for m in model.modules() if type(m) is Qwen3_5Attention]
    if len(modules) != 16:
        raise ValueError(f"Expected 16 full-attention layers, got {len(modules)}")
    for module in modules:
        module.__class__ = Qwen38SwishAttention
    return len(modules)


def self_test():
    import copy
    from transformers.models.qwen3_5.configuration_qwen3_5 import Qwen3_5TextConfig
    torch.manual_seed(38)
    config = Qwen3_5TextConfig(hidden_size=32, num_attention_heads=2, num_key_value_heads=1,
                             head_dim=16, num_hidden_layers=1)
    config._attn_implementation = "eager"
    baseline = Qwen3_5Attention(config, 0).eval()
    actual = copy.deepcopy(baseline)
    actual.__class__ = Qwen38SwishAttention
    inputs = torch.randn(1, 3, 32)
    positions = (torch.ones(1, 3, 16), torch.zeros(1, 3, 16))
    ordinary = baseline(inputs, positions, None)[0]
    # Independent reference: sigmoid(gate) * gate at the output projection.
    gate = baseline.q_proj(inputs).view(1, 3, 2, 32).chunk(2, -1)[1].reshape(1, 3, 32)
    hook = baseline.o_proj.register_forward_pre_hook(lambda module, args: (args[0] * gate,))
    expected = baseline(inputs, positions, None)[0]
    hook.remove()
    result = actual(inputs, positions, None)[0]
    torch.testing.assert_close(result, expected, rtol=1e-5, atol=1e-6)
    assert not torch.allclose(result, ordinary)
    assert type(baseline) is Qwen3_5Attention
    print("swish attention reference and instance isolation passed")


if __name__ == "__main__":
    self_test()
