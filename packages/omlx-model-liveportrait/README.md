# MLX LivePortrait

Native Apple-Silicon LivePortrait animation for AI2Apps. The Package accepts
one reference portrait and one driving video, transfers pose and expression,
and produces an H.264 MP4. Driving-video audio can be preserved without
re-encoding.

The default `quality` profile uses FP32. The opt-in `fast` profile uses BF16.
FP16 is intentionally rejected because validation found non-finite motion
values. Processing is local and the Package has no outbound network access.

This is portrait animation, not identity-model face swapping. It does not ship
InsightFace checkpoints.
