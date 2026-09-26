# CAMPPlus speaker embedding (dense TDNN) — MLX port of windextts/models/campplus.py.
# [B,T,80] fbank -> [B,192]. Eval-only (BatchNorm uses running stats). Module
# attribute names mirror the torch ckpt keys 1:1 (xvector.tdnn.nonlinear.*,
# head.layer1.0.shortcut.*, ...) so the converter's generic remap applies.
import mlx.core as mx
import mlx.nn as nn

from omlx.vendor.indextts25 import ops
from omlx.vendor.indextts25.ops import Seq


def _nonlin(config_str, channels):
    # modules named exactly like torch get_nonlinear ("batchnorm","relu")
    items = {}
    for name in config_str.split("-"):
        if name == "relu":
            items[name] = nn.ReLU()
        elif name in ("batchnorm", "batchnorm_"):
            items["batchnorm"] = BN1d(channels, affine=(name == "batchnorm"))
        else:
            raise ValueError(f"Unexpected module ({name}).")
    return Seq(items)


def _c1(layer, x):  # torch [B,C,T] -> mlx Conv1d [B,T,C] -> [B,O,T]
    return layer(x.transpose(0, 2, 1)).transpose(0, 2, 1)


def _c2(layer, x):  # torch [B,C,F,T] -> mlx Conv2d [B,kh=F,kw=T,C] -> torch [B,O,F',T']
    return layer(x.transpose(0, 2, 3, 1)).transpose(0, 3, 1, 2)


class BN1d(nn.Module):  # eval-only batchnorm over axis 1 (torch NCL layout)
    def __init__(self, c, affine=True):
        super().__init__()
        self.affine = affine
        if affine:
            self.weight = mx.ones((c,))
            self.bias = mx.zeros((c,))
        self.running_mean = mx.zeros((c,))
        self.running_var = mx.ones((c,))

    def __call__(self, x):
        shp = (1, -1) + (1,) * (x.ndim - 2)
        m, v = self.running_mean.reshape(shp), self.running_var.reshape(shp)
        y = (x - m) / mx.sqrt(v + 1e-5)
        if self.affine:
            y = y * self.weight.reshape(shp) + self.bias.reshape(shp)
        return y


class StatsPool(nn.Module):
    def __call__(self, x):  # [B,C,T] -> [B,C*2]
        return mx.concatenate([x.mean(-1), mx.sqrt(mx.var(x, axis=-1, ddof=1))], -1)


class TDNNLayer(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride=1, padding=0, dilation=1, bias=False, config_str="batchnorm-relu"):
        super().__init__()
        if padding < 0:
            padding = (kernel_size - 1) // 2 * dilation  # same-padding contract
        self.linear = nn.Conv1d(in_channels, out_channels, kernel_size, stride=stride, padding=padding, dilation=dilation, bias=bias)
        self.nonlinear = _nonlin(config_str, out_channels)

    def __call__(self, x):
        return self.nonlinear(_c1(self.linear, x))


