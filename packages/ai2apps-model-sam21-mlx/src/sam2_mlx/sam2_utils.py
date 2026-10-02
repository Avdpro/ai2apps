"""SAM2 utilities ported to MLX: MLP, DropPath, LayerNorm2d, window ops."""

import mlx.core as mx
import mlx.nn as nn


class MLP(nn.Module):
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        output_dim: int,
        num_layers: int,
        activation=nn.ReLU,
        sigmoid_output: bool = False,
    ):
        super().__init__()
        self.num_layers = num_layers
        self.sigmoid_output = sigmoid_output
        dims = [input_dim] + [hidden_dim] * (num_layers - 1) + [output_dim]
        self.layers = [nn.Linear(dims[i], dims[i + 1]) for i in range(num_layers)]
        self.act = activation()

    def __call__(self, x: mx.array) -> mx.array:
        for i, layer in enumerate(self.layers):
            x = self.act(layer(x)) if i < self.num_layers - 1 else layer(x)
        if self.sigmoid_output:
            x = mx.sigmoid(x)
        return x


class DropPath(nn.Module):
    def __init__(self, drop_prob: float = 0.0, scale_by_keep: bool = True):
        super().__init__()
        self.drop_prob = drop_prob
        self.scale_by_keep = scale_by_keep

    def __call__(self, x: mx.array) -> mx.array:
        if self.drop_prob == 0.0:
            return x
        keep_prob = 1 - self.drop_prob
        shape = (x.shape[0],) + (1,) * (x.ndim - 1)
        mask = mx.bernoulli(keep_prob, shape=shape)
        if keep_prob > 0.0 and self.scale_by_keep:
            mask = mask / keep_prob
        return x * mask


class LayerNorm2d(nn.Module):
    """Channel-wise LayerNorm for 4D tensors [B, C, H, W] (channels-first)."""

    def __init__(self, num_channels: int, eps: float = 1e-6):
        super().__init__()
        self.eps = eps
        self.weight = mx.ones((num_channels,))
        self.bias = mx.zeros((num_channels,))

    def __call__(self, x: mx.array) -> mx.array:
        # x: [B, C, H, W] channels-first
        mean = x.mean(axis=1, keepdims=True)
        var = ((x - mean) ** 2).mean(axis=1, keepdims=True)
        x = (x - mean) / mx.sqrt(var + self.eps)
        return self.weight.reshape(1, -1, 1, 1) * x + self.bias.reshape(1, -1, 1, 1)


def window_partition(x: mx.array, window_size: int):
    """Partition [B, H, W, C] into windows. Returns windows, (Hp, Wp)."""
    B, H, W, C = x.shape
    pad_h = (window_size - H % window_size) % window_size
    pad_w = (window_size - W % window_size) % window_size
    if pad_h > 0 or pad_w > 0:
        x = mx.pad(x, [(0, 0), (0, pad_h), (0, pad_w), (0, 0)])
    Hp, Wp = H + pad_h, W + pad_w
    x = x.reshape(B, Hp // window_size, window_size, Wp // window_size, window_size, C)
    windows = x.transpose(0, 1, 3, 2, 4, 5).reshape(-1, window_size, window_size, C)
    return windows, (Hp, Wp)


def window_unpartition(windows: mx.array, window_size: int, pad_hw: tuple, hw: tuple):
    """Reverse window_partition."""
    Hp, Wp = pad_hw
    H, W = hw
    B = windows.shape[0] // (Hp * Wp // window_size // window_size)
    x = windows.reshape(B, Hp // window_size, Wp // window_size, window_size, window_size, -1)
    x = x.transpose(0, 1, 3, 2, 4, 5).reshape(B, Hp, Wp, -1)
    if Hp > H or Wp > W:
        x = x[:, :H, :W, :]
    return x


def get_activation_fn(activation: str):
    if activation == "relu":
        return nn.ReLU()
    if activation == "gelu":
        return nn.GELU()
    raise RuntimeError(f"activation should be relu/gelu, not {activation}.")
