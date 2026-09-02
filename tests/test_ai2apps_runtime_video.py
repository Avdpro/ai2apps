# SPDX-License-Identifier: Apache-2.0
"""Video codec and Runtime contract gates for the AI2Apps oMLX Runtime."""

from __future__ import annotations

import json
from pathlib import Path

import av
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "packages" / "ai2apps-runtime-omlx"


def test_runtime_manifests_are_synchronized_for_video():
    service = yaml.safe_load((RUNTIME / "service.yaml").read_text())
    package = json.loads((RUNTIME / "ai2apps.json").read_text())
    descriptor = json.loads((RUNTIME / "META" / "runtime-manifest.json").read_text())

    assert service["version"] == package["package"]["version"] == descriptor["version"] == "1.5.7"
    for capability in ("video-generation", "video-codecs", "audio-codecs", "z-image"):
        assert capability in service["capabilities"]
        assert capability in descriptor["capabilities"]


def test_runtime_source_exposes_worker_lifecycle_control_routes():
    server = (ROOT / "ai2apps" / "model_worker" / "server.py").read_text()

    assert '@app.post("/v1/control/drain")' in server
    assert '@app.post("/v1/control/resume")' in server


def test_runtime_pyav_encodes_h264_aac_mp4(tmp_path):
    av.codec.Codec("libx264", "w")
    av.codec.Codec("aac", "w")
    output = tmp_path / "runtime-video-smoke.mp4"
    with av.open(str(output), "w", format="mp4") as container:
        video = container.add_stream("libx264", rate=24)
        video.width = video.height = 32
        video.pix_fmt = "yuv420p"
        audio = container.add_stream("aac", rate=32_000)
        audio.layout = "stereo"
        for value in (0, 64, 128):
            pixels = np.full((32, 32, 3), value, dtype=np.uint8)
            for packet in video.encode(av.VideoFrame.from_ndarray(pixels, format="rgb24")):
                container.mux(packet)
        for packet in video.encode():
            container.mux(packet)
        samples = np.zeros((2, 1024), dtype=np.float32)
        frame = av.AudioFrame.from_ndarray(samples, format="fltp", layout="stereo")
        frame.sample_rate = 32_000
        for packet in audio.encode(frame):
            container.mux(packet)
        for packet in audio.encode():
            container.mux(packet)

    with av.open(str(output)) as container:
        assert container.streams.video[0].codec_context.name == "h264"
        assert container.streams.audio[0].codec_context.name == "aac"
