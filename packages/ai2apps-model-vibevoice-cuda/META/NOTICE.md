VibeVoice is developed by Microsoft (MIT). Fixed source commit:
1541f590c7099820f10ea012f48d2399282df69f.
The Runtime retains the official inference code and its license. This Package
retains six voice presets converted to safetensors without tensor changes;
resources/vibevoice/official-voices-safe/manifest.json records original and
converted hashes and exact roundtrip evidence. No pickle presets or converter
are executed by the installed Package.

Qwen/Qwen2.5-0.5B tokenizer assets are fixed at
060db6499f32faf8b98477b0a26969ef7d8b9987; its license is retained separately in
licenses/Qwen-tokenizer-LICENSE.txt and with the tokenizer files.
Main microsoft/VibeVoice-Realtime-0.5B weights remain external and unmodified.
