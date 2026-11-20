import numpy as np


def _rotation_matrix(
    pitch: np.ndarray, yaw: np.ndarray, roll: np.ndarray
) -> np.ndarray:
    pitch, yaw, roll = [
        np.asarray(value, dtype=np.float32).reshape(-1) * np.pi / 180
        for value in (pitch, yaw, roll)
    ]
    result = []
    for pitch_value, yaw_value, roll_value in zip(pitch, yaw, roll, strict=True):
        sin_p, cos_p = (np.sin(pitch_value), np.cos(pitch_value))
        sin_y, cos_y = (np.sin(yaw_value), np.cos(yaw_value))
        sin_r, cos_r = (np.sin(roll_value), np.cos(roll_value))
        rot_x = np.array(
            ((1, 0, 0), (0, cos_p, -sin_p), (0, sin_p, cos_p)), dtype=np.float32
        )
        rot_y = np.array(
            ((cos_y, 0, sin_y), (0, 1, 0), (-sin_y, 0, cos_y)), dtype=np.float32
        )
        rot_z = np.array(
            ((cos_r, -sin_r, 0), (sin_r, cos_r, 0), (0, 0, 1)), dtype=np.float32
        )
        result.append((rot_z @ rot_y @ rot_x).T)
    return np.stack(result)
