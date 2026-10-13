"""Single-view camera geometry, independent of Torch and OpenCV.

Coordinates use x right, y down, z forward. A single photograph cannot reveal
occluded surfaces; the rasterizer intentionally returns holes, not invented data.
"""

import numpy as np


def camera_from_encoding(encoding, height=512, width=512):
    p = np.asarray(encoding, dtype=np.float32)
    if p.shape[-1] != 9 or not np.isfinite(p).all():
        raise ValueError("Expected finite nine-component camera encoding")
    q = p[..., 3:7]
    norm = np.sum(q * q, axis=-1)
    if np.any(norm < 1e-12):
        raise ValueError("Degenerate camera quaternion")
    i, j, k, r = np.moveaxis(q, -1, 0)
    s = 2 / norm
    rotation = np.stack(
        (
            1 - s * (j * j + k * k),
            s * (i * j - k * r),
            s * (i * k + j * r),
            s * (i * j + k * r),
            1 - s * (i * i + k * k),
            s * (j * k - i * r),
            s * (i * k - j * r),
            s * (j * k + i * r),
            1 - s * (i * i + j * j),
        ),
        axis=-1,
    ).reshape(p.shape[:-1] + (3, 3))
    fov = p[..., 7:9]
    if np.any(fov <= 0) or np.any(fov >= np.pi):
        raise ValueError("Invalid camera field of view")
    intrinsic = np.zeros(p.shape[:-1] + (3, 3), dtype=np.float32)
    intrinsic[..., 0, 0] = (width / 2) / np.tan(fov[..., 1] / 2)
    intrinsic[..., 1, 1] = (height / 2) / np.tan(fov[..., 0] / 2)
    intrinsic[..., 0, 2] = width / 2
    intrinsic[..., 1, 2] = height / 2
    intrinsic[..., 2, 2] = 1
    return np.concatenate((rotation, p[..., :3, None]), axis=-1), intrinsic


def point_cloud(depth, intrinsic):
    z = np.asarray(depth, dtype=np.float32)
    K = np.asarray(intrinsic, dtype=np.float32)
    if z.ndim != 2 or K.shape != (3, 3) or K[0, 0] <= 0 or K[1, 1] <= 0:
        raise ValueError("Invalid depth/intrinsics")
    y, x = np.indices(z.shape, dtype=np.float32)
    return np.stack(
        ((x - K[0, 2]) * z / K[0, 0], (y - K[1, 2]) * z / K[1, 1], z), axis=-1
    )


def orbit_pose(pivot, yaw=0.0, pitch=0.0, radius=1.0, roll=0.0):
    pivot = np.asarray(pivot, dtype=np.float64)
    if (
        pivot.shape != (3,)
        or not np.isfinite(pivot).all()
        or pivot[2] <= 0
        or radius <= 0
    ):
        raise ValueError("Invalid orbit pivot/radius")
    a, b = np.deg2rad([yaw, pitch])
    eye = pivot + radius * pivot[2] * np.array(
        [np.sin(a) * np.cos(b), -np.sin(b), -np.cos(a) * np.cos(b)]
    )
    forward = pivot - eye
    forward /= np.linalg.norm(forward)
    right = np.cross([0, 1, 0], forward)
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    rotation = np.stack((right, down, forward))
    c,s=np.cos(np.deg2rad(roll)),np.sin(np.deg2rad(roll))
    rotation=np.array([[c,-s,0],[s,c,0],[0,0,1]]) @ rotation
    return rotation, -rotation @ eye


def render(points, colors, intrinsic, pose, size):
    """Nearest-point z buffer; return RGB and explicit valid-pixel mask."""
    height, width = size
    R, t = pose
    p = np.asarray(points).reshape(-1, 3) @ R.T + t
    c = np.asarray(colors, dtype=np.uint8).reshape(-1, 3)
    good = np.isfinite(p).all(axis=-1) & (p[:, 2] > 1e-8)
    idx = np.flatnonzero(good)
    u = np.rint(p[idx, 0] * intrinsic[0, 0] / p[idx, 2] + intrinsic[0, 2]).astype(
        np.int64
    )
    v = np.rint(p[idx, 1] * intrinsic[1, 1] / p[idx, 2] + intrinsic[1, 2]).astype(
        np.int64
    )
    inside = (u >= 0) & (u < width) & (v >= 0) & (v < height)
    idx, u, v = idx[inside], u[inside], v[inside]
    order = np.argsort(p[idx, 2], kind="stable")
    pixel = v[order] * width + u[order]
    unique, first = np.unique(pixel, return_index=True)
    rgb = np.full((height * width, 3), 96, dtype=np.uint8)
    mask = np.zeros(height * width, dtype=bool)
    rgb[unique] = c[idx[order[first]]]
    mask[unique] = True
    return rgb.reshape(height, width, 3), mask.reshape(height, width)
