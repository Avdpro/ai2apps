"""Lightweight temporal association and landmark smoothing for face swaps."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .detector import FaceDetection


@dataclass
class FaceTrack:
    track_id: int
    bbox: np.ndarray
    landmarks: np.ndarray
    score: float
    age: int = 1
    missed: int = 0

    def detection(self) -> FaceDetection:
        return FaceDetection(self.bbox.copy(), self.score, self.landmarks.copy())


class TemporalFaceTracker:
    """Greedy IoU tracker with EMA geometry for stable face alignment."""

    def __init__(
        self,
        *,
        iou_threshold: float = 0.2,
        smoothing: float = 0.65,
        max_missed: int = 3,
    ):
        self.iou_threshold = iou_threshold
        self.smoothing = smoothing
        self.max_missed = max_missed
        self._next_id = 1
        self._tracks: dict[int, FaceTrack] = {}

    @property
    def tracks(self) -> tuple[FaceTrack, ...]:
        return tuple(sorted(self._tracks.values(), key=lambda item: item.track_id))

    def update(self, detections: list[FaceDetection]) -> tuple[FaceTrack, ...]:
        unmatched_tracks = set(self._tracks)
        unmatched_detections = set(range(len(detections)))
        pairs: list[tuple[float, int, int]] = []
        for track_id, track in self._tracks.items():
            for detection_index, detection in enumerate(detections):
                pairs.append(
                    (_iou(track.bbox, detection.bbox), track_id, detection_index)
                )
        for overlap, track_id, detection_index in sorted(pairs, reverse=True):
            if overlap < self.iou_threshold:
                break
            if (
                track_id not in unmatched_tracks
                or detection_index not in unmatched_detections
            ):
                continue
            self._merge(self._tracks[track_id], detections[detection_index])
            unmatched_tracks.remove(track_id)
            unmatched_detections.remove(detection_index)
        for track_id in unmatched_tracks:
            self._tracks[track_id].missed += 1
            self._tracks[track_id].age += 1
        for detection_index in unmatched_detections:
            detection = detections[detection_index]
            self._tracks[self._next_id] = FaceTrack(
                track_id=self._next_id,
                bbox=detection.bbox.copy(),
                landmarks=detection.landmarks.copy(),
                score=detection.score,
            )
            self._next_id += 1
        self._tracks = {
            key: value
            for key, value in self._tracks.items()
            if value.missed <= self.max_missed
        }
        return self.tracks

    def _merge(self, track: FaceTrack, detection: FaceDetection) -> None:
        previous = self.smoothing
        current = 1.0 - previous
        track.bbox = track.bbox * previous + detection.bbox * current
        track.landmarks = track.landmarks * previous + detection.landmarks * current
        track.score = detection.score
        track.age += 1
        track.missed = 0


def _iou(left: np.ndarray, right: np.ndarray) -> float:
    x1 = max(float(left[0]), float(right[0]))
    y1 = max(float(left[1]), float(right[1]))
    x2 = min(float(left[2]), float(right[2]))
    y2 = min(float(left[3]), float(right[3]))
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = max(0.0, float(left[2] - left[0])) * max(0.0, float(left[3] - left[1]))
    right_area = max(0.0, float(right[2] - right[0])) * max(
        0.0, float(right[3] - right[1])
    )
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0
