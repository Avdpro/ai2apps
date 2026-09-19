"""MLX-native LivePortrait component orchestration."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .assets import resolve_model
from .media import resize_bgr
from .onnx_mlx import MLXOnnxGraph


class MLXLivePortrait:
    def __init__(self, model_root: str | Path):
        root = Path(model_root)
        self.appearance_graph = MLXOnnxGraph(
            resolve_model(
                root,
                "appearance_feature_extractor.onnx",
                aliases=("liveportrait_appearance_feature_extractor.onnx",),
            )
        )
        self.motion_graph = MLXOnnxGraph(
            resolve_model(
                root,
                "motion_extractor.onnx",
                aliases=("liveportrait_motion_extractor.onnx",),
            )
        )
        self.stitch_graph = MLXOnnxGraph(
            resolve_model(
                root,
                "stitching.onnx",
                aliases=("liveportrait_stitching.onnx",),
            )
        )
        self.eye_graph = MLXOnnxGraph(
            resolve_model(
                root,
                "stitching_eye.onnx",
                aliases=("liveportrait_stitching_eye.onnx",),
            )
        )
        self.lip_graph = MLXOnnxGraph(
            resolve_model(
                root,
                "stitching_lip.onnx",
                aliases=("liveportrait_stitching_lip.onnx",),
            )
        )
        self.warp_graph = MLXOnnxGraph(
            resolve_model(
                root,
                "warping_spade.onnx",
                aliases=("liveportrait_warping_spade.onnx",),
            )
        )
        self.mx = self.motion_graph.mx

    @staticmethod
    def _input(image_bgr: np.ndarray) -> np.ndarray:
        resized = resize_bgr(image_bgr, (256, 256))
        return resized[..., ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0

    def appearance(self, image_bgr: np.ndarray):
        outputs = self.appearance_graph({"img": self._input(image_bgr)})
        self.appearance_graph.evaluate(outputs)
        return outputs[0]

    def motion(self, image_bgr: np.ndarray) -> dict[str, object]:
        outputs = self.motion_graph({"img": self._input(image_bgr)})
        self.motion_graph.evaluate(outputs)
        result = dict(zip(self.motion_graph.outputs, outputs, strict=True))
        for name in ("pitch", "yaw", "roll"):
            result[name] = self._headpose_degree(result[name])
        result["kp"] = result["kp"].reshape(1, 21, 3)
        result["exp"] = result["exp"].reshape(1, 21, 3)
        return result

    def transform_keypoints(self, info: dict[str, object]):
        mx = self.mx
        rotation = self._rotation_matrix(info["pitch"], info["yaw"], info["roll"])
        keypoints = info["kp"] @ rotation + info["exp"]
        keypoints = keypoints * info["scale"][..., None]
        translation = mx.concatenate(
            (info["t"][:, :2], mx.zeros((info["t"].shape[0], 1))), axis=1
        )
        return keypoints + translation[:, None, :]

    def stitch(self, source, driving):
        default = self._stitch_delta(source, source)
        current = self._stitch_delta(source, driving)
        expression_delta = (current[:, :63] - default[:, :63]).reshape(1, 21, 3)
        xy_delta = current[:, 63:65] - default[:, 63:65]
        translation = self.mx.concatenate(
            (xy_delta, self.mx.zeros((xy_delta.shape[0], 1))), axis=1
        )
        return driving + expression_delta + translation[:, None, :]

    def retarget_eye(self, source, close_ratio):
        features = self.mx.concatenate((source.reshape(1, -1), close_ratio), axis=1)
        outputs = self.eye_graph({"input": features})
        self.eye_graph.evaluate(outputs)
        return outputs[0].reshape(1, 21, 3)

    def retarget_lip(self, source, close_ratio):
        features = self.mx.concatenate((source.reshape(1, -1), close_ratio), axis=1)
        outputs = self.lip_graph({"input": features})
        self.lip_graph.evaluate(outputs)
        return outputs[0].reshape(1, 21, 3)

    def warp_decode(self, feature, source, driving) -> np.ndarray:
        outputs = self.warp_graph(
            {"feature_3d": feature, "kp_source": source, "kp_driving": driving}
        )
        self.warp_graph.evaluate(outputs)
        rgb = np.asarray(outputs[0], dtype=np.float32)[0].transpose(1, 2, 0)
        return np.clip(rgb[..., ::-1] * 255.0, 0, 255).astype(np.uint8)

    def reenact(self, source_bgr: np.ndarray, driving_bgr: np.ndarray) -> np.ndarray:
        source_state = self.prepare_source(source_bgr)
        driving_state = self.prepare_driving(driving_bgr)
        return self.drive_prepared(source_state, driving_state)

    def prepare_source(self, source_bgr: np.ndarray) -> dict[str, object]:
        """Extract source appearance and geometry once for image/video driving."""

        feature = self.appearance(source_bgr)
        info = self.motion(source_bgr)
        return {
            "feature": feature,
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
        """Render one driving frame using absolute or anchor-relative motion."""

        source_info = source_state["info"]
        source_keypoints = source_state["keypoints"]
        driving_info = driving_state["info"]
        if driving_anchor is None:
            driving_keypoints = self.transform_keypoints(driving_info)
        else:
            anchor_info = driving_anchor["info"]
            rotation = (
                driving_state["rotation"]
                @ self.mx.transpose(driving_anchor["rotation"], (0, 2, 1))
                @ source_state["rotation"]
            )
            expression = source_info["exp"] + (driving_info["exp"] - anchor_info["exp"])
            scale = source_info["scale"] * (
                driving_info["scale"] / anchor_info["scale"]
            )
            translation = source_info["t"] + (driving_info["t"] - anchor_info["t"])
            translation = self.mx.concatenate(
                (translation[:, :2], self.mx.zeros((translation.shape[0], 1))), axis=1
            )
            driving_keypoints = scale[..., None] * (
                source_info["kp"] @ rotation + expression
            )
            driving_keypoints = driving_keypoints + translation[:, None, :]
        driving_keypoints = self.stitch(source_keypoints, driving_keypoints)
        driving_keypoints = source_keypoints + (
            driving_keypoints - source_keypoints
        ) * float(multiplier)
        return self.warp_decode(
            source_state["feature"], source_keypoints, driving_keypoints
        )

    def _stitch_delta(self, source, driving):
        features = self.mx.concatenate(
            (source.reshape(1, -1), driving.reshape(1, -1)), axis=1
        )
        outputs = self.stitch_graph({"input": features})
        self.stitch_graph.evaluate(outputs)
        return outputs[0]

    def _headpose_degree(self, prediction):
        indices = self.mx.arange(66, dtype=self.mx.float32)
        return (
            self.mx.sum(self.mx.softmax(prediction, axis=1) * indices, axis=1) * 3
            - 97.5
        )

    def _rotation_matrix(self, pitch, yaw, roll):
        mx = self.mx
        pitch, yaw, roll = [
            value.reshape(-1, 1) * np.pi / 180 for value in (pitch, yaw, roll)
        ]
        ones = mx.ones_like(pitch)
        zeros = mx.zeros_like(pitch)
        rot_x = mx.concatenate(
            (
                ones,
                zeros,
                zeros,
                zeros,
                mx.cos(pitch),
                -mx.sin(pitch),
                zeros,
                mx.sin(pitch),
                mx.cos(pitch),
            ),
            axis=1,
        ).reshape(-1, 3, 3)
        rot_y = mx.concatenate(
            (
                mx.cos(yaw),
                zeros,
                mx.sin(yaw),
                zeros,
                ones,
                zeros,
                -mx.sin(yaw),
                zeros,
                mx.cos(yaw),
            ),
            axis=1,
        ).reshape(-1, 3, 3)
        rot_z = mx.concatenate(
            (
                mx.cos(roll),
                -mx.sin(roll),
                zeros,
                mx.sin(roll),
                mx.cos(roll),
                zeros,
                zeros,
                zeros,
                ones,
            ),
            axis=1,
        ).reshape(-1, 3, 3)
        return mx.transpose(rot_z @ rot_y @ rot_x, (0, 2, 1))
