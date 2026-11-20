# VibeVoice Realtime CUDA — development source

Official BF16 CUDA synthesis with six English voice presets, offline tokenizer,
seeded generation and the existing ten-minute output guard. No cloning, speed,
emotion, instructions, multi-speaker or streaming support is claimed.
The Runtime owns the official model implementation and dependencies; this
Package owns the fixed tokenizer and safetensors voice assets with licenses.

Main weights remain external. Their fixed Registry distribution is not yet
published, so weights.distribution_id remains absent. Runtime >=0.6.0,
signed Package installation and real installed synthesis remain release gates.
