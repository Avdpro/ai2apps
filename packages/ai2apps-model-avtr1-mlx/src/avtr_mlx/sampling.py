"""MLX trilinear grid sampling for AVTR-1's LivePortrait deformation path.

Matches torch.nn.functional.grid_sample for 5-D NCDHW input. Inference only.
"""

import mlx.core as mx


def grid_sample_3d(volume, grid, *, padding_mode="zeros", align_corners=False):
    if (
        volume.ndim != 5
        or grid.ndim != 5
        or grid.shape[-1] != 3
        or volume.shape[0] != grid.shape[0]
    ):
        raise ValueError("Expected NCDHW volume and NDHW3 sampling grid")
    if padding_mode not in {"zeros", "border", "reflection"}:
        raise ValueError("Unsupported padding mode")
    n, channels, depth, height, width = volume.shape
    coordinates = []
    for axis, size in enumerate((width, height, depth)):
        value = grid[..., axis].astype(mx.float32)
        value = mx.where(mx.isnan(value), -1.0, value)
        value = (
            (value + 1) * ((size - 1) / 2)
            if align_corners
            else ((value + 1) * size - 1) / 2
        )
        if padding_mode == "reflection":
            if size == 1:
                value = mx.zeros_like(value)
            else:
                low, span = (0.0, size - 1) if align_corners else (-0.5, size)
                distance = mx.abs(value - low)
                turns = mx.floor(distance / span)
                remainder = distance - turns * span
                value = (
                    mx.where(
                        (turns.astype(mx.int32) % 2) == 0, remainder, span - remainder
                    )
                    + low
                )
        if padding_mode != "zeros":
            value = mx.clip(value, 0, size - 1)
        coordinates.append(value)
    x, y, z = coordinates
    lo = [mx.floor(value).astype(mx.int32) for value in coordinates]
    fractions = [value - lower for value, lower in zip(coordinates, lo)]
    flat = volume.transpose(0, 2, 3, 4, 1).reshape(n * depth * height * width, channels)
    batch = mx.arange(n).reshape(n, 1, 1, 1) * (depth * height * width)
    out = mx.zeros((*grid.shape[:-1], channels), dtype=mx.float32)
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                ix, iy, iz = lo[0] + dx, lo[1] + dy, lo[2] + dz
                valid = (
                    (ix >= 0)
                    & (ix < width)
                    & (iy >= 0)
                    & (iy < height)
                    & (iz >= 0)
                    & (iz < depth)
                )
                index = (
                    batch
                    + mx.clip(iz, 0, depth - 1) * height * width
                    + mx.clip(iy, 0, height - 1) * width
                    + mx.clip(ix, 0, width - 1)
                )
                weight = (
                    (fractions[0] if dx else 1 - fractions[0])
                    * (fractions[1] if dy else 1 - fractions[1])
                    * (fractions[2] if dz else 1 - fractions[2])
                )
                if padding_mode == "zeros":
                    weight = weight * valid
                out = out + flat[index].astype(mx.float32) * weight[..., None]
    return out.transpose(0, 4, 1, 2, 3).astype(volume.dtype)
