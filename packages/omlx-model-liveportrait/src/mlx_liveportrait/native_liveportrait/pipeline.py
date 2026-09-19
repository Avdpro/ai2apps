"""Product-facing orchestration for the specialized native MLX models."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..media import resize_bgr
from .mlx_appearance_feature_extractor_model import (
    MlxAppearanceFeatureExtractorModel,
)
from .mlx_motion_extractor_model import MlxMotionExtractorModel
from .mlx_stitching_model import MlxStitchingModel
from .mlx_warping_spade_model import MlxWarpingSpadeModel


class NativeMLXLivePortrait:
    """LivePortrait with directly converted official weights and native layers."""

    def __init__(self, model_root: str | Path, *, dtype: str = "fp32"):
        if dtype == "fp16":
            raise ValueError("FP16 motion is disabled because it produces non-finite values")
        root = Path(model_root)
        options = {"dtype": dtype}
        self.appearance_model = MlxAppearanceFeatureExtractorModel(
            model_path=str(root / "appearance_feature_extractor.npz"), **options
        )
        self.motion_model = MlxMotionExtractorModel(
            model_path=str(root / "motion_extractor.npz"), **options
        )
        self.warp_model = MlxWarpingSpadeModel(
            model_path=[
                str(root / "warping_module.npz"),
                str(root / "spade_generator.npz"),
            ],
            **options,
        )
        self.stitch_model = MlxStitchingModel(
            model_path=str(root / "stitching.npz"), **options
        )
        self.eye_model = MlxStitchingModel(
            model_path=str(root / "stitching_eye.npz"), **options
        )
        self.lip_model = MlxStitchingModel(
            model_path=str(root / "stitching_lip.npz"), **options
        )

    @staticmethod
    def _rgb256(image_bgr: np.ndarray) -> np.ndarray:
        return np.ascontiguousarray(resize_bgr(image_bgr, (256, 256))[..., ::-1])

    def appearance(self, image_bgr: np.ndarray) -> np.ndarray:
        return self.appearance_model.predict(self._rgb256(image_bgr))

    def motion(self, image_bgr: np.ndarray) -> dict[str, np.ndarray]:
        values = self.motion_model.predict(self._rgb256(image_bgr))
        return dict(
            zip(("pitch", "yaw", "roll", "t", "exp", "scale", "kp"), values, strict=True)
        )

    @staticmethod
    def _rotation_matrix(
        pitch: np.ndarray, yaw: np.ndarray, roll: np.ndarray
    ) -> np.ndarray:
        pitch, yaw, roll = [
            np.asarray(value, dtype=np.float32).reshape(-1) * np.pi / 180
            for value in (pitch, yaw, roll)
        ]
        result = []
        for pitch_value, yaw_value, roll_value in zip(
            pitch, yaw, roll, strict=True
        ):
            sin_p, cos_p = np.sin(pitch_value), np.cos(pitch_value)
            sin_y, cos_y = np.sin(yaw_value), np.cos(yaw_value)
            sin_r, cos_r = np.sin(roll_value), np.cos(roll_value)
            rot_x = np.array(
                ((1, 0, 0), (0, cos_p, -sin_p), (0, sin_p, cos_p)),
                dtype=np.float32,
            )
            rot_y = np.array(
                ((cos_y, 0, sin_y), (0, 1, 0), (-sin_y, 0, cos_y)),
                dtype=np.float32,
            )
            rot_z = np.array(
                ((cos_r, -sin_r, 0), (sin_r, cos_r, 0), (0, 0, 1)),
                dtype=np.float32,
            )
            result.append((rot_z @ rot_y @ rot_x).T)
        return np.stack(result)

    def transform_keypoints(self, info: dict[str, np.ndarray]) -> np.ndarray:
        rotation = self._rotation_matrix(info["pitch"], info["yaw"], info["roll"])
        keypoints = info["kp"] @ rotation + info["exp"]
        keypoints *= info["scale"][..., None]
        translation = np.concatenate(
            (info["t"][:, :2], np.zeros((info["t"].shape[0], 1), np.float32)),
            axis=1,
        )
        return keypoints + translation[:, None, :]

    def _stitch_delta(self, source: np.ndarray, driving: np.ndarray) -> np.ndarray:
        features = np.concatenate((source.reshape(1, -1), driving.reshape(1, -1)), axis=1)
        return self.stitch_model.predict(features)

    def stitch(self, source: np.ndarray, driving: np.ndarray) -> np.ndarray:
        default = self._stitch_delta(source, source)
        current = self._stitch_delta(source, driving)
        expression_delta = (current[:, :63] - default[:, :63]).reshape(1, 21, 3)
        xy_delta = current[:, 63:65] - default[:, 63:65]
        translation = np.concatenate(
            (xy_delta, np.zeros((xy_delta.shape[0], 1), np.float32)), axis=1
        )
        return driving + expression_delta + translation[:, None, :]

    def prepare_source(self, source_bgr: np.ndarray) -> dict[str, object]:
        info = self.motion(source_bgr)
        return {
            "feature": self.appearance(source_bgr),
            "info": info,
            "rotation": self._rotation_matrix(info["pitch"], info["yaw"], info["roll"]),
            "keypoints": self.transform_keypoints(info),
        }

    def prepare_driving(self, driving_bgr: np.ndarray) -> dict[str, object]:
        info = self.motion(driving_bgr)
        return {
            "info": info,
            "rotation": self._rotation_matrix(info["pitch"], info["yaw"], info["roll"]),
        }

    def drive_prepared(
        self,
        source_state: dict[str, object],
        driving_state: dict[str, object],
        *,
        driving_anchor: dict[str, object] | None = None,
        multiplier: float = 1.0,
    ) -> np.ndarray:
        source_info = source_state["info"]
        source_keypoints = source_state["keypoints"]
        driving_info = driving_state["info"]
        if driving_anchor is None:
            driving_keypoints = self.transform_keypoints(driving_info)
        else:
            anchor_info = driving_anchor["info"]
            rotation = (
                driving_state["rotation"]
                @ np.transpose(driving_anchor["rotation"], (0, 2, 1))
                @ source_state["rotation"]
            )
            expression = source_info["exp"] + (
                driving_info["exp"] - anchor_info["exp"]
            )
            scale = source_info["scale"] * (
                driving_info["scale"] / anchor_info["scale"]
            )
            translation = source_info["t"] + (
                driving_info["t"] - anchor_info["t"]
            )
            translation = np.concatenate(
                (
                    translation[:, :2],
                    np.zeros((translation.shape[0], 1), np.float32),
                ),
                axis=1,
            )
            driving_keypoints = scale[..., None] * (
                source_info["kp"] @ rotation + expression
            )
            driving_keypoints += translation[:, None, :]
        driving_keypoints = self.stitch(source_keypoints, driving_keypoints)
        driving_keypoints = source_keypoints + (
            driving_keypoints - source_keypoints
        ) * float(multiplier)
        rgb = self.warp_model.predict(
            source_state["feature"],
            source_keypoints,
            driving_keypoints,
            return_numpy=True,
            return_uint8=True,
        )
        return np.ascontiguousarray(rgb[..., ::-1])

    def reenact(self, source_bgr: np.ndarray, driving_bgr: np.ndarray) -> np.ndarray:
        return self.drive_prepared(
            self.prepare_source(source_bgr), self.prepare_driving(driving_bgr)
        )
