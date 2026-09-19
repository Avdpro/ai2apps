"""Immutable upstream references for the Seed-VC port."""

REPOSITORY = "https://github.com/Plachtaa/seed-vc"
REVISION = "51383efd921027683c89e5348211d93ff12ac2a8"
ARCHIVED_AT = "2025-11-21"

# Start with the non-F0 v1 offline model. It has the shortest path to a useful
# zero-shot reference-voice result and reuses Runtime Whisper + BigVGAN pieces.
INITIAL_MODEL = "seed-uvit-whisper-small-wavenet"
INITIAL_SAMPLE_RATE = 22_050
