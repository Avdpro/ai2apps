"""Experimental H3 continuation timing; not yet advertised as a provider capability.

All intervals are half-open. The original soundtrack is muxed once; these
windows only describe conditioning audio and the video frames to retain.
"""

from dataclasses import dataclass


FPS = 24
AUDIO_LATENT_HZ = 40
CONDITIONING_RATE = 32000


def _positive_integer(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _shared_grid(frames: int) -> bool:
    return frames >= 39 and (frames - 39) % 51 == 0


def sample_boundary(frame: int, sample_rate: int) -> int:
    """Round an absolute frame boundary to nearest sample, ties upward."""
    _positive_integer(sample_rate, "sample_rate")
    if type(frame) is not int or frame < 0:
        raise ValueError("frame must be a nonnegative integer")
    return (2 * frame * sample_rate + FPS) // (2 * FPS)


@dataclass(frozen=True)
class H3Window:
    index: int
    start_frame: int
    generate_frames: int
    context_frames: int
    keep_frames: int

    @property
    def output_start(self) -> int:
        return self.start_frame + self.context_frames

    @property
    def output_end(self) -> int:
        return self.output_start + self.keep_frames

    @property
    def audio_latents(self) -> int:
        return self.generate_frames * AUDIO_LATENT_HZ // FPS

    def conditioning_span(self, total_samples: int) -> tuple[int, int, int]:
        """Return start/end in globally resampled 32 kHz PCM, plus right padding.

        Resample the complete source once before slicing. Only the true source
        endpoint may be padded; interior windows use actual audio lookahead.
        """
        _positive_integer(total_samples, "total_samples")
        start = sample_boundary(self.start_frame, CONDITIONING_RATE)
        end = start + self.audio_latents * 800
        if start >= total_samples:
            raise ValueError("window starts beyond the source audio")
        return start, min(end, total_samples), max(0, end - total_samples)


def plan_h3_windows(
    total_samples: int,
    sample_rate: int,
    *,
    window_frames: int = 192,
    context_frames: int = 39,
) -> tuple[H3Window, ...]:
    """Plan exact frame coverage without accumulating per-clip rounding errors.

    Window and context sizes must land on both the H3 VAE grid and the audio
    grid. This initial prototype accepts up to 345 frames (14.375 seconds).
    The last window shrinks on the same grid. The final video covers the audio
    with less than one frame of overhang; no speech is stretched or truncated.
    """
    _positive_integer(total_samples, "total_samples")
    _positive_integer(sample_rate, "sample_rate")
    for value, name in ((window_frames, "window_frames"), (context_frames, "context_frames")):
        _positive_integer(value, name)
        if not _shared_grid(value):
            raise ValueError(f"{name} must be 39 + 51*k")
    if window_frames > 345 or context_frames >= window_frames:
        raise ValueError("require context_frames < window_frames <= 345")
    total_frames = (total_samples * FPS + sample_rate - 1) // sample_rate
    result = []
    emitted = 0
    while emitted < total_frames:
        context = context_frames if result else 0
        wanted = min(window_frames, context + total_frames - emitted)
        target = 39 + max(0, (wanted - 39 + 50) // 51) * 51
        keep = min(target - context, total_frames - emitted)
        result.append(H3Window(len(result), emitted - context, target, context, keep))
        emitted += keep
    return tuple(result)
