# Music, Sound Effects and Song Creation

Version 0.2.0 contains three Voice Studio Mini-Apps in one App Package. Model alternatives and license confirmation use trusted ACPF profiles. Outputs, history, playback, saving and drag remain Host-owned.

Music and Sound Effects use their existing ACE-Step / Stable Audio choices. Powered by Stability AI when using Stable Audio; ACPF presents the original Stability AI and Gemma terms before weight acquisition.

Song Creation requires the Host `audio.song_generation` broker and Runtime 1.8.10 or later. It provides musical direction, sectioned lyrics, full/melody/off planning, optional editable UTF-8 ABC import, maximum length, seed, synthesis settings, draft saving, stage progress and cancellation. The maximum length is a limit, not a promise of exact output length; reaching it can truncate the ending. Output uses Voice Studio's shared Preview & Output.

Only models declaring `audio_generation.workflow: ai2apps.song-generation/v1` appear in Song Creation. Its installation entry invokes the dedicated ACPF profile. YuE2 uses the separate `ai2apps/model-yue2-mlx` Package and signed HF/ModelScope checkpoint distributions; original-license consent is required before download. Stage checkpoint/resume, partial rerender and transcription are outside this version.
