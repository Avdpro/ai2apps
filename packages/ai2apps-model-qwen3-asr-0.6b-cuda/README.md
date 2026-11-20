# Qwen3 ASR 0.6B CUDA

CUDA/Transformers speech-recognition Model Worker for AI2Apps Spark. The
checkpoint is installed separately in the shared Hugging Face cache and pinned
to an immutable upstream revision. Worker execution has no outbound network.

The signed adapter includes the upstream `chat_template.jinja` from
`Qwen/Qwen3-ASR-0.6B-hf@e8cb6ff5b151ad5c0e49bf9328a9d628efb5def2`
(Apache-2.0), SHA-256 `a103579066642f0e035873f12de6046a1bbc909a7a2833732fda9fd6bc7c528d`.
It supplies the processor template omitted by the existing six-file distribution,
without modifying the shared checkpoint or downloading files inside a Worker.
