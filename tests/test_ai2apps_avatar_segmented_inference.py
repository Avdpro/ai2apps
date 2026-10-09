from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace as NS
import asyncio
import av
import numpy as np
import pytest
import soundfile as sf
from ai2apps.avatar.segmented_inference import (
    invoke_segmented,
    model_identity,
    validate_video,
)
from ai2apps.avatar.segment_jobs import h3_segments
from ai2apps.avatar.segments import SCHEMA, write_packet, file_digest
from ai2apps.avatar.segment_media import save_segment


@pytest.mark.asyncio
async def test_host_runs_windows_preserves_audio_and_reuses_verified_prefix(tmp_path):
    audio = tmp_path / "source.wav"
    sf.write(audio, np.sin(np.arange(16000 * 9) * 0.03).astype(np.float32) * 0.1, 16000)
    image = tmp_path / "portrait.png"
    image.write_bytes(b"frozen-image")
    model = NS(
        id="test/avatar",
        service_key="test",
        weights={"revision": "abc"},
        metadata={},
        capabilities=("avatar_video",),
        video_capabilities={
            "avatar_segments": {
                "schema": SCHEMA,
                "planner": "h3-v1",
                "window_frames": 192,
            }
        },
    )
    package = NS(package_digest="immutable-package")
    calls = []
    timeline = h3_segments(16000 * 9, 16000)

    async def invoke(model_id, operation, payload, packet, **kwargs):
        part = payload["avatar_segment"]
        index = part["index"]
        segment = timeline[index]
        assert payload["duration"] == segment.generate_frames / 24
        calls.append(index)
        if index:
            assert (
                file_digest(kwargs["files"]["avatar_context"][1])
                == part["previous_state"]
            )
        media = tmp_path / f"clip-{index}.mp4"
        state = tmp_path / f"state-{index}.npy"
        save_segment(
            media,
            np.full(
                (segment.end_frame - segment.start_frame, 32, 32, 3),
                index * 80,
                np.uint8,
            ),
        )
        np.save(state, np.ones((1, 2), np.float32) * index)
        write_packet(
            packet,
            media,
            state,
            identity=part["identity"],
            index=index,
            start_frame=segment.start_frame,
            end_frame=segment.end_frame,
            fps=24,
            previous_state=part["previous_state"],
        )

    runtime = NS(
        package_manager=NS(packages=NS(active=lambda _: package)),
        model_invocations=NS(invoke_background_to_file=invoke),
    )
    output = tmp_path / "result.mp4"
    args = dict(
        root=tmp_path / "segments",
        task_id="test",
        frozen_model=model_identity(runtime, model),
        cancelled=lambda: False,
        progress=lambda _: None,
        admitted=lambda: None,
    )
    files = {
        "audio": ("source.wav", audio, "audio/wav"),
        "portrait": ("portrait.png", image, "image/png"),
    }
    await invoke_segmented(
        runtime, model, {"width": 32, "height": 32}, files, output, **args
    )
    assert calls == [0, 1]
    with av.open(str(output)) as media:
        assert len(media.streams.audio) == 1
        frames = list(media.decode(video=0))
        assert len(frames) == 216
        assert [f.pts * f.time_base for f in frames] == [
            Fraction(i, 24) for i in range(216)
        ]
    await invoke_segmented(
        runtime, model, {"width": 32, "height": 32}, files, output, **args
    )
    assert calls == [0, 1]
    (args["root"] / "000001.zip").write_bytes(b"corrupt")
    await invoke_segmented(
        runtime, model, {"width": 32, "height": 32}, files, output, **args
    )
    assert calls == [0, 1, 1]
    package.package_digest = "changed"
    with pytest.raises(ValueError, match="model changed"):
        await invoke_segmented(
            runtime, model, {"width": 32, "height": 32}, files, output, **args
        )


def test_media_receipt_rejects_incomplete_video(tmp_path):
    path = tmp_path / "short.mp4"
    save_segment(path, np.zeros((5, 32, 32, 3), np.uint8))
    with pytest.raises(ValueError, match="frame count"):
        validate_video(path, 6, width=32, height=32)


def test_streaming_host_mux_keeps_stereo_tail_without_aac_priming_delay(tmp_path):
    from ai2apps.avatar.segment_media import join_segments
    from scipy.signal import correlate, correlation_lags

    rate = 22050
    samples = np.zeros((61653, 2), np.float32)
    random = np.random.default_rng(13)
    for channel, start in enumerate((1200, 30000)):
        samples[start : start + 9000, channel] = (
            np.convolve(random.normal(size=9000), np.ones(7) / 7, mode="same") * 0.2
        )
    audio = tmp_path / "source.wav"
    sf.write(audio, samples, rate, subtype="PCM_16")
    clips = []
    for index, count in enumerate((34, 34)):
        clip = tmp_path / f"{index}.mp4"
        save_segment(clip, np.zeros((count, 32, 32, 3), np.uint8))
        clips.append(clip)
    target = tmp_path / "joined.mp4"
    join_segments(clips, audio, target)
    with av.open(str(target)) as media:
        stream = media.streams.audio[0]
        assert len(stream.codec_context.layout.channels) == 2
        assert (
            abs(float(stream.duration * stream.time_base) - len(samples) / rate) < 0.001
        )
        decoded = np.concatenate([f.to_ndarray() for f in media.decode(stream)], axis=1)
    for channel in (0, 1):
        corr = correlate(decoded[channel], samples[:, channel], method="fft")
        lag = correlation_lags(decoded.shape[1], len(samples))[np.argmax(corr)]
        assert abs(lag) <= 2


def test_segmented_package_requires_supported_host_feature():
    from ai2apps.packages.manager import ServicePackageManager, HOST_PACKAGE_FEATURES
    from ai2apps.packages.models import CompatibilityContext
    from ai2apps.packages import PackageError
    manager=object.__new__(ServicePackageManager)
    package=NS(manifest=NS(raw={}))
    requirement={"features":["avatar.segmented-jobs.v1"]}
    manager.compatibility=CompatibilityContext(os_name="darwin",architecture="arm64",python_version="3.11.0")
    with pytest.raises(PackageError) as error:
        manager._check_requirements(requirement,package)
    assert error.value.code=="platform_feature_missing"
    manager.compatibility=CompatibilityContext(os_name="darwin",architecture="arm64",python_version="3.11.0",features=HOST_PACKAGE_FEATURES)
    manager._check_requirements(requirement,package)