class CAMLayer(nn.Module):
    def __init__(self, bn_channels, out_channels, kernel_size, stride, padding, dilation, bias, reduction=2):
        super().__init__()
        self.linear_local = nn.Conv1d(bn_channels, out_channels, kernel_size, stride=stride, padding=padding, dilation=dilation, bias=bias)
        self.linear1 = nn.Conv1d(bn_channels, bn_channels // reduction, 1)
        self.linear2 = nn.Conv1d(bn_channels // reduction, out_channels, 1)

    def __call__(self, x):
        y = _c1(self.linear_local, x)
        seg = ops.avg_pool_expand(x, 100)  # avg_pool1d(k=100, ceil) expanded back
        m = mx.sigmoid(_c1(self.linear2, mx.maximum(_c1(self.linear1, x.mean(-1, keepdims=True) + seg), 0)))
        return y * m


class DenseBlock(nn.Module):  # CAMDenseTDNNBlock: tdnnd layers CONCAT their outputs
    def __init__(self, items):
        super().__init__()
        self._order = list(items)
        for n, md in items.items():
            setattr(self, n, md)  # attrs keep ckpt keys (block1.tdnnd1...)

    def __call__(self, x):
        for n in self._order:
            x = mx.concatenate([x, getattr(self, n)(x)], 1)
        return x

    def __len__(self):
        return len(self._order)

    def __getitem__(self, i):
        return getattr(self, self._order[i])


class CAMDenseTDNNLayer(nn.Module):
    def __init__(self, in_channels, out_channels, bn_channels, kernel_size, stride=1, dilation=1, bias=False, config_str="batchnorm-relu"):
        super().__init__()
        padding = (kernel_size - 1) // 2 * dilation
        self.nonlinear1 = _nonlin(config_str, in_channels)
        self.linear1 = nn.Conv1d(in_channels, bn_channels, 1, bias=False)
        self.nonlinear2 = _nonlin(config_str, bn_channels)
        self.cam_layer = CAMLayer(bn_channels, out_channels, kernel_size, stride, padding, dilation, bias)

    def __call__(self, x):
        return self.cam_layer(self.nonlinear2(_c1(self.linear1, self.nonlinear1(x))))


class BasicResBlock(nn.Module):
    def __init__(self, in_planes, planes, stride=1):
        super().__init__()
        self.conv1 = nn.Conv2d(in_planes, planes, 3, stride=(stride, 1), padding=1, bias=False)
        self.bn1 = BN1d(planes)
        self.conv2 = nn.Conv2d(planes, planes, 3, padding=1, bias=False)
        self.bn2 = BN1d(planes)
        self.shortcut = (Seq({"0": nn.Conv2d(in_planes, planes, 1, stride=(stride, 1), bias=False),
                              "1": BN1d(planes)})
                         if stride != 1 or in_planes != planes else Seq({}))

    def __call__(self, x):
        y = mx.maximum(self.bn1(_c2(self.conv1, x)), 0)
        y = self.bn2(_c2(self.conv2, y))
        if len(self.shortcut):
            sx = _c2(self.shortcut[0], x)
            y = y + (self.shortcut[1](sx) if len(self.shortcut) > 1 else sx)
        else:
            y = y + x
        return mx.maximum(y, 0)


class FCM(nn.Module):
    # 2x stride-2 res blocks on the freq axis, then squeeze conv (stride 2x1)
    def __init__(self, m_channels=32, feat_dim=80):
        super().__init__()
        self.conv1 = nn.Conv2d(1, m_channels, 3, padding=1, bias=False)
        self.bn1 = BN1d(m_channels)
        self.layer1 = Seq({"0": BasicResBlock(m_channels, m_channels, stride=2), "1": BasicResBlock(m_channels, m_channels)})
        self.layer2 = Seq({"0": BasicResBlock(m_channels, m_channels, stride=2), "1": BasicResBlock(m_channels, m_channels)})
        self.conv2 = nn.Conv2d(m_channels, m_channels, 3, stride=(2, 1), padding=1, bias=False)
        self.bn2 = BN1d(m_channels)
        self.out_channels = m_channels * (feat_dim // 8)

    def __call__(self, x):  # x [B,F,T] -> [B, C*F, T]
        x = x[:, None]
        x = mx.maximum(self.bn1(_c2(self.conv1, x)), 0)
        x = self.layer2(self.layer1(x))
        x = mx.maximum(self.bn2(_c2(self.conv2, x)), 0)
        return x.reshape(x.shape[0], -1, x.shape[-1])


class TransitLayer(nn.Module):
    def __init__(self, in_channels, out_channels, bias=True, config_str="batchnorm-relu"):
        super().__init__()
        self.nonlinear = _nonlin(config_str, in_channels)
        self.linear = nn.Conv1d(in_channels, out_channels, 1, bias=bias)

    def __call__(self, x):
        return _c1(self.linear, self.nonlinear(x))


class DenseLayer(nn.Module):
    def __init__(self, in_channels, out_channels, bias=False, config_str="batchnorm-relu"):
        super().__init__()
        self.linear = nn.Conv1d(in_channels, out_channels, 1, bias=bias)
        self.nonlinear = _nonlin(config_str, out_channels)

    def __call__(self, x):  # [B,C] or [B,C,T]
        is2d = x.ndim == 2
        if is2d:
            x = x[..., None]
        y = self.nonlinear(_c1(self.linear, x))
        return y[..., 0] if is2d else y


class CAMPPlus(nn.Module):
    def __init__(self, feat_dim=80, embedding_size=192, growth_rate=32, bn_size=4,
                 init_channels=128, config_str="batchnorm-relu"):
        super().__init__()
        self.head = FCM(feat_dim=feat_dim)
        channels = self.head.out_channels
        xv = {"tdnn": TDNNLayer(channels, init_channels, 5, stride=2, padding=-1, config_str=config_str)}
        channels = init_channels
        for i, (num_layers, kernel_size, dilation) in enumerate(zip((12, 24, 16), (3, 3, 3), (1, 2, 2))):
            xv[f"block{i + 1}"] = DenseBlock({f"tdnnd{j + 1}": CAMDenseTDNNLayer(
                channels + j * growth_rate, growth_rate, bn_size * growth_rate,
                kernel_size, dilation=dilation, config_str=config_str) for j in range(num_layers)})
            channels += num_layers * growth_rate
            xv[f"transit{i + 1}"] = TransitLayer(channels, channels // 2, bias=False, config_str=config_str)
            channels //= 2
        xv["out_nonlinear"] = _nonlin(config_str, channels)
        xv["stats"] = StatsPool()
        xv["dense"] = DenseLayer(channels * 2, embedding_size, config_str="batchnorm_")
        self.xvector = Seq(xv)

    def __call__(self, x):  # [B,T,F] -> [B,192]
        x = mx.transpose(x, (0, 2, 1))  # (B,T,F) => (B,F,T)
        return self.xvector(self.head(x))
