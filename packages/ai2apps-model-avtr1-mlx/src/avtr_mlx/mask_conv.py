"""Pure MLX mask convolution lowering; adapted from LivePortrait (MIT)."""

import mlx.core as mx


def pack_mask_conv3d_weight_2d(weight: mx.array) -> mx.array:
    """Pack Conv3d weights as a single Conv2d kernel over depth-stacked channels."""
    oc, kd, kh, kw, ic = weight.shape
    return mx.contiguous(
        mx.transpose(weight, (0, 2, 3, 1, 4)).reshape(oc, kh, kw, kd * ic)
    )


def mask_conv3d_packed_2d(
    x: mx.array,
    weight_packed: mx.array,
    bias: mx.array,
    *,
    depth_kernel: int,
    padding: int,
) -> mx.array:
    """Conv3d mask head as one Conv2d over depth-stacked channels."""
    n, d, h, w, ic = x.shape
    pad_d = depth_kernel // 2
    x_padded = mx.pad(x, [(0, 0), (pad_d, pad_d), (0, 0), (0, 0), (0, 0)])
    x_packed = mx.concatenate(
        [x_padded[:, kd : kd + d, :, :, :] for kd in range(depth_kernel)],
        axis=-1,
    )
    y = mx.conv2d(
        x_packed.reshape(n * d, h, w, depth_kernel * ic), weight_packed, padding=padding
    )
    return y.reshape(n, d, h, w, weight_packed.shape[0]) + bias
